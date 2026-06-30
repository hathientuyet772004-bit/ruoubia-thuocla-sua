import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Download, LayoutGrid, List, MapPin, RefreshCw, Search, Table2 } from 'lucide-react';
import { classifyApiError, fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { downloadBlob, filenameFromDisposition } from '../shared/utils';
import { Page, Panel, ProductGrid, ProductList, ProductRows, StatePanel } from '../shared/ui';

const API_BASE = '/api';

export default function ProductsPage({ route = '/products' }) {
  const initialStore = useMemo(() => new URLSearchParams(route.split('?')[1] || '').get('store') || '', [route]);
  const [q, setQ] = useState('');
  const [source, setSource] = useState('all');
  const [store, setStore] = useState(initialStore);
  const [notice, setNotice] = useState(null);
  const [viewMode, setViewMode] = useState('table');
  useEffect(() => setStore(initialStore), [initialStore]);

  const [resource, reload] = useApiResource(
    () => Promise.all([
      fetchApiList('/products/search', { params: { q: q || undefined, source, store: store || undefined, category: 'all', limit: 80 } }),
      fetchApiList('/dashboard/sources'),
    ]).then(([products, sources]) => ({ products, sources })),
    [q, source, store]
  );
  const products = resource.data?.products || [];

  const downloadProducts = async () => {
    try {
      const response = await axios.get(`${API_BASE}/products/export`, {
        params: { q: q || undefined, source, store: store || undefined, category: 'all' },
        responseType: 'blob',
      });
      downloadBlob(response.data, filenameFromDisposition(response.headers['content-disposition'], 'product-price-list.csv'));
      setNotice({ tone: 'good', text: 'Đã tải CSV sản phẩm và giá bán.' });
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };

  const content = viewMode === 'cards'
    ? <ProductGrid products={products} />
    : viewMode === 'list'
      ? <ProductList products={products} />
      : <ProductRows products={products} className="products-table-wrapper" tableClassName="products-table products-table--page" />;

  return (
    <Page
      title="Sản phẩm & giá bán"
      subtitle="Dữ liệu sản phẩm và giá bán lấy trực tiếp từ API, có liên kết cửa hàng khi crawler thu thập được store fields."
      actions={
        <>
          <label className="route-search"><Search /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm sản phẩm..." /></label>
          <label className="route-search"><MapPin /><input value={store} onChange={(e) => setStore(e.target.value)} placeholder="Lọc theo cửa hàng..." /></label>
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            {(resource.data?.sources || ['all']).map((s) => <option key={s} value={s}>{s === 'all' ? 'Tất cả nguồn' : s}</option>)}
          </select>
          <div className="route-segmented" role="group" aria-label="Kiểu hiển thị sản phẩm">
            <button className={viewMode === 'table' ? 'active' : ''} onClick={() => setViewMode('table')} title="Bảng"><Table2 />Bảng</button>
            <button className={viewMode === 'list' ? 'active' : ''} onClick={() => setViewMode('list')} title="Danh sách"><List />Danh sách</button>
            <button className={viewMode === 'cards' ? 'active' : ''} onClick={() => setViewMode('cards')} title="Thẻ"><LayoutGrid />Thẻ</button>
          </div>
          <button onClick={downloadProducts}><Download />Tải CSV</button>
          <button onClick={reload}><RefreshCw />Tải lại</button>
        </>
      }
    >
      <div className="products-route-grid">
        <Panel title="Khám phá sản phẩm" className="products-panel">
          {notice && <p className={`route-notice ${notice.tone}`}>{notice.text}</p>}
          <StatePanel resource={resource} onRetry={reload} empty={!products.length}>
            {content}
          </StatePanel>
        </Panel>
      </div>
    </Page>
  );
}
