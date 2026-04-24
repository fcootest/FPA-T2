import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { riApi } from '../api/ri'
import type { ConfigListItem } from '../types/ri'

export default function RIConfigListPage() {
  const [configs, setConfigs] = useState<ConfigListItem[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    riApi.listConfigs().then(setConfigs).finally(() => setLoading(false))
  }, [])

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this config?')) return
    await riApi.deleteConfig(id)
    setConfigs(prev => prev.filter(c => c.config_id !== id))
  }

  const handleClone = async (id: string, name: string) => {
    const cloned = await riApi.cloneConfig(id, `Copy of ${name}`)
    navigate(`/ri/configs/${cloned.config_id}`)
  }

  if (loading) return <div className="p-8">Loading...</div>

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">RI Config Templates</h1>
        <button
          onClick={() => navigate('/ri/configs/new')}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          + New Config
        </button>
      </div>
      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3">Code</th>
              <th className="text-left p-3">Name</th>
              <th className="text-center p-3">YBFull</th>
              <th className="text-center p-3">XPeriod</th>
              <th className="text-center p-3">Seed</th>
              <th className="text-right p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {configs.map(cfg => (
              <tr key={cfg.config_id} className="border-b hover:bg-gray-50">
                <td className="p-3 font-mono text-xs">{cfg.config_code}</td>
                <td className="p-3">{cfg.config_name}</td>
                <td className="p-3 text-center">
                  {cfg.yb_full_count}
                  {cfg.yb_full_count > 30 && <span className="ml-1 text-orange-500">⚠</span>}
                </td>
                <td className="p-3 text-center">
                  {cfg.xperiod_count}
                  {cfg.xperiod_count > 10 && <span className="ml-1 text-orange-500">⚠</span>}
                </td>
                <td className="p-3 text-center">{cfg.is_seed ? '🔒' : ''}</td>
                <td className="p-3 text-right space-x-2">
                  {!cfg.is_seed && (
                    <button
                      onClick={() => navigate(`/ri/configs/${cfg.config_id}`)}
                      className="text-blue-600 hover:underline"
                    >
                      Edit
                    </button>
                  )}
                  <button
                    onClick={() => handleClone(cfg.config_id, cfg.config_name)}
                    className="text-green-600 hover:underline"
                  >
                    Clone
                  </button>
                  {!cfg.is_seed && (
                    <button
                      onClick={() => handleDelete(cfg.config_id)}
                      className="text-red-600 hover:underline"
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
