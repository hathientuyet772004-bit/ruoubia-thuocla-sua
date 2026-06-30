import React, { useState } from 'react';
import axios from 'axios';
import { Check, RefreshCw, X } from 'lucide-react';
import { classifyApiError, fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { dedupStatusLabel, hostFromUrl } from '../shared/utils';
import { Page, Panel, Pill, StatePanel } from '../shared/ui';

const API_BASE = '/api';

export default function AiReviewPage({ navigate }) {
  const [status, setStatus] = useState('needs_review');
  const [domain, setDomain] = useState('all');
  const [notice, setNotice] = useState(null);
  const [resource, reload] = useApiResource(
    () => Promise.all([
      fetchApiList('/extraction/ai/review-items', { params: { status, domain: domain === 'all' ? undefined : domain, limit: 80 } }),
      fetchApiList('/sources'),
    ]).then(([items, sources]) => ({ items, sources })),
    [status, domain]
  );
  const items = resource.data?.items || [];
  const domains = ['all', ...(resource.data?.sources || []).map((s) => hostFromUrl(s.url || s.domain || ''))];

  const decide = async (item, action) => {
    try {
      if (action === 'approved') {
        await axios.post(`${API_BASE}/extraction/ai/review-items/${item.review_id}/publish`);
      } else {
        await axios.patch(`${API_BASE}/extraction/ai/review-items/${item.review_id}`, { status: action });
      }
      setNotice({ tone: 'good', text: `Đã ghi trạng thái ${action} cho ${item.payload?.name || item.review_id}.` });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };

  return (
    <Page
      title="AI duyệt tay"
      subtitle="Danh sách ứng viên do AI sinh ra để đội của bạn rà soát và công bố."
      actions={
        <>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {['needs_review', 'approved', 'rejected', 'all'].map((s) => (
              <option key={s} value={s}>{dedupStatusLabel(s)}</option>
            ))}
          </select>
          <select value={domain} onChange={(e) => setDomain(e.target.value)}>
            {domains.map((d) => <option key={d} value={d}>{d === 'all' ? 'Tất cả nguồn' : d}</option>)}
          </select>
          <button onClick={reload}><RefreshCw />Tải lại</button>
        </>
      }
    >
      <Panel title="Hàng đợi AI">
        {notice && <p className={`route-notice ${notice.tone}`}>{notice.text}</p>}
        <StatePanel resource={resource} onRetry={reload} empty={!items.length}>
          <table>
            <thead>
              <tr><th>Ứng viên</th><th>Loại</th><th>Độ tin cậy</th><th>Lý do</th><th>Trạng thái</th><th>Xử lý</th></tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.review_id}>
                  <td>
                    <b>{item.payload?.name || item.payload?.store_name || '-'}</b>
                    <small className="dedup-compare">{item.payload?.url || item.raw_page_url || '-'}</small>
                  </td>
                  <td>{item.entity_type}</td>
                  <td>{Math.round(Number(item.confidence || 0) * 100)}%</td>
                  <td>{item.reason || '-'}</td>
                  <td><Pill tone={item.status === 'approved' ? 'good' : item.status === 'rejected' ? 'bad' : 'warning'}>{item.status}</Pill></td>
                  <td>
                    <button onClick={() => decide(item, 'approved')}><Check />Duyệt & công bố</button>
                    <button onClick={() => decide(item, 'rejected')}><X />Loại</button>
                    <button onClick={() => decide(item, 'needs_review')}><RefreshCw />Giữ rà soát</button>
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
