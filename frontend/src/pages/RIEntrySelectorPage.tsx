import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { riApi } from '../api/ri'
import type { ConfigListItem } from '../types/ri'

export default function RIEntrySelectorPage() {
  const [configs, setConfigs] = useState<ConfigListItem[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    riApi.listConfigs().then(setConfigs).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8">Loading...</div>

  const seedConfigs = configs.filter(c => c.is_seed)
  const userConfigs = configs.filter(c => !c.is_seed)

  const ConfigRow = ({ cfg }: { cfg: ConfigListItem }) => (
    <div
      key={cfg.config_id}
      className="flex items-center justify-between p-4 hover:bg-gray-50 cursor-pointer"
      onClick={() => navigate(`/ri/entries/create?config=${cfg.config_id}`)}
    >
      <div>
        <div className="font-medium">{cfg.config_name}</div>
        <div className="text-sm text-gray-500">
          {cfg.config_code} · {cfg.yb_full_count} rows · {cfg.xperiod_count} periods
        </div>
      </div>
      <div className="flex items-center gap-2">
        {cfg.is_seed && <span className="text-xs text-gray-500">🔒 Seed</span>}
        <span className="text-blue-600">→</span>
      </div>
    </div>
  )

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Select Config Template</h1>
      <div className="border rounded-lg overflow-hidden">
        {/* BUG-031: Seed section */}
        {seedConfigs.length > 0 && (
          <>
            <div className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wide bg-gray-50 border-b">
              System Templates
            </div>
            <div className="divide-y">
              {seedConfigs.map(cfg => <ConfigRow key={cfg.config_id} cfg={cfg} />)}
            </div>
          </>
        )}
        {/* BUG-031: User section */}
        {userConfigs.length > 0 && (
          <>
            <div className={`px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wide bg-gray-50 border-b${seedConfigs.length > 0 ? ' border-t' : ''}`}>
              My Templates
            </div>
            <div className="divide-y">
              {userConfigs.map(cfg => <ConfigRow key={cfg.config_id} cfg={cfg} />)}
            </div>
          </>
        )}
        {configs.length === 0 && (
          <div className="p-8 text-center text-gray-400 text-sm">
            No templates yet — create one below
          </div>
        )}
      </div>
      <button
        onClick={() => navigate('/ri/configs/new')}
        className="mt-4 text-blue-600 hover:underline text-sm"
      >
        + Create new config
      </button>
    </div>
  )
}
