import React, { useMemo } from 'react';
import { RefreshCw } from 'lucide-react';
import { fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { JobRows, Page, Panel, Pill, Stat, StatePanel, TableShell } from '../shared/ui';

function pipelineStatusLabel(status) {
  return ({
    completed: 'Hoàn tất',
    running: 'Đang chạy',
    queued: 'Đang chờ',
    blocked: 'Bị chặn',
    failed: 'Thất bại',
  })[status] || status || '-';
}

function pipelineStatusTone(status) {
  if (status === 'completed') return 'good';
  if (status === 'running' || status === 'queued') return 'warning';
  if (status === 'blocked' || status === 'failed') return 'bad';
  return 'neutral';
}

function PipelineRunRows({ runs }) {
  return (
    <TableShell>
      <thead>
        <tr>
          <th>Pipeline</th>
          <th>Trạng thái</th>
          <th>Trang thô</th>
          <th>Sản phẩm</th>
          <th>Offers</th>
          <th>Rule</th>
          <th>Cập nhật</th>
          <th>Cảnh báo</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => {
          const summary = run.summary || {};
          const warnings = summary.warnings || [];
          return (
            <tr key={run.run_id || run.id}>
              <td><b>{run.pipeline_name || run.pipeline_id}</b><small>{run.run_id || run.id}</small></td>
              <td><Pill tone={pipelineStatusTone(run.status)}>{pipelineStatusLabel(run.status)}</Pill></td>
              <td>{Number(summary.raw_artifacts || 0).toLocaleString('vi-VN')}</td>
              <td>{Number(summary.products_written || 0).toLocaleString('vi-VN')}</td>
              <td>{Number(summary.offers_written || 0).toLocaleString('vi-VN')}</td>
              <td>{Number(summary.rules_saved || 0).toLocaleString('vi-VN')} lưu · {Number(summary.rules_reused || 0).toLocaleString('vi-VN')} dùng lại</td>
              <td>{run.updated_at || run.finished_at || run.created_at ? new Date(run.updated_at || run.finished_at || run.created_at).toLocaleString() : '-'}</td>
              <td title={warnings.join('\n')}>{warnings[0] || '-'}</td>
            </tr>
          );
        })}
      </tbody>
    </TableShell>
  );
}

export default function RunsPage({ navigate }) {
  const [resource, reload] = useApiResource(
    () => Promise.all([
      fetchApiList('/pipelines/runs?limit=80'),
      fetchApiList('/jobs?limit=80'),
    ]).then(([pipelineRuns, jobs]) => ({ pipelineRuns, jobs })),
    []
  );
  const jobs = resource.data?.jobs || [];
  const pipelineRuns = resource.data?.pipelineRuns || [];
  const totals = useMemo(() => ({
    rawCompleted: jobs.filter((j) => j.status === 'Completed').length,
    rawPending: jobs.filter((j) => j.status === 'Pending').length,
    rawFailed: jobs.filter((j) => j.status === 'Failed').length,
    pipelineCompleted: pipelineRuns.filter((run) => run.status === 'completed').length,
    pipelineBlocked: pipelineRuns.filter((run) => run.status === 'blocked').length,
    pipelineFailed: pipelineRuns.filter((run) => run.status === 'failed').length,
  }), [jobs, pipelineRuns]);

  return (
    <Page
      title="Lượt chạy"
      subtitle="Theo dõi pipeline crawler, rule AI, writer và các trang thô đã capture."
      actions={<button onClick={reload}><RefreshCw />Tải lại</button>}
    >
      <div className="route-stats compact">
        <Stat label="Pipeline hoàn tất" value={totals.pipelineCompleted} note="lượt chạy" />
        <Stat label="Pipeline bị chặn" value={totals.pipelineBlocked} note="cần xử lý" tone="warning" />
        <Stat label="Pipeline thất bại" value={totals.pipelineFailed} note="lỗi chạy" tone="bad" />
        <Stat label="Trang thô" value={totals.rawCompleted} note={`${totals.rawPending} chờ · ${totals.rawFailed} lỗi`} tone="neutral" />
      </div>
      <Panel title="Lượt chạy pipeline">
        <StatePanel resource={resource} onRetry={reload} empty={!pipelineRuns.length}>
          <PipelineRunRows runs={pipelineRuns} />
        </StatePanel>
      </Panel>
      <Panel title="Tác vụ trang thô">
        <StatePanel resource={resource} onRetry={reload} empty={!jobs.length}>
          <JobRows jobs={jobs} navigate={navigate} />
        </StatePanel>
      </Panel>
    </Page>
  );
}
