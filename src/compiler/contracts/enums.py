"""Enumerations for execution lifecycle, results, error codes, and operational policies."""

from enum import StrEnum


class JobExecutionState(StrEnum):
    """Workflow execution states tracking task lifecycle progress."""

    RECEIVED = "RECEIVED"
    INSPECTING = "INSPECTING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobResultState(StrEnum):
    """Qualitative verdict on whether parsed dataset meets acceptance criteria."""

    ACCEPTED = "ACCEPTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


class ErrorSeverity(StrEnum):
    """Severity classification for validation reports and admission alerts."""

    FATAL = "FATAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class UnitSource(StrEnum):
    """Where unit information was discovered."""

    HEADER_ROW = "header_row"
    METADATA_BLOCK = "metadata_block"
    CLIENT_CONTRACT = "client_contract"
    UNKNOWN = "unknown"


class ErrorCode(StrEnum):
    """Structured error codes with distinct diagnostic domains."""

    # Admission & Security
    ERR_ADM_PATH_TRAVERSAL = "ERR_ADM_PATH_TRAVERSAL"
    ERR_ADM_ZIP_BOMB = "ERR_ADM_ZIP_BOMB"
    ERR_ADM_FILE_CORRUPT = "ERR_ADM_FILE_CORRUPT"
    ERR_ADM_UNSUPPORTED_FORMAT = "ERR_ADM_UNSUPPORTED_FORMAT"
    ERR_ADM_MAX_SIZE_EXCEEDED = "ERR_ADM_MAX_SIZE_EXCEEDED"

    # Structure & Discovery
    ERR_STRUCT_AMBIGUOUS_HEADER = "ERR_STRUCT_AMBIGUOUS_HEADER"
    ERR_STRUCT_DISPERSED_REGIONS = "ERR_STRUCT_DISPERSED_REGIONS"
    ERR_STRUCT_DUPLICATE_COLUMNS = "ERR_STRUCT_DUPLICATE_COLUMNS"
    ERR_STRUCT_MISSING_SHEET = "ERR_STRUCT_MISSING_SHEET"

    # Validation & Quality
    ERR_VAL_SCHEMA_VIOLATION = "ERR_VAL_SCHEMA_VIOLATION"
    ERR_VAL_UNRESOLVED_UNIT = "ERR_VAL_UNRESOLVED_UNIT"
    ERR_VAL_TIMEZONE_AMBIGUOUS = "ERR_VAL_TIMEZONE_AMBIGUOUS"
    ERR_VAL_CADENCE_IRREGULAR = "ERR_VAL_CADENCE_IRREGULAR"
    ERR_VAL_MISSING_SIGNAL = "ERR_VAL_MISSING_SIGNAL"
    ERR_VAL_MISSING_ASSET = "ERR_VAL_MISSING_ASSET"
    ERR_VAL_CROSS_FILE_DISAGREEMENT = "ERR_VAL_CROSS_FILE_DISAGREEMENT"
    ERR_VAL_STALE_CONTRACT = "ERR_VAL_STALE_CONTRACT"

    # Plan Execution
    ERR_EXEC_UNSUPPORTED_OP = "ERR_EXEC_UNSUPPORTED_OP"
    ERR_EXEC_INVALID_RANGE = "ERR_EXEC_INVALID_RANGE"
    ERR_EXEC_ROW_MULTIPLICATION = "ERR_EXEC_ROW_MULTIPLICATION"
    ERR_EXEC_PARTIAL_RESULT = "ERR_EXEC_PARTIAL_RESULT"


class PlanOperationType(StrEnum):
    """Allowlisted transformation operations."""

    SELECT_REGION = "select_region"
    FLATTEN_HEADERS = "flatten_headers"
    UNPIVOT = "unpivot"
    TYPE_CAST = "type_cast"
    PARSE_DURATION = "parse_duration"
    FORMULA_POLICY = "formula_policy"
    FILTER_ROWS = "filter_rows"


class SharingTier(StrEnum):
    """Recipe applicability tier."""

    TENANT_BOUND = "tenant_bound"
    TEMPLATE = "template"


class ArchiveType(StrEnum):
    """Supported admission payload types."""

    SINGLE_XLSX = "single_xlsx"
    ZIP_ARCHIVE = "zip_archive"


class DuplicatePolicy(StrEnum):
    """Handling policy when identical timestamps appear on the same asset."""

    PRESERVE_DISTINCT_OBSERVATIONS = "preserve_distinct_observations"
    ERROR_ON_DISAGREEMENT = "error_on_disagreement"


class PartialBatchPolicy(StrEnum):
    """Handling policy for batches with mixed accepted and review files."""

    PUBLISH_ACCEPTED_FLAG_REVIEW = "publish_accepted_flag_review"
    BLOCK_ENTIRE_BATCH = "block_entire_batch"
    PUBLISH_ACCEPTED_SPLIT_DATASET = "publish_accepted_split_dataset"


class DateEpoch(StrEnum):
    """Workbook base date epoch."""

    EPOCH_1900 = "1900"
    EPOCH_1904 = "1904"
