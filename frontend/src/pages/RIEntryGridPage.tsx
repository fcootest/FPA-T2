import { useEffect, useState, useCallback } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { riApi } from '../api/ri'
import type {
  UICell,
  UICellKey,
  ScnType,
  EntryTemplateResponse,
  CellPayload,
} from '../types/ri'
import { SCN_TYPES, makeUICellKey } from '../types/ri'

type CellMap = Map<UICellKey, UICell>

export default function RIEntryGridPage() {
  useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const configId = searchParams.get('config') || ''

  const [template, setTemplate] = useState<EntryTemplateResponse | null>(null)
  const [cells, setCells] = useState<CellMap>(new Map())
  const [masters, setMasters] = useState({
    cat: '',
    pck: '',
    src: '',
    ff: '',
    alt: '',
  })
  const [saving, setSaving] = useState(false)
  const [runCode, setRunCode] = useState<string | null>(null)
  const [status, setStatus] = useState<'DRAFT' | 'SAVED'>('DRAFT')

  useEffect(() => {
    if (configId) {
      riApi.getEntryTemplate(configId).then(setTemplate)
    }
  }, [configId])

  const getCellValue = (yb: string, xp: string, scn: ScnType): number | null => {
    return cells.get(makeUICellKey(yb, xp, scn))?.value ?? null
  }

  const setCellValue = useCallback(
    (yb: string, xp: string, scn: ScnType, value: number | null) => {
      const key = makeUICellKey(yb, xp, scn)
      setCells(prev => {
        const next = new Map(prev)
        next.set(key, {
          yb_full_code: yb,
          xperiod_code: xp,
          scn_type: scn,
          value,
          is_dirty: true,
        })
        return next
      })
    },
    []
  )

  const handleSave = async () => {
    if (!template || !masters.cat) return
    setSaving(true)
    try {
      const cellPayloads: CellPayload[] = []
      for (const [, cell] of cells) {
        cellPayloads.push({
          yb_full_code: cell.yb_full_code,
          xperiod_code: cell.xperiod_code,
          scn_type: cell.scn_type,
          value: cell.value,
        })
      }
      const resp = await riApi.saveEntry({
        config_id: template.config.config_id,
        ...masters,
        cells: cellPayloads,
      })
      setRunCode(resp.run_code)
      setStatus('SAVED')
    } finally {
      setSaving(false)
    }
  }

  if (!template) return <div className="p-8">Loading template...</div>

  const { yb_fulls, xperiods } = template

  return (
    <div className="flex flex-col h-screen">
      {/* Header — BUG-030: show config details */}
      <div className="p-3 border-b flex items-center justify-between bg-white">
        <div>
          <div className="font-bold">{template.config.config_name}</div>
          <div className="text-xs text-gray-400 mt-0.5">
            {template.config.config_code} · {yb_fulls.length} rows · {xperiods.length} periods · {SCN_TYPES.length} SCN
          </div>
        </div>
        <div className="flex gap-2 items-center">
          <span className="text-sm text-gray-500">
            {status}
            {runCode && ` · RUN: ${runCode}`}
          </span>
          <button
            onClick={handleSave}
            disabled={saving || !masters.cat}
            className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            title={!masters.cat ? 'Select CAT first' : undefined}
          >
            {saving ? 'Saving…' : 'Save All SCN'}
          </button>
          <button
            onClick={() => navigate('/ri/entries/new')}
            className="px-3 py-1.5 border rounded text-sm hover:bg-gray-50"
          >
            ← Back
          </button>
        </div>
      </div>

      {/* Top bar — 5 master dropdowns (AP §3.3.1); SCN is NOT a dropdown */}
      <div className="p-3 border-b bg-gray-50 flex gap-3 flex-wrap items-end">
        {(['cat', 'pck', 'src', 'ff', 'alt'] as const).map(key => (
          <div key={key}>
            <label className="text-xs text-gray-500 uppercase block">{key}</label>
            <select
              value={masters[key]}
              onChange={e => setMasters(p => ({ ...p, [key]: e.target.value }))}
              className="border rounded px-2 py-1 text-sm mt-0.5"
            >
              <option value="">-- {key.toUpperCase()} --</option>
              {(
                (template.masters as Record<string, { code: string; name: string }[]>)[
                  `${key.toUpperCase()}_OPTIONS`
                ] || []
              ).map((o: { code: string; name: string }) => (
                <option key={o.code} value={o.code}>
                  {o.code} — {o.name}
                </option>
              ))}
            </select>
          </div>
        ))}
        <div className="self-end text-xs text-gray-400 ml-auto">
          RUN: {runCode || '(auto on Save)'}
        </div>
      </div>

      {/* ZBFull code preview — one per SCN block (AP §3.3.2) */}
      {masters.cat && (
        <div className="px-3 py-1 border-b bg-blue-50 text-xs text-blue-700 font-mono flex gap-6">
          {SCN_TYPES.map(scn => (
            <span key={scn}>
              {[masters.cat, masters.pck, masters.src, masters.ff, masters.alt, scn]
                .filter(Boolean)
                .join('-')}
              -(RUN…)
            </span>
          ))}
        </div>
      )}

      {/* Entry grid — 3 SCN blocks × N XPeriod cols (AP §3.3.1) */}
      <div className="flex-1 overflow-auto">
        <table className="text-xs border-collapse w-max">
          <thead>
            {/* BUG-029: SCN block group headers */}
            <tr>
              <th colSpan={3} className="sticky left-0 z-10 bg-gray-50 border p-1" />
              {SCN_TYPES.map(scn => (
                <th
                  key={scn}
                  colSpan={xperiods.length}
                  className="border p-1 text-center font-semibold bg-gray-100 tracking-wide"
                >
                  {scn}
                </th>
              ))}
            </tr>
            <tr>
              {/* Frozen label columns */}
              <th className="sticky left-0 z-10 bg-white border p-2 min-w-[180px]">KRFull</th>
              <th className="sticky left-[180px] z-10 bg-white border p-2 min-w-[120px]">
                FilterFull
              </th>
              <th className="sticky left-[300px] z-10 bg-white border p-2 w-16">Unit</th>

              {/* 3 SCN blocks × N XPeriod */}
              {SCN_TYPES.map(scn =>
                xperiods.map(xp => (
                  <th
                    key={`${scn}-${xp.xperiod_code}`}
                    className="border p-2 min-w-[80px] text-center bg-gray-50"
                  >
                    <div>{xp.label || xp.xperiod_code}</div>
                  </th>
                ))
              )}
            </tr>
          </thead>
          <tbody>
            {yb_fulls.map(yb => (
              <tr key={yb.yb_full_code} className="hover:bg-blue-50/30">
                <td className="sticky left-0 bg-white border p-1.5 font-mono text-[10px]">
                  {yb.kr_full_code}
                </td>
                <td className="sticky left-[180px] bg-white border p-1.5 text-[10px]">
                  {yb.filter_full_code}
                </td>
                <td className="sticky left-[300px] bg-white border p-1.5 text-center">
                  {yb.unit}
                </td>
                {SCN_TYPES.map(scn =>
                  xperiods.map(xp => (
                    <td
                      key={`${scn}-${xp.xperiod_code}`}
                      className="border p-0"
                    >
                      <input
                        type="number"
                        value={
                          getCellValue(yb.yb_full_code, xp.xperiod_code, scn) ?? ''
                        }
                        onChange={e =>
                          setCellValue(
                            yb.yb_full_code,
                            xp.xperiod_code,
                            scn,
                            e.target.value === '' ? null : Number(e.target.value)
                          )
                        }
                        className="w-full h-full px-1 py-1 text-right focus:bg-blue-50 focus:outline-none"
                        placeholder="0"
                      />
                    </td>
                  ))
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Status bar */}
      <div className="p-2 border-t text-xs text-gray-500">
        {cells.size} cells filled · {yb_fulls.length} rows × {xperiods.length} periods ×{' '}
        {SCN_TYPES.length} SCN
      </div>
    </div>
  )
}
