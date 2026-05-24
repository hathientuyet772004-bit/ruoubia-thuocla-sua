import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import {
  AlertTriangle,
  Boxes,
  ChevronRight,
  Download,
  FileSearch,
  Globe,
  LayoutGrid,
  List,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  Table2,
  Upload
} from 'lucide-react';
import ProductCard from '../components/ProductCard';
import { classifyApiError, expectApiList, fetchApiList } from '../apiClient';
import { routeId } from '../routeShell';

const API_BASE = '/api';

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

function dedupStatusLabel(status) {
  return ({ pending: 'Đang chờ', merged: 'Đã gộp', rejected: 'Đã loại', needs_review: 'Cần rà soát', all: 'Tất cả' })[status] || status;
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

function Panel({ title, className = '', children, actions }) {
  return <section className={`route-panel ${className}`}><header><h2>{title}</h2>{actions}</header>{children}</section>;
}

function SourceRows({ sources, navigate }) {
  return <table><thead><tr><th>Tên</th><th>Tên miền</th><th>Loại</th><th>Danh mục</th><th>Dữ liệu cục bộ</th></tr></thead><tbody>{sources.map((source) => <tr key={source.id}><td><RouteLink to={`/sources/${source.id}`} navigate={navigate}>{source.name}</RouteLink></td><td>{hostFromUrl(source.url)}</td><td>{sourceTypeLabel(source.type)}</td><td>{source.category || source.group || '-'}</td><td><Pill tone={source.saved_locally ? 'good' : 'warning'}>{source.saved_locally ? 'Đã có' : 'Chưa thu thập'}</Pill></td></tr>)}</tbody></table>;
}

function JobRows({ jobs, navigate }) {
  return <table><thead><tr><th>Lượt chạy / tác vụ</th><th>Nguồn</th><th>Trạng thái</th><th>Cập nhật</th><th>Trang thô</th></tr></thead><tbody>{jobs.map((job) => <tr key={job.id}><td><RouteLink to={`/runs/${routeId(job.id)}`} navigate={navigate}>{job.filename || job.id}</RouteLink></td><td>{job.source}</td><td><Pill tone={job.status === 'Completed' ? 'good' : job.status === 'Failed' ? 'bad' : 'warning'}>{jobStatusLabel(job.status)}</Pill></td><td>{new Date(job.timestamp).toLocaleString()}</td><td><RouteLink to={`/tasks/${routeId(job.id)}/raw`} navigate={navigate}>Mở</RouteLink></td></tr>)}</tbody></table>;
}

function ProductRows({ products }) {
  return <table><thead><tr><th>Sản phẩm</th><th>Nguồn</th><th>Danh mục</th><th>Giá</th><th>Cập nhật giá bán</th></tr></thead><tbody>{products.map((product, index) => <tr key={`${product.url || product.name}-${index}`}><td>{product.name || 'Sản phẩm chưa có tên'}</td><td>{product.source || product.source_site || '-'}</td><td>{product.category || '-'}</td><td>{Number(product.price ?? product.price_numeric ?? 0).toLocaleString()} VND</td><td>{product.updated_at ? new Date(product.updated_at).toLocaleString() : '-'}</td></tr>)}</tbody></table>;
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
  return <div className="product-list-view">{products.map((product, index) => <article key={`${product.url || product.name}-${index}`}><div><b>{product.name || 'Sản phẩm chưa có tên'}</b><span>{product.source || product.source_site || '-'} · {product.category || '-'}</span></div><strong>{Number(product.price ?? product.price_numeric ?? 0).toLocaleString()} VND</strong><a href={product.url || '#'} target="_blank" rel="noreferrer">Mở nguồn</a></article>)}</div>;
}

function StoreRows({ stores }) {
  return <table><thead><tr><th>Cửa hàng</th><th>Nguồn</th><th>Địa chỉ</th><th>Điện thoại</th><th>Cập nhật</th></tr></thead><tbody>{stores.map((store, index) => <tr key={`${store.id || store.url || store.name}-${index}`}><td>{store.name || 'Cửa hàng chưa có tên'}</td><td>{store.source || '-'}</td><td>{store.address || '-'}</td><td>{store.phone || '-'}</td><td>{store.updated_at ? new Date(store.updated_at).toLocaleString() : '-'}</td></tr>)}</tbody></table>;
}

function StoreList({ stores }) {
  return <div className="product-list-view">{stores.map((store, index) => <article key={`${store.id || store.url || store.name}-${index}`}><div><b>{store.name || 'Cửa hàng chưa có tên'}</b><span>{store.source || '-'} · {store.address || '-'}</span></div><strong>{store.phone || '-'}</strong><a href={store.url || '#'} target="_blank" rel="noreferrer">Mở nguồn</a></article>)}</div>;
}

export function DashboardPage({ navigate }) {
  const [resource, reload] = useApiResource(async () => {
    const [stats, sources, jobs, products] = await Promise.all([axios.get(`${API_BASE}/dashboard/stats`), fetchApiList('/sources'), fetchApiList('/jobs?limit=6'), fetchApiList('/dashboard/recent-products?limit=6')]);
    return { stats: stats.data, sources, jobs, products };
  }, []);
  const data = resource.data;
  const failed = data?.jobs?.filter((job) => job.status === 'Failed').length || 0;
  return <Page title="Tổng quan" subtitle="Các khối quan trọng để vào đúng luồng công việc tiếp theo." actions={<button onClick={reload}><RefreshCw />Làm mới</button>}><StatePanel resource={resource} onRetry={reload} empty={false}><div className="dashboard-route-grid"><div className="route-stats"><Stat label="Sản phẩm lớp Gold" value={(data?.stats?.products?.total || 0).toLocaleString()} note={`${data?.stats?.products?.sources || 0} nguồn`} /><Stat label="Nguồn đã đăng ký" value={data?.sources?.length || 0} note="Danh mục nguồn" /><Stat label="Tác vụ đang chờ" value={data?.stats?.files?.pending || 0} note="Hàng đợi Bronze" tone="warning" /><Stat label="Tệp đã xử lý" value={data?.stats?.files?.completed || 0} note="Kho đầu ra" /><Stat label="Tác vụ lỗi" value={data?.stats?.files?.failed || failed} note="Cần rà soát" tone="bad" /><Stat label="Giá trung bình" value={`${Number(data?.stats?.market?.avg_price || 0).toLocaleString()} VND`} note={data?.stats?.market?.trend || 'Dữ liệu thị trường'} /></div><Panel title="Lượt chạy gần đây" actions={<RouteLink to="/runs" navigate={navigate}>Tất cả <ChevronRight /></RouteLink>}><JobRows jobs={data?.jobs || []} navigate={navigate} /></Panel><Panel title="Sản phẩm và giá bán gần đây" actions={<RouteLink to="/products" navigate={navigate}>Mở danh sách <ChevronRight /></RouteLink>}><ProductRows products={data?.products || []} /></Panel><Panel title="Luồng quan trọng" className="route-shortcuts"><RouteLink to="/sources" navigate={navigate}><Globe />Danh mục nguồn</RouteLink><RouteLink to="/extraction/rules" navigate={navigate}><FileSearch />Quy tắc trích xuất</RouteLink><RouteLink to="/dedup" navigate={navigate}><Boxes />Rà soát trùng lặp</RouteLink></Panel></div></StatePanel></Page>;
}

export function SourcesPage({ navigate, onAdd }) {
  const [query, setQuery] = useState('');
  const [notice, setNotice] = useState(null);
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
  return <Page title="Nguồn dữ liệu" subtitle="Danh mục nguồn lấy trực tiếp từ API." actions={<><label className="route-search"><Search /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Lọc nguồn..." /></label><button onClick={() => downloadSourceFile('/sources/template', 'source-import-template.csv')}><Download />Mẫu thêm nguồn</button><button onClick={() => uploadInputRef.current?.click()}><Upload />Tải lên danh sách</button><input ref={uploadInputRef} className="hidden-file-input" type="file" accept=".csv,text/csv" onChange={uploadSources} /><button onClick={() => downloadSourceFile('/sources/export', 'source-list.csv')}><Download />Tải xuống danh sách</button><button onClick={reload}><RefreshCw />Tải lại</button><button onClick={onAdd}><Plus />Thêm nguồn</button></>}><Panel title="Danh mục nguồn">{notice ? <p className={`route-notice ${notice.tone}`}>{notice.text}</p> : null}<StatePanel resource={resource} onRetry={reload} empty={!sources.length}><SourceRows sources={sources} navigate={navigate} /></StatePanel></Panel></Page>;
}

export function SourceDetailPage({ sourceId, navigate }) {
  const [resource, reload] = useApiResource(() => fetchApiList('/sources'), [sourceId]);
  const source = resource.data?.find((item) => String(item.id) === String(sourceId));
  const [discovery, reloadDiscovery] = useApiResource(() => sourceId ? axios.get(`${API_BASE}/sources/${sourceId}/discovery`).then((response) => response.data) : Promise.resolve(null), [sourceId]);
  const [artifactId, setArtifactId] = useState('');
  useEffect(() => {
    const firstArtifact = discovery.data?.raw_artifacts?.[0]?.id;
    if (firstArtifact && !artifactId) setArtifactId(firstArtifact);
  }, [artifactId, discovery.data]);
  const selectedArtifact = discovery.data?.raw_artifacts?.find((item) => item.id === artifactId);
  const [artifactPreview, reloadArtifactPreview] = useApiResource(() => selectedArtifact ? axios.get(`${API_BASE}/extraction/raw-artifacts/${selectedArtifact.id}`, { params: { domain: discovery.data?.domain } }).then((response) => response.data) : Promise.resolve(null), [artifactId, discovery.data?.domain]);
  return <Page title="Chi tiết nguồn" subtitle="Màn hình riêng cho thông tin và hành động của nguồn." actions={<><RouteLink to="/sources" navigate={navigate}>Về danh sách nguồn</RouteLink><button onClick={() => { reload(); reloadDiscovery(); reloadArtifactPreview(); }}><RefreshCw />Tải lại</button></>}><StatePanel resource={resource} onRetry={reload} empty={!source}><div className="detail-route-grid"><Panel title="Hồ sơ nguồn"><dl className="route-dl"><dt>Tên</dt><dd>{source?.name}</dd><dt>Tên miền</dt><dd>{hostFromUrl(source?.url)}</dd><dt>Loại</dt><dd>{sourceTypeLabel(source?.type)}</dd><dt>Danh mục</dt><dd>{source?.category}</dd><dt>Ghi chú</dt><dd>{source?.note || 'Chưa có ghi chú'}</dd></dl></Panel><Panel title="Phát hiện dữ liệu"><StatePanel resource={discovery} onRetry={reloadDiscovery} empty={!discovery.data}><dl className="route-dl"><dt>Tên miền</dt><dd>{discovery.data?.domain || '-'}</dd><dt>Trang thô</dt><dd>{discovery.data?.summary?.raw_artifact_count || 0}</dd><dt>Quy tắc</dt><dd><Pill tone={discovery.data?.summary?.has_rule ? 'good' : 'warning'}>{discovery.data?.summary?.has_rule ? 'Đã cấu hình' : 'Chưa có'}</Pill></dd><dt>Mục tiêu</dt><dd>{discovery.data?.rule?.targets?.length ? discovery.data.rule.targets.map(extractionTargetLabel).join(', ') : '-'}</dd></dl>{discovery.data?.raw_artifacts?.length ? <table><thead><tr><th>Trang thô</th><th>Loại</th><th>Cập nhật</th><th>Xem</th></tr></thead><tbody>{discovery.data.raw_artifacts.slice(0, 6).map((item) => <tr key={item.id}><td>{item.filename}</td><td>{extractionTargetLabel(item.page_type)}</td><td>{item.updated_at ? new Date(item.updated_at).toLocaleString() : '-'}</td><td><button onClick={() => setArtifactId(item.id)}>Xem</button></td></tr>)}</tbody></table> : <div className="route-state empty"><FileSearch />Nguồn này chưa có trang thô để kiểm thử selector.</div>}</StatePanel></Panel><Panel title="Xem trước trang thô"><StatePanel resource={artifactPreview} onRetry={reloadArtifactPreview} empty={!selectedArtifact}><dl className="route-dl"><dt>Tệp</dt><dd>{artifactPreview.data?.raw_page?.filename || selectedArtifact?.filename || '-'}</dd><dt>URL</dt><dd>{artifactPreview.data?.raw_page?.url || '-'}</dd><dt>Kích thước HTML</dt><dd>{Number(artifactPreview.data?.content_length || 0).toLocaleString()} ký tự</dd></dl><pre>{artifactPreview.data?.text_preview || 'Không có nội dung văn bản để xem trước.'}</pre></StatePanel></Panel><Panel title="Hành động tiếp theo" className="route-shortcuts"><RouteLink to="/runs" navigate={navigate}>Xem lượt chạy</RouteLink><RouteLink to="/extraction/rules" navigate={navigate}>Sửa quy tắc trích xuất</RouteLink><RouteLink to="/products" navigate={navigate}>Kiểm tra sản phẩm</RouteLink></Panel></div></StatePanel></Page>;
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

export function ProductsPage() {
  const [q, setQ] = useState('');
  const [source, setSource] = useState('all');
  const [notice, setNotice] = useState(null);
  const [viewMode, setViewMode] = useState('table');
  const [resource, reload] = useApiResource(() => Promise.all([fetchApiList('/products/search', { params: { q: q || undefined, source, category: 'all', limit: 80 } }), fetchApiList('/dashboard/sources')]).then(([products, sources]) => ({ products, sources })), [q, source]);
  const products = resource.data?.products || [];
  const downloadProducts = async () => {
    try {
      const response = await axios.get(`${API_BASE}/products/export`, { params: { q: q || undefined, source, category: 'all' }, responseType: 'blob' });
      downloadBlob(response.data, filenameFromDisposition(response.headers['content-disposition'], 'product-price-list.csv'));
      setNotice({ tone: 'good', text: 'Đã tải CSV sản phẩm và giá bán.' });
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };
  const content = viewMode === 'cards' ? <ProductGrid products={products} /> : viewMode === 'list' ? <ProductList products={products} /> : <ProductRows products={products} />;
  return <Page title="Sản phẩm & giá bán" subtitle="Dữ liệu sản phẩm và giá bán lấy trực tiếp từ API." actions={<><label className="route-search"><Search /><input value={q} onChange={(event) => setQ(event.target.value)} placeholder="Tìm sản phẩm..." /></label><select value={source} onChange={(event) => setSource(event.target.value)}>{(resource.data?.sources || ['all']).map((item) => <option key={item} value={item}>{item === 'all' ? 'Tất cả nguồn' : item}</option>)}</select><div className="route-segmented" role="group" aria-label="Kiểu hiển thị sản phẩm"><button className={viewMode === 'table' ? 'active' : ''} onClick={() => setViewMode('table')} title="Hiển thị dạng bảng"><Table2 />Bảng</button><button className={viewMode === 'list' ? 'active' : ''} onClick={() => setViewMode('list')} title="Hiển thị dạng danh sách"><List />Danh sách</button><button className={viewMode === 'cards' ? 'active' : ''} onClick={() => setViewMode('cards')} title="Hiển thị dạng thẻ"><LayoutGrid />Thẻ</button></div><button onClick={downloadProducts}><Download />Tải CSV</button><button onClick={reload}><RefreshCw />Tải lại</button></>}><div className="products-route-grid" style={{ gridTemplateColumns: '1fr' }}><Panel title="Khám phá sản phẩm">{notice ? <p className={`route-notice ${notice.tone}`}>{notice.text}</p> : null}<StatePanel resource={resource} onRetry={reload} empty={!products.length}>{content}</StatePanel></Panel></div></Page>;
}

export function StoresPage() {
  const [q, setQ] = useState('');
  const [source, setSource] = useState('all');
  const [viewMode, setViewMode] = useState('table');
  const [notice, setNotice] = useState(null);
  const [resource, reload] = useApiResource(() => Promise.all([fetchApiList('/stores/search', { params: { q: q || undefined, source, limit: 200 } }), fetchApiList('/dashboard/sources')]).then(([stores, sources]) => ({ stores, sources })), [q, source]);
  const stores = resource.data?.stores || [];
  const downloadStores = async () => {
    try {
      const response = await axios.get(`${API_BASE}/stores/export`, { params: { q: q || undefined, source }, responseType: 'blob' });
      downloadBlob(response.data, filenameFromDisposition(response.headers['content-disposition'], 'store-list.csv'));
      setNotice({ tone: 'good', text: 'Đã tải CSV cửa hàng.' });
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };
  const content = viewMode === 'list' ? <StoreList stores={stores} /> : <StoreRows stores={stores} />;
  return <Page title="Cửa hàng" subtitle="Danh sách cửa hàng và địa điểm lấy từ sc_stores / sc_store_locations." actions={<><label className="route-search"><Search /><input value={q} onChange={(event) => setQ(event.target.value)} placeholder="Tìm cửa hàng..." /></label><select value={source} onChange={(event) => setSource(event.target.value)}>{(resource.data?.sources || ['all']).map((item) => <option key={item} value={item}>{item === 'all' ? 'Tất cả nguồn' : item}</option>)}</select><div className="route-segmented" role="group" aria-label="Kiểu hiển thị cửa hàng"><button className={viewMode === 'table' ? 'active' : ''} onClick={() => setViewMode('table')} title="Hiển thị dạng bảng"><Table2 />Bảng</button><button className={viewMode === 'list' ? 'active' : ''} onClick={() => setViewMode('list')} title="Hiển thị dạng danh sách"><List />Danh sách</button></div><button onClick={downloadStores}><Download />Tải CSV</button><button onClick={reload}><RefreshCw />Tải lại</button></>}><Panel title="Danh sách cửa hàng">{notice ? <p className={`route-notice ${notice.tone}`}>{notice.text}</p> : null}<StatePanel resource={resource} onRetry={reload} empty={!stores.length}>{content}</StatePanel></Panel></Page>;
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
