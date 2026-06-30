import React, { useRef, useState } from 'react';
import axios from 'axios';
import { Download, Plus, RefreshCw, Search, Upload } from 'lucide-react';
import { classifyApiError, fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { downloadBlob, filenameFromDisposition } from '../shared/utils';
import { Page, Panel, SourceRows, StatePanel } from '../shared/ui';

const API_BASE = '/api';

export default function SourcesPage({ navigate, onAdd }) {
  const [query, setQuery] = useState('');
  const [notice, setNotice] = useState(null);
  const [collectingId, setCollectingId] = useState('');
  const uploadInputRef = useRef(null);
  const [resource, reload] = useApiResource(() => fetchApiList('/sources'), []);
  const sources = (resource.data || []).filter((s) =>
    `${s.name} ${s.url} ${s.category}`.toLowerCase().includes(query.toLowerCase())
  );

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
      <Panel title="Danh mục nguồn">
        {notice && <p className={`route-notice ${notice.tone}`}>{notice.text}</p>}
        <StatePanel resource={resource} onRetry={reload} empty={!sources.length}>
          <SourceRows sources={sources} navigate={navigate} onCollect={collectSource} collectingId={collectingId} />
        </StatePanel>
      </Panel>
    </Page>
  );
}
