import { useState, useEffect } from 'react'
import api from '../services/api'

export default function RoutesPage() {
  const [tenants, setTenants] = useState([])
  const [tenantId, setTenantId] = useState('')
  const [trunks, setTrunks] = useState([])
  const [outbound, setOutbound] = useState([])
  const [inbound, setInbound] = useState([])
  const [tab, setTab] = useState('Sortantes')
  const [showOutModal, setShowOutModal] = useState(false)
  const [showInModal, setShowInModal] = useState(false)
  const [outForm, setOutForm] = useState({ name: '', dial_patterns: '', trunk_id: '', strip_digits: 0, prepend_digits: '', priority: 10 })
  const [inForm, setInForm] = useState({ did_number: '', destination_type: 'extension', destination: '' })

  useEffect(() => { api.get('/tenants').then(r => setTenants(r.data)) }, [])

  const load = async (tid = tenantId) => {
    if (!tid) return
    const [tr, ob, ib] = await Promise.all([
      api.get(`/trunks/tenant/${tid}`),
      api.get(`/routes/outbound/tenant/${tid}`),
      api.get(`/routes/inbound/tenant/${tid}`),
    ])
    setTrunks(tr.data)
    setOutbound(ob.data)
    setInbound(ib.data)
  }

  useEffect(() => { load() }, [tenantId])

  const saveOut = async e => {
    e.preventDefault()
    await api.post(`/routes/outbound/tenant/${tenantId}`, outForm)
    setShowOutModal(false)
    load()
  }

  const saveIn = async e => {
    e.preventDefault()
    await api.post(`/routes/inbound/tenant/${tenantId}`, inForm)
    setShowInModal(false)
    load()
  }

  const delOut = async id => { await api.delete(`/routes/outbound/${id}`); load() }
  const delIn = async id => { await api.delete(`/routes/inbound/${id}`); load() }

  return (
    <div>
      <h1 className="page-title">Routes</h1>
      <div className="toolbar">
        <select className="search-input" value={tenantId} onChange={e => setTenantId(e.target.value)}>
          <option value="">Sélectionner un tenant</option>
          {tenants.map(t => <option key={t.id} value={t.id}>{t.company_name}</option>)}
        </select>
      </div>

      <div className="tabs">
        {['Sortantes', 'Entrantes'].map(t => (
          <button key={t} className={`tab-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Sortantes' && (
        <div>
          <div style={{ marginBottom: '.75rem' }}>
            <button className="btn btn-primary btn-sm" disabled={!tenantId} onClick={() => setShowOutModal(true)}>+ Route sortante</button>
          </div>
          <table>
            <thead><tr><th>Nom</th><th>Patterns</th><th>Trunk</th><th>Strip</th><th>Prepend</th><th>Priorité</th><th></th></tr></thead>
            <tbody>
              {outbound.map(r => (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td><code style={{ fontSize: '.8rem' }}>{r.dial_patterns}</code></td>
                  <td>{trunks.find(t => t.id === r.trunk_id)?.name || r.trunk_id?.slice(0, 8)}</td>
                  <td>{r.strip_digits}</td>
                  <td>{r.prepend_digits || '—'}</td>
                  <td>{r.priority}</td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => delOut(r.id)}>Suppr.</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'Entrantes' && (
        <div>
          <div style={{ marginBottom: '.75rem' }}>
            <button className="btn btn-primary btn-sm" disabled={!tenantId} onClick={() => setShowInModal(true)}>+ Route entrante</button>
          </div>
          <table>
            <thead><tr><th>Numéro DID</th><th>Type destination</th><th>Destination</th><th></th></tr></thead>
            <tbody>
              {inbound.map(r => (
                <tr key={r.id}>
                  <td>{r.did_number}</td>
                  <td><span className="badge badge-blue">{r.destination_type}</span></td>
                  <td>{r.destination}</td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => delIn(r.id)}>Suppr.</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showOutModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Nouvelle route sortante</h3>
            <form onSubmit={saveOut}>
              <div className="form-group"><label>Nom</label><input value={outForm.name} onChange={e => setOutForm({ ...outForm, name: e.target.value })} required /></div>
              <div className="form-group"><label>Patterns (ex: 1NXXNXXXXXX,011.)</label><input value={outForm.dial_patterns} onChange={e => setOutForm({ ...outForm, dial_patterns: e.target.value })} required /></div>
              <div className="form-group"><label>Trunk</label>
                <select value={outForm.trunk_id} onChange={e => setOutForm({ ...outForm, trunk_id: e.target.value })} required>
                  <option value="">-- Sélectionner --</option>
                  {trunks.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
              <div className="form-group"><label>Strip digits</label><input type="number" value={outForm.strip_digits} onChange={e => setOutForm({ ...outForm, strip_digits: +e.target.value })} /></div>
              <div className="form-group"><label>Prepend digits</label><input value={outForm.prepend_digits} onChange={e => setOutForm({ ...outForm, prepend_digits: e.target.value })} /></div>
              <div className="form-group"><label>Priorité</label><input type="number" value={outForm.priority} onChange={e => setOutForm({ ...outForm, priority: +e.target.value })} /></div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowOutModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Créer</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showInModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Nouvelle route entrante</h3>
            <form onSubmit={saveIn}>
              <div className="form-group"><label>Numéro DID</label><input value={inForm.did_number} onChange={e => setInForm({ ...inForm, did_number: e.target.value })} required /></div>
              <div className="form-group"><label>Type destination</label>
                <select value={inForm.destination_type} onChange={e => setInForm({ ...inForm, destination_type: e.target.value })}>
                  {['extension', 'ivr', 'queue', 'voicemail', 'hangup'].map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group"><label>Destination</label><input value={inForm.destination} onChange={e => setInForm({ ...inForm, destination: e.target.value })} /></div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowInModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Créer</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
