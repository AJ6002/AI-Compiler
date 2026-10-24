# Zero Ungrounded Stubs — Mandatory CCED Policy

## Rule
No frontend view, route, component, or store in this repository may display synthetic, hardcoded, placeholder, or outsourced data that is not backed 1:1 by authoritative CCED backend files or live Port 8000 SCADA telemetry.

## Authoritative Backing Sources
1. **Cluster Mapping**: `ESP_Catalog_13_Well_Cluster_Mapping.json` (13 anchor clusters, flow regimes, and 170 field well mappings).
2. **Diagnostic Formulae**: `ESP_Catalog_Master_Formulae_Catalog.json` (43 verified equations, symbols, units, and site origins).
3. **Telemetry & Assets**: Live SCADA services on Port 8000 (`/api/collector/status`, `/api/esp/assets`, `/api/esp/telemetry/live`) connected to MQTT `:1883`.

## Prohibited Behaviors
- **NO Outsourced Catalogs**: Never import or synthesize pump curves or equipment specs from web mirrors (e.g. `SRC-WEB-BORETS-2017-CATALOG` / `pdfcoffee.com`).
- **NO Fabricated Records**: Never inline motor nameplates, cable types, VSD models, or sensors unless present in the CCED master files.
- **NO Phantom Alerts**: Never hardcode active field alerts or issue lists (e.g. `ISSUE-FS-96`). Alerts must originate dynamically from live SCADA threshold trips.
- **NO Empty/Hollow Tabs**: If backend files lack data for an equipment class or feature (e.g. Fluid/PVT or Operating Limits), omit the tab or render an explicit "Unassigned in Master Record" message.
