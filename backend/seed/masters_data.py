"""
Static master data for seeding Config_FPA_T tables.
AP §2.4 /masters/* endpoints serve this data.
"""

MASTER_FF = [
    {"code": "MF", "name": "Monthly",    "description": "Monthly frequency — 1 month per period"},
    {"code": "QF", "name": "Quarterly",  "description": "Quarterly frequency — 3 months per period"},
    {"code": "HF", "name": "Half-year",  "description": "Half-year frequency — 6 months per period"},
    {"code": "YF", "name": "Yearly",     "description": "Yearly frequency — 12 months per period"},
]

MASTER_SCN = [
    {"code": "OPT",  "name": "Optimistic",  "scn_type": "OPT"},
    {"code": "REAL", "name": "Realistic",   "scn_type": "REAL"},
    {"code": "PESS", "name": "Pessimistic", "scn_type": "PESS"},
]

MASTER_CAT = [
    {"code": "PLN", "name": "Plan",     "description": "Planning category"},
    {"code": "FCT", "name": "Forecast", "description": "Forecast category"},
    {"code": "ACT", "name": "Actual",   "description": "Actual category"},
]

MASTER_ALT = [
    {"code": "PLA4", "name": "Planning Alt 4", "description": "Default alternative scenario"},
    {"code": "PLA1", "name": "Planning Alt 1", "description": ""},
    {"code": "PLA2", "name": "Planning Alt 2", "description": ""},
    {"code": "PLA3", "name": "Planning Alt 3", "description": ""},
]

MASTER_SRC = [
    {"code": "GH",   "name": "Group Head",      "description": ""},
    {"code": "COH",  "name": "CEO of Venture",   "description": ""},
    {"code": "TH",   "name": "Tech Head",        "description": ""},
    {"code": "HQ",   "name": "Headquarters",     "description": ""},
    {"code": "CEH",  "name": "Center Head",      "description": ""},
]

MASTER_PCK = [
    {"code": "PCA", "name": "PCA Pack",   "description": "Plan/Config/Actual pack"},
    {"code": "PCB", "name": "PCB Pack",   "description": ""},
]

# Standard XPeriod codes for 2026 — user can add more
MASTER_XPERIOD = [
    {"xperiod_code": "M2601", "period_type": "MF", "label": "Jan 2026",  "sort_order": 1},
    {"xperiod_code": "M2602", "period_type": "MF", "label": "Feb 2026",  "sort_order": 2},
    {"xperiod_code": "M2603", "period_type": "MF", "label": "Mar 2026",  "sort_order": 3},
    {"xperiod_code": "M2604", "period_type": "MF", "label": "Apr 2026",  "sort_order": 4},
    {"xperiod_code": "M2605", "period_type": "MF", "label": "May 2026",  "sort_order": 5},
    {"xperiod_code": "M2606", "period_type": "MF", "label": "Jun 2026",  "sort_order": 6},
    {"xperiod_code": "M2607", "period_type": "MF", "label": "Jul 2026",  "sort_order": 7},
    {"xperiod_code": "M2608", "period_type": "MF", "label": "Aug 2026",  "sort_order": 8},
    {"xperiod_code": "M2609", "period_type": "MF", "label": "Sep 2026",  "sort_order": 9},
    {"xperiod_code": "M2610", "period_type": "MF", "label": "Oct 2026",  "sort_order": 10},
    {"xperiod_code": "M2611", "period_type": "MF", "label": "Nov 2026",  "sort_order": 11},
    {"xperiod_code": "M2612", "period_type": "MF", "label": "Dec 2026",  "sort_order": 12},
    {"xperiod_code": "Q2603", "period_type": "QF", "label": "Q1 2026",   "sort_order": 13},
    {"xperiod_code": "Q2606", "period_type": "QF", "label": "Q2 2026",   "sort_order": 14},
    {"xperiod_code": "Q2609", "period_type": "QF", "label": "Q3 2026",   "sort_order": 15},
    {"xperiod_code": "Q2612", "period_type": "QF", "label": "Q4 2026",   "sort_order": 16},
    {"xperiod_code": "H2606", "period_type": "HF", "label": "H1 2026",   "sort_order": 17},
    {"xperiod_code": "H2612", "period_type": "HF", "label": "H2 2026",   "sort_order": 18},
    {"xperiod_code": "Y26",   "period_type": "YF", "label": "Year 2026", "sort_order": 19},
]

# KR Items (levels L1..L8) — sample set; extended via seed script from GSheets
MASTER_KR_ITEMS = [
    {"kr_item_code": "KRN",  "level_code": "L1", "name": "KR Node (rate/ratio)"},
    {"kr_item_code": "KRF",  "level_code": "L1", "name": "KR Financial (amount)"},
    {"kr_item_code": "RATE", "level_code": "L2", "name": "Rate"},
    {"kr_item_code": "PRM",  "level_code": "L2", "name": "Premium"},
    {"kr_item_code": "GI",   "level_code": "L2", "name": "Gross Inflow"},
    {"kr_item_code": "BHR",  "level_code": "L3", "name": "Bonus/HR"},
    {"kr_item_code": "NOEM", "level_code": "L2", "name": "Headcount"},
    {"kr_item_code": "AOMC", "level_code": "L3", "name": "AOMC"},
    {"kr_item_code": "PL2",  "level_code": "L3", "name": "PL2"},
]

# Filter Items (CDT → non_agg) — sample set
MASTER_FILTER_ITEMS = [
    {"filter_item_code": "SMI",  "level_code": "CDT1", "name": "SMI Venture"},
    {"filter_item_code": "MAR",  "level_code": "CDT2", "name": "Marketing dept"},
    {"filter_item_code": "DEV",  "level_code": "CDT2", "name": "Dev dept"},
    {"filter_item_code": "ALLO", "level_code": "L4",   "name": "Allocation"},
    {"filter_item_code": "PER",  "level_code": "L4",   "name": "Period"},
    {"filter_item_code": "BAC",  "level_code": "L4",   "name": "BAC"},
    {"filter_item_code": "OPX",  "level_code": "L4",   "name": "OPX"},
    {"filter_item_code": "CAC",  "level_code": "L4",   "name": "CAC"},
    {"filter_item_code": "MAC",  "level_code": "L4",   "name": "MAC"},
    {"filter_item_code": "OMC",  "level_code": "L4",   "name": "OMC"},
]
