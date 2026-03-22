/** API 客户端 */

const BASE = '/api'

export interface Task {
  id: string
  task_uuid: string
  trace_id: string
  title: string
  description: string
  state: string
  priority: string
  exec_mode: string | null
  assignee_synapse: string | null
  creator: string
  flow_log: FlowEntry[]
  progress_log: ProgressEntry[]
  todos: Todo[]
  meta: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface FlowEntry {
  from: string | null
  to: string
  agent: string
  reason: string
  ts: string
}

export interface ProgressEntry {
  agent: string
  content: string
  ts: string
}

export interface Todo {
  id?: string
  title: string
  done: boolean
}

export interface Synapse {
  id: string
  name: string
  role: string
  emoji: string
  tier: number
}

export interface Lesson {
  id: string
  domain: string
  tags: string
  outcome: string
  content: string
  frequency: number
  last_used: string
  task_id: string | null
}

export interface Playbook {
  id: string
  slug: string
  version: number
  is_active: boolean
  domain: string
  title: string
  content: string
  use_count: number
  success_rate: number
  crystallized: boolean
}

export interface BusEvent {
  event_id: string
  trace_id: string
  topic: string
  event_type: string
  producer: string
  payload: Record<string, unknown>
  created_at: string
}

export interface TaskStats {
  total: number
  active: number
  complete: number
  cancelled: number
  by_state: Record<string, number>
}

// ── Tasks ────────────────────────────────────────────────

export async function fetchTasks(params?: { state?: string; q?: string; priority?: string }): Promise<Task[]> {
  const sp = new URLSearchParams()
  if (params?.state)    sp.set('state', params.state)
  if (params?.q)        sp.set('q', params.q)
  if (params?.priority) sp.set('priority', params.priority)
  const qs = sp.toString()
  const r = await fetch(`${BASE}/tasks${qs ? '?' + qs : ''}`)
  return r.json()
}

export async function fetchTask(id: string): Promise<Task> {
  const r = await fetch(`${BASE}/tasks/${id}`)
  return r.json()
}

export async function createTask(payload: { title: string; description?: string; priority?: string }): Promise<Task> {
  const r = await fetch(`${BASE}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return r.json()
}

export async function transitionTask(id: string, new_state: string, agent = 'dashboard', reason = ''): Promise<Task> {
  const r = await fetch(`${BASE}/tasks/${id}/transition`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_state, agent, reason }),
  })
  return r.json()
}

export async function fetchStats(): Promise<TaskStats> {
  const r = await fetch(`${BASE}/tasks/stats`)
  return r.json()
}

export async function patchTask(id: string, fields: { title?: string; description?: string; priority?: string }): Promise<Task> {
  const r = await fetch(`${BASE}/tasks/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  })
  return r.json()
}

export async function deleteTask(id: string): Promise<void> {
  await fetch(`${BASE}/tasks/${id}`, { method: 'DELETE' })
}

export async function bulkTransition(task_ids: string[], new_state: string, agent = 'dashboard', reason = ''): Promise<{ ok: string[]; failed: { id: string; reason: string }[] }> {
  const r = await fetch(`${BASE}/tasks/bulk/transition`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_ids, new_state, agent, reason }),
  })
  return r.json()
}

// ── Synapses ─────────────────────────────────────────────

export async function fetchSynapses(): Promise<Synapse[]> {
  const r = await fetch(`${BASE}/synapses`)
  return r.json()
}

// ── Lessons ──────────────────────────────────────────────

export async function fetchLessons(domain?: string): Promise<Lesson[]> {
  const url = domain ? `${BASE}/lessons?domain=${domain}` : `${BASE}/lessons`
  const r = await fetch(url)
  return r.json()
}

// ── Playbooks ────────────────────────────────────────────

export async function fetchPlaybooks(domain?: string): Promise<Playbook[]> {
  const url = domain ? `${BASE}/playbooks?domain=${domain}` : `${BASE}/playbooks`
  const r = await fetch(url)
  return r.json()
}

// ── Events ───────────────────────────────────────────────

export async function fetchEvents(task_id?: string): Promise<BusEvent[]> {
  const url = task_id ? `${BASE}/events?task_id=${task_id}&limit=50` : `${BASE}/events?limit=50`
  const r = await fetch(url)
  return r.json()
}
