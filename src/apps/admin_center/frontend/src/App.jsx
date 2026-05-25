import React, { useState } from 'react';
import axios from 'axios';
import { CircleDot } from 'lucide-react';
import SourceModal from './components/SourceModal';
import Toast from './components/Toast';
import {
  classifyApiError,
  DashboardPage,
  DedupPage,
  AiReviewPage,
  ExtractionRulesPage,
  ProductsPage,
  RunDetailPage,
  RunsPage,
  SourceDetailPage,
  SourcesPage,
  StoresPage,
  TaskRawPage,
  UnknownPage
} from './pages/adminRoutes';
import { navGroups, segment, useRoute } from './routeShell';
import './admin-console.css';

function App() {
  const [path, navigate] = useRoute();
  const [modalOpen, setModalOpen] = useState(false);
  const [message, setMessage] = useState(null);
  const routePath = path.split('?')[0];
  const sourceId = segment(routePath, '/sources/');
  const runId = segment(routePath, '/runs/');
  const taskId = routePath.startsWith('/tasks/') ? segment(routePath, '/tasks/') : null;
  const activeTitle = navGroups.flatMap((group) => group.items).find(([to]) => routePath === to || routePath.startsWith(`${to}/`))?.[1] || 'Trang không xác định';

  const saveSource = async (formData) => {
    try {
      await axios.post('/api/sources', formData);
      setModalOpen(false);
      setMessage({ type: 'success', text: 'Đã tạo nguồn. Tải lại danh sách để xem dữ liệu mới.' });
    } catch (error) {
      const failure = classifyApiError(error);
      setMessage({ type: failure.kind === 'permission' ? 'warning' : 'error', text: failure.message });
    }
  };

  let content;
  if (routePath === '/dashboard') content = <DashboardPage navigate={navigate} />;
  else if (routePath === '/sources') content = <SourcesPage navigate={navigate} onAdd={() => setModalOpen(true)} />;
  else if (sourceId) content = <SourceDetailPage sourceId={sourceId} navigate={navigate} />;
  else if (routePath === '/runs') content = <RunsPage navigate={navigate} />;
  else if (runId) content = <RunDetailPage jobId={runId} navigate={navigate} />;
  else if (routePath === '/products') content = <ProductsPage route={path} />;
  else if (routePath === '/stores') content = <StoresPage navigate={navigate} />;
  else if (routePath === '/extraction/rules') content = <ExtractionRulesPage />;
  else if (routePath === '/ai/review') content = <AiReviewPage navigate={navigate} />;
  else if (taskId) content = <TaskRawPage jobId={taskId} navigate={navigate} />;
  else if (routePath === '/dedup') content = <DedupPage />;
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
      <SourceModal isOpen={modalOpen} onClose={() => setModalOpen(false)} onSave={saveSource} editingSource={null} />
      <Toast message={message} />
    </div>
  );
}

export default App;
