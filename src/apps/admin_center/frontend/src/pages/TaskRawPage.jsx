import React from 'react';
import axios from 'axios';
import { fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { Page, Panel, RouteLink, StatePanel } from '../shared/ui';
import { routeId } from '../routeShell';

const API_BASE = '/api';

export default function TaskRawPage({ jobId, navigate }) {
  const [latest, latestReload] = useApiResource(() => fetchApiList('/jobs?limit=1').then((jobs) => jobs[0]), []);
  const resolvedId = jobId === 'latest' ? latest.data?.id : jobId;
  const [resource, reload] = useApiResource(
    () => resolvedId ? axios.get(`${API_BASE}/jobs/logs/${resolvedId}`).then((r) => r.data) : Promise.resolve(null),
    [resolvedId]
  );

  if (jobId === 'latest' && latest.status !== 'ready') {
    return (
      <Page title="Xem trang thô tác vụ" subtitle="Đang tìm tác vụ mới nhất.">
        <StatePanel resource={latest} onRetry={latestReload} empty={false} />
      </Page>
    );
  }

  return (
    <Page
      title="Xem trang thô tác vụ"
      subtitle={`Siêu dữ liệu và tệp trích xuất của tác vụ ${resolvedId || 'không rõ'}.`}
      actions={<RouteLink to={`/runs/${routeId(resolvedId || 'unknown')}`} navigate={navigate}>Mở chi tiết lượt chạy</RouteLink>}
    >
      <StatePanel resource={resource} onRetry={reload} empty={!resource.data}>
        <div className="raw-route-grid">
          <Panel title="Siêu dữ liệu"><pre>{JSON.stringify(resource.data?.metadata || {}, null, 2)}</pre></Panel>
          <Panel title="Sự kiện"><pre>{(resource.data?.events || []).join('\n')}</pre></Panel>
          <Panel title="Đầu ra"><pre>{JSON.stringify(resource.data?.output_summary || {}, null, 2)}</pre></Panel>
        </div>
      </StatePanel>
    </Page>
  );
}
