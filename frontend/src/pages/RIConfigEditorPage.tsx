import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import DataGrid, { Column, textEditor } from 'react-data-grid'
import 'react-data-grid/lib/styles.css'
import { riApi } from '../api/ri'
import type { RIScreenConfig } from '../types/ri'

const RI_COLS = [
  'fnf', 'kr1', 'kr2', 'kr3', 'kr4', 'kr5', 'kr6', 'kr7', 'kr8',
  'cdt1', 'cdt2', 'cdt3', 'cdt4',
  'pt1_now', 'pt2_now', 'du_now', 'pt1_prev', 'pt2_prev', 'du_prev',
  'owntype', 'aitype', 'cty1', 'cty2', 'ostype', 'fu1', 'fu2', 'ch',
  'egt1', 'egt2', 'egt3', 'egt4', 'egt5', 'hr1', 'hr2', 'hr3', 'sec',
  'px', 'ppc', 'np', 'le1', 'le2', 'unit', 'td_bu', 'non_agg',
]

type GridRow = Record<string, string> & { _id: string }

const GRID_COLUMNS: Column<GridRow>[] = [
  { key: '_id', name: '#', width: 40, frozen: true },
  ...RI_COLS.map(col => ({
    key: col,
    name: col.toUpperCase(),
    width: col === 'unit' ? 80 : 70,
    renderEditCell: textEditor,
  })),
]

export default function RIConfigEditorPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const isNew = !id
  const [config, setConfig] = useState<Partial<RIScreenConfig>>({
    is_seed: false,
    yb_full_codes: [],
    xperiod_codes: [],
  })
  const [rows, setRows] = useState<GridRow[]>([])
  const [xperiodCodes, setXperiodCodes] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isNew && id) {
      riApi.getConfig(id).then(cfg => {
        setConfig(cfg)
        setXperiodCodes(cfg.xperiod_codes)
      })
    }
  }, [id, isNew])

  const handlePaste = useCallback(
    (e: ClipboardEvent) => {
      const tsv = e.clipboardData?.getData('text/plain') || ''
      if (!tsv.includes('\t')) return
      riApi.pasteValidate(tsv).then(result => {
        if (result.valid) {
          const newRows: GridRow[] = result.rows.map(
            (r: Record<string, string>, i: number) => ({
              _id: String(rows.length + i + 1),
              ...r,
            })
          )
          setRows(prev => [...prev, ...newRows])
        }
      })
    },
    [rows.length]
  )

  useEffect(() => {
    document.addEventListener('paste', handlePaste as EventListener)
    return () => document.removeEventListener('paste', handlePaste as EventListener)
  }, [handlePaste])

  const addRow = () => {
    const empty: GridRow = {
      _id: String(rows.length + 1),
      ...Object.fromEntries(RI_COLS.map(c => [c, ''])),
    }
    setRows(prev => [...prev, empty])
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const req = {
        config_name: config.config_name || '',
        config_code: config.config_code,
        rows: rows.map(r => {
          const { _id, ...rest } = r
          return { kr_items: [], filter_items: [], ...rest }
        }),
        xperiod_codes: xperiodCodes,
      }
      if (isNew) {
        const created = await riApi.createConfig(req)
        navigate(`/ri/configs/${created.config_id}`)
      } else {
        await riApi.updateConfig(id!, req)
      }
    } finally {
      setSaving(false)
    }
  }

  const isSeed = config.is_seed === true

  return (
    <div className="p-4 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">
          {isNew ? 'New Config' : `Edit: ${config.config_name}`}
        </h1>
        <div className="flex gap-2">
          {isSeed && (
            <span className="px-2 py-1 bg-gray-200 text-gray-600 rounded text-sm">
              🔒 Seed
            </span>
          )}
          {!isSeed && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          )}
          {!isNew && (
            <button
              onClick={() =>
                riApi
                  .cloneConfig(id!, `Copy of ${config.config_name}`)
                  .then(c => navigate(`/ri/configs/${c.config_id}`))
              }
              className="px-4 py-2 border rounded hover:bg-gray-50"
            >
              Clone
            </button>
          )}
          <button
            onClick={() => navigate('/ri/configs')}
            className="px-4 py-2 border rounded"
          >
            Cancel
          </button>
        </div>
      </div>

      {/* Meta fields */}
      <div className="flex gap-4">
        <div className="flex-1">
          <label className="text-sm text-gray-600">Config Name</label>
          <input
            value={config.config_name || ''}
            onChange={e => setConfig(p => ({ ...p, config_name: e.target.value }))}
            disabled={isSeed}
            className="w-full border rounded px-2 py-1 mt-1"
          />
        </div>
        <div>
          <label className="text-sm text-gray-600">XPeriod codes (comma-separated)</label>
          <input
            value={xperiodCodes.join(',')}
            onChange={e =>
              setXperiodCodes(
                e.target.value
                  .split(',')
                  .map(s => s.trim())
                  .filter(Boolean)
              )
            }
            disabled={isSeed}
            className="w-full border rounded px-2 py-1 mt-1"
            placeholder="M2601,Q2603,Y26"
          />
          {xperiodCodes.length > 10 && (
            <p className="text-orange-500 text-xs mt-1">
              ⚠ More than 10 XPeriods (still allowed)
            </p>
          )}
        </div>
      </div>

      {rows.length > 30 && (
        <p className="text-orange-500 text-sm">
          ⚠ {rows.length} rows — more than recommended 30 (still allowed)
        </p>
      )}

      {/* 44-col react-data-grid — mirrors GSheet RI cols I:BA */}
      <div style={{ height: 500 }}>
        <DataGrid
          columns={GRID_COLUMNS}
          rows={rows}
          onRowsChange={setRows}
          className="rdg-light h-full"
        />
      </div>

      {!isSeed && (
        <div className="flex gap-2">
          <button
            onClick={addRow}
            className="px-3 py-1 border rounded text-sm hover:bg-gray-50"
          >
            + Add Row
          </button>
          <span className="text-sm text-gray-500 self-center">
            or Ctrl+V to paste from GSheet (cols I:BA)
          </span>
        </div>
      )}
    </div>
  )
}
