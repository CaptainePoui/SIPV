import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'

export default function Tenants() {
  const [tenants, setTenants] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ company_name: '', account_number: '', max_extensions: 10, max_trunks: 5 })
  const navigate = useNavigate()

  const load = async () => {
    const { data } = await api.get('/tenants')
    setTenants(data)
  }

  useEffect(() => { load() }, [])

  const save = async e => {
    e.preventDefault()
    await api.post('/tenants', form)
    setShowModal(false)
    setForm({ company_name: '', account_number: '', max_extensions: 10, max_trunks: 5 })
    load()
  }

  return (
    <div>
      <div className="toolbar">
        <h1 className="page-title" style={{ margin: 0 }}>Tenants</h1>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>+ Nouveau</button>
      </div>

      <table>
        <thead>
          <tr>
            <th>Compagnie</th>
            <th>Compte</th>
            <th>Extensions</th>
            <th>Trunks</th>
            <th>Statut</th>
          </tr>
        </thead>
        <tbody>
          {tenants.map(t => (
            <tr key={t.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/tenants/${t.id}`)}>
              <td>{t.company_name}</td>
              <td><code>{t.account_number}</code></td>
              <td>{t.max_extensions}</td>
              <td>{t.max_trunks}</td>
              <td>
                <span className={`badge ${t.is_active ? 'badge-green' : 'badge-gray'}`}>
                  {t.is_active ? 'Actif' : 'Inactif'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showModal && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Nouveau tenant</h3>
            <form onSubmit={save}>
              <div className="form-group">
                <label>Compagnie</label>
                <input value={form.company_name} onChange={e => setForm({ ...form, company_name: e.target.value })} required />
              </div>
              <div className="form-group">
                <label>Numéro de compte</label>
                <input value={form.account_number} onChange={e => setForm({ ...form, account_number: e.target.value })} required />
              </div>
              <div className="form-group">
                <label>Max extensions</label>
                <input type="number" value={form.max_extensions} onChange={e => setForm({ ...form, max_extensions: +e.target.value })} />
              </div>
              <div className="form-group">
                <label>Max trunks</label>
                <input type="number" value={form.max_trunks} onChange={e => setForm({ ...form, max_trunks: +e.target.value })} />
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
