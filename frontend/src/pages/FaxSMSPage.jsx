import { useState, useEffect } from 'react'
import api from '../services/api'

const STATUS_BADGE = { pending: 'badge-gray', processing: 'badge-orange', delivered: 'badge-green', failed: 'badge-red', received: 'badge-blue', queued: 'badge-gray', sent: 'badge-blue' }

export default function FaxSMSPage() {
  const [tenants, setTenants] = useState([])
  const [tenantId, setTenantId] = useState('')
  const [tab, setTab] = useState('Fax')
  // Fax
  const [faxLines, setFaxLines] = useState([])
  const [faxJobs, setFaxJobs] = useState([])
  // SMS
  const [smsConfig, setSmsConfig] = useState(null)
  const [smsMessages, setSmsMessages] = useState([])
  const [showSMSModal, setShowSMSModal] = useState(false)
  const [smsForm, setSmsForm] = useState({ to_number: '', body: '' })
  const [showFaxLineModal, setShowFaxLineModal] = useState(false)
  const [faxLineForm, setFaxLineForm] = useState({ fax_number: '', label: '', delivery_email: '', use_t38: true })

  useEffect(() => { api.get('/tenants').then(r => setTenants(r.data)) }, [])

  const load = async (tid = tenantId) => {
    if (!tid) return
    const [fl, fj, sm] = await Promise.all([
      api.get(`/fax/lines/tenant/${tid}`),
      api.get(`/fax/jobs/tenant/${tid}`),
      api.get(`/sms/messages/tenant/${tid}`),
    ])
    setFaxLines(fl.data)
    setFaxJobs(fj.data)
    setSmsMessages(sm.data)
    try {
      const cfg = await api.get(`/sms/config/${tid}`)
      setSmsConfig(cfg.data)
    } catch { setSmsConfig(null) }
  }

  useEffect(() => { load() }, [tenantId])

  const saveFaxLine = async e => {
    e.preventDefault()
    await api.post(`/fax/lines/tenant/${tenantId}`, faxLineForm)
    setShowFaxLineModal(false)
    load()
  }

  const delFaxLine = async id => { await api.delete(`/fax/lines/${id}`); load() }

  const sendSMS = async e => {
    e.preventDefault()
    await api.post(`/sms/send/tenant/${tenantId}`, smsForm)
    setShowSMSModal(false)
    setSmsForm({ to_number: '', body: '' })
    load()
  }

  return (
    <div>
      <h1 className="page-title">Fax / SMS</h1>
      <div className="toolbar">
        <select className="search-input" value={tenantId} onChange={e => setTenantId(e.target.value)}>
          <option value="">Sélectionner un tenant</option>
          {tenants.map(t => <option key={t.id} value={t.id}>{t.company_name}</option>)}
        </select>
      </div>

      <div className="tabs">
        {['Fax', 'SMS'].map(t => (
          <button key={t} className={`tab-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Fax' && (
        <div>
          <div className="card">
            <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              Lignes fax
              <button className="btn btn-primary btn-sm" disabled={!tenantId} onClick={() => setShowFaxLineModal(true)}>+ Ligne</button>
            </div>
            <table>
              <thead><tr><th>Numéro</th><th>Étiquette</th><th>Courriel livraison</th><th>T.38</th><th>ATA</th><th></th></tr></thead>
              <tbody>
                {faxLines.map(f => (
                  <tr key={f.id}>
                    <td>{f.fax_number}</td>
                    <td>{f.label || '—'}</td>
                    <td>{f.delivery_email || '—'}</td>
                    <td><span className={`badge ${f.use_t38 ? 'badge-green' : 'badge-gray'}`}>{f.use_t38 ? 'Oui' : 'Non'}</span></td>
                    <td>{f.ata_ip ? `${f.ata_ip} (${f.ata_model || '?'})` : '—'}</td>
                    <td><button className="btn btn-danger btn-sm" onClick={() => delFaxLine(f.id)}>Suppr.</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <div className="card-title">Historique fax</div>
            <table>
              <thead><tr><th>Direction</th><th>Statut</th><th>Numéro distant</th><th>Pages</th><th>Email envoyé</th><th>Date</th></tr></thead>
              <tbody>
                {faxJobs.map(j => (
                  <tr key={j.id}>
                    <td><span className={`badge ${j.direction === 'inbound' ? 'badge-blue' : 'badge-orange'}`}>{j.direction}</span></td>
                    <td><span className={`badge ${STATUS_BADGE[j.status] || 'badge-gray'}`}>{j.status}</span></td>
                    <td>{j.remote_number || '—'}</td>
                    <td>{j.pages ?? '—'}</td>
                    <td><span className={`badge ${j.email_sent ? 'badge-green' : 'badge-gray'}`}>{j.email_sent ? 'Oui' : 'Non'}</span></td>
                    <td>{new Date(j.created_at).toLocaleString('fr-CA')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'SMS' && (
        <div>
          {smsConfig ? (
            <div className="card" style={{ marginBottom: '1rem' }}>
              <div className="info-grid">
                <div className="info-row"><span className="info-label">Fournisseur</span><span className="info-value">{smsConfig.provider}</span></div>
                <div className="info-row"><span className="info-label">Numéro expéditeur</span><span className="info-value">{smsConfig.from_number || '—'}</span></div>
                <div className="info-row"><span className="info-label">Limite mensuelle</span><span className="info-value">{smsConfig.monthly_limit ?? 'Illimité'}</span></div>
                <div className="info-row"><span className="info-label">Statut</span><span className="info-value"><span className={`badge ${smsConfig.is_active ? 'badge-green' : 'badge-gray'}`}>{smsConfig.is_active ? 'Actif' : 'Inactif'}</span></span></div>
              </div>
            </div>
          ) : tenantId && (
            <div className="error-msg" style={{ marginBottom: '1rem' }}>Aucune configuration SMS pour ce tenant.</div>
          )}

          <div style={{ marginBottom: '.75rem' }}>
            <button className="btn btn-primary btn-sm" disabled={!tenantId || !smsConfig?.is_active} onClick={() => setShowSMSModal(true)}>Envoyer SMS</button>
          </div>

          <table>
            <thead><tr><th>Direction</th><th>Statut</th><th>De</th><th>Vers</th><th>Message</th><th>Date</th></tr></thead>
            <tbody>
              {smsMessages.map(m => (
                <tr key={m.id}>
                  <td><span className={`badge ${m.direction === 'inbound' ? 'badge-blue' : 'badge-orange'}`}>{m.direction}</span></td>
                  <td><span className={`badge ${STATUS_BADGE[m.status] || 'badge-gray'}`}>{m.status}</span></td>
                  <td>{m.from_number}</td>
                  <td>{m.to_number}</td>
                  <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.body}</td>
                  <td>{new Date(m.created_at).toLocaleString('fr-CA')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showFaxLineModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Nouvelle ligne fax</h3>
            <form onSubmit={saveFaxLine}>
              <div className="form-group"><label>Numéro fax</label><input value={faxLineForm.fax_number} onChange={e => setFaxLineForm({ ...faxLineForm, fax_number: e.target.value })} required /></div>
              <div className="form-group"><label>Étiquette</label><input value={faxLineForm.label} onChange={e => setFaxLineForm({ ...faxLineForm, label: e.target.value })} /></div>
              <div className="form-group"><label>Courriel de livraison</label><input type="email" value={faxLineForm.delivery_email} onChange={e => setFaxLineForm({ ...faxLineForm, delivery_email: e.target.value })} /></div>
              <div style={{ marginBottom: '.85rem' }}>
                <label><input type="checkbox" checked={faxLineForm.use_t38} onChange={e => setFaxLineForm({ ...faxLineForm, use_t38: e.target.checked })} /> Utiliser T.38</label>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowFaxLineModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Créer</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showSMSModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Envoyer un SMS</h3>
            <form onSubmit={sendSMS}>
              <div className="form-group"><label>Numéro destinataire</label><input value={smsForm.to_number} onChange={e => setSmsForm({ ...smsForm, to_number: e.target.value })} required /></div>
              <div className="form-group"><label>Message</label><textarea value={smsForm.body} onChange={e => setSmsForm({ ...smsForm, body: e.target.value })} required /></div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowSMSModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Envoyer</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
