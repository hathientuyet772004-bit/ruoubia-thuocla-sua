import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { FileSearch, RefreshCw } from 'lucide-react';
import { classifyApiError, fetchApiList } from '../apiClient';
import { useApiResource } from '../shared/hooks';
import { extractionTargetLabel } from '../shared/utils';
import { Page, Panel, Pill, StatePanel } from '../shared/ui';

const API_BASE = '/api';

function PreviewRows({ rows }) {
  return (
    <table className="selector-preview-table">
      <thead><tr><th>Trường</th><th>Số khớp</th><th>Mẫu</th></tr></thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.name}>
            <td>{row.name}</td>
            <td><Pill tone={row.matches ? 'good' : row.required ? 'bad' : 'warning'}>{row.matches}</Pill></td>
            <td>{row.sample || '-'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ExtractionRulesPage() {
  const [domain, setDomain] = useState('');
  const [target, setTarget] = useState('product_detail');
  const [artifactId, setArtifactId] = useState('');
  const [fields, setFields] = useState([]);
  const [previewRows, setPreviewRows] = useState([]);
  const [notice, setNotice] = useState(null);
  const [rules, reloadRules] = useApiResource(() => fetchApiList('/extraction/rules'), []);

  useEffect(() => {
    if (!domain && rules.data?.length) setDomain(rules.data[0].domain);
  }, [domain, rules.data]);

  const [rule, reloadRule] = useApiResource(
    () => domain
      ? axios.get(`${API_BASE}/extraction/rules/${domain}`, { params: { target, raw_artifact_id: artifactId || undefined } }).then((r) => r.data)
      : Promise.resolve(null),
    [domain, target, artifactId]
  );

  useEffect(() => {
    if (rule.data?.target && rule.data.target !== target) setTarget(rule.data.target);
    setFields(rule.data?.fields || []);
    setPreviewRows(rule.data?.preview || []);
    if (!artifactId && rule.data?.raw_page?.id) setArtifactId(rule.data.raw_page.id);
  }, [artifactId, rule.data, target]);

  const selectDomain = (nextDomain) => {
    setDomain(nextDomain);
    setTarget('product_detail');
    setArtifactId('');
  };

  const updateField = (name, selector) =>
    setFields((cur) => cur.map((f) => f.name === name ? { ...f, selector } : f));

  const testRule = async () => {
    try {
      const response = await axios.post(`${API_BASE}/extraction/rules/${domain}/preview`, { target, fields, raw_artifact_id: artifactId || undefined });
      setPreviewRows(response.data.preview || []);
      setNotice({ tone: 'good', text: `Đã kiểm thử xem trước với ${response.data.raw_page?.filename || 'trang thô trống'}.` });
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };

  const saveRule = async () => {
    try {
      await axios.patch(`${API_BASE}/extraction/rules/${domain}`, { target, fields, expected_version: rule.data.version, raw_artifact_id: artifactId || undefined });
      setNotice({ tone: 'good', text: 'Đã lưu quy tắc selector vào bộ nhớ cấu trúc.' });
      reloadRule();
      reloadRules();
    } catch (error) {
      const failure = classifyApiError(error);
      setNotice({ tone: 'bad', text: failure.message });
    }
  };

  return (
    <Page
      title="Trình dựng quy tắc trích xuất"
      subtitle="Chọn trang thô, kiểm thử selector và lưu quy tắc theo tên miền."
      actions={
        <>
          <select value={domain} onChange={(e) => selectDomain(e.target.value)}>
            {(rules.data || []).map((item) => <option key={item.domain}>{item.domain}</option>)}
          </select>
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            {(rule.data?.targets || ['product_detail']).map((t) => <option key={t} value={t}>{extractionTargetLabel(t)}</option>)}
          </select>
          <select value={artifactId} onChange={(e) => setArtifactId(e.target.value)}>
            <option value="">Trang thô mới nhất</option>
            {(rule.data?.raw_artifacts || []).map((a) => <option key={a.id} value={a.id}>{a.filename}</option>)}
          </select>
          <button onClick={reloadRule}><RefreshCw />Tải lại</button>
        </>
      }
    >
      <StatePanel resource={rules} onRetry={reloadRules} empty={!rules.data?.length}>
        <StatePanel resource={rule} onRetry={reloadRule} empty={!rule.data}>
          <div className="builder-route-grid live-rule-grid">
            <Panel title="Mục tiêu">
              {fields.map((field) => (
                <label className="selector-field" key={field.name}>
                  {field.name}
                  {field.required ? <Pill tone="warning">bắt buộc</Pill> : null}
                  <input value={field.selector || ''} onChange={(e) => updateField(field.name, e.target.value)} />
                </label>
              ))}
            </Panel>
            <Panel title="Xem trước trang thô" className="rule-raw-panel">
              {rule.data?.raw_page ? (
                <dl className="route-dl">
                  <dt>Tệp</dt><dd>{rule.data.raw_page.filename}</dd>
                  <dt>Tác vụ</dt><dd>{rule.data.raw_page.task_id}</dd>
                  <dt>Loại trang</dt><dd>{extractionTargetLabel(rule.data.raw_page.page_type)}</dd>
                  <dt>Đường dẫn</dt><dd>{rule.data.raw_page.path}</dd>
                  <dt>Cập nhật</dt><dd>{new Date(rule.data.raw_page.updated_at).toLocaleString()}</dd>
                </dl>
              ) : (
                <div className="route-state empty"><FileSearch />Tên miền này chưa có MHTML thô để kiểm thử selector.</div>
              )}
              <pre>{JSON.stringify({ target, fields, version: rule.data?.version }, null, 2)}</pre>
            </Panel>
            <Panel
              title="Xem trước selector"
              actions={
                <>
                  <button onClick={testRule}><RefreshCw />Kiểm thử</button>
                  <button onClick={saveRule}>Lưu quy tắc</button>
                </>
              }
            >
              {notice && <p className={`route-notice ${notice.tone}`}>{notice.text}</p>}
              {previewRows.length > 0
                ? <PreviewRows rows={previewRows} />
                : <div className="route-state empty"><FileSearch />Bấm Kiểm thử để xem kết quả.</div>}
            </Panel>
          </div>
        </StatePanel>
      </StatePanel>
    </Page>
  );
}
