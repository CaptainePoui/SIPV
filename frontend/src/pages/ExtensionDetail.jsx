import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import api from '../services/api'

export default function ExtensionDetail() {
  const { id } = useParams()
  const [ext, setExt] = useState(null)
  const [tenant, setTenant] = useState(null)
  const [voicemail, setVoicemail] = useState(null)
  const [phone, setPhone] = useState(null)
  const [reg, setReg] = useState(null)
  const [form, setForm] = useState(null)
  const [newPassword, setNewPassword] = useState(null)
  const [schedules, setSchedules] = useState([])

  const CODECS = [
    { value: '', label: 'Aucune restriction (défaut profil)' },
    { value: 'ulaw', label: 'ulaw (G.711u)' },
    { value: 'alaw', label: 'alaw (G.711a)' },
    { value: 'g722', label: 'G.722 (HD)' },
    { value: 'g729', label: 'G.729' },
  ]

  const load = async () => {
    const { data: e } = await api.get(`/extensions/${id}`)
    setExt(e)
    setForm({
      name: e.name,
      caller_id_name: e.caller_id_name || '',
      caller_id_number: e.caller_id_number || '',
      max_contacts: e.max_contacts,
      record_calls: e.record_calls,
      is_active: e.is_active,
      codec: e.codec || '',
      schedule_id: e.schedule_id || '',
    })

    const [t, vms, phones, scheds] = await Promise.all([
      api.get(`/tenants/${e.tenant_id}`),
      api.get(`/voicemail/tenant/${e.tenant_id}`),
      api.get(`/provisioning/tenant/${e.tenant_id}`),
      api.get(`/schedules/tenant/${e.tenant_id}`),
    ])
    setTenant(t.data)
    setVoicemail(vms.data.find(v => v.extension_id === e.id) || null)
    setPhone(phones.data.find(p => p.extension_id === e.id) || null)
    setSchedules(scheds.data)

    try {
      const { data: r } = await api.get(`/esl/registration/${e.username}`)
      setReg(r)
    } catch {
      setReg({ registered: false, contact: null, error: true })
    }
  }

  useEffect(() => { load() }, [id])

  const save = async ev => {
    ev.preventDefault()
    await api.put(`/extensions/${id}`, {
      ...form,
      codec: form.codec || null,
      schedule_id: form.schedule_id || null,
    })
    load()
  }

  const regenPassword = async () => {
    if (!confirm('Générer un nouveau mot de passe SIP pour cette extension ?')) return
    const { data } = await api.post(`/extensions/${id}/regenerate-password`)
    setNewPassword(data.password)
    load()
  }

  if (!ext || !form) return <div>Chargement...</div>

  return (
    <div>
      <div className="breadcrumb">
        <Link to="/tenants">Tenants</Link> / <Link to={`/tenants/${ext.tenant_id}`}>{tenant?.company_name}</Link> / {ext.extension}
      </div>
      <div className="toolbar">
        <h1 className="page-title" style={{ margin: 0 }}>{ext.extension} — {ext.name}</h1>
        <span className={`badge ${ext.freeswitch_synced ? 'badge-green' : 'badge-orange'}`}>
          {ext.freeswitch_synced ? 'Synchronisé' : 'En attente de sync'}
        </span>
      </div>

      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginTop: 0 }}>Statut live</h3>
        {reg?.error && <div className="info-value">FreeSWITCH injoignable</div>}
        {!reg?.error && (
          <div className="info-grid">
            <div className="info-row">
              <span className="info-label">Enregistrement</span>
              <span className={`badge ${reg?.registered ? 'badge-green' : 'badge-gray'}`}>
                {reg?.registered ? 'Registered' : 'Unregistered'}
              </span>
            </div>
            {reg?.contact && <div className="info-row"><span className="info-label">Contact</span><span className="info-value"><code>{reg.contact}</code></span></div>}
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginTop: 0 }}>Infos SIP</h3>
        <form onSubmit={save}>
          <div className="info-grid">
            <div className="info-row"><span className="info-label">Username SIP</span><span className="info-value"><code>{ext.username}</code></span></div>
            <div className="info-row">
              <span className="info-label">Mot de passe</span>
              <span className="info-value">
                <button type="button" className="btn btn-secondary btn-sm" onClick={regenPassword}>Régénérer</button>
              </span>
            </div>
          </div>
          {newPassword && (
            <div className="info-value" style={{ marginTop: '.5rem', padding: '.5rem', background: '#fff8e1', borderRadius: 4 }}>
              Nouveau mot de passe (affiché une seule fois) : <code>{newPassword}</code>
            </div>
          )}
          <div className="form-group">
            <label>Nom</label>
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div className="form-group">
            <label>Caller ID nom</label>
            <input value={form.caller_id_name} onChange={e => setForm({ ...form, caller_id_name: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Caller ID numéro</label>
            <input value={form.caller_id_number} onChange={e => setForm({ ...form, caller_id_number: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Max contacts (appareils simultanés)</label>
            <input type="number" min="1" value={form.max_contacts} onChange={e => setForm({ ...form, max_contacts: Number(e.target.value) })} />
          </div>
          <div className="form-group">
            <label>Codec</label>
            <select value={form.codec} onChange={e => setForm({ ...form, codec: e.target.value })}>
              {CODECS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label><input type="checkbox" checked={form.record_calls} onChange={e => setForm({ ...form, record_calls: e.target.checked })} /> Enregistrer les appels</label>
          </div>
          <div className="form-group">
            <label><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} /> Actif</label>
          </div>
          <button className="btn btn-primary btn-sm" type="submit">Enregistrer</button>
        </form>
      </div>

      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginTop: 0 }}>Voicemail</h3>
        {!voicemail && <div className="info-value">Aucune boîte vocale liée à cette extension.</div>}
        {voicemail && (
          <div className="info-grid">
            <div className="info-row"><span className="info-label">Courriel</span><span className="info-value">{voicemail.email || '—'}</span></div>
            <div className="info-row"><span className="info-label">Notification courriel</span><span className="info-value">{voicemail.email_on_new ? 'Oui' : 'Non'}</span></div>
            <div className="info-row"><span className="info-label">Pièce jointe MP3</span><span className="info-value">{voicemail.attach_message ? 'Oui' : 'Non'}</span></div>
            <div className="info-row"><span className="info-label">Suppression après envoi</span><span className="info-value">{voicemail.delete_after_email ? 'Oui' : 'Non'}</span></div>
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginTop: 0 }}>Provisioning</h3>
        {!phone && <div className="info-value">Aucun téléphone assigné à cette extension.</div>}
        {phone && (
          <div className="info-grid">
            <div className="info-row"><span className="info-label">Adresse MAC</span><span className="info-value"><code>{phone.mac_address}</code></span></div>
            <div className="info-row"><span className="info-label">Emplacement</span><span className="info-value">{phone.location || '—'}</span></div>
            <div className="info-row"><span className="info-label">Dernière connexion</span><span className="info-value">{phone.last_seen ? new Date(phone.last_seen).toLocaleString('fr-CA') : 'Jamais'}</span></div>
          </div>
        )}
      </div>

      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginTop: 0 }}>Horaires</h3>
        <div className="form-group">
          <label>Horaire assigné (renvoi hors-heures)</label>
          <select
            value={form.schedule_id}
            onChange={async e => {
              const schedule_id = e.target.value || null
              await api.put(`/extensions/${id}`, { schedule_id })
              load()
            }}
          >
            <option value="">Aucun — toujours disponible</option>
            {schedules.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        {form.schedule_id && (() => {
          const s = schedules.find(sc => sc.id === form.schedule_id)
          return s ? (
            <div className="info-value">
              Hors-heures → {s.closed_destination_type || '—'} {s.closed_destination ? `(${s.closed_destination})` : ''}
            </div>
          ) : null
        })()}
      </div>

      <div className="card" style={{ opacity: 0.6 }}>
        <h3 style={{ marginTop: 0 }}>Lien ERPCRM</h3>
        <div className="info-value">À venir — dépend de TASK-S022 (lien contact ERPCRM), pas encore implémenté.</div>
      </div>
    </div>
  )
}
