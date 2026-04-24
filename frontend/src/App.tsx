import { Component, type ErrorInfo, type ReactNode } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import RIConfigListPage from './pages/RIConfigListPage'
import RIConfigEditorPage from './pages/RIConfigEditorPage'
import RIEntrySelectorPage from './pages/RIEntrySelectorPage'
import RIEntryGridPage from './pages/RIEntryGridPage'

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[FPA-T2 ErrorBoundary]', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 40, fontFamily: 'monospace' }}>
          <h2 style={{ color: '#dc2626' }}>Lỗi giao diện</h2>
          <p style={{ color: '#6b7280', marginBottom: 16 }}>
            Màn hình gặp lỗi không mong muốn. Thông tin kỹ thuật ở console.
          </p>
          <pre style={{ background: '#fef2f2', padding: 16, borderRadius: 4, fontSize: 12, overflowX: 'auto', color: '#991b1b' }}>
            {(this.state.error as Error).message}
          </pre>
          <button
            onClick={() => { this.setState({ error: null }); window.location.reload() }}
            style={{ marginTop: 16, padding: '8px 16px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
          >
            Tải lại trang
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<RIConfigListPage />} />
          <Route path="/ri/configs" element={<RIConfigListPage />} />
          <Route path="/ri/configs/new" element={<RIConfigEditorPage />} />
          <Route path="/ri/configs/:id" element={<RIConfigEditorPage />} />
          <Route path="/ri/entries/new" element={<RIEntrySelectorPage />} />
          <Route path="/ri/entries/create" element={<RIEntryGridPage />} />
          <Route path="/ri/entries/:id" element={<RIEntryGridPage />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
