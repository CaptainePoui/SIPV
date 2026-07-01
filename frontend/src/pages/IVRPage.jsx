import { useState, useEffect } from 'react'
import api from '../services/api'

export default function IVRPage() {
  const [tenants, setTenants] = useState([])
  const [tenantId, setTenantId] = useState('')
  const [ivrs, setIvrs] = useState([])
  const [queues, setQueues] = useState([])
  const [ringGroups, setRingGroups] = useState([])
  const [tab, setTab] = useState('IVR')
  const [showIVRModal, setShowIVRModal] = useState(false)
  const [ivrForm, setIvrForm] = useState({ name: '', greeting_message: '', timeout_seconds: 10, max_retries: 3, invalid_destination: '', timeout_destination: '' })

  useEffect(() => { api.get('/tenants').then(r => setTenants(r.data)) }, [])

  const load = async (tid = tenantId) => {
    if (!tid) return
    const [i, q, r] = await Promise.all([
      api.get(`/ivr/ivrs/tenant/${tid}`),
      api.get(`/ivr/queues/tenant/${tid}`),
      api.get(`/ivr/ring-groups/tenant/${tid}`),
    ])
    setIvrs(i.data)
    setQueues(q.data)
    setRingGroups(r.data)
  }

  useEffect(() => { load() }, [tenantId])

  const saveIVR = async e => {
    e.preventDefault()
    await api.post(`/ivr/ivrs/tenant/${tenantId}`, ivrForm)
    setShowIVRModal(false)
    setIvrForm({ name: '', greeting_message: '', timeout_seconds: 10, max_retries: 3, invalid_destination: '', timeout_destination: '' })
    load()
  }

  const deleteIVR = async id => {
    if (!confirm('Supprimer cet IVR?')) return
    await api.delete(`/ivr/ivrs/${id}`)
    load()
  }

  return (
    <div>
      <h1 className="page-title">IVR / Files d'attente</h1>
      <div className="toolbar">
        <select className="search-input" value={tenantId} onChange={e => { setTenantId(e.target.value) }}>
          <option value="">Sélectionner un tenant</option>
          {tenants.map(t => <option key={t.id} value={t.id}>{t.company_name}</option>)}
        </select>
      </div>

      <div className="tabs">
        {['IVR', 'Files d\'attente', 'Groupes d\'appels'].map(t => (
          <button key={t} className={`tab-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'IVR' && (
        <div>
          <div style={{ marginBottom: '.75rem' }}>
            <button className="btn btn-primary btn-sm" disabled={!tenantId} onClick={() => setShowIVRModal(true)}>+ IVR</button>
          </div>
          <table>
            <thead><tr><th>Nom</th><th>Timeout</th><th>Max tentatives</th><th>Destination invalide</th><th></th></tr></thead>
            <tbody>
              {ivrs.map(i => (
                <tr key={i.id}>
                  <td>{i.name}</td>
                  <td>{i.timeout_seconds}s</td>
                  <td>{i.max_retries}</td>
                  <td>{i.invalid_destination || '—'}</td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => deleteIVR(i.id)}>Suppr.</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'Files d\'attente' && (
        <table>
          <thead><tr><th>Nom</th><th>Stratégie</th><th>Timeout</th><th>Max attente</th><th>Musique</th></tr></thead>
          <tbody>
            {queues.map(q => (
              <tr key={q.id}>
                <td>{q.name}</td>
                <td>{q.strategy}</td>
                <td>{q.timeout_seconds}s</td>
                <td>{q.max_wait_seconds}s</td>
                <td>{q.music_on_hold || 'default'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === 'Groupes d\'appels' && (
        <table>
          <thead><tr><th>Nom</th><th>Extension</th><th>Stratégie</th><th>Membres</th><th>Sonnerie</th></tr></thead>
          <tbody>
            {ringGroups.map(r => (
              <tr key={r.id}>
                <td>{r.name}</td>
                <td>{r.extension}</td>
                <td>{r.ring_strategy}</td>
                <td style={{ fontFamily: 'monospace', fontSize: '.82rem' }}>{r.members}</td>
                <td>{r.ring_time}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showIVRModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Nouvel IVR</h3>
            <form onSubmit={saveIVR}>
              <div className="form-group"><label>Nom</label><input value={ivrForm.name} onChange={e => setIvrForm({ ...ivrForm, name: e.target.value })} required /></div>
              <div className="form-group"><label>Message d'accueil</label><input value={ivrForm.greeting_message} onChange={e => setIvrForm({ ...ivrForm, greeting_message: e.target.value })} /></div>
              <div className="form-group"><label>Timeout (sec)</label><input type="number" value={ivrForm.timeout_seconds} onChange={e => setIvrForm({ ...ivrForm, timeout_seconds: +e.target.value })} /></div>
              <div className="form-group"><label>Max tentatives</label><input type="number" value={ivrForm.max_retries} onChange={e => setIvrForm({ ...ivrForm, max_retries: +e.target.value })} /></div>
              <div className="form-group"><label>Destination (choix invalide)</label><input value={ivrForm.invalid_destination} onChange={e => setIvrForm({ ...ivrForm, invalid_destination: e.target.value })} /></div>
              <div className="form-group"><label>Destination (timeout)</label><input value={ivrForm.timeout_destination} onChange={e => setIvrForm({ ...ivrForm, timeout_destination: e.target.value })} /></div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowIVRModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Créer</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
