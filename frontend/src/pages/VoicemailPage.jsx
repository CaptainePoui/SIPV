import { useState, useEffect } from 'react'
import api from '../services/api'

export default function VoicemailPage() {
  const [tenants, setTenants] = useState([])
  const [tenantId, setTenantId] = useState('')
  const [boxes, setBoxes] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ mailbox: '', fullname: '', email: '', email_on_new: true, attach_message: true, delete_after_email: false, max_messages: 100 })

  useEffect(() => { api.get('/tenants').then(r => setTenants(r.data)) }, [])

  const load = async (tid = tenantId) => {
    if (!tid) return
    const { data } = await api.get(`/voicemail/tenant/${tid}`)
    setBoxes(data)
  }

  useEffect(() => { load() }, [tenantId])

  const save = async e => {
    e.preventDefault()
    await api.post(`/voicemail/tenant/${tenantId}`, form)
    setShowModal(false)
    setForm({ mailbox: '', fullname: '', email: '', email_on_new: true, attach_message: true, delete_after_email: false, max_messages: 100 })
    load()
  }

  const del = async id => {
    if (!confirm('Supprimer cette boîte vocale?')) return
    await api.delete(`/voicemail/${id}`)
    load()
  }

  const toggleActive = async (box) => {
    await api.put(`/voicemail/${box.id}`, { is_active: !box.is_active })
    load()
  }

  return (
    <div>
      <h1 className="page-title">Messagerie vocale</h1>
      <div className="toolbar">
        <select className="search-input" value={tenantId} onChange={e => setTenantId(e.target.value)}>
          <option value="">Sélectionner un tenant</option>
          {tenants.map(t => <option key={t.id} value={t.id}>{t.company_name}</option>)}
        </select>
        <button className="btn btn-primary btn-sm" disabled={!tenantId} onClick={() => setShowModal(true)}>+ Boîte vocale</button>
      </div>

      <table>
        <thead><tr><th>Boîte</th><th>Nom</th><th>Courriel</th><th>Notif. email</th><th>Joindre</th><th>Max messages</th><th>Statut</th><th></th></tr></thead>
        <tbody>
          {boxes.map(b => (
            <tr key={b.id}>
              <td><code>{b.mailbox}@{b.context}</code></td>
              <td>{b.fullname}</td>
              <td>{b.email || '—'}</td>
              <td><span className={`badge ${b.email_on_new ? 'badge-green' : 'badge-gray'}`}>{b.email_on_new ? 'Oui' : 'Non'}</span></td>
              <td><span className={`badge ${b.attach_message ? 'badge-green' : 'badge-gray'}`}>{b.attach_message ? 'Oui' : 'Non'}</span></td>
              <td>{b.max_messages}</td>
              <td>
                <button className={`btn btn-sm ${b.is_active ? 'badge-green' : 'badge-gray'}`} style={{ border: '1px solid #ddd' }} onClick={() => toggleActive(b)}>
                  {b.is_active ? 'Actif' : 'Inactif'}
                </button>
              </td>
              <td><button className="btn btn-danger btn-sm" onClick={() => del(b.id)}>Suppr.</button></td>
            </tr>
          ))}
        </tbody>
      </table>

      {showModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Nouvelle boîte vocale</h3>
            <form onSubmit={save}>
              <div className="form-group"><label>Numéro de boîte</label><input value={form.mailbox} onChange={e => setForm({ ...form, mailbox: e.target.value })} required /></div>
              <div className="form-group"><label>Nom complet</label><input value={form.fullname} onChange={e => setForm({ ...form, fullname: e.target.value })} required /></div>
              <div className="form-group"><label>Courriel</label><input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></div>
              <div className="form-group"><label>Max messages</label><input type="number" value={form.max_messages} onChange={e => setForm({ ...form, max_messages: +e.target.value })} /></div>
              <div style={{ display: 'flex', gap: '1rem', marginBottom: '.85rem', fontSize: '.9rem' }}>
                <label><input type="checkbox" checked={form.email_on_new} onChange={e => setForm({ ...form, email_on_new: e.target.checked })} /> Notif. courriel</label>
                <label><input type="checkbox" checked={form.attach_message} onChange={e => setForm({ ...form, attach_message: e.target.checked })} /> Joindre WAV</label>
                <label><input type="checkbox" checked={form.delete_after_email} onChange={e => setForm({ ...form, delete_after_email: e.target.checked })} /> Suppr. après email</label>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Créer</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
