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

// Fix 3: hardcoded — no /masters/units endpoint exists
const UNIT_OPTIONS = ['bVND', 'mVND', 'VND', 'mUSD', 'USD', '%', 'pers', 'hrs', '#']

type GridRow = Record<string, string> & { _id: string }

function computePreview(row: GridRow) {
  const kr = ['kr1', 'kr2', 'kr3', 'kr4', 'kr5', 'kr6', 'kr7', 'kr8']
    .map(k => row[k]).filter(Boolean).join('-')
  const filter = ['cdt1', 'cdt2', 'cdt3', 'cdt4', 'td_bu']
    .map(k => row[k]).filter(Boolean).join('-')
  return { kr: kr || '—', filter: filter || '—' }
}

// Parse raw TSV text into GridRow array, mapping by column position (cols I:BA)
function parseTsvToRows(tsv: string, baseIdx: number): GridRow[] {
  return tsv
    .trim()
    .split('\n')
    .map((line, i) => {
      const cells = line.split('\t')
      const row: GridRow = {
        _id: String(baseIdx + i + 1),
        ...Object.fromEntries(RI_COLS.map(c => [c, ''])),
      }
      RI_COLS.forEach((col, ci) => {
        row[col] = (cells[ci] ?? '').trim()
      })
      return row
    })
    .filter(r => RI_COLS.some(c => r[c] !== ''))
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
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null)

  // Fix 2: XPeriod master list — backend returns plain array, not {items:[]}
  const [availableXperiods, setAvailableXperiods] = useState<XPeriod[]>([])

  // Preview panel
  const [previewExpanded, setPreviewExpanded] = useState(false)

  // Fix 4: paste modal
  const [pasteModalOpen, setPasteModalOpen] = useState(false)
  const [pasteText, setPasteText] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!isNew && id) {
      riApi.getConfig(id).then(cfg => {
        setConfig(cfg)
        setXperiodCodes(cfg.xperiod_codes)
      })
    }
  }, [id, isNew])

  // Fix 2: correctly handle plain-array response from /masters/xperiods
  useEffect(() => {
    riApi.getMasters('xperiods')
      .then((data: unknown) => {
        const list = Array.isArray(data) ? data : (data as { items?: XPeriod[] }).items ?? []
        setAvailableXperiods(list as XPeriod[])
      })
      .catch(() => {})
  }, [])

  // Auto-expand preview when first row is added
  useEffect(() => {
    if (rows.length > 0 && !previewExpanded) setPreviewExpanded(true)
  }, [rows.length]) // eslint-disable-line react-hooks/exhaustive-deps

  // Ctrl+V anywhere on page still works
  const handlePaste = useCallback(
    (e: ClipboardEvent) => {
      // Ignore if user is typing in an input/textarea
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') return
      const tsv = e.clipboardData?.getData('text/plain') || ''
      if (!tsv.includes('\t')) return
      e.preventDefault()
      const newRows = parseTsvToRows(tsv, rows.length)
      if (newRows.length > 0) setRows(prev => [...prev, ...newRows])
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
    setSaveMsg(null)
    try {
      const req = {
        config_name: config.config_name || '',
        config_code: config.config_code,
        rows: rows.map(r => {
          const { _id, ...rest } = r
          return { kr_items: [], filter_items: [], ...rest }
        }),
        xperiod_codes: xperiodCodes.filter(Boolean),
      }
      if (isNew) {
        await riApi.createConfig(req)
        // Navigate to entry selector so user immediately sees the new config
        navigate('/ri/entries/new')
      } else {
        await riApi.updateConfig(id!, req)
        setSaveMsg({ ok: true, text: `Đã lưu "${config.config_name}" thành công.` })
        setTimeout(() => setSaveMsg(null), 4000)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setSaveMsg({ ok: false, text: `Lỗi khi lưu: ${msg}` })
    } finally {
      setSaving(false)
    }
  }

  // Fix 4: import paste modal text
  const handlePasteImport = () => {
    if (!pasteText.trim()) return
    const newRows = parseTsvToRows(pasteText, rows.length)
    if (newRows.length > 0) {
      setRows(prev => [...prev, ...newRows])
    }
    setPasteText('')
    setPasteModalOpen(false)
  }

  // Fix 4: import from CSV/TSV file
  const handleFileImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => {
      const text = ev.target?.result as string
      // Normalize: CSV with commas → only treat as TSV if tabs present
      const tsv = text.includes('\t') ? text : text.replace(/,/g, '\t')
      const newRows = parseTsvToRows(tsv, rows.length)
      if (newRows.length > 0) setRows(prev => [...prev, ...newRows])
    }
    reader.readAsText(file)
    // Reset so same file can be picked again
    e.target.value = ''
  }

  const isSeed = config.is_seed === true

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, height: '100vh', overflow: 'hidden' }}>
      {/* Fix 1: RIConfigHeader — code + name + seed badge + actions */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '8px 16px',
        borderBottom: '1px solid #e5e7eb', background: '#fff', flexShrink: 0,
      }}>
        {/* Code */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 110 }}>
          <label style={{ fontSize: 10, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Code</label>
          <input
            value={config.config_code || ''}
            onChange={e => setConfig(p => ({ ...p, config_code: e.target.value }))}
            disabled={isSeed}
            placeholder="e.g. RI-GH-01"
            style={{
              border: '1px solid #d1d5db', borderRadius: 4, padding: '3px 7px',
              fontSize: 13, width: 110,
              background: isSeed ? '#f9fafb' : '#fff',
            }}
          />
        </div>

        {/* Name */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1, maxWidth: 320 }}>
          <label style={{ fontSize: 10, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Name</label>
          <input
            value={config.config_name || ''}
            onChange={e => setConfig(p => ({ ...p, config_name: e.target.value }))}
            disabled={isSeed}
            placeholder="Config name"
            style={{
              border: '1px solid #d1d5db', borderRadius: 4, padding: '3px 7px',
              fontSize: 13, width: '100%',
              background: isSeed ? '#f9fafb' : '#fff',
            }}
          />
        </div>

        {/* Seed badge */}
        {isSeed && (
          <span style={{
            padding: '3px 8px', background: '#fef3c7', color: '#92400e',
            borderRadius: 4, fontSize: 12, fontWeight: 600, border: '1px solid #fde68a',
          }}>
            🔒 Seed — Read Only
          </span>
        )}

        <div style={{ flex: 1 }} />

        {/* Save message inline */}
        {saveMsg && (
          <span style={{
            fontSize: 12, padding: '4px 10px', borderRadius: 4, fontWeight: 500,
            background: saveMsg.ok ? '#dcfce7' : '#fee2e2',
            color: saveMsg.ok ? '#166534' : '#991b1b',
            border: `1px solid ${saveMsg.ok ? '#86efac' : '#fca5a5'}`,
          }}>
            {saveMsg.ok ? '✓ ' : '✗ '}{saveMsg.text}
          </span>
        )}

        {/* Actions */}
        {!isSeed && (
          <button
            onClick={handleSave}
            disabled={saving || !config.config_name}
            title={!config.config_name ? 'Nhập tên config trước' : undefined}
            style={{
              padding: '5px 16px', background: saving ? '#9ca3af' : (!config.config_name ? '#d1d5db' : '#2563eb'),
              color: '#fff', border: 'none', borderRadius: 4,
              cursor: saving || !config.config_name ? 'not-allowed' : 'pointer',
              fontSize: 13, fontWeight: 600,
            }}
          >
            {saving ? 'Đang lưu…' : '💾 Save'}
          </button>
        )}
        {!isNew && (
          <button
            onClick={() =>
              riApi.cloneConfig(id!, `Copy of ${config.config_name}`)
                .then(c => navigate(`/ri/configs/${c.config_id}`))
            }
            style={{ padding: '5px 12px', border: '1px solid #d1d5db', borderRadius: 4, cursor: 'pointer', background: '#fff', fontSize: 13 }}
          >
            Clone
          </button>
        )}
        <button
          onClick={() => navigate('/ri/entries/new')}
          style={{ padding: '5px 12px', border: '1px solid #d1d5db', borderRadius: 4, cursor: 'pointer', background: '#fff', fontSize: 13 }}
        >
          ← Entries
        </button>
        <button
          onClick={() => navigate('/ri/configs')}
          style={{ padding: '5px 12px', border: '1px solid #d1d5db', borderRadius: 4, cursor: 'pointer', background: '#fff', fontSize: 13, color: '#6b7280' }}
        >
          Configs
        </button>
      </div>

      {/* Scrollable body */}
      <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 12, padding: 16 }}>

        {/* Fix 2: XPeriod as slot-dropdowns row */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: '#6b7280', fontWeight: 600 }}>
            XPeriod Kỳ ({xperiodCodes.filter(Boolean).length} kỳ)
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
            {xperiodCodes.map((code, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 2, border: '1px solid #d1d5db', borderRadius: 4, background: '#fff', overflow: 'hidden' }}>
                <select
                  value={code}
                  disabled={isSeed}
                  onChange={e => {
                    const next = [...xperiodCodes]
                    next[idx] = e.target.value
                    setXperiodCodes(next)
                  }}
                  style={{
                    border: 'none', padding: '4px 6px', fontSize: 12,
                    background: 'transparent', cursor: isSeed ? 'default' : 'pointer',
                    outline: 'none', minWidth: 90,
                  }}
                >
                  <option value="">-- chọn kỳ --</option>
                  {availableXperiods.map(xp => (
                    <option key={xp.xperiod_code} value={xp.xperiod_code}>
                      {xp.xperiod_code}{xp.label ? ` · ${xp.label}` : ''}
                    </option>
                  ))}
                  {/* Keep existing value if not in master yet */}
                  {code && !availableXperiods.some(x => x.xperiod_code === code) && (
                    <option value={code}>{code}</option>
                  )}
                </select>
                {!isSeed && (
                  <button
                    onClick={() => setXperiodCodes(prev => prev.filter((_, i) => i !== idx))}
                    style={{ border: 'none', background: '#f3f4f6', cursor: 'pointer', padding: '4px 6px', color: '#6b7280', fontSize: 12, lineHeight: 1 }}
                    title="Xóa kỳ này"
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
            {!isSeed && (
              <button
                onClick={() => setXperiodCodes(prev => [...prev, ''])}
                style={{
                  padding: '4px 10px', border: '1px dashed #9ca3af', borderRadius: 4,
                  background: '#fff', cursor: 'pointer', fontSize: 12, color: '#6b7280',
                }}
              >
                + Thêm kỳ
              </button>
            )}
            {availableXperiods.length === 0 && (
              <span style={{ fontSize: 11, color: '#f97316' }}>
                ⚠ Chưa load được danh mục XPeriod — server offline?
              </span>
            )}
          </div>
          {xperiodCodes.filter(Boolean).length > 10 && (
            <p style={{ color: '#f97316', fontSize: 12, margin: 0 }}>⚠ Hơn 10 kỳ — vẫn cho phép</p>
          )}
        </div>

        {/* YBFull Preview Panel */}
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 4, overflow: 'hidden' }}>
          <button
            onClick={() => setPreviewExpanded(prev => !prev)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6, width: '100%',
              padding: '6px 10px', background: '#f9fafb', border: 'none',
              borderBottom: previewExpanded ? '1px solid #e5e7eb' : 'none',
              cursor: 'pointer', fontSize: 13, color: '#374151', textAlign: 'left',
            }}
          >
            <span>{previewExpanded ? '▼' : '▶'}</span>
            <span>YBFull Preview ({rows.length} dòng)</span>
          </button>
          {previewExpanded && (
            <div style={{ maxHeight: 180, overflowY: 'auto' }}>
              {rows.length === 0 ? (
                <p style={{ padding: '12px 10px', margin: 0, fontSize: 12, color: '#9ca3af' }}>Chưa có dòng nào</p>
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
            ⚠ {rows.length} dòng — nhiều hơn khuyến nghị 30
          </p>
        )}

        {/* 44-col grid */}
        <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: 440, border: '1px solid #d1d5db', borderRadius: 4, flex: '1 1 auto' }}>
          <table style={{ borderCollapse: 'collapse', fontSize: 12, minWidth: 'max-content' }}>
            <thead>
              <tr>
                <th style={{ ...thStyle, position: 'sticky', top: 0, left: 0, zIndex: 3, background: '#f9fafb', width: 32 }}>#</th>
                {RI_COLS.map(col => (
                  <th key={col} style={{ ...thStyle, position: 'sticky', top: 0, zIndex: 2, background: '#f9fafb', minWidth: col === 'unit' ? 90 : 60 }}>
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
                  <td colSpan={RI_COLS.length + 2} style={{ padding: '32px', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
                    Chưa có dòng — nhấn "+ Add Row", hoặc dùng nút Paste / Import bên dưới
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
                          // Fix 3: hardcoded unit options
                          <select
                            value={row[col] || ''}
                            disabled={isSeed}
                            onChange={e => updateCell(ri, col, e.target.value)}
                            style={{
                              width: '100%', border: 'none', padding: '3px 4px',
                              fontSize: 12, background: 'transparent', outline: 'none',
                              minWidth: 90, cursor: isSeed ? 'default' : 'pointer',
                            }}
                          >
                            <option value=""></option>
                            {UNIT_OPTIONS.map(u => <option key={u} value={u}>{u}</option>)}
                            {row[col] && !UNIT_OPTIONS.includes(row[col]) && (
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
                              width: '100%', border: 'none', padding: '3px 5px',
                              fontSize: 12, background: 'transparent', outline: 'none', minWidth: 60,
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
                          title="Xóa dòng"
                        >✕</button>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Fix 4: toolbar with paste modal + file import */}
        {!isSeed && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              onClick={addRow}
              style={{ padding: '5px 12px', border: '1px solid #d1d5db', borderRadius: 4, cursor: 'pointer', background: '#fff', fontSize: 13 }}
            >
              + Add Row
            </button>
            <button
              onClick={() => { setPasteText(''); setPasteModalOpen(true) }}
              style={{ padding: '5px 12px', border: '1px solid #d1d5db', borderRadius: 4, cursor: 'pointer', background: '#fff', fontSize: 13 }}
            >
              📋 Paste from GSheet
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              style={{ padding: '5px 12px', border: '1px solid #d1d5db', borderRadius: 4, cursor: 'pointer', background: '#fff', fontSize: 13 }}
            >
              📁 Import Excel/CSV
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.tsv,.txt"
              style={{ display: 'none' }}
              onChange={handleFileImport}
            />
            <span style={{ fontSize: 12, color: '#9ca3af' }}>
              {rows.length} dòng · thứ tự cột I:BA của GSheet
            </span>
          </div>
        )}
      </div>

      {/* Fix 4: Paste modal */}
      {pasteModalOpen && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
          }}
          onClick={e => { if (e.target === e.currentTarget) setPasteModalOpen(false) }}
        >
          <div style={{ background: '#fff', borderRadius: 8, padding: 24, width: 560, maxWidth: '90vw', boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}>
            <h3 style={{ margin: '0 0 8px', fontSize: 16, fontWeight: 700 }}>📋 Paste from GSheet</h3>
            <p style={{ margin: '0 0 12px', fontSize: 13, color: '#6b7280', lineHeight: 1.5 }}>
              1. Trong GSheet, chọn range dữ liệu <strong>cột I đến BA</strong> (44 cột: FNF → NON_AGG)<br />
              2. Copy (Ctrl+C)<br />
              3. Click vào ô bên dưới → Ctrl+V<br />
              4. Nhấn <strong>Import</strong>
            </p>
            <textarea
              autoFocus
              value={pasteText}
              onChange={e => setPasteText(e.target.value)}
              placeholder="Paste dữ liệu từ GSheet vào đây (Ctrl+V)…"
              style={{
                width: '100%', height: 160, border: '1px solid #d1d5db', borderRadius: 4,
                padding: 8, fontSize: 12, fontFamily: 'monospace', resize: 'vertical',
                boxSizing: 'border-box',
              }}
            />
            <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setPasteModalOpen(false)}
                style={{ padding: '6px 16px', border: '1px solid #d1d5db', borderRadius: 4, cursor: 'pointer', background: '#fff', fontSize: 13 }}
              >
                Hủy
              </button>
              <button
                onClick={handlePasteImport}
                disabled={!pasteText.trim()}
                style={{
                  padding: '6px 16px', background: pasteText.trim() ? '#2563eb' : '#9ca3af',
                  color: '#fff', border: 'none', borderRadius: 4, cursor: pasteText.trim() ? 'pointer' : 'default',
                  fontSize: 13, fontWeight: 600,
                }}
              >
                Import {pasteText.trim() ? `(${pasteText.trim().split('\n').filter(Boolean).length} dòng)` : ''}
              </button>
            </div>
          </div>
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
