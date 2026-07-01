import { useState, useEffect } from 'react'
import api from '../services/api'

export default function CDRPage() {
  const [tenants, setTenants] = useState([])
  const [tenantId, setTenantId] = useState('')
  const [records, setRecords] = useState([])
  const [summary, setSummary] = useState(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    api.get('/tenants').then(r => setTenants(r.data))
  }, [])

  const load = async (tid = tenantId, p = page) => {
    if (!tid) return
    const [cdrs, sum] = await Promise.all([
      api.get(`/cdr/tenant/${tid}?page=${p}&page_size=50`),
      api.get(`/cdr/tenant/${tid}/summary`),
    ])
    setRecords(cdrs.data.items)
    setTotal(cdrs.data.total)
    setSummary(sum.data)
  }

  useEffect(() => { load() }, [tenantId, page])

  const fmtDur = s => {
    if (!s) return '—'
    const m = Math.floor(s / 60), sec = s % 60
    return `${m}m${sec.toString().padStart(2, '0')}s`
  }

  const fmtCost = c => c ? `$${Number(c).toFixed(4)}` : '—'

  return (
    <div>
      <h1 className="page-title">CDR</h1>

      <div className="toolbar">
        <select className="search-input" value={tenantId} onChange={e => { setTenantId(e.target.value); setPage(1) }}>
          <option value="">Sélectionner un tenant</option>
          {tenants.map(t => <option key={t.id} value={t.id}>{t.company_name}</option>)}
        </select>
      </div>

      {summary && (
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
          {[
            ['Appels total', summary.total_calls],
            ['Répondus', summary.answered_calls],
            ['Durée facturée', fmtDur(summary.total_billsec)],
            ['Coût total', fmtCost(summary.total_cost)],
          ].map(([label, val]) => (
            <div key={label} className="card" style={{ flex: 1, margin: 0 }}>
              <div className="info-label">{label}</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#0f3460' }}>{val}</div>
            </div>
          ))}
        </div>
      )}

      <table>
        <thead>
          <tr>
            <th>Date/Heure</th>
            <th>Direction</th>
            <th>De</th>
            <th>Vers</th>
            <th>Durée</th>
            <th>Disposition</th>
            <th>Coût</th>
          </tr>
        </thead>
        <tbody>
          {records.map(r => (
            <tr key={r.id}>
              <td>{r.start_time ? new Date(r.start_time).toLocaleString('fr-CA') : '—'}</td>
              <td><span className={`badge ${r.direction === 'inbound' ? 'badge-blue' : 'badge-orange'}`}>{r.direction || '—'}</span></td>
              <td>{r.src || '—'}</td>
              <td>{r.dst || '—'}</td>
              <td>{fmtDur(r.billsec)}</td>
              <td>
                <span className={`badge ${r.disposition === 'ANSWERED' ? 'badge-green' : r.disposition === 'BUSY' ? 'badge-orange' : 'badge-red'}`}>
                  {r.disposition || '—'}
                </span>
              </td>
              <td>{fmtCost(r.cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {total > 50 && (
        <div style={{ display: 'flex', gap: '.5rem', marginTop: '.75rem', justifyContent: 'flex-end' }}>
          <button className="btn btn-sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Préc.</button>
          <span style={{ padding: '.3rem .6rem', fontSize: '.88rem' }}>Page {page} / {Math.ceil(total / 50)}</span>
          <button className="btn btn-sm" disabled={page * 50 >= total} onClick={() => setPage(p => p + 1)}>Suiv.</button>
        </div>
      )}
    </div>
  )
}
