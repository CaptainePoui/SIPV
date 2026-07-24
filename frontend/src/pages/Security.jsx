import { useState, useEffect } from 'react'
import api from '../services/api'

const SEV_BADGE = { info: 'badge-blue', warning: 'badge-orange', critical: 'badge-red' }
const TABS = ['Événements', 'IPs bloquées', 'ACL']

export default function Security() {
  const [tab, setTab] = useState('Événements')
  const [events, setEvents] = useState([])
  const [blocked, setBlocked] = useState([])
  const [acl, setAcl] = useState([])
  const [showBlockModal, setShowBlockModal] = useState(false)
  const [blockForm, setBlockForm] = useState({ ip_address: '', reason: '', expires_hours: 24 })
  const [showACLModal, setShowACLModal] = useState(false)
  const [aclForm, setAclForm] = useState({ cidr: '', action: 'deny', description: '', priority: 100 })

  const load = async () => {
    const [ev, bl, ac] = await Promise.all([
      api.get('/security/events?limit=100'),
      api.get('/security/blocked-ips'),
      api.get('/security/acl'),
    ])
    setEvents(ev.data)
    setBlocked(bl.data)
    setAcl(ac.data)
  }

  useEffect(() => { load() }, [])

  const resolve = async id => {
    await api.put(`/security/events/${id}/resolve`)
    load()
  }

  const unblock = async id => {
    await api.delete(`/security/blocked-ips/${id}`)
    load()
  }

  const saveBlock = async e => {
    e.preventDefault()
    await api.post('/security/blocked-ips', blockForm)
    setShowBlockModal(false)
    setBlockForm({ ip_address: '', reason: '', expires_hours: 24 })
    load()
  }

  const saveACL = async e => {
    e.preventDefault()
    await api.post('/security/acl', aclForm)
    setShowACLModal(false)
    setAclForm({ cidr: '', action: 'deny', description: '', priority: 100 })
    load()
  }

  const deleteACL = async id => {
    await api.delete(`/security/acl/${id}`)
    load()
  }

  return (
    <div>
      <h1 className="page-title">Sécurité</h1>

      <div className="tabs">
        {TABS.map(t => <button key={t} className={`tab-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</button>)}
      </div>

      {tab === 'Événements' && (
        <table>
          <thead><tr><th>Type</th><th>Sévérité</th><th>IP source</th><th>Description</th><th>Résolu</th><th>Date</th><th></th></tr></thead>
          <tbody>
            {events.map(e => (
              <tr key={e.id}>
                <td>{e.event_type}</td>
                <td><span className={`badge ${SEV_BADGE[e.severity] || 'badge-gray'}`}>{e.severity}</span></td>
                <td>{e.source_ip || '—'}</td>
                <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.description || '—'}</td>
                <td><span className={`badge ${e.resolved ? 'badge-green' : 'badge-orange'}`}>{e.resolved ? 'Oui' : 'Non'}</span></td>
                <td>{new Date(e.created_at).toLocaleString('fr-CA')}</td>
                <td>{!e.resolved && <button className="btn btn-sm btn-primary" onClick={() => resolve(e.id)}>Résoudre</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === 'IPs bloquées' && (
        <div>
          <div style={{ marginBottom: '.75rem' }}>
            <button className="btn btn-primary btn-sm" onClick={() => setShowBlockModal(true)}>+ Bloquer IP</button>
          </div>
          <table>
            <thead><tr><th>IP</th><th>Raison</th><th>Nb blocages</th><th>Expire</th><th></th></tr></thead>
            <tbody>
              {blocked.map(b => (
                <tr key={b.id}>
                  <td><code>{b.ip_address}</code></td>
                  <td>{b.reason || '—'}</td>
                  <td>{b.block_count}</td>
                  <td>{b.expires_at ? new Date(b.expires_at).toLocaleString('fr-CA') : 'Permanent'}</td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => unblock(b.id)}>Débloquer</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'ACL' && (
        <div>
          <div style={{ marginBottom: '.75rem' }}>
            <button className="btn btn-primary btn-sm" onClick={() => setShowACLModal(true)}>+ Règle ACL</button>
          </div>
          <table>
            <thead><tr><th>Portée</th><th>CIDR</th><th>Action</th><th>Description</th><th>Priorité</th><th></th></tr></thead>
            <tbody>
              {acl.map(r => (
                <tr key={r.id}>
                  <td>
                    <span className={`badge ${r.extension_id ? 'badge-blue' : r.tenant_id ? 'badge-orange' : 'badge-gray'}`}>
                      {r.extension_id ? 'Poste' : r.tenant_id ? 'Compagnie' : 'Global'}
                    </span>
                  </td>
                  <td><code>{r.cidr}</code></td>
                  <td><span className={`badge ${r.action === 'allow' ? 'badge-green' : 'badge-red'}`}>{r.action}</span></td>
                  <td>{r.description || '—'}</td>
                  <td>{r.priority}</td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => deleteACL(r.id)}>Suppr.</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showBlockModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Bloquer une IP</h3>
            <form onSubmit={saveBlock}>
              <div className="form-group"><label>Adresse IP</label><input value={blockForm.ip_address} onChange={e => setBlockForm({ ...blockForm, ip_address: e.target.value })} required /></div>
              <div className="form-group"><label>Raison</label><input value={blockForm.reason} onChange={e => setBlockForm({ ...blockForm, reason: e.target.value })} /></div>
              <div className="form-group"><label>Expiration (heures, 0=permanent)</label><input type="number" value={blockForm.expires_hours} onChange={e => setBlockForm({ ...blockForm, expires_hours: +e.target.value })} /></div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowBlockModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Bloquer</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showACLModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Nouvelle règle ACL</h3>
            <form onSubmit={saveACL}>
              <div className="form-group"><label>CIDR (ex: 192.168.1.0/24)</label><input value={aclForm.cidr} onChange={e => setAclForm({ ...aclForm, cidr: e.target.value })} required /></div>
              <div className="form-group"><label>Action</label>
                <select value={aclForm.action} onChange={e => setAclForm({ ...aclForm, action: e.target.value })}>
                  <option value="allow">Autoriser</option>
                  <option value="deny">Refuser</option>
                </select>
              </div>
              <div className="form-group"><label>Description</label><input value={aclForm.description} onChange={e => setAclForm({ ...aclForm, description: e.target.value })} /></div>
              <div className="form-group"><label>Priorité</label><input type="number" value={aclForm.priority} onChange={e => setAclForm({ ...aclForm, priority: +e.target.value })} /></div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowACLModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Créer</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
