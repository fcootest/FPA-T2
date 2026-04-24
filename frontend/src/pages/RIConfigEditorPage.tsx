import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
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
        <div style={{ flex: 1 }}>
          <label style={{ fontSize: 12, color: '#6b7280', display: 'block', marginBottom: 4 }}>
            XPeriod codes (comma-separated)
          </label>
          <input
            value={xperiodCodes.join(',')}
            onChange={e =>
              setXperiodCodes(e.target.value.split(',').map(s => s.trim()).filter(Boolean))
            }
            disabled={isSeed}
            placeholder="M2601,Q2603,Y26"
            style={{ width: '100%', border: '1px solid #d1d5db', borderRadius: 4, padding: '4px 8px', boxSizing: 'border-box' }}
          />
          {xperiodCodes.length > 10 && (
            <p style={{ color: '#f97316', fontSize: 12, margin: '4px 0 0' }}>⚠ More than 10 XPeriods (still allowed)</p>
          )}
        </div>
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
                          minWidth: col === 'unit' ? 70 : 60,
                        }}
                        onFocus={e => (e.target.style.background = '#eff6ff')}
                        onBlur={e => (e.target.style.background = 'transparent')}
                      />
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
          <span style={{ fontSize: 12, color: '#9ca3af' }}>
            or Ctrl+V to paste from GSheet (cols I:BA) · {rows.length} rows
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
