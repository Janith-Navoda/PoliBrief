import { useState, useEffect } from 'react'
import {
  HardDrive, Trash2, Clock, RefreshCw, Power,
  ShieldCheck, Database, FileText, Loader2, CheckCircle2
} from 'lucide-react'
import toast from 'react-hot-toast'
import { systemApi } from '../services/api'
import { formatPoliTimestamp } from '../utils/dateTime'

export default function SettingsPage() {
  const [stats, setStats] = useState(null)
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [cleaning, setCleaning] = useState(false)
  const [refreshingLogs, setRefreshingLogs] = useState(false)
  const [shutdownModalOpen, setShutdownModalOpen] = useState(false)
  const [shuttingDown, setShuttingDown] = useState(false)
  const [loadError, setLoadError] = useState('')

  const loadData = async () => {
    try {
      setLoadError('')
      setLoading(true)
      const [statsRes, logsRes] = await Promise.all([
        systemApi.storageStats(),
        systemApi.logs(15),
      ])
      setStats(statsRes.data)
      setLogs(logsRes.data)
    } catch (err) {
      setLoadError('Failed to load system settings and metrics.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleManualCleanup = async () => {
    try {
      setCleaning(true)
      const res = await systemApi.cleanup()
      const r = res.data.result
      toast.success(
        `Cleanup complete: ${r.articles_deleted} articles, ${r.fingerprints_deleted} fingerprints, ${r.logs_deleted} logs purged.`
      )
      loadData()
    } catch (err) {
      toast.error('Retention cleanup failed')
    } finally {
      setCleaning(false)
    }
  }

  const handleRefreshLogs = async () => {
    try {
      setRefreshingLogs(true)
      const res = await systemApi.logs(15)
      setLogs(res.data)
      toast.success('Scheduler logs refreshed')
    } catch (err) {
      toast.error('Failed to refresh logs')
    } finally {
      setRefreshingLogs(false)
    }
  }

  const handleShutdown = async () => {
    try {
      setShuttingDown(true)
      await systemApi.shutdown()
      toast.success('PoliBrief shutdown initiated. You can now close your browser tab.')
      setShutdownModalOpen(false)
    } catch (err) {
      toast.error('Shutdown request failed')
      setShuttingDown(false)
    }
  }

  const formatTimestamp = (isoString) => {
    return formatPoliTimestamp(isoString)
  }

  if (loading) {
    return (
      <div className="py-24 text-center text-[#767676]">
        <div className="spinner spinner-lg mx-auto mb-3" />
        <p className="text-xs font-semibold tracking-wider uppercase">Loading system configuration & storage metrics…</p>
      </div>
    )
  }

  return (
    <div className="space-y-10 sm:space-y-12">
      {loadError && <div className="alert alert-error" role="alert"><span className="flex-1">{loadError}</span><button type="button" className="underline font-semibold" onClick={loadData}>Retry</button></div>}
      {/* ── Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 sm:pb-8 border-b border-[#E5E5E5]">
        <div className="space-y-1 max-w-2xl">
          <span className="text-xs font-bold tracking-widest uppercase text-[#767676] block mb-1">
            System Operations
          </span>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-[#111111] uppercase leading-tight">
            System Settings & Retention
          </h1>
          <p className="text-xs sm:text-sm text-[#767676] leading-relaxed mt-1">
            Inspect local storage footprints, enforce 30-day retention policies, review background logs, and manage process lifecycles.
          </p>
        </div>

        {/* Exit Application Action */}
        <div className="shrink-0 self-start md:self-end">
          <button
            onClick={() => setShutdownModalOpen(true)}
            className="btn btn-secondary h-10 px-4 text-xs font-semibold text-[#B91C1C] hover:bg-[#FEE2E2] hover:border-[#FECACA] border-[#E5E5E5] inline-flex items-center gap-2 cursor-pointer transition-colors shadow-2xs"
            title="Gracefully exit PoliBrief application"
          >
            <Power size={13} />
            <span>Exit Application</span>
          </button>
        </div>
      </div>

      {/* ── Section 1: Storage Footprint & 30-Day Retention ── */}
      <section className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-[#F0F0F0]">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-[#111111] tracking-tight">
              Storage Footprint & 30-Day Retention
            </h2>
            <p className="text-xs sm:text-sm text-[#767676] mt-0.5">
              All data is stored locally in SQLite with strict automated retention enforcement.
            </p>
          </div>

          <button
            onClick={handleManualCleanup}
            disabled={cleaning}
            className="btn btn-primary h-10 px-4 text-xs font-semibold cursor-pointer inline-flex items-center gap-2 shadow-xs hover:shadow transition-colors shrink-0 self-start sm:self-auto"
            title="Execute retention policy now"
          >
            {cleaning ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
            <span>{cleaning ? 'Purging Expired Records…' : 'Run Retention Cleanup Now'}</span>
          </button>
        </div>

        {/* Four Evenly Sized Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
          {/* 1. SQLite Database */}
          <div className="card p-5 sm:p-6 bg-white border border-[#E5E5E5] rounded-2xl flex flex-col justify-between shadow-2xs">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#767676]">SQLite Database</span>
              <div className="w-8 h-8 rounded-lg bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#162238]">
                <Database size={15} />
              </div>
            </div>
            <div className="text-2xl sm:text-3xl font-black text-[#111111] tracking-tight mb-1">
              {stats?.database_size_mb ?? 0} MB
            </div>
            <p className="text-xs text-[#767676]">WAL mode & foreign keys</p>
          </div>

          {/* 2. Generated Images */}
          <div className="card p-5 sm:p-6 bg-white border border-[#E5E5E5] rounded-2xl flex flex-col justify-between shadow-2xs">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#767676]">Generated Images</span>
              <div className="w-8 h-8 rounded-lg bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#162238]">
                <FileText size={15} />
              </div>
            </div>
            <div className="text-2xl sm:text-3xl font-black text-[#111111] tracking-tight mb-1">
              {stats?.generated_images_size_mb ?? 0} MB
            </div>
            <p className="text-xs text-[#767676]">Branded 1080×1080 visual cards</p>
          </div>

          {/* 3. Application Logs */}
          <div className="card p-5 sm:p-6 bg-white border border-[#E5E5E5] rounded-2xl flex flex-col justify-between shadow-2xs">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#767676]">Application Logs</span>
              <div className="w-8 h-8 rounded-lg bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#162238]">
                <Clock size={15} />
              </div>
            </div>
            <div className="text-2xl sm:text-3xl font-black text-[#111111] tracking-tight mb-1">
              {stats?.logs_size_mb ?? 0} MB
            </div>
            <p className="text-xs text-[#767676]">30-day operational rolling log</p>
          </div>

          {/* 4. Total Managed Storage */}
          <div className="card p-5 sm:p-6 bg-[#F8F9FA] border border-[#E5E5E5] rounded-2xl flex flex-col justify-between shadow-2xs">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#162238]">Total Managed</span>
              <div className="w-8 h-8 rounded-lg bg-white border border-[#E5E5E5] flex items-center justify-center text-[#162238]">
                <HardDrive size={15} />
              </div>
            </div>
            <div className="text-2xl sm:text-3xl font-black text-[#162238] tracking-tight mb-1">
              {stats?.total_managed_mb ?? 0} MB
            </div>
            <p className="text-xs text-[#767676]">{stats?.articles_expiring_within_72h ?? 0} articles expiring soon</p>
          </div>
        </div>

        {/* ── Retention Safeguards Information Panel ── */}
        <div className="card p-6 sm:p-7 bg-white border border-[#E5E5E5] rounded-2xl shadow-2xs space-y-4">
          <div className="flex items-center gap-2.5 pb-3 border-b border-[#E5E5E5]">
            <div className="w-8 h-8 rounded-lg bg-[#DCFCE7] border border-[#BBF7D0] flex items-center justify-center text-[#15803D]">
              <ShieldCheck size={16} />
            </div>
            <div>
              <h3 className="text-sm sm:text-base font-bold text-[#111111] tracking-tight">
                Mandatory Retention Safeguards Enforced
              </h3>
              <p className="text-xs text-[#767676]">
                Automated background safeguards protecting ongoing editorial work and system integrity
              </p>
            </div>
          </div>

          <div className="divide-y divide-[#F0F0F0]">
            {/* Safeguard 1 */}
            <div className="py-3.5 flex items-start gap-3.5">
              <div className="w-7 h-7 rounded-lg bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#111111] shrink-0 mt-0.5">
                <Clock size={13} />
              </div>
              <div className="space-y-0.5 min-w-0 flex-1">
                <h4 className="text-xs sm:text-sm font-bold text-[#111111]">30-Day Article Lifetime</h4>
                <p className="text-xs text-[#666666] leading-relaxed">
                  Articles older than 30 days are reviewed during startup cleanup and daily cleanup. Items protected by active editorial work are retained.
                </p>
              </div>
            </div>

            {/* Safeguard 2 */}
            <div className="py-3.5 flex items-start gap-3.5">
              <div className="w-7 h-7 rounded-lg bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#15803D] shrink-0 mt-0.5">
                <CheckCircle2 size={13} />
              </div>
              <div className="space-y-0.5 min-w-0 flex-1">
                <h4 className="text-xs sm:text-sm font-bold text-[#111111]">Editorial Draft Protection</h4>
                <p className="text-xs text-[#666666] leading-relaxed">
                  Unresolved drafts are retained regardless of age and surfaced for administrator review. Their referenced articles and images remain protected.
                </p>
              </div>
            </div>

            {/* Safeguard 3 */}
            <div className="py-3.5 flex items-start gap-3.5">
              <div className="w-7 h-7 rounded-lg bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#C9A15A] shrink-0 mt-0.5">
                <ShieldCheck size={13} />
              </div>
              <div className="space-y-0.5 min-w-0 flex-1">
                <h4 className="text-xs sm:text-sm font-bold text-[#111111]">90-Day Duplicate Fingerprints</h4>
                <p className="text-xs text-[#666666] leading-relaxed">
                  Content fingerprints are retained for 90 days to prevent re-ingesting recycled wire stories and duplicate feeds.
                </p>
              </div>
            </div>

            {/* Safeguard 4 */}
            <div className="py-3.5 flex items-start gap-3.5">
              <div className="w-7 h-7 rounded-lg bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#162238] shrink-0 mt-0.5">
                <HardDrive size={13} />
              </div>
              <div className="space-y-0.5 min-w-0 flex-1">
                <h4 className="text-xs sm:text-sm font-bold text-[#111111]">Orphaned Image Cleanup</h4>
                <p className="text-xs text-[#666666] leading-relaxed">
                  Unreferenced temporary preview images older than 2 hours are safely swept and unlinked from the local media store.
                </p>
              </div>
            </div>

            {/* Safeguard 5 */}
            <div className="py-3.5 flex items-start gap-3.5">
              <div className="w-7 h-7 rounded-lg bg-[#F8F9FA] border border-[#E5E5E5] flex items-center justify-center text-[#111111] shrink-0 mt-0.5">
                <Database size={13} />
              </div>
              <div className="space-y-0.5 min-w-0 flex-1">
                <h4 className="text-xs sm:text-sm font-bold text-[#111111]">Database Maintenance & WAL Checkpoints</h4>
                <p className="text-xs text-[#666666] leading-relaxed">
                  Executes SQLite <code className="bg-[#F8F9FA] border border-[#E5E5E5] px-1.5 py-0.5 rounded text-[#111111] font-mono text-[11px]">PRAGMA optimize</code> and WAL checkpoints to maintain instantaneous queries and compact file sizes.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Section 2: Background Scheduler Execution Logs ── */}
      <section className="space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-[#F0F0F0]">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-[#111111] tracking-tight">
              Background Scheduler Execution Logs
            </h2>
            <p className="text-xs sm:text-sm text-[#767676] mt-0.5">
              Audit records of automated news collection and retention passes.
            </p>
          </div>

          <button
            onClick={handleRefreshLogs}
            disabled={refreshingLogs}
            className="btn btn-secondary h-10 px-4 text-xs font-semibold cursor-pointer inline-flex items-center gap-2 shadow-2xs hover:shadow-xs transition-colors shrink-0 self-start sm:self-auto"
            title="Refresh execution logs"
          >
            <RefreshCw size={13} className={refreshingLogs ? 'animate-spin' : ''} />
            <span>Refresh Logs</span>
          </button>
        </div>

        {/* Execution Logs Table Container */}
        <div className="card bg-white border border-[#E5E5E5] rounded-2xl overflow-hidden shadow-2xs">
          {logs.length === 0 ? (
            <div className="py-16 text-center text-xs text-[#767676]">
              <Clock size={24} className="mx-auto mb-2 text-[#999999]" />
              <p className="font-semibold">No background job runs recorded yet.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-[#E5E5E5] bg-[#F8F9FA] text-[#767676] uppercase tracking-wider text-[10px]">
                    <th className="py-3.5 px-5 font-bold w-48">Job Name</th>
                    <th className="py-3.5 px-5 font-bold w-48">Started At</th>
                    <th className="py-3.5 px-5 font-bold w-48">Finished At</th>
                    <th className="py-3.5 px-5 font-bold w-32">Status</th>
                    <th className="py-3.5 px-5 font-bold min-w-[200px]">Details / Errors</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E5E5]">
                  {logs.map(log => {
                    const isSuccess = log.status === 'SUCCESS'
                    const isRunning = log.status === 'RUNNING'
                    const isPartial = log.status === 'PARTIAL'
                    return (
                      <tr key={log.id} className="hover:bg-[#F8F9FA] transition-colors">
                        <td className="py-3.5 px-5 font-mono font-bold text-[#111111]">
                          {log.job_name}
                        </td>
                        <td className="py-3.5 px-5 text-[#767676]">
                          {formatTimestamp(log.started_at)}
                        </td>
                        <td className="py-3.5 px-5 text-[#767676]">
                          {formatTimestamp(log.finished_at)}
                        </td>
                        <td className="py-3.5 px-5">
                          <span className={`badge text-[10px] font-bold uppercase tracking-wider ${
                            isSuccess
                              ? 'badge-success'
                              : isRunning
                              ? 'badge-info'
                              : isPartial
                              ? 'badge-warning'
                              : 'badge-error'
                          }`}>
                            {log.status}
                          </span>
                        </td>
                        <td className="py-3.5 px-5 text-[#767676] max-w-sm truncate">
                          {log.error_message || 'Completed cleanly'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      {/* ── Shutdown Confirmation Modal ── */}
      {shutdownModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div role="dialog" aria-modal="true" aria-labelledby="shutdown-dialog-title" className="card w-full max-w-md p-6 sm:p-7 bg-white border border-[#E5E5E5] rounded-2xl shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-[#FEE2E2] flex items-center justify-center text-[#B91C1C] shrink-0">
                <Power size={20} />
              </div>
              <div>
                <h3 id="shutdown-dialog-title" className="text-base font-bold text-[#111111]">Stop PoliBrief Application</h3>
                <p className="text-xs text-[#767676]">Graceful shutdown of all local processes</p>
              </div>
            </div>

            <p className="text-xs text-[#555555] leading-relaxed">
              This will stop the in-process news collection scheduler, terminate the local FastAPI backend server, and cleanly release SQLite database locks. You can safely close your browser tab afterwards.
            </p>

            <div className="flex items-center justify-end gap-2.5 pt-4 border-t border-[#E5E5E5]">
              <button
                type="button"
                onClick={() => setShutdownModalOpen(false)}
                className="btn btn-secondary h-10 px-4 text-xs font-semibold cursor-pointer"
                disabled={shuttingDown}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleShutdown}
                disabled={shuttingDown}
                className="btn btn-danger h-10 px-4 text-xs font-semibold cursor-pointer inline-flex items-center gap-1.5 shadow-xs"
              >
                {shuttingDown && <Loader2 size={13} className="animate-spin" />}
                <span>Confirm Exit</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
