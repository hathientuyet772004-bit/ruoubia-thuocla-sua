import React, { useState } from 'react';
import axios from 'axios';
import { RefreshCw } from 'lucide-react';
import { classifyApiError, fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { dedupStatusLabel } from '../shared/utils';
import { Page, Panel, Pill, Stat, StatePanel } from '../shared/ui';

const API_BASE = '/api';

export default function DedupPage() {
  const [notice, setNotice] = useState(null);
  const [status, setStatus] = useState('pending');
  const [resource, reload] = useApiResource(
    () => Promise.all([
      fetchApiList('/dedup/candidates', { params: { limit: 200, status: 'all' } }),
      fetchApiList('/dedup/candidates', { params: { limit: 24, status } }),
    ]).then(([allCandidates, visibleCandidates]) => ({ allCandidates, visibleCandidates })),
    [status]
  );
  const allCandidates = resource.data?.allCandidates || [];
  const candidates = resource.data?.visibleCandidates || [];
  const counts = {
    all: allCandidates.length,
    pending: allCandidates.filter((item) => item.status === 'pending').length,
    needs_review: allCandidates.filter((item) => item.status === 'needs_review').length,
    merged: allCandidates.filter((item) => item.status === 'merged').length,
    rejected: allCandidates.filter((item) => item.status === 'rejected').length,
  };

  const decide = async (candidate, decision) => {
    try {
      await axios.post(`${API_BASE}/dedup/candidates/${candidate.id}/decision`, { status: decision });
      setNotice({ tone: 'good', text: `Đã ghi trạng thái ${dedupStatusLabel(decision).toLowerCase()} cho ${candidate.left.name}.` });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };

  const refreshCandidates = async () => {
    try {
      const response = await axios.post(`${API_BASE}/dedup/candidates/refresh`);
      setNotice({ tone: 'good', text: `Đã làm mới ${response.data.candidate_count} ứng viên trùng lặp.` });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };

  return (
    <Page
      title="Rà soát trùng lặp"
      subtitle="Hàng đợi trùng lặp có trạng thái thực từ dữ liệu đầu ra."
      actions={
        <>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {['pending', 'merged', 'rejected', 'needs_review', 'all'].map((s) => (
              <option key={s} value={s}>{dedupStatusLabel(s)}</option>
            ))}
          </select>
          <button onClick={refreshCandidates}><RefreshCw />Tính lại ứng viên</button>
          <button onClick={reload}><RefreshCw />Tải lại</button>
        </>
      }
    >
      <div className="route-stats compact">
        <Stat label="Ứng viên" value={counts.all} note="tổng queue" tone="neutral" />
        <Stat label="Đang chờ" value={counts.pending} note="cần quyết định" tone={counts.pending ? 'warning' : 'neutral'} />
        <Stat label="Rà soát" value={counts.needs_review} note="cần xem kỹ" tone={counts.needs_review ? 'warning' : 'neutral'} />
        <Stat label="Đã xử lý" value={counts.merged + counts.rejected} note="gộp hoặc loại" tone="good" />
      </div>
      <Panel title="Ứng viên trùng lặp">
        {notice && <p className={`route-notice ${notice.tone}`}>{notice.text}</p>}
        <StatePanel resource={resource} onRetry={reload} empty={!candidates.length}>
          <table>
            <thead>
              <tr><th>Ứng viên</th><th>Nguồn</th><th>Trạng thái</th><th>Độ tin cậy</th><th>Lý do</th><th>Quyết định</th></tr>
            </thead>
            <tbody>
              {candidates.map((c) => (
                <tr key={c.id}>
                  <td><b>{c.left.name}</b><small className="dedup-compare">{c.right.name}</small></td>
                  <td>{c.left.source}<small className="dedup-compare">{c.right.source}</small></td>
                  <td><Pill tone={c.status === 'merged' ? 'good' : c.status === 'rejected' ? 'bad' : 'warning'}>{dedupStatusLabel(c.status)}</Pill></td>
                  <td>{Math.round(c.confidence * 100)}%</td>
                  <td>{c.reasons.join(', ')}</td>
                  <td>
                    <button onClick={() => decide(c, 'merged')}>Gộp</button>
                    <button onClick={() => decide(c, 'rejected')}>Loại</button>
                    <button onClick={() => decide(c, 'needs_review')}>Rà soát</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </StatePanel>
      </Panel>
    </Page>
  );
}
