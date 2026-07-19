import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Check, Download, RefreshCw, Save, Sparkles, X } from 'lucide-react';
import { classifyApiError, fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { downloadBlob, hostFromUrl, splitList } from '../shared/utils';
import { Page, Panel, Pill, StatePanel, TableShell } from '../shared/ui';

const API_BASE = '/api';
const DEFAULT_COLUMNS = 'name,category,brand,price,currency,rating,store_name,store_address,source,url';
const DEFAULT_FORM = {
  sourceId: '',
  rowCount: 30,
  productTypes: '',
  referenceSources: '',
  region: 'Việt Nam',
  outputColumns: DEFAULT_COLUMNS,
  generationMode: 'synthetic',
  persist: true,
};

function statusTone(status) {
  if (status === 'approved' || status === 'validated') return 'good';
  if (status === 'rejected') return 'bad';
  return 'warning';
}

function statusLabel(status) {
  return ({
    approved: 'Đã duyệt',
    rejected: 'Đã loại',
    validated: 'Đã kiểm tra',
    synthetic: 'Synthetic',
    grounded_synthetic: 'Grounded',
  })[status] || status || '-';
}

export default function GenDataPage({ navigate }) {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [result, setResult] = useState(null);
  const [state, setState] = useState('idle');
  const [notice, setNotice] = useState(null);
  const [promptDraft, setPromptDraft] = useState('');
  const [promptState, setPromptState] = useState('idle');

  const [resource, reload] = useApiResource(
    () => Promise.all([
      fetchApiList('/sources'),
      fetchApiList('/sources/synthetic-batches?limit=80'),
      axios.get(`${API_BASE}/sources/generation-prompt/latest`).then((r) => r.data),
    ]).then(([sources, batches, prompt]) => ({ sources, batches, prompt })),
    []
  );

  const sources = resource.data?.sources || [];
  const batches = resource.data?.batches || [];
  const selectedSource = useMemo(
    () => sources.find((source) => String(source.id) === String(form.sourceId)),
    [form.sourceId, sources]
  );

  useEffect(() => {
    if (!sources.length || form.sourceId) return;
    const preferred = sources.find((source) => source.has_raw_data) || sources[0];
    setForm((current) => ({
      ...current,
      sourceId: preferred.id,
      productTypes: current.productTypes || preferred.category || '',
      referenceSources: current.referenceSources || preferred.url || preferred.name || '',
    }));
  }, [form.sourceId, sources]);

  useEffect(() => {
    if (!selectedSource) return;
    setForm((current) => ({
      ...current,
      productTypes: current.productTypes || selectedSource.category || '',
      referenceSources: current.referenceSources || selectedSource.url || selectedSource.name || '',
    }));
  }, [selectedSource]);

  useEffect(() => {
    if (resource.data?.prompt?.content) setPromptDraft(resource.data.prompt.content);
  }, [resource.data?.prompt?.content]);

  const updateForm = (patch) => setForm((current) => ({ ...current, ...patch }));

  const generateData = async () => {
    if (!form.sourceId) return;
    setState('loading');
    setResult(null);
    setNotice(null);
    try {
      const response = await axios.post(`${API_BASE}/sources/${form.sourceId}/generate-data`, {
        row_count: Number(form.rowCount) || 30,
        product_types: splitList(form.productTypes),
        reference_sources: splitList(form.referenceSources),
        region: form.region || 'Việt Nam',
        output_columns: splitList(form.outputColumns),
        generation_mode: form.generationMode,
        persist: form.persist,
      });
      setResult(response.data);
      setState('ready');
      setNotice({ tone: 'good', text: `Đã sinh ${response.data?.summary?.total || 0} dòng dữ liệu.` });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setState('error');
      setResult({ error: failure.message });
      setNotice({ tone: 'bad', text: failure.message });
    }
  };

  const savePrompt = async () => {
    setPromptState('loading');
    setNotice(null);
    try {
      await axios.post(`${API_BASE}/sources/generation-prompt`, { content: promptDraft });
      setPromptState('ready');
      setNotice({ tone: 'good', text: 'Đã lưu prompt tạo dữ liệu.' });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setPromptState('error');
      setNotice({ tone: 'bad', text: failure.message });
    }
  };

  const decideBatch = async (batch, status) => {
    try {
      await axios.put(`${API_BASE}/sources/${batch.source_id}/synthetic-batches/${batch.batch_id}/decision`, { status });
      setNotice({ tone: 'good', text: `Đã ghi trạng thái ${statusLabel(status)} cho batch.` });
      reload();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };

  const downloadCsv = () => {
    if (!result?.csv) return;
    const sourceName = selectedSource?.name || 'source';
    downloadBlob(new Blob([result.csv], { type: 'text/csv;charset=utf-8' }), `generated-data-${sourceName}.csv`);
  };

  return (
    <Page
      title="Tạo dữ liệu"
      subtitle="Sinh dữ liệu sản phẩm thay thế hoặc có căn cứ từ trang thô đã thu thập."
      actions={
        <>
          <button onClick={reload}><RefreshCw />Tải lại</button>
          <button onClick={generateData} disabled={state === 'loading' || !form.sourceId}><Sparkles />{state === 'loading' ? 'Đang sinh...' : 'Sinh dữ liệu'}</button>
          {result?.csv && <button onClick={downloadCsv}><Download />Tải CSV</button>}
        </>
      }
    >
      {notice && <p className={`route-notice ${notice.tone}`}>{notice.text}</p>}
      <StatePanel resource={resource} onRetry={reload} empty={!sources.length}>
        <div className="detail-route-grid">
          <Panel title="Cấu hình tạo dữ liệu">
            <div className="synthetic-form-grid">
              <label className="pipeline-field pipeline-field--wide">
                <span>Nguồn dữ liệu</span>
                <select value={form.sourceId} onChange={(event) => updateForm({ sourceId: event.target.value, productTypes: '', referenceSources: '' })}>
                  {sources.map((source) => (
                    <option key={source.id} value={source.id}>
                      {source.name || hostFromUrl(source.url)} · {source.category || '-'} · {hostFromUrl(source.url)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="pipeline-field">
                <span>Số dòng</span>
                <input type="number" min="1" max="200" value={form.rowCount} onChange={(event) => updateForm({ rowCount: event.target.value })} />
              </label>
              <label className="pipeline-field">
                <span>Khu vực</span>
                <input value={form.region} onChange={(event) => updateForm({ region: event.target.value })} />
              </label>
              <label className="pipeline-field">
                <span>Chế độ</span>
                <select value={form.generationMode} onChange={(event) => updateForm({ generationMode: event.target.value })}>
                  <option value="synthetic">Synthetic</option>
                  <option value="grounded_synthetic">Grounded synthetic</option>
                </select>
              </label>
              <label className="pipeline-field pipeline-checkbox">
                <input type="checkbox" checked={form.persist} onChange={(event) => updateForm({ persist: event.target.checked })} />
                <span>Lưu vào kho dữ liệu</span>
              </label>
              <label className="pipeline-field pipeline-field--wide">
                <span>Loại sản phẩm</span>
                <textarea value={form.productTypes} onChange={(event) => updateForm({ productTypes: event.target.value })} />
              </label>
              <label className="pipeline-field pipeline-field--wide">
                <span>Nguồn tham khảo</span>
                <textarea value={form.referenceSources} onChange={(event) => updateForm({ referenceSources: event.target.value })} />
              </label>
              <label className="pipeline-field pipeline-field--wide">
                <span>Cột đầu ra</span>
                <textarea value={form.outputColumns} onChange={(event) => updateForm({ outputColumns: event.target.value })} />
              </label>
            </div>
          </Panel>

          <Panel title="Nguồn đang chọn">
            <dl className="route-dl">
              <dt>Tên</dt><dd>{selectedSource?.name || '-'}</dd>
              <dt>Tên miền</dt><dd>{hostFromUrl(selectedSource?.url || '')}</dd>
              <dt>Danh mục</dt><dd>{selectedSource?.category || '-'}</dd>
              <dt>Trang thô</dt><dd><Pill tone={selectedSource?.has_raw_data ? 'good' : 'warning'}>{selectedSource?.has_raw_data ? 'Đã có' : 'Chưa có'}</Pill></dd>
              <dt>Sản phẩm</dt><dd>{Number(selectedSource?.product_count || 0).toLocaleString('vi-VN')}</dd>
            </dl>
          </Panel>

          <Panel
            title="Prompt tạo dữ liệu"
            actions={<button onClick={savePrompt} disabled={promptState === 'loading' || !promptDraft.trim()}><Save />{promptState === 'loading' ? 'Đang lưu...' : 'Lưu prompt'}</button>}
          >
            <textarea
              className="prompt-editor"
              value={promptDraft}
              onChange={(event) => setPromptDraft(event.target.value)}
            />
          </Panel>

          <Panel title="Kết quả sinh dữ liệu">
            {state === 'idle' ? (
              <div className="route-state empty"><Sparkles />Chọn nguồn và bấm Sinh dữ liệu.</div>
            ) : state === 'loading' ? (
              <div className="route-state loading"><RefreshCw />Đang gọi Gemini và kiểm tra dữ liệu...</div>
            ) : result?.error ? (
              <div className="route-state error"><X />{result.error}</div>
            ) : (
              <div className="synthetic-result">
                <dl className="route-dl">
                  <dt>Số dòng</dt><dd>{result?.summary?.total || 0}</dd>
                  <dt>Model</dt><dd>{result?.model || '-'}</dd>
                  <dt>Kiểm tra</dt><dd><Pill tone={result?.validation?.accepted ? 'good' : 'bad'}>{result?.validation?.status || '-'}</Pill></dd>
                  <dt>Đã lưu</dt><dd>{result?.persisted ? `${result.persisted.rows} dòng · ${result.persisted.collection}` : 'Chưa lưu'}</dd>
                </dl>
                <pre>{result?.markdown}</pre>
                <pre>{result?.csv}</pre>
              </div>
            )}
          </Panel>

          <Panel title="Batch dữ liệu gần đây">
            <StatePanel resource={{ status: 'ready' }} empty={!batches.length}>
              <TableShell className="pipeline-table-wrapper" tableClassName="pipeline-table">
                <thead><tr><th>Batch</th><th>Nguồn</th><th>Dòng</th><th>Chế độ</th><th>Trạng thái</th><th>Cập nhật</th><th>Duyệt</th></tr></thead>
                <tbody>
                  {batches.map((batch) => (
                    <tr key={batch.batch_id}>
                      <td><b>{batch.batch_id}</b><small>{batch.model || '-'}</small></td>
                      <td>{batch.source_name || batch.source_domain || '-'}</td>
                      <td>{batch.rows || 0}</td>
                      <td><Pill>{statusLabel(batch.data_origin)}</Pill></td>
                      <td><Pill tone={statusTone(batch.review_status)}>{statusLabel(batch.review_status)}</Pill></td>
                      <td>{batch.updated_at ? new Date(batch.updated_at).toLocaleString() : '-'}</td>
                      <td>
                        <button onClick={() => decideBatch(batch, 'approved')} disabled={batch.collection !== 'sc_synthetic_products'}><Check />Duyệt</button>
                        <button onClick={() => decideBatch(batch, 'rejected')} disabled={batch.collection !== 'sc_synthetic_products'}><X />Loại</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableShell>
            </StatePanel>
          </Panel>
        </div>
      </StatePanel>
    </Page>
  );
}
