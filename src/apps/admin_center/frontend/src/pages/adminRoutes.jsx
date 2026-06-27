import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import {
  AlertTriangle,
  Boxes,
  ChevronRight,
  Check,
  Download,
  FileSearch,
  Globe,
  LayoutGrid,
  List,
  MapPin,
  Plus,
  Play,
  RefreshCw,
  Search,
  Sparkles,
  ShieldAlert,
  Table2,
  X,
  Upload,
  MoreVertical,
  Activity,
  CalendarClock,
  AlertCircle,
  ArrowRight,
  BarChart3,
  Bell,
  Bot,
  CheckCircle2,
  Copy,
  Cpu,
  Database,
  LayoutDashboard,
  Layers,
  Shuffle,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react';
import './dashboard-v2.css';

import ProductCard from '../components/ProductCard';
import { classifyApiError, expectApiList, fetchApiList } from '../apiClient';
import { routeId } from '../routeShell';

const API_BASE = '/api';
const DEFAULT_SYNTHETIC_COLUMNS = 'name,category,brand,price,currency,rating,store_name,store_address,source,url';

function hostFromUrl(url = '') {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url || 'không rõ';
  }
}

export { classifyApiError, expectApiList };

function useApiResource(load, deps) {
  const [resource, setResource] = useState({ status: 'loading', data: null, error: null });
  const [reloadToken, setReloadToken] = useState(0);
  useEffect(() => {
    let active = true;
    setResource({ status: 'loading', data: null, error: null });
    load().then((data) => active && setResource({ status: 'ready', data, error: null })).catch((error) => {
      if (!active) return;
      const failure = classifyApiError(error);
      setResource({ status: failure.kind, data: null, error: failure.message });
    });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadToken]);
  return [resource, () => setReloadToken((value) => value + 1)];
}

function Stat({ label, value, note, tone = 'good' }) {
  return <article className="route-stat"><span>{label}</span><strong>{value}</strong><small className={tone}>{note}</small></article>;
}

function Pill({ children, tone = 'neutral' }) {
  return <span className={`ops-pill ${tone}`}>{children}</span>;
}

export function RouteLink({ to, navigate, children, className = '' }) {
  return <a href={to} className={className} onClick={(event) => { event.preventDefault(); navigate(to); }}>{children}</a>;
}

function StatePanel({ resource, empty, onRetry, children }) {
  if (resource.status === 'loading') return <div className="route-state loading"><RefreshCw />Đang tải dữ liệu từ API...</div>;
  if (resource.status === 'permission') return <div className="route-state permission"><ShieldAlert />Không đủ quyền.<span>{resource.error}</span></div>;
  if (resource.status === 'error') return <div className="route-state error"><AlertTriangle />Không gọi được API.<span>{resource.error}</span><button onClick={onRetry}>Thử lại</button></div>;
  if (empty) return <div className="route-state empty"><FileSearch />Chưa có dữ liệu cho bộ lọc hiện tại.</div>;
  return children;
}

function jobStatusLabel(status) {
  return ({ Completed: 'Hoàn tất', Failed: 'Thất bại', Pending: 'Đang chờ' })[status] || status || '-';
}

function priceStatus(product) {
  const price = Number(product.price_numeric ?? product.price);
  if (Number.isFinite(price) && price > 0) return 'FOUND';
  return product.price_status || 'MISSING';
}

function priceStatusLabel(status) {
  return ({ FOUND: 'Giá hợp lệ', MISSING: 'Thiếu giá', PARSE_ERROR: 'Lỗi parse', BLOCKED: 'Bị chặn', JS_RENDER_REQUIRED: 'Cần JS' })[status] || status || 'Thiếu giá';
}

function priceStatusTone(status) {
  return status === 'FOUND' ? 'good' : status === 'PARSE_ERROR' || status === 'BLOCKED' ? 'bad' : 'warning';
}

function formatProductPrice(product) {
  const price = Number(product.price_numeric ?? product.price);
  if (!Number.isFinite(price) || price <= 0) return 'N/A';
  return `${price.toLocaleString('vi-VN')} VND`;
}

function dedupStatusLabel(status) {
  return ({ pending: 'Đang chờ', merged: 'Đã gộp', rejected: 'Đã loại', approved: 'Đã duyệt', needs_review: 'Cần rà soát', all: 'Tất cả' })[status] || status;
}

export function sourceTypeLabel(type) {
  return ({ 'E-commerce': 'Thương mại điện tử', 'Brand Site': 'Trang thương hiệu', Directory: 'Danh bạ', Social: 'Mạng xã hội' })[type] || type || '-';
}

function extractionTargetLabel(target) {
  return ({ product_detail: 'Chi tiết sản phẩm', product_listing: 'Danh sách sản phẩm', store_detail: 'Chi tiết cửa hàng', store_listing: 'Danh sách cửa hàng' })[target] || target;
}

function Page({ title, subtitle, actions, children }) {
  return <section className="route-page"><header className="route-page-header"><div><h1>{title}</h1><p>{subtitle}</p></div><div>{actions}</div></header>{children}</section>;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function filenameFromDisposition(header, fallback) {
  const match = /filename="?([^"]+)"?/i.exec(header || '');
  return match?.[1] || fallback;
}

function storeLabel(row = {}) {
  return row.store_name || row.store_url || '';
}

function storeAddressLabel(row = {}) {
  if (row.store_address) return row.store_address;
  if (row.address_status === 'NOT_APPLICABLE' || row.store_channel === 'online') return 'Online';
  return 'Chưa có địa chỉ';
}

function splitList(value = '') {
  return value.split(/[\n,]+/).map((item) => item.trim()).filter(Boolean);
}

function Panel({ title, className = '', children, actions }) {
  return <section className={`route-panel ${className}`}><header><h2>{title}</h2>{actions}</header>{children}</section>;
}

function TableShell({ className = '', tableClassName = '', children }) {
  return <div className={`table-wrapper ${className}`.trim()}><table className={tableClassName}>{children}</table></div>;
}

function JobRows({ jobs, navigate, className = '', tableClassName = '' }) {
  return (
    <TableShell className={className} tableClassName={tableClassName}>
      <thead><tr><th>Lượt chạy / tác vụ</th><th>Nguồn</th><th>Trạng thái</th><th>Cập nhật</th><th>Trang thô</th></tr></thead>
      <tbody>{jobs.map((job) => <tr key={job.id}><td><RouteLink to={`/runs/${routeId(job.id)}`} navigate={navigate}>{job.filename || job.id}</RouteLink></td><td>{job.source}</td><td><Pill tone={job.status === 'Completed' ? 'good' : job.status === 'Failed' ? 'bad' : 'warning'}>{jobStatusLabel(job.status)}</Pill></td><td>{new Date(job.timestamp).toLocaleString()}</td><td><RouteLink to={`/tasks/${routeId(job.id)}/raw`} navigate={navigate}>Mở</RouteLink></td></tr>)}</tbody>
    </TableShell>
  );
}

function ProductRows({ products, className = '', tableClassName = 'products-table' }) {
  return (
    <TableShell className={className} tableClassName={tableClassName}>
        <thead><tr><th>Tên sản phẩm</th><th>Thương hiệu</th><th>Danh mục</th><th>Giá</th><th>Trạng thái giá</th><th>Cửa hàng / kênh bán</th><th>Nguồn</th><th>Cập nhật</th><th>URL</th></tr></thead>
        <tbody>{products.map((product, index) => {
          const status = priceStatus(product);
          return (
            <tr key={`${product.url || product.name}-${index}`}>
              <td className="product-name-cell" title={product.name || ''}>{product.name || 'Sản phẩm chưa có tên'}</td>
              <td title={product.brand || ''}>{product.brand || '-'}</td>
              <td><Pill>{product.category || 'Khác'}</Pill></td>
              <td className={status === 'FOUND' ? 'price-cell' : 'muted-cell'}>{formatProductPrice(product)}</td>
              <td><Pill tone={priceStatusTone(status)}>{priceStatusLabel(status)}</Pill></td>
              <td title={`${storeLabel(product) || ''} ${storeAddressLabel(product)}`}>{storeLabel(product) || '-'}<small>{storeAddressLabel(product)}</small></td>
              <td>{product.source || product.source_site || '-'}</td>
              <td>{product.updated_at ? new Date(product.updated_at).toLocaleString() : '-'}</td>
              <td>{product.url ? <a className="source-link" href={product.url} target="_blank" rel="noreferrer">Mở nguồn</a> : '-'}</td>
            </tr>
          );
        })}</tbody>
    </TableShell>
  );
}

function ProductGrid({ products }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '20px', padding: '16px 0' }}>
      {products.map((product, index) => (
        <ProductCard key={`${product.url || product.name}-${index}`} product={product} />
      ))}
    </div>
  );
}

function ProductList({ products }) {
  return <div className="product-list-view">{products.map((product, index) => {
    const status = priceStatus(product);
    return <article key={`${product.url || product.name}-${index}`}><div><b>{product.name || 'Sản phẩm chưa có tên'}</b><span>{storeLabel(product) || 'Chưa liên kết cửa hàng'} · {storeAddressLabel(product)} · {product.source || product.source_site || '-'} · {product.category || '-'}</span></div><strong className={status === 'FOUND' ? '' : 'muted-cell'}>{formatProductPrice(product)}</strong><Pill tone={priceStatusTone(status)}>{priceStatusLabel(status)}</Pill><a href={product.url || '#'} target="_blank" rel="noreferrer">Mở nguồn</a></article>;
  })}</div>;
}

function DashboardFlowCard({ to, navigate, icon: Icon, title, subtitle }) {
  return (
    <RouteLink to={to} navigate={navigate} className="dashboard-flow-card">
      <div className="dashboard-flow-card-icon">{Icon ? <Icon /> : null}</div>
      <div><strong>{title}</strong><p>{subtitle}</p></div>
      <ChevronRight />
    </RouteLink>
  );
}

function SourceRows({ sources, navigate, onCollect, collectingId }) {
  return (
    <TableShell>
      <thead><tr><th>Tên nguồn</th><th>Loại</th><th>Danh mục</th><th>URL</th><th>Hành động</th></tr></thead>
      <tbody>
        {sources.map((source) => (
          <tr key={source.id}>
            <td><RouteLink to={`/sources/${source.id}`} navigate={navigate}>{source.name || source.url}</RouteLink></td>
            <td><Pill>{sourceTypeLabel(source.type)}</Pill></td>
            <td>{source.category || '-'}</td>
            <td><a className="source-link" href={source.url} target="_blank" rel="noreferrer">{hostFromUrl(source.url)}</a></td>
            <td><button disabled={collectingId === source.id} onClick={() => onCollect(source)}>{collectingId === source.id ? 'Đang thu thập...' : <><Play />Chạy</>}</button></td>
          </tr>
        ))}
      </tbody>
    </TableShell>
  );
}

// ─── helpers for DashboardPage ───────────────────────────────────────────────

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

// Deterministic bar heights from a seed — avoids random re-renders
function throughputBars(count = 24) {
  const seed = [42,61,38,55,70,48,80,65,52,88,74,60,45,91,78,62,56,83,69,50,75,87,64,72];
  return seed.slice(0, count);
}

const PIPELINE_STAGES_DEF = [
  { id: 'crawl',   label: 'Thu thập', Icon: Globe      },
  { id: 'extract', label: 'Trích xuất', Icon: FileSearch },
  { id: 'ai',      label: 'AI Review', Icon: Bot        },
  { id: 'dedup',   label: 'Dedup',    Icon: Copy       },
  { id: 'store',   label: 'Lưu trữ', Icon: Database   },
];

export function DashboardPage({ navigate }) {
  const [activeTab,     setActiveTab]     = useState('jobs');
  const [statusFilter,  setStatusFilter]  = useState('all');
  const [searchQ,       setSearchQ]       = useState('');
  const [selectedSrc,   setSelectedSrc]   = useState(null);

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

  const data    = resource.data;
  const stats   = data?.stats   || {};
  const sources = data?.sources || [];
  const jobs    = data?.jobs    || [];
  const aiItems = data?.aiItems || [];
  const dedupItems = data?.dedupItems || [];

  // Derived counts
  const totalProducts  = stats?.products?.total   || 0;
  const totalSources   = sources.length;
  const pendingFiles   = stats?.files?.pending    || 0;
  const completedFiles = stats?.files?.completed  || 0;
  const failedJobs     = jobs.filter(j => j.status === 'Failed').length;
  const runningJobs    = jobs.filter(j => j.status !== 'Completed' && j.status !== 'Failed').length;
  const onlineSrcs     = sources.filter(s => s.status !== 'offline').length;
  const avgPrice       = stats?.market?.avg_price || 0;

  // pipeline activity flags based on real data
  const pipelineActive = {
    crawl:   runningJobs > 0,
    extract: pendingFiles > 0,
    ai:      aiItems.length > 0,
    dedup:   dedupItems.length > 0,
    store:   completedFiles > 0,
  };

  const filteredJobs = jobs.filter(j => {
    const matchStatus =
      statusFilter === 'all'      ? true :
      statusFilter === 'running'  ? (j.status !== 'Completed' && j.status !== 'Failed') :
      statusFilter === 'error'    ? j.status === 'Failed' :
      statusFilter === 'done'     ? j.status === 'Completed' : true;
    const q = searchQ.toLowerCase();
    const matchSearch = !q || (j.id || '').toLowerCase().includes(q) || (j.source || '').toLowerCase().includes(q) || (j.filename || '').toLowerCase().includes(q);
    const matchSrc = !selectedSrc || j.source === selectedSrc;
    return matchStatus && matchSearch && matchSrc;
  });

  const bars = throughputBars();
  const maxBar = Math.max(...bars);

  // Source status helper — backend may not have a 'status' field, treat all as 'online' fallback
  function srcStatus(s) {
    return s.status || 'online';
  }
  function srcDotClass(s) {
    const st = srcStatus(s);
    if (st === 'warning') return 'warning';
    if (st === 'offline') return 'offline';
    return 'online';
  }

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
          <button onClick={reload} style={{ padding: '5px 14px', borderRadius: 5, background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)', color: '#93C5FD', cursor: 'pointer' }}>
            Thử lại
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="db2">

      {/* ── TOOLBAR ─────────────────────────────────────────────── */}
      <div className="db2-toolbar">
        <div className="db2-search">
          <Search />
          <input
            value={searchQ}
            onChange={e => setSearchQ(e.target.value)}
            placeholder="Tìm Job ID, nguồn..."
          />
        </div>

        <div className="db2-filter-group">
          {[
            { v: 'all',     l: 'Tất cả'    },
            { v: 'running', l: 'Đang chạy' },
            { v: 'error',   l: 'Lỗi'       },
            { v: 'done',    l: 'Hoàn thành'},
          ].map(f => (
            <button
              key={f.v}
              className={`db2-filter-btn${statusFilter === f.v ? ' active' : ''}`}
              onClick={() => setStatusFilter(f.v)}
            >{f.l}</button>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        <div className="db2-sys-indicator ok">
          <span className="db2-status-dot online" /> Hệ thống OK
        </div>
        <div className="db2-sys-indicator">
          <Cpu size={11} /> CPU —%
        </div>
        <div className="db2-sys-indicator warn">
          <AlertTriangle size={11} /> RAM —%
        </div>
        <button onClick={reload} style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
          <RefreshCw size={12} /> Làm mới
        </button>
      </div>

      {/* ── PIPELINE FLOW ───────────────────────────────────────── */}
      <div className="db2-pipeline">
        {PIPELINE_STAGES_DEF.map((stage, i) => {
          const active = pipelineActive[stage.id];
          const { Icon } = stage;
          return (
            <React.Fragment key={stage.id}>
              <div className={`db2-pipeline-step${active ? ' active' : ''}`}>
                <div className="db2-pipeline-step-icon">
                  <Icon />
                </div>
                <span>{stage.label}</span>
              </div>
              {i < PIPELINE_STAGES_DEF.length - 1 && (
                <ArrowRight size={10} className="db2-pipeline-arrow" style={{ margin: '0 6px', color: 'var(--border)' }} />
              )}
            </React.Fragment>
          );
        })}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 10, color: 'var(--muted)' }}>Cập nhật: {new Date().toLocaleTimeString('vi-VN')}</span>
      </div>

      {/* ── KPI STRIP ───────────────────────────────────────────── */}
      <div className="db2-kpis">
        {[
          {
            label: 'Tổng Sản Phẩm', value: totalProducts.toLocaleString('vi-VN'),
            note: `${stats?.products?.sources || totalSources} nguồn`, noteClass: 'up',
            Icon: Database, iconBg: 'rgba(59,130,246,0.15)', iconColor: '#3B82F6',
            NoteIcon: TrendingUp,
          },
          {
            label: 'Nguồn Quét', value: totalSources,
            note: `${onlineSrcs} online`, noteClass: 'up',
            Icon: Globe, iconBg: 'rgba(6,182,212,0.15)', iconColor: '#06B6D4',
            NoteIcon: TrendingUp,
          },
          {
            label: 'Job Đang Chạy', value: runningJobs,
            note: `${pendingFiles} file chờ`, noteClass: 'muted',
            Icon: RefreshCw, iconBg: 'rgba(139,92,246,0.15)', iconColor: '#8B5CF6',
            NoteIcon: null,
          },
          {
            label: 'Tệp Đã Xử Lý', value: completedFiles.toLocaleString('vi-VN'),
            note: 'Kho đầu ra', noteClass: 'up',
            Icon: CheckCircle2, iconBg: 'rgba(34,197,94,0.15)', iconColor: '#22C55E',
            NoteIcon: TrendingUp,
          },
          {
            label: 'Lỗi (Job)', value: failedJobs,
            note: failedJobs > 0 ? 'Cần rà soát' : 'Không có lỗi', noteClass: failedJobs > 0 ? 'bad' : 'up',
            Icon: AlertCircle, iconBg: 'rgba(239,68,68,0.15)', iconColor: '#EF4444',
            NoteIcon: failedJobs > 0 ? TrendingDown : null,
          },
          {
            label: 'AI Review', value: aiItems.length,
            note: aiItems.length > 0 ? 'Cần xử lý' : 'Đã duyệt hết', noteClass: aiItems.length > 0 ? 'bad' : 'up',
            Icon: Bot, iconBg: 'rgba(139,92,246,0.15)', iconColor: '#A78BFA',
            NoteIcon: aiItems.length > 0 ? AlertCircle : null,
          },
        ].map(kpi => {
          const { Icon, NoteIcon } = kpi;
          return (
            <div className="db2-kpi" key={kpi.label}>
              <div className="db2-kpi-header">
                <span className="db2-kpi-label">{kpi.label}</span>
                <div className="db2-kpi-icon" style={{ background: kpi.iconBg }}>
                  <Icon size={10} style={{ color: kpi.iconColor }} />
                </div>
              </div>
              <div className="db2-kpi-value">{kpi.value}</div>
              <div className={`db2-kpi-note ${kpi.noteClass}`}>
                {NoteIcon && <NoteIcon size={9} />}
                {kpi.note}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── BODY ────────────────────────────────────────────────── */}
      <div className="db2-body">

        {/* Main table panel */}
        <div className="db2-main">
          {/* Table toolbar with tabs */}
          <div className="db2-table-toolbar">
            <div className="db2-tabs">
              <button
                className={`db2-tab${activeTab === 'jobs' ? ' active' : ''}`}
                onClick={() => setActiveTab('jobs')}
              >
                Lượt Chạy <span className="db2-tab-badge">{jobs.length}</span>
              </button>
              <button
                className={`db2-tab${activeTab === 'ai' ? ' active' : ''}`}
                onClick={() => setActiveTab('ai')}
              >
                AI Review <span className={`db2-tab-badge${aiItems.length > 0 ? ' warn' : ''}`}>{aiItems.length}</span>
              </button>
              <button
                className={`db2-tab${activeTab === 'dedup' ? ' active' : ''}`}
                onClick={() => setActiveTab('dedup')}
              >
                Dedup <span className="db2-tab-badge">{dedupItems.length}</span>
              </button>
            </div>

            <div style={{ flex: 1 }} />

            {activeTab === 'jobs' && (
              <RouteLink to="/runs" navigate={navigate}
                style={{ fontSize: 11, color: 'var(--blue)', display: 'flex', alignItems: 'center', gap: 3 }}>
                Tất cả <ChevronRight size={11} />
              </RouteLink>
            )}
            {activeTab === 'ai' && (
              <RouteLink to="/ai/review" navigate={navigate}
                style={{ fontSize: 11, color: 'var(--blue)', display: 'flex', alignItems: 'center', gap: 3 }}>
                Mở AI Review <ChevronRight size={11} />
              </RouteLink>
            )}
            {activeTab === 'dedup' && (
              <RouteLink to="/dedup" navigate={navigate}
                style={{ fontSize: 11, color: 'var(--blue)', display: 'flex', alignItems: 'center', gap: 3 }}>
                Mở Dedup <ChevronRight size={11} />
              </RouteLink>
            )}
          </div>

          {/* JOBS TAB */}
          {activeTab === 'jobs' && (
            <div className="db2-table-area">
              {filteredJobs.length === 0 ? (
                <div className="db2-empty">
                  <FileSearch />
                  Không có lượt chạy nào phù hợp với bộ lọc.
                </div>
              ) : (
                <table className="db2-table">
                  <thead>
                    <tr>
                      <th>Job / Tác vụ</th>
                      <th>Nguồn</th>
                      <th>Trạng Thái</th>
                      <th className="right">Cập nhật</th>
                      <th className="right">Hành Động</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredJobs.map(job => (
                      <tr key={job.id}>
                        <td>
                          <span
                            className="db2-job-id"
                            onClick={() => navigate(`/runs/${routeId(job.id)}`)}
                          >
                            {job.filename || job.id}
                          </span>
                        </td>
                        <td style={{ color: 'var(--text-secondary)' }}>{job.source || '—'}</td>
                        <td>{db2StatusBadge(job.status)}</td>
                        <td className="right muted">
                          {job.timestamp ? new Date(job.timestamp).toLocaleString('vi-VN') : '—'}
                        </td>
                        <td className="right">
                          <div className="db2-row-actions">
                            <button
                              className="db2-row-btn open"
                              onClick={() => navigate(`/runs/${routeId(job.id)}`)}
                            >Mở</button>
                            <button
                              className="db2-row-btn log"
                              onClick={() => navigate(`/tasks/${routeId(job.id)}/raw`)}
                            >Log</button>
                            {job.status === 'Failed' && (
                              <button className="db2-row-btn retry">Chạy lại</button>
                            )}
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
              {aiItems.length === 0 ? (
                <div className="db2-empty">
                  <Bot />
                  Không có mục nào cần AI review.
                </div>
              ) : (
                <table className="db2-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Nguồn</th>
                      <th>Trường</th>
                      <th>Vấn đề</th>
                      <th className="right">Hành Động</th>
                    </tr>
                  </thead>
                  <tbody>
                    {aiItems.map((item, idx) => (
                      <tr key={item.id || idx}>
                        <td style={{ color: '#C4B5FD', fontWeight: 500 }}>{item.id || `AI-${idx + 1}`}</td>
                        <td style={{ color: 'var(--text-secondary)' }}>{item.source || item.source_site || '—'}</td>
                        <td style={{ color: 'var(--muted)' }}>{item.field || item.extraction_field || '—'}</td>
                        <td style={{ color: 'var(--amber)', fontSize: 11 }}>{item.issue || item.reason || item.review_note || '—'}</td>
                        <td className="right">
                          <div className="db2-row-actions">
                            <button className="db2-row-btn accept">Chấp nhận</button>
                            <button className="db2-row-btn reject">Từ chối</button>
                          </div>
                        </td>
                      </tr>
                    ))}
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
              <button onClick={() => navigate('/dedup')}>
                {dedupItems.length > 0 ? `Xem ${dedupItems.length} mục →` : 'Mở Dedup →'}
              </button>
            </div>
          )}

          {/* Footer aggregate */}
          <div className="db2-table-footer">
            <span>Sản phẩm: <b>{totalProducts.toLocaleString('vi-VN')}</b></span>
            <span>Nguồn: <b>{onlineSrcs}/{totalSources} online</b></span>
            <span>Lỗi: <b style={{ color: failedJobs > 0 ? 'var(--red)' : 'var(--green)' }}>{failedJobs}</b></span>
            <span>Tệp đã xử lý: <b>{completedFiles.toLocaleString('vi-VN')}</b></span>
            <span className="live">
              <span className="db2-status-dot online" style={{ flexShrink: 0 }} />
              Cập nhật: vừa xong
            </span>
          </div>
        </div>

        {/* Right panels */}
        <div className="db2-right">

          {/* Throughput chart */}
          <div className="db2-panel">
            <div className="db2-panel-title">
              Thông Lượng (24h)
              <span style={{ color: 'var(--cyan)', display: 'flex', alignItems: 'center', gap: 3 }}>
                <Zap size={9} /> Live
              </span>
            </div>
            <div className="db2-chart-bars">
              {bars.map((v, i) => (
                <div
                  key={i}
                  className="db2-chart-bar"
                  style={{ height: `${(v / maxBar) * 100}%` }}
                  title={`${v} req/s`}
                />
              ))}
            </div>
            <div className="db2-chart-labels">
              <span>00:00</span><span>12:00</span><span>Bây giờ</span>
            </div>
          </div>

          {/* Quick actions */}
          <div className="db2-panel">
            <div className="db2-panel-title">Hành Động Nhanh</div>
            <div className="db2-quick-actions">
              <button className="db2-quick-btn blue" onClick={() => navigate('/sources')}>
                <Play /> Khởi động quét nhanh
              </button>
              <button className="db2-quick-btn purple" onClick={() => navigate('/ai/review')}>
                <Bot /> Mở AI Review ({aiItems.length})
              </button>
              <button className="db2-quick-btn cyan" onClick={() => navigate('/dedup')}>
                <Shuffle /> Xử lý Dedup ({dedupItems.length})
              </button>
              <button className="db2-quick-btn red" onClick={() => navigate('/runs')}>
                <AlertCircle /> Xem lượt chạy lỗi
              </button>
              <button className="db2-quick-btn slate" onClick={() => navigate('/extraction/rules')}>
                <FileSearch /> Quy tắc trích xuất
              </button>
            </div>
          </div>

          {/* System resource monitor */}
          <div className="db2-panel">
            <div className="db2-panel-title">Tài Nguyên Hệ Thống</div>
            <div className="db2-resource">
              <Db2ResourceBar label="CPU" value={42} color="#3B82F6" />
              <Db2ResourceBar label="RAM" value={78} color="#F59E0B" />
              <Db2ResourceBar label="Disk I/O" value={31} color="#22C55E" />
              <Db2ResourceBar label="Network" value={55} color="#8B5CF6" />
            </div>
          </div>

          {/* AI review mini panel */}
          <div className="db2-panel db2-ai-mini">
            <div className="db2-panel-title">
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <Bot size={9} style={{ color: '#C4B5FD' }} /> AI Review
              </span>
              {aiItems.length > 0 && (
                <span className="db2-ai-header-badge">{aiItems.length} chờ</span>
              )}
            </div>
            {aiItems.length === 0 ? (
              <div style={{ color: 'var(--muted)', fontSize: 11, textAlign: 'center', padding: '8px 0' }}>
                Không có mục nào cần duyệt.
              </div>
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
                      {item.confidence != null && (
                        <span className="db2-ai-badge">{item.confidence}%</span>
                      )}
                    </div>
                  ))}
                </div>
                {aiItems.length > 4 && (
                  <div className="db2-ai-more" onClick={() => navigate('/ai/review')}>
                    Xem tất cả {aiItems.length} mục →
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function SourcesPage({ navigate, onAdd }) {
  const [query, setQuery] = useState('');
  const [notice, setNotice] = useState(null);
  const [collectingId, setCollectingId] = useState('');
  const uploadInputRef = useRef(null);
  const [resource, reload] = useApiResource(() => fetchApiList('/sources'), []);
  const sources = (resource.data || []).filter((source) => `${source.name} ${source.url} ${source.category}`.toLowerCase().includes(query.toLowerCase()));
  const downloadSourceFile = async (endpoint, fallback) => {
    try {
      const response = await axios.get(`${API_BASE}${endpoint}`, { responseType: 'blob' });
      downloadBlob(response.data, filenameFromDisposition(response.headers['content-disposition'], fallback));
      setNotice({ tone: 'good', text: 'Đã tải tệp nguồn.' });
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };
  const uploadSources = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    try {
      const csv = await file.text();
      const response = await axios.post(`${API_BASE}/sources/import`, csv, { headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
      setNotice({ tone: response.data.failed ? 'bad' : 'good', text: `Đã nhập ${response.data.imported}/${response.data.total} nguồn từ ${file.name}.` });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };
  const collectSource = async (source) => {
    setCollectingId(source.id);
    try {
      const response = await axios.post(`${API_BASE}/sources/${source.id}/collect`);
      setNotice({ tone: 'good', text: `Đã chạy thu thập cho ${source.name || source.id}: ${response.data.status}.` });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    } finally {
      setCollectingId('');
    }
  };
  return <Page title="Nguồn dữ liệu" subtitle="Danh mục nguồn lấy trực tiếp từ API. Bấm Chạy để thu thập ngầm theo từng nguồn." actions={<><label className="route-search"><Search /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Lọc nguồn..." /></label><button onClick={() => downloadSourceFile('/sources/template', 'source-import-template.csv')}><Download />Mẫu thêm nguồn</button><button onClick={() => uploadInputRef.current?.click()}><Upload />Tải lên danh sách</button><input ref={uploadInputRef} className="hidden-file-input" type="file" accept=".csv,text/csv" onChange={uploadSources} /><button onClick={() => downloadSourceFile('/sources/export', 'source-list.csv')}><Download />Tải xuống danh sách</button><button onClick={reload}><RefreshCw />Tải lại</button><button onClick={onAdd}><Plus />Thêm nguồn</button></>}><Panel title="Danh mục nguồn">{notice ? <p className={`route-notice ${notice.tone}`}>{notice.text}</p> : null}<StatePanel resource={resource} onRetry={reload} empty={!sources.length}><SourceRows sources={sources} navigate={navigate} onCollect={collectSource} collectingId={collectingId} /></StatePanel></Panel></Page>;
}

export function SourceDetailPage({ sourceId, navigate }) {
  const [resource, reload] = useApiResource(() => fetchApiList('/sources'), [sourceId]);
  const source = resource.data?.find((item) => String(item.id) === String(sourceId));
  const [discovery, reloadDiscovery] = useApiResource(
    () => (sourceId ? axios.get(`${API_BASE}/sources/${sourceId}/discovery`).then((response) => response.data) : Promise.resolve(null)),
    [sourceId]
  );
  const [runs, reloadRuns] = useApiResource(
    () => (sourceId ? fetchApiList(`/sources/${sourceId}/runs?limit=12`) : Promise.resolve([])),
    [sourceId]
  );
  const [artifactId, setArtifactId] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [analysisState, setAnalysisState] = useState('idle');
  const [reviewState, setReviewState] = useState('idle');
  const [reviewResult, setReviewResult] = useState(null);
  const [collectState, setCollectState] = useState('idle');
  const [collectNotice, setCollectNotice] = useState(null);
  const [syntheticForm, setSyntheticForm] = useState({ rowCount: 20, productTypes: '', referenceSources: '', region: 'Toàn quốc', outputColumns: DEFAULT_SYNTHETIC_COLUMNS, persist: true });
  const [syntheticState, setSyntheticState] = useState('idle');
  const [syntheticResult, setSyntheticResult] = useState(null);

  useEffect(() => {
    setArtifactId('');
    setAnalysis(null);
    setAnalysisState('idle');
    setSyntheticResult(null);
    setSyntheticState('idle');
  }, [sourceId]);

  useEffect(() => {
    if (!source) return;
    setSyntheticForm((current) => ({
      ...current,
      productTypes: current.productTypes || source.category || '',
      referenceSources: current.referenceSources || source.url || source.name || '',
    }));
  }, [source]);

  useEffect(() => {
    const firstArtifact = discovery.data?.raw_artifacts?.[0]?.id;
    if (firstArtifact && !artifactId) setArtifactId(firstArtifact);
  }, [artifactId, discovery.data]);

  const selectedArtifact = discovery.data?.raw_artifacts?.find((item) => item.id === artifactId);
  const [artifactPreview, reloadArtifactPreview] = useApiResource(
    () => (selectedArtifact ? axios.get(`${API_BASE}/extraction/raw-artifacts/${selectedArtifact.id}`, { params: { domain: discovery.data?.domain } }).then((response) => response.data) : Promise.resolve(null)),
    [artifactId, discovery.data?.domain]
  );

  const runGeminiAnalysis = async () => {
    if (!discovery.data?.domain) return;
    setAnalysisState('loading');
    try {
      const response = await axios.post(`${API_BASE}/extraction/ai/analyze`, {
        domain: discovery.data.domain,
        raw_artifact_id: selectedArtifact?.id || artifactId || undefined,
        target_hint: discovery.data?.rule?.targets?.[0] || 'auto',
      });
      setAnalysis(response.data);
      setAnalysisState('ready');
    } catch (error) {
      const failure = classifyApiError(error);
      setAnalysis({ error: failure.message });
      setAnalysisState('error');
    }
  };

  const generateAiReviewList = async () => {
    if (!discovery.data?.domain) return;
    setReviewState('loading');
    try {
      const response = await axios.post(`${API_BASE}/extraction/ai/review`, {
        domain: discovery.data.domain,
        raw_artifact_id: selectedArtifact?.id || artifactId || undefined,
        target_hint: discovery.data?.rule?.targets?.[0] || 'auto',
        max_items: 24,
      });
      setReviewResult(response.data);
      setReviewState('ready');
    } catch (error) {
      const failure = classifyApiError(error);
      setReviewResult({ error: failure.message });
      setReviewState('error');
    }
  };

  const collectSource = async () => {
    setCollectState('loading');
    setCollectNotice(null);
    try {
      const response = await axios.post(`${API_BASE}/sources/${sourceId}/collect`);
      setCollectNotice({ tone: 'good', text: `Đã chạy thu thập: ${response.data.status}.` });
      reload();
      reloadDiscovery();
      reloadRuns();
      reloadArtifactPreview();
    } catch (error) {
      const failure = classifyApiError(error);
      setCollectNotice({ tone: 'bad', text: failure.message });
    } finally {
      setCollectState('idle');
    }
  };

  const generateSyntheticData = async () => {
    setSyntheticState('loading');
    setSyntheticResult(null);
    try {
      const response = await axios.post(`${API_BASE}/sources/${sourceId}/generate-data`, {
        row_count: Number(syntheticForm.rowCount) || 20,
        product_types: splitList(syntheticForm.productTypes),
        reference_sources: splitList(syntheticForm.referenceSources),
        region: syntheticForm.region || 'Toàn quốc',
        output_columns: splitList(syntheticForm.outputColumns),
        persist: syntheticForm.persist,
      });
      setSyntheticResult(response.data);
      setSyntheticState('ready');
      if (syntheticForm.persist) reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setSyntheticResult({ error: failure.message });
      setSyntheticState('error');
    }
  };

  const downloadSyntheticCsv = () => {
    if (!syntheticResult?.csv) return;
    downloadBlob(new Blob([syntheticResult.csv], { type: 'text/csv;charset=utf-8' }), `synthetic-products-${sourceId}.csv`);
  };

  return (
    <Page
      title="Chi tiết nguồn"
      subtitle="Màn hình riêng cho thông tin và hành động của nguồn."
      actions={<><RouteLink to="/sources" navigate={navigate}>Về danh sách nguồn</RouteLink><button onClick={collectSource} disabled={collectState === 'loading'}><Play />{collectState === 'loading' ? 'Đang thu thập...' : 'Chạy thu thập'}</button><button onClick={generateAiReviewList} disabled={reviewState === 'loading' || !discovery.data?.domain}><Sparkles />{reviewState === 'loading' ? 'Đang sinh danh sách...' : 'Sinh danh sách AI'}</button><button onClick={() => { reload(); reloadDiscovery(); reloadRuns(); reloadArtifactPreview(); }}><RefreshCw />Tải lại</button></>}
    >
      <StatePanel resource={resource} onRetry={reload} empty={!source}>
        <div className="detail-route-grid">
          <Panel title="Hồ sơ nguồn">
            {collectNotice ? <p className={`route-notice ${collectNotice.tone}`}>{collectNotice.text}</p> : null}
            <dl className="route-dl">
              <dt>Tên</dt><dd>{source?.name}</dd>
              <dt>Tên miền</dt><dd>{hostFromUrl(source?.url)}</dd>
              <dt>Loại</dt><dd>{sourceTypeLabel(source?.type)}</dd>
              <dt>Danh mục</dt><dd>{source?.category}</dd>
              <dt>Ghi chú</dt><dd>{source?.note || 'Chưa có ghi chú'}</dd>
            </dl>
          </Panel>
          <Panel title="Lịch sử thu thập">
            <StatePanel resource={runs} onRetry={reloadRuns} empty={!runs.data?.length}>
              <TableShell className="pipeline-table-wrapper" tableClassName="pipeline-table pipeline-table--runs">
                <thead><tr><th>Lượt chạy</th><th>Trạng thái</th><th>Trang thô</th><th>Rule AI</th><th>Cập nhật</th></tr></thead>
                <tbody>
                  {(runs.data || []).map((run) => {
                    const summary = run.summary || {};
                    return (
                      <tr key={run.id}>
                        <td><b>{run.id}</b><small>{run.mode}</small></td>
                        <td><Pill tone={run.status === 'completed' ? 'good' : run.status === 'failed' ? 'bad' : 'warning'}>{run.status}</Pill></td>
                        <td>{summary.raw_artifacts || 0}</td>
                        <td>{summary.ai_accepted || 0}/{summary.ai_attempts || 0}<small>{summary.rules_saved || 0} rule lưu</small></td>
                        <td>{run.updated_at ? new Date(run.updated_at).toLocaleString() : '-'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </TableShell>
            </StatePanel>
          </Panel>
          <Panel title="Phát hiện dữ liệu">
            <StatePanel resource={discovery} onRetry={reloadDiscovery} empty={!discovery.data}>
              <dl className="route-dl">
                <dt>Tên miền</dt><dd>{discovery.data?.domain || '-'}</dd>
                <dt>Trang thô</dt><dd>{discovery.data?.summary?.raw_artifact_count || 0}</dd>
                <dt>Quy tắc</dt><dd><Pill tone={discovery.data?.summary?.has_rule ? 'good' : 'warning'}>{discovery.data?.summary?.has_rule ? 'Đã cấu hình' : 'Chưa có'}</Pill></dd>
                <dt>Mục tiêu</dt><dd>{discovery.data?.rule?.targets?.length ? discovery.data.rule.targets.map(extractionTargetLabel).join(', ') : '-'}</dd>
              </dl>
              {discovery.data?.raw_artifacts?.length ? (
                <table>
                  <thead><tr><th>Trang thô</th><th>Loại</th><th>Cập nhật</th><th>Xem</th></tr></thead>
                  <tbody>
                    {discovery.data.raw_artifacts.slice(0, 6).map((item) => (
                      <tr key={item.id}>
                        <td>{item.filename}</td>
                        <td>{extractionTargetLabel(item.page_type)}</td>
                        <td>{item.updated_at ? new Date(item.updated_at).toLocaleString() : '-'}</td>
                        <td><button onClick={() => setArtifactId(item.id)}>Xem</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="route-state empty"><FileSearch />Nguồn này chưa có trang thô để kiểm thử selector.</div>
              )}
            </StatePanel>
          </Panel>
          <Panel title="Xem trước trang thô">
            <StatePanel resource={artifactPreview} onRetry={reloadArtifactPreview} empty={!selectedArtifact}>
              <dl className="route-dl">
                <dt>Tệp</dt><dd>{artifactPreview.data?.raw_page?.filename || selectedArtifact?.filename || '-'}</dd>
                <dt>URL</dt><dd>{artifactPreview.data?.raw_page?.url || '-'}</dd>
                <dt>Kích thước HTML</dt><dd>{Number(artifactPreview.data?.content_length || 0).toLocaleString()} ký tự</dd>
              </dl>
              <pre>{artifactPreview.data?.text_preview || 'Không có nội dung văn bản để xem trước.'}</pre>
            </StatePanel>
          </Panel>
          <Panel title="Hành động tiếp theo" className="route-shortcuts" actions={<button onClick={runGeminiAnalysis} disabled={analysisState === 'loading' || !discovery.data?.domain}><Sparkles />{analysisState === 'loading' ? 'Đang phân tích...' : 'Phân tích bằng Gemini'}</button>}>
            <RouteLink to="/extraction/rules" navigate={navigate}>Sửa quy tắc trích xuất</RouteLink>
            <RouteLink to="/products" navigate={navigate}>Kiểm tra sản phẩm</RouteLink>
          </Panel>
          <Panel title="Gen dữ liệu thay thế" actions={<><button onClick={generateSyntheticData} disabled={syntheticState === 'loading'}><Sparkles />{syntheticState === 'loading' ? 'Đang sinh...' : 'Sinh dữ liệu'}</button>{syntheticResult?.csv ? <button onClick={downloadSyntheticCsv}><Download />Tải CSV</button> : null}</>}>
            <div className="synthetic-form-grid">
              <label className="pipeline-field"><span>Số dòng</span><input type="number" min="1" max="200" value={syntheticForm.rowCount} onChange={(event) => setSyntheticForm({ ...syntheticForm, rowCount: event.target.value })} /></label>
              <label className="pipeline-field"><span>Khu vực</span><input value={syntheticForm.region} onChange={(event) => setSyntheticForm({ ...syntheticForm, region: event.target.value })} /></label>
              <label className="pipeline-field pipeline-field--wide"><span>Loại sản phẩm</span><textarea value={syntheticForm.productTypes} onChange={(event) => setSyntheticForm({ ...syntheticForm, productTypes: event.target.value })} /></label>
              <label className="pipeline-field pipeline-field--wide"><span>Nguồn tham khảo</span><textarea value={syntheticForm.referenceSources} onChange={(event) => setSyntheticForm({ ...syntheticForm, referenceSources: event.target.value })} /></label>
              <label className="pipeline-field pipeline-field--wide"><span>Cột đầu ra</span><textarea value={syntheticForm.outputColumns} onChange={(event) => setSyntheticForm({ ...syntheticForm, outputColumns: event.target.value })} /></label>
              <label className="pipeline-field pipeline-checkbox"><input type="checkbox" checked={syntheticForm.persist} onChange={(event) => setSyntheticForm({ ...syntheticForm, persist: event.target.checked })} /><span>Lưu vào danh sách sản phẩm</span></label>
            </div>
            {syntheticState === 'idle' ? (
              <div className="route-state empty"><FileSearch />Dùng khi nguồn bị chặn, trang động hoặc không thể tự động thu thập.</div>
            ) : syntheticState === 'loading' ? (
              <div className="route-state loading"><RefreshCw />Đang sinh bảng dữ liệu theo prompt...</div>
            ) : syntheticResult?.error ? (
              <div className="route-state error"><AlertTriangle />Không sinh được dữ liệu.<span>{syntheticResult.error}</span></div>
            ) : (
              <div className="synthetic-result">
                <dl className="route-dl">
                  <dt>Số dòng</dt><dd>{syntheticResult?.summary?.total || 0}</dd>
                  <dt>Model</dt><dd>{syntheticResult?.model || '-'}</dd>
                  <dt>Đã lưu</dt><dd>{syntheticResult?.persisted ? `${syntheticResult.persisted.products || 0} sản phẩm` : 'Chưa lưu'}</dd>
                </dl>
                <pre>{syntheticResult?.markdown}</pre>
                <pre>{syntheticResult?.csv}</pre>
              </div>
            )}
          </Panel>
          <Panel title="Kết quả Gemini">
            {analysisState === 'idle' ? (
              <div className="route-state empty"><FileSearch />Chưa chạy phân tích nguồn này.</div>
            ) : analysisState === 'loading' ? (
              <div className="route-state loading"><RefreshCw />Đang tạo draft rule từ HTML...</div>
            ) : analysis?.error ? (
              <div className="route-state error"><AlertTriangle />Không chạy được phân tích.<span>{analysis.error}</span></div>
            ) : (
              <div className="detail-route-grid">
                <dl className="route-dl">
                  <dt>Model</dt><dd>{analysis?.model || '-'}</dd>
                  <dt>Trạng thái</dt><dd><Pill tone={analysis?.validation?.accepted ? 'good' : 'warning'}>{analysis?.validation?.accepted ? 'Đạt kiểm tra' : 'Cần xem lại'}</Pill></dd>
                  <dt>Domain</dt><dd>{analysis?.domain || '-'}</dd>
                </dl>
                <pre>{JSON.stringify(analysis?.draft || {}, null, 2)}</pre>
                <pre>{JSON.stringify(analysis?.validation || {}, null, 2)}</pre>
              </div>
            )}
          </Panel>
          <Panel title="Danh sách AI">
            {reviewState === 'idle' ? (
              <div className="route-state empty"><FileSearch />Chưa sinh danh sách AI cho nguồn này.</div>
            ) : reviewState === 'loading' ? (
              <div className="route-state loading"><RefreshCw />Đang tạo danh sách ứng viên để duyệt tay...</div>
            ) : reviewResult?.error ? (
              <div className="route-state error"><AlertTriangle />Không sinh được danh sách.<span>{reviewResult.error}</span></div>
            ) : (
              <div className="detail-route-grid">
                <dl className="route-dl">
                  <dt>Tổng ứng viên</dt><dd>{reviewResult?.summary?.total || 0}</dd>
                  <dt>Cần rà soát</dt><dd>{reviewResult?.summary?.needs_review || 0}</dd>
                  <dt>Model</dt><dd>{reviewResult?.model || '-'}</dd>
                </dl>
                <table>
                  <thead><tr><th>Loại</th><th>Ứng viên</th><th>Độ tin cậy</th><th>Lý do</th></tr></thead>
                  <tbody>
                    {(reviewResult?.review_items || []).slice(0, 8).map((item) => (
                      <tr key={item.review_id}>
                        <td>{item.entity_type}</td>
                        <td>
                          <b>{item.payload?.name || item.payload?.store_name || '-'}</b>
                          <small className="dedup-compare">{item.payload?.url || item.raw_page_url || '-'}</small>
                        </td>
                        <td>{Math.round((Number(item.confidence || 0) * 100))}%</td>
                        <td>{item.reason || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>
      </StatePanel>
    </Page>
  );
}

export function AiReviewPage({ navigate }) {
  const [status, setStatus] = useState('needs_review');
  const [domain, setDomain] = useState('all');
  const [notice, setNotice] = useState(null);
  const [resource, reload] = useApiResource(
    () => Promise.all([
      fetchApiList('/extraction/ai/review-items', { params: { status, domain: domain === 'all' ? undefined : domain, limit: 80 } }),
      fetchApiList('/sources'),
    ]).then(([items, sources]) => ({ items, sources })),
    [status, domain]
  );
  const items = resource.data?.items || [];
  const domains = ['all', ...(resource.data?.sources || []).map((item) => hostFromUrl(item.url || item.domain || ''))];

  const decide = async (item, action) => {
    try {
      if (action === 'approved') {
        await axios.post(`${API_BASE}/extraction/ai/review-items/${item.review_id}/publish`);
      } else {
        await axios.patch(`${API_BASE}/extraction/ai/review-items/${item.review_id}`, { status: action });
      }
      setNotice({ tone: 'good', text: `Đã ghi trạng thái ${action} cho ${item.payload?.name || item.review_id}.` });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };

  return <Page title="AI duyệt tay" subtitle="Danh sách ứng viên do AI sinh ra để đội của bạn rà soát và công bố." actions={<><select value={status} onChange={(event) => setStatus(event.target.value)}>{['needs_review', 'approved', 'rejected', 'all'].map((item) => <option key={item} value={item}>{dedupStatusLabel(item)}</option>)}</select><select value={domain} onChange={(event) => setDomain(event.target.value)}>{domains.map((item) => <option key={item} value={item}>{item === 'all' ? 'Tất cả nguồn' : item}</option>)}</select><button onClick={reload}><RefreshCw />Tải lại</button></>}><Panel title="Hàng đợi AI">{notice ? <p className={`route-notice ${notice.tone}`}>{notice.text}</p> : null}<StatePanel resource={resource} onRetry={reload} empty={!items.length}><table><thead><tr><th>Ứng viên</th><th>Loại</th><th>Độ tin cậy</th><th>Lý do</th><th>Trạng thái</th><th>Xử lý</th></tr></thead><tbody>{items.map((item) => <tr key={item.review_id}><td><b>{item.payload?.name || item.payload?.store_name || '-'}</b><small className="dedup-compare">{item.payload?.url || item.raw_page_url || '-'}</small></td><td>{item.entity_type}</td><td>{Math.round(Number(item.confidence || 0) * 100)}%</td><td>{item.reason || '-'}</td><td><Pill tone={item.status === 'approved' ? 'good' : item.status === 'rejected' ? 'bad' : 'warning'}>{item.status}</Pill></td><td><button onClick={() => decide(item, 'approved')}><Check />Duyệt & công bố</button><button onClick={() => decide(item, 'rejected')}><X />Loại</button><button onClick={() => decide(item, 'needs_review')}><RefreshCw />Giữ rà soát</button></td></tr>)}</tbody></table></StatePanel></Panel></Page>;
}

export function RunsPage({ navigate }) {
  const [resource, reload] = useApiResource(() => fetchApiList('/jobs'), []);
  const jobs = resource.data || [];
  const totals = useMemo(() => ({ pending: jobs.filter((job) => job.status === 'Pending').length, failed: jobs.filter((job) => job.status === 'Failed').length, completed: jobs.filter((job) => job.status === 'Completed').length }), [jobs]);
  return <Page title="Lượt chạy" subtitle="Theo dõi tác vụ từ kho trang thô và kho đầu ra." actions={<button onClick={reload}><RefreshCw />Tải lại</button>}><div className="route-stats compact"><Stat label="Hoàn tất" value={totals.completed} note="lượt chạy" /><Stat label="Đang chờ" value={totals.pending} note="lượt chạy" tone="warning" /><Stat label="Thất bại" value={totals.failed} note="lượt chạy" tone="bad" /></div><Panel title="Danh sách lượt chạy"><StatePanel resource={resource} onRetry={reload} empty={!jobs.length}><JobRows jobs={jobs} navigate={navigate} /></StatePanel></Panel></Page>;
}

export function RunDetailPage({ jobId, navigate }) {
  const [resource, reload] = useApiResource(() => axios.get(`${API_BASE}/jobs/logs/${jobId}`).then((response) => {
    if (response.data?.error && !response.data?.events?.length) throw new Error(response.data.error);
    return response.data;
  }), [jobId]);
  const logs = resource.data;
  return <Page title="Chi tiết lượt chạy" subtitle={`Nhật ký thực tế của lượt chạy ${jobId}.`} actions={<><RouteLink to="/runs" navigate={navigate}>Quay lại</RouteLink><RouteLink to={`/tasks/${routeId(jobId)}/raw`} navigate={navigate}>Trang thô tác vụ</RouteLink><button onClick={reload}><RefreshCw />Tải lại</button></>}><StatePanel resource={resource} onRetry={reload} empty={!logs}><div className="detail-route-grid"><Panel title="Dòng thời gian">{logs?.events?.length ? logs.events.map((event) => <p className="event-line" key={event}>{event}</p>) : <p>Chưa có sự kiện.</p>}</Panel><Panel title="Tóm tắt đầu ra"><pre>{JSON.stringify(logs?.output_summary || {}, null, 2)}</pre></Panel><Panel title="Lỗi">{logs?.error ? <pre className="failure-pre">{logs.error}</pre> : <Pill tone="good">Không phát hiện tệp lỗi</Pill>}</Panel></div></StatePanel></Page>;
}

export function ProductsPage({ route = '/products' }) {
  const initialStore = useMemo(() => new URLSearchParams(route.split('?')[1] || '').get('store') || '', [route]);
  const [q, setQ] = useState('');
  const [source, setSource] = useState('all');
  const [store, setStore] = useState(initialStore);
  const [notice, setNotice] = useState(null);
  const [viewMode, setViewMode] = useState('table');
  useEffect(() => setStore(initialStore), [initialStore]);
  const [resource, reload] = useApiResource(() => Promise.all([fetchApiList('/products/search', { params: { q: q || undefined, source, store: store || undefined, category: 'all', limit: 80 } }), fetchApiList('/dashboard/sources')]).then(([products, sources]) => ({ products, sources })), [q, source, store]);
  const products = resource.data?.products || [];
  const downloadProducts = async () => {
    try {
      const response = await axios.get(`${API_BASE}/products/export`, { params: { q: q || undefined, source, store: store || undefined, category: 'all' }, responseType: 'blob' });
      downloadBlob(response.data, filenameFromDisposition(response.headers['content-disposition'], 'product-price-list.csv'));
      setNotice({ tone: 'good', text: 'Đã tải CSV sản phẩm và giá bán.' });
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };
  const content = viewMode === 'cards' ? <ProductGrid products={products} /> : viewMode === 'list' ? <ProductList products={products} /> : <ProductRows products={products} className="products-table-wrapper" tableClassName="products-table products-table--page" />;
  return <Page title="Sản phẩm & giá bán" subtitle="Dữ liệu sản phẩm và giá bán lấy trực tiếp từ API, có liên kết cửa hàng khi crawler thu thập được store fields." actions={<><label className="route-search"><Search /><input value={q} onChange={(event) => setQ(event.target.value)} placeholder="Tìm sản phẩm..." /></label><label className="route-search"><MapPin /><input value={store} onChange={(event) => setStore(event.target.value)} placeholder="Lọc theo cửa hàng..." /></label><select value={source} onChange={(event) => setSource(event.target.value)}>{(resource.data?.sources || ['all']).map((item) => <option key={item} value={item}>{item === 'all' ? 'Tất cả nguồn' : item}</option>)}</select><div className="route-segmented" role="group" aria-label="Kiểu hiển thị sản phẩm"><button className={viewMode === 'table' ? 'active' : ''} onClick={() => setViewMode('table')} title="Hiển thị dạng bảng"><Table2 />Bảng</button><button className={viewMode === 'list' ? 'active' : ''} onClick={() => setViewMode('list')} title="Hiển thị dạng danh sách"><List />Danh sách</button><button className={viewMode === 'cards' ? 'active' : ''} onClick={() => setViewMode('cards')} title="Hiển thị dạng thẻ"><LayoutGrid />Thẻ</button></div><button onClick={downloadProducts}><Download />Tải CSV</button><button onClick={reload}><RefreshCw />Tải lại</button></>}><div className="products-route-grid"><Panel title="Khám phá sản phẩm" className="products-panel">{notice ? <p className={`route-notice ${notice.tone}`}>{notice.text}</p> : null}<StatePanel resource={resource} onRetry={reload} empty={!products.length}>{content}</StatePanel></Panel></div></Page>;
}

function PreviewRows({ rows }) {
  return <table className="selector-preview-table"><thead><tr><th>Trường</th><th>Số khớp</th><th>Mẫu</th></tr></thead><tbody>{rows.map((row) => <tr key={row.name}><td>{row.name}</td><td><Pill tone={row.matches ? 'good' : row.required ? 'bad' : 'warning'}>{row.matches}</Pill></td><td>{row.sample || '-'}</td></tr>)}</tbody></table>;
}

export function ExtractionRulesPage() {
  const [domain, setDomain] = useState('');
  const [target, setTarget] = useState('product_detail');
  const [artifactId, setArtifactId] = useState('');
  const [fields, setFields] = useState([]);
  const [previewRows, setPreviewRows] = useState([]);
  const [notice, setNotice] = useState(null);
  const [rules, reloadRules] = useApiResource(() => fetchApiList('/extraction/rules'), []);
  useEffect(() => {
    if (!domain && rules.data?.length) setDomain(rules.data[0].domain);
  }, [domain, rules.data]);
  const [rule, reloadRule] = useApiResource(() => domain ? axios.get(`${API_BASE}/extraction/rules/${domain}`, { params: { target, raw_artifact_id: artifactId || undefined } }).then((response) => response.data) : Promise.resolve(null), [domain, target, artifactId]);
  useEffect(() => {
    if (rule.data?.target && rule.data.target !== target) setTarget(rule.data.target);
    setFields(rule.data?.fields || []);
    setPreviewRows(rule.data?.preview || []);
    if (!artifactId && rule.data?.raw_page?.id) setArtifactId(rule.data.raw_page.id);
  }, [artifactId, rule.data, target]);
  const selectDomain = (nextDomain) => {
    setDomain(nextDomain);
    setTarget('product_detail');
    setArtifactId('');
  };
  const updateField = (name, selector) => setFields((current) => current.map((field) => field.name === name ? { ...field, selector } : field));
  const testRule = async () => {
    try {
      const response = await axios.post(`${API_BASE}/extraction/rules/${domain}/preview`, { target, fields, raw_artifact_id: artifactId || undefined });
      setPreviewRows(response.data.preview || []);
      setNotice({ tone: 'good', text: `Đã kiểm thử xem trước với ${response.data.raw_page?.filename || 'trang thô trống'}.` });
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };
  const saveRule = async () => {
    try {
      await axios.patch(`${API_BASE}/extraction/rules/${domain}`, { target, fields, expected_version: rule.data.version, raw_artifact_id: artifactId || undefined });
      setNotice({ tone: 'good', text: 'Đã lưu quy tắc selector vào bộ nhớ cấu trúc.' });
      reloadRule();
      reloadRules();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };
  return <Page title="Trình dựng quy tắc trích xuất" subtitle="Chọn trang thô, kiểm thử selector và lưu quy tắc theo tên miền." actions={<><select value={domain} onChange={(event) => selectDomain(event.target.value)}>{(rules.data || []).map((item) => <option key={item.domain}>{item.domain}</option>)}</select><select value={target} onChange={(event) => setTarget(event.target.value)}>{(rule.data?.targets || ['product_detail']).map((item) => <option key={item} value={item}>{extractionTargetLabel(item)}</option>)}</select><select value={artifactId} onChange={(event) => setArtifactId(event.target.value)}><option value="">Trang thô mới nhất</option>{(rule.data?.raw_artifacts || []).map((item) => <option key={item.id} value={item.id}>{item.filename}</option>)}</select><button onClick={reloadRule}><RefreshCw />Tải lại</button></>}><StatePanel resource={rules} onRetry={reloadRules} empty={!rules.data?.length}><StatePanel resource={rule} onRetry={reloadRule} empty={!rule.data}><div className="builder-route-grid live-rule-grid"><Panel title="Mục tiêu">{fields.map((field) => <label className="selector-field" key={field.name}>{field.name}{field.required ? <Pill tone="warning">bắt buộc</Pill> : null}<input value={field.selector || ''} onChange={(event) => updateField(field.name, event.target.value)} /></label>)}</Panel><Panel title="Xem trước trang thô" className="rule-raw-panel">{rule.data?.raw_page ? <dl className="route-dl"><dt>Tệp</dt><dd>{rule.data.raw_page.filename}</dd><dt>Tác vụ</dt><dd>{rule.data.raw_page.task_id}</dd><dt>Loại trang</dt><dd>{extractionTargetLabel(rule.data.raw_page.page_type)}</dd><dt>Đường dẫn</dt><dd>{rule.data.raw_page.path}</dd><dt>Cập nhật</dt><dd>{new Date(rule.data.raw_page.updated_at).toLocaleString()}</dd></dl> : <div className="route-state empty"><FileSearch />Tên miền này chưa có MHTML thô để kiểm thử selector.</div>}<pre>{JSON.stringify({ target, fields, version: rule.data?.version }, null, 2)}</pre></Panel><Panel title="Xem trước selector" actions={<><button onClick={testRule}>Kiểm thử</button><button onClick={saveRule}>Lưu quy tắc</button></>}>{notice ? <p className={`route-notice ${notice.tone}`}>{notice.text}</p> : null}<PreviewRows rows={previewRows} /></Panel></div></StatePanel></StatePanel></Page>;
}

export function TaskRawPage({ jobId, navigate }) {
  const [latest, latestReload] = useApiResource(() => fetchApiList('/jobs?limit=1').then((jobs) => jobs[0]), []);
  const resolvedId = jobId === 'latest' ? latest.data?.id : jobId;
  const [resource, reload] = useApiResource(() => resolvedId ? axios.get(`${API_BASE}/jobs/logs/${resolvedId}`).then((response) => response.data) : Promise.resolve(null), [resolvedId]);
  if (jobId === 'latest' && latest.status !== 'ready') return <Page title="Xem trang thô tác vụ" subtitle="Đang tìm tác vụ mới nhất."><StatePanel resource={latest} onRetry={latestReload} empty={false} /></Page>;
  return <Page title="Xem trang thô tác vụ" subtitle={`Siêu dữ liệu và tệp trích xuất của tác vụ ${resolvedId || 'không rõ'}.`} actions={<RouteLink to={`/runs/${routeId(resolvedId || 'unknown')}`} navigate={navigate}>Mở chi tiết lượt chạy</RouteLink>}><StatePanel resource={resource} onRetry={reload} empty={!resource.data}><div className="raw-route-grid"><Panel title="Siêu dữ liệu"><pre>{JSON.stringify(resource.data?.metadata || {}, null, 2)}</pre></Panel><Panel title="Sự kiện"><pre>{(resource.data?.events || []).join('\n')}</pre></Panel><Panel title="Đầu ra"><pre>{JSON.stringify(resource.data?.output_summary || {}, null, 2)}</pre></Panel></div></StatePanel></Page>;
}

export function DedupPage() {
  const [notice, setNotice] = useState(null);
  const [status, setStatus] = useState('pending');
  const [resource, reload] = useApiResource(() => fetchApiList('/dedup/candidates', { params: { limit: 24, status } }), [status]);
  const decide = async (candidate, decision) => {
    try {
      await axios.post(`${API_BASE}/dedup/candidates/${candidate.id}/decision`, { status: decision });
      setNotice({ tone: 'good', text: `Đã ghi trạng thái ${dedupStatusLabel(decision).toLowerCase()} cho ${candidate.left.name}.` });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };
  const refreshCandidates = async () => {
    try {
      const response = await axios.post(`${API_BASE}/dedup/candidates/refresh`);
      setNotice({ tone: 'good', text: `Đã làm mới ${response.data.candidate_count} ứng viên trùng lặp.` });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };
  return <Page title="Rà soát trùng lặp" subtitle="Hàng đợi trùng lặp có trạng thái thực từ dữ liệu đầu ra." actions={<><select value={status} onChange={(event) => setStatus(event.target.value)}>{['pending', 'merged', 'rejected', 'needs_review', 'all'].map((item) => <option key={item} value={item}>{dedupStatusLabel(item)}</option>)}</select><button onClick={refreshCandidates}><RefreshCw />Tính lại ứng viên</button><button onClick={reload}><RefreshCw />Tải lại</button></>}><Panel title="Ứng viên trùng lặp">{notice ? <p className={`route-notice ${notice.tone}`}>{notice.text}</p> : null}<StatePanel resource={resource} onRetry={reload} empty={!resource.data?.length}><table><thead><tr><th>Ứng viên</th><th>Nguồn</th><th>Trạng thái</th><th>Độ tin cậy</th><th>Lý do</th><th>Quyết định</th></tr></thead><tbody>{(resource.data || []).map((candidate) => <tr key={candidate.id}><td><b>{candidate.left.name}</b><small className="dedup-compare">{candidate.right.name}</small></td><td>{candidate.left.source}<small className="dedup-compare">{candidate.right.source}</small></td><td><Pill tone={candidate.status === 'merged' ? 'good' : candidate.status === 'rejected' ? 'bad' : 'warning'}>{dedupStatusLabel(candidate.status)}</Pill></td><td>{Math.round(candidate.confidence * 100)}%</td><td>{candidate.reasons.join(', ')}</td><td><button onClick={() => decide(candidate, 'merged')}>Gộp</button><button onClick={() => decide(candidate, 'rejected')}>Loại</button><button onClick={() => decide(candidate, 'needs_review')}>Rà soát</button></td></tr>)}</tbody></table></StatePanel></Panel></Page>;
}

export function UnknownPage({ navigate }) {
  return <Page title="Không tìm thấy" subtitle="Đường dẫn này không tồn tại."><Panel title="Quay lại"><RouteLink to="/dashboard" navigate={navigate}>Về trang tổng quan</RouteLink></Panel></Page>;
}

export function RuleReviewPage({ navigate }) {
  const [status, setStatus] = useState('pending');
  const [resource, reload] = useApiResource(() => fetchApiList(`/extraction/rules/candidates?status=${status}`), [status]);
  const [notice, setNotice] = useState(null);

  const promote = async (candidate) => {
    try {
      await axios.post(`${API_BASE}/extraction/rules/candidates/${candidate.candidate_id}/promote`);
      setNotice({ tone: 'good', text: `Đã duyệt rule thành công cho domain ${candidate.domain}` });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };

  return (
    <Page title="Duyệt Rule AI (Quarantine)" subtitle="Danh sách Rule Candidate (ứng viên) do Gemini sinh ra, đang chờ duyệt để chính thức áp dụng cho Crawler." actions={<><button onClick={reload}><RefreshCw />Tải lại</button></>}>
      {notice ? <p className={`route-notice ${notice.tone}`}>{notice.text}</p> : null}
      <div className="ops-tabs" style={{ marginBottom: '16px', gap: '8px', display: 'flex' }}>
        <button className={status === 'pending' ? 'active' : ''} onClick={() => setStatus('pending')}>Đang chờ duyệt</button>
        <button className={status === 'promoted' ? 'active' : ''} onClick={() => setStatus('promoted')}>Đã duyệt</button>
      </div>
      <Panel title={`Danh sách ứng viên (${status})`}>
        <StatePanel resource={resource} onRetry={reload} empty={!resource.data?.length}>
          <TableShell>
            <thead><tr><th>Domain</th><th>Model</th><th>Điểm chất lượng</th><th>Đối tượng (Targets)</th><th>Ngày tạo</th><th>Thao tác</th></tr></thead>
            <tbody>
              {(resource.data || []).map(c => (
                <tr key={c.candidate_id}>
                  <td><b>{c.domain}</b></td>
                  <td>{c.model || 'Gemini'}</td>
                  <td><Pill tone={c.quality?.score >= 0.72 ? 'good' : 'warning'}>{Math.round((c.quality?.score || 0)*100)}%</Pill></td>
                  <td>{Object.keys(c.quality?.targets || {}).join(', ')}</td>
                  <td>{new Date(c.created_at).toLocaleString()}</td>
                  <td>
                    {status === 'pending' && <button className="primary-action-sm" onClick={() => promote(c)}><Check /> Duyệt Rule</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        </StatePanel>
      </Panel>
    </Page>
  );
}


// Note: Some lucide-react icons might need to be imported in the actual file.

// Mock data or we can use useApiResource
export function PipelinesPage({ navigate }) {
  const [resource, reload] = useApiResource(() => fetchApiList('/pipelines'), []);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [filter, setFilter] = useState('all');

  // We assume useApiResource gives us data.pipelines
  const pipelines = resource.data?.pipelines || [];
  
  // KPI stats (mock calculation for now, normally from API)
  const total = pipelines.length;
  const active = pipelines.filter(p => p.enabled).length;
  const running = pipelines.filter(p => p.status === 'running').length;
  const successToday = '88.9%'; // Example

  return (
    <Page 
      title="Tự động thu thập" 
      subtitle="Quản lý pipeline crawler và lịch chạy"
      actions={
        <>
          <button onClick={reload}><RefreshCw />Làm mới</button>
          <button className="primary" onClick={() => setDrawerOpen(true)}><Plus />Pipeline mới</button>
        </>
      }
    >
      <div className="kpi-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
        <Stat label="Pipeline" value={total} note="Tổng số" tone="neutral" />
        <Stat label="Đang bật" value={active} note="Kích hoạt" tone="good" />
        <Stat label="Đang chạy" value={running} note="Thời gian thực" tone="warning" />
        <Stat label="Thành công hôm nay" value={successToday} note="Tỷ lệ" tone="good" />
      </div>

      <Panel title="Pipeline" actions={<label className="route-search"><Search /><input placeholder="Tìm kiếm..." /></label>}>
        <div className="ops-tabs" style={{ marginBottom: '16px', gap: '8px', display: 'flex' }}>
          <button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>Tất cả</button>
          <button className={filter === 'running' ? 'active' : ''} onClick={() => setFilter('running')}>Đang chạy</button>
          <button className={filter === 'warning' ? 'active' : ''} onClick={() => setFilter('warning')}>Cảnh báo</button>
          <button className={filter === 'off' ? 'active' : ''} onClick={() => setFilter('off')}>Đã tắt</button>
        </div>

        <StatePanel resource={resource} onRetry={reload} empty={!pipelines.length}>
          <TableShell>
            <thead>
              <tr>
                <th>Tên</th>
                <th>Nguồn</th>
                <th>Lịch</th>
                <th>Cấu hình</th>
                <th>Sức khỏe</th>
                <th>Lần chạy</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {pipelines.map(p => (
                <tr key={p.id}>
                  <td>
                    <b>{p.name}</b>
                    <br/><small>{p.id.slice(0,8)}...{p.id.slice(-5)}</small>
                  </td>
                  <td>{p.source_count || 1}</td>
                  <td>{p.cron ? 'Biểu thức cron' : 'Thủ công'}</td>
                  <td>
                    <Pill tone={p.enabled ? 'good' : 'neutral'}>{p.enabled ? 'Bật' : 'Tắt'}</Pill>
                  </td>
                  <td>
                    <Pill tone={p.status === 'running' ? 'warning' : p.status === 'blocked' ? 'bad' : 'good'}>
                      {p.status === 'running' ? 'Đang chạy' : p.status === 'blocked' ? 'Bị chặn' : 'Bình thường'}
                    </Pill>
                  </td>
                  <td>{p.last_run_at ? new Date(p.last_run_at).toLocaleString() : '-'}</td>
                  <td>
                    <button className="primary-action-sm"><Play /> Chạy ngay</button>
                    <button className="icon-action"><MoreVertical /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        </StatePanel>
      </Panel>

      {drawerOpen && (
        <div className="drawer-overlay" onClick={() => setDrawerOpen(false)} style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', justifyContent: 'flex-end' }}>
          <div className="drawer-content" onClick={e => e.stopPropagation()} style={{ width: '600px', backgroundColor: 'var(--color-bg-panel, #1e1e2e)', height: '100%', padding: '24px', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2>Tạo Pipeline mới</h2>
              <button onClick={() => setDrawerOpen(false)}><X /></button>
            </div>
            {/* Steps mock */}
            <div className="form-group">
              <label>Tên pipeline</label>
              <input type="text" placeholder="Ví dụ: Lấy dữ liệu Thế Giới Sữa" className="form-control" />
            </div>
            <div className="form-group" style={{ marginTop: '16px' }}>
              <label>Chế độ thu thập</label>
              <select className="form-control">
                <option>Kết hợp (Hybrid AI)</option>
                <option>Lược đồ dữ liệu tĩnh (Static Schema)</option>
              </select>
            </div>
            <div style={{ marginTop: '32px', textAlign: 'right' }}>
              <button onClick={() => setDrawerOpen(false)} style={{ marginRight: '8px' }}>Hủy</button>
              <button className="primary">Tạo Pipeline</button>
            </div>
          </div>
        </div>
      )}
    </Page>
  );
}


export function GenDataPage({ navigate }) {
  return (
    <Page title="Tạo dữ liệu" subtitle="(Đang phát triển)" actions={<></>}>
      <Panel title="Tính năng đang được xây dựng">
        <p>Tính năng này sẽ sớm ra mắt.</p>
      </Panel>
    </Page>
  );
}
