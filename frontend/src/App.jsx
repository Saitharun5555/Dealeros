import { useState, useEffect, useCallback } from 'react'
import './App.css'

const REASONS = [
  { value: '', label: 'All reasons' },
  { value: 'MISSING_IN_B', label: 'Missing in B' },
  { value: 'ORPHAN_IN_B', label: 'Orphan in B' },
  { value: 'DUPLICATE_IN_B', label: 'Duplicate in B' },
  { value: 'VALUE_MISMATCH', label: 'Value mismatch' },
  { value: 'LOCATION_MISMATCH', label: 'Location mismatch' },
  { value: 'DATE_MISMATCH', label: 'Date mismatch' },
]

const REASON_LABELS = Object.fromEntries(
  REASONS.filter(r => r.value).map(r => [r.value, r.label])
)

function formatValue(val) {
  if (val === null || val === undefined) return ''
  const negative = val.startsWith('-')
  const [whole, fraction = '00'] = val.replace('-', '').split('.')
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${negative ? '-' : ''}${grouped}.${fraction.padEnd(2, '0').slice(0, 2)}`
}

function ReasonBadge({ reason }) {
  const colours = {
    MISSING_IN_B: '#c0392b',
    ORPHAN_IN_B: '#8e44ad',
    DUPLICATE_IN_B: '#e67e22',
    VALUE_MISMATCH: '#2980b9',
    LOCATION_MISMATCH: '#16a085',
    DATE_MISMATCH: '#7f8c8d',
  }
  const bg = colours[reason] || '#555'
  return (
    <span className="reason-badge" style={{ backgroundColor: bg }}>
      {REASON_LABELS[reason] || reason}
    </span>
  )
}

export default function App() {
  const [org, setOrg] = useState('ORG-A')
  const [reason, setReason] = useState('')
  const [sort, setSort] = useState('')
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchData = useCallback(async () => {
    if (!org) return
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ org })
      if (reason) params.set('reason', reason)
      if (sort) params.set('sort', sort)
      const res = await fetch(`/api/disagreements/?${params}`)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.error || `HTTP ${res.status}`)
      }
      const json = await res.json()
      setData(json)
    } catch (err) {
      setError(err.message)
      setData([])
    } finally {
      setLoading(false)
    }
  }, [org, reason, sort])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  function handleValueSort() {
    setSort(prev => {
      if (prev === 'value') return '-value'
      if (prev === '-value') return ''
      return 'value'
    })
  }

  const sortIcon = sort === 'value' ? ' ▲' : sort === '-value' ? ' ▼' : ' ⇅'

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <h1>DealerOS</h1>
          <p>Transaction reconciliation between System A and System B</p>
        </div>
      </header>

      <main className="main">
        <section className="filters">
          <div className="filter-group">
            <label htmlFor="org-select">Organisation</label>
            <select
              id="org-select"
              value={org}
              onChange={e => { setOrg(e.target.value); setReason(''); setSort('') }}
            >
              <option value="ORG-A">ORG-A</option>
              <option value="ORG-B">ORG-B</option>
            </select>
          </div>

          <div className="filter-group">
            <label htmlFor="reason-select">Reason</label>
            <select
              id="reason-select"
              value={reason}
              onChange={e => setReason(e.target.value)}
            >
              {REASONS.map(r => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>

          <div className="filter-group filter-count">
            {!loading && !error && (
              <span>{data.length} disagreement{data.length !== 1 ? 's' : ''}</span>
            )}
          </div>
        </section>

        {loading && (
          <div className="state-box loading">
            <div className="spinner" />
            <span>Loading…</span>
          </div>
        )}

        {error && (
          <div className="state-box error">
            <strong>Error:</strong> {error}
          </div>
        )}

        {!loading && !error && data.length === 0 && (
          <div className="state-box empty">
            No disagreements found for <strong>{org}</strong>
            {reason && <> with reason <strong>{REASON_LABELS[reason]}</strong></>}.
          </div>
        )}

        {!loading && !error && data.length > 0 && (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Reason</th>
                  <th>Record ID</th>
                  <th>Location</th>
                  <th>System A Value</th>
                  <th>System B Value</th>
                  <th
                    className="sortable"
                    onClick={handleValueSort}
                    title="Click to sort by difference"
                  >
                    Difference{sortIcon}
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.map((row, idx) => (
                  <tr key={idx}>
                    <td><ReasonBadge reason={row.reason} /></td>
                    <td className="mono">{row.record_id || ''}</td>
                    <td className="mono">{row.location || ''}</td>
                    <td className="number">{formatValue(row.a_value)}</td>
                    <td className="number">{formatValue(row.b_value)}</td>
                    <td className={`number ${row.difference?.startsWith('-') ? 'negative' : row.difference?.startsWith('0') ? '' : row.difference ? 'positive' : ''}`}>
                      {formatValue(row.difference)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}
