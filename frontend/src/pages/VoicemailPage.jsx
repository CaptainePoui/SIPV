import { useState, useEffect, useRef } from 'react'
import api from '../services/api'

const LANGUAGES = [
  { value: 'fr', label: 'Français' },
  { value: 'en', label: 'English' },
]

const GREETING_LABELS = {
  unavailable: 'Non disponible',
  busy: 'Occupé',
  name: 'Nom du poste',
  temp: 'Accueil temporaire',
}

function GlobalSettings() {
  const [settings, setSettings] = useState(null)
  const [open, setOpen] = useState(false)

  const load = () => api.get('/voicemail/global-settings').then(r => setSettings(r.data))
  useEffect(() => { load() }, [])

  const save = async () => {
    await api.put('/voicemail/global-settings', settings)
    load()
    setOpen(false)
  }

  if (!settings) return null

  return (
    <div className="card" style={{ marginBottom: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>Voicemail global</h3>
        <button className="btn btn-secondary btn-sm" onClick={() => setOpen(o => !o)}>{open ? 'Fermer' : 'Modifier'}</button>
      </div>
      {!open && (
        <div className="info-grid" style={{ marginTop: '.5rem' }}>
          <div className="info-row"><span className="info-label">Conserver sur le serveur par défaut</span><span className="info-value">{settings.voicemail_delete_after_email ? 'Non' : 'Oui'}</span></div>
          <div className="info-row"><span className="info-label">Langue par défaut</span><span className="info-value">{LANGUAGES.find(l => l.value === settings.voicemail_language)?.label}</span></div>
          <div className="info-row"><span className="info-label">Max messages par défaut</span><span className="info-value">{settings.voicemail_max_messages}</span></div>
          <div className="info-row"><span className="info-label">Durée max par défaut</span><span className="info-value">{settings.voicemail_max_message_length}s</span></div>
        </div>
      )}
      {open && (
        <div style={{ marginTop: '.75rem' }}>
          <div className="form-group">
            <label><input type="checkbox" checked={!settings.voicemail_delete_after_email} onChange={e => setSettings({ ...settings, voicemail_delete_after_email: !e.target.checked })} /> Conserver le message sur le serveur (par défaut)</label>
          </div>
          <div className="form-group">
            <label>Langue par défaut</label>
            <select value={settings.voicemail_language} onChange={e => setSettings({ ...settings, voicemail_language: e.target.value })}>
              {LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Nombre max de messages par défaut</label>
            <input type="number" min="1" value={settings.voicemail_max_messages} onChange={e => setSettings({ ...settings, voicemail_max_messages: Number(e.target.value) })} />
          </div>
          <div className="form-group">
            <label>Durée max d'un message par défaut (secondes)</label>
            <input type="number" min="1" value={settings.voicemail_max_message_length} onChange={e => setSettings({ ...settings, voicemail_max_message_length: Number(e.target.value) })} />
          </div>
          <small style={{ color: '#6B7280' }}>S'applique à toute compagnie ou poste qui n'a pas défini sa propre valeur.</small>
          <div className="modal-footer" style={{ marginTop: '.5rem' }}>
            <button className="btn btn-primary btn-sm" onClick={save}>Enregistrer</button>
          </div>
        </div>
      )}
    </div>
  )
}

function EditModal({ box, tenant, onClose, onSaved }) {
  const [form, setForm] = useState({
    language: box.language,
    transcription_enabled: box.transcription_enabled,
    temp_greeting_enabled: box.temp_greeting_enabled,
    max_messages: box.max_messages,
    max_message_length: box.max_message_length,
    // 3 etats : 'inherit' (null cote API), 'true', 'false'
    delete_after_email_mode: box.delete_after_email === null ? 'inherit' : String(box.delete_after_email),
  })
  const fileInputs = useRef({})

  const save = async () => {
    const delete_after_email = form.delete_after_email_mode === 'inherit' ? null : form.delete_after_email_mode === 'true'
    await api.put(`/voicemail/${box.id}`, {
      language: form.language, transcription_enabled: form.transcription_enabled,
      temp_greeting_enabled: form.temp_greeting_enabled, max_messages: form.max_messages,
      max_message_length: form.max_message_length, delete_after_email,
    })
    onSaved()
  }

  const uploadGreeting = async (type, file) => {
    const fd = new FormData()
    fd.append('file', file)
    await api.post(`/voicemail/${box.id}/greetings/${type}`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    onSaved(true)
  }

  const deleteGreeting = async (type) => {
    await api.delete(`/voicemail/${box.id}/greetings/${type}`)
    onSaved(true)
  }

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h3>Paramètres — {box.mailbox} ({box.fullname})</h3>

        <div className="form-group">
          <label>Conserver le message sur le serveur</label>
          <select value={form.delete_after_email_mode} onChange={e => setForm({ ...form, delete_after_email_mode: e.target.value })}>
            <option value="inherit">Hérité (compagnie / global{tenant?.voicemail_delete_after_email != null ? ` — compagnie: ${tenant.voicemail_delete_after_email ? 'Non' : 'Oui'}` : ''})</option>
            <option value="true">Oui — spécifique à ce poste</option>
            <option value="false">Non — spécifique à ce poste</option>
          </select>
          <small style={{ color: '#6B7280' }}>Valeur effective actuelle : {box.effective_delete_after_email ? 'Non conservé' : 'Conservé'} sur le serveur.</small>
        </div>
        <div className="form-group">
          <label>Langue (poste + boîte vocale)</label>
          <select value={form.language} onChange={e => setForm({ ...form, language: e.target.value })}>
            {LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>Nombre max de messages</label>
          <input type="number" min="1" value={form.max_messages} onChange={e => setForm({ ...form, max_messages: Number(e.target.value) })} />
        </div>
        <div className="form-group">
          <label>Durée max d'un message (secondes)</label>
          <input type="number" min="1" value={form.max_message_length} onChange={e => setForm({ ...form, max_message_length: Number(e.target.value) })} />
        </div>
        <div className="form-group">
          <label><input type="checkbox" checked={form.transcription_enabled} onChange={e => setForm({ ...form, transcription_enabled: e.target.checked })} /> Transcription des messages</label>
        </div>
        <div className="form-group">
          <label><input type="checkbox" checked={form.temp_greeting_enabled} onChange={e => setForm({ ...form, temp_greeting_enabled: e.target.checked })} /> Message d'accueil temporaire activé</label>
        </div>

        <h4 style={{ marginBottom: '.5rem' }}>Accueils audio</h4>
        {Object.entries(GREETING_LABELS).map(([type, label]) => {
          const has = box[`has_greeting_${type}`]
          return (
            <div key={type} className="info-row" style={{ marginBottom: 6 }}>
              <span className="info-label">{label}</span>
              <span className="info-value" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {has && <a href={`${api.defaults.baseURL}/voicemail/${box.id}/greetings/${type}`} target="_blank" rel="noreferrer">Télécharger</a>}
                <input ref={el => fileInputs.current[type] = el} type="file" accept="audio/*" style={{ display: 'none' }}
                  onChange={e => e.target.files[0] && uploadGreeting(type, e.target.files[0])} />
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => fileInputs.current[type].click()}>
                  {has ? 'Remplacer' : 'Uploader'}
                </button>
                {has && <button type="button" className="btn btn-danger btn-sm" onClick={() => deleteGreeting(type)}>Suppr.</button>}
              </span>
            </div>
          )
        })}

        <div className="modal-footer" style={{ marginTop: '1rem' }}>
          <button type="button" className="btn" onClick={onClose}>Fermer</button>
          <button type="button" className="btn btn-primary" onClick={save}>Enregistrer</button>
        </div>
      </div>
    </div>
  )
}

export default function VoicemailPage() {
  const [tenants, setTenants] = useState([])
  const [tenantId, setTenantId] = useState('')
  const [boxes, setBoxes] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [editBox, setEditBox] = useState(null)
  const [form, setForm] = useState({ mailbox: '', fullname: '', email: '', email_on_new: true, attach_message: true, max_messages: 100 })

  useEffect(() => { api.get('/tenants').then(r => setTenants(r.data)) }, [])

  const load = async (tid = tenantId) => {
    if (!tid) return
    const { data } = await api.get(`/voicemail/tenant/${tid}`)
    setBoxes(data)
    return data
  }

  useEffect(() => { load() }, [tenantId])

  const currentTenant = tenants.find(t => t.id === tenantId)

  const save = async e => {
    e.preventDefault()
    await api.post(`/voicemail/tenant/${tenantId}`, form)
    setShowModal(false)
    setForm({ mailbox: '', fullname: '', email: '', email_on_new: true, attach_message: true, max_messages: 100 })
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

      <GlobalSettings />

      <div className="toolbar">
        <select className="search-input" value={tenantId} onChange={e => setTenantId(e.target.value)}>
          <option value="">Sélectionner un tenant</option>
          {tenants.map(t => <option key={t.id} value={t.id}>{t.company_name}</option>)}
        </select>
        <button className="btn btn-primary btn-sm" disabled={!tenantId} onClick={() => setShowModal(true)}>+ Boîte vocale</button>
      </div>

      <table>
        <thead><tr><th>Boîte</th><th>Nom</th><th>Courriel</th><th>Langue</th><th>Conserver sur serveur</th><th>Max messages</th><th>Statut</th><th></th></tr></thead>
        <tbody>
          {boxes.map(b => (
            <tr key={b.id}>
              <td><code>{b.mailbox}@{b.context}</code></td>
              <td>{b.fullname}</td>
              <td>{b.email || '—'}</td>
              <td>{LANGUAGES.find(l => l.value === b.language)?.label || b.language}</td>
              <td>
                <span className={`badge ${b.effective_delete_after_email ? 'badge-gray' : 'badge-green'}`}>
                  {b.effective_delete_after_email ? 'Non' : 'Oui'}
                </span>
                {b.delete_after_email !== null && <span style={{ fontSize: '.75rem', marginLeft: 4, color: '#6B7280' }}>(spécifique)</span>}
              </td>
              <td>{b.max_messages}</td>
              <td>
                <button className={`btn btn-sm ${b.is_active ? 'badge-green' : 'badge-gray'}`} style={{ border: '1px solid #ddd' }} onClick={() => toggleActive(b)}>
                  {b.is_active ? 'Actif' : 'Inactif'}
                </button>
              </td>
              <td style={{ display: 'flex', gap: 6 }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setEditBox(b)}>Paramètres</button>
                <button className="btn btn-danger btn-sm" onClick={() => del(b.id)}>Suppr.</button>
              </td>
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
              </div>
              <small style={{ color: '#6B7280' }}>"Conserver sur le serveur" hérite de la compagnie/du réglage global par défaut — ajustable ensuite via "Paramètres".</small>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Créer</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {editBox && (
        <EditModal
          box={editBox}
          tenant={currentTenant}
          onClose={() => setEditBox(null)}
          onSaved={async (keepOpen) => {
            const fresh = await load()
            if (!keepOpen) setEditBox(null)
            else setEditBox(fresh.find(b => b.id === editBox.id) || null)
          }}
        />
      )}
    </div>
  )
}
