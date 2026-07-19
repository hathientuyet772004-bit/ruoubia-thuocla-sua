import React from 'react';
import { AlertTriangle, FileSearch, RefreshCw, ShieldAlert } from 'lucide-react';
import ProductCard from '../components/ProductCard';
import { routeId } from '../routeShell';
import { formatProductPrice, jobStatusLabel, priceStatus, priceStatusLabel, priceStatusTone, sourceTypeLabel, storeAddressLabel, storeLabel } from './utils';

export function Stat({ label, value, note, tone = 'good' }) {
  return <article className="route-stat"><span>{label}</span><strong>{value}</strong><small className={tone}>{note}</small></article>;
}

export function Pill({ children, tone = 'neutral' }) {
  return <span className={`ops-pill ${tone}`}>{children}</span>;
}

export function RouteLink({ to, navigate, children, className = '', style }) {
  return (
    <a href={to} className={className} style={style} onClick={(e) => { e.preventDefault(); navigate(to); }}>
      {children}
    </a>
  );
}

export function StatePanel({ resource, empty, onRetry, children }) {
  if (resource.status === 'loading') return <div className="route-state loading"><RefreshCw />Đang tải dữ liệu từ API...</div>;
  if (resource.status === 'permission') return <div className="route-state permission"><ShieldAlert />Không đủ quyền.<span>{resource.error}</span></div>;
  if (resource.status === 'error') return <div className="route-state error"><AlertTriangle />Không gọi được API.<span>{resource.error}</span><button onClick={onRetry}>Thử lại</button></div>;
  if (empty) return <div className="route-state empty"><FileSearch />Chưa có dữ liệu cho bộ lọc hiện tại.</div>;
  return children;
}

export function Page({ title, subtitle, actions, children }) {
  return (
    <section className="route-page">
      <header className="route-page-header">
        <div><h1>{title}</h1><p>{subtitle}</p></div>
        <div>{actions}</div>
      </header>
      {children}
    </section>
  );
}

export function Panel({ title, className = '', children, actions }) {
  return (
    <section className={`route-panel ${className}`}>
      <header><h2>{title}</h2>{actions}</header>
      {children}
    </section>
  );
}

export function TableShell({ className = '', tableClassName = '', children }) {
  return <div className={`table-wrapper ${className}`.trim()}><table className={tableClassName}>{children}</table></div>;
}

export function JobRows({ jobs, navigate, className = '', tableClassName = '' }) {
  return (
    <TableShell className={className} tableClassName={tableClassName}>
      <thead><tr><th>Lượt chạy / tác vụ</th><th>Nguồn</th><th>Trạng thái</th><th>Cập nhật</th><th>Trang thô</th></tr></thead>
      <tbody>
        {jobs.map((job) => (
          <tr key={job.id}>
            <td><RouteLink to={`/runs/${routeId(job.id)}`} navigate={navigate}>{job.filename || job.id}</RouteLink></td>
            <td>{job.source}</td>
            <td><Pill tone={job.status === 'Completed' ? 'good' : job.status === 'Failed' ? 'bad' : 'warning'}>{jobStatusLabel(job.status)}</Pill></td>
            <td>{new Date(job.timestamp).toLocaleString()}</td>
            <td><RouteLink to={`/tasks/${routeId(job.id)}/raw`} navigate={navigate}>Mở</RouteLink></td>
          </tr>
        ))}
      </tbody>
    </TableShell>
  );
}

export function ProductRows({ products, className = '', tableClassName = 'products-table' }) {
  return (
    <TableShell className={className} tableClassName={tableClassName}>
      <thead><tr><th>Tên sản phẩm</th><th>Mã ghép</th><th>Thương hiệu</th><th>Danh mục</th><th>Giá</th><th>Trạng thái giá</th><th>Cửa hàng / kênh bán</th><th>Nguồn</th><th>Cập nhật</th><th>URL</th></tr></thead>
      <tbody>
        {products.map((product, index) => {
          const status = priceStatus(product);
          return (
            <tr key={`${product.url || product.name}-${index}`}>
              <td className="product-name-cell" title={product.name || ''}>{product.name || 'Sản phẩm chưa có tên'}</td>
              <td title={product.canonical_key || ''}><code>{product.canonical_product_id || '-'}</code></td>
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
        })}
      </tbody>
    </TableShell>
  );
}

export function ProductGrid({ products }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '20px', padding: '16px 0' }}>
      {products.map((product, index) => (
        <ProductCard key={`${product.url || product.name}-${index}`} product={product} />
      ))}
    </div>
  );
}

export function ProductList({ products }) {
  return (
    <div className="product-list-view">
      {products.map((product, index) => {
        const status = priceStatus(product);
        return (
          <article key={`${product.url || product.name}-${index}`}>
            <div>
              <b>{product.name || 'Sản phẩm chưa có tên'}</b>
              <span>{storeLabel(product) || 'Chưa liên kết cửa hàng'} · {storeAddressLabel(product)} · {product.source || product.source_site || '-'} · {product.category || '-'}</span>
            </div>
            <strong className={status === 'FOUND' ? '' : 'muted-cell'}>{formatProductPrice(product)}</strong>
            <Pill tone={priceStatusTone(status)}>{priceStatusLabel(status)}</Pill>
            <a href={product.url || '#'} target="_blank" rel="noreferrer">Mở nguồn</a>
          </article>
        );
      })}
    </div>
  );
}

export function SourceRows({ sources, navigate, onCollect, collectingId }) {
  return (
    <TableShell>
      <thead><tr><th>Tên nguồn</th><th>Loại</th><th>Danh mục</th><th>URL</th><th>Dữ liệu</th><th>Sản phẩm</th><th>Cách ly</th><th>Hành động</th></tr></thead>
      <tbody>
        {sources.map((source) => (
          <tr key={source.id}>
            <td><RouteLink to={`/sources/${source.id}`} navigate={navigate}>{source.name || source.url}</RouteLink></td>
            <td><Pill>{sourceTypeLabel(source.type)}</Pill></td>
            <td>{source.category || '-'}</td>
            <td><a className="source-link" href={source.url} target="_blank" rel="noreferrer">{new URL(source.url).hostname.replace(/^www\./, '')}</a></td>
            <td><Pill tone={source.has_raw_data ? 'good' : 'warning'}>{source.has_raw_data ? 'Có trang thô' : 'Chưa có'}</Pill></td>
            <td>{Number(source.product_count || 0).toLocaleString('vi-VN')}</td>
            <td><Pill tone={source.quarantine_count ? 'warning' : 'neutral'}>{Number(source.quarantine_count || 0).toLocaleString('vi-VN')}</Pill></td>
            <td>
              <button disabled={collectingId === source.id} onClick={() => onCollect(source)}>
                {collectingId === source.id ? 'Đang thu thập...' : 'Chạy'}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </TableShell>
  );
}
