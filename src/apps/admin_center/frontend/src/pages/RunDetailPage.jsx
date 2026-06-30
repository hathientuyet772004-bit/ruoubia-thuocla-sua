import React from 'react';
import axios from 'axios';
import { RefreshCw } from 'lucide-react';
import { Page, Panel, Pill, RouteLink, StatePanel } from '../shared/ui';
import { useApiResource } from '../shared/hooks';
import { routeId } from '../routeShell';

const API_BASE = '/api';

export default function RunDetailPage({ jobId, navigate }) {
  const [resource, reload] = useApiResource(() =>
    axios.get(`${API_BASE}/jobs/logs/${jobId}`).then((r) => {
      if (r.data?.error && !r.data?.events?.length) throw new Error(r.data.error);
      return r.data;
    }), [jobId]);
  const logs = resource.data;

  return (
    <Page
      title="Chi tiết lượt chạy"
      subtitle={`Nhật ký thực tế của lượt chạy ${jobId}.`}
      actions={
        <>
          <RouteLink to="/runs" navigate={navigate}>Quay lại</RouteLink>
          <RouteLink to={`/tasks/${routeId(jobId)}/raw`} navigate={navigate}>Trang thô tác vụ</RouteLink>
          <button onClick={reload}><RefreshCw />Tải lại</button>
        </>
      }
    >
      <StatePanel resource={resource} onRetry={reload} empty={!logs}>
        <div className="detail-route-grid">
          <Panel title="Dòng thời gian">
            {logs?.events?.length
              ? logs.events.map((e) => <p className="event-line" key={e}>{e}</p>)
              : <p>Chưa có sự kiện.</p>}
          </Panel>
          <Panel title="Tóm tắt đầu ra">
            <pre>{JSON.stringify(logs?.output_summary || {}, null, 2)}</pre>
          </Panel>
          <Panel title="Lỗi">
            {logs?.error
              ? <pre className="failure-pre">{logs.error}</pre>
              : <Pill tone="good">Không phát hiện tệp lỗi</Pill>}
          </Panel>
        </div>
      </StatePanel>
    </Page>
  );
}
