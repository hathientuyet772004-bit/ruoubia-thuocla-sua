import React, { useMemo, useState } from 'react';
import axios from 'axios';
import { MoreVertical, Play, Plus, RefreshCw, Search, X } from 'lucide-react';
import { classifyApiError, fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { Page, Panel, Pill, Stat, StatePanel, TableShell } from '../shared/ui';

const API_BASE = '/api';

function runStatusLabel(status) {
  return ({
    completed: 'Thành công',
    running: 'Đang chạy',
    queued: 'Đang chờ',
    blocked: 'Bị chặn',
    failed: 'Lỗi',
  })[status] || 'Chưa chạy';
}

function runStatusTone(status) {
  if (status === 'completed') return 'good';
  if (status === 'running' || status === 'queued') return 'warning';
  if (status === 'blocked' || status === 'failed') return 'bad';
  return 'neutral';
}

export default function PipelinesPage({ navigate }) {
  const [resource, reload] = useApiResource(() => fetchApiList('/pipelines'), []);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [notice, setNotice] = useState(null);
  const [runningPipelineId, setRunningPipelineId] = useState(null);

  const pipelines = Array.isArray(resource.data) ? resource.data : [];
  const filteredPipelines = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return pipelines.filter((pipeline) => {
      const status = pipeline.last_run_status || pipeline.status;
      const matchesFilter =
        filter === 'all' ||
        (filter === 'running' && ['running', 'queued'].includes(status)) ||
        (filter === 'warning' && ['blocked', 'failed'].includes(status)) ||
        (filter === 'off' && !pipeline.enabled);
      const matchesQuery = !keyword || [
        pipeline.name,
        pipeline.description,
        pipeline.mode,
        ...(pipeline.entry_urls || []),
      ].some((value) => String(value || '').toLowerCase().includes(keyword));
      return matchesFilter && matchesQuery;
    });
  }, [filter, pipelines, query]);
  const total = pipelines.length;
  const active = pipelines.filter((p) => p.enabled).length;
  const running = pipelines.filter((p) => ['running', 'queued'].includes(p.last_run_status || p.status)).length;
  const completed = pipelines.filter((p) => p.last_run_status === 'completed').length;
  const finished = pipelines.filter((p) => ['completed', 'failed', 'blocked'].includes(p.last_run_status)).length;
  const successRate = finished ? `${Math.round((completed / finished) * 1000) / 10}%` : '-';

  const runNow = async (pipelineId) => {
    setRunningPipelineId(pipelineId);
    setNotice(null);
    try {
      const response = await axios.post(`${API_BASE}/pipelines/${pipelineId}/run`);
      setNotice({ tone: 'good', text: `Đã chạy pipeline: ${runStatusLabel(response.data?.status)}.` });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    } finally {
      setRunningPipelineId(null);
    }
  };

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
      {notice && <p className={`route-notice ${notice.tone}`}>{notice.text}</p>}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
        <Stat label="Pipeline" value={total} note="Tổng số" tone="neutral" />
        <Stat label="Đang bật" value={active} note="Kích hoạt" tone="good" />
        <Stat label="Đang chạy" value={running} note="Thời gian thực" tone="warning" />
        <Stat label="Thành công" value={successRate} note="Theo lần chạy gần nhất" tone="good" />
      </div>

      <Panel
        title="Pipeline"
        actions={<label className="route-search"><Search /><input placeholder="Tìm kiếm..." value={query} onChange={(event) => setQuery(event.target.value)} /></label>}
      >
        <div className="ops-tabs" style={{ marginBottom: '16px', gap: '8px', display: 'flex' }}>
          {['all', 'running', 'warning', 'off'].map((f) => (
            <button key={f} className={filter === f ? 'active' : ''} onClick={() => setFilter(f)}>
              {f === 'all' ? 'Tất cả' : f === 'running' ? 'Đang chạy' : f === 'warning' ? 'Cảnh báo' : 'Đã tắt'}
            </button>
          ))}
        </div>
        <StatePanel resource={resource} onRetry={reload} empty={!filteredPipelines.length}>
          <TableShell>
            <thead>
              <tr><th>Tên</th><th>Nguồn</th><th>Lịch</th><th>Cấu hình</th><th>Sức khỏe</th><th>Lần chạy</th><th>Thao tác</th></tr>
            </thead>
            <tbody>
              {filteredPipelines.map((p) => {
                const status = p.last_run_status || p.status;
                return (
                <tr key={p.id}>
                  <td><b>{p.name}</b><br /><small>{p.id.slice(0, 8)}...{p.id.slice(-5)}</small></td>
                  <td>{p.source_count || 1}</td>
                  <td>{p.cron ? 'Biểu thức cron' : 'Thủ công'}</td>
                  <td><Pill tone={p.enabled ? 'good' : 'neutral'}>{p.enabled ? 'Bật' : 'Tắt'}</Pill></td>
                  <td><Pill tone={runStatusTone(status)}>{runStatusLabel(status)}</Pill></td>
                  <td>{p.last_run_at ? new Date(p.last_run_at).toLocaleString() : '-'}</td>
                  <td>
                    <button className="primary-action-sm" disabled={runningPipelineId === p.id} onClick={() => runNow(p.id)}><Play /> {runningPipelineId === p.id ? 'Đang chạy...' : 'Chạy ngay'}</button>
                    <button className="icon-action"><MoreVertical /></button>
                  </td>
                </tr>
              );
              })}
            </tbody>
          </TableShell>
        </StatePanel>
      </Panel>

      {drawerOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', justifyContent: 'flex-end' }} onClick={() => setDrawerOpen(false)}>
          <div style={{ width: '600px', backgroundColor: 'var(--color-bg-panel, #1e1e2e)', height: '100%', padding: '24px', overflowY: 'auto' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2>Tạo Pipeline mới</h2>
              <button onClick={() => setDrawerOpen(false)}><X /></button>
            </div>
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
