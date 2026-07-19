import React, { useRef, useState } from 'react';
import axios from 'axios';
import { Download, Plus, RefreshCw, Search, Upload } from 'lucide-react';
import { classifyApiError, fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { downloadBlob, filenameFromDisposition } from '../shared/utils';
import { Page, Panel, SourceRows, Stat, StatePanel } from '../shared/ui';

const API_BASE = '/api';
const RUN_TERMINAL_STATUSES = new Set(['completed', 'failed', 'blocked']);

function runStatusLabel(status) {
  return ({
    completed: 'hoàn tất',
    running: 'đang chạy',
    queued: 'đang chờ',
    blocked: 'bị chặn',
    failed: 'thất bại',
  })[status] || status || 'không rõ';
}

function firstRunWarning(run) {
  const warnings = run?.summary?.warnings || [];
  return warnings[0] ? ` Lý do: ${warnings[0]}.` : '';
}

async function waitForLatestSourceRun(sourceId, startedAfter = 0, maxAttempts = 18) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, attempt === 0 ? 1200 : 2000));
    const runs = await fetchApiList(`/sources/${sourceId}/runs?limit=1`);
    const latest = runs[0];
    if (!latest) continue;
    const createdAt = new Date(latest.created_at || latest.updated_at || 0).getTime();
    if (createdAt && createdAt + 3000 < startedAfter) continue;
    if (RUN_TERMINAL_STATUSES.has(latest.status)) return latest;
    if (attempt === maxAttempts - 1) return latest;
  }
  return null;
}

export default function SourcesPage({ navigate, onAdd }) {
  const [query, setQuery] = useState('');
  const [notice, setNotice] = useState(null);
  const [collectingId, setCollectingId] = useState('');
  const uploadInputRef = useRef(null);
  const [resource, reload] = useApiResource(() => fetchApiList('/sources'), []);
  const sources = (resource.data || []).filter((s) =>
    `${s.name} ${s.url} ${s.category} ${s.type} ${s.note}`.toLowerCase().includes(query.toLowerCase())
  );
  const allSources = resource.data || [];
  const capturedSources = allSources.filter((source) => source.has_raw_data).length;
  const totalProducts = allSources.reduce((sum, source) => sum + Number(source.product_count || 0), 0);
  const quarantined = allSources.reduce((sum, source) => sum + Number(source.quarantine_count || 0), 0);

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
      const requestedAt = Date.now();
      const response = await axios.post(`${API_BASE}/sources/${source.id}/collect`);
      setNotice({ tone: 'warning', text: `Đã nhận lệnh thu thập cho ${source.name || source.id}; đang kiểm tra kết quả lượt chạy...` });
      reload();
      const latestRun = await waitForLatestSourceRun(source.id, requestedAt);
      if (latestRun) {
        const status = runStatusLabel(latestRun.status);
        const rawCount = Number(latestRun.summary?.raw_artifacts || 0).toLocaleString('vi-VN');
        const productCount = Number(latestRun.summary?.products_written || 0).toLocaleString('vi-VN');
        const tone = latestRun.status === 'completed' ? 'good' : RUN_TERMINAL_STATUSES.has(latestRun.status) ? 'bad' : 'warning';
        setNotice({
          tone,
          text: `Lượt chạy ${source.name || source.id} đã ${status}: ${rawCount} trang thô, ${productCount} sản phẩm.${firstRunWarning(latestRun)}`,
        });
        reload();
      } else {
        setNotice({ tone: 'warning', text: `Đã gửi lệnh thu thập cho ${source.name || source.id}, nhưng chưa thấy lượt chạy mới. Mở Lượt chạy để kiểm tra tiếp.` });
      }
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    } finally {
      setCollectingId('');
    }
  };

  return (
    <Page
      title="Nguồn dữ liệu"
      subtitle="Danh mục nguồn lấy trực tiếp từ API. Bấm Chạy để thu thập ngầm theo từng nguồn."
      actions={
        <>
          <label className="route-search">
            <Search />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Lọc nguồn..." />
          </label>
          <button onClick={() => downloadSourceFile('/sources/template', 'source-import-template.csv')}><Download />Mẫu thêm nguồn</button>
          <button onClick={() => uploadInputRef.current?.click()}><Upload />Tải lên danh sách</button>
          <input ref={uploadInputRef} className="hidden-file-input" type="file" accept=".csv,text/csv" onChange={uploadSources} />
          <button onClick={() => downloadSourceFile('/sources/export', 'source-list.csv')}><Download />Tải xuống danh sách</button>
          <button onClick={reload}><RefreshCw />Tải lại</button>
          <button onClick={onAdd}><Plus />Thêm nguồn</button>
        </>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
        <Stat label="Nguồn" value={allSources.length} note="Tổng số" tone="neutral" />
        <Stat label="Có trang thô" value={capturedSources} note="Đã thu thập" tone="good" />
        <Stat label="Sản phẩm" value={totalProducts.toLocaleString('vi-VN')} note="Trong kho giá" tone="good" />
        <Stat label="Cách ly" value={quarantined.toLocaleString('vi-VN')} note="Cần rà soát" tone={quarantined ? 'warning' : 'neutral'} />
      </div>
      <Panel title="Danh mục nguồn">
        {notice && <p className={`route-notice ${notice.tone}`}>{notice.text}</p>}
        <StatePanel resource={resource} onRetry={reload} empty={!sources.length}>
          <SourceRows sources={sources} navigate={navigate} onCollect={collectSource} collectingId={collectingId} />
        </StatePanel>
      </Panel>
    </Page>
  );
}
