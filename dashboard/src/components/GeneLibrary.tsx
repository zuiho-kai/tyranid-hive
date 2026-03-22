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
      const ts = new Date().toISOString().slice(0, 10)
      a.href = url
      a.download = `hive-genes-${ts}.json`
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
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Sub-tabs + 工具栏 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 20px 0', borderBottom: '1px solid #1e2030' }}>
        <div style={{ display: 'flex', gap: 2 }}>
          {(['lessons', 'playbooks'] as Tab[]).map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: '5px 14px', border: 'none', borderRadius: '6px 6px 0 0', cursor: 'pointer', fontSize: 12,
              background: tab === t ? '#1e2030' : 'transparent',
              color: tab === t ? '#a78bfa' : '#64748b',
              borderBottom: tab === t ? '2px solid #7c3aed' : '2px solid transparent',
            }}>
              {t === 'lessons' ? '📚 经验教训' : '📖 作战手册'}
            </button>
          ))}
        </div>
        {/* 导出/导入按钮 */}
        <div style={{ display: 'flex', gap: 6, paddingBottom: 4 }}>
          <button
            onClick={doExport}
            disabled={exporting}
            title="导出全部基因为 JSON"
            style={{ padding: '4px 10px', background: '#1e2030', border: '1px solid #2d3148', borderRadius: 4, color: '#a78bfa', cursor: 'pointer', fontSize: 11 }}
          >
            {exporting ? '导出中…' : '↑ 导出'}
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            title="从 JSON 文件导入基因"
            style={{ padding: '4px 10px', background: '#1e2030', border: '1px solid #2d3148', borderRadius: 4, color: '#94a3b8', cursor: 'pointer', fontSize: 11 }}
          >
            {importing ? '导入中…' : '↓ 导入'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            style={{ display: 'none' }}
            onChange={e => { if (e.target.files?.[0]) doImport(e.target.files[0]) }}
          />
        </div>
      </div>

      {/* 导入结果消息 */}
      {importMsg && (
        <div style={{
          margin: '8px 20px 0',
          padding: '6px 12px',
          borderRadius: 4,
          fontSize: 12,
          background: importMsg.startsWith('✓') ? '#052e16' : '#2d0a0a',
          color: importMsg.startsWith('✓') ? '#22c55e' : '#ef4444',
          border: `1px solid ${importMsg.startsWith('✓') ? '#166534' : '#7f1d1d'}`,
        }}>
          {importMsg}
          <button onClick={() => setImportMsg(null)} style={{ float: 'right', background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 11 }}>✕</button>
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
        {loading ? (
          <div style={{ color: '#374151', fontSize: 13 }}>加载中…</div>
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
    return <div style={{ color: '#374151', fontSize: 13, textAlign: 'center', marginTop: 40 }}>暂无经验教训记录</div>
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {lessons.map(l => (
        <div key={l.id} style={{ background: '#13131a', borderRadius: 8, padding: '12px 16px', border: '1px solid #1e2030' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <div style={{ display: 'flex', gap: 6 }}>
              <span style={{ fontSize: 11, padding: '2px 8px', background: '#1e2030', borderRadius: 4, color: '#8b5cf6' }}>{l.domain}</span>
              <span style={{ fontSize: 11, padding: '2px 8px', background: outcomeColor(l.outcome) + '22', borderRadius: 4, color: outcomeColor(l.outcome) }}>{l.outcome}</span>
            </div>
            <span style={{ fontSize: 11, color: '#374151' }}>×{l.frequency}</span>
          </div>
          <div style={{ fontSize: 13, color: '#e2e8f0', lineHeight: 1.6, marginBottom: 6 }}>{l.content}</div>
          {l.tags && <div style={{ fontSize: 11, color: '#475569' }}>{l.tags}</div>}
        </div>
      ))}
    </div>
  )
}

function PlaybooksView({ playbooks }: { playbooks: Playbook[] }) {
  if (playbooks.length === 0) {
    return <div style={{ color: '#374151', fontSize: 13, textAlign: 'center', marginTop: 40 }}>暂无作战手册</div>
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {playbooks.map(p => (
        <div key={p.id} style={{ background: '#13131a', borderRadius: 8, padding: '12px 16px', border: `1px solid ${p.is_active ? '#2d3148' : '#1a1a24'}`, opacity: p.is_active ? 1 : 0.6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
            <div>
              <span style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0' }}>{p.title}</span>
              {p.crystallized && <span style={{ marginLeft: 6, fontSize: 10, color: '#06b6d4', border: '1px solid #06b6d4', borderRadius: 3, padding: '1px 5px' }}>晶化</span>}
            </div>
            <div style={{ display: 'flex', gap: 6, fontSize: 11, color: '#64748b' }}>
              <span>v{p.version}</span>
              <span>·</span>
              <span style={{ color: p.is_active ? '#22c55e' : '#374151' }}>{p.is_active ? '活跃' : '归档'}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, fontSize: 11, color: '#475569', marginBottom: 6 }}>
            <span>{p.domain}</span>
            <span>·</span>
            <span>使用 {p.use_count} 次</span>
            <span>·</span>
            <span>成功率 {Math.round(p.success_rate * 100)}%</span>
          </div>
          <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5, whiteSpace: 'pre-wrap', maxHeight: 80, overflow: 'hidden' }}>{p.content}</div>
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
