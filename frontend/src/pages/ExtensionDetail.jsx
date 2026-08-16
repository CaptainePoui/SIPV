import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import api from '../services/api'

export default function ExtensionDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [ext, setExt] = useState(null)
  const [tenant, setTenant] = useState(null)
  const [voicemail, setVoicemail] = useState(null)
  const [phone, setPhone] = useState(null)
  const [reg, setReg] = useState(null)
  const [monitoring, setMonitoring] = useState(null)
  const [form, setForm] = useState(null)
  const [newPassword, setNewPassword] = useState(null)
  const [revealedAdminPassword, setRevealedAdminPassword] = useState(null)
  const [schedules, setSchedules] = useState([])
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [e911Addresses, setE911Addresses] = useState([])
  const [e911Assignment, setE911Assignment] = useState(null)
  const [e911Form, setE911Form] = useState({ e911_address_id: '', emergency_location: '', floor: '', office: '' })

  const CALL_PERMISSIONS = [
    { value: 'local', label: 'Local seulement' },
    { value: 'national', label: 'National (interurbain inclus)' },
    { value: 'international', label: 'International' },
  ]

  const TRANSPORTS = [
    { value: 'tls', label: 'TLS (recommandé, chiffré)' },
    { value: 'tcp', label: 'TCP' },
    { value: 'udp', label: 'UDP' },
  ]
  // Seul le transport choisi est accepté pour ce poste — une tentative de
  // connexion avec un autre transport est refusée par SIPV (403).

  const load = async () => {
    const { data: e } = await api.get(`/extensions/${id}`)
    setExt(e)
    setForm({
      name: e.name,
      caller_id_name: e.caller_id_name || '',
      caller_id_number: e.caller_id_number || '',
      max_contacts: e.max_contacts,
      max_concurrent_calls: e.max_concurrent_calls ?? '',
      record_calls: e.record_calls,
      record_mode: e.record_mode || 'manual',
      is_active: e.is_active,
      codec_list: e.codec_list || 'ulaw,alaw,g722,g729',
      distinctive_ring: e.distinctive_ring || '',
      transport: e.transport || 'tls',
      schedule_id: e.schedule_id || '',
      site: e.site || '',
      description: e.description || '',
      call_permission: e.call_permission || 'international',
      forward_immediate_enabled: e.forward_immediate_enabled,
      forward_immediate_destination: e.forward_immediate_destination || '',
      forward_busy_enabled: e.forward_busy_enabled,
      forward_busy_destination: e.forward_busy_destination || '',
      forward_no_answer_enabled: e.forward_no_answer_enabled,
      forward_no_answer_destination: e.forward_no_answer_destination || '',
      forward_no_answer_delay_seconds: e.forward_no_answer_delay_seconds ?? 20,
      forward_offline_destination: e.forward_offline_destination || '',
      dnd_enabled: e.dnd_enabled,
      dnd_locked: e.dnd_locked,
      auto_answer_enabled: e.auto_answer_enabled,
      pickup_group: e.pickup_group || '',
      paging_groups: e.paging_groups || '',
      can_intercept_calls: e.can_intercept_calls,
    })

    const [t, vms, phones, scheds, addrs] = await Promise.all([
      api.get(`/tenants/${e.tenant_id}`),
      api.get(`/voicemail/tenant/${e.tenant_id}`),
      api.get(`/provisioning/tenant/${e.tenant_id}`),
      api.get(`/schedules/tenant/${e.tenant_id}`),
      api.get(`/e911/addresses/tenant/${e.tenant_id}`),
    ])
    setTenant(t.data)
    setVoicemail(vms.data.find(v => v.extension_id === e.id) || null)
    setPhone(phones.data.find(p => p.extension_id === e.id) || null)
    setSchedules(scheds.data)
    setE911Addresses(addrs.data)

    try {
      const { data: assign } = await api.get(`/e911/extension-assignments/by-extension/${e.id}`)
      setE911Assignment(assign)
      setE911Form({ e911_address_id: assign.e911_address_id, emergency_location: assign.emergency_location || '', floor: assign.floor || '', office: assign.office || '' })
    } catch {
      setE911Assignment(null)
      setE911Form({ e911_address_id: '', emergency_location: '', floor: '', office: '' })
    }

    try {
      const { data: r } = await api.get(`/esl/registration/${e.username}`)
      setReg(r)
    } catch {
      setReg({ registered: false, contact: null, error: true })
    }

    try {
      const { data: m } = await api.get(`/esl/monitoring/${e.username}`)
      setMonitoring(m)
    } catch {
      setMonitoring(null)
    }
  }

  useEffect(() => { load() }, [id])

  const save = async ev => {
    ev.preventDefault()
    await api.put(`/extensions/${id}`, {
      ...form,
      schedule_id: form.schedule_id || null,
      max_concurrent_calls: form.max_concurrent_calls === '' ? null : Number(form.max_concurrent_calls),
      forward_immediate_destination: form.forward_immediate_destination || null,
      forward_busy_destination: form.forward_busy_destination || null,
      forward_no_answer_destination: form.forward_no_answer_destination || null,
      forward_offline_destination: form.forward_offline_destination || null,
      pickup_group: form.pickup_group || null,
      paging_groups: form.paging_groups || null,
    })
    load()
  }

  const regenPassword = async () => {
    if (!confirm('Générer un nouveau mot de passe SIP pour cette extension ?')) return
    const { data } = await api.post(`/extensions/${id}/regenerate-password`)
    setNewPassword(data.password)
    load()
  }

  const save911 = async () => {
    if (!e911Form.e911_address_id) { alert('Choisir une adresse 911.'); return }
    if (e911Assignment) {
      await api.put(`/e911/extension-assignments/${e911Assignment.id}`, e911Form)
    } else {
      await api.post(`/e911/extension-assignments/tenant/${ext.tenant_id}`, { extension_id: id, ...e911Form })
    }
    load()
  }

  const remove911 = async () => {
    if (!e911Assignment) return
    if (!confirm('Retirer l\'adresse 911 de ce poste ?')) return
    await api.delete(`/e911/extension-assignments/${e911Assignment.id}`)
    load()
  }

  const deleteExt = async () => {
    await api.delete(`/extensions/${id}`)
    navigate(`/tenants/${ext.tenant_id}`)
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
            {reg?.registered && (
              <div className="info-row">
                <span className="info-label">Appareils enregistrés</span>
                <span className="info-value">{reg.registered_count} / {ext.max_contacts}</span>
              </div>
            )}
            {reg?.registered && reg?.public_ip && (
              <div className="info-row">
                <span className="info-label">IP publique</span>
                <span className="info-value" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <code>{reg.public_ip}</code>
                  {reg.is_blocked ? (
                    <span className="badge badge-red">Bloqué (F2B)</span>
                  ) : (
                    <span className="badge badge-green">Non bloqué</span>
                  )}
                  <button type="button" className="btn btn-secondary btn-sm" onClick={async () => {
                    await api.post(`/security/acl/whitelist-extension/${ext.id}`)
                    alert('IP ajoutée à la whitelist de ce poste.')
                  }}>Ajouter à la whitelist</button>
                </span>
              </div>
            )}
            {monitoring?.ping_status && (
              <div className="info-row">
                <span className="info-label">Ping SIP</span>
                <span className="info-value">
                  <span className={`badge ${monitoring.ping_status === 'Reachable' ? 'badge-green' : 'badge-red'}`}>{monitoring.ping_status}</span>
                  {monitoring.ping_time_ms != null && <span style={{ marginLeft: 8 }}>{monitoring.ping_time_ms} ms</span>}
                </span>
              </div>
            )}
            {monitoring?.expires_in_seconds != null && (
              <div className="info-row"><span className="info-label">Expire dans</span><span className="info-value">{monitoring.expires_in_seconds}s</span></div>
            )}
            {monitoring?.call_quality?.active_call ? (
              <div className="info-row">
                <span className="info-label">Qualité d'appel (en cours)</span>
                <span className="info-value">
                  {monitoring.call_quality.mos != null ? `MOS ${monitoring.call_quality.mos}` : '—'}
                  {monitoring.call_quality.jitter_ms != null && ` · Gigue ${monitoring.call_quality.jitter_ms}ms`}
                  {monitoring.call_quality.packet_loss_percent != null && ` · Perte ${monitoring.call_quality.packet_loss_percent}%`}
                </span>
              </div>
            ) : reg?.registered && (
              <div className="info-row"><span className="info-label">Qualité d'appel</span><span className="info-value" style={{ color: '#9CA3AF' }}>Aucun appel en cours</span></div>
            )}
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
            <small style={{ color: '#6B7280' }}>Une tentative de connexion supplémentaire au-delà de ce nombre est refusée.</small>
          </div>
          <div className="form-group">
            <label>Nombre maximal d'appels simultanés</label>
            <input type="number" min="1" value={form.max_concurrent_calls} onChange={e => setForm({ ...form, max_concurrent_calls: e.target.value })} placeholder="Aucune limite" />
          </div>
          <div className="form-group">
            <label>Codecs (ordre de préférence, séparés par virgule)</label>
            <input value={form.codec_list} onChange={e => setForm({ ...form, codec_list: e.target.value })} placeholder="ulaw,alaw,g722,g729" />
            <small style={{ color: '#6B7280' }}>Standard du projet : ulaw (PCMU) en premier — meilleur rapport qualité/poids.</small>
          </div>
          <div className="form-group">
            <label>Transport SIP</label>
            <select value={form.transport} onChange={e => setForm({ ...form, transport: e.target.value })}>
              {TRANSPORTS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <small style={{ color: '#6B7280' }}>Seul ce transport sera accepté pour ce poste — une tentative avec un autre transport sera refusée.</small>
          </div>
          <div className="form-group">
            <label>Sonnerie distinctive</label>
            <input value={form.distinctive_ring} onChange={e => setForm({ ...form, distinctive_ring: e.target.value })} placeholder="Défaut" />
          </div>
          <div className="form-group">
            <label><input type="checkbox" checked={form.record_calls} onChange={e => setForm({ ...form, record_calls: e.target.checked })} /> Enregistrer les appels</label>
          </div>
          {form.record_calls && (
            <div className="form-group">
              <label>Mode d'enregistrement</label>
              <select value={form.record_mode} onChange={e => setForm({ ...form, record_mode: e.target.value })}>
                <option value="manual">Manuel (déclenché par l'agent)</option>
                <option value="auto">Automatique (systématique)</option>
              </select>
            </div>
          )}
          <div className="form-group">
            <label><input type="checkbox" checked={form.is_active} onChange={e => setForm({ ...form, is_active: e.target.checked })} /> Actif</label>
          </div>
          <div className="form-group">
            <label><input type="checkbox" checked={form.auto_answer_enabled} onChange={e => setForm({ ...form, auto_answer_enabled: e.target.checked })} /> Réponse automatique (page / intercom)</label>
          </div>
          <button className="btn btn-primary btn-sm" type="submit">Enregistrer</button>
        </form>
      </div>

      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginTop: 0 }}>Identification &amp; plan d'appel</h3>
        <form onSubmit={save}>
          <div className="form-group">
            <label>Succursale / site</label>
            <input value={form.site} onChange={e => setForm({ ...form, site: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Description</label>
            <input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Plan d'appel</label>
            <select value={form.call_permission} onChange={e => setForm({ ...form, call_permission: e.target.value })}>
              {CALL_PERMISSIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
            <small style={{ color: '#DC6803' }}>⚠️ Pas encore appliqué au routage des appels — champ informatif pour l'instant.</small>
          </div>
          <button className="btn btn-primary btn-sm" type="submit">Enregistrer</button>
        </form>
      </div>

      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginTop: 0 }}>Renvois &amp; ne pas déranger</h3>
        <form onSubmit={save}>
          <div className="form-group">
            <label><input type="checkbox" checked={form.forward_immediate_enabled} onChange={e => setForm({ ...form, forward_immediate_enabled: e.target.checked })} /> Renvoi immédiat</label>
            {form.forward_immediate_enabled && (
              <input value={form.forward_immediate_destination} onChange={e => setForm({ ...form, forward_immediate_destination: e.target.value })} placeholder="Destination (poste, numéro...)" />
            )}
          </div>
          <div className="form-group">
            <label><input type="checkbox" checked={form.forward_busy_enabled} onChange={e => setForm({ ...form, forward_busy_enabled: e.target.checked })} /> Renvoi sur occupation</label>
            {form.forward_busy_enabled && (
              <input value={form.forward_busy_destination} onChange={e => setForm({ ...form, forward_busy_destination: e.target.value })} placeholder="Destination" />
            )}
          </div>
          <div className="form-group">
            <label><input type="checkbox" checked={form.forward_no_answer_enabled} onChange={e => setForm({ ...form, forward_no_answer_enabled: e.target.checked })} /> Renvoi sur non-réponse</label>
            {form.forward_no_answer_enabled && (
              <>
                <input value={form.forward_no_answer_destination} onChange={e => setForm({ ...form, forward_no_answer_destination: e.target.value })} placeholder="Destination" />
                <input type="number" min="1" value={form.forward_no_answer_delay_seconds} onChange={e => setForm({ ...form, forward_no_answer_delay_seconds: Number(e.target.value) })} style={{ width: 90, marginLeft: 8 }} />
                <span style={{ marginLeft: 4, fontSize: '.85rem', color: '#6B7280' }}>secondes avant renvoi</span>
              </>
            )}
          </div>
          <div className="form-group">
            <label>Renvoi hors ligne (poste non enregistré)</label>
            <input value={form.forward_offline_destination} onChange={e => setForm({ ...form, forward_offline_destination: e.target.value })} placeholder="Destination (optionnel)" />
          </div>
          <div className="form-group">
            <label><input type="checkbox" checked={form.dnd_enabled} onChange={e => setForm({ ...form, dnd_enabled: e.target.checked })} /> Ne pas déranger (DND)</label>
          </div>
          <div className="form-group">
            <label><input type="checkbox" checked={form.dnd_locked} onChange={e => setForm({ ...form, dnd_locked: e.target.checked })} /> DND verrouillé (l'utilisateur ne peut pas le désactiver depuis son poste/portail)</label>
          </div>
          <div className="form-group">
            <label>Groupe de pickup (*8)</label>
            <input value={form.pickup_group} onChange={e => setForm({ ...form, pickup_group: e.target.value })} placeholder="Aucun" />
          </div>
          <div className="form-group">
            <label>Groupes de paging</label>
            <input value={form.paging_groups} onChange={e => setForm({ ...form, paging_groups: e.target.value })} placeholder="Séparés par virgule" />
          </div>
          <div className="form-group">
            <label><input type="checkbox" checked={form.can_intercept_calls} onChange={e => setForm({ ...form, can_intercept_calls: e.target.checked })} /> Autorisé à intercepter un appel en cours</label>
          </div>
          <small style={{ color: '#DC6803', display: 'block', marginTop: 4 }}>⚠️ Renvois, DND, pickup/paging pas encore appliqués par le dialplan — champs de configuration en place, l'action réelle sur les appels est un développement séparé.</small>
          <button className="btn btn-primary btn-sm" type="submit" style={{ marginTop: 8 }}>Enregistrer</button>
        </form>
      </div>

      {ext.groups?.length > 0 && (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h3 style={{ marginTop: 0 }}>Groupes d'appartenance</h3>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {ext.groups.map((g, i) => <li key={i}>{g}</li>)}
          </ul>
        </div>
      )}

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
            <div className="info-row"><span className="info-label">Numéro de série</span><span className="info-value">{phone.serial_number || '—'}</span></div>
            <div className="info-row"><span className="info-label">Version matérielle</span><span className="info-value">{phone.hardware_version || '—'}</span></div>
            <div className="info-row"><span className="info-label">Emplacement</span><span className="info-value">{phone.location || '—'}</span></div>
            <div className="info-row"><span className="info-label">Module d'expansion</span><span className="info-value">{phone.expansion_module || 'Aucun'}</span></div>
            <div className="info-row"><span className="info-label">Wi-Fi</span><span className="info-value">{phone.wifi_enabled ? 'Activé' : 'Désactivé'}</span></div>
            <div className="info-row"><span className="info-label">Bluetooth</span><span className="info-value">{phone.bluetooth_enabled ? 'Activé' : 'Désactivé'}</span></div>
            <div className="info-row"><span className="info-label">Casque utilisé</span><span className="info-value">{phone.headset_used ? 'Oui' : 'Non'}</span></div>
            <div className="info-row"><span className="info-label">Conformité provisioning</span><span className="info-value">{phone.provisioning_status === 'provisionne' ? 'Provisionné' : 'Jamais provisionné'}</span></div>
            <div className="info-row"><span className="info-label">Dernier provisioning</span><span className="info-value">{phone.last_provisioned ? new Date(phone.last_provisioned).toLocaleString('fr-CA') : '—'}</span></div>
            <div className="info-row"><span className="info-label">Dernière connexion</span><span className="info-value">{phone.last_seen ? new Date(phone.last_seen).toLocaleString('fr-CA') : 'Jamais'}</span></div>
            {phone.has_admin_password && (
              <div className="info-row">
                <span className="info-label">Mot de passe admin</span>
                <span className="info-value">
                  {revealedAdminPassword ? <code>{revealedAdminPassword}</code> : (
                    <button type="button" className="btn btn-secondary btn-sm" onClick={async () => {
                      const { data } = await api.get(`/provisioning/${phone.id}/reveal-admin-password`)
                      setRevealedAdminPassword(data.admin_password)
                    }}>Révéler</button>
                  )}
                </span>
              </div>
            )}
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

      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginTop: 0 }}>911 — localisation d'urgence</h3>
        {e911Addresses.length === 0 && <div className="info-value">Aucune adresse 911 créée pour cette compagnie (page E911).</div>}
        {e911Addresses.length > 0 && (
          <>
            <div className="form-group">
              <label>Adresse 911 liée</label>
              <select value={e911Form.e911_address_id} onChange={e => setE911Form({ ...e911Form, e911_address_id: e.target.value })}>
                <option value="">— Aucune —</option>
                {e911Addresses.map(a => <option key={a.id} value={a.id}>{a.label} — {a.civic_number} {a.street_name}, {a.city}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Emplacement d'urgence (précision dans le bâtiment)</label>
              <input value={e911Form.emergency_location} onChange={e => setE911Form({ ...e911Form, emergency_location: e.target.value })} placeholder="ex: Près de la sortie nord" />
            </div>
            <div className="form-group">
              <label>Étage</label>
              <input value={e911Form.floor} onChange={e => setE911Form({ ...e911Form, floor: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Bureau</label>
              <input value={e911Form.office} onChange={e => setE911Form({ ...e911Form, office: e.target.value })} />
            </div>
            <small style={{ color: '#6B7280' }}>Succursale : voir "Succursale / site" dans Identification &amp; plan d'appel ci-dessus — pas dupliqué ici.</small>
            <div className="modal-footer" style={{ marginTop: 8 }}>
              {e911Assignment && <button type="button" className="btn btn-danger btn-sm" onClick={remove911}>Retirer</button>}
              <button type="button" className="btn btn-primary btn-sm" onClick={save911}>Enregistrer</button>
            </div>
          </>
        )}
      </div>

      <div className="card" style={{ opacity: 0.6, marginBottom: '1rem' }}>
        <h3 style={{ marginTop: 0 }}>Lien ERPCRM</h3>
        <div className="info-value">À venir — dépend de TASK-S022 (lien contact ERPCRM), pas encore implémenté.</div>
      </div>

      <div className="card" style={{ borderColor: '#f5c6cb' }}>
        <h3 style={{ marginTop: 0 }}>Zone dangereuse</h3>
        <button type="button" className="btn btn-danger btn-sm" onClick={() => setConfirmDelete(true)}>
          Supprimer ce poste
        </button>
      </div>

      {confirmDelete && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Supprimer l'extension {ext.extension} ?</h3>
            <p>
              Poste <strong>{ext.extension} — {ext.name}</strong> ({ext.username}).
              Cette action est irréversible.
            </p>
            <p style={{ fontSize: '.85rem', color: '#6B7280' }}>
              Le mot de passe SIP actuel sera conservé dans le journal d'audit — si tu dois
              recréer ce poste plus tard, tu pourras récupérer le même mot de passe via
              l'historique de l'extension.
            </p>
            <div className="modal-footer">
              <button type="button" className="btn" onClick={() => setConfirmDelete(false)}>Annuler</button>
              <button type="button" className="btn btn-danger" onClick={deleteExt}>Supprimer</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
