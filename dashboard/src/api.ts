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

export async function fetchTasks(params?: { state?: string; q?: string; priority?: string; sort_by?: string; order?: string }): Promise<Task[]> {
  const sp = new URLSearchParams()
  if (params?.state)    sp.set('state', params.state)
  if (params?.q)        sp.set('q', params.q)
  if (params?.priority) sp.set('priority', params.priority)
  if (params?.sort_by)  sp.set('sort_by', params.sort_by)
  if (params?.order)    sp.set('order', params.order)
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

export async function appendTodo(id: string, title: string): Promise<Task> {
  const r = await fetch(`${BASE}/tasks/${id}/todos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
  return r.json()
}

export async function toggleTodo(id: string, index: number): Promise<Task> {
  const r = await fetch(`${BASE}/tasks/${id}/todos/${index}`, { method: 'PATCH' })
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

export async function createLesson(payload: { domain: string; content: string; outcome?: string; tags?: string[] }): Promise<Lesson> {
  const r = await fetch(`${BASE}/lessons`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return r.json()
}

export async function bumpLesson(id: string): Promise<Lesson> {
  const r = await fetch(`${BASE}/lessons/${id}/bump`, { method: 'POST' })
  return r.json()
}

// ── Playbooks ────────────────────────────────────────────

export async function fetchPlaybooks(domain?: string): Promise<Playbook[]> {
  const url = domain ? `${BASE}/playbooks?domain=${domain}` : `${BASE}/playbooks`
  const r = await fetch(url)
  return r.json()
}

export async function createPlaybook(payload: { slug: string; domain: string; title: string; content: string }): Promise<Playbook> {
  const r = await fetch(`${BASE}/playbooks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return r.json()
}

// ── Overview Stats ───────────────────────────────────────

export interface OverviewStats {
  tasks: {
    total: number
    by_state: Record<string, number>
  }
  lessons: {
    total: number
    by_domain: Record<string, number>
    by_outcome: Record<string, number>
    top_active: { id: string; domain: string; content: string; frequency: number }[]
  }
  playbooks: {
    total: number
    active: number
    crystallized: number
    by_domain: Record<string, number>
  }
}

export async function fetchOverviewStats(): Promise<OverviewStats> {
  const r = await fetch(`${BASE}/stats/overview`)
  return r.json()
}

// ── Overmind Analyze ─────────────────────────────────────

export interface AnalysisResult {
  summary: string
  domain: string
  todos: string[]
  risks: string[]
  recommended_state: string
}

export async function analyzeTask(id: string): Promise<{ task: Task; analysis: AnalysisResult }> {
  const r = await fetch(`${BASE}/tasks/${id}/analyze`, { method: 'POST' })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${r.status}`)
  }
  return r.json()
}

// ── Trial Race ────────────────────────────────────────────

export interface TrialSynapseResult {
  returncode: number
  success: boolean
  stdout: string
  stderr: string
  elapsed_sec: number
}

export interface TrialResult {
  task_id: string
  winner: string | null
  tie: boolean
  results: Record<string, TrialSynapseResult>
}

export async function trialTask(
  id: string,
  synapses: [string, string],
  message?: string,
  domain?: string,
): Promise<TrialResult> {
  const r = await fetch(`${BASE}/tasks/${id}/trial`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ synapses, message: message || '', domain: domain || '' }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${r.status}`)
  }
  return r.json()
}

// ── Timeline / 生物质净值曲线 ──────────────────────────────

export interface TimelinePoint {
  date: string
  tasks_created: number
  tasks_completed: number
  lessons_added: number
  net_biomass: number
}

export interface TimelineData {
  days: number
  points: TimelinePoint[]
}

export async function fetchTimeline(days = 30): Promise<TimelineData> {
  const r = await fetch(`${BASE}/stats/timeline?days=${days}`)
  return r.json()
}

// ── Evolution Status ─────────────────────────────────────

export interface DomainStatus {
  domain: string
  total: number
  success_count: number
  ready_to_evolve: boolean
}

export interface EvolutionStatus {
  threshold: number
  domains: DomainStatus[]
}

export async function fetchEvolutionStatus(): Promise<EvolutionStatus> {
  const r = await fetch(`${BASE}/evolution/status`)
  return r.json()
}

export async function triggerEvolveDomain(domain: string): Promise<Record<string, unknown> | null> {
  const r = await fetch(`${BASE}/evolution/domain/${domain}`, { method: 'POST' })
  if (r.status === 204) return null
  return r.json()
}

// ── Chain Mode ────────────────────────────────────────────

export interface ChainStageResult {
  synapse: string
  returncode: number
  success: boolean
  stdout: string
  stderr: string
  elapsed_sec: number
}

export interface ChainResult {
  task_id: string
  success: boolean
  final_output: string
  results: ChainStageResult[]
}

export async function chainTask(
  id: string,
  synapses: string[],
  message?: string,
  domain?: string,
): Promise<ChainResult> {
  const r = await fetch(`${BASE}/tasks/${id}/chain`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ synapses, message: message || '', domain: domain || '' }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${r.status}`)
  }
  return r.json()
}

// ── Swarm Mode ───────────────────────────────────────────

export interface SwarmUnitInput {
  synapse: string
  message: string
  domain?: string
}

export interface SwarmUnitResult {
  synapse:     string
  message:     string
  returncode:  number
  success:     boolean
  stdout:      string
  stderr:      string
  elapsed_sec: number
}

export interface SwarmResult {
  task_id:       string
  total:         number
  success_count: number
  fail_count:    number
  success_rate:  number
  all_success:   boolean
  results:       SwarmUnitResult[]
}

export async function swarmTask(
  id: string,
  units: SwarmUnitInput[],
  maxConcurrent = 5,
): Promise<SwarmResult> {
  const r = await fetch(`${BASE}/tasks/${id}/swarm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ units, max_concurrent: maxConcurrent }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${r.status}`)
  }
  return r.json()
}

// ── Events ───────────────────────────────────────────────

export async function fetchEvents(task_id?: string): Promise<BusEvent[]> {
  const url = task_id ? `${BASE}/events?task_id=${task_id}&limit=50` : `${BASE}/events?limit=50`
  const r = await fetch(url)
  return r.json()
}

// ── Fitness 适存度 ────────────────────────────────────────

export interface SynapseScore {
  synapse_id:    string
  fitness:       number
  raw_biomass:   number
  mark_count:    number
  success_count: number
  fail_count:    number
  success_rate:  number
}

export interface FitnessLeaderboard {
  total:  number
  scores: SynapseScore[]
}

export async function fetchFitnessLeaderboard(limit = 20): Promise<FitnessLeaderboard> {
  const r = await fetch(`${BASE}/fitness/leaderboard?limit=${limit}`)
  return r.json()
}

export interface FitnessRecommendation {
  synapse_id:   string
  domain:       string
  fitness:      number
  success_rate: number
  mark_count:   number
  reason:       string
}

export async function recommendSynapse(
  domain: string,
  candidates?: string[],
): Promise<FitnessRecommendation | null> {
  const params = new URLSearchParams({ domain })
  if (candidates?.length) params.set('candidates', candidates.join(','))
  const r = await fetch(`${BASE}/fitness/recommend?${params}`)
  if (r.status === 404) return null
  return r.json()
}
