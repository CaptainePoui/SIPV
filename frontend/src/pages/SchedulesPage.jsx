import { useState, useEffect } from 'react'
import api from '../services/api'

const DAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

export default function SchedulesPage() {
  const [tenants, setTenants] = useState([])
  const [tenantId, setTenantId] = useState('')
  const [schedules, setSchedules] = useState([])
  const [holidays, setHolidays] = useState([])
  const [tab, setTab] = useState('Horaires')
  const [showSchedModal, setShowSchedModal] = useState(false)
  const [showHolModal, setShowHolModal] = useState(false)
  const [schedForm, setSchedForm] = useState({ name: '', timezone: 'America/Montreal', closed_destination_type: 'voicemail', closed_destination: '', rules: [{ days_of_week: [0,1,2,3,4], open_time: '09:00', close_time: '17:00', label: 'Heures ouvrables' }] })
  const [holForm, setHolForm] = useState({ date: '', name: '', recurring: false, override_destination_type: '', override_destination: '' })

  useEffect(() => { api.get('/tenants').then(r => setTenants(r.data)) }, [])

  const load = async (tid = tenantId) => {
    if (!tid) return
    const [sc, ho] = await Promise.all([
      api.get(`/schedules/tenant/${tid}`),
      api.get(`/schedules/holidays/tenant/${tid}`),
    ])
    setSchedules(sc.data)
    setHolidays(ho.data)
  }

  useEffect(() => { load() }, [tenantId])

  const checkOpen = async (schedId) => {
    const { data } = await api.get(`/schedules/${schedId}/is-open`)
    alert(`Statut: ${data.is_open ? 'OUVERT' : 'FERMÉ'}\nRaison: ${data.reason}${data.holiday ? ' — ' + data.holiday : ''}`)
  }

  const saveSched = async e => {
    e.preventDefault()
    await api.post(`/schedules/tenant/${tenantId}`, schedForm)
    setShowSchedModal(false)
    load()
  }

  const delSched = async id => { await api.delete(`/schedules/${id}`); load() }

  const saveHol = async e => {
    e.preventDefault()
    await api.post(`/schedules/holidays/tenant/${tenantId}`, holForm)
    setShowHolModal(false)
    setHolForm({ date: '', name: '', recurring: false, override_destination_type: '', override_destination: '' })
    load()
  }

  const delHol = async id => { await api.delete(`/schedules/holidays/${id}`); load() }

  return (
    <div>
      <h1 className="page-title">Horaires</h1>
      <div className="toolbar">
        <select className="search-input" value={tenantId} onChange={e => setTenantId(e.target.value)}>
          <option value="">Sélectionner un tenant</option>
          {tenants.map(t => <option key={t.id} value={t.id}>{t.company_name}</option>)}
        </select>
      </div>

      <div className="tabs">
        {['Horaires', 'Jours fériés'].map(t => (
          <button key={t} className={`tab-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'Horaires' && (
        <div>
          <div style={{ marginBottom: '.75rem' }}>
            <button className="btn btn-primary btn-sm" disabled={!tenantId} onClick={() => setShowSchedModal(true)}>+ Horaire</button>
          </div>
          <table>
            <thead><tr><th>Nom</th><th>Fuseau</th><th>Règles</th><th>Fermé → </th><th></th></tr></thead>
            <tbody>
              {schedules.map(s => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.timezone}</td>
                  <td>
                    {s.rules.map((r, i) => (
                      <div key={i} style={{ fontSize: '.82rem' }}>
                        {r.days_of_week.map(d => DAYS[d]).join(', ')} · {r.open_time}–{r.close_time}
                      </div>
                    ))}
                  </td>
                  <td>{s.closed_destination_type ? `${s.closed_destination_type}: ${s.closed_destination || '—'}` : '—'}</td>
                  <td style={{ display: 'flex', gap: '.4rem' }}>
                    <button className="btn btn-sm" style={{ background: '#27ae60', color: '#fff' }} onClick={() => checkOpen(s.id)}>Tester</button>
                    <button className="btn btn-danger btn-sm" onClick={() => delSched(s.id)}>Suppr.</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'Jours fériés' && (
        <div>
          <div style={{ marginBottom: '.75rem' }}>
            <button className="btn btn-primary btn-sm" disabled={!tenantId} onClick={() => setShowHolModal(true)}>+ Jour férié</button>
          </div>
          <table>
            <thead><tr><th>Date</th><th>Nom</th><th>Récurrent</th><th>Destination override</th><th></th></tr></thead>
            <tbody>
              {holidays.map(h => (
                <tr key={h.id}>
                  <td>{h.date}</td>
                  <td>{h.name}</td>
                  <td><span className={`badge ${h.recurring ? 'badge-blue' : 'badge-gray'}`}>{h.recurring ? 'Annuel' : 'Ponctuel'}</span></td>
                  <td>{h.override_destination_type ? `${h.override_destination_type}: ${h.override_destination || '—'}` : 'Défaut fermé'}</td>
                  <td><button className="btn btn-danger btn-sm" onClick={() => delHol(h.id)}>Suppr.</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showSchedModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Nouvel horaire</h3>
            <form onSubmit={saveSched}>
              <div className="form-group"><label>Nom</label><input value={schedForm.name} onChange={e => setSchedForm({ ...schedForm, name: e.target.value })} required /></div>
              <div className="form-group"><label>Fuseau horaire</label>
                <select value={schedForm.timezone} onChange={e => setSchedForm({ ...schedForm, timezone: e.target.value })}>
                  <option value="America/Montreal">America/Montreal</option>
                  <option value="America/Toronto">America/Toronto</option>
                  <option value="America/Vancouver">America/Vancouver</option>
                  <option value="America/New_York">America/New_York</option>
                </select>
              </div>
              <div style={{ fontSize: '.85rem', color: '#666', marginBottom: '.5rem' }}>Règle par défaut : Lun–Ven 09:00–17:00</div>
              <div className="form-group"><label>Destination si fermé</label>
                <select value={schedForm.closed_destination_type} onChange={e => setSchedForm({ ...schedForm, closed_destination_type: e.target.value })}>
                  <option value="voicemail">Messagerie vocale</option>
                  <option value="ivr">IVR</option>
                  <option value="hangup">Raccrocher</option>
                </select>
              </div>
              <div className="form-group"><label>Ext./ID destination</label><input value={schedForm.closed_destination} onChange={e => setSchedForm({ ...schedForm, closed_destination: e.target.value })} /></div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowSchedModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Créer</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showHolModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Nouveau jour férié</h3>
            <form onSubmit={saveHol}>
              <div className="form-group"><label>Date</label><input type="date" value={holForm.date} onChange={e => setHolForm({ ...holForm, date: e.target.value })} required /></div>
              <div className="form-group"><label>Nom</label><input value={holForm.name} onChange={e => setHolForm({ ...holForm, name: e.target.value })} required /></div>
              <div style={{ marginBottom: '.85rem' }}>
                <label style={{ fontSize: '.9rem' }}><input type="checkbox" checked={holForm.recurring} onChange={e => setHolForm({ ...holForm, recurring: e.target.checked })} /> Récurrent (chaque année)</label>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn" onClick={() => setShowHolModal(false)}>Annuler</button>
                <button type="submit" className="btn btn-primary">Créer</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
