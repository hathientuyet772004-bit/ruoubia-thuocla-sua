import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
  Activity, AlertCircle, AlertTriangle, ArrowRight, Check,
  CheckCircle2, Cpu, Database, FileSearch, Globe,
  RefreshCw, Search, TrendingDown, TrendingUp, X, Zap,
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
  { id: 'store',   label: 'Lưu trữ',  Icon: Database   },
];

export default function DashboardPage({ navigate }) {
  const [activeTab,    setActiveTab]    = useState('jobs');
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQ,      setSearchQ]      = useState('');
  const [selectedSrc,  setSelectedSrc]  = useState(null);
  const [countdown,    setCountdown]    = useState(30);
  const [autoRefresh,  setAutoRefresh]  = useState(true);

  const [resource, reload] = useApiResource(async () => {
    const [statsRes, sources, jobs] = await Promise.all([
      axios.get(`${API_BASE}/dashboard/stats`),
      fetchApiList('/sources'),
      fetchApiList('/jobs?limit=25'),
    ]);
    return { stats: statsRes.data, sources, jobs };
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const tick = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) { reload(); return 30; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, [autoRefresh, reload]);

  const manualReload = () => { reload(); setCountdown(30); };

  const data      = resource.data;
  const stats     = data?.stats   || {};
  const sources   = data?.sources || [];
  const jobs      = data?.jobs    || [];

  const totalProducts  = stats?.products?.total  || 0;
  const totalSources   = sources.length;
  const pendingFiles   = stats?.files?.pending   || 0;
  const completedFiles = stats?.files?.completed || 0;
  const failedJobs     = jobs.filter((j) => j.status === 'Failed').length;
  const runningJobs    = jobs.filter((j) => j.status !== 'Completed' && j.status !== 'Failed').length;
  const onlineSrcs     = sources.filter((s) => s.status !== 'offline').length;

  const pipelineActive = {
    crawl: runningJobs > 0, extract: pendingFiles > 0, store: completedFiles > 0,
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
            </div>
            <div style={{ flex: 1 }} />
            {activeTab === 'jobs' && <RouteLink to="/runs" navigate={navigate} style={{ fontSize: 11, color: 'var(--blue)', display: 'flex', alignItems: 'center', gap: 3 }}>Tất cả</RouteLink>}
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

        </div>
      </div>
    </div>
  );
}
