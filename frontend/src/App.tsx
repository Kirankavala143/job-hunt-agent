import { useState, useRef, useEffect, useMemo } from 'react'
import JobCard from './JobCard'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const SESSION_ID_KEY = 'job_hunt_session_id'

function getSessionId(): string {
  let sessionId = sessionStorage.getItem(SESSION_ID_KEY)

  if (!sessionId) {
    sessionId = crypto.randomUUID()
    sessionStorage.setItem(SESSION_ID_KEY, sessionId)
  }

  return sessionId
}

interface Job {
  title: string
  company: string
  location: string
  url: string
  description: string
  source: string
  ats_score?: number
  semantic_score?: number
  combined_score?: number
  matched_skills?: string[]
}

interface Message {
  role: 'user' | 'agent'
  content: string
  jobs?: Job[]
  raw_jobs?: Job[]
}

type SortKey = 'combined_score' | 'ats_score' | 'semantic_score'

function ScoreSlider({
  label, value, onChange, color
}: { label: string; value: number; onChange: (v: number) => void; color: string }) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-slate-400">{label} ≥</span>
        <span className={`font-bold ${color}`}>{value}%</span>
      </div>
      <input
        type="range" min={0} max={100} step={5} value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full appearance-none cursor-pointer accent-blue-500 bg-slate-700"
      />
    </div>
  )
}

function SourceChip({ label, active, count, onClick }: {
  label: string; active: boolean; count: number; onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`text-xs px-2.5 py-1 rounded-full border transition-all ${
        active
          ? 'bg-blue-600 border-blue-500 text-white'
          : 'bg-slate-800 border-slate-600 text-slate-400 hover:border-slate-500'
      }`}
    >
      {label} <span className="opacity-70">({count})</span>
    </button>
  )
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([{
    role: 'agent',
    content: "👋 Hello! I'm your **AI Job Hunt Agent**.\n\nUpload your resume, then ask me to find you jobs. Every result will be **scored against your resume** with both an ATS score and a Semantic match score — so you always see the best fits first."
  }])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [resumeName, setResumeName] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Filter/sort state (applied to the latest agent message with jobs)
  const [atsThreshold, setAtsThreshold] = useState(0)
  const [semanticThreshold, setSemanticThreshold] = useState(0)
  const [sortKey, setSortKey] = useState<SortKey>('combined_score')
  const [activeSource, setActiveSource] = useState<string | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Get the latest job-bearing message
  const latestJobMsg = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].jobs && messages[i].jobs!.length > 0) return messages[i]
    }
    return null
  }, [messages])

  // All unique sources from latest jobs
  const allSources = useMemo(() => {
    if (!latestJobMsg?.jobs) return []
    const counts: Record<string, number> = {}
    for (const j of latestJobMsg.jobs) {
      const src = j.source || 'Unknown'
      counts[src] = (counts[src] || 0) + 1
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1])
  }, [latestJobMsg])

  // Filtered + sorted jobs
  const filteredJobs = useMemo(() => {
    if (!latestJobMsg?.jobs) return []
    return latestJobMsg.jobs
      .filter(j => (j.ats_score ?? 0) >= atsThreshold)
      .filter(j => (j.semantic_score ?? 0) >= semanticThreshold)
      .filter(j => activeSource ? j.source === activeSource : true)
      .sort((a, b) => (b[sortKey] ?? 0) - (a[sortKey] ?? 0))
  }, [latestJobMsg, atsThreshold, semanticThreshold, sortKey, activeSource])

  const handleSend = async () => {
    if (!input.trim()) return
    const userMsg: Message = { role: 'user', content: input }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsLoading(true)
    // Reset filters for new search
    setAtsThreshold(0)
    setSemanticThreshold(0)
    setActiveSource(null)
    setSortKey('combined_score')

    try {
      const res = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': getSessionId()
        },
        body: JSON.stringify({ message: userMsg.content })
      })
      const data = await res.json()
      setMessages(prev => [...prev, {
        role: 'agent',
        content: data.reply || 'No response from agent.',
        jobs: data.jobs || [],
        raw_jobs: data.raw_jobs || []
      }])
    } catch (err: any) {
      setMessages(prev => [...prev, {
        role: 'agent',
        content: `Error communicating with backend: ${err.message}`
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.type !== 'application/pdf') { alert('Please upload a PDF.'); return }
    setIsUploading(true)
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await fetch(`${API_BASE_URL}/api/upload_resume`, {
      method: 'POST',
      headers: {
        'X-Session-ID': getSessionId()
      },
      body: form
    })
      const data = await res.json()
      if (res.ok) {
        setResumeName(file.name)
        setMessages(prev => [...prev, {
          role: 'agent',
          content: `✅ Resume **${file.name}** parsed successfully (${data.text_length} chars). I'll use it to score every job against your profile.`
        }])
      } else {
        alert(`Upload failed: ${data.detail || 'Unknown error'}`)
      }
    } catch {
      alert('Error connecting to backend.')
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }



  return (
    <div className="flex h-screen bg-slate-950 text-slate-50 font-sans overflow-hidden">

      {/* ── Sidebar ─────────────────────────────────────────── */}
      <aside className="w-72 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col hidden md:flex">
        <div className="p-5 border-b border-slate-800">
          <h1 className="text-xl font-black bg-gradient-to-r from-blue-400 via-indigo-400 to-emerald-400 bg-clip-text text-transparent">
            JobHunt AI
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">Resume-powered job discovery</p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* Resume Upload */}
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">Resume</p>
            <input type="file" accept="application/pdf" className="hidden" ref={fileInputRef} onChange={handleFileUpload} />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className={`w-full flex items-center gap-2 p-3 rounded-xl border text-sm transition-all ${
                resumeName
                  ? 'bg-emerald-900/30 border-emerald-700/50 text-emerald-300'
                  : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600'
              } disabled:opacity-50`}
            >
              <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span className="truncate">{isUploading ? 'Uploading…' : resumeName || 'Upload Resume (PDF)'}</span>
            </button>
          </div>

          {/* Score Filters — only show when jobs are loaded */}
          {latestJobMsg && latestJobMsg.jobs && latestJobMsg.jobs.length > 0 && (
            <>
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">Score Filters</p>
                <div className="space-y-4">
                  <ScoreSlider label="ATS Score" value={atsThreshold} onChange={setAtsThreshold} color="text-violet-400" />
                  <ScoreSlider label="Semantic Score" value={semanticThreshold} onChange={setSemanticThreshold} color="text-cyan-400" />
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">Sort By</p>
                <select
                  value={sortKey}
                  onChange={e => setSortKey(e.target.value as SortKey)}
                  className="w-full bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-2"
                >
                  <option value="combined_score">Combined Score</option>
                  <option value="ats_score">ATS Score</option>
                  <option value="semantic_score">Semantic Score</option>
                </select>
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">Source</p>
                <div className="flex flex-wrap gap-1.5">
                  <SourceChip label="All" active={!activeSource} count={latestJobMsg.jobs.length} onClick={() => setActiveSource(null)} />
                  {allSources.map(([src, count]) => (
                    <SourceChip key={src} label={src} active={activeSource === src} count={count} onClick={() => setActiveSource(activeSource === src ? null : src)} />
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </aside>

      {/* ── Main Area ────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col overflow-hidden">
      
        {/* Chat messages */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-5">
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div className={`max-w-2xl rounded-2xl px-5 py-3.5 ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800/80 text-slate-200 border border-slate-700/60 shadow'
              }`}>
                {msg.role === 'user' ? (
                  <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                ) : (
                  <div className="prose prose-invert prose-sm max-w-none prose-p:leading-relaxed prose-a:text-blue-400 prose-strong:text-slate-100">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex items-start">
              <div className="bg-slate-800/80 border border-slate-700/60 rounded-2xl px-5 py-3.5 flex items-center gap-2">
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" />
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce delay-100" />
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce delay-200" />
                <span className="text-xs text-slate-400 ml-1">Scraping & scoring jobs…</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* ── Job Results Panel ──────────────────────────────── */}
        {latestJobMsg && latestJobMsg.jobs && latestJobMsg.jobs.length > 0 && (
          <div className="border-t border-slate-800 bg-slate-950 flex flex-col" style={{ maxHeight: '60vh' }}>
            {/* Results bar */}
            <div className="flex items-center justify-between px-5 py-2.5 border-b border-slate-800 bg-slate-900/60">
              <div className="flex items-center gap-3 text-sm">
                <span className="font-bold text-white">{filteredJobs.length}</span>
                <span className="text-slate-400">jobs</span>
                {(atsThreshold > 0 || semanticThreshold > 0 || activeSource) && (
                  <>
                    <span className="w-px h-4 bg-slate-700" />
                    <button
                      onClick={() => { setAtsThreshold(0); setSemanticThreshold(0); setActiveSource(null) }}
                      className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      Clear filters ×
                    </button>
                  </>
                )}
              </div>
              <span className="text-xs text-slate-500">
                Sorted by {sortKey.replace('_', ' ').replace('score', '').trim()} score ↓
              </span>
            </div>

            {/* Job cards grid */}
            <div className="overflow-y-auto p-4">
              {filteredJobs.length === 0 ? (
                <div className="text-center text-slate-500 py-8 text-sm">
                  No jobs match your current filters. Try lowering the score thresholds.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {filteredJobs.map((job, idx) => (
                    <JobCard key={idx} job={job} rank={idx + 1} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Input ─────────────────────────────────────────── */}
        <div className="p-4 bg-slate-900 border-t border-slate-800">
          <div className="max-w-3xl mx-auto flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              placeholder="e.g. Find remote ML internships in India…"
              className="flex-1 bg-slate-800 border border-slate-700 text-slate-200 rounded-full pl-5 pr-4 py-3 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
            />
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="p-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded-full transition-colors shrink-0"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}
