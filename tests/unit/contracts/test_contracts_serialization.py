from datetime import UTC, datetime

from src.compiler.contracts import (
    ArchiveType,
    AssetMap,
    BatchValidationReport,
    ClientContract,
    DateEpoch,
    DuplicatePolicy,
    ErrorCode,
    ErrorSeverity,
    FileEntry,
    HandoffManifest,
    JobResultState,
    ObservationId,
    ParsePlan,
    PartialBatchPolicy,
    PlanOperation,
    PlanOperationType,
    Recipe,
    RegionBoundary,
    SheetStructure,
    SignalDefinition,
    SignalDictionary,
    StructuralSignature,
    UploadManifest,
    ValidationErrorItem,
    ValidationReport,
    WorkbookStructure,
)


def test_observation_id_serialization_and_key():
    now = datetime(2026, 10, 22, 12, 0, 0, tzinfo=UTC)
    obs = ObservationId(
        tenant_id="tenant_alpha",
        project_id="project_beta",
        asset_id="COMPRESSOR_101",
        timestamp_utc=now,
        raw_source_row=42,
        source_file="october_data.xlsx",
    )
    json_data = obs.model_dump_json()
    reloaded = ObservationId.model_validate_json(json_data)
    assert reloaded == obs
    assert len(obs.observation_key) == 64  # SHA-256 length


def test_upload_manifest_roundtrip():
    manifest = UploadManifest(
        tenant_id="tenant_alpha",
        project_id="project_beta",
        upload_id="upl_12345",
        archive_type=ArchiveType.ZIP_ARCHIVE,
        uploaded_at=datetime.now(UTC),
        total_files=2,
        total_compressed_bytes=1048576,
        files=[
            FileEntry(
                relative_path="file_1.xlsx",
                sha256="abc123def456",
                byte_size=524288,
                mime_type_detected="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            FileEntry(
                relative_path="file_2.xlsx",
                sha256="789xyz123abc",
                byte_size=524288,
                mime_type_detected="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        ],
    )
    dumped = manifest.model_dump_json()
    loaded = UploadManifest.model_validate_json(dumped)
    assert loaded == manifest


def test_client_contract_roundtrip():
    contract = ClientContract(
        tenant_id="tenant_alpha",
        project_id="project_beta",
        contract_id="contract_001",
        version="1.0.0",
        expected_assets=["COMP_1", "COMP_2"],
        required_signals=["DISPENSER_1.PRESSURE", "DISPENSER_1.FLOW_RATE"],
        optional_signals=["DISPENSER_1.TEMPERATURE"],
        allowed_units={"DISPENSER_1.PRESSURE": ["bar", "psi"], "DISPENSER_1.FLOW_RATE": ["m3/h"]},
        timezone="UTC",
        expected_cadence_seconds=60,
        duplicate_timestamp_policy=DuplicatePolicy.PRESERVE_DISTINCT_OBSERVATIONS,
        partial_batch_policy=PartialBatchPolicy.PUBLISH_ACCEPTED_FLAG_REVIEW,
    )
    dumped = contract.model_dump_json()
    loaded = ClientContract.model_validate_json(dumped)
    assert loaded == contract


def test_signal_dictionary_and_asset_map():
    sig_dict = SignalDictionary(
        tenant_id="tenant_alpha",
        project_id="project_beta",
        dictionary_id="sig_dict_01",
        version="1.0.0",
        signals={
            "SIG_PRESS": SignalDefinition(
                signal_id="SIG_PRESS",
                canonical_path="COMPRESSOR_1.PRESSURE",
                canonical_unit="bar",
                data_type="numeric",
            )
        },
    )
    assert SignalDictionary.model_validate_json(sig_dict.model_dump_json()) == sig_dict

    asset_map = AssetMap(
        tenant_id="tenant_alpha",
        project_id="project_beta",
        map_id="map_01",
        version="1.0.0",
        mappings={"PNB950667": "COMPRESSOR_1"},
    )
    assert AssetMap.model_validate_json(asset_map.model_dump_json()) == asset_map


def test_parse_plan_and_recipe():
    plan = ParsePlan(
        tenant_id="tenant_alpha",
        project_id="project_beta",
        plan_id="plan_01",
        target_sheet="Sheet1",
        operations=[
            PlanOperation(
                op=PlanOperationType.SELECT_REGION,
                params={"min_row": 2, "max_row": 100},
            ),
            PlanOperation(
                op=PlanOperationType.UNPIVOT,
                params={"id_vars": ["TIMESTAMP"], "value_vars": ["PRESS", "TEMP"]},
            ),
        ],
    )
    assert ParsePlan.model_validate_json(plan.model_dump_json()) == plan

    recipe = Recipe(
        tenant_id="tenant_alpha",
        project_id="project_beta",
        recipe_id="recipe_01",
        version="1.0.0",
        generation_system="Honeywell_DCS_v4",
        signature=StructuralSignature(
            sheet_names=["Sheet1"],
            header_patterns=["TIMESTAMP", "PRESS", "TEMP"],
            min_columns=3,
        ),
        plan=plan,
        approved_by="data_steward_jane",
        approved_at=datetime.now(UTC),
    )
    assert Recipe.model_validate_json(recipe.model_dump_json()) == recipe


def test_validation_reports_and_handoff():
    val_report = ValidationReport(
        tenant_id="tenant_alpha",
        project_id="project_beta",
        report_id="rep_01",
        target_object_id="obj_file_1",
        result_state=JobResultState.REVIEW_REQUIRED,
        errors=[
            ValidationErrorItem(
                code=ErrorCode.ERR_VAL_UNRESOLVED_UNIT,
                severity=ErrorSeverity.ERROR,
                message="Unit missing for signal PRESSURE",
                sheet="Sheet1",
                remediation="Specify unit mapping in ClientContract or header row",
            )
        ],
    )
    assert ValidationReport.model_validate_json(val_report.model_dump_json()) == val_report

    batch_report = BatchValidationReport(
        tenant_id="tenant_alpha",
        project_id="project_beta",
        batch_id="batch_01",
        result_state=JobResultState.REVIEW_REQUIRED,
        files_expected=5,
        files_found=5,
        files_accepted=4,
        files_review_required=1,
        files_missing=[],
        per_file_statuses={"f1": JobResultState.ACCEPTED, "f2": JobResultState.REVIEW_REQUIRED},
    )
    assert BatchValidationReport.model_validate_json(batch_report.model_dump_json()) == batch_report

    handoff = HandoffManifest(
        tenant_id="tenant_alpha",
        project_id="project_beta",
        handoff_id="hnd_01",
        dataset_id="ds_2026_10",
        result_state=JobResultState.ACCEPTED,
        compiler_version="0.1.0",
        contract_version="1.0.0",
        measurement_tables=["s3://bucket/tables/m1.parquet"],
        signal_dictionary_uri="s3://bucket/dictionaries/signals.parquet",
        provenance_map_uri="s3://bucket/provenance/source-map.parquet",
        validation_report_uri="s3://bucket/reports/validation-report.json",
        assets_expected=4,
        assets_accepted=4,
    )
    assert HandoffManifest.model_validate_json(handoff.model_dump_json()) == handoff


def test_workbook_structure():
    struct = WorkbookStructure(
        tenant_id="tenant_alpha",
        project_id="project_beta",
        source_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        workbook_name="factory_readings.xlsx",
        date_epoch=DateEpoch.EPOCH_1900,
        sheets=[
            SheetStructure(
                name="Readings",
                index=0,
                max_row=500,
                max_col=10,
                merged_ranges=["A1:D1"],
                candidate_regions=[RegionBoundary(min_row=2, max_row=500, min_col=1, max_col=10)],
            )
        ],
    )
    assert WorkbookStructure.model_validate_json(struct.model_dump_json()) == struct
