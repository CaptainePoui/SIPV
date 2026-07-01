import { useState, useEffect } from 'react'
import api from '../services/api'

export default function E911Page() {
  const [tenants, setTenants] = useState([])
  const [tenantId, setTenantId] = useState('')
  const [addresses, setAddresses] = useState([])
  const [assignments, setAssignments] = useState([])
  const [missing, setMissing] = useState([])
  const [dids, setDids] = useState([])
  const [tab, setTab] = useState('Adresses')
  const [showAddrModal, setShowAddrModal] = useState(false)
  const [showAssignModal, setShowAssignModal] = useState(false)
  const [addrForm, setAddrForm] = useState({ label: '', civic_number: '', street_name: '', unit: '', city: '', province: 'QC', postal_code: '', country: 'CA' })
  const [assignForm, setAssignForm] = useState({ did_id: '', e911_address_id: '', alert_email: '' })

  useEffect(() => { api.get('/tenants').then(r => setTenants(r.data)) }, [])

  const load = async (tid = tenantId) => {
    if (!tid) return
    const [ad, as_, di, mi] = await Promise.all([
      api.get(`/e911/addresses/tenant/${tid}`),
      api.get(`/e911/assignments/tenant/${tid}`),
      api.get(`/dids/tenant/${tid}`),
      api.get(`/e911/dids-without-911/tenant/${tid}`),
    ])
    setAddresses(ad.data)
    setAssignments(as_.data)
    setDids(di.data)
    setMissing(mi.data.dids_without_911)
  }

  useEffect(() => { load() }, [tenantId])

  const saveAddr = async e => {
    e.preventDefault()
    await api.post(`/e911/addresses/tenant/${tenantId}`, addrForm)
    setShowAddrModal(false)
    load()
  }

  const saveAssign = async e => {
    e.preventDefault()
    await api.post(`/e911/assignments/tenant/${tenantId}`, assignForm)
    setShowAssignModal(false)
    load()
  }

  const delAddr = async id => { if (!confirm('Supprimer cette adresse?')) return; await api.delete(`/e911/addresses/${id}`); load() }
  const delAssign = async id => { await api.delete(`/e911/assignments/${id}`); load() }

  const addrLabel = id => addresses.find(a => a.id === id)?.label || '—'
  const didNum = id => dids.find(d => d.id === id)?.did_number || '—'

  return (
    <div>
      <h1 className="page-title">Adresses 911</h1>
      <div className="toolbar">
        <select className="search-input" value={tenantId} onChange={e => setTenantId(e.target.value)}>
          <option value="">Sélectionner un tenant</option>
          {tenants.map(t => <option key={t.id} value={t.id}>{t.company_name}</option>)}
        </select>
      </div>

      {missing.length > 0 && (
        <div style={{ background: '#fce4e4', border: '1px solid #e74c3c', borderRadius: 6, padding: '.75rem 1rem', marginBottom: '1rem', color: '#c0392b', fontSize: '.9rem' }}>
          ⚠ {missing.length} DID(s) sans adresse 911 : {missing.map(d => d.did_number).join(', ')}
        </div>
      )}

      <div className="tabs">
        {['Adresses', 'Assignations'].map(t => (
          <button key={t} className={`tab-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Adresses' && (
        <div>
          <div style={{ marginBottom: '.75rem' }}>
            <button className="btn btn-primary btn-sm" disabled={!tenantId} onClick={() => setShowAddrModal(true)}>+ Adresse</button>
          </div>
          <table>
            <thead><tr><th>Étiquette</th><th>Adresse civique</th><th>Ville</th><th>Province</th><th>Code postal</th><th>Validée</th><th></th></tr></thead>
            <tbody>
              {addresses.map(a => (
                <tr key={a.id}>
                  <td>{a.label}</td>
                  <td>{a.civic_number} {a.street_name}{a.unit ? `, u. ${a.unit}` : ''}</td>
                  <td>{a.city}</td>
                  <td>{a.province}</td>
                  <td>{a.postal_code}</td>
                  <td><span className={`badge ${a.is_validated ? 'badge-green' : 'badge-orange'}`}>{a.is_validated ? 'Oui' : 'En attente'}</span></td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => delAddr(a.id)}>Suppr.</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'Assignations' && (
        <div>
          <div style={{ marginBottom: '.75rem' }}>
            <button className="btn btn-primary btn-sm" disabled={!tenantId || addresses.length === 0} onClick={() => setShowAssignModal(true)}>+ Assignation</button>
          </div>
          <table>
            <thead><tr><th>DID</th><th>Adresse 911</th><th>Alerte courriel</th><th></th></tr></thead>
            <tbody>
              {assignments.map(a => (
                <tr key={a.id}>
                  <td>{didNum(a.did_id)}</td>
                  <td>{addrLabel(a.e911_address_id)}</td>
                  <td>{a.alert_email || '—'}</td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => delAssign(a.id)}>Suppr.</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showAddrModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Nouvelle adresse 911</h3>
            <form onSubmit={saveAddr}>
              <div className="form-group"><label>Étiquette</label><input value={addrForm.label} onChange={e => setAddrForm({ ...addrForm, label: e.target.value })} required /></div>
              <div style={{ display: 'flex', gap: '.5rem' }}>
                <div className="form-group" style={{ flex: 1 }}><label>No civique</label><input value={addrForm.civic_number} onChange={e => setAddrForm({ ...addrForm, civic_number: e.target.value })} required /></div>
                <div className="form-group" style={{ flex: 3 }}><label>Rue</label><input value={addrForm.street_name} onChange={e => setAddrForm({ ...addrForm, street_name: e.target.value })} required /></div>
              </div>
              <div className="form-group"><label>Unité/App</label><input value={addrForm.unit} onChange={e => setAddrForm({ ...addrForm, unit: e.target.value })} /></div>
              <div className="form-group"><label>Ville</label><input value={addrForm.city} onChange={e => setAddrForm({ ...addrForm, city: e.target.value })} required /></div>
              <div style={{ display: 'flex', gap: '.5rem' }}>
                <div className="form-group" style={{ flex: 1 }}><label>Province</label>
                  <select value={addrForm.province} onChange={e => setAddrForm({ ...addrForm, province: e.target.value })}>
                    {['QC','ON','BC','AB','MB','SK','NS','NB','PE','NL','YT','NT','NU'].map(p => <option key={p}>{p}</option>)}
                  </select>
                </div>
                <div className="form-group" style={{ flex: 1 }}><label>Code postal</label><input value={addrForm.postal_code} onChange={e => setAddrForm({ ...addrForm, postal_code: e.target.value })} required /></div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowAddrModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Créer</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showAssignModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Assignation 911</h3>
            <form onSubmit={saveAssign}>
              <div className="form-group"><label>DID</label>
                <select value={assignForm.did_id} onChange={e => setAssignForm({ ...assignForm, did_id: e.target.value })} required>
                  <option value="">-- Sélectionner --</option>
                  {missing.map(d => <option key={d.did_id} value={d.did_id}>{d.did_number}</option>)}
                </select>
              </div>
              <div className="form-group"><label>Adresse 911</label>
                <select value={assignForm.e911_address_id} onChange={e => setAssignForm({ ...assignForm, e911_address_id: e.target.value })} required>
                  <option value="">-- Sélectionner --</option>
                  {addresses.map(a => <option key={a.id} value={a.id}>{a.label} — {a.civic_number} {a.street_name}, {a.city}</option>)}
                </select>
              </div>
              <div className="form-group"><label>Alerte courriel (appels 911)</label><input type="email" value={assignForm.alert_email} onChange={e => setAssignForm({ ...assignForm, alert_email: e.target.value })} /></div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowAssignModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Assigner</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
