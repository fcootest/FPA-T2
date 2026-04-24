import axios from 'axios'
import type { ConfigListItem, RIScreenConfig, SaveConfigRequest, EntryTemplateResponse, SaveEntryRequest, SaveEntryResponse, RIScreenEntry } from '../types/ri'

const api = axios.create({ baseURL: '/api/ri' })

export const riApi = {
  listConfigs: () => api.get<ConfigListItem[]>('/configs').then(r => r.data),
  getConfig: (id: string) => api.get<RIScreenConfig>(`/configs/${id}`).then(r => r.data),
  createConfig: (req: SaveConfigRequest) => api.post<RIScreenConfig>('/configs', req).then(r => r.data),
  updateConfig: (id: string, req: SaveConfigRequest) => api.put<RIScreenConfig>(`/configs/${id}`, req).then(r => r.data),
  deleteConfig: (id: string) => api.delete(`/configs/${id}`),
  cloneConfig: (id: string, newName: string) => api.post<RIScreenConfig>(`/configs/${id}/clone`, { new_name: newName }).then(r => r.data),
  pasteValidate: (tsv: string) => api.post('/configs/paste-validate', { tsv }).then(r => r.data),

  getEntryTemplate: (configId: string) => api.get<EntryTemplateResponse>(`/entries/template/${configId}`).then(r => r.data),
  saveEntry: (req: SaveEntryRequest) => api.post<SaveEntryResponse>('/entries', req).then(r => r.data),
  getEntry: (id: string) => api.get<RIScreenEntry>(`/entries/${id}`).then(r => r.data),
  getEntryDisplay: (id: string) => api.get(`/entries/${id}/display`).then(r => r.data),

  getMasters: (type: string) => api.get(`/masters/${type}`).then(r => r.data),
}
