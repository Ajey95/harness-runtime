import { useEffect, useMemo, useState } from 'react'

const API = 'http://localhost:8000'
const REFRESH_MS = 5000

const statusColors = {
  completed: '#166534',
  verification_failed: '#b91c1c',
  pending_approval: '#b45309',
  rejected: '#991b1b',
  running: '#1d4ed8',
  unknown: '#374151',
}

function toTitle(text) {
  return String(text || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function stepCategory(step) {
  if (!step) return 'reasoning'
  if (step.includes('verification')) return 'verification'
  if (step.includes('approval') || step.includes('risk')) return 'middleware'
  if (step.includes('tool_call') || step.includes('propose_patch') || step.includes('apply_patch')) return 'tool-call'
  return 'reasoning'
}

function lifecycleNodes(traces) {
  const has = (prefix) => traces.some((t) => String(t.step || '').startsWith(prefix))
  return [
    { id: 'task_started', label: 'Task Start', present: has('task_started') },
    { id: 'analysis', label: 'Analysis', present: has('analysis') || has('analysis_result') },
    { id: 'risk_classified', label: 'Risk', present: has('risk_classified') },
    { id: 'approval', label: 'Approval', present: has('approval_requested') || has('approval_response') },
    { id: 'patch', label: 'Patch', present: has('propose_patch') || has('apply_patch') || has('tool_call') },
    { id: 'verification', label: 'Verification', present: has('verification_started') || has('verification_result') },
    { id: 'completion', label: 'Completion', present: has('completed') || has('verification_failed') || has('rejected') },
  ]
}

function deltaMs(prev, next) {
  if (!prev || !next) return null
  const a = Date.parse(prev)
  const b = Date.parse(next)
  if (Number.isNaN(a) || Number.isNaN(b)) return null
  return Math.max(0, b - a)
}

function shortTaskId(taskId) {
  if (!taskId) return 'unknown'
  if (taskId.length <= 18) return taskId
  return `${taskId.slice(0, 8)}...${taskId.slice(-6)}`
}

export default function Home() {
  const [traces, setTraces] = useState([])
  const [approvals, setApprovals] = useState([])
  const [reports, setReports] = useState([])
  const [metricsSummary, setMetricsSummary] = useState(null)
  const [metricsByTask, setMetricsByTask] = useState({})
  const [verificationByTask, setVerificationByTask] = useState({})
  const [selectedTaskId, setSelectedTaskId] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [timelineFilters, setTimelineFilters] = useState({
    reasoning: true,
    'tool-call': true,
    middleware: true,
    verification: true,
  })

  async function loadDashboardData() {
    try {
      setError('')
      const [tracesRes, approvalsRes, reportsRes, metricsRes] = await Promise.all([
        fetch(`${API}/traces`),
        fetch(`${API}/approvals`),
        fetch(`${API}/reports`),
        fetch(`${API}/metrics`),
      ])
      if (!tracesRes.ok || !approvalsRes.ok || !reportsRes.ok || !metricsRes.ok) {
        throw new Error('Dashboard fetch failed')
      }
      const [traceData, approvalsData, reportsData, metricsData] = await Promise.all([
        tracesRes.json(),
        approvalsRes.json(),
        reportsRes.json(),
        metricsRes.json(),
      ])
      const nextTraces = Array.isArray(traceData) ? traceData : []
      const nextApprovals = Array.isArray(approvalsData) ? approvalsData : []
      const nextReports = Array.isArray(reportsData) ? reportsData : []
      setTraces(nextTraces)
      setApprovals(nextApprovals)
      setReports(nextReports)
      setMetricsSummary(metricsData?.summary || null)
      const byTask = {}
      for (const item of metricsData?.tasks || []) {
        byTask[item.task_id] = item
      }
      setMetricsByTask(byTask)
      setLastUpdated(new Date())
      setSelectedTaskId((prev) => {
        if (prev && nextTraces.some((t) => t.task_id === prev)) return prev
        return nextTraces[0]?.task_id || ''
      })
    } catch (e) {
      setError(e?.message || 'Unable to load dashboard data')
    } finally {
      setLoading(false)
    }
  }

  async function loadVerification(taskId) {
    if (!taskId) return
    try {
      const res = await fetch(`${API}/verify/${taskId}`)
      if (!res.ok) {
        setVerificationByTask((prev) => ({ ...prev, [taskId]: null }))
        return
      }
      const data = await res.json()
      setVerificationByTask((prev) => ({ ...prev, [taskId]: data }))
    } catch {
      setVerificationByTask((prev) => ({ ...prev, [taskId]: null }))
    }
  }

  useEffect(() => {
    loadDashboardData()
    const id = setInterval(loadDashboardData, REFRESH_MS)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (selectedTaskId) loadVerification(selectedTaskId)
  }, [selectedTaskId, lastUpdated])

  async function startVerify(taskId) {
    if (!taskId) return
    await fetch(`${API}/verify/${taskId}`, { method: 'POST' })
    await loadDashboardData()
    await loadVerification(taskId)
  }

  async function approve(taskId) {
    if (!taskId) return
    await fetch(
      `${API}/approvals/${taskId}?approved=true&approver=dashboard&note=approved`,
      { method: 'POST' }
    )
    await loadDashboardData()
  }

  const selectedTask = useMemo(
    () => traces.find((t) => t.task_id === selectedTaskId) || null,
    [traces, selectedTaskId]
  )
  const selectedReport = useMemo(
    () => reports.find((r) => r.task_id === selectedTaskId) || null,
    [reports, selectedTaskId]
  )
  const selectedApproval = useMemo(
    () => approvals.find((a) => a.task_id === selectedTaskId) || null,
    [approvals, selectedTaskId]
  )
  const selectedVerification = verificationByTask[selectedTaskId] || null
  const selectedTaskMetrics = metricsByTask[selectedTaskId] || null

  const kpis = useMemo(() => {
    const active = metricsSummary
      ? (metricsSummary.status_counts?.running || 0) + (metricsSummary.pending_approvals || 0)
      : traces.filter((t) => ['running', 'pending_approval'].includes(t.status)).length
    const completed = metricsSummary
      ? (metricsSummary.status_counts?.completed || 0)
      : traces.filter((t) => t.status === 'completed').length
    const verificationFailed = metricsSummary
      ? (metricsSummary.verification_failed || 0)
      : traces.filter((t) => t.status === 'verification_failed').length
    const pendingApprovals = metricsSummary
      ? (metricsSummary.pending_approvals || 0)
      : traces.filter((t) => t.status === 'pending_approval').length
    const degraded = metricsSummary ? (metricsSummary.degraded_tasks || 0) : 0
    return [
      { label: 'Total Tasks', value: metricsSummary?.total_tasks ?? traces.length },
      { label: 'Active', value: active },
      { label: 'Completed', value: completed },
      { label: 'Verification Failed', value: verificationFailed },
      { label: 'Pending Approvals', value: pendingApprovals },
      { label: 'Degraded Tasks', value: degraded },
    ]
  }, [traces, metricsSummary])

  const timeline = useMemo(() => {
    const items = selectedTask?.traces || []
    return items
      .map((entry, idx) => {
        const category = stepCategory(entry.step)
        return {
          ...entry,
          index: idx + 1,
          category,
          deltaMs: idx > 0 ? deltaMs(items[idx - 1]?.timestamp, entry.timestamp) : null,
        }
      })
      .filter((item) => timelineFilters[item.category])
  }, [selectedTask, timelineFilters])

  const graphLifeNodes = lifecycleNodes(selectedTask?.traces || [])
  const graphMiddleware = (selectedTask?.traces || []).filter((t) => stepCategory(t.step) === 'middleware')
  const graphToolCalls = (selectedTask?.traces || []).filter((t) => stepCategory(t.step) === 'tool-call')

  const card = {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    padding: 12,
  }

  return (
    <main style={{ padding: 16, fontFamily: 'Arial, sans-serif', background: '#f8fafc', minHeight: '100vh' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h1 style={{ margin: 0 }}>Harness Runtime Operations Console</h1>
          <small style={{ color: '#475569' }}>
            Live refresh every {REFRESH_MS / 1000}s · Last updated: {lastUpdated ? lastUpdated.toLocaleTimeString() : '—'}
          </small>
        </div>
        <button onClick={loadDashboardData}>Refresh Now</button>
      </header>

      {error && <div style={{ ...card, borderColor: '#fca5a5', color: '#b91c1c', marginBottom: 12 }}>{error}</div>}
      {loading && <div style={{ ...card, marginBottom: 12 }}>Loading dashboard...</div>}

      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(6, minmax(120px, 1fr))', gap: 8, marginBottom: 12 }}>
        {kpis.map((k) => (
          <div key={k.label} style={card}>
            <div style={{ fontSize: 12, color: '#64748b' }}>{k.label}</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{k.value}</div>
          </div>
        ))}
      </section>

      <section style={{ display: 'grid', gridTemplateColumns: '320px 1fr 320px', gap: 12 }}>
        <aside style={card}>
          <h3 style={{ marginTop: 0 }}>Task List</h3>
          {traces.length === 0 && <p style={{ margin: 0 }}>No tasks yet.</p>}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {traces.map((t) => {
              const selected = selectedTaskId === t.task_id
              return (
                <button
                  key={t.task_id}
                  onClick={() => setSelectedTaskId(t.task_id)}
                  style={{
                    textAlign: 'left',
                    border: selected ? '2px solid #2563eb' : '1px solid #e5e7eb',
                    borderRadius: 8,
                    background: selected ? '#eff6ff' : '#fff',
                    padding: 10,
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ fontWeight: 700 }}>{shortTaskId(t.task_id)}</div>
                  <div style={{ color: statusColors[t.status] || statusColors.unknown, fontSize: 12 }}>
                    {toTitle(t.status || 'unknown')}
                  </div>
                </button>
              )
            })}
          </div>
        </aside>

        <section style={{ display: 'grid', gridTemplateRows: 'auto auto', gap: 12 }}>
          <div style={card}>
            <h3 style={{ marginTop: 0 }}>Reasoning Graph</h3>
            {!selectedTask && <p style={{ margin: 0 }}>Select a task to view lifecycle graph.</p>}
            {selectedTask && (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
                  {graphLifeNodes.map((node, idx) => (
                    <div key={node.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div
                        style={{
                          padding: '6px 10px',
                          borderRadius: 999,
                          border: `1px solid ${node.present ? '#16a34a' : '#cbd5e1'}`,
                          color: node.present ? '#166534' : '#64748b',
                          background: node.present ? '#f0fdf4' : '#f8fafc',
                          fontSize: 12,
                        }}
                      >
                        {node.label}
                      </div>
                      {idx < graphLifeNodes.length - 1 && <span style={{ color: '#94a3b8' }}>→</span>}
                    </div>
                  ))}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 8 }}>
                    <strong style={{ fontSize: 12 }}>Middleware Decisions</strong>
                    {graphMiddleware.length === 0 && <div style={{ fontSize: 12, marginTop: 6 }}>No middleware events</div>}
                    {graphMiddleware.map((m, idx) => (
                      <div key={`${m.step}-${idx}`} style={{ fontSize: 12, marginTop: 6 }}>
                        {toTitle(m.step)}{m.detail ? ` — ${m.detail}` : ''}
                      </div>
                    ))}
                  </div>
                  <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 8 }}>
                    <strong style={{ fontSize: 12 }}>Tool Calls / Patch Actions</strong>
                    {graphToolCalls.length === 0 && <div style={{ fontSize: 12, marginTop: 6 }}>No tool-call events</div>}
                    {graphToolCalls.map((m, idx) => (
                      <div key={`${m.step}-${idx}`} style={{ fontSize: 12, marginTop: 6 }}>
                        {toTitle(m.step)}{m.detail ? ` — ${m.detail}` : ''}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>

          <div style={card}>
            <h3 style={{ marginTop: 0 }}>Execution Timeline</h3>
            <div style={{ display: 'flex', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
              {Object.keys(timelineFilters).map((key) => (
                <label key={key} style={{ fontSize: 12 }}>
                  <input
                    type="checkbox"
                    checked={timelineFilters[key]}
                    onChange={(e) => setTimelineFilters((prev) => ({ ...prev, [key]: e.target.checked }))}
                  />{' '}
                  {toTitle(key)}
                </label>
              ))}
            </div>
            {!selectedTask && <p style={{ margin: 0 }}>Select a task to inspect timeline.</p>}
            {selectedTask && timeline.length === 0 && <p style={{ margin: 0 }}>No timeline events for current filters.</p>}
            {timeline.map((entry) => (
              <div key={`${entry.step}-${entry.index}`} style={{ borderTop: '1px solid #eef2f7', paddingTop: 8, marginTop: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <strong style={{ fontSize: 13 }}>{entry.index}. {toTitle(entry.step)}</strong>
                  <span style={{ fontSize: 11, color: '#64748b' }}>{entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : '—'}</span>
                </div>
                <div style={{ fontSize: 12, color: '#334155', marginTop: 2 }}>
                  Category: {toTitle(entry.category)}
                  {entry.deltaMs != null ? ` · +${entry.deltaMs} ms from previous event` : ''}
                </div>
                {entry.detail && <div style={{ fontSize: 12, marginTop: 2 }}>{entry.detail}</div>}
              </div>
            ))}
          </div>
        </section>

        <aside style={{ display: 'grid', gridTemplateRows: 'auto auto auto auto', gap: 12 }}>
          <div style={card}>
            <h3 style={{ marginTop: 0 }}>Task Summary</h3>
            {!selectedTask && <p style={{ margin: 0 }}>No task selected.</p>}
            {selectedTask && (
              <>
                <div style={{ fontSize: 12, marginBottom: 4 }}>Task: <strong>{selectedTask.task_id}</strong></div>
                <div style={{ fontSize: 12, marginBottom: 4 }}>
                  Status:{' '}
                  <span style={{ color: statusColors[selectedTask.status] || statusColors.unknown }}>
                    {toTitle(selectedTask.status || 'unknown')}
                  </span>
                </div>
                <div style={{ fontSize: 12, marginBottom: 4 }}>Trace Events: {selectedTask.traces?.length || 0}</div>
              </>
            )}
          </div>

          <div style={card}>
            <h3 style={{ marginTop: 0 }}>Observability Summary</h3>
            <div style={{ fontSize: 12, marginBottom: 4 }}>Risk: <strong>{toTitle(selectedReport?.risk || 'unknown')}</strong></div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>
              Approval: <strong>{selectedApproval ? String(selectedApproval.approved) : 'unknown'}</strong>
            </div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>
              Verification: <strong>{toTitle(selectedReport?.verification_status || selectedVerification?.status || 'not_started')}</strong>
            </div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>
              Duration: <strong>{selectedReport?.duration_ms != null ? `${selectedReport.duration_ms} ms` : 'unknown'}</strong>
            </div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>
              Avg Runtime: <strong>{metricsSummary?.average_duration_ms != null ? `${metricsSummary.average_duration_ms} ms` : 'unknown'}</strong>
            </div>
          </div>

          <div style={card}>
            <h3 style={{ marginTop: 0 }}>Lifecycle Health</h3>
            {!selectedTaskMetrics && <div style={{ fontSize: 12 }}>No metrics for selected task</div>}
            {selectedTaskMetrics && (
              <>
                <div style={{ fontSize: 12, marginBottom: 4 }}>
                  Trace Runtime: <strong>{selectedTaskMetrics.metrics?.trace_runtime_ms != null ? `${selectedTaskMetrics.metrics.trace_runtime_ms} ms` : 'unknown'}</strong>
                </div>
                <div style={{ fontSize: 12, marginBottom: 4 }}>
                  Events: <strong>{selectedTaskMetrics.metrics?.event_count ?? 0}</strong>
                </div>
                <div style={{ fontSize: 12, marginBottom: 4 }}>
                  Stage Mix: <strong>{JSON.stringify(selectedTaskMetrics.metrics?.stage_counts || {})}</strong>
                </div>
                <div style={{ fontSize: 12 }}>
                  Degraded Signals: <strong>{selectedTaskMetrics.metrics?.degraded_signal_count ?? 0}</strong>
                </div>
              </>
            )}
          </div>

          <div style={card}>
            <h3 style={{ marginTop: 0 }}>Approvals & Actions</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
              <button disabled={!selectedTaskId} onClick={() => startVerify(selectedTaskId)}>Run Verification</button>
              <button disabled={!selectedTaskId} onClick={() => approve(selectedTaskId)}>Approve Task</button>
            </div>
            <div style={{ fontSize: 12, color: '#334155' }}>
              {selectedApproval
                ? `Latest approval: ${String(selectedApproval.approved)} by ${selectedApproval.approver || 'unknown'}`
                : 'No approval record for selected task'}
            </div>
          </div>
        </aside>
      </section>
    </main>
  )
}
