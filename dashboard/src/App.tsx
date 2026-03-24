import { useCallback, useDeferredValue, useEffect, useMemo, useState } from 'react'
import {
  createMission,
  fetchStats,
  fetchSynapses,
  fetchTasks,
} from './api'
import type {
  BusEvent,
  MissionMode,
  MissionRequest,
  MissionUnitInput,
  Synapse,
  Task,
  TaskStats,
} from './api'
import { useHiveWebSocket } from './useWebSocket'
import ChannelSidebar from './components/ChannelSidebar'
import DetailPanel from './components/DetailPanel'
import TrunkChat from './components/TrunkChat'

export interface MissionDraft {
  message: string
  priority: string
  mode: MissionMode
  trialCandidates: [string, string]
  chainStages: string[]
  swarmUnits: MissionUnitInput[]
}

const DEFAULT_DRAFT: MissionDraft = {
  message: '',
  priority: 'high',
  mode: 'auto',
  trialCandidates: ['code-expert', 'research-analyst'],
  chainStages: ['code-expert', 'research-analyst'],
  swarmUnits: [
    { synapse: 'research-analyst', message: '补充资料与背景信息' },
    { synapse: 'code-expert', message: '完成主要实现或修复' },
  ],
}

const DONE_STATES = new Set(['Complete', 'Cancelled'])

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [synapses, setSynapses] = useState<Synapse[]>([])
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [draft, setDraft] = useState<MissionDraft>(DEFAULT_DRAFT)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const deferredSearch = useDeferredValue(search)

  const refreshTasks = useCallback(async () => {
    setLoading(true)
    try {
      const params = deferredSearch.trim() ? { q: deferredSearch.trim() } : undefined
      const [nextTasks, nextStats] = await Promise.all([fetchTasks(params), fetchStats()])
      setTasks(nextTasks)
      setStats(nextStats)
      setSelectedTaskId(current => {
        if (!current) return nextTasks.find(task => !DONE_STATES.has(task.state))?.id ?? nextTasks[0]?.id ?? null
        return nextTasks.some(task => task.id === current)
          ? current
          : nextTasks.find(task => !DONE_STATES.has(task.state))?.id ?? nextTasks[0]?.id ?? null
      })
    } finally {
      setLoading(false)
    }
  }, [deferredSearch])

  useEffect(() => {
    void fetchSynapses().then(setSynapses)
    void refreshTasks()
  }, [refreshTasks])

  const handleWsEvent = useCallback((event: BusEvent) => {
    if (event.topic.startsWith('task.')) {
      void refreshTasks()
    }
  }, [refreshTasks])

  const { connected, events } = useHiveWebSocket(handleWsEvent)

  const selectedTask = useMemo(
    () => tasks.find(task => task.id === selectedTaskId) ?? null,
    [selectedTaskId, tasks],
  )

  const filteredTasks = useMemo(() => {
    const needle = deferredSearch.trim().toLowerCase()
    if (!needle) return tasks
    return tasks.filter(task =>
      [task.title, task.description, task.id, task.exec_mode ?? '']
        .join(' ')
        .toLowerCase()
        .includes(needle),
    )
  }, [deferredSearch, tasks])

  const handleSubmitMission = useCallback(async () => {
    const description = draft.message.trim()
    if (!description) return

    setSubmitting(true)
    try {
      const title = deriveTitle(description)
      const payload = buildMissionPayload(draft, title, description)
      const mission = await createMission(payload)
      setTasks(current => [mission.task, ...current.filter(task => task.id !== mission.task.id)])
      setSelectedTaskId(mission.task.id)
      setDraft(current => ({ ...current, message: '' }))
      await refreshTasks()
    } finally {
      setSubmitting(false)
    }
  }, [draft, refreshTasks])

  return (
    <div className="relative min-h-screen overflow-hidden bg-[var(--cl-bg)] text-[var(--cl-text)]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(109,121,181,0.14),transparent_28%),radial-gradient(circle_at_top_right,rgba(79,131,169,0.10),transparent_24%),radial-gradient(circle_at_bottom_left,rgba(177,133,76,0.12),transparent_22%),linear-gradient(180deg,#fffdf9_0%,#f6f1ea_52%,#efe6da_100%)]" />
      <div className="absolute inset-0 opacity-[0.18]" style={{ backgroundImage: 'linear-gradient(rgba(93,72,47,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(93,72,47,0.05) 1px, transparent 1px)', backgroundSize: '26px 26px' }} />

      <div className="relative flex min-h-screen flex-col gap-4 p-4 lg:h-screen lg:flex-row lg:overflow-hidden">
        <ChannelSidebar
          connected={connected}
          loading={loading}
          onSearchChange={setSearch}
          onSelectTask={setSelectedTaskId}
          search={search}
          selectedTaskId={selectedTaskId}
          stats={stats}
          synapseCount={synapses.length}
          tasks={filteredTasks}
        />

        <div className="min-h-[54vh] flex-1 overflow-hidden rounded-[32px] border border-[var(--cl-border)] bg-[var(--cl-surface)] shadow-[0_28px_90px_rgba(122,91,62,0.12)] backdrop-blur-xl">
          <TrunkChat
            draft={draft}
            events={events}
            onDraftChange={setDraft}
            onSubmitMission={handleSubmitMission}
            selectedTask={selectedTask}
            submitting={submitting}
            synapses={synapses}
          />
        </div>

        <DetailPanel
          draft={draft}
          events={events}
          selectedTask={selectedTask}
          synapses={synapses}
        />
      </div>
    </div>
  )
}

function buildMissionPayload(draft: MissionDraft, title: string, description: string): MissionRequest {
  const payload: MissionRequest = {
    title,
    description,
    priority: draft.priority,
    mode: draft.mode,
  }

  if (draft.mode === 'trial') {
    payload.trial_candidates = draft.trialCandidates
  }
  if (draft.mode === 'chain') {
    payload.chain_stages = draft.chainStages.filter(Boolean)
  }
  if (draft.mode === 'swarm') {
    payload.swarm_units = draft.swarmUnits
      .filter(unit => unit.synapse && unit.message.trim())
      .map(unit => ({
        synapse: unit.synapse,
        message: unit.message.trim(),
        domain: unit.domain?.trim() || '',
      }))
  }

  return payload
}

function deriveTitle(message: string) {
  const firstLine = message.split('\n').find(line => line.trim())?.trim() ?? message.trim()
  if (firstLine.length <= 62) return firstLine
  return `${firstLine.slice(0, 62).trimEnd()}...`
}
