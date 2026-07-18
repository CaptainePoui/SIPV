import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import api from '../services/api'

const TABS = ['Extensions', 'Trunks', 'DIDs', 'Changes']

export default function TenantDetail() {
  const { id } = useParams()
  const [tenant, setTenant] = useState(null)
  const [tab, setTab] = useState('Extensions')
  const [extensions, setExtensions] = useState([])
  const [trunks, setTrunks] = useState([])
  const [dids, setDids] = useState([])
  const [changes, setChanges] = useState([])
  const [showExtModal, setShowExtModal] = useState(false)
  const [extForm, setExtForm] = useState({ extension: '', name: '', voicemail_email: '' })
  const [confirmDeleteExt, setConfirmDeleteExt] = useState(null)

  const load = async () => {
    const [t, e, tr, d, ch] = await Promise.all([
      api.get(`/tenants/${id}`),
      api.get(`/extensions/tenant/${id}`),
      api.get(`/trunks/tenant/${id}`),
      api.get(`/dids/tenant/${id}`),
      api.get(`/changes/pending/${id}`),
    ])
    setTenant(t.data)
    setExtensions(e.data)
    setTrunks(tr.data)
    setDids(d.data)
    setChanges(ch.data)
  }

  useEffect(() => { load() }, [id])

  const commit = async () => {
    await api.post(`/changes/commit/${id}`)
    load()
  }

  const rollback = async () => {
    if (!confirm('Annuler tous les changements en attente?')) return
    await api.post(`/changes/rollback/${id}`)
    load()
  }

  const saveExt = async e => {
    e.preventDefault()
    await api.post(`/extensions/tenant/${id}`, extForm)
    setShowExtModal(false)
    setExtForm({ extension: '', name: '', voicemail_email: '' })
    load()
  }

  const deleteExt = async () => {
    if (!confirmDeleteExt) return
    await api.delete(`/extensions/${confirmDeleteExt.id}`)
    setConfirmDeleteExt(null)
    load()
  }

  if (!tenant) return <div>Chargement...</div>

  return (
    <div>
      <div className="breadcrumb"><Link to="/tenants">Tenants</Link> / {tenant.company_name}</div>
      <div className="toolbar">
        <h1 className="page-title" style={{ margin: 0 }}>{tenant.company_name}</h1>
        <code style={{ background: '#e8f4f8', padding: '.2rem .5rem', borderRadius: 4 }}>{tenant.account_number}</code>
        <span className={`badge ${tenant.is_active ? 'badge-green' : 'badge-gray'}`}>{tenant.is_active ? 'Actif' : 'Inactif'}</span>
      </div>

      <div className="card" style={{ marginBottom: '1rem' }}>
        <div className="info-grid">
          <div className="info-row"><span className="info-label">Max extensions</span><span className="info-value">{tenant.max_extensions}</span></div>
          <div className="info-row"><span className="info-label">Max trunks</span><span className="info-value">{tenant.max_trunks}</span></div>
          <div className="info-row"><span className="info-label">Contexte</span><span className="info-value">{tenant.context_prefix}</span></div>
          <div className="info-row"><span className="info-label">Changes en attente</span><span className="info-value">{changes.length}</span></div>
        </div>
        {changes.length > 0 && (
          <div style={{ marginTop: '.75rem', display: 'flex', gap: '.5rem' }}>
            <button className="btn btn-primary btn-sm" onClick={commit}>Commiter ({changes.length})</button>
            <button className="btn btn-danger btn-sm" onClick={rollback}>Rollback</button>
          </div>
        )}
      </div>

      <div className="tabs">
        {TABS.map(t => <button key={t} className={`tab-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</button>)}
      </div>

      {tab === 'Extensions' && (
        <div>
          <div style={{ marginBottom: '.75rem' }}>
            <button className="btn btn-primary btn-sm" onClick={() => setShowExtModal(true)}>+ Extension</button>
          </div>
          <table>
            <thead><tr><th>Extension</th><th>Nom</th><th>Username SIP</th><th>Email VM</th><th>Synced</th><th></th></tr></thead>
            <tbody>
              {extensions.map(e => (
                <tr key={e.id}>
                  <td><Link to={`/extensions/${e.id}`}>{e.extension}</Link></td>
                  <td>{e.name}</td>
                  <td><code>{e.username}</code></td>
                  <td>{e.voicemail_email || '—'}</td>
                  <td><span className={`badge ${e.freeswitch_synced ? 'badge-green' : 'badge-orange'}`}>{e.freeswitch_synced ? 'Oui' : 'En attente'}</span></td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => setConfirmDeleteExt(e)}>Suppr.</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'Trunks' && (
        <table>
          <thead><tr><th>Nom</th><th>Provider</th><th>Host</th><th>Username</th><th>Statut</th></tr></thead>
          <tbody>
            {trunks.map(t => (
              <tr key={t.id}>
                <td>{t.name}</td>
                <td>{t.provider || '—'}</td>
                <td>{t.host}</td>
                <td>{t.username}</td>
                <td><span className={`badge ${t.is_active ? 'badge-green' : 'badge-gray'}`}>{t.is_active ? 'Actif' : 'Inactif'}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === 'DIDs' && (
        <table>
          <thead><tr><th>Numéro</th><th>Type</th><th>Destination</th><th>911</th><th>Statut</th></tr></thead>
          <tbody>
            {dids.map(d => (
              <tr key={d.id}>
                <td>{d.did_number}</td>
                <td>{d.did_type}</td>
                <td>{d.destination_type} : {d.destination || '—'}</td>
                <td><span className={`badge ${d.has_911 ? 'badge-green' : 'badge-red'}`}>{d.has_911 ? 'Oui' : 'Non'}</span></td>
                <td><span className={`badge ${d.is_active ? 'badge-green' : 'badge-gray'}`}>{d.is_active ? 'Actif' : 'Inactif'}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === 'Changes' && (
        <table>
          <thead><tr><th>Type</th><th>Entité</th><th>Statut</th><th>Créé par</th><th>Date</th></tr></thead>
          <tbody>
            {changes.map(c => (
              <tr key={c.id}>
                <td>{c.change_type}</td>
                <td>{c.entity_type} {c.entity_id ? `(${c.entity_id.slice(0, 8)}…)` : ''}</td>
                <td><span className={`badge ${c.status === 'applied' ? 'badge-green' : c.status === 'failed' ? 'badge-red' : 'badge-orange'}`}>{c.status}</span></td>
                <td>{c.created_by || '—'}</td>
                <td>{new Date(c.created_at).toLocaleString('fr-CA')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {confirmDeleteExt && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Supprimer l'extension {confirmDeleteExt.extension} ?</h3>
            <p>
              Poste <strong>{confirmDeleteExt.extension} — {confirmDeleteExt.name}</strong> ({confirmDeleteExt.username}).
              Cette action est irréversible.
            </p>
            <p style={{ fontSize: '.85rem', color: '#6B7280' }}>
              Le mot de passe SIP actuel sera conservé dans le journal d'audit — si tu dois
              recréer ce poste plus tard, tu pourras récupérer le même mot de passe via
              l'historique de l'extension.
            </p>
            <div className="modal-footer">
              <button type="button" className="btn" onClick={() => setConfirmDeleteExt(null)}>Annuler</button>
              <button type="button" className="btn btn-danger" onClick={deleteExt}>Supprimer</button>
            </div>
          </div>
        </div>
      )}

      {showExtModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Nouvelle extension</h3>
            <form onSubmit={saveExt}>
              <div className="form-group"><label>Extension (ex: 100)</label><input value={extForm.extension} onChange={e => setExtForm({ ...extForm, extension: e.target.value })} required /></div>
              <div className="form-group"><label>Nom</label><input value={extForm.name} onChange={e => setExtForm({ ...extForm, name: e.target.value })} required /></div>
              <div className="form-group"><label>Courriel messagerie vocale</label><input type="email" value={extForm.voicemail_email} onChange={e => setExtForm({ ...extForm, voicemail_email: e.target.value })} /></div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowExtModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Créer</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
