/**
 * RI module TypeScript types.
 * Mirrors backend/models/ri.py — cross-referenced with AP_FPA-T2_RI_V10_20260424.md §1.
 */

// ---------------------------------------------------------------------------
// Enums / literals
// ---------------------------------------------------------------------------

export const SCN_TYPES = ['OPT', 'REAL', 'PESS'] as const
export type ScnType = (typeof SCN_TYPES)[number]

export const PPR_MODES = ['Same', 'Spread'] as const
export type PprMode = (typeof PPR_MODES)[number]

export const PERIOD_TYPES = ['MF', 'QF', 'HF', 'YF'] as const
export type PeriodType = (typeof PERIOD_TYPES)[number]

export const ENTRY_STATUSES = ['DRAFT', 'SAVED'] as const
export type EntryStatus = (typeof ENTRY_STATUSES)[number]

// ---------------------------------------------------------------------------
// Master entities
// ---------------------------------------------------------------------------

export interface MasterItem {
  code: string
  name: string
  description?: string
}

export type CAT = MasterItem
export type PCK = MasterItem
export type SRC = MasterItem
export type FF = MasterItem
export type ALT = MasterItem

export interface SCN extends MasterItem {
  scn_type: ScnType
}

export interface RUN {
  run_code: string
  run_ts: string  // ISO datetime
}

// ---------------------------------------------------------------------------
// KRItem / FilterItem → KRFull / FilterFull → YBFull (AP §5.1)
// ---------------------------------------------------------------------------

export interface KRItem {
  kr_item_code: string
  level_code: string
  name?: string
}

export interface FilterItem {
  filter_item_code: string
  level_code: string
  name?: string
}

export interface KRFull {
  kr_full_code: string
  items: KRItem[]
}

export interface FilterFull {
  filter_full_code: string
  items: FilterItem[]
}

export interface YBFull {
  yb_full_code: string
  kr_full_code: string
  filter_full_code: string
  fnf: 'KRN' | 'KRF'
  unit: string
  ppr_mode: PprMode | null
  sort_order: number
}

// ---------------------------------------------------------------------------
// XPeriod (AP §5.8.1)
// ---------------------------------------------------------------------------

export interface XPeriod {
  xperiod_code: string   // e.g. "M2603", "Q2603", "H2606", "Y26"
  period_type: PeriodType
  label: string
  sort_order: number
}

// ---------------------------------------------------------------------------
// ZBFull — 7-master composite (AP §5.2)
// ---------------------------------------------------------------------------

export interface ZBFull {
  zb_full_code: string
  cat_code: string
  pck_code: string
  src_code: string
  ff_code: string
  alt_code: string
  scn_code: string
  run_code: string
}

export function buildZBFullCode(
  cat: string, pck: string, src: string, ff: string,
  alt: string, scn: string, run: string,
): string {
  return `${cat}-${pck}-${src}-${ff}-${alt}-${scn}-${run}`
}

// ---------------------------------------------------------------------------
// RIScreenConfig (AP §1.2)
// ---------------------------------------------------------------------------

export interface RIScreenConfig {
  config_id: string
  config_code: string
  config_name: string
  is_seed: boolean
  yb_full_codes: string[]
  xperiod_codes: string[]
  created_by: string
  created_at: string
  updated_at: string
}

export interface ConfigListItem {
  config_id: string
  config_code: string
  config_name: string
  is_seed: boolean
  yb_full_count: number
  xperiod_count: number
  created_at: string
}

// ---------------------------------------------------------------------------
// RIScreenEntry (AP §1.1 — new entity)
// ---------------------------------------------------------------------------

export interface RIScreenEntry {
  entry_id: string
  config_id: string
  zb_full_code: string
  scn_type: ScnType
  run_code: string
  created_by: string
  created_at: string
  status: EntryStatus
}

// ---------------------------------------------------------------------------
// UICell — FE-only state, NEVER persisted (AP §1.1 #3)
// ---------------------------------------------------------------------------

/**
 * Transient FE-only cell. No entry_id, no cell_id.
 * Lives in React state; discarded on page reload.
 * Becomes RICell only after Save triggers POST /api/ri/entries.
 */
export interface UICell {
  yb_full_code: string
  xperiod_code: string
  scn_type: ScnType
  value: number | null
  is_dirty: boolean
}

/** Composite key for UICell map: `${yb_full_code}__${xperiod_code}__${scn_type}` */
export type UICellKey = `${string}__${string}__${ScnType}`

export function makeUICellKey(yb: string, xp: string, scn: ScnType): UICellKey {
  return `${yb}__${xp}__${scn}`
}

// ---------------------------------------------------------------------------
// RICell — persisted cell (AP §1.1 #4)
// ---------------------------------------------------------------------------

export interface RICell {
  cell_id: string
  entry_id: string
  yb_full_code: string
  xperiod_code: string
  zb_full_code: string
  now_value: number
  prev_value: number
  now_y_block_fnf_fnf: string
  time_col_name: string
  so_row_id: string
}

// ---------------------------------------------------------------------------
// API request/response shapes (AP §2.4)
// ---------------------------------------------------------------------------

export interface SaveConfigRequest {
  config_code?: string
  config_name: string
  rows: ConfigRow[]
  xperiod_codes: string[]
  created_by?: string
}

export interface ConfigRow {
  kr_items: KRItem[]
  filter_items: FilterItem[]
  ppr_mode?: PprMode
  unit?: string
}

export interface SaveEntryRequest {
  config_id: string
  cat: string
  pck: string
  src: string
  ff: string
  alt: string
  cells: CellPayload[]
  created_by?: string
}

export interface CellPayload {
  yb_full_code: string
  xperiod_code: string
  scn_type: ScnType
  value: number | null
}

export interface EntryTemplateResponse {
  config: RIScreenConfig
  yb_fulls: YBFull[]
  xperiods: XPeriod[]
  masters: {
    CAT_OPTIONS: CAT[]
    PCK_OPTIONS: PCK[]
    SRC_OPTIONS: SRC[]
    FF_OPTIONS: FF[]
    ALT_OPTIONS: ALT[]
  }
}

export interface SaveEntryResponse {
  entries: RIScreenEntry[]   // 3 entries: OPT / REAL / PESS
  run_code: string
}

// ---------------------------------------------------------------------------
// Type guards
// ---------------------------------------------------------------------------

export function isScnType(value: unknown): value is ScnType {
  return SCN_TYPES.includes(value as ScnType)
}

export function isPprMode(value: unknown): value is PprMode {
  return PPR_MODES.includes(value as PprMode)
}
