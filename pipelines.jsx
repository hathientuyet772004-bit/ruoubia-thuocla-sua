import React, { useState } from 'react';
import axios from 'axios';
import { Play, Check, X, MoreVertical, RefreshCw, Plus, Search, Activity, CalendarClock } from 'lucide-react';
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
