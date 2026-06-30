import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
  Activity, AlertCircle, AlertTriangle, ArrowRight, Bot, Check,
  CheckCircle2, Copy, Cpu, Database, FileSearch, Globe,
  RefreshCw, Search, Shuffle, TrendingDown, TrendingUp, X, Zap,
} from 'lucide-react';
import './dashboard-v2.css';
import { fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { RouteLink } from '../shared/ui';
import { routeId } from '../routeShell';

const API_BASE = '/api';

function db2JobStatusInfo(status) {
  if (status === 'Completed') return { cls: 'done',    Icon: CheckCircle2, label: 'Hoàn thành' };
  if (status === 'Failed')    return { cls: 'error',   Icon: X,            label: 'Thất bại'   };
  if (status === 'Pending')   return { cls: 'pending', Icon: AlertCircle,  label: 'Đang chờ'   };
  return                             { cls: 'running', Icon: RefreshCw,    label: status || '—' };
}

function db2StatusBadge(status) {
  const { cls, Icon, label } = db2JobStatusInfo(status);
  return (
    <span className={`db2-status-badge ${cls}`}>
      <Icon size={9} className={cls === 'running' ? 'spin-slow' : ''} />
      {label}
    </span>
  );
}

function Db2ResourceBar({ label, value, color }) {
  return (
    <div className="db2-resource-row">
      <div className="db2-resource-label"><span>{label}</span><span>{value}%</span></div>
      <div className="db2-resource-bar">
        <div className="db2-resource-fill" style={{ width: `${value}%`, background: color }} />
      </div>
    </div>
  );
}

function throughputBars(count = 24) {
  const seed = [42,61,38,55,70,48,80,65,52,88,74,60,45,91,78,62,56,83,69,50,75,87,64,72];
  return seed.slice(0, count);
}

const PIPELINE_STAGES_DEF = [
  { id: 'crawl',   label: 'Thu thập',  Icon: Globe      },
  { id: 'extract', label: 'Trích xuất', Icon: FileSearch },
  { id: 'ai',      label: 'AI Review', Icon: Bot        },
  { id: 'dedup',   label: 'Dedup',     Icon: Copy       },
  { id: 'store',   label: 'Lưu trữ',  Icon: Database   },
];

export default function DashboardPage({ navigate }) {
  const [activeTab,    setActiveTab]    = useState('jobs');
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQ,      setSearchQ]      = useState('');
  const [selectedSrc,  setSelectedSrc]  = useState(null);
  const [countdown,    setCountdown]    = useState(30);
  const [autoRefresh,  setAutoRefresh]  = useState(true);
  const [dismissedIds, setDismissedIds] = useState(new Set());
  const [reviewBusy,   setReviewBusy]   = useState(new Set());
  const [notice,       setNotice]       = useState(null);

  const [resource, reload] = useApiResource(async () => {
    const [statsRes, sources, jobs, aiItems, dedupItems] = await Promise.all([
      axios.get(`${API_BASE}/dashboard/stats`),
      fetchApiList('/sources'),
      fetchApiList('/jobs?limit=25'),
      fetchApiList('/extraction/ai/review-items?status=needs_review&limit=80').catch(() => []),
      fetchApiList('/dedup/candidates?limit=24&status=pending').catch(() => []),
    ]);
    return { stats: statsRes.data, sources, jobs, aiItems, dedupItems };
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const tick = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) { reload(); setDismissedIds(new Set()); return 30; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, [autoRefresh, reload]);

  const manualReload = () => { reload(); setCountdown(30); setDismissedIds(new Set()); };

  async function reviewAction(item, action) {
    const id = item.review_id;
    if (!id || reviewBusy.has(id)) return;
    setReviewBusy((prev) => new Set(prev).add(id));
    setNotice(null);
    try {
      if (action === 'approved') {
        await axios.post(`${API_BASE}/extraction/ai/review-items/${id}/publish`);
      }
      await axios.patch(`${API_BASE}/extraction/ai/review-items/${id}`, { status: action });
      setDismissedIds((prev) => new Set(prev).add(id));
      setNotice({ tone: 'good', text: action === 'approved' ? `✓ Đã duyệt & công bố mục ${id}.` : `✕ Đã từ chối mục ${id}.` });
    } catch (err) {
      setNotice({ tone: 'bad', text: `Lỗi khi xử lý mục ${id}: ${err?.response?.data?.detail || err.message}` });
    } finally {
      setReviewBusy((prev) => { const s = new Set(prev); s.delete(id); return s; });
    }
  }

  const data      = resource.data;
  const stats     = data?.stats   || {};
  const sources   = data?.sources || [];
  const jobs      = data?.jobs    || [];
  const aiItems   = (data?.aiItems || []).filter((i) => !dismissedIds.has(i.review_id));
  const dedupItems = data?.dedupItems || [];

  const totalProducts  = stats?.products?.total  || 0;
  const totalSources   = sources.length;
  const pendingFiles   = stats?.files?.pending   || 0;
  const completedFiles = stats?.files?.completed || 0;
  const failedJobs     = jobs.filter((j) => j.status === 'Failed').length;
  const runningJobs    = jobs.filter((j) => j.status !== 'Completed' && j.status !== 'Failed').length;
  const onlineSrcs     = sources.filter((s) => s.status !== 'offline').length;

  const pipelineActive = {
    crawl: runningJobs > 0, extract: pendingFiles > 0,
    ai: aiItems.length > 0, dedup: dedupItems.length > 0, store: completedFiles > 0,
  };

  const filteredJobs = jobs.filter((j) => {
    const matchStatus =
      statusFilter === 'all'     ? true :
      statusFilter === 'running' ? (j.status !== 'Completed' && j.status !== 'Failed') :
      statusFilter === 'error'   ? j.status === 'Failed' :
      statusFilter === 'done'    ? j.status === 'Completed' : true;
    const q = searchQ.toLowerCase();
    const matchSearch = !q || (j.id || '').toLowerCase().includes(q) || (j.source || '').toLowerCase().includes(q) || (j.filename || '').toLowerCase().includes(q);
    const matchSrc = !selectedSrc || j.source === selectedSrc;
    return matchStatus && matchSearch && matchSrc;
  });

  const bars = throughputBars();
  const maxBar = Math.max(...bars);

  if (resource.status === 'loading') {
    return (
      <div className="db2" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--muted)', fontSize: 13 }}>
          <RefreshCw size={14} className="spin-slow" /> Đang tải dữ liệu...
        </div>
      </div>
    );
  }

  if (resource.status === 'error') {
    return (
      <div className="db2" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', color: 'var(--muted)' }}>
          <AlertTriangle size={24} style={{ margin: '0 auto 8px', display: 'block', color: 'var(--amber)' }} />
          <p style={{ marginBottom: 10, fontSize: 12 }}>Không gọi được API. {resource.error}</p>
          <button onClick={reload} style={{ padding: '5px 14px', borderRadius: 5, background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)', color: '#93C5FD', cursor: 'pointer' }}>Thử lại</button>
        </div>
      </div>
    );
  }

  return (
    <div className="db2">
      {/* TOOLBAR */}
      <div className="db2-toolbar">
        <div className="db2-search">
          <Search />
          <input value={searchQ} onChange={(e) => setSearchQ(e.target.value)} placeholder="Tìm Job ID, nguồn..." />
        </div>
        <div className="db2-filter-group">
          {[{ v: 'all', l: 'Tất cả' }, { v: 'running', l: 'Đang chạy' }, { v: 'error', l: 'Lỗi' }, { v: 'done', l: 'Hoàn thành' }].map((f) => (
            <button key={f.v} className={`db2-filter-btn${statusFilter === f.v ? ' active' : ''}`} onClick={() => setStatusFilter(f.v)}>{f.l}</button>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <div className="db2-sys-indicator ok"><span className="db2-status-dot online" /> Hệ thống OK</div>
        <div className="db2-sys-indicator"><Cpu size={11} /> CPU —%</div>
        <div className="db2-sys-indicator warn"><AlertTriangle size={11} /> RAM —%</div>
        <button
          onClick={() => setAutoRefresh((v) => !v)}
          style={{ padding: '3px 9px', borderRadius: 5, border: '1px solid', fontSize: 11, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, background: autoRefresh ? 'rgba(34,197,94,0.1)' : 'rgba(51,65,85,0.3)', color: autoRefresh ? '#4ADE80' : 'var(--muted)', borderColor: autoRefresh ? 'rgba(34,197,94,0.25)' : 'var(--border)' }}
        >
          <Activity size={11} /> {autoRefresh ? `Auto ${countdown}s` : 'Auto: tắt'}
        </button>
        <button onClick={manualReload} style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
          <RefreshCw size={12} /> Làm mới
        </button>
      </div>

      {/* PIPELINE FLOW */}
      <div className="db2-pipeline">
        {PIPELINE_STAGES_DEF.map((stage, i) => {
          const active = pipelineActive[stage.id];
          const { Icon } = stage;
          return (
            <React.Fragment key={stage.id}>
              <div className={`db2-pipeline-step${active ? ' active' : ''}`}>
                <div className="db2-pipeline-step-icon"><Icon /></div>
                <span>{stage.label}</span>
              </div>
              {i < PIPELINE_STAGES_DEF.length - 1 && <ArrowRight size={10} className="db2-pipeline-arrow" style={{ margin: '0 6px', color: 'var(--border)' }} />}
            </React.Fragment>
          );
        })}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 10, color: 'var(--muted)' }}>Cập nhật: {new Date().toLocaleTimeString('vi-VN')}</span>
      </div>

      {/* KPI STRIP */}
      <div className="db2-kpis">
        {[
          { label: 'Tổng Sản Phẩm', value: totalProducts.toLocaleString('vi-VN'), note: `${stats?.products?.sources || totalSources} nguồn`, noteClass: 'up', Icon: Database, iconBg: 'rgba(59,130,246,0.15)', iconColor: '#3B82F6', NoteIcon: TrendingUp },
          { label: 'Nguồn Quét', value: totalSources, note: `${onlineSrcs} online`, noteClass: 'up', Icon: Globe, iconBg: 'rgba(6,182,212,0.15)', iconColor: '#06B6D4', NoteIcon: TrendingUp },
          { label: 'Job Đang Chạy', value: runningJobs, note: `${pendingFiles} file chờ`, noteClass: 'muted', Icon: RefreshCw, iconBg: 'rgba(139,92,246,0.15)', iconColor: '#8B5CF6', NoteIcon: null },
          { label: 'Tệp Đã Xử Lý', value: completedFiles.toLocaleString('vi-VN'), note: 'Kho đầu ra', noteClass: 'up', Icon: CheckCircle2, iconBg: 'rgba(34,197,94,0.15)', iconColor: '#22C55E', NoteIcon: TrendingUp },
          { label: 'Lỗi', value: failedJobs, note: failedJobs > 0 ? 'Cần xử lý' : 'Không có lỗi', noteClass: failedJobs > 0 ? 'bad' : 'up', Icon: AlertTriangle, iconBg: 'rgba(239,68,68,0.15)', iconColor: '#EF4444', NoteIcon: failedJobs > 0 ? TrendingDown : null },
          { label: 'AI Review', value: aiItems.length, note: aiItems.length > 0 ? 'Cần xử lý' : 'Đã duyệt hết', noteClass: aiItems.length > 0 ? 'bad' : 'up', Icon: Bot, iconBg: 'rgba(139,92,246,0.15)', iconColor: '#A78BFA', NoteIcon: aiItems.length > 0 ? AlertCircle : null },
        ].map((kpi) => {
          const { Icon, NoteIcon } = kpi;
          return (
            <div className="db2-kpi" key={kpi.label}>
              <div className="db2-kpi-header">
                <span className="db2-kpi-label">{kpi.label}</span>
                <div className="db2-kpi-icon" style={{ background: kpi.iconBg }}><Icon size={10} style={{ color: kpi.iconColor }} /></div>
              </div>
              <div className="db2-kpi-value">{kpi.value}</div>
              <div className={`db2-kpi-note ${kpi.noteClass}`}>{NoteIcon && <NoteIcon size={9} />}{kpi.note}</div>
            </div>
          );
        })}
      </div>

      {/* BODY */}
      <div className="db2-body">
        <div className="db2-main">
          {/* Table toolbar */}
          <div className="db2-table-toolbar">
            <div className="db2-tabs">
              <button className={`db2-tab${activeTab === 'jobs' ? ' active' : ''}`} onClick={() => setActiveTab('jobs')}>
                Lượt Chạy <span className="db2-tab-badge">{jobs.length}</span>
              </button>
              <button className={`db2-tab${activeTab === 'ai' ? ' active' : ''}`} onClick={() => setActiveTab('ai')}>
                AI Review <span className={`db2-tab-badge${aiItems.length > 0 ? ' warn' : ''}`}>{aiItems.length}</span>
              </button>
              <button className={`db2-tab${activeTab === 'dedup' ? ' active' : ''}`} onClick={() => setActiveTab('dedup')}>
                Dedup <span className="db2-tab-badge">{dedupItems.length}</span>
              </button>
            </div>
            <div style={{ flex: 1 }} />
            {activeTab === 'jobs' && <RouteLink to="/runs" navigate={navigate} style={{ fontSize: 11, color: 'var(--blue)', display: 'flex', alignItems: 'center', gap: 3 }}>Tất cả</RouteLink>}
            {activeTab === 'ai' && <RouteLink to="/ai/review" navigate={navigate} style={{ fontSize: 11, color: 'var(--blue)', display: 'flex', alignItems: 'center', gap: 3 }}>Mở AI Review</RouteLink>}
            {activeTab === 'dedup' && <RouteLink to="/dedup" navigate={navigate} style={{ fontSize: 11, color: 'var(--blue)', display: 'flex', alignItems: 'center', gap: 3 }}>Mở Dedup</RouteLink>}
          </div>

          {/* JOBS TAB */}
          {activeTab === 'jobs' && (
            <div className="db2-table-area">
              {filteredJobs.length === 0 ? (
                <div className="db2-empty"><FileSearch />Không có lượt chạy nào phù hợp với bộ lọc.</div>
              ) : (
                <table className="db2-table">
                  <thead><tr><th>Job / Tác vụ</th><th>Nguồn</th><th>Trạng Thái</th><th className="right">Cập nhật</th><th className="right">Hành Động</th></tr></thead>
                  <tbody>
                    {filteredJobs.map((job) => (
                      <tr key={job.id}>
                        <td><span className="db2-job-id" onClick={() => navigate(`/runs/${routeId(job.id)}`)}>{job.filename || job.id}</span></td>
                        <td style={{ color: 'var(--text-secondary)' }}>{job.source || '—'}</td>
                        <td>{db2StatusBadge(job.status)}</td>
                        <td className="right muted">{job.timestamp ? new Date(job.timestamp).toLocaleString('vi-VN') : '—'}</td>
                        <td className="right">
                          <div className="db2-row-actions">
                            <button className="db2-row-btn open" onClick={() => navigate(`/runs/${routeId(job.id)}`)}>Mở</button>
                            <button className="db2-row-btn log" onClick={() => navigate(`/tasks/${routeId(job.id)}/raw`)}>Log</button>
                            {job.status === 'Failed' && <button className="db2-row-btn retry">Chạy lại</button>}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* AI REVIEW TAB */}
          {activeTab === 'ai' && (
            <div className="db2-table-area">
              {notice && (
                <div style={{ padding: '7px 14px', margin: '8px 12px 0', borderRadius: 5, fontSize: 12, background: notice.tone === 'good' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)', color: notice.tone === 'good' ? '#4ADE80' : '#F87171', border: `1px solid ${notice.tone === 'good' ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span>{notice.text}</span>
                  <button onClick={() => setNotice(null)} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', opacity: 0.6, padding: '0 2px' }}><X size={12} /></button>
                </div>
              )}
              {aiItems.length === 0 ? (
                <div className="db2-empty"><Bot />{(data?.aiItems || []).length > 0 ? `Đã xử lý xong ${(data?.aiItems || []).length} mục — bấm Làm mới để tải danh sách mới.` : 'Không có mục nào cần AI review.'}</div>
              ) : (
                <table className="db2-table">
                  <thead><tr><th>Ứng viên / Tên</th><th>Nguồn</th><th>Loại</th><th>Độ tin cậy</th><th>Lý do</th><th className="right">Hành Động</th></tr></thead>
                  <tbody>
                    {aiItems.map((item, idx) => {
                      const busy = reviewBusy.has(item.review_id);
                      const conf = Math.round(Number(item.confidence || 0) * 100);
                      const confColor = conf >= 80 ? '#4ADE80' : conf >= 60 ? '#FBBF24' : '#F87171';
                      return (
                        <tr key={item.review_id || idx} style={{ opacity: busy ? 0.5 : 1, transition: 'opacity 0.2s' }}>
                          <td style={{ color: '#C4B5FD', fontWeight: 500 }}>{item.payload?.name || item.payload?.store_name || item.id || `AI-${idx + 1}`}</td>
                          <td style={{ color: 'var(--text-secondary)' }}>{item.source || item.source_site || item.payload?.url?.replace(/https?:\/\//, '').split('/')[0] || '—'}</td>
                          <td style={{ color: 'var(--muted)', fontSize: 11 }}>{item.entity_type || '—'}</td>
                          <td>{conf > 0 && <span style={{ color: confColor, fontSize: 11, fontWeight: 500 }}>{conf}%</span>}</td>
                          <td style={{ color: 'var(--amber)', fontSize: 11, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.reason || item.issue || item.review_note || '—'}</td>
                          <td className="right">
                            <div className="db2-row-actions">
                              <button className="db2-row-btn accept" disabled={busy || !item.review_id} onClick={() => reviewAction(item, 'approved')} title="Duyệt & công bố">
                                {busy ? <RefreshCw size={9} className="spin-slow" /> : <Check size={9} />}{busy ? '…' : 'Duyệt'}
                              </button>
                              <button className="db2-row-btn reject" disabled={busy || !item.review_id} onClick={() => reviewAction(item, 'rejected')} title="Từ chối">
                                <X size={9} /> Từ chối
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* DEDUP TAB */}
          {activeTab === 'dedup' && (
            <div className="db2-dedup-cta">
              <Shuffle />
              {dedupItems.length > 0
                ? <><strong style={{ color: 'var(--text-secondary)' }}>{dedupItems.length} cặp trùng lặp</strong> đang chờ xét duyệt.</>
                : 'Không có cặp trùng lặp nào đang chờ.'}
              <button onClick={() => navigate('/dedup')}>{dedupItems.length > 0 ? `Xem ${dedupItems.length} mục →` : 'Mở Dedup →'}</button>
            </div>
          )}

          {/* Footer */}
          <div className="db2-table-footer">
            <span>Sản phẩm: <b>{totalProducts.toLocaleString('vi-VN')}</b></span>
            <span>Nguồn: <b>{onlineSrcs}/{totalSources} online</b></span>
            <span>Lỗi: <b style={{ color: failedJobs > 0 ? 'var(--red)' : 'var(--green)' }}>{failedJobs}</b></span>
            <span>Tệp đã xử lý: <b>{completedFiles.toLocaleString('vi-VN')}</b></span>
            <span className="live"><span className="db2-status-dot online" style={{ flexShrink: 0 }} />Cập nhật: vừa xong</span>
          </div>
        </div>

        {/* Right panels */}
        <div className="db2-right">
          <div className="db2-panel">
            <div className="db2-panel-title">Thông Lượng (24h)<span style={{ color: 'var(--cyan)', display: 'flex', alignItems: 'center', gap: 3 }}><Zap size={9} /> Live</span></div>
            <div className="db2-chart-bars">
              {bars.map((v, i) => <div key={i} className="db2-chart-bar" style={{ height: `${(v / maxBar) * 100}%` }} title={`${v} req/s`} />)}
            </div>
            <div className="db2-chart-labels"><span>00:00</span><span>12:00</span><span>Bây giờ</span></div>
          </div>

          <div className="db2-panel">
            <div className="db2-panel-title">Hành Động Nhanh</div>
            <div className="db2-quick-actions">
              <button className="db2-quick-btn blue" onClick={() => navigate('/sources')}><Check /> Khởi động quét nhanh</button>
              <button className="db2-quick-btn purple" onClick={() => navigate('/ai/review')}><Bot /> Mở AI Review ({aiItems.length})</button>
              <button className="db2-quick-btn cyan" onClick={() => navigate('/dedup')}><Shuffle /> Xử lý Dedup ({dedupItems.length})</button>
              <button className="db2-quick-btn red" onClick={() => navigate('/runs')}><AlertCircle /> Xem lượt chạy lỗi</button>
              <button className="db2-quick-btn slate" onClick={() => navigate('/extraction/rules')}><FileSearch /> Quy tắc trích xuất</button>
            </div>
          </div>

          <div className="db2-panel">
            <div className="db2-panel-title">Tài Nguyên Hệ Thống</div>
            <div className="db2-resource">
              <Db2ResourceBar label="CPU" value={42} color="#3B82F6" />
              <Db2ResourceBar label="RAM" value={78} color="#F59E0B" />
              <Db2ResourceBar label="Disk I/O" value={31} color="#22C55E" />
              <Db2ResourceBar label="Network" value={55} color="#8B5CF6" />
            </div>
          </div>

          <div className="db2-panel db2-ai-mini">
            <div className="db2-panel-title">
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Bot size={9} style={{ color: '#C4B5FD' }} /> AI Review</span>
              {aiItems.length > 0 && <span className="db2-ai-header-badge">{aiItems.length} chờ</span>}
            </div>
            {aiItems.length === 0 ? (
              <div style={{ color: 'var(--muted)', fontSize: 11, textAlign: 'center', padding: '8px 0' }}>Không có mục nào cần duyệt.</div>
            ) : (
              <>
                <div className="db2-ai-items">
                  {aiItems.slice(0, 4).map((item, idx) => (
                    <div className="db2-ai-item" key={item.id || idx}>
                      <AlertTriangle />
                      <div className="db2-ai-item-text">
                        <div className="db2-ai-item-source">{item.source || item.source_site || '—'}</div>
                        <div className="db2-ai-item-issue">{item.issue || item.reason || item.review_note || '—'}</div>
                      </div>
                      {item.confidence != null && <span className="db2-ai-badge">{item.confidence}%</span>}
                    </div>
                  ))}
                </div>
                {aiItems.length > 4 && <div className="db2-ai-more" onClick={() => navigate('/ai/review')}>Xem tất cả {aiItems.length} mục →</div>}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
