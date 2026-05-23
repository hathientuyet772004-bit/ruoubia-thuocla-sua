import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { CircleDot } from 'lucide-react';
import AdminLogin from './components/AdminLogin';
import SourceModal from './components/SourceModal';
import Toast from './components/Toast';
import {
  classifyApiError,
  DashboardPage,
  DedupPage,
  ExtractionRulesPage,
  ProductsPage,
  RunDetailPage,
  RunsPage,
  SourceDetailPage,
  SourcesPage,
  TaskRawPage,
  UnknownPage
} from './pages/adminRoutes';
import { navGroups, segment, useRoute } from './routeShell';
import './admin-console.css';

function App() {
  const [path, navigate] = useRoute();
  const [modalOpen, setModalOpen] = useState(false);
  const [message, setMessage] = useState(null);
  const [session, setSession] = useState({ status: 'loading', data: null });
  const sourceId = segment(path, '/sources/');
  const runId = segment(path, '/runs/');
  const taskId = path.startsWith('/tasks/') ? segment(path, '/tasks/') : null;
  const activeTitle = navGroups.flatMap((group) => group.items).find(([to]) => path === to || path.startsWith(`${to}/`))?.[1] || 'Trang không xác định';

  useEffect(() => {
    axios.get('/api/auth/session')
      .then((response) => setSession({ status: 'ready', data: response.data }))
      .catch(() => setSession({ status: 'login', data: null }));
  }, []);

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
  if (path === '/dashboard') content = <DashboardPage navigate={navigate} />;
  else if (path === '/sources') content = <SourcesPage navigate={navigate} onAdd={() => setModalOpen(true)} />;
  else if (sourceId) content = <SourceDetailPage sourceId={sourceId} navigate={navigate} />;
  else if (path === '/runs') content = <RunsPage navigate={navigate} />;
  else if (runId) content = <RunDetailPage jobId={runId} navigate={navigate} />;
  else if (path === '/products') content = <ProductsPage />;
  else if (path === '/extraction/rules') content = <ExtractionRulesPage />;
  else if (taskId) content = <TaskRawPage jobId={taskId} navigate={navigate} />;
  else if (path === '/dedup') content = <DedupPage />;
  else content = <UnknownPage navigate={navigate} />;

  if (session.status === 'loading') return <div className="admin-login loading">Đang kiểm tra phiên quản trị...</div>;
  if (session.status === 'login') return <AdminLogin onLogin={(data) => setSession({ status: 'ready', data })} />;

  return (
    <div className="ops-app routed-app">
      <aside className="ops-sidebar">
        <div className="ops-brand"><CircleDot /><strong>Nền tảng thu thập</strong></div>
        {navGroups.map((group) => (
          <section className="route-nav-group" key={group.label}>
            <small>{group.label}</small>
            <nav>{group.items.map(([to, label, Icon]) => <button key={to} className={path === to || path.startsWith(`${to}/`) ? 'active' : ''} onClick={() => navigate(to)} title={label}><Icon /><span>{label}</span></button>)}</nav>
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
