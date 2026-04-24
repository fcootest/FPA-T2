# POST-IMPLEMENTATION AUDIT REPORT
**Module:** FPA-T2 RI — Plan Input Config & Entry
**AP Reference:** AP_FPA-T2_RI_V10_20260424.md
**ISP Reference:** IncrementalStepPlan-FPA-T2-RI.md
**Code base:** `C:\Users\Administrator\Documents\Test_Calude\FPA-T2-Code`
**Auditor:** Claude Sonnet 4.6 | **Date:** 2026-04-24

> **layerevent.md not found in repo.** Classification uses AP §7 taxonomy:
> - **A** = UI/API only — no Entity Schema change
> - **B** = Entity Schema change, no Layer Event read/write, no CalculateKR/ExtractEvent
> - **C** = Layer Event or CalculateKR read/write (out of scope for this module)

---

## SECTION 1: SUMMARY

| Category | Count |
|----------|-------|
| **Missing** | 8 |
| **Extra** | 0 |
| **Incorrect** | 13 |
| **Total findings** | **21** |

**Overall status: ❌ FAIL**

3 critical bugs (ID-01, ID-02, ID-03) prevent the PPR DOWN→UP pipeline from functioning correctly in production. The `load_for_ui` function permanently returns empty results due to a missing BQ column write. Flow F3 (reload saved entry) is completely broken.

---

## SECTION 2: DETAILED AUDIT LIST

---

### ID-01 — WriteSORow missing `z_block_zblock1_pack`

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | B |
| **Component** | `backend/services/ppr_service.py` — `WriteSORow()` |
| **Impact** | **High** |

**Description:**
`z_block_zblock1_pack` (PCK code) is never written to `so_rows_pca`. All 6 other Z-Block fields are written, but PCK is silently dropped.

**Expected (AP §1.1, §5.8.3):**
Z-Block = 7 fields: `z_block_zblock1_{category, pack, scenario, source, frequency, run}` + `now_zblock2_alt`. `WriteSORow` must persist all 7.

**Actual (code):**
`ppr_service.py:116–127` builds `bq_row` with `category`, `scenario`, `source`, `frequency`, `run`, `now_zblock2_alt`, `now_y_block_fnf_fnf` — `z_block_zblock1_pack` is absent.

**Violation:** ArchitecturePack §1.1, §5.8.3

**Consequence:**
`load_for_ui` WHERE clause (`ppr_service.py:293`) reconstructs `zb_full_code` via:
```sql
CONCAT(z_block_zblock1_category, '-', z_block_zblock1_pack, '-', ...)
```
Because PCK is never written, the CONCAT produces `"CAT--SRC-FF-ALT-SCN-RUN"` (double dash), which never matches the stored `zb_full_code`. **PPR UP returns zero rows permanently.**

**Recommendation:**
1. Add `"z_block_zblock1_pack": ri_row.pck_code` to `bq_row` in `WriteSORow`.
2. Fix ID-02 first to ensure `ri_row.pck_code` is populated.

---

### ID-02 — RIRow z_block fields never populated in `RICellToRIRow`

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | B |
| **Component** | `backend/services/ppr_service.py` — `RICellToRIRow()` |
| **Impact** | **High** |

**Description:**
`RIRow` is created with `cat_code`, `pck_code`, `src_code`, `ff_code`, `alt_code`, `scn_code`, `run_code`, `fnf` all as empty strings `""`. These are never populated from `zb_full_code`.

**Expected (AP §5.8.2, §5.8.3):**
`RIRow` must carry the decomposed Z-Block fields so `WriteSORow` can write them as individual BQ columns.

**Actual (code):**
`ppr_service.py:83–96` — `RICellToRIRow` sets only `zb_full_code` and `yb_full_code`; all `*_code` decomposed fields remain `""`. `WriteSORow` then writes empty strings for all Z-Block columns.

**Violation:** ArchitecturePack §5.8.2, §5.8.3

**Recommendation:**
After creating `RIRow` in `RICellToRIRow`, decompose `zb_full_code` by splitting on the known 7-part structure `CAT-PCK-SRC-FF-ALT-SCN-RUN{date}-{time}`. Pass decomposed codes, or accept a `zb_full: ZBFull` argument that carries pre-decomposed parts.

```python
# Example fix in RICellToRIRow or caller:
parts = zb_full_code.split("-")
# cat=parts[0], pck=parts[1], src=parts[2], ff=parts[3],
# alt=parts[4], scn=parts[5], run="-".join(parts[6:])
```

---

### ID-03 — `GET /api/ri/entries/{id}` returns no cells

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | A |
| **Component** | `backend/routers/ri_entry.py:39–43` |
| **Impact** | **High** |

**Description:**
Endpoint returns only the `RIScreenEntry` record. AP requires returning the entry **plus cells** so the UI can re-render the grid on reload (Flow F3).

**Expected (AP §2.4 #8, §4.4 F3.2):**
`GET /api/ri/entries/{id}` → `entry + cells` (cell values for re-rendering the grid).

**Actual (code):**
```python
return entry_svc._get_entry(client, entry_id).model_dump(mode="json")
```
No cells returned.

**Violation:** ArchitecturePack §2.4 #8, §4.4 F3

**Recommendation:**
```python
@router.get("/{entry_id}")
async def get_entry(entry_id: str):
    client = get_bq_client()
    entry = entry_svc._get_entry(client, entry_id)
    cells = entry_svc.get_entry_display(client, entry_id)
    return {
        "entry": entry.model_dump(mode="json"),
        "cells": [c.model_dump(mode="json") for c in cells],
    }
```

---

### ID-04 — `save_entry` inserts RICell rows missing Z-Block metadata

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | B |
| **Component** | `backend/services/ri_entry_service.py:132–143` |
| **Impact** | **Medium** |

**Description:**
`so_cell_v1` rows are inserted without any Z-Block metadata (`z_block_zblock1_*`). Only `entry_id`, `yb_full_code`, `xperiod_code`, `zb_full_code`, `now_value`, `now_y_block_fnf_fnf` are written.

**Expected (AP §1.1 #4):**
`RICell` mirrors `so_cell_v1` (109 cols). Now-Block (57 fields) includes `z_block_zblock1_{category,pack,scenario,source,frequency,run}` + `now_zblock2_alt`.

**Violation:** ArchitecturePack §1.1 #4

**Recommendation:**
Parse `req.cat`, `req.pck`, `req.src`, `req.ff`, `req.alt` from the request and the SCN from each entry's `zb_full_code`. Add all Z-Block fields to `ri_cell_rows` dict.

---

### ID-05 — Master table naming: `master_*` vs `ri_master_*`

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | B |
| **Component** | `backend/migrations/bq_migrate.py`, `backend/routers/ri_masters.py` |
| **Impact** | **Medium** |

**Description:**
All master tables are named `master_*` (e.g., `master_cat`). ISP Step 3 specifies prefix `ri_master_*`.

**Expected (ISP Step 3):**
Tables `ri_master_cat`, `ri_master_pck`, `ri_master_src`, `ri_master_ff`, `ri_master_alt`, `ri_master_scn`, `ri_master_run`.

**Actual (code):**
`bq_migrate.py:72–117` defines `master_cat`, `master_pck`, etc.

**Violation:** IncrementalStepPlan Step 3

**Recommendation:**
Standardize to one convention. If `ri_master_*` is chosen (follows ISP), rename all table references in `bq_migrate.py`, `seed_masters.py`, and `ri_masters.py`. Document the chosen convention.

---

### ID-06 — `ensure_tables()` not called at startup

| Field | Value |
|-------|-------|
| **Type** | Missing |
| **Classification** | B |
| **Component** | `backend/main.py:11–15` |
| **Impact** | **Medium** |

**Description:**
`ensure_tables()` is never invoked during app startup. ISP Step 2 explicitly requires wiring it into the FastAPI lifespan.

**Expected (ISP Step 2):**
"Wire `ensure_tables()` into FastAPI lifespan startup event in `backend/main.py`."

**Actual (code):**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    get_bq_client()   # only warms up client; does NOT create tables
    yield
```

**Violation:** IncrementalStepPlan Step 2

**Recommendation:**
```python
from backend.migrations.bq_migrate import ensure_dataset, ensure_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    client = get_bq_client()
    ensure_dataset(client)
    ensure_tables(client)
    yield
```

---

### ID-07 — `backend/startup.py` artifact not created

| Field | Value |
|-------|-------|
| **Type** | Missing |
| **Classification** | B |
| **Component** | `backend/startup.py` |
| **Impact** | **Low** |

**Description:**
ISP Step 2 lists `backend/startup.py` as a mandatory artifact. File does not exist.

**Expected (ISP Step 2 Artifacts):** `backend/startup.py — calls ensure_tables() on app startup`.

**Violation:** IncrementalStepPlan Step 2

**Recommendation:**
Either create `backend/startup.py` containing the `ensure_tables()` call and import it from `main.py`, or close as "merged into main.py" and update the ISP artifact list.

---

### ID-08 — `is_active BOOL` field missing from all master schemas

| Field | Value |
|-------|-------|
| **Type** | Missing |
| **Classification** | B |
| **Component** | `backend/migrations/bq_migrate.py` — all master schemas |
| **Impact** | **Medium** |

**Description:**
All 9 master tables are missing `is_active BOOL` column. ISP Step 3 Test Case #5 explicitly requires it.

**Expected (ISP Step 3 TC #5):**
"Each master table has at minimum: `code STRING (PK)`, `name STRING`, `is_active BOOL`."

**Actual (code):**
Master schemas have `code`, `name`, `description` only.

**Violation:** IncrementalStepPlan Step 3

**Recommendation:**
Add `SchemaField("is_active", "BOOL")` to all 9 master table schemas. Set `is_active: True` in all seed data.

---

### ID-09 — JSON seed files not created

| Field | Value |
|-------|-------|
| **Type** | Missing |
| **Classification** | B |
| **Component** | `backend/seed/masters/` |
| **Impact** | **Low** |

**Description:**
ISP Step 3 specifies JSON seed files for each master. Code uses a Python dict in `masters_data.py` instead.

**Expected (ISP Step 3 Artifacts):**
`backend/seed/masters/cat.json`, `pck.json`, `src.json`, `ff.json`, `alt.json`, `scn.json`, `run.json`

**Violation:** IncrementalStepPlan Step 3

**Recommendation:**
Generate JSON files from `masters_data.py` or update ISP artifact paths to `masters_data.py`. Functionally equivalent either way.

---

### ID-10 — `test_masters_api.py` not created

| Field | Value |
|-------|-------|
| **Type** | Missing |
| **Classification** | A |
| **Component** | `backend/tests/test_masters_api.py` |
| **Impact** | **Low** |

**Description:**
ISP Step 3 requires `backend/tests/test_masters_api.py`. File is absent; masters router has no test coverage.

**Expected (ISP Step 3):**
Tests: `GET /api/ri/masters/{type}` returns `[{"code", "name", "is_active"}]`; invalid type returns 422/404.

**Violation:** IncrementalStepPlan Step 3

**Recommendation:**
Create `test_masters_api.py` with mocked BQ client; assert each of the 9 endpoints returns correct shape and content.

---

### ID-11 — `master_run` table and endpoint missing

| Field | Value |
|-------|-------|
| **Type** | Missing |
| **Classification** | B |
| **Component** | `bq_migrate.py`, `ri_masters.py`, `masters_data.py` |
| **Impact** | **Medium** |

**Description:**
ISP Step 3 lists 7 master tables including `ri_master_run`. No `master_run` table schema, no seed data, no `GET /api/ri/masters/run` endpoint. RUN codes generated by `_generate_run_code()` are never persisted to a master registry.

**Expected (AP §5.4):**
```python
def generate_run_code():
    ...
    RUN.upsert(run_code=code, run_ts=now)   # ← persist to master_run
    return code
```

**Violation:** ArchitecturePack §5.4, IncrementalStepPlan Step 3

**Recommendation:**
Add `master_run` schema, seed procedure, `GET /api/ri/masters/run` endpoint. Call upsert in `_generate_run_code()`.

---

### ID-12 — PPR DOWN called synchronously in `save_entry`

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | A |
| **Component** | `backend/services/ri_entry_service.py:151–153` |
| **Impact** | **Medium** |

**Description:**
`prepare_for_calculate()` is called **synchronously** inside `save_entry()`. AP §5.9.3 specifies it should be enqueued after a successful save.

**Expected (AP §5.9.3):**
"`POST /api/ri/entries` success → **enqueue** `prepare_for_calculate(entry_id)`."
A separate dedicated endpoint `POST /api/ri/entries/{id}/prepare` exists for manual trigger.

**Actual (code):**
```python
# ppr_service.py called synchronously during save
if all_ri_cells:
    prepare_for_calculate(all_ri_cells, yb_map, xp_map, client)
```
With 300 cells (30 YBFull × 10 XPeriod), this adds significant latency well beyond the AP §5.6 target of `< 1.5s` for entry save.

**Violation:** ArchitecturePack §5.9.3, §5.6

**Recommendation:**
Move `prepare_for_calculate()` to a FastAPI `BackgroundTasks` or job queue. Return immediately after RIScreenEntry + RICell inserts complete.

---

### ID-13 — YF XPeriod code `Y2612` wrong in tests

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | B |
| **Component** | `backend/tests/test_ppr_integration.py:71,116` · `test_performance_edge.py` |
| **Impact** | **Medium** |

**Description:**
Tests use `"Y2612"` as the YF XPeriod code. AP §5.8.1 defines the YF format as `Y{YY}` (2-digit year), e.g., `"Y26"` for 2026.

**Expected (AP §5.8.1):**
`Y26 → [m2601..m2612]`. Code `expand_to_months()` for YF: `yy = code[1:]` = `"26"` → correct.

**Actual (code):**
`_make_xp("Y2612", "YF")` → `code[1:] = "2612"` → generates `m261201`, `m261202`, … (invalid month codes).

**Violation:** ArchitecturePack §5.8.1

**Recommendation:**
Replace all `"Y2612"` with `"Y26"` in test fixtures. Add assertion:
```python
assert XPeriod(xperiod_code="Y26", period_type="YF", ...).expand_to_months() == [
    "m2601", "m2602", "m2603", "m2604", "m2605", "m2606",
    "m2607", "m2608", "m2609", "m2610", "m2611", "m2612",
]
```

---

### ID-14 — P03 response missing `SCN_OPTIONS`

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | A |
| **Component** | `backend/services/ri_config_service.py` — `load_entry_template()` |
| **Impact** | **Low** |

**Description:**
AP §2.2 P03 `top_bar` dict includes `SCN_OPTIONS: ["OPT","REAL","PESS"]`. Implemented `masters` dict omits it.

**Expected (AP §2.2 P03):**
```python
"top_bar": {
    "CAT_OPTIONS": ..., "PCK_OPTIONS": ..., "SRC_OPTIONS": ...,
    "FF_OPTIONS": ..., "ALT_OPTIONS": ...,
    "SCN_OPTIONS": ["OPT", "REAL", "PESS"],   # ← required
}
```

**Violation:** ArchitecturePack §2.2 P03

**Recommendation:**
Add `"SCN_OPTIONS": ["OPT", "REAL", "PESS"]` to the `masters` dict in `load_entry_template()`.

---

### ID-15 — ISP Step 2 uses `zbfull_key` but code uses `zb_full_code`

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | B |
| **Component** | `backend/migrations/bq_migrate.py:47` |
| **Impact** | **Low** |

**Description:**
ISP Step 2 SubStep 2 proposed `zbfull_key` as the column name. AP §1.1 specifies `zb_full_code`. Code follows AP (correct).

**Verdict:** ISP has a stale field name. AP is the higher authority. **No code change needed.**

**Recommendation:**
Update ISP Step 2 to use `zb_full_code` to match AP §1.1.

---

### ID-16 — `seed_masters.py` file path deviates from ISP

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | B |
| **Component** | `backend/seed/seed_masters.py` |
| **Impact** | **Low** |

**Expected (ISP Step 3):** `backend/migrations/bq_seed_masters.py`
**Actual:** `backend/seed/seed_masters.py`

**Verdict:** Functionally equivalent. Different directory only. Update ISP artifact path.

---

### ID-17 — Masters router file name deviation

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | A |
| **Component** | `backend/routers/ri_masters.py` |
| **Impact** | **Low** |

**Expected (ISP Step 3):** `backend/routers/masters.py`
**Actual:** `backend/routers/ri_masters.py`

**Verdict:** `ri_` prefix is consistent with other module routers. Better naming. Update ISP.

---

### ID-18 — `load_for_ui` SELECT missing `z_block_zblock1_pack`

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | A |
| **Component** | `backend/services/ppr_service.py:287–296` |
| **Impact** | **High** (compounding with ID-01) |

**Description:**
`z_block_zblock1_pack` appears in the WHERE CONCAT but not in SELECT. Combined with ID-01 (pack never written to BQ), the WHERE clause can never match.

**Violation:** ArchitecturePack §5.9.2

**Recommendation:**
Fix ID-01 first. Then add `z_block_zblock1_pack` to the SELECT clause for completeness and future use.

---

### ID-19 — `paste-validate` has no GET protection

| Field | Value |
|-------|-------|
| **Type** | Missing |
| **Classification** | A |
| **Component** | `backend/routers/ri_config.py:73` |
| **Impact** | **Low** |

**Description:**
`POST /api/ri/configs/paste-validate` is registered correctly. However, `GET /api/ri/configs/paste-validate` will match the `GET /{config_id}` route with `config_id="paste-validate"` and return a confusing 404.

**Recommendation:**
Acceptable as-is. Document that `/paste-validate` is POST-only. No code change required.

---

### ID-20 — `ppr_mode null → Spread` AP §5.9.5 vs code behavior

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | B |
| **Component** | `backend/models/ri.py:99–102` — `effective_ppr_mode()` |
| **Impact** | **Medium** |

**Description:**
AP §5.9.5 edge case states `ppr_mode null → Default = "Spread"`. Code returns `"Same"` for KRN rows when `ppr_mode is None`. This contradicts §5.9.5 but is consistent with §5.8.0 (`KRN → Same`).

**AP Internal Inconsistency:**
- §5.8.0: `KRN → Same`, `KRF → Spread` (fnf-based rule)
- §5.9.5: `ppr_mode null → Default = Spread` (blanket rule)

**Verdict:** Code follows §5.8.0 (correct for KRN rows). §5.9.5 appears to be describing the BQ column default, not the runtime logic. **Clarify with POSUP.**

**Recommendation:**
Escalate to POSUP: which rule takes precedence? Until clarified, retain current behavior (§5.8.0 fnf-based derivation).

---

### ID-21 — `RIScreenEntry.status` starts as `SAVED` (no DRAFT state)

| Field | Value |
|-------|-------|
| **Type** | Incorrect |
| **Classification** | A |
| **Component** | `backend/services/ri_entry_service.py:81` |
| **Impact** | **Low** |

**Description:**
AP §2.3 state machine shows `DRAFT → SAVED`. Code creates entries with `status="SAVED"` immediately at creation time, before cells are inserted.

**Expected (AP §2.3):** Entry starts as `DRAFT`; transitions to `SAVED` after all cells are persisted successfully.

**Consequence:** If BQ cell insert fails after entry is written, entry is stuck as `SAVED` with no cells — inconsistent state.

**Recommendation:**
Create entry as `DRAFT`, insert cells, then update status to `SAVED`. Document that BQ streaming lacks transaction support (accepted limitation).

---

## SECTION 3: API CONTRACT AUDIT

| # | Endpoint | Method | FE Interface | BE Model | Status | Notes |
|---|----------|--------|--------------|----------|--------|-------|
| 1 | `/api/ri/configs` | GET | `ConfigListItem[]` (ri.ts:132) | `ConfigListItem` (ri.py:398) | ✅ MATCH | — |
| 2 | `/api/ri/configs/{id}` | GET | `RIScreenConfig` (ri.ts:120) | `RIScreenConfig` (ri.py:188) | ✅ MATCH | — |
| 3 | `/api/ri/configs` | POST | `SaveConfigRequest` (ri.ts:202) | `SaveConfigRequest` (ri.py:366) | ✅ MATCH | — |
| 4 | `/api/ri/configs/{id}` | PUT | `SaveConfigRequest` (ri.ts:202) | `SaveConfigRequest` (ri.py:366) | ✅ MATCH | — |
| 5 | `/api/ri/configs/{id}` | DELETE | — | — | ✅ MATCH | No body |
| 6 | `/api/ri/entries/template/{config_id}` | GET | `EntryTemplateResponse` (ri.ts:235) | inline dict (ri_entry.py:24) | ⚠ PARTIAL | `SCN_OPTIONS` missing |
| 7 | `/api/ri/entries` | POST | `SaveEntryRequest` (ri.ts:217) | `SaveEntryRequest` (ri.py:374) | ⚠ PARTIAL | `value: null` not tested |
| 8 | `/api/ri/entries/{id}` | GET | `RIScreenEntry` + cells | `RIScreenEntry` only (ri_entry.py:39) | ❌ MISMATCH | Cells absent |
| 9 | `/api/ri/masters/cat` | GET | `CAT[]` (ri.ts:32) | `dict[]` | ✅ MATCH | — |
| 10 | `/api/ri/masters/pck` | GET | `PCK[]` (ri.ts:33) | `dict[]` | ✅ MATCH | — |
| 11 | `/api/ri/masters/src` | GET | `SRC[]` (ri.ts:34) | `dict[]` | ✅ MATCH | — |
| 12 | `/api/ri/masters/ff` | GET | `FF[]` (ri.ts:35) | `dict[]` | ✅ MATCH | — |
| 13 | `/api/ri/masters/alt` | GET | `ALT[]` (ri.ts:36) | `dict[]` | ✅ MATCH | — |
| 14 | `/api/ri/masters/scn` | GET | `SCN[]` (ri.ts:38) | `dict[]` | ✅ MATCH | — |
| 15 | `/api/ri/masters/kr-items` | GET | `KRItem[]` (ri.ts:51) | `dict[]` | ✅ MATCH | — |
| 16 | `/api/ri/masters/filter-items` | GET | `FilterItem[]` (ri.ts:56) | `dict[]` | ✅ MATCH | — |
| 17 | `/api/ri/masters/xperiods` | GET | `XPeriod[]` (ri.ts:87) | `dict[]` | ✅ MATCH | — |
| 18 | `/api/ri/configs/{id}/clone` | POST | `{new_name: string}` | `CloneRequest` (ri_config.py:51) | ✅ MATCH | — |
| 19 | `/api/ri/configs/paste-validate` | POST | `{tsv: string}` | `PasteValidateRequest` (ri_config.py:63) | ✅ MATCH | — |
| 20 | `/api/ri/entries/{id}/prepare` | POST | — | — (ri_entry.py:46) | ✅ MATCH | No body |
| 21 | `/api/ri/entries/{id}/display` | GET | `RICell[]` (ri.ts:185) | `list[RICell]` (ri_entry.py:53) | ✅ MATCH | — |

---

### MISMATCH DETAIL — Endpoint #6: `GET /api/ri/entries/template/{config_id}`

**FE expects** (`EntryTemplateResponse` ri.ts:235):
```typescript
{
  config: RIScreenConfig
  yb_fulls: YBFull[]
  xperiods: XPeriod[]
  masters: {
    CAT_OPTIONS: CAT[]
    PCK_OPTIONS: PCK[]
    SRC_OPTIONS: SRC[]
    FF_OPTIONS: FF[]
    ALT_OPTIONS: ALT[]
    // SCN_OPTIONS NOT declared in FE type — but AP requires it
  }
}
```

**BE returns** (`load_entry_template` ri_config_service.py):
```python
{
    "config": ...,
    "yb_fulls": [...],
    "xperiods": [...],
    "masters": {
        "CAT_OPTIONS": ...,
        "PCK_OPTIONS": ...,
        "SRC_OPTIONS": ...,
        "FF_OPTIONS": ...,
        "ALT_OPTIONS": ...,
        # SCN_OPTIONS MISSING
    }
}
```

**Delta:** `SCN_OPTIONS: ["OPT","REAL","PESS"]` absent from `masters` dict. AP §2.2 P03 explicitly includes it.

**Fix:** Add to `ri_config_service.load_entry_template()`:
```python
"SCN_OPTIONS": ["OPT", "REAL", "PESS"],
```
Add `SCN_OPTIONS: ScnType[]` to `EntryTemplateResponse.masters` in `ri.ts`.

---

### MISMATCH DETAIL — Endpoint #8: `GET /api/ri/entries/{id}` — missing cells

**FE expects** (implied by Flow F3 AP §4.4):
```typescript
{
  entry: RIScreenEntry
  cells: RICell[]   // ← required to re-render the grid
}
```

**BE returns:**
```python
RIScreenEntry.model_dump(mode="json")  # ← entry only, no cells
```

**Delta:**
| Field | FE expects | BE returns | Match? |
|-------|-----------|------------|--------|
| `entry` | `RIScreenEntry` | `RIScreenEntry` | ✅ |
| `cells` | `RICell[]` | *(absent)* | ❌ |

**Fix:**
```python
@router.get("/{entry_id}")
async def get_entry(entry_id: str):
    client = get_bq_client()
    entry = entry_svc._get_entry(client, entry_id)
    cells = entry_svc.get_entry_display(client, entry_id)
    return {
        "entry": entry.model_dump(mode="json"),
        "cells": [c.model_dump(mode="json") for c in cells],
    }
```

---

## SECTION 4: COVERAGE CHECK

### Architectural Pack — Component Coverage

| AP Component | Status | Notes |
|---|---|---|
| Entity: RIScreenConfig (§1.2) | ✅ IMPLEMENTED | Field names follow ISP (shorter) not AP (`ri_screen_config_id`) |
| Entity: RIScreenEntry (§1.1 new) | ✅ IMPLEMENTED | `entry_id` not `ri_screen_entry_id`; ISP takes precedence |
| Entity: UICell (FE-only, §1.1 #3) | ✅ IMPLEMENTED | No `entry_id`/`cell_id` — correct |
| Entity: RICell (§1.1 #4, so_cell_v1) | ⚠ PARTIAL | Z-Block metadata missing on insert (ID-04) |
| Entity: RIRow (§1.1 #5, so_rows_pca) | ⚠ PARTIAL | Decomposed z_block codes never populated (ID-02) |
| Entity: YBFull (`ppr_mode` + `unit`) | ✅ IMPLEMENTED | `effective_ppr_mode()` correct per §5.8.0 |
| Entity: XPeriod + `expand_to_months()` | ✅ IMPLEMENTED | Cross-year Q correct; MF=1, QF=3, HF=6, YF=12 |
| Entity: ZBFull (7-master composite) | ✅ IMPLEMENTED | `build_code()` and `to_key()` correct |
| Seed 5 configs PPR-PCA-* (§1.4) | ⚠ PARTIAL | PPR-PCA-CEH has no sheet_id |
| P01 — Save RIScreenConfig | ✅ IMPLEMENTED | |
| P02 — List configs | ✅ IMPLEMENTED | |
| P03 — Load entry template | ⚠ PARTIAL | `SCN_OPTIONS` missing (ID-14) |
| P04 — Resolve ZBFull | ✅ IMPLEMENTED | Inline in `save_entry()` |
| P05 — UICell FE state | ✅ IMPLEMENTED | |
| P06 — Save entry (3 SCN) | ⚠ PARTIAL | Z-Block metadata missing; PPR sync (ID-02, ID-04, ID-12) |
| P07 — KRItem+FilterItem → YBFull | ✅ IMPLEMENTED | `build_kr_full_code`, `build_filter_full_code` |
| PPR-1 `RICell_PeriodToMonth` | ✅ IMPLEMENTED | |
| PPR-2 `RICellToRIRow` | ⚠ PARTIAL | z_block fields not populated (ID-02) |
| PPR-3 `WriteSORow` | ❌ INCORRECT | Missing `z_block_zblock1_pack` (ID-01) |
| PPR-4a `SORowToRICellMonth` (ISP BLOCK fix) | ✅ IMPLEMENTED | Correctly resolves AP BLOCK §5.8.4 |
| PPR-4b `RICell_MonthToPeriod` | ✅ IMPLEMENTED | |
| `prepare_for_calculate()` orchestration | ⚠ PARTIAL | Sync not async (ID-12) |
| `load_for_ui()` orchestration | ❌ INCORRECT | Returns empty — depends on ID-01 fix |
| `is_seed` guard 403 on PUT/DELETE | ✅ IMPLEMENTED | |
| Clone → `is_seed=False` | ✅ IMPLEMENTED | |
| Paste-validate TSV (44 cols) | ✅ IMPLEMENTED | |
| PPR endpoint #20 `/prepare` | ✅ IMPLEMENTED | |
| PPR endpoint #21 `/display` | ✅ IMPLEMENTED | |
| 4 FE screens (§3.1) | ✅ IMPLEMENTED | |
| GSheets seed reader (§1.4) | ✅ IMPLEMENTED | |
| BQ migration idempotent (§1.2) | ⚠ PARTIAL | Not called at startup (ID-06) |
| Master tables × 9 | ⚠ PARTIAL | Missing `is_active`, missing `master_run` (ID-08, ID-11) |
| RUN code registry | ❌ MISSING | `master_run` table + upsert absent (ID-11) |

### IncrementalStepPlan — Step Coverage

| Step | Status | Notes |
|------|--------|-------|
| Step 0: Scaffold | ✅ IMPLEMENTED | health, CORS, BQ singleton |
| Step 1: Pydantic + TS types | ✅ IMPLEMENTED | All entities |
| Step 2: BQ migration | ⚠ PARTIAL | `startup.py` absent; `ensure_tables` not wired (ID-06, ID-07) |
| Step 3: Masters seed | ⚠ PARTIAL | `is_active` absent; JSON files absent; `master_run` absent; naming (ID-05, ID-08, ID-09, ID-10, ID-11) |
| Step 4: Config CRUD | ✅ IMPLEMENTED | |
| Step 5: YBFull/XPeriod + masters router | ✅ IMPLEMENTED | |
| Steps 6–11: FE screens | ✅ IMPLEMENTED | |
| Steps 12–14: PPR DOWN | ⚠ PARTIAL | WriteSORow missing PCK; RIRow z_block not populated (ID-01, ID-02) |
| Steps 15–17: PPR UP | ❌ INCORRECT | `load_for_ui` always empty (ID-01 root cause) |
| Step 18: GSheets reader | ✅ IMPLEMENTED | |
| Step 19: Seed import | ✅ IMPLEMENTED | |
| Step 20: `is_seed` guard tests | ✅ IMPLEMENTED | |
| Step 21: PPR integration tests | ⚠ PARTIAL | YF code format wrong (ID-13) |
| Step 22: E2E test | ✅ IMPLEMENTED | |
| Step 23: Performance/edge cases | ⚠ PARTIAL | YF code format wrong (ID-13) |

---

## SECTION 5: FINAL VERDICT

**Is implementation aligned with architecture? NO**

---

### Bugs that MUST be fixed before release (ordered by priority)

| Pri | ID | File | Issue | Fix Effort |
|-----|----|------|-------|-----------|
| 🔴 P0 | ID-01 | `ppr_service.py:116` | `WriteSORow` missing `z_block_zblock1_pack` → PPR UP always returns empty | 1 line |
| 🔴 P0 | ID-02 | `ppr_service.py:83` | `RICellToRIRow` never populates z_block decomposed codes → all BQ rows have empty metadata | ~15 lines |
| 🔴 P0 | ID-03 | `ri_entry.py:39` | `GET /api/ri/entries/{id}` returns no cells → Flow F3 (reload entry) broken | ~5 lines |
| 🟠 P1 | ID-04 | `ri_entry_service.py:132` | `save_entry` RICell insert missing Z-Block metadata on so_cell_v1 | ~8 lines |
| 🟠 P1 | ID-06 | `main.py:11` | `ensure_tables()` not called at startup → fresh deployment fails silently | 2 lines |
| 🟠 P1 | ID-11 | `bq_migrate.py`, `ri_masters.py` | `master_run` table + endpoint + upsert in `_generate_run_code()` missing | ~20 lines |
| 🟡 P2 | ID-08 | `bq_migrate.py` | `is_active BOOL` missing from all 9 master schemas | schema + seed |
| 🟡 P2 | ID-12 | `ri_entry_service.py:151` | PPR DOWN synchronous → violates AP §5.6 latency target | refactor |
| 🟡 P2 | ID-13 | test files | YF XPeriod code `Y2612` → should be `Y26`; month codes corrupted | test fix |
| 🟡 P2 | ID-14 | `ri_config_service.py` | `SCN_OPTIONS` absent from P03 masters dict | 1 line |
| 🔵 P3 | ID-07 | — | `startup.py` artifact absent | low |
| 🔵 P3 | ID-05 | `bq_migrate.py` | master table naming `master_*` vs `ri_master_*` | rename |
| 🔵 P3 | ID-16–17 | file paths | `seed_masters.py`, `ri_masters.py` path deviations from ISP | update ISP |

---

### Root cause analysis — P0 bugs

All three P0 bugs share a single root cause: **`RICellToRIRow` was designed to group cells by `(zb_full_code, yb_full_code)` but was never given responsibility for decomposing `zb_full_code` into its 7 constituent parts.**

```
RICellToRIRow()   ← creates RIRow with zb_full_code only; cat/pck/src/... = ""
      ↓
WriteSORow()      ← writes empty Z-Block cols; MISSING z_block_zblock1_pack
      ↓
so_rows_pca       ← PCK column = NULL; all other z_block_* = ""
      ↓
load_for_ui()     ← WHERE CONCAT produces "CAT--SRC-FF-..." ≠ stored zb_full_code
      ↓
result            ← 0 rows returned → grid always empty on reload
```

**Single fix unblocks all three:**
In `RICellToRIRow` (or its caller `prepare_for_calculate`), split `zb_full_code` by `"-"` respecting the known 7-part structure and populate all `*_code` fields on `RIRow`. Then `WriteSORow` can write all 7 Z-Block columns correctly.
