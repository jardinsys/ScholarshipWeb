import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Navbar } from '@/components/Navbar'
import DashboardPage from '@/pages/DashboardPage'
import ProfilePage   from '@/pages/ProfilePage'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-dvh">
        <Navbar />
        <Routes>
          <Route path="/"          element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App