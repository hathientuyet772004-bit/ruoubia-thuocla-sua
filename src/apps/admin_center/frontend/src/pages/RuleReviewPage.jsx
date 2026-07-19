import React, { useState } from 'react';
import axios from 'axios';
import { Check, RefreshCw } from 'lucide-react';
import { classifyApiError, fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { Page, Panel, Pill, Stat, StatePanel, TableShell } from '../shared/ui';

const API_BASE = '/api';
const STATUSES = [
  ['all', 'Tất cả'],
  ['validated', 'Có thể duyệt'],
  ['promoted', 'Đã duyệt'],
  ['rejected', 'Bị loại'],
];

function candidateStatusLabel(status) {
  return ({
    validated: 'Có thể duyệt',
    promoted: 'Đã duyệt',
    rejected: 'Bị loại',
    pending: 'Đang chờ',
  })[status] || status || '-';
}

function candidateStatusTone(status) {
  if (status === 'promoted' || status === 'validated') return 'good';
  if (status === 'rejected') return 'bad';
  return 'warning';
}

export default function RuleReviewPage({ navigate }) {
  const [status, setStatus] = useState('all');
  const [resource, reload] = useApiResource(
    () => Promise.all([
      fetchApiList('/extraction/rules/candidates?limit=200'),
      fetchApiList(`/extraction/rules/candidates?status=${status}&limit=200`),
    ]).then(([allCandidates, visibleCandidates]) => ({ allCandidates, visibleCandidates })),
    [status]
  );
  const [notice, setNotice] = useState(null);
  const allCandidates = resource.data?.allCandidates || [];
  const candidates = resource.data?.visibleCandidates || [];
  const counts = {
    all: allCandidates.length,
    validated: allCandidates.filter((candidate) => candidate.status === 'validated').length,
    promoted: allCandidates.filter((candidate) => candidate.status === 'promoted').length,
    rejected: allCandidates.filter((candidate) => candidate.status === 'rejected').length,
  };

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
      <div className="route-stats compact">
        <Stat label="Ứng viên" value={counts.all} note="tổng số" tone="neutral" />
        <Stat label="Có thể duyệt" value={counts.validated} note="đạt quality gate" tone="good" />
        <Stat label="Đã duyệt" value={counts.promoted} note="đang áp dụng" tone="good" />
        <Stat label="Bị loại" value={counts.rejected} note="không đạt" tone={counts.rejected ? 'bad' : 'neutral'} />
      </div>
      <div className="ops-tabs" style={{ marginBottom: '16px', gap: '8px', display: 'flex' }}>
        {STATUSES.map(([value, label]) => (
          <button key={value} className={status === value ? 'active' : ''} onClick={() => setStatus(value)}>
            {label} <span>{counts[value]}</span>
          </button>
        ))}
      </div>
      <Panel title={`Danh sách ứng viên (${candidateStatusLabel(status)})`}>
        <StatePanel resource={resource} onRetry={reload} empty={!candidates.length}>
          <TableShell>
            <thead>
              <tr><th>Domain</th><th>Trạng thái</th><th>Model</th><th>Điểm chất lượng</th><th>Đối tượng</th><th>Valid rows</th><th>Lý do</th><th>Ngày tạo</th><th>Thao tác</th></tr>
            </thead>
            <tbody>
              {candidates.map((c) => {
                const targets = c.quality?.targets || {};
                const targetNames = Object.keys(targets);
                const targetStats = Object.values(targets);
                const validRows = targetStats.reduce((sum, target) => sum + Number(target.valid_rows || 0), 0);
                const passedTargets = targetStats.filter((target) => target.passed).length;
                const reason = c.quality?.accepted
                  ? 'Đạt ngưỡng kiểm thử'
                  : targetNames.length
                    ? `${passedTargets}/${targetNames.length} target đạt`
                    : c.structure?.notes || 'Không tìm thấy selector hợp lệ';
                return (
                  <tr key={c.candidate_id}>
                    <td><b>{c.domain}</b><small>{c.candidate_id}</small></td>
                    <td><Pill tone={candidateStatusTone(c.status)}>{candidateStatusLabel(c.status)}</Pill></td>
                    <td>{c.model || 'Gemini'}</td>
                    <td><Pill tone={c.quality?.score >= 0.72 ? 'good' : 'warning'}>{Math.round((c.quality?.score || 0) * 100)}%</Pill></td>
                    <td>{targetNames.join(', ') || '-'}</td>
                    <td>{validRows.toLocaleString('vi-VN')}</td>
                    <td title={c.structure?.notes || reason}>{reason}</td>
                    <td>{c.created_at ? new Date(c.created_at).toLocaleString() : '-'}</td>
                    <td>{c.status === 'validated' && <button className="primary-action-sm" onClick={() => promote(c)}><Check /> Duyệt Rule</button>}</td>
                  </tr>
                );
              })}
            </tbody>
          </TableShell>
        </StatePanel>
      </Panel>
    </Page>
  );
}
