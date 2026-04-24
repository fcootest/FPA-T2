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

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Select Config Template</h1>
      <div className="border rounded-lg overflow-hidden divide-y">
        {configs.map(cfg => (
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
        ))}
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
