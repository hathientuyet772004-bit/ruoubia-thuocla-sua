import React, { useMemo } from 'react';
import { RefreshCw } from 'lucide-react';
import { fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { JobRows, Page, Panel, Stat, StatePanel } from '../shared/ui';

export default function RunsPage({ navigate }) {
  const [resource, reload] = useApiResource(() => fetchApiList('/jobs'), []);
  const jobs = resource.data || [];
  const totals = useMemo(() => ({
    pending: jobs.filter((j) => j.status === 'Pending').length,
    failed: jobs.filter((j) => j.status === 'Failed').length,
    completed: jobs.filter((j) => j.status === 'Completed').length,
  }), [jobs]);

  return (
    <Page
      title="Lượt chạy"
      subtitle="Theo dõi tác vụ từ kho trang thô và kho đầu ra."
      actions={<button onClick={reload}><RefreshCw />Tải lại</button>}
    >
      <div className="route-stats compact">
        <Stat label="Hoàn tất" value={totals.completed} note="lượt chạy" />
        <Stat label="Đang chờ" value={totals.pending} note="lượt chạy" tone="warning" />
        <Stat label="Thất bại" value={totals.failed} note="lượt chạy" tone="bad" />
      </div>
      <Panel title="Danh sách lượt chạy">
        <StatePanel resource={resource} onRetry={reload} empty={!jobs.length}>
          <JobRows jobs={jobs} navigate={navigate} />
        </StatePanel>
      </Panel>
    </Page>
  );
}
