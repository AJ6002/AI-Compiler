# ADR-006: Secure Admission & Defensive Archive Inspection

## Status
Accepted

## Context
Spreadsheet uploads from industrial clients are untrusted data payloads that may contain malicious structures such as ZIP bombs (extreme compression ratios or exponential file expansion), directory traversal sequences (`../../etc/passwd`), password-protected streams, or corrupt binaries masquerading as `.xlsx` files. Parsing unverified archives with heavy spreadsheet libraries exposes the service to memory exhaustion, process crashes, and arbitrary filesystem access.

## Decision
1. **Admission Gate as First Line of Defense:** All uploads must pass through `AdmissionGate` before any spreadsheet reader or parsing library is invoked.
2. **Strict Verification Rules:**
   - **Magic Bytes Validation:** Verify PKZIP signature `PK\x03\x04` regardless of file extension or HTTP Content-Type headers.
   - **Path Traversal Guard:** Entry paths containing `..`, absolute indicators, leading slashes, or Windows drive prefixes are immediately rejected with `ERR_ADM_PATH_TRAVERSAL`.
   - **Expansion & Zip Bomb Ceilings:** Limit cumulative uncompressed expansion to 500 MB, single entry expansion to 100 MB, entry count to 100 files, and expansion ratio to 100:1.
   - **Unsupported Features:** Encrypted entries and nested ZIP archives are explicitly rejected.
3. **Immutable Raw Storage:** Accepted uploads are stored without mutation in an isolated object store partitioned by `raw/{tenant_id}/{project_id}/{object_id}.bin` with calculated SHA-256 digests.
4. **Hard Phase Boundary:** Rejected payloads emit structured `ValidationErrorItem` records and are strictly prohibited from progressing to reader workers.

## Consequences
- Heavy parsing engines (openpyxl, POI, Python unzippers) only process sanitized, bounds-checked payloads.
- All admission events produce deterministic `UploadManifest` records.
