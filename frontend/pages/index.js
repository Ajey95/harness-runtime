import { useEffect, useState } from 'react'

const API = 'http://localhost:8000'

export default function Home() {
  const [traces, setTraces] = useState([])
  const [approvals, setApprovals] = useState([])

  async function loadTraces() {
    const res = await fetch(`${API}/traces`)
    const data = await res.json()
    setTraces(data || [])
  }

  async function loadApprovals() {
    const res = await fetch(`${API}/approvals`)
    const data = await res.json()
    setApprovals(data || [])
  }

  useEffect(() => { loadTraces(); loadApprovals(); }, [])

  async function startVerify(taskId) {
    await fetch(`${API}/verify/${taskId}`, { method: 'POST' })
    alert('Verification started for ' + taskId)
  }

  async function approve(taskId) {
    await fetch(`${API}/approvals/${taskId}?approved=true&approver=dashboard&note=approved`, { method: 'POST' })
    alert('Approved ' + taskId)
    loadApprovals()
  }

  return (
    <main style={{ padding: 24, fontFamily: 'Arial, sans-serif' }}>
      <h1>Harness Runtime Dashboard</h1>
      <div style={{ display: 'flex', gap: 24 }}>
        <section style={{ flex: 1 }}>
          <h2>Traces</h2>
          <button onClick={loadTraces}>Refresh Traces</button>
          {traces.length === 0 && <p>No traces yet</p>}
          {traces.map(t => (
            <div key={t.task_id} style={{ border: '1px solid #eee', padding: 8, marginTop: 8 }}>
              <strong>{t.task_id}</strong> — {t.status}
              <div style={{ marginTop: 8 }}>
                <button onClick={() => startVerify(t.task_id)}>Run Verification</button>
              </div>
              <pre style={{ background: '#fafafa', padding: 8 }}>{JSON.stringify(t.traces, null, 2)}</pre>
            </div>
          ))}
        </section>

        <aside style={{ width: 360 }}>
          <h2>Approvals</h2>
          <button onClick={loadApprovals}>Refresh Approvals</button>
          {approvals.length === 0 && <p>No approvals</p>}
          {approvals.map(a => (
            <div key={a.task_id} style={{ border: '1px solid #eee', padding: 8, marginTop: 8 }}>
              <strong>{a.task_id}</strong>
              <div>Approved: {String(a.approved)}</div>
              <div>Approver: {a.approver}</div>
              <div style={{ marginTop: 8 }}>
                <button onClick={() => approve(a.task_id)}>Approve</button>
              </div>
            </div>
          ))}
        </aside>
      </div>
    </main>
  )
}
