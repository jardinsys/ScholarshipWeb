import { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Navbar } from '@/components/Navbar'
import DashboardPage from '@/pages/DashboardPage'
import BrowsePage from '@/pages/BrowsePage'
import ProfilePage from '@/pages/ProfilePage'

function App() {
  const [user, setUser] = useState(null)  // null = logged out

  return (
    <BrowserRouter>
      <div className="min-h-dvh">
        <Navbar user={user} onLogout={() => setUser(null)} />
        <Routes>
          <Route path="/"          element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage user={user} onAuth={setUser} />} />
          <Route path="/browse"    element={<BrowsePage user={user} onAuth={setUser} />} />
          <Route path="/profile"   element={<ProfilePage user={user} />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App