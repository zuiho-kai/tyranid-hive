import type { BusEvent, Handoff, Lifeform, Synapse, Task } from '../api'

const utf8Decoder = new TextDecoder('utf-8', { fatal: false })

const modeLabels: Record<string, string> = {
  auto: '自动路由',
  solo: '单线处理',
  trial: '对比评审',
  chain: '串行协作',
  swarm: '并行分化',
}

const stateLabels: Record<string, string> = {
  Start: '已创建',
  Incubating: '任务受理',
  Planning: '规划中',
  Reviewing: '审阅中',
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
  review: '审阅中',
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
  overmind: '虫群主宰',
  'code-expert': '实施子主脑',
  'research-analyst': '研究子主脑',
  'evolution-master': '演化子主脑',
  'finance-scout': '市场子主脑',
}

const synapseLabels: Record<string, { name: string; role: string; emoji: string }> = {
  overmind: {
    name: '虫群主宰',
    role: '负责接球、判断和最终收敛',
    emoji: '宰',
  },
  'evolution-master': {
    name: '演化子主脑',
    role: '负责提炼经验和调整谱系策略',
    emoji: '演',
  },
  'code-expert': {
    name: '实施子主脑',
    role: '负责实现、修复和验证',
    emoji: '实',
  },
  'research-analyst': {
    name: '研究子主脑',
    role: '负责检索、整理和归纳',
    emoji: '研',
  },
  'finance-scout': {
    name: '市场子主脑',
    role: '负责行情、资金与市场信号',
    emoji: '市',
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
    .replace(/闁崇帟?/g, '->')
    .replace(/闁炽儺娲闁炽儺娉闁炽儺娉瑋闁炽儺娉箌闁炽儺娉縷闁炽儺娲€/g, '...')
    .replace(/闁愁櫌?/g, '-')
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

export function displayLifeformName(lifeform: Lifeform | null | undefined, fallback = '') {
  if (!lifeform) return fallback
  if (lifeform.display_name) return sanitizeText(lifeform.display_name, lifeform.display_name)
  if (lifeform.name) return sanitizeText(lifeform.name, lifeform.name)
  return fallback
}

export function displayTaskOwner(task: Pick<Task, 'current_owner' | 'assignee_synapse'> | null | undefined) {
  if (!task) return '虫群主宰'
  const ownerName = displayLifeformName(task.current_owner, '')
  if (ownerName) return ownerName
  if (task.assignee_synapse) {
    return synapseLabels[task.assignee_synapse]?.name ?? sanitizeText(task.assignee_synapse, task.assignee_synapse)
  }
  return '虫群主宰'
}

export function displayHandoffTarget(handoff: Handoff | null | undefined, lifeforms: Lifeform[] = []) {
  if (!handoff) return '未指定对象'
  if (handoff.to_lifeform) return displayLifeformName(handoff.to_lifeform, '未指定对象')
  const found = handoff.to_lifeform_id
    ? lifeforms.find(item => item.id === handoff.to_lifeform_id)
    : undefined
  return displayLifeformName(found, '未指定对象')
}

export function displayHandoffSource(handoff: Handoff | null | undefined, lifeforms: Lifeform[] = []) {
  if (!handoff) return '未知来源'
  if (handoff.from_lifeform) return displayLifeformName(handoff.from_lifeform, '未知来源')
  const found = handoff.from_lifeform_id
    ? lifeforms.find(item => item.id === handoff.from_lifeform_id)
    : undefined
  return displayLifeformName(found, '未知来源')
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
  if (value === 'trial-race') return '对比评审'
  if (value === 'chain-runner') return '串行协作'
  if (value === 'swarm-runner') return '并行分化'
  if (value === 'task_service') return '任务服务'
  if (value === 'dispatcher') return '调度器'
  if (value === 'orchestrator') return '编排器'
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
