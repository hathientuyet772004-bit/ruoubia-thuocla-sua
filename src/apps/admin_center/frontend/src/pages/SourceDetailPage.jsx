import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Download, FileSearch, Play, RefreshCw, Sparkles } from 'lucide-react';
import { classifyApiError, fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { extractionTargetLabel, hostFromUrl, sourceTypeLabel, splitList } from '../shared/utils';
import { Page, Panel, Pill, RouteLink, StatePanel, TableShell } from '../shared/ui';

const API_BASE = '/api';
const DEFAULT_SYNTHETIC_COLUMNS = 'name,category,brand,price,currency,rating,store_name,store_address,source,url';
const RUN_TERMINAL_STATUSES = new Set(['completed', 'failed', 'blocked']);

function runStatusLabel(status) {
  return ({
    completed: 'hoàn tất',
    running: 'đang chạy',
    queued: 'đang chờ',
    blocked: 'bị chặn',
    failed: 'thất bại',
  })[status] || status || 'không rõ';
}

function firstRunWarning(run) {
  const warnings = run?.summary?.warnings || [];
  return warnings[0] ? ` Lý do: ${warnings[0]}.` : '';
}

async function waitForLatestSourceRun(sourceId, startedAfter = 0, maxAttempts = 18) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, attempt === 0 ? 1200 : 2000));
    const runs = await fetchApiList(`/sources/${sourceId}/runs?limit=1`);
    const latest = runs[0];
    if (!latest) continue;
    const createdAt = new Date(latest.created_at || latest.updated_at || 0).getTime();
    if (createdAt && createdAt + 3000 < startedAfter) continue;
    if (RUN_TERMINAL_STATUSES.has(latest.status)) return latest;
    if (attempt === maxAttempts - 1) return latest;
  }
  return null;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = filename;
  document.body.appendChild(link); link.click(); link.remove();
  URL.revokeObjectURL(url);
}

export default function SourceDetailPage({ sourceId, navigate }) {
  const [resource, reload] = useApiResource(() => fetchApiList('/sources'), [sourceId]);
  const source = resource.data?.find((s) => String(s.id) === String(sourceId));

  const [discovery, reloadDiscovery] = useApiResource(
    () => sourceId ? axios.get(`${API_BASE}/sources/${sourceId}/discovery`).then((r) => r.data) : Promise.resolve(null),
    [sourceId]
  );
  const [runs, reloadRuns] = useApiResource(
    () => sourceId ? fetchApiList(`/sources/${sourceId}/runs?limit=12`) : Promise.resolve([]),
    [sourceId]
  );
  const [artifactId, setArtifactId] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [analysisState, setAnalysisState] = useState('idle');
  const [reviewState, setReviewState] = useState('idle');
  const [reviewResult, setReviewResult] = useState(null);
  const [collectState, setCollectState] = useState('idle');
  const [collectNotice, setCollectNotice] = useState(null);
  const [syntheticForm, setSyntheticForm] = useState({ rowCount: 20, productTypes: '', referenceSources: '', region: 'Toàn quốc', outputColumns: DEFAULT_SYNTHETIC_COLUMNS, persist: true });
  const [syntheticState, setSyntheticState] = useState('idle');
  const [syntheticResult, setSyntheticResult] = useState(null);

  useEffect(() => {
    setArtifactId(''); setAnalysis(null); setAnalysisState('idle');
    setSyntheticResult(null); setSyntheticState('idle');
  }, [sourceId]);

  useEffect(() => {
    if (!source) return;
    setSyntheticForm((cur) => ({ ...cur, productTypes: cur.productTypes || source.category || '', referenceSources: cur.referenceSources || source.url || source.name || '' }));
  }, [source]);

  useEffect(() => {
    const first = discovery.data?.raw_artifacts?.[0]?.id;
    if (first && !artifactId) setArtifactId(first);
  }, [artifactId, discovery.data]);

  const selectedArtifact = discovery.data?.raw_artifacts?.find((a) => a.id === artifactId);
  const [artifactPreview, reloadArtifactPreview] = useApiResource(
    () => selectedArtifact ? axios.get(`${API_BASE}/extraction/raw-artifacts/${selectedArtifact.id}`, { params: { domain: discovery.data?.domain } }).then((r) => r.data) : Promise.resolve(null),
    [artifactId, discovery.data?.domain]
  );

  const runGeminiAnalysis = async () => {
    if (!discovery.data?.domain) return;
    setAnalysisState('loading');
    try {
      const response = await axios.post(`${API_BASE}/extraction/ai/analyze`, { domain: discovery.data.domain, raw_artifact_id: selectedArtifact?.id || artifactId || undefined, target_hint: discovery.data?.rule?.targets?.[0] || 'auto' });
      setAnalysis(response.data); setAnalysisState('ready');
    } catch (error) {
      const failure = classifyApiError(error);
      setAnalysis({ error: failure.message }); setAnalysisState('error');
    }
  };

  const generateAiReviewList = async () => {
    if (!discovery.data?.domain) return;
    setReviewState('loading');
    try {
      const response = await axios.post(`${API_BASE}/extraction/ai/review`, { domain: discovery.data.domain, raw_artifact_id: selectedArtifact?.id || artifactId || undefined, target_hint: discovery.data?.rule?.targets?.[0] || 'auto', max_items: 24 });
      setReviewResult(response.data); setReviewState('ready');
    } catch (error) {
      const failure = classifyApiError(error);
      setReviewResult({ error: failure.message }); setReviewState('error');
    }
  };

  const collectSource = async () => {
    setCollectState('loading'); setCollectNotice(null);
    try {
      const requestedAt = Date.now();
      await axios.post(`${API_BASE}/sources/${sourceId}/collect`);
      setCollectNotice({ tone: 'warning', text: `Đã nhận lệnh thu thập; đang kiểm tra kết quả lượt chạy...` });
      reload(); reloadDiscovery(); reloadRuns(); reloadArtifactPreview();
      const latestRun = await waitForLatestSourceRun(sourceId, requestedAt);
      if (latestRun) {
        const rawCount = Number(latestRun.summary?.raw_artifacts || 0).toLocaleString('vi-VN');
        const productCount = Number(latestRun.summary?.products_written || 0).toLocaleString('vi-VN');
        const tone = latestRun.status === 'completed' ? 'good' : RUN_TERMINAL_STATUSES.has(latestRun.status) ? 'bad' : 'warning';
        setCollectNotice({
          tone,
          text: `Lượt chạy đã ${runStatusLabel(latestRun.status)}: ${rawCount} trang thô, ${productCount} sản phẩm.${firstRunWarning(latestRun)}`,
        });
        reload(); reloadDiscovery(); reloadRuns(); reloadArtifactPreview();
      } else {
        setCollectNotice({ tone: 'warning', text: 'Đã gửi lệnh thu thập, nhưng chưa thấy lượt chạy mới. Mở Lượt chạy để kiểm tra tiếp.' });
      }
    } catch (error) {
      const failure = classifyApiError(error);
      setCollectNotice({ tone: 'bad', text: failure.message });
    } finally { setCollectState('idle'); }
  };

  const generateSyntheticData = async () => {
    setSyntheticState('loading'); setSyntheticResult(null);
    try {
      const response = await axios.post(`${API_BASE}/sources/${sourceId}/generate-data`, { row_count: Number(syntheticForm.rowCount) || 20, product_types: splitList(syntheticForm.productTypes), reference_sources: splitList(syntheticForm.referenceSources), region: syntheticForm.region || 'Toàn quốc', output_columns: splitList(syntheticForm.outputColumns), persist: syntheticForm.persist });
      setSyntheticResult(response.data); setSyntheticState('ready');
      if (syntheticForm.persist) reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setSyntheticResult({ error: failure.message }); setSyntheticState('error');
    }
  };

  const downloadSyntheticCsv = () => {
    if (!syntheticResult?.csv) return;
    downloadBlob(new Blob([syntheticResult.csv], { type: 'text/csv;charset=utf-8' }), `synthetic-products-${sourceId}.csv`);
  };

  return (
    <Page
      title="Chi tiết nguồn"
      subtitle="Màn hình riêng cho thông tin và hành động của nguồn."
      actions={
        <>
          <RouteLink to="/sources" navigate={navigate}>Về danh sách nguồn</RouteLink>
          <button onClick={collectSource} disabled={collectState === 'loading'}><Play />{collectState === 'loading' ? 'Đang thu thập...' : 'Chạy thu thập'}</button>
          <button onClick={generateAiReviewList} disabled={reviewState === 'loading' || !discovery.data?.domain}><Sparkles />{reviewState === 'loading' ? 'Đang sinh danh sách...' : 'Sinh danh sách AI'}</button>
          <button onClick={() => { reload(); reloadDiscovery(); reloadRuns(); reloadArtifactPreview(); }}><RefreshCw />Tải lại</button>
        </>
      }
    >
      <StatePanel resource={resource} onRetry={reload} empty={!source}>
        <div className="detail-route-grid">
          <Panel title="Hồ sơ nguồn">
            {collectNotice && <p className={`route-notice ${collectNotice.tone}`}>{collectNotice.text}</p>}
            <dl className="route-dl">
              <dt>Tên</dt><dd>{source?.name}</dd>
              <dt>Tên miền</dt><dd>{hostFromUrl(source?.url)}</dd>
              <dt>Loại</dt><dd>{sourceTypeLabel(source?.type)}</dd>
              <dt>Danh mục</dt><dd>{source?.category}</dd>
              <dt>Ghi chú</dt><dd>{source?.note || 'Chưa có ghi chú'}</dd>
            </dl>
          </Panel>

          <Panel title="Lịch sử thu thập">
            <StatePanel resource={runs} onRetry={reloadRuns} empty={!runs.data?.length}>
              <TableShell className="pipeline-table-wrapper" tableClassName="pipeline-table pipeline-table--runs">
                <thead><tr><th>Lượt chạy</th><th>Trạng thái</th><th>Trang thô</th><th>Rule AI</th><th>Cập nhật</th></tr></thead>
                <tbody>
                  {(runs.data || []).map((run) => {
                    const summary = run.summary || {};
                    return (
                      <tr key={run.id}>
                        <td><b>{run.id}</b><small>{run.mode}</small></td>
                        <td><Pill tone={run.status === 'completed' ? 'good' : run.status === 'failed' ? 'bad' : 'warning'}>{run.status}</Pill></td>
                        <td>{summary.raw_artifacts || 0}</td>
                        <td>{summary.ai_accepted || 0}/{summary.ai_attempts || 0}<small>{summary.rules_saved || 0} rule lưu</small></td>
                        <td>{run.updated_at ? new Date(run.updated_at).toLocaleString() : '-'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </TableShell>
            </StatePanel>
          </Panel>

          <Panel title="Phát hiện dữ liệu">
            <StatePanel resource={discovery} onRetry={reloadDiscovery} empty={!discovery.data}>
              <dl className="route-dl">
                <dt>Tên miền</dt><dd>{discovery.data?.domain || '-'}</dd>
                <dt>Trang thô</dt><dd>{discovery.data?.summary?.raw_artifact_count || 0}</dd>
                <dt>Quy tắc</dt><dd><Pill tone={discovery.data?.summary?.has_rule ? 'good' : 'warning'}>{discovery.data?.summary?.has_rule ? 'Đã cấu hình' : 'Chưa có'}</Pill></dd>
                <dt>Mục tiêu</dt><dd>{discovery.data?.rule?.targets?.length ? discovery.data.rule.targets.map(extractionTargetLabel).join(', ') : '-'}</dd>
              </dl>
              {discovery.data?.raw_artifacts?.length ? (
                <table>
                  <thead><tr><th>Trang thô</th><th>Loại</th><th>Cập nhật</th><th>Xem</th></tr></thead>
                  <tbody>
                    {discovery.data.raw_artifacts.slice(0, 6).map((item) => (
                      <tr key={item.id}>
                        <td>{item.filename}</td>
                        <td>{extractionTargetLabel(item.page_type)}</td>
                        <td>{item.updated_at ? new Date(item.updated_at).toLocaleString() : '-'}</td>
                        <td><button onClick={() => setArtifactId(item.id)}>Xem</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="route-state empty"><FileSearch />Nguồn này chưa có trang thô để kiểm thử selector.</div>
              )}
            </StatePanel>
          </Panel>

          <Panel title="Xem trước trang thô">
            <StatePanel resource={artifactPreview} onRetry={reloadArtifactPreview} empty={!selectedArtifact}>
              <dl className="route-dl">
                <dt>Tệp</dt><dd>{artifactPreview.data?.raw_page?.filename || selectedArtifact?.filename || '-'}</dd>
                <dt>URL</dt><dd>{artifactPreview.data?.raw_page?.url || '-'}</dd>
                <dt>Kích thước HTML</dt><dd>{Number(artifactPreview.data?.content_length || 0).toLocaleString()} ký tự</dd>
              </dl>
              <pre>{artifactPreview.data?.text_preview || 'Không có nội dung văn bản để xem trước.'}</pre>
            </StatePanel>
          </Panel>

          <Panel
            title="Hành động tiếp theo"
            className="route-shortcuts"
            actions={<button onClick={runGeminiAnalysis} disabled={analysisState === 'loading' || !discovery.data?.domain}><Sparkles />{analysisState === 'loading' ? 'Đang phân tích...' : 'Phân tích bằng Gemini'}</button>}
          >
            <RouteLink to="/extraction/rules" navigate={navigate}>Sửa quy tắc trích xuất</RouteLink>
            <RouteLink to="/products" navigate={navigate}>Kiểm tra sản phẩm</RouteLink>
          </Panel>

          <Panel
            title="Gen dữ liệu thay thế"
            actions={
              <>
                <button onClick={generateSyntheticData} disabled={syntheticState === 'loading'}><Sparkles />{syntheticState === 'loading' ? 'Đang sinh...' : 'Sinh dữ liệu'}</button>
                {syntheticResult?.csv && <button onClick={downloadSyntheticCsv}><Download />Tải CSV</button>}
              </>
            }
          >
            <div className="synthetic-form-grid">
              <label className="pipeline-field"><span>Số dòng</span><input type="number" min="1" max="200" value={syntheticForm.rowCount} onChange={(e) => setSyntheticForm({ ...syntheticForm, rowCount: e.target.value })} /></label>
              <label className="pipeline-field"><span>Khu vực</span><input value={syntheticForm.region} onChange={(e) => setSyntheticForm({ ...syntheticForm, region: e.target.value })} /></label>
              <label className="pipeline-field pipeline-field--wide"><span>Loại sản phẩm</span><textarea value={syntheticForm.productTypes} onChange={(e) => setSyntheticForm({ ...syntheticForm, productTypes: e.target.value })} /></label>
              <label className="pipeline-field pipeline-field--wide"><span>Nguồn tham khảo</span><textarea value={syntheticForm.referenceSources} onChange={(e) => setSyntheticForm({ ...syntheticForm, referenceSources: e.target.value })} /></label>
              <label className="pipeline-field pipeline-field--wide"><span>Cột đầu ra</span><textarea value={syntheticForm.outputColumns} onChange={(e) => setSyntheticForm({ ...syntheticForm, outputColumns: e.target.value })} /></label>
              <label className="pipeline-field pipeline-checkbox"><input type="checkbox" checked={syntheticForm.persist} onChange={(e) => setSyntheticForm({ ...syntheticForm, persist: e.target.checked })} /><span>Lưu vào danh sách sản phẩm</span></label>
            </div>
            {syntheticState === 'idle' ? <div className="route-state empty"><FileSearch />Dùng khi nguồn bị chặn, trang động hoặc không thể tự động thu thập.</div>
              : syntheticState === 'loading' ? <div className="route-state loading"><RefreshCw />Đang sinh bảng dữ liệu theo prompt...</div>
              : syntheticResult?.error ? <div className="route-state error"><span>{syntheticResult.error}</span></div>
              : (
                <div className="synthetic-result">
                  <dl className="route-dl">
                    <dt>Số dòng</dt><dd>{syntheticResult?.summary?.total || 0}</dd>
                    <dt>Model</dt><dd>{syntheticResult?.model || '-'}</dd>
                    <dt>Đã lưu</dt><dd>{syntheticResult?.persisted ? `${syntheticResult.persisted.products || 0} sản phẩm` : 'Chưa lưu'}</dd>
                  </dl>
                  <pre>{syntheticResult?.markdown}</pre>
                  <pre>{syntheticResult?.csv}</pre>
                </div>
              )}
          </Panel>

          <Panel title="Kết quả Gemini">
            {analysisState === 'idle' ? <div className="route-state empty"><FileSearch />Chưa chạy phân tích nguồn này.</div>
              : analysisState === 'loading' ? <div className="route-state loading"><RefreshCw />Đang tạo draft rule từ HTML...</div>
              : analysis?.error ? <div className="route-state error"><span>{analysis.error}</span></div>
              : (
                <div className="detail-route-grid">
                  <dl className="route-dl">
                    <dt>Model</dt><dd>{analysis?.model || '-'}</dd>
                    <dt>Trạng thái</dt><dd><Pill tone={analysis?.validation?.accepted ? 'good' : 'warning'}>{analysis?.validation?.accepted ? 'Đạt kiểm tra' : 'Cần xem lại'}</Pill></dd>
                    <dt>Domain</dt><dd>{analysis?.domain || '-'}</dd>
                  </dl>
                  <pre>{JSON.stringify(analysis?.draft || {}, null, 2)}</pre>
                  <pre>{JSON.stringify(analysis?.validation || {}, null, 2)}</pre>
                </div>
              )}
          </Panel>

          <Panel title="Danh sách AI">
            {reviewState === 'idle' ? <div className="route-state empty"><FileSearch />Chưa sinh danh sách AI cho nguồn này.</div>
              : reviewState === 'loading' ? <div className="route-state loading"><RefreshCw />Đang tạo danh sách ứng viên để duyệt tay...</div>
              : reviewResult?.error ? <div className="route-state error"><span>{reviewResult.error}</span></div>
              : (
                <div className="detail-route-grid">
                  <dl className="route-dl">
                    <dt>Tổng ứng viên</dt><dd>{reviewResult?.summary?.total || 0}</dd>
                    <dt>Cần rà soát</dt><dd>{reviewResult?.summary?.needs_review || 0}</dd>
                    <dt>Model</dt><dd>{reviewResult?.model || '-'}</dd>
                  </dl>
                  <table>
                    <thead><tr><th>Loại</th><th>Ứng viên</th><th>Độ tin cậy</th><th>Lý do</th></tr></thead>
                    <tbody>
                      {(reviewResult?.review_items || []).slice(0, 8).map((item) => (
                        <tr key={item.review_id}>
                          <td>{item.entity_type}</td>
                          <td><b>{item.payload?.name || item.payload?.store_name || '-'}</b><small className="dedup-compare">{item.payload?.url || item.raw_page_url || '-'}</small></td>
                          <td>{Math.round((Number(item.confidence || 0) * 100))}%</td>
                          <td>{item.reason || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
          </Panel>
        </div>
      </StatePanel>
    </Page>
  );
}
