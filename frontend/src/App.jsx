import { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, NavLink } from 'react-router-dom'
import api from './services/api'
import Tenants from './pages/Tenants'
import TenantDetail from './pages/TenantDetail'
import ExtensionDetail from './pages/ExtensionDetail'
import Security from './pages/Security'
import CDRPage from './pages/CDRPage'
import IVRPage from './pages/IVRPage'
import RoutesPage from './pages/RoutesPage'
import VoicemailPage from './pages/VoicemailPage'
import ProvisioningPage from './pages/ProvisioningPage'
import SchedulesPage from './pages/SchedulesPage'
import E911Page from './pages/E911Page'
import FaxSMSPage from './pages/FaxSMSPage'
import './App.css'

const NAV = [
  { to: '/tenants',     label: 'Tenants' },
  { to: '/ivr',         label: 'IVR / Files' },
  { to: '/routes',      label: 'Routes' },
  { to: '/voicemail',   label: 'Voicemail' },
  { to: '/provisioning',label: 'Téléphones' },
  { to: '/schedules',   label: 'Horaires' },
  { to: '/e911',        label: '911' },
  { to: '/fax-sms',     label: 'Fax / SMS' },
  { to: '/cdr',         label: 'CDR' },
  { to: '/security',    label: 'Sécurité' },
]

function Login({ onLogin }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const submit = async e => {
    e.preventDefault()
    setError('')
    try {
      const { data } = await api.post('/auth/login', { email, password })
      localStorage.setItem('sipv_token', data.access_token)
      onLogin()
    } catch {
      setError('Identifiants invalides')
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-form" onSubmit={submit}>
        <h2>Simple IP SIPV</h2>
        {error && <div className="error-msg">{error}</div>}
        <input placeholder="Courriel" value={email} onChange={e => setEmail(e.target.value)} type="email" required />
        <input placeholder="Mot de passe" value={password} onChange={e => setPassword(e.target.value)} type="password" required />
        <button type="submit">Connexion</button>
      </form>
    </div>
  )
}

function Layout({ onLogout, children }) {
  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="sidebar-title">SIPV Admin</div>
        {NAV.map(n => (
          <NavLink key={n.to} to={n.to} className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}>
            {n.label}
          </NavLink>
        ))}
        <button className="logout-btn" onClick={onLogout}>Déconnexion</button>
      </nav>
      <main className="main-content">{children}</main>
    </div>
  )
}

function AppRoutes({ onLogout }) {
  return (
    <Layout onLogout={onLogout}>
      <Routes>
        <Route path="/" element={<Navigate to="/tenants" replace />} />
        <Route path="/tenants" element={<Tenants />} />
        <Route path="/tenants/:id" element={<TenantDetail />} />
        <Route path="/extensions/:id" element={<ExtensionDetail />} />
        <Route path="/ivr" element={<IVRPage />} />
        <Route path="/routes" element={<RoutesPage />} />
        <Route path="/voicemail" element={<VoicemailPage />} />
        <Route path="/provisioning" element={<ProvisioningPage />} />
        <Route path="/schedules" element={<SchedulesPage />} />
        <Route path="/e911" element={<E911Page />} />
        <Route path="/fax-sms" element={<FaxSMSPage />} />
        <Route path="/cdr" element={<CDRPage />} />
        <Route path="/security" element={<Security />} />
      </Routes>
    </Layout>
  )
}

export default function App() {
  const [auth, setAuth] = useState(!!localStorage.getItem('sipv_token'))

  const logout = () => {
    localStorage.removeItem('sipv_token')
    setAuth(false)
  }

  if (!auth) return <Login onLogin={() => setAuth(true)} />

  return (
    <BrowserRouter>
      <AppRoutes onLogout={logout} />
    </BrowserRouter>
  )
}
