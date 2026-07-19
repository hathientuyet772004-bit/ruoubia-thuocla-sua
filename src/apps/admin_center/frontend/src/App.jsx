import React, { useState } from 'react';
import axios from 'axios';
import { CircleDot } from 'lucide-react';
import SourceModal from './components/SourceModal';
import Toast from './components/Toast';
import {
  classifyApiError,
  DashboardPage,
  ExtractionRulesPage,
  GenDataPage,
  PipelinesPage,
  ProductsPage,
  RunDetailPage,
  RunsPage,
  SourceDetailPage,
  SourcesPage,
  TaskRawPage,
  UnknownPage,
  RuleReviewPage
} from './pages/adminRoutes';
import { navGroups, segment, useRoute } from './routeShell';
import './admin-console.css';

function App() {
  const [path, navigate] = useRoute();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingSource, setEditingSource] = useState(null);
  const [message, setMessage] = useState(null);
  const routePath = path.split('?')[0];
  const sourceId = segment(routePath, '/sources/');
  const runId = segment(routePath, '/runs/');
  const taskId = routePath.startsWith('/tasks/') ? segment(routePath, '/tasks/') : null;
  const activeTitle = navGroups.flatMap((group) => group.items).find(([to]) => routePath === to || routePath.startsWith(`${to}/`))?.[1] || 'Trang không xác định';

  const saveSource = async (formData) => {
    try {
      if (editingSource) {
        await axios.put(`/api/sources/${editingSource.id}`, formData);
        setMessage({ type: 'success', text: 'Đã cập nhật thông tin nguồn thành công.' });
      } else {
        await axios.post('/api/sources', formData);
        setMessage({ type: 'success', text: 'Đã tạo nguồn. Tải lại danh sách để xem dữ liệu mới.' });
      }
      setModalOpen(false);
      setEditingSource(null);
    } catch (error) {
      const failure = classifyApiError(error);
      setMessage({ type: failure.kind === 'permission' ? 'warning' : 'error', text: failure.message });
    }
  };

  let content;
  if (routePath === '/dashboard') content = <DashboardPage navigate={navigate} />;
  else if (routePath === '/sources') content = <SourcesPage navigate={navigate} onAdd={() => { setEditingSource(null); setModalOpen(true); }} onEdit={(src) => { setEditingSource(src); setModalOpen(true); }} />;
  else if (sourceId) content = <SourceDetailPage sourceId={sourceId} navigate={navigate} />;
  else if (routePath === '/collection') content = <PipelinesPage navigate={navigate} />;
  else if (routePath === '/gen-data') content = <GenDataPage navigate={navigate} />;
  else if (routePath === '/runs') content = <RunsPage navigate={navigate} />;
  else if (runId) content = <RunDetailPage jobId={runId} navigate={navigate} />;
  else if (routePath === '/products') content = <ProductsPage route={path} />;
  else if (routePath === '/extraction/rules') content = <ExtractionRulesPage navigate={navigate} />;
  else if (routePath === '/extraction/candidates') content = <RuleReviewPage navigate={navigate} />;
  else if (taskId) content = <TaskRawPage jobId={taskId} navigate={navigate} />;
  else content = <UnknownPage navigate={navigate} />;

  return (
    <div className="ops-app routed-app">
      <aside className="ops-sidebar">
        <div className="ops-brand"><CircleDot /><strong>Nền tảng thu thập</strong></div>
        {navGroups.map((group) => (
          <section className="route-nav-group" key={group.label}>
            <small>{group.label}</small>
            <nav>{group.items.map(([to, label, Icon]) => <button key={to} className={routePath === to || routePath.startsWith(`${to}/`) ? 'active' : ''} onClick={() => navigate(to)} title={label}><Icon /><span>{label}</span></button>)}</nav>
          </section>
        ))}
      </aside>
      <main className="route-main">
        <header className="ops-topbar"><strong>Trung tâm quản trị</strong><span>{activeTitle}</span></header>
        {content}
      </main>
      <SourceModal isOpen={modalOpen} onClose={() => { setModalOpen(false); setEditingSource(null); }} onSave={saveSource} editingSource={editingSource} />
      <Toast message={message} />
    </div>
  );
}

export default App;
