import { useState, useEffect } from 'react'
import api from '../services/api'

export default function ProvisioningPage() {
  const [tenants, setTenants] = useState([])
  const [tenantId, setTenantId] = useState('')
  const [models, setModels] = useState([])
  const [phones, setPhones] = useState([])
  const [tab, setTab] = useState('Téléphones')
  const [showPhoneModal, setShowPhoneModal] = useState(false)
  const [showModelModal, setShowModelModal] = useState(false)
  const [phoneForm, setPhoneForm] = useState({ mac_address: '', display_name: '', location: '', phone_model_id: '', extension_id: '' })
  const [modelForm, setModelForm] = useState({ brand: '', model: '', firmware_version: '', max_accounts: 1, provisioning_protocol: 'http' })
  const [extensions, setExtensions] = useState([])

  useEffect(() => {
    api.get('/tenants').then(r => setTenants(r.data))
    api.get('/provisioning/models').then(r => setModels(r.data))
  }, [])

  const load = async (tid = tenantId) => {
    if (!tid) return
    const [ph, ext] = await Promise.all([
      api.get(`/provisioning/tenant/${tid}`),
      api.get(`/extensions/tenant/${tid}`),
    ])
    setPhones(ph.data)
    setExtensions(ext.data)
  }

  useEffect(() => { load() }, [tenantId])

  const savePhone = async e => {
    e.preventDefault()
    const payload = { ...phoneForm }
    if (!payload.phone_model_id) delete payload.phone_model_id
    if (!payload.extension_id) delete payload.extension_id
    await api.post(`/provisioning/tenant/${tenantId}`, payload)
    setShowPhoneModal(false)
    setPhoneForm({ mac_address: '', display_name: '', location: '', phone_model_id: '', extension_id: '' })
    load()
  }

  const saveModel = async e => {
    e.preventDefault()
    await api.post('/provisioning/models', modelForm)
    setShowModelModal(false)
    setModelForm({ brand: '', model: '', firmware_version: '', max_accounts: 1, provisioning_protocol: 'http' })
    api.get('/provisioning/models').then(r => setModels(r.data))
  }

  const delPhone = async id => { await api.delete(`/provisioning/${id}`); load() }

  const modelName = id => {
    const m = models.find(x => x.id === id)
    return m ? `${m.brand} ${m.model}` : '—'
  }

  const extName = id => {
    const e = extensions.find(x => x.id === id)
    return e ? `${e.extension} — ${e.name}` : '—'
  }

  return (
    <div>
      <h1 className="page-title">Provisioning téléphones</h1>
      <div className="toolbar">
        <select className="search-input" value={tenantId} onChange={e => setTenantId(e.target.value)}>
          <option value="">Sélectionner un tenant</option>
          {tenants.map(t => <option key={t.id} value={t.id}>{t.company_name}</option>)}
        </select>
      </div>

      <div className="tabs">
        {['Téléphones', 'Modèles'].map(t => (
          <button key={t} className={`tab-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Téléphones' && (
        <div>
          <div style={{ marginBottom: '.75rem' }}>
            <button className="btn btn-primary btn-sm" disabled={!tenantId} onClick={() => setShowPhoneModal(true)}>+ Téléphone</button>
          </div>
          <table>
            <thead><tr><th>MAC</th><th>Nom</th><th>Emplacement</th><th>Modèle</th><th>Extension</th><th>Dernière config.</th><th>Statut</th><th></th></tr></thead>
            <tbody>
              {phones.map(p => (
                <tr key={p.id}>
                  <td><code>{p.mac_address}</code></td>
                  <td>{p.display_name || '—'}</td>
                  <td>{p.location || '—'}</td>
                  <td>{modelName(p.phone_model_id)}</td>
                  <td>{p.extension_id ? extName(p.extension_id) : '—'}</td>
                  <td>{p.last_provisioned ? new Date(p.last_provisioned).toLocaleString('fr-CA') : 'Jamais'}</td>
                  <td><span className={`badge ${p.is_active ? 'badge-green' : 'badge-gray'}`}>{p.is_active ? 'Actif' : 'Inactif'}</span></td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => delPhone(p.id)}>Suppr.</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'Modèles' && (
        <div>
          <div style={{ marginBottom: '.75rem' }}>
            <button className="btn btn-primary btn-sm" onClick={() => setShowModelModal(true)}>+ Modèle</button>
          </div>
          <table>
            <thead><tr><th>Marque</th><th>Modèle</th><th>Firmware</th><th>Max comptes</th><th>Protocole</th><th>Template</th></tr></thead>
            <tbody>
              {models.map(m => (
                <tr key={m.id}>
                  <td>{m.brand}</td>
                  <td>{m.model}</td>
                  <td>{m.firmware_version || '—'}</td>
                  <td>{m.max_accounts}</td>
                  <td>{m.provisioning_protocol}</td>
                  <td><span className={`badge ${m.config_template ? 'badge-green' : 'badge-gray'}`}>{m.config_template ? 'Oui' : 'Non'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showPhoneModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Enregistrer un téléphone</h3>
            <form onSubmit={savePhone}>
              <div className="form-group"><label>Adresse MAC</label><input value={phoneForm.mac_address} onChange={e => setPhoneForm({ ...phoneForm, mac_address: e.target.value })} placeholder="AA:BB:CC:DD:EE:FF" required /></div>
              <div className="form-group"><label>Nom d'affichage</label><input value={phoneForm.display_name} onChange={e => setPhoneForm({ ...phoneForm, display_name: e.target.value })} /></div>
              <div className="form-group"><label>Emplacement</label><input value={phoneForm.location} onChange={e => setPhoneForm({ ...phoneForm, location: e.target.value })} /></div>
              <div className="form-group"><label>Modèle</label>
                <select value={phoneForm.phone_model_id} onChange={e => setPhoneForm({ ...phoneForm, phone_model_id: e.target.value })}>
                  <option value="">-- Sélectionner --</option>
                  {models.map(m => <option key={m.id} value={m.id}>{m.brand} {m.model}</option>)}
                </select>
              </div>
              <div className="form-group"><label>Extension</label>
                <select value={phoneForm.extension_id} onChange={e => setPhoneForm({ ...phoneForm, extension_id: e.target.value })}>
                  <option value="">-- Sélectionner --</option>
                  {extensions.map(x => <option key={x.id} value={x.id}>{x.extension} — {x.name}</option>)}
                </select>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowPhoneModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Enregistrer</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showModelModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Nouveau modèle</h3>
            <form onSubmit={saveModel}>
              <div className="form-group"><label>Marque</label><input value={modelForm.brand} onChange={e => setModelForm({ ...modelForm, brand: e.target.value })} required /></div>
              <div className="form-group"><label>Modèle</label><input value={modelForm.model} onChange={e => setModelForm({ ...modelForm, model: e.target.value })} required /></div>
              <div className="form-group"><label>Firmware</label><input value={modelForm.firmware_version} onChange={e => setModelForm({ ...modelForm, firmware_version: e.target.value })} /></div>
              <div className="form-group"><label>Max comptes SIP</label><input type="number" value={modelForm.max_accounts} onChange={e => setModelForm({ ...modelForm, max_accounts: +e.target.value })} /></div>
              <div className="form-group"><label>Protocole</label>
                <select value={modelForm.provisioning_protocol} onChange={e => setModelForm({ ...modelForm, provisioning_protocol: e.target.value })}>
                  <option value="http">HTTP</option>
                  <option value="https">HTTPS</option>
                  <option value="tftp">TFTP</option>
                </select>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowModelModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Créer</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
