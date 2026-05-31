import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import './index.css'

// ─── Scenario metadata ────────────────────────────────────────────────────────
const SCENE = {
  red_light:  { code: 'RL-01', location: 'Traffic Signal · Urban India',    gps: '12.9716°N 77.5946°E', speedBase: 45 },
  helmet:     { code: 'CH-02', location: 'Anna Salai · Chennai, TN',        gps: '13.0827°N 80.2707°E', speedBase: 42 },
  general:    { code: 'GT-03', location: 'Urban Traffic Surveillance',       gps: '19.0760°N 72.8777°E', speedBase: 35 },
  wrong_side: { code: 'WS-04', location: 'NH-48 · Highway Segment',         gps: '28.6139°N 77.2090°E', speedBase: 65 },
}

const VTYPE_ICON  = { red_light: '🚦', helmet: '⛑️', general: '🎥', wrong_side: '↩️' }
const VTYPE_LABEL = { red_light: 'Red Light', helmet: 'Helmet', general: 'Traffic', wrong_side: 'Wrong-Side' }

// ─── Helpers ──────────────────────────────────────────────────────────────────
const M = ({ children, className = '' }) =>
  <span className={`font-mono ${className}`}>{children}</span>

const Label = ({ children, className = '' }) =>
  <div className={`text-[10px] font-semibold tracking-[0.16em] uppercase text-[#8ba3c4] ${className}`}>{children}</div>

function adaptRule(br) {
  const states = []
  if (br.fine_tn) states.push(['TN', br.fine_tn])
  if (br.fine_mh) states.push(['MH', br.fine_mh])
  if (br.fine_ka) states.push(['KA', br.fine_ka])
  return {
    title:        br.violation,
    section:      br.law,
    fineNational: br.fine_national,
    states,
    risk:         br.risk || '',
    msg:          br.msg,
    severity:     br.severity,
  }
}

// ─── Header ───────────────────────────────────────────────────────────────────
function Header({ activeVideo, status, frameCount, isConnected, device }) {
  const sc = SCENE[activeVideo?.vtype || 'general'] || SCENE.general
  const statusDot = isConnected ? '' : 'off'
  const statusColor = isConnected ? 'text-[#4ade80]' : 'text-[#8ba3c4]'

  return (
    <header className="flex items-center justify-between gap-4 flex-none px-1">
      {/* Brand */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-none"
            style={{ background: 'linear-gradient(135deg,#1e3a8a,#1d4ed8)', border: '1px solid rgba(59,130,246,0.4)' }}>
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#93c5fd" strokeWidth="1.7">
              <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/>
              <circle cx="12" cy="12" r="3" fill="#93c5fd"/>
              <path d="M12 4.5v2M12 17.5v2M4.5 12h2M17.5 12h2" strokeLinecap="round"/>
            </svg>
          </div>
          <div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-[20px] font-black tracking-tight text-white">SANJAYA</span>
              <span className="text-[20px] font-black tracking-tight text-[#60a5fa] glow-blue">EDGE</span>
            </div>
            <p className="text-[10px] text-[#8ba3c4] font-mono mt-0.5">AI Road Safety Co-Pilot · IIT Madras CoERS Hackathon 2026</p>
          </div>
        </div>

        {/* Device badge */}
        <div className="hidden lg:flex items-center gap-2 ml-2 pl-4 border-l border-[#1e2f4a]">
          <span className="badge badge-blue">{device === 'cuda' ? '⚡ GPU' : '🖥️ CPU'}</span>
          <span className="badge badge-indigo">YOLOv8n</span>
          <span className="badge badge-indigo">OpenCV HSV</span>
        </div>
      </div>

      {/* Right status */}
      <div className="flex items-center gap-3">
        <div className="hidden md:flex items-center gap-2 text-[10.5px] font-mono">
          <span className="text-[#3d5880]">NODE</span>
          <span className="text-[#8ba3c4]">{sc.code}</span>
          <span className="text-[#1e2f4a] mx-0.5">|</span>
          <span className="text-[#3d5880]">LOC</span>
          <span className="text-[#8ba3c4]">{sc.location}</span>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <span className={`dot-pulse ${statusDot}`} />
          <M className={`text-[11px] font-semibold ${statusColor}`}>{status}</M>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <Label className="!text-[#3d5880]">Frame</Label>
          <M className="text-[12px] font-bold text-[#eef2ff] num">{String(frameCount).padStart(6, '0')}</M>
        </div>
      </div>
    </header>
  )
}

// ─── Video selector ────────────────────────────────────────────────────────────
function VideoSelector({ videos, activeKey, onSelect, isConnected, onDisconnect }) {
  const grouped = useMemo(() => {
    const g = {}
    videos.forEach(v => { if (!g[v.vtype]) g[v.vtype] = []; g[v.vtype].push(v) })
    return g
  }, [videos])

  const typeOrder = ['red_light', 'helmet', 'general', 'wrong_side']
  const sorted = typeOrder.filter(t => grouped[t]).concat(Object.keys(grouped).filter(t => !typeOrder.includes(t)))

  function select(key) {
    if (isConnected) onDisconnect()
    onSelect(key)
  }

  if (videos.length <= 6) {
    return (
      <div className="flex items-center gap-2 flex-wrap">
        {videos.map(v => (
          <button key={v.key} onClick={() => select(v.key)}
            className={`text-[11px] font-mono font-medium px-3.5 py-1.5 rounded-lg border transition-all whitespace-nowrap
              ${activeKey === v.key
                ? 'text-[#93c5fd] glow-blue'
                : 'text-[#8ba3c4] hover:text-[#eef2ff]'
              }`}
            style={activeKey === v.key
              ? { background: 'rgba(59,130,246,0.15)', borderColor: 'rgba(59,130,246,0.5)' }
              : { background: 'var(--bg-surface)', borderColor: 'var(--border)' }
            }>
            {VTYPE_ICON[v.vtype] || '🎥'} {v.label}
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {sorted.map(vtype => (
        <div key={vtype} className="relative group">
          <button className={`text-[11px] font-mono font-medium px-3.5 py-1.5 rounded-lg border transition-all
            ${grouped[vtype]?.some(v => v.key === activeKey)
              ? 'text-[#93c5fd]'
              : 'text-[#8ba3c4] hover:text-[#eef2ff]'
            }`}
            style={grouped[vtype]?.some(v => v.key === activeKey)
              ? { background: 'rgba(59,130,246,0.15)', borderColor: 'rgba(59,130,246,0.5)' }
              : { background: 'var(--bg-surface)', borderColor: 'var(--border)' }
            }>
            {VTYPE_ICON[vtype] || '🎥'} {VTYPE_LABEL[vtype]} ({grouped[vtype]?.length})
          </button>
          <div className="absolute top-full left-0 mt-1 z-50 hidden group-hover:block min-w-[200px]">
            <div className="card p-1.5 space-y-0.5 shadow-2xl" style={{ borderColor: 'var(--border-mid)' }}>
              {grouped[vtype]?.map(v => (
                <button key={v.key} onClick={() => select(v.key)}
                  className={`w-full text-left text-[11px] font-mono px-3 py-1.5 rounded-lg transition-all
                    ${activeKey === v.key ? 'text-[#93c5fd]' : 'text-[#8ba3c4] hover:text-[#eef2ff] hover:bg-white/[0.04]'}`}
                  style={activeKey === v.key ? { background: 'rgba(59,130,246,0.15)' } : {}}>
                  {v.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── HUD overlay ──────────────────────────────────────────────────────────────
function HUD({ activeVideo, isConnected, alertFlash, elapsedSec, speedNow }) {
  const sc = SCENE[activeVideo?.vtype || 'general'] || SCENE.general
  const bktClass = alertFlash ? 'red' : isConnected ? '' : 'off'

  return (
    <div className="absolute inset-0 pointer-events-none select-none" style={{ zIndex: 3 }}>
      <span className={`bracket tl ${bktClass}`}/>
      <span className={`bracket tr ${bktClass}`}/>
      <span className={`bracket bl ${bktClass}`}/>
      <span className={`bracket br ${bktClass}`}/>

      {/* Centre crosshair */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="relative w-16 h-16 opacity-30">
          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-blue-400"/>
          <div className="absolute top-1/2 left-0 right-0 h-px bg-blue-400"/>
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full ring-1 ring-blue-400"/>
        </div>
      </div>

      {isConnected && <div className="scanline"/>}

      {/* Top row */}
      <div className="absolute top-3 left-4 right-4 flex justify-between items-start text-[10px] font-mono">
        <div className="space-y-0.5">
          {isConnected ? (
            <div className="flex items-center gap-1.5">
              <span className="rec-blink text-red-400">●</span>
              <span className="text-red-400 font-semibold">REC  LIVE  1080p</span>
            </div>
          ) : (
            <span className="text-[#3d5880]">○  STANDBY</span>
          )}
          <div className="text-[#8ba3c4]">{sc.location}</div>
          <div className="text-[#3d5880]">{sc.gps}</div>
        </div>
        <div className="text-right space-y-0.5">
          <div className="text-[#eef2ff]">T+ {elapsedSec.toFixed(2)}s</div>
          <div className="text-[#3d5880]">ENGINE: YOLOv8n · COCO</div>
          <div className="text-[#3d5880]">HSV: TRAFFIC LIGHT</div>
        </div>
      </div>

      {/* Bottom row */}
      <div className="absolute bottom-3 left-4 right-4 flex justify-between items-end text-[10px] font-mono">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="text-[#3d5880]">SPD</span>
            <span className="text-white text-[14px] font-bold num">{speedNow}</span>
            <span className="text-[#3d5880]">km/h</span>
          </div>
          <div className="text-[#3d5880]">NODE {sc.code}  ·  ALT 14m</div>
        </div>
        <div className="text-right space-y-0.5">
          <div className="text-[#3d5880]">OPTICAL FLOW: LK</div>
          <div className="text-[#3d5880]">LAW: MVA 1988 · IPC 283</div>
        </div>
      </div>

      {/* Alert flash overlay */}
      {alertFlash && (
        <div className="absolute inset-0 pointer-events-none"
          style={{ background: 'rgba(239,68,68,0.07)', boxShadow: 'inset 0 0 60px rgba(239,68,68,0.15)' }}/>
      )}
    </div>
  )
}

// ─── Feed header bar ──────────────────────────────────────────────────────────
function FeedBar({ activeVideo, isConnected, frameCount }) {
  const sc = SCENE[activeVideo?.vtype || 'general'] || SCENE.general
  return (
    <div className="flex items-center justify-between px-4 py-2 border-b flex-none"
      style={{ borderColor: 'var(--border)', background: 'rgba(8,13,24,0.7)' }}>
      <div className="flex items-center gap-3 text-[11px] font-mono">
        {isConnected ? (
          <span className="flex items-center gap-1.5 font-semibold text-red-400">
            <span className="rec-blink">●</span> REC
          </span>
        ) : (
          <span className="text-[#3d5880]">○ STBY</span>
        )}
        <span className="text-[#1e2f4a]">|</span>
        <span className="text-[#8ba3c4]">EDGE-CAM</span>
        <span className="text-[#3d5880]">//</span>
        <span className="text-[#93c5fd]">{sc.code}</span>
        <span className="text-[#1e2f4a]">|</span>
        <span className="text-[#8ba3c4]">{activeVideo?.label || '—'}</span>
      </div>
      <div className="flex items-center gap-3 text-[10.5px] font-mono text-[#3d5880]">
        <span>{sc.location}</span>
        <span className="text-[#1e2f4a]">|</span>
        <span>F <span className="text-[#8ba3c4]">{String(frameCount).padStart(5, '0')}</span></span>
      </div>
    </div>
  )
}

// ─── Stat pill ────────────────────────────────────────────────────────────────
function StatPill({ label, value, sub, tone = 'default' }) {
  const valueColor = {
    default: 'text-[#eef2ff]',
    blue:    'text-[#60a5fa] glow-blue',
    red:     'text-[#f87171] glow-red',
    amber:   'text-[#fbbf24] glow-amber',
    green:   'text-[#4ade80] glow-green',
  }[tone]

  return (
    <div className="card px-4 py-3 flex flex-col gap-0.5 min-w-0" style={{ borderColor: 'var(--border)' }}>
      <Label>{label}</Label>
      <div className={`font-mono text-[22px] font-bold num leading-none ${valueColor}`}>{value}</div>
      {sub && <div className="text-[10px] text-[#3d5880] font-mono mt-0.5">{sub}</div>}
    </div>
  )
}

// ─── Violation event card ─────────────────────────────────────────────────────
function EventCard({ evt, idx }) {
  const r   = evt.rule
  const sev = r.severity

  const isSafe = sev === 'SAFE'
  const isCrit = sev === 'CRITICAL'
  const isHigh = sev === 'HIGH'

  const sevClass = isSafe ? 'sev-safe' : isCrit ? 'sev-critical' : 'sev-high'
  const headerColor = isSafe ? 'text-[#4ade80]' : isCrit ? 'text-[#f87171]' : 'text-[#fbbf24]'
  const headerLabel = isSafe ? 'COMPLIANCE — SAFE' : isCrit ? 'CRITICAL VIOLATION' : 'VIOLATION DETECTED'
  const dotClass    = isSafe ? '' : isCrit ? 'red' : 'amber'
  const badgeClass  = isSafe ? 'badge-green' : isCrit ? 'badge-red' : 'badge-amber'

  return (
    <article className={`rise-in rounded-xl overflow-hidden border border-transparent ${sevClass}`}>
      <div className="p-3.5 space-y-2">
        {/* Row 1: severity label + confidence */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className={`dot-pulse ${dotClass}`}/>
            <span className={`text-[10px] font-bold tracking-[0.15em] uppercase ${headerColor}`}>
              {headerLabel}
            </span>
          </div>
          {!isSafe && (
            <span className="text-[10.5px] font-mono text-[#8ba3c4]">
              CONF <span className="text-[#eef2ff] font-semibold">{evt.confidence}%</span>
            </span>
          )}
        </div>

        {/* Row 2: violation title + law */}
        <div>
          <h3 className="text-[14px] font-bold text-[#eef2ff] leading-tight">{r.title}</h3>
          <p className="text-[11px] font-mono text-[#8ba3c4] mt-0.5">{r.section}</p>
        </div>

        {/* Row 3: risk quote */}
        {!isSafe && r.risk && (
          <p className="text-[11px] italic text-[#94a3b8] leading-snug border-l-2 border-[#1e2f4a] pl-2">
            {r.risk}
          </p>
        )}

        {/* Row 4: message */}
        <p className="text-[11px] text-[#8ba3c4] leading-snug">{r.msg}</p>

        {/* Row 5: fines */}
        {!isSafe ? (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className={`badge ${badgeClass} font-semibold`}>{r.fineNational}</span>
            {r.states?.map(([s, v]) => (
              <span key={s} className="badge badge-indigo">{s}: {v}</span>
            ))}
          </div>
        ) : (
          <span className="badge badge-green">Status: Compliant</span>
        )}

        {/* Row 6: meta footer */}
        <div className="flex items-center justify-between pt-1.5 border-t border-[#1e2f4a]">
          <M className="text-[10px] text-[#3d5880]">EVT #{String(idx + 1).padStart(3, '0')} · Frame {String(evt.frame).padStart(5, '0')}</M>
          <M className="text-[10px] text-[#3d5880]">{evt.time}</M>
        </div>
      </div>
    </article>
  )
}

// ─── Empty state ──────────────────────────────────────────────────────────────
function EmptyState() {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center px-6 gap-4 py-10">
      <svg viewBox="0 0 64 64" width="52" height="52" fill="none" stroke="#3b82f6" strokeWidth="1.4" className="opacity-50">
        <path d="M32 6l22 8v14c0 14-10 26-22 30C20 54 10 42 10 28V14l22-8z"/>
        <path d="M22 30l8 8 14-16" strokeWidth="2.2"/>
      </svg>
      <div className="space-y-1.5">
        <p className="text-[13px] font-semibold text-[#8ba3c4]">Awaiting compliance events…</p>
        <p className="text-[11px] text-[#3d5880] max-w-[220px]">
          Red light jumps, helmet violations, wrong-side driving, traffic blocking, and pedestrian hazards will appear here.
        </p>
      </div>
    </div>
  )
}

// ─── Event log panel ──────────────────────────────────────────────────────────
function EventLog({ events, onClear }) {
  const logEndRef = useRef(null)
  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [events])

  const violations = events.filter(e => e.rule.severity !== 'SAFE').length
  const safe       = events.length - violations

  return (
    <aside className="card flex flex-col overflow-hidden h-full" style={{ borderColor: 'var(--border)' }}>
      {/* Panel header */}
      <header className="px-4 py-3 border-b flex items-center justify-between flex-none"
        style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2.5">
          <span className="dot-pulse amber"/>
          <h2 className="text-[11.5px] font-bold tracking-[0.16em] uppercase text-[#eef2ff]">
            Compliance Event Log
          </h2>
        </div>
        {events.length > 0 && (
          <button onClick={onClear}
            className="text-[10.5px] font-mono text-[#3d5880] hover:text-[#8ba3c4] transition-colors">
            Clear
          </button>
        )}
      </header>

      {/* Summary strip */}
      <div className="px-4 py-2 border-b flex items-center justify-between flex-none"
        style={{ borderColor: 'var(--border)', background: 'rgba(8,13,24,0.4)' }}>
        <M className="text-[10px] text-[#3d5880]">MVA 1988 · IPC 283 · State Traffic Rules</M>
        <M className="text-[10px]">
          <span className="text-[#f87171] font-semibold">{violations}</span>
          <span className="text-[#3d5880]"> violations · </span>
          <span className="text-[#4ade80] font-semibold">{safe}</span>
          <span className="text-[#3d5880]"> safe</span>
        </M>
      </div>

      {/* Detector legend */}
      <div className="px-4 py-2 border-b flex-none" style={{ borderColor: 'var(--border)' }}>
        <div className="flex flex-wrap gap-1.5">
          {[
            ['🚦 Red Light',    'badge-red'],
            ['⛑ Helmet',        'badge-amber'],
            ['↩ Wrong-Side',    'badge-red'],
            ['🚧 Blocking',     'badge-amber'],
            ['🚶 Pedestrian',   'badge-amber'],
          ].map(([label, cls]) => (
            <span key={label} className={`badge ${cls} text-[9.5px]`}>{label}</span>
          ))}
        </div>
      </div>

      {/* Cards */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-0">
        {events.length === 0 ? <EmptyState /> : (
          events.slice().reverse().map((e, i) => (
            <EventCard key={e.id} evt={e} idx={events.length - 1 - i}/>
          ))
        )}
        <div ref={logEndRef}/>
      </div>

      {/* Voice copilot footer */}
      <footer className="px-4 py-2.5 border-t flex items-center justify-between flex-none"
        style={{ borderColor: 'var(--border)', background: 'rgba(8,13,24,0.6)' }}>
        <M className="text-[10px] text-[#3d5880]">VOICE COPILOT · en-IN</M>
        <div className="flex items-center gap-1.5">
          <span className="dot-pulse blue"/>
          <M className="text-[10px] text-[#60a5fa]">ARMED</M>
        </div>
      </footer>
    </aside>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [videos,      setVideos]      = useState([])
  const [activeKey,   setActiveKey]   = useState('red_light')
  const [alerts,      setAlerts]      = useState([])
  const [isConnected, setIsConnected] = useState(false)
  const [liveFrame,   setLiveFrame]   = useState(null)
  const [frameCount,  setFrameCount]  = useState(0)
  const [status,      setStatus]      = useState('STANDBY')
  const [critCount,   setCritCount]   = useState(0)
  const [alertFlash,  setAlertFlash]  = useState(false)
  const [elapsedSec,  setElapsedSec]  = useState(0)
  const [device,      setDevice]      = useState('cpu')

  const wsRef      = useRef(null)
  const speechQ    = useRef([])
  const speaking   = useRef(false)
  const startTsRef = useRef(null)
  const rafRef     = useRef(null)
  const speakNextRef = useRef(null)

  const activeVideo = videos.find(v => v.key === activeKey) || null
  const sc          = SCENE[activeVideo?.vtype || 'general'] || SCENE.general

  // Fetch video list + device info
  useEffect(() => {
    fetch('http://localhost:8000/api/videos')
      .then(r => r.json())
      .then(list => {
        setVideos(list)
        if (list.length > 0 && !list.find(v => v.key === activeKey))
          setActiveKey(list[0].key)
      })
      .catch(() => {
        setVideos([
          { key: 'red_light',       label: 'Red Light — Clear', vtype: 'red_light', filename: 'red_light_clear.mp4' },
          { key: 'red_light_india', label: 'Red Light — India', vtype: 'red_light', filename: 'red_light_india.webm' },
          { key: 'no_helmet',       label: 'Helmet Violation',  vtype: 'helmet',    filename: 'no_helmet.webm' },
        ])
      })

    fetch('http://localhost:8000/health')
      .then(r => r.json())
      .then(h => { if (h.device) setDevice(h.device) })
      .catch(() => {})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Elapsed timer
  useEffect(() => {
    if (!isConnected) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      setElapsedSec(0); return
    }
    startTsRef.current = performance.now()
    const tick = () => {
      setElapsedSec((performance.now() - startTsRef.current) / 1000)
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [isConnected])

  const speakNext = useCallback(() => {
    if (speaking.current || speechQ.current.length === 0) return
    speaking.current = true
    const utt = new SpeechSynthesisUtterance(speechQ.current.shift())
    utt.rate = 0.88; utt.pitch = 1.0; utt.lang = 'en-IN'
    utt.onend = () => { speaking.current = false; speakNextRef.current?.() }
    window.speechSynthesis.speak(utt)
  }, [])
  useEffect(() => { speakNextRef.current = speakNext }, [speakNext])

  const queueSpeech = useCallback((text) => {
    speechQ.current.push(text)
    speakNextRef.current?.()
  }, [])

  const disconnect = useCallback(() => {
    wsRef.current?.close()
    window.speechSynthesis.cancel()
    speechQ.current = []; speaking.current = false
    setStatus('STANDBY'); setIsConnected(false); setLiveFrame(null)
  }, [])

  const connect = useCallback(() => {
    if (wsRef.current) wsRef.current.close()
    setAlerts([]); setLiveFrame(null); setFrameCount(0)
    setCritCount(0); setAlertFlash(false); setStatus('CONNECTING…')
    window.speechSynthesis.cancel()
    speechQ.current = []; speaking.current = false

    const ws = new WebSocket(`ws://localhost:8000/ws/stream/${activeKey}`)
    wsRef.current = ws

    ws.onopen  = () => { setIsConnected(true);  setStatus('ACTIVE SCANNING') }
    ws.onclose = () => { setIsConnected(false); setStatus('STOPPED') }
    ws.onerror = () => { setIsConnected(false); setStatus('ERROR — Backend offline?') }

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)

      if (msg.type === 'FRAME') {
        setLiveFrame(`data:image/jpeg;base64,${msg.data}`)
        setFrameCount(msg.frame)
        return
      }

      if (msg.type === 'ALERT') {
        const evt = {
          id:         `${msg.frame}-${Date.now()}`,
          confidence: msg.confidence,
          frame:      msg.frame,
          time:       new Date().toLocaleTimeString('en-IN', { hour12: false }),
          rule:       adaptRule(msg.rule),
        }
        setAlerts(prev => [...prev, evt])
        if (msg.rule.severity === 'CRITICAL') {
          setCritCount(c => c + 1)
          setAlertFlash(true)
          setTimeout(() => setAlertFlash(false), 800)
        } else if (msg.rule.severity === 'HIGH') {
          setAlertFlash(true)
          setTimeout(() => setAlertFlash(false), 500)
        }
        queueSpeech(`Warning. ${msg.rule.violation}. Fine: ${msg.rule.fine_national}.`)
      }

      if (msg.type === 'ERROR') setStatus(`ERROR: ${msg.msg}`)
    }
  }, [activeKey, queueSpeech])

  useEffect(() => () => wsRef.current?.close(), [])

  const stats = useMemo(() => {
    const violations = alerts.filter(a => a.rule.severity !== 'SAFE')
    const critical   = alerts.filter(a => a.rule.severity === 'CRITICAL').length
    const high       = alerts.filter(a => a.rule.severity === 'HIGH').length
    const conf       = violations.length
      ? Math.round(violations.reduce((s, a) => s + a.confidence, 0) / violations.length) : 0
    const fineTotal  = violations.reduce((sum, a) => {
      return sum + (parseInt((a.rule.fineNational || '0').replace(/[^\d]/g, '')) || 0)
    }, 0)
    return { total: alerts.length, critical, high, conf, fineTotal }
  }, [alerts])

  const speedNow = Math.max(0, sc.speedBase + Math.round(Math.sin(elapsedSec * 1.7) * 6))

  return (
    <div className={`h-screen w-screen flex flex-col overflow-hidden relative z-10 p-4 gap-3 transition-colors duration-200 ${alertFlash && critCount > 0 ? 'flash-red' : ''}`}>

      <Header
        activeVideo={activeVideo}
        status={status}
        frameCount={frameCount}
        isConnected={isConnected}
        device={device}
      />

      {/* Controls row */}
      <div className="flex items-center justify-between gap-4 flex-none flex-wrap">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <Label className="mr-1 flex-none">Scenario</Label>
          <VideoSelector
            videos={videos}
            activeKey={activeKey}
            onSelect={setActiveKey}
            isConnected={isConnected}
            onDisconnect={disconnect}
          />
        </div>

        <div className="flex items-center gap-3 flex-none">
          <M className="text-[10px] text-[#3d5880]">{videos.length} scenario{videos.length !== 1 ? 's' : ''} loaded</M>
          {!isConnected ? (
            <button onClick={connect}
              className="font-mono text-[12px] font-bold tracking-wide px-5 py-2 rounded-lg transition-all text-white"
              style={{ background: 'linear-gradient(135deg,#1d4ed8,#2563eb)', border: '1px solid rgba(59,130,246,0.5)', boxShadow: '0 0 24px rgba(59,130,246,0.35)' }}>
              ▶ START SCAN
            </button>
          ) : (
            <button onClick={disconnect}
              className="font-mono text-[12px] font-bold tracking-wide px-5 py-2 rounded-lg transition-all text-[#f87171]"
              style={{ background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.35)' }}>
              ■ STOP SCAN
            </button>
          )}
        </div>
      </div>

      {/* Main grid */}
      <main className="flex-1 grid grid-cols-3 gap-3 min-h-0">

        {/* Feed — 2 cols */}
        <section className="col-span-2 flex flex-col gap-3 min-h-0">

          {/* Video feed card */}
          <div className="card flex flex-col overflow-hidden flex-1 min-h-0" style={{ borderColor: 'var(--border)' }}>
            <FeedBar activeVideo={activeVideo} isConnected={isConnected} frameCount={frameCount}/>

            <div className="relative flex-1 overflow-hidden vignette flex items-center justify-center bg-black min-h-0">
              {liveFrame ? (
                <img
                  src={liveFrame}
                  alt="AI annotated live feed"
                  className="max-w-full max-h-full object-contain relative"
                  style={{ zIndex: 1 }}
                />
              ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-4" style={{ zIndex: 1 }}>
                  <div className="text-6xl opacity-15">📷</div>
                  <div className="text-center space-y-2">
                    <p className="text-[13px] font-semibold text-[#8ba3c4]">
                      {activeVideo ? `${VTYPE_ICON[activeVideo.vtype] || '🎥'} ${activeVideo.label}` : 'Select a scenario'}
                    </p>
                    <p className="text-[11px] font-mono text-[#3d5880]">Press START SCAN to begin</p>
                    <p className="text-[10px] font-mono text-[#1e2f4a]">ws://localhost:8000/ws/stream/{activeKey}</p>
                  </div>
                </div>
              )}

              <HUD
                activeVideo={activeVideo}
                isConnected={isConnected}
                alertFlash={alertFlash}
                elapsedSec={elapsedSec}
                speedNow={speedNow}
              />
            </div>
          </div>

          {/* Stats strip */}
          <div className="grid grid-cols-5 gap-2 flex-none">
            <StatPill label="Total Events"  value={String(stats.total).padStart(2,'0')}    sub="This run"          tone="blue"  />
            <StatPill label="Critical"       value={String(stats.critical).padStart(2,'0')} sub="Red · Blocking"    tone="red"   />
            <StatPill label="High Risk"      value={String(stats.high).padStart(2,'0')}     sub="Helmet · Ped."     tone="amber" />
            <StatPill label="Avg Confidence" value={`${stats.conf}%`}                       sub="YOLOv8n detect."   tone="green" />
            <StatPill label="Fine Exposure"  value={`₹${stats.fineTotal.toLocaleString('en-IN')}`} sub="Cumulative est." tone="amber" />
          </div>
        </section>

        {/* Event log — 1 col */}
        <section className="col-span-1 min-h-0 flex flex-col">
          <EventLog events={alerts} onClear={() => setAlerts([])}/>
        </section>
      </main>
    </div>
  )
}
