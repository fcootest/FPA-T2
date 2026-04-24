import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { riApi } from '../api/ri'
import type { RIScreenConfig, XPeriod } from '../types/ri'

const RI_COLS = [
  'fnf', 'kr1', 'kr2', 'kr3', 'kr4', 'kr5', 'kr6', 'kr7', 'kr8',
  'cdt1', 'cdt2', 'cdt3', 'cdt4',
  'pt1_now', 'pt2_now', 'du_now', 'pt1_prev', 'pt2_prev', 'du_prev',
  'owntype', 'aitype', 'cty1', 'cty2', 'ostype', 'fu1', 'fu2', 'ch',
  'egt1', 'egt2', 'egt3', 'egt4', 'egt5', 'hr1', 'hr2', 'hr3', 'sec',
  'px', 'ppc', 'np', 'le1', 'le2', 'unit', 'td_bu', 'non_agg',
]

type GridRow = Record<string, string> & { _id: string }

function computePreview(row: GridRow) {
  const kr = ['kr1', 'kr2', 'kr3', 'kr4', 'kr5', 'kr6', 'kr7', 'kr8']
    .map(k => row[k]).filter(Boolean).join('-')
  const filter = ['cdt1', 'cdt2', 'cdt3', 'cdt4', 'td_bu']
    .map(k => row[k]).filter(Boolean).join('-')
  return { kr: kr || '—', filter: filter || '—' }
}

export default function RIConfigEditorPage() {
  const { id } = useParams<{ id?: string }>()
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

  // BUG-025: XPeriod pill UI state
  const [availableXperiods, setAvailableXperiods] = useState<XPeriod[]>([])
  const [xperiodPickerOpen, setXperiodPickerOpen] = useState(false)
  const pickerRef = useRef<HTMLDivElement>(null)

  // BUG-026: Preview panel state
  const [previewExpanded, setPreviewExpanded] = useState(false)

  useEffect(() => {
    if (!isNew && id) {
      riApi.getConfig(id).then(cfg => {
        setConfig(cfg)
        setXperiodCodes(cfg.xperiod_codes)
      })
    }
  }, [id, isNew])

  // BUG-025: Fetch available xperiods from masters
  useEffect(() => {
    riApi.getMasters('xperiods').then((data: { items?: XPeriod[] }) => {
      setAvailableXperiods(data.items || [])
    }).catch(() => {
      // silently ignore if endpoint unavailable
    })
  }, [])

  // BUG-026: Auto-expand preview when rows are added
  useEffect(() => {
    if (rows.length > 0) setPreviewExpanded(true)
  }, [rows.length > 0]) // eslint-disable-line react-hooks/exhaustive-deps

  // BUG-025: Close picker when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setXperiodPickerOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

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

  const updateCell = useCallback((rowIdx: number, col: string, value: string) => {
    setRows(prev => {
      const next = [...prev]
      next[rowIdx] = { ...next[rowIdx], [col]: value }
      return next
    })
  }, [])

  const deleteRow = (rowIdx: number) => {
    setRows(prev => prev.filter((_, i) => i !== rowIdx))
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

  // BUG-027: Fetch unit options from masters
  const [availableUnits, setAvailableUnits] = useState<{ code: string; name: string }[]>([])
  useEffect(() => {
    riApi.getMasters('units').then((data: { items?: { code: string; name: string }[] }) => {
      setAvailableUnits(data.items || [])
    }).catch(() => {})
  }, [])

  // BUG-028: Paste button handler
  const handlePasteButtonClick = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText()
      if (!text.includes('\t')) return
      const result = await riApi.pasteValidate(text)
      if (result.valid) {
        const newRows: GridRow[] = result.rows.map(
          (r: Record<string, string>, i: number) => ({
            _id: String(rows.length + i + 1),
            ...r,
          })
        )
        setRows(prev => [...prev, ...newRows])
      }
    } catch {
      // clipboard permission denied or API error
    }
  }, [rows.length])

  // BUG-025: xperiods not yet selected
  const unselectedXperiods = availableXperiods.filter(
    xp => !xperiodCodes.includes(xp.xperiod_code)
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>
          {isNew ? 'New Config' : `Edit: ${config.config_name}`}
        </h1>
        <div style={{ display: 'flex', gap: 8 }}>
          {isSeed && (
            <span style={{ padding: '4px 8px', background: '#e5e7eb', color: '#6b7280', borderRadius: 4, fontSize: 13 }}>
              🔒 Seed (read-only)
            </span>
          )}
          {!isSeed && (
            <button
              onClick={handleSave}
              disabled={saving}
              style={{ padding: '6px 16px', background: saving ? '#9ca3af' : '#2563eb', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          )}
          {!isNew && (
            <button
              onClick={() =>
                riApi.cloneConfig(id!, `Copy of ${config.config_name}`)
                  .then(c => navigate(`/ri/configs/${c.config_id}`))
              }
              style={{ padding: '6px 16px', border: '1px solid #d1d5db', borderRadius: 4, cursor: 'pointer', background: '#fff' }}
            >
              Clone
            </button>
          )}
          <button
            onClick={() => navigate('/ri/configs')}
            style={{ padding: '6px 16px', border: '1px solid #d1d5db', borderRadius: 4, cursor: 'pointer', background: '#fff' }}
          >
            ← Back
          </button>
        </div>
      </div>

      {/* Meta fields */}
      <div style={{ display: 'flex', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: 12, color: '#6b7280', display: 'block', marginBottom: 4 }}>Config Name</label>
          <input
            value={config.config_name || ''}
            onChange={e => setConfig(p => ({ ...p, config_name: e.target.value }))}
            disabled={isSeed}
            style={{ width: '100%', border: '1px solid #d1d5db', borderRadius: 4, padding: '4px 8px', boxSizing: 'border-box' }}
          />
        </div>

        {/* BUG-025: XPeriod pill/tag UI */}
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: 12, color: '#6b7280', display: 'block', marginBottom: 4 }}>
            XPeriod codes
          </label>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 4,
              alignItems: 'center',
              border: '1px solid #d1d5db',
              borderRadius: 4,
              padding: '4px 6px',
              minHeight: 34,
              background: isSeed ? '#f9fafb' : '#fff',
            }}
          >
            {xperiodCodes.map(code => (
              <span
                key={code}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  background: '#e5e7eb',
                  borderRadius: 3,
                  padding: '2px 6px',
                  fontSize: 12,
                  color: '#374151',
                }}
              >
                {code}
                {!isSeed && (
                  <button
                    onClick={() => setXperiodCodes(prev => prev.filter(c => c !== code))}
                    style={{
                      border: 'none',
                      background: 'none',
                      cursor: 'pointer',
                      color: '#6b7280',
                      fontSize: 11,
                      padding: 0,
                      lineHeight: 1,
                    }}
                    title={`Remove ${code}`}
                  >
                    ×
                  </button>
                )}
              </span>
            ))}
            {!isSeed && (
              <div ref={pickerRef} style={{ position: 'relative' }}>
                <button
                  onClick={() => setXperiodPickerOpen(prev => !prev)}
                  style={{
                    border: '1px dashed #9ca3af',
                    background: 'none',
                    borderRadius: 3,
                    padding: '2px 8px',
                    fontSize: 12,
                    color: '#6b7280',
                    cursor: 'pointer',
                  }}
                >
                  + Add {xperiodPickerOpen ? '▴' : '▾'}
                </button>
                {xperiodPickerOpen && (
                  <div
                    style={{
                      position: 'absolute',
                      top: '100%',
                      left: 0,
                      zIndex: 10,
                      background: '#fff',
                      border: '1px solid #d1d5db',
                      borderRadius: 4,
                      boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
                      minWidth: 160,
                      maxHeight: 200,
                      overflowY: 'auto',
                      marginTop: 2,
                    }}
                  >
                    {unselectedXperiods.length === 0 ? (
                      <div style={{ padding: '8px 12px', fontSize: 12, color: '#9ca3af' }}>
                        {availableXperiods.length === 0 ? 'Loading…' : 'All added'}
                      </div>
                    ) : (
                      unselectedXperiods.map(xp => (
                        <button
                          key={xp.xperiod_code}
                          onClick={() => {
                            setXperiodCodes(prev => [...prev, xp.xperiod_code])
                            setXperiodPickerOpen(false)
                          }}
                          style={{
                            display: 'block',
                            width: '100%',
                            textAlign: 'left',
                            padding: '6px 12px',
                            border: 'none',
                            background: 'none',
                            fontSize: 12,
                            cursor: 'pointer',
                            color: '#111827',
                          }}
                          onMouseEnter={e => (e.currentTarget.style.background = '#f3f4f6')}
                          onMouseLeave={e => (e.currentTarget.style.background = 'none')}
                        >
                          <span style={{ fontWeight: 600 }}>{xp.xperiod_code}</span>
                          {xp.label && (
                            <span style={{ color: '#6b7280', marginLeft: 6 }}>{xp.label}</span>
                          )}
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
          {xperiodCodes.length > 10 && (
            <p style={{ color: '#f97316', fontSize: 12, margin: '4px 0 0' }}>⚠ More than 10 XPeriods (still allowed)</p>
          )}
        </div>
      </div>

      {/* BUG-026: YBFull Preview Panel */}
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 4, overflow: 'hidden' }}>
        <button
          onClick={() => setPreviewExpanded(prev => !prev)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            width: '100%',
            padding: '6px 10px',
            background: '#f9fafb',
            border: 'none',
            borderBottom: previewExpanded ? '1px solid #e5e7eb' : 'none',
            cursor: 'pointer',
            fontSize: 13,
            color: '#374151',
            textAlign: 'left',
          }}
        >
          <span>{previewExpanded ? '▼' : '▶'}</span>
          <span>YBFull Preview ({rows.length} rows)</span>
        </button>
        {previewExpanded && (
          <div style={{ maxHeight: 180, overflowY: 'auto' }}>
            {rows.length === 0 ? (
              <p style={{ padding: '12px 10px', margin: 0, fontSize: 12, color: '#9ca3af' }}>No rows yet</p>
            ) : (
              <table style={{ borderCollapse: 'collapse', fontSize: 12, width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{ ...thStyle, position: 'sticky', top: 0, background: '#f9fafb', width: 32 }}>#</th>
                    <th style={{ ...thStyle, position: 'sticky', top: 0, background: '#f9fafb' }}>KRFull</th>
                    <th style={{ ...thStyle, position: 'sticky', top: 0, background: '#f9fafb' }}>FilterFull</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, ri) => {
                    const { kr, filter } = computePreview(row)
                    return (
                      <tr key={row._id} style={{ background: ri % 2 === 0 ? '#fff' : '#f9fafb' }}>
                        <td style={{ ...tdStyle, textAlign: 'center', color: '#9ca3af' }}>{ri + 1}</td>
                        <td style={{ ...tdStyle, fontFamily: 'monospace' }}>{kr}</td>
                        <td style={{ ...tdStyle, fontFamily: 'monospace' }}>{filter}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {rows.length > 30 && (
        <p style={{ color: '#f97316', fontSize: 13, margin: 0 }}>
          ⚠ {rows.length} rows — more than recommended 30 (still allowed)
        </p>
      )}

      {/* 44-col plain table — mirrors GSheet RI cols I:BA */}
      <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: 480, border: '1px solid #d1d5db', borderRadius: 4 }}>
        <table style={{ borderCollapse: 'collapse', fontSize: 12, minWidth: 'max-content' }}>
          <thead>
            <tr>
              <th style={{ ...thStyle, position: 'sticky', top: 0, left: 0, zIndex: 3, background: '#f9fafb', width: 32 }}>#</th>
              {RI_COLS.map(col => (
                <th key={col} style={{ ...thStyle, position: 'sticky', top: 0, zIndex: 2, background: '#f9fafb', minWidth: col === 'unit' ? 70 : 60 }}>
                  {col.toUpperCase()}
                </th>
              ))}
              {!isSeed && (
                <th style={{ ...thStyle, position: 'sticky', top: 0, zIndex: 2, background: '#f9fafb', width: 40 }}>✕</th>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={RI_COLS.length + 2} style={{ padding: '24px', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
                  No rows yet — click "+ Add Row" or Ctrl+V to paste from GSheet (cols I:BA)
                </td>
              </tr>
            ) : (
              rows.map((row, ri) => (
                <tr key={row._id} style={{ background: ri % 2 === 0 ? '#fff' : '#f9fafb' }}>
                  <td style={{ ...tdStyle, textAlign: 'center', color: '#9ca3af', position: 'sticky', left: 0, background: ri % 2 === 0 ? '#fff' : '#f9fafb', zIndex: 1 }}>
                    {ri + 1}
                  </td>
                  {RI_COLS.map(col => (
                    <td key={col} style={{ ...tdStyle, padding: 0 }}>
                      {col === 'unit' ? (
                        <select
                          value={row[col] || ''}
                          disabled={isSeed}
                          onChange={e => updateCell(ri, col, e.target.value)}
                          style={{
                            width: '100%',
                            border: 'none',
                            padding: '3px 5px',
                            fontSize: 12,
                            background: 'transparent',
                            outline: 'none',
                            minWidth: 70,
                            cursor: isSeed ? 'default' : 'pointer',
                          }}
                        >
                          <option value=""></option>
                          {availableUnits.map(u => (
                            <option key={u.code} value={u.code}>{u.code}</option>
                          ))}
                          {/* keep current value visible even if not in list yet */}
                          {row[col] && !availableUnits.some(u => u.code === row[col]) && (
                            <option value={row[col]}>{row[col]}</option>
                          )}
                        </select>
                      ) : (
                        <input
                          type="text"
                          value={row[col] || ''}
                          disabled={isSeed}
                          onChange={e => updateCell(ri, col, e.target.value)}
                          style={{
                            width: '100%',
                            border: 'none',
                            padding: '3px 5px',
                            fontSize: 12,
                            background: 'transparent',
                            outline: 'none',
                            minWidth: 60,
                          }}
                          onFocus={e => (e.target.style.background = '#eff6ff')}
                          onBlur={e => (e.target.style.background = 'transparent')}
                        />
                      )}
                    </td>
                  ))}
                  {!isSeed && (
                    <td style={{ ...tdStyle, textAlign: 'center' }}>
                      <button
                        onClick={() => deleteRow(ri)}
                        style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#ef4444', fontSize: 13 }}
                        title="Delete row"
                      >
                        ✕
                      </button>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {!isSeed && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            onClick={addRow}
            style={{ padding: '5px 12px', border: '1px solid #d1d5db', borderRadius: 4, cursor: 'pointer', background: '#fff', fontSize: 13 }}
          >
            + Add Row
          </button>
          <button
            onClick={handlePasteButtonClick}
            style={{ padding: '5px 12px', border: '1px solid #d1d5db', borderRadius: 4, cursor: 'pointer', background: '#fff', fontSize: 13 }}
            title="Copy cols I:BA from GSheet, then click here"
          >
            📋 Paste from GSheet
          </button>
          <span style={{ fontSize: 12, color: '#9ca3af' }}>
            {rows.length} rows · cols I:BA
          </span>
        </div>
      )}
    </div>
  )
}

const thStyle: React.CSSProperties = {
  border: '1px solid #e5e7eb',
  padding: '5px 6px',
  fontWeight: 600,
  textAlign: 'left',
  whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  border: '1px solid #e5e7eb',
  padding: '2px 4px',
}
