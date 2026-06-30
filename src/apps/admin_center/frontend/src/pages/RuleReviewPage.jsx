import React, { useState } from 'react';
import axios from 'axios';
import { Check, RefreshCw } from 'lucide-react';
import { classifyApiError, fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { Page, Panel, Pill, StatePanel, TableShell } from '../shared/ui';

const API_BASE = '/api';

export default function RuleReviewPage({ navigate }) {
  const [status, setStatus] = useState('pending');
  const [resource, reload] = useApiResource(
    () => fetchApiList(`/extraction/rules/candidates?status=${status}`),
    [status]
  );
  const [notice, setNotice] = useState(null);

  const promote = async (candidate) => {
    try {
      await axios.post(`${API_BASE}/extraction/rules/candidates/${candidate.candidate_id}/promote`);
      setNotice({ tone: 'good', text: `Đã duyệt rule thành công cho domain ${candidate.domain}` });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };

  return (
    <Page
      title="Duyệt Rule AI (Quarantine)"
      subtitle="Danh sách Rule Candidate (ứng viên) do Gemini sinh ra, đang chờ duyệt để chính thức áp dụng cho Crawler."
      actions={<button onClick={reload}><RefreshCw />Tải lại</button>}
    >
      {notice && <p className={`route-notice ${notice.tone}`}>{notice.text}</p>}
      <div className="ops-tabs" style={{ marginBottom: '16px', gap: '8px', display: 'flex' }}>
        <button className={status === 'pending' ? 'active' : ''} onClick={() => setStatus('pending')}>Đang chờ duyệt</button>
        <button className={status === 'promoted' ? 'active' : ''} onClick={() => setStatus('promoted')}>Đã duyệt</button>
      </div>
      <Panel title={`Danh sách ứng viên (${status})`}>
        <StatePanel resource={resource} onRetry={reload} empty={!resource.data?.length}>
          <TableShell>
            <thead>
              <tr><th>Domain</th><th>Model</th><th>Điểm chất lượng</th><th>Đối tượng (Targets)</th><th>Ngày tạo</th><th>Thao tác</th></tr>
            </thead>
            <tbody>
              {(resource.data || []).map((c) => (
                <tr key={c.candidate_id}>
                  <td><b>{c.domain}</b></td>
                  <td>{c.model || 'Gemini'}</td>
                  <td><Pill tone={c.quality?.score >= 0.72 ? 'good' : 'warning'}>{Math.round((c.quality?.score || 0) * 100)}%</Pill></td>
                  <td>{Object.keys(c.quality?.targets || {}).join(', ')}</td>
                  <td>{new Date(c.created_at).toLocaleString()}</td>
                  <td>{status === 'pending' && <button className="primary-action-sm" onClick={() => promote(c)}><Check /> Duyệt Rule</button>}</td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        </StatePanel>
      </Panel>
    </Page>
  );
}
