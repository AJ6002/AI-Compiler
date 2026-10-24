"""Deterministic activities for ingestion, discovery, execution, and publication."""

from __future__ import annotations

import datetime
import io
import uuid
import zipfile

import pyarrow.parquet as pq

from src.compiler.admission.gate import AdmissionGate
from src.compiler.admission.models import AdmissionResult
from src.compiler.batch.assembler import BatchAssembler
from src.compiler.batch.types import BatchAssemblyResult, FileProcessingOutcome
from src.compiler.contracts.client import ClientContract
from src.compiler.contracts.enums import (
    ArchiveType,
    ErrorCode,
    ErrorSeverity,
    JobResultState,
    PlanOperationType,
)
from src.compiler.contracts.manifests import HandoffManifest
from src.compiler.contracts.plans import ParsePlan, PlanOperation
from src.compiler.contracts.validation import ValidationErrorItem, ValidationReport
from src.compiler.execution.executor import PlanExecutor
from src.compiler.plans.compiler import PlanCompiler
from src.compiler.readers.openpyxl_reader import OpenpyxlReader
from src.compiler.recipes.registry import RecipeRegistry
from src.compiler.recipes.review import ReviewItem, ReviewQueue
from src.compiler.recipes.signatures import DriftDetector, SignatureGenerator
from src.compiler.storage.object_store import ObjectStore
from src.compiler.structure.discovery_engine import RuleBasedDiscoveryEngine
from src.compiler.structure.types import DiscoveredLayout
from src.compiler.validation.gate import ClientValidationGate
from src.compiler.validation.plan_validator import PlanValidator
from src.compiler.workflows.errors import DeterministicSourceFault
from src.compiler.workflows.models import HandoffEvent, JobRecord
from src.compiler.workflows.outbox import HandoffOutbox


class IngestionActivities:
    """Deterministic activities executed within the compiler workflow engine."""

    def __init__(
        self,
        object_store: ObjectStore,
        recipe_registry: RecipeRegistry | None = None,
        review_queue: ReviewQueue | None = None,
        outbox: HandoffOutbox | None = None,
        reader: OpenpyxlReader | None = None,
        discovery: RuleBasedDiscoveryEngine | None = None,
        compiler: PlanCompiler | None = None,
        executor: PlanExecutor | None = None,
        validation_gate: ClientValidationGate | None = None,
        plan_validator: PlanValidator | None = None,
        batch_assembler: BatchAssembler | None = None,
    ) -> None:
        self.store = object_store
        self.recipe_registry = recipe_registry or RecipeRegistry()
        self.review_queue = review_queue or ReviewQueue()
        self.outbox = outbox or HandoffOutbox()
        self.reader = reader or OpenpyxlReader()
        self.discovery = discovery or RuleBasedDiscoveryEngine()
        self.compiler = compiler or PlanCompiler()
        self.executor = executor or PlanExecutor(reader=self.reader)
        self.gate = validation_gate or ClientValidationGate()
        self.plan_validator = plan_validator or PlanValidator(
            executor=self.executor, gate=self.gate, reader=self.reader
        )
        self.batch_assembler = batch_assembler or BatchAssembler()

    def admission_activity(
        self,
        job: JobRecord,
        raw_bytes: bytes,
        filename: str,
    ) -> AdmissionResult:
        """Admit raw payload, verify security boundaries, and store immutably."""
        gate = AdmissionGate(self.store)
        result = gate.admit(
            raw_bytes=raw_bytes,
            filename=filename,
            tenant_id=job.tenant_id,
            project_id=job.project_id,
        )
        if result.status == JobResultState.FAILED:
            raise DeterministicSourceFault(f"Admission rejected: {result.summary}")
        return result

    def discovery_activity(
        self,
        job: JobRecord,
        admission: AdmissionResult,
    ) -> list[tuple[str, bytes, DiscoveredLayout]]:
        """Inspect and discover structural layout for each file in upload."""
        discovered: list[tuple[str, bytes, DiscoveredLayout]] = []

        manifest = admission.manifest
        if not manifest:
            raise DeterministicSourceFault("Missing admission manifest.")

        # Determine archive vs single file
        storage_key = f"raw/{job.tenant_id}/{job.project_id}/{admission.object_id}.bin"
        if manifest.archive_type == ArchiveType.ZIP_ARCHIVE:
            raw_archive = self.store.get(storage_key)
            with zipfile.ZipFile(io.BytesIO(raw_archive), "r") as zf:
                for file_entry in manifest.files:
                    fname = file_entry.relative_path
                    fbytes = zf.read(fname)
                    structure = self.reader.inspect(
                        source=fbytes,
                        tenant_id=job.tenant_id,
                        project_id=job.project_id,
                        workbook_name=fname,
                    )
                    layout = self.discovery.discover_sheet(structure.sheets[0])
                    discovered.append((fname, fbytes, layout))
        else:
            file_entry = manifest.files[0]
            raw_file = self.store.get(storage_key)
            structure = self.reader.inspect(
                source=raw_file,
                tenant_id=job.tenant_id,
                project_id=job.project_id,
                workbook_name=file_entry.relative_path,
            )
            layout = self.discovery.discover_sheet(structure.sheets[0])
            discovered.append((file_entry.relative_path, raw_file, layout))

        return discovered

    def plan_resolution_activity(
        self,
        job: JobRecord,
        discoveries: list[tuple[str, bytes, DiscoveredLayout]],
    ) -> list[tuple[str, bytes, DiscoveredLayout, ParsePlan | None, ReviewItem | None]]:
        """Resolve recipes via structural signatures or compile candidate plans."""
        resolved: list[
            tuple[str, bytes, DiscoveredLayout, ParsePlan | None, ReviewItem | None]
        ] = []

        for fname, fbytes, layout in discoveries:
            if not layout.tables or layout.verdict != JobResultState.ACCEPTED:
                # Structural failure -> needs review item
                review_item = self.review_queue.enqueue(
                    tenant_id=job.tenant_id,
                    project_id=job.project_id,
                    target_object_id=fname,
                    sheet_name=layout.sheet_name,
                    discovered_headers=[],
                    draft_plan=ParsePlan(
                        tenant_id=job.tenant_id,
                        project_id=job.project_id,
                        plan_id=f"plan_unresolved_{uuid.uuid4().hex[:8]}",
                        target_sheet=layout.sheet_name,
                        operations=[
                            PlanOperation(
                                op=PlanOperationType.SELECT_REGION,
                                params={"min_row": 1, "max_row": 1, "min_col": 1, "max_col": 1},
                            )
                        ],
                    ),
                    validation_errors=[
                        ValidationErrorItem(
                            code=ErrorCode.ERR_STRUCT_DISPERSED_REGIONS,
                            severity=ErrorSeverity.ERROR,
                            message=(
                                f"No valid data tables discovered in sheet '{layout.sheet_name}'."
                            ),
                            remediation="Steward layout verification required.",
                        )
                    ],
                )
                resolved.append((fname, fbytes, layout, None, review_item))
                continue

            sig = SignatureGenerator.from_layout(layout)
            recipe = self.recipe_registry.lookup(job.tenant_id, sig, allow_templates=True)

            if recipe:
                drift = DriftDetector.detect(recipe.signature, sig)
                if not drift.has_drift:
                    resolved.append((fname, fbytes, layout, recipe.plan, None))
                    continue

            # No recipe or drift detected -> compile fresh plan and validate
            asset_id = layout.sheet_name
            plan = self.compiler.compile(
                layout=layout,
                tenant_id=job.tenant_id,
                project_id=job.project_id,
                default_asset_id=asset_id,
            )

            # Pass through 3-level PlanValidator before acceptance
            val_rep = self.plan_validator.validate(
                plan=plan,
                source=fbytes,
                layout=layout,
                source_filename=fname,
                default_asset_id=asset_id,
            )

            if val_rep.status != JobResultState.ACCEPTED:
                review_item = self.review_queue.enqueue(
                    tenant_id=job.tenant_id,
                    project_id=job.project_id,
                    target_object_id=fname,
                    sheet_name=layout.sheet_name,
                    discovered_headers=[c.path for t in layout.tables for c in t.columns],
                    candidate_recipe_id=None,
                    validation_errors=[
                        ValidationErrorItem(
                            code=iss.code,
                            severity=ErrorSeverity.ERROR,
                            message=f"[{iss.level}] {iss.message}",
                            sheet=layout.sheet_name,
                            cell_coordinate=iss.source_reference,
                            remediation="Review proposed plan transformations.",
                        )
                        for iss in val_rep.issues
                    ],
                )
                resolved.append((fname, fbytes, layout, None, review_item))
            else:
                resolved.append((fname, fbytes, layout, plan, None))

        return resolved

    def execution_and_validation_activity(
        self,
        job: JobRecord,
        contract: ClientContract,
        resolved: list[tuple[str, bytes, DiscoveredLayout, ParsePlan | None, ReviewItem | None]],
    ) -> list[FileProcessingOutcome]:
        """Execute resolved plans through Arrow executor and ClientValidationGate."""
        outcomes: list[FileProcessingOutcome] = []

        for fname, fbytes, layout, plan, review_item in resolved:
            if review_item is not None or plan is None:
                # File was defective in discovery
                rep = ValidationReport(
                    report_id=f"rep_{uuid.uuid4().hex[:8]}",
                    tenant_id=job.tenant_id,
                    project_id=job.project_id,
                    target_object_id=fname,
                    result_state=JobResultState.REVIEW_REQUIRED,
                    errors=review_item.validation_errors if review_item else [],
                )
                outcomes.append(
                    FileProcessingOutcome(
                        filename=fname,
                        object_id=f"obj_{fname}",
                        sha256=f"sha_{fname}",
                        result_state=JobResultState.REVIEW_REQUIRED,
                        validation_report=rep,
                    )
                )
                continue

            # Execute plan
            asset_id = layout.sheet_name
            exec_result = self.executor.execute(
                source=fbytes,
                plan=plan,
                source_filename=fname,
                default_asset_id=asset_id,
            )

            # Validate output
            val_report = self.gate.validate(
                execution_result=exec_result,
                contract=contract,
                target_object_id=fname,
                discovered_layout=layout,
            )

            # If validation gate rejected, enqueue in review queue
            if val_report.result_state != JobResultState.ACCEPTED:
                self.review_queue.enqueue(
                    tenant_id=job.tenant_id,
                    project_id=job.project_id,
                    target_object_id=fname,
                    sheet_name=layout.sheet_name,
                    discovered_headers=[c.path for t in layout.tables for c in t.columns],
                    draft_plan=plan,
                    validation_errors=val_report.errors,
                    validation_warnings=val_report.warnings,
                )

            outcomes.append(
                FileProcessingOutcome(
                    filename=fname,
                    object_id=f"obj_{fname}",
                    sha256=f"sha_{fname}",
                    result_state=val_report.result_state,
                    validation_report=val_report,
                    execution_result=exec_result,
                    asset_id=asset_id,
                )
            )

        return outcomes

    def batch_publish_activity(
        self,
        job: JobRecord,
        contract: ClientContract,
        outcomes: list[FileProcessingOutcome],
    ) -> BatchAssemblyResult:
        """Assemble multi-file batch, publish accepted Parquet tables, and emit handoff event."""
        dataset_id = job.dataset_id or f"ds_{uuid.uuid4().hex[:12]}"

        # 1. Assemble batch
        batch_result = self.batch_assembler.assemble(
            batch_id=job.job_id,
            contract=contract,
            outcomes=outcomes,
        )

        # 2. Stage and publish Parquet tables if present
        meas_uri = ""
        prov_uri = ""
        table_uris: list[str] = []

        if batch_result.batch_measurements_table is not None:
            meas_buf = io.BytesIO()
            pq.write_table(batch_result.batch_measurements_table, meas_buf)
            meas_bytes = meas_buf.getvalue()

            # Atomic commit to published storage
            base_dir = f"{job.tenant_id}/{job.project_id}/published/{dataset_id}"
            meas_key = f"{base_dir}/tables/batch-measurements.parquet"
            meas_uri = self.store.put(meas_key, meas_bytes)
            table_uris.append(meas_uri)

        if batch_result.batch_provenance_table is not None:
            prov_buf = io.BytesIO()
            pq.write_table(batch_result.batch_provenance_table, prov_buf)
            prov_bytes = prov_buf.getvalue()

            base_dir = f"{job.tenant_id}/{job.project_id}/published/{dataset_id}"
            prov_key = f"{base_dir}/provenance/batch-source-map.parquet"
            prov_uri = self.store.put(prov_key, prov_bytes)

        # 3. Write validation report
        val_rep_key = (
            f"{job.tenant_id}/{job.project_id}/published/{dataset_id}/validation-report.json"
        )
        val_rep_json = batch_result.batch_validation_report.model_dump_json(indent=2).encode(
            "utf-8"
        )
        val_rep_uri = self.store.put(val_rep_key, val_rep_json)

        # 4. Write handoff manifest
        coverage: dict[str, float] = {}
        for sig in contract.required_signals:
            coverage[sig] = 1.0 if batch_result.result_state == JobResultState.ACCEPTED else 0.8

        handoff = HandoffManifest(
            tenant_id=job.tenant_id,
            project_id=job.project_id,
            handoff_id=f"hnd_{uuid.uuid4().hex[:12]}",
            dataset_id=dataset_id,
            result_state=batch_result.result_state,
            compiler_version="0.1.0",
            contract_version=contract.version,
            measurement_tables=table_uris if table_uris else ["none"],
            signal_dictionary_uri="embedded",
            provenance_map_uri=prov_uri or "none",
            validation_report_uri=val_rep_uri,
            signal_coverage=coverage,
            assets_expected=batch_result.batch_validation_report.files_expected,
            assets_accepted=batch_result.batch_validation_report.files_accepted,
            assets_missing=batch_result.batch_validation_report.files_missing,
        )

        handoff_key = f"{job.tenant_id}/{job.project_id}/published/{dataset_id}/handoff.json"
        handoff_uri = self.store.put(handoff_key, handoff.model_dump_json(indent=2).encode("utf-8"))

        # 5. Emit Outbox Event
        event = HandoffEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            job_id=job.job_id,
            tenant_id=job.tenant_id,
            project_id=job.project_id,
            dataset_id=dataset_id,
            result_state=batch_result.result_state,
            handoff_manifest_uri=handoff_uri,
            payload_sha256=handoff.source_sha256
            if hasattr(handoff, "source_sha256")
            else "sha_published",
            emitted_at=datetime.datetime.now(datetime.UTC),
            delivered=False,
        )
        self.outbox.emit(event)

        return batch_result
