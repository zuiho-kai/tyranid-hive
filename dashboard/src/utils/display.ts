import type { BusEvent, Synapse, Task } from '../api'

const utf8Decoder = new TextDecoder('utf-8', { fatal: false })

const modeLabels: Record<string, string> = {
  auto: '自动路由',
  solo: '单代理',
  trial: '对比评审',
  chain: '串行协作',
  swarm: '并行协作',
}

const stateLabels: Record<string, string> = {
  Start: '已创建',
  Incubating: '任务受理',
  Planning: '规划中',
  Reviewing: '评审中',
  Spawning: '准备执行',
  Executing: '执行中',
  Consolidating: '整理中',
  WaitingInput: '等待补充',
  Complete: '已完成',
  Dormant: '已阻塞',
  Cancelled: '已取消',
}

const lifecycleLabels: Record<string, string> = {
  idea: '待开始',
  spec: '规划中',
  progress: '进行中',
  review: '评审中',
  done: '已完成',
  blocked: '已阻塞',
}

const priorityLabels: Record<string, string> = {
  low: '低',
  normal: '普通',
  high: '高',
  critical: '紧急',
}

const stageLabels: Record<string, string> = {
  mission: '任务受理',
  routing: '路由判断',
  execution: '执行阶段',
  idle: '空闲',
  overmind: '主脑',
  'code-expert': '代码专家',
  'research-analyst': '研究分析',
  'evolution-master': '演化主控',
  'finance-scout': '金融侦察',
}

const synapseLabels: Record<string, { name: string; role: string; emoji: string }> = {
  overmind: {
    name: '主脑',
    role: '负责受理、判断和任务分流',
    emoji: 'O',
  },
  'evolution-master': {
    name: '演化主控',
    role: '沉淀经验并转成可复用策略',
    emoji: 'E',
  },
  'code-expert': {
    name: '代码专家',
    role: '负责实现、修复与验证',
    emoji: 'C',
  },
  'research-analyst': {
    name: '研究分析',
    role: '负责查资料、比方案、做摘要',
    emoji: 'R',
  },
  'finance-scout': {
    name: '金融侦察',
    role: '负责金融数据与市场信号收集',
    emoji: 'F',
  },
}

function looksLikeQuestionGarble(text: string) {
  const trimmed = text.trim()
  return trimmed.length >= 3 && /^\?+$/.test(trimmed)
}

function looksLikeLatin1Utf8Garble(text: string) {
  return /[\u00c0-\u00ff]/.test(text) || /[\u0080-\u009f]/.test(text)
}

function cjkCount(text: string) {
  return (text.match(/[\u3400-\u9fff]/g) ?? []).length
}

function repairLatin1Utf8(text: string) {
  if (!looksLikeLatin1Utf8Garble(text)) return text

  try {
    const chars = Array.from(text)
    if (chars.some(char => char.charCodeAt(0) > 0xff)) return text

    const bytes = Uint8Array.from(chars.map(char => char.charCodeAt(0)))
    const repaired = utf8Decoder.decode(bytes)
    return cjkCount(repaired) > cjkCount(text) ? repaired : text
  } catch {
    return text
  }
}

function replaceKnownGarble(text: string) {
  return text
    .replace(/閳玕?/g, '->')
    .replace(/閳ヮ洣|閳ヮ泧|閳ヮ泬|閳ヮ泹|閳ヮ泿|閳ヮ洀/g, '...')
    .replace(/閳?/g, '-')
}

export function sanitizeText(value: unknown, fallback = ''): string {
  if (typeof value !== 'string') return fallback

  let text = value
  text = repairLatin1Utf8(text)
  text = replaceKnownGarble(text)

  if (looksLikeQuestionGarble(text)) return fallback
  return text
}

export function sanitizeJson(value: unknown): unknown {
  if (typeof value === 'string') return sanitizeText(value)
  if (Array.isArray(value)) return value.map(item => sanitizeJson(item))
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, sanitizeJson(item)]),
    )
  }
  return value
}

export function formatMode(value: string | null | undefined) {
  return modeLabels[value ?? ''] ?? (value || '自动路由')
}

export function formatState(value: string | null | undefined) {
  return stateLabels[value ?? ''] ?? (value || '未知状态')
}

export function formatStage(value: string | null | undefined) {
  return stageLabels[value ?? ''] ?? sanitizeText(value ?? '', value || '未知阶段')
}

export function formatEventType(value: string) {
  const clean = sanitizeText(value, value)
  return clean
    .split('.')
    .map(part => part.replace(/_/g, ' '))
    .join(' / ')
}

export function displayTaskTitle(task: Pick<Task, 'title' | 'id'> | null | undefined) {
  if (!task) return '未命名任务'
  return sanitizeText(task.title, task.id)
}

export function displayTaskDescription(task: Pick<Task, 'description'> | null | undefined) {
  if (!task) return ''
  return sanitizeText(task.description, '')
}

export function formatSpeaker(value: string) {
  if (value.startsWith('synapse.')) {
    const synapseId = value.slice('synapse.'.length)
    return synapseLabels[synapseId]?.name ?? synapseId
  }
  if (value === 'system') return '系统'
  if (value === 'user') return '用户'
  if (value === 'mission-api') return '任务接口'
  if (value === 'mode-router') return '路由器'
  if (value === 'task_service') return '任务服务'
  if (value === 'dispatcher') return '调度器'
  return sanitizeText(value, value)
}

export function displaySynapse(synapse: Synapse) {
  const fallback = synapseLabels[synapse.id]
  return {
    emoji: fallback?.emoji ?? sanitizeText(synapse.emoji, synapse.id.slice(0, 1).toUpperCase()),
    name: fallback?.name ?? sanitizeText(synapse.name, synapse.id),
    role: fallback?.role ?? sanitizeText(synapse.role, synapse.id),
  }
}

export function summarizeFallbackEvent(event: BusEvent) {
  return formatEventType(event.event_type)
}

export function getLifecycleState(state: string | null | undefined) {
  if (!state) return 'idea'
  if (state === 'Complete') return 'done'
  if (state === 'Cancelled' || state === 'Dormant' || state === 'WaitingInput') return 'blocked'
  if (state === 'Planning') return 'spec'
  if (state === 'Reviewing') return 'review'
  if (state === 'Spawning' || state === 'Executing' || state === 'Consolidating') return 'progress'
  return 'idea'
}

export function formatLifecycleState(state: string | null | undefined) {
  const key = getLifecycleState(state)
  return lifecycleLabels[key] ?? lifecycleLabels.idea
}

export function formatPriority(value: string | null | undefined) {
  return priorityLabels[value ?? ''] ?? (value || '普通')
}

export function getTaskBlockers(task: Pick<Task, 'meta'> | null | undefined) {
  return readMetaList(task?.meta, 'analysis_blockers')
}

export function getTaskRisks(task: Pick<Task, 'meta'> | null | undefined) {
  return readMetaList(task?.meta, 'analysis_risks')
}

export function getTaskSummary(task: Pick<Task, 'meta'> | null | undefined) {
  if (!task?.meta) return ''
  return sanitizeText(task.meta.analysis_summary, '')
}

export function getRouteCue(task: Pick<Task, 'exec_mode' | 'state'> | null | undefined) {
  if (!task) return '自动路由'
  if (task.state === 'WaitingInput') return '等待补充'
  return formatMode(task.exec_mode)
}

function readMetaList(meta: Record<string, unknown> | undefined, key: string) {
  const value = meta?.[key]
  if (!Array.isArray(value)) return []
  return value
    .map(item => sanitizeText(item, ''))
    .filter(Boolean)
}
