import { useState, useEffect, useRef } from 'react'
import { fetchLessons, fetchPlaybooks, exportGenes, importGenes } from '../api'
import type { Lesson, Playbook, GenesBundle } from '../api'

type Tab = 'lessons' | 'playbooks'

export default function GeneLibrary() {
  const [tab, setTab] = useState<Tab>('lessons')
  const [lessons, setLessons] = useState<Lesson[]>([])
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [importing, setImporting] = useState(false)
  const [importMsg, setImportMsg] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const reload = () => {
    setLoading(true)
    if (tab === 'lessons') {
      fetchLessons().then(setLessons).finally(() => setLoading(false))
    } else {
      fetchPlaybooks().then(setPlaybooks).finally(() => setLoading(false))
    }
  }

  useEffect(() => { reload() }, [tab])

  const doExport = async () => {
    setExporting(true)
    try {
      const bundle = await exportGenes()
      const json = JSON.stringify(bundle, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `hive-genes-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  const doImport = async (file: File) => {
    setImporting(true)
    setImportMsg(null)
    try {
      const text = await file.text()
      const bundle = JSON.parse(text) as Partial<GenesBundle>
      const result = await importGenes(bundle)
      setImportMsg(`✓ 导入完成  经验 +${result.lessons_added}  手册 +${result.playbooks_added}  跳过 ${result.playbooks_skipped}`)
      reload()
    } catch (e) {
      setImportMsg(`✗ 导入失败: ${String(e)}`)
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-5 pt-2.5 border-b border-ww-subtle">
        <div className="flex gap-0.5">
          {(['lessons', 'playbooks'] as Tab[]).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3.5 py-1.5 border-none rounded-t-md cursor-pointer text-xs transition-colors ${
                tab === t
                  ? 'bg-ww-card text-opus-primary border-b-2 border-b-opus-primary'
                  : 'bg-transparent text-ww-dim border-b-2 border-b-transparent hover:text-ww-muted'
              }`}
            >
              {t === 'lessons' ? '📚 经验教训' : '📖 作战手册'}
            </button>
          ))}
        </div>
        <div className="flex gap-1.5 pb-1">
          <button onClick={doExport} disabled={exporting} className="px-2.5 py-1 bg-ww-card border border-ww-subtle rounded text-opus-primary cursor-pointer text-[11px] hover:bg-ww-surface transition-colors">
            {exporting ? '导出中…' : '↑ 导出'}
          </button>
          <button onClick={() => fileInputRef.current?.click()} disabled={importing} className="px-2.5 py-1 bg-ww-card border border-ww-subtle rounded text-ww-muted cursor-pointer text-[11px] hover:bg-ww-surface transition-colors">
            {importing ? '导入中…' : '↓ 导入'}
          </button>
          <input ref={fileInputRef} type="file" accept=".json" className="hidden" onChange={e => { if (e.target.files?.[0]) doImport(e.target.files[0]) }} />
        </div>
      </div>

      {importMsg && (
        <div className={`mx-5 mt-2 px-3 py-1.5 rounded text-xs border ${
          importMsg.startsWith('✓')
            ? 'bg-ww-success/10 text-ww-success border-ww-success/30'
            : 'bg-ww-danger/10 text-ww-danger border-ww-danger/30'
        }`}>
          {importMsg}
          <button onClick={() => setImportMsg(null)} className="float-right bg-transparent border-none text-ww-dim cursor-pointer text-[11px]">✕</button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-5">
        {loading ? (
          <div className="text-ww-dim text-[13px]">加载中…</div>
        ) : tab === 'lessons' ? (
          <LessonsView lessons={lessons} />
        ) : (
          <PlaybooksView playbooks={playbooks} />
        )}
      </div>
    </div>
  )
}

function LessonsView({ lessons }: { lessons: Lesson[] }) {
  if (lessons.length === 0) {
    return <div className="text-ww-dim text-[13px] text-center mt-10">暂无经验教训记录</div>
  }
  return (
    <div className="flex flex-col gap-2.5">
      {lessons.map(l => (
        <div key={l.id} className="bg-ww-surface rounded-lg px-4 py-3 border border-ww-subtle">
          <div className="flex justify-between mb-1.5">
            <div className="flex gap-1.5">
              <span className="text-[11px] px-2 py-0.5 bg-ww-card rounded text-opus-primary">{l.domain}</span>
              <span className="text-[11px] px-2 py-0.5 rounded" style={{ background: outcomeColor(l.outcome) + '22', color: outcomeColor(l.outcome) }}>{l.outcome}</span>
            </div>
            <span className="text-[11px] text-ww-dim">×{l.frequency}</span>
          </div>
          <div className="text-[13px] text-ww-main leading-relaxed mb-1.5">{l.content}</div>
          {l.tags && <div className="text-[11px] text-ww-dim">{l.tags}</div>}
        </div>
      ))}
    </div>
  )
}

function PlaybooksView({ playbooks }: { playbooks: Playbook[] }) {
  if (playbooks.length === 0) {
    return <div className="text-ww-dim text-[13px] text-center mt-10">暂无作战手册</div>
  }
  return (
    <div className="flex flex-col gap-2.5">
      {playbooks.map(p => (
        <div key={p.id} className={`bg-ww-surface rounded-lg px-4 py-3 border ${p.is_active ? 'border-ww-subtle' : 'border-ww-surface opacity-60'}`}>
          <div className="flex justify-between items-start mb-1.5">
            <div>
              <span className="text-sm font-semibold text-ww-main">{p.title}</span>
              {p.crystallized && <span className="ml-1.5 text-[10px] text-gemini-primary border border-gemini-primary rounded px-1.5 py-px">晶化</span>}
            </div>
            <div className="flex gap-1.5 text-[11px] text-ww-dim">
              <span>v{p.version}</span>
              <span>·</span>
              <span className={p.is_active ? 'text-ww-success' : 'text-ww-dim'}>{p.is_active ? '活跃' : '归档'}</span>
            </div>
          </div>
          <div className="flex gap-2.5 text-[11px] text-ww-dim mb-1.5">
            <span>{p.domain}</span><span>·</span>
            <span>使用 {p.use_count} 次</span><span>·</span>
            <span>成功率 {Math.round(p.success_rate * 100)}%</span>
          </div>
          <div className="text-xs text-ww-dim leading-normal whitespace-pre-wrap max-h-20 overflow-hidden">{p.content}</div>
        </div>
      ))}
    </div>
  )
}

function outcomeColor(outcome: string): string {
  if (outcome === 'success') return '#22c55e'
  if (outcome === 'failure') return '#ef4444'
  if (outcome === 'partial') return '#f59e0b'
  return '#64748b'
}
