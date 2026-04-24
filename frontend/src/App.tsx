import { BrowserRouter, Routes, Route } from 'react-router-dom'
import RIConfigListPage from './pages/RIConfigListPage'
import RIConfigEditorPage from './pages/RIConfigEditorPage'
import RIEntrySelectorPage from './pages/RIEntrySelectorPage'
import RIEntryGridPage from './pages/RIEntryGridPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RIConfigListPage />} />
        <Route path="/ri/configs" element={<RIConfigListPage />} />
        <Route path="/ri/configs/new" element={<RIConfigEditorPage />} />
        <Route path="/ri/configs/:id" element={<RIConfigEditorPage />} />
        <Route path="/ri/entries/new" element={<RIEntrySelectorPage />} />
        <Route path="/ri/entries/:id" element={<RIEntryGridPage />} />
      </Routes>
    </BrowserRouter>
  )
}
