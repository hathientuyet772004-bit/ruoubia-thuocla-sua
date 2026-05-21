import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  BarChart3,
  LayoutDashboard,
  MousePointer2,
  Settings as SettingsIcon,
  CheckCircle2,
  Clock,
  AlertCircle,
  Database,
  Search,
  ExternalLink,
  RefreshCw,
  Layers,
  Globe,
  Beer,
  Baby,
  Flame,
  Filter,
  Plus,
  Edit,
  Trash2,
  Activity,
  History,
  FileText,
  Monitor,
  X
} from 'lucide-react';

// Components
import UrlBar from './components/UrlBar';
import Toast from './components/Toast';
import SourceModal from './components/SourceModal';
import ProductCard from './components/ProductCard';

const API_BASE = '/api';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [stats, setStats] = useState(null);
  const [products, setProducts] = useState([]);
  const [sources, setSources] = useState([]);
  const [sourceOptions, setSourceOptions] = useState(['all']);
  const [selectedSource, setSelectedSource] = useState('all');
  const [selectedSourceGroup, setSelectedSourceGroup] = useState('all');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [trends, setTrends] = useState([]);
  const [comparison, setComparison] = useState([]);

  // Collector States
  const [url, setUrl] = useState('');
  const [browserActive, setBrowserActive] = useState(false);
  const [loadTime, setLoadTime] = useState(null);
  const [pageType, setPageType] = useState(null);

  // Master Data States
  const [masterProducts, setMasterProducts] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterSource, setFilterSource] = useState('all');

  // Job Monitor States
  const [jobs, setJobs] = useState([]);
  const [jobStats, setJobStats] = useState({ pending: 0, completed: 0, failed: 0 });
  const [selectedJobLog, setSelectedJobLog] = useState(null);

  // Modal States
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingSource, setEditingSource] = useState(null);

  useEffect(() => {
    fetchDashboardData();
    fetchSources();
    fetchMasterProducts();
    fetchJobs();
    const interval = setInterval(() => {
      fetchDashboardData();
      if (activeTab === 'jobs') fetchJobs();
    }, 10000); // 10s refresh for monitor
    return () => clearInterval(interval);
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === 'products') {
      fetchMasterProducts();
    }
  }, [searchQuery, filterCategory, filterSource, activeTab]);

  const fetchDashboardData = async () => {
    try {
      const statsRes = await axios.get(`${API_BASE}/dashboard/stats`);
      setStats(statsRes.data);

      const prodRes = await axios.get(`${API_BASE}/dashboard/recent-products`);
      setProducts(prodRes.data);

      const sourceOptRes = await axios.get(`${API_BASE}/dashboard/sources`);
      setSourceOptions(sourceOptRes.data);

      const trendRes = await axios.get(`${API_BASE}/dashboard/trends`);
      setTrends(trendRes.data);

      const compRes = await axios.get(`${API_BASE}/dashboard/comparison`);
      setComparison(compRes.data);
    } catch (err) {
      console.error("Fetch data failed", err);
    }
  };

  const fetchSources = async () => {
    try {
      const res = await axios.get(`${API_BASE}/sources`);
      setSources(res.data);
    } catch (err) {
      console.error("Fetch sources failed", err);
    }
  };

  const fetchMasterProducts = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/products/search`, {
        params: {
          q: searchQuery,
          category: filterCategory,
          source: filterSource
        }
      });
      setMasterProducts(res.data);
    } catch (err) {
      console.error("Fetch products failed", err);
    } finally {
      setLoading(false);
    }
  };

  const handleLaunchBrowser = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/browser/launch`, { url: url || 'https://google.com' });
      setBrowserActive(true);
      showToast("Browser launched successfully");
      if (res.data.url) setUrl(res.data.url);
    } catch (err) {
      showToast("Failed to launch browser", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleNavigate = async (e) => {
    if (e) e.preventDefault();
    if (!url) return;

    if (browserActive) {
      try {
        await axios.post(`${API_BASE}/browser/navigate`, { url });
      } catch (err) {
        showToast("Navigation failed", "error");
      }
    } else {
      window.open(url, '_blank');
    }
  };

  const handleCollect = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/browser/collect`);
      showToast(`Captured: ${res.data.title}`);
      fetchDashboardData();
    } catch (err) {
      showToast("Collection failed", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleCloseBrowser = async () => {
    try {
      await axios.post(`${API_BASE}/browser/close`);
      setBrowserActive(false);
      showToast("Browser closed");
    } catch (err) {
      console.error(err);
    }
  };

  const fetchJobs = async () => {
    try {
      const res = await axios.get(`${API_BASE}/jobs`);
      setJobs(res.data);
      // Calculate stats
      const stats = {
        pending: res.data.filter(j => j.status === 'Pending').length,
        completed: res.data.filter(j => j.status === 'Completed').length,
        failed: res.data.filter(j => j.status === 'Failed').length,
      };
      setJobStats(stats);
    } catch (err) {
      console.error("Fetch jobs failed", err);
    }
  };

  const handleRetryJob = async (jobId) => {
    try {
      const res = await axios.post(`${API_BASE}/jobs/retry/${jobId}`);
      showToast(res.data.message);
      fetchJobs();
    } catch (err) {
      showToast("Retry failed", "error");
    }
  };

  const handleViewLogs = async (jobId) => {
    try {
      const res = await axios.get(`${API_BASE}/jobs/logs/${jobId}`);
      if (res.data.error) {
        showToast(res.data.error, "error");
        return;
      }
      setSelectedJobLog(res.data);
    } catch (err) {
      showToast("Failed to fetch logs", "error");
    }
  };

  const handleSourceChange = async (source) => {
    setSelectedSource(source);
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/dashboard/recent-products?source=${source}`);
      setProducts(res.data);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSource = async (formData) => {
    try {
      if (editingSource) {
        await axios.put(`${API_BASE}/sources/${editingSource.id}`, formData);
        setMessage({ type: 'success', text: 'Cập nhật nguồn thành công!' });
      } else {
        await axios.post(`${API_BASE}/sources`, formData);
        setMessage({ type: 'success', text: 'Thêm nguồn mới thành công!' });
      }
      setIsModalOpen(false);
      fetchSources();
    } catch (err) {
      setMessage({ type: 'error', text: 'Lỗi khi lưu nguồn: ' + err.message });
    }
  };

  const handleDeleteSource = async (id) => {
    if (!window.confirm('Bạn có chắc chắn muốn xóa website này?')) return;
    try {
      await axios.delete(`${API_BASE}/sources/${id}`);
      setMessage({ type: 'success', text: 'Đã xóa nguồn.' });
      fetchSources();
    } catch (err) {
      setMessage({ type: 'error', text: 'Lỗi khi xóa: ' + err.message });
    }
  };

  const filteredSources = sources.filter(s => {
    if (selectedSourceGroup === 'all') return true;
    return s.group === selectedSourceGroup;
  });

  const getSourceIcon = (group) => {
    if (group === 'Rượu bia') return <Beer size={20} color="#e67e22" />;
    if (group === 'Thuốc lá') return <Flame size={20} color="#95a5a6" />;
    if (group === 'Sữa') return <Baby size={20} color="#3498db" />;
    return <Globe size={20} />;
  };

  return (
    <div className="admin-container">
      {/* Sidebar */}
      <aside className="admin-sidebar glass-morphism">
        <div className="brand">
          <Layers className="icon-pulse" color="var(--accent-cyan)" />
          <span>Admin Center</span>
        </div>

        <nav className="nav-menu">
          <button
            className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <LayoutDashboard size={20} />
            <span>Dashboard</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'sources' ? 'active' : ''}`}
            onClick={() => setActiveTab('sources')}
          >
            <Globe size={20} />
            <span>Manage Sources</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'products' ? 'active' : ''}`}
            onClick={() => setActiveTab('products')}
          >
            <Database size={20} />
            <span>Master Data</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'jobs' ? 'active' : ''}`}
            onClick={() => setActiveTab('jobs')}
          >
            <Activity size={20} />
            <span>Job Monitor</span>
          </button>

          <button
            className={`nav-item ${activeTab === 'collector' ? 'active' : ''}`}
            onClick={() => setActiveTab('collector')}
          >
            <MousePointer2 size={20} />
            <span>Interactive Collector</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="system-health">
            <div className="status-dot online"></div>
            <span>Backend Online</span>
          </div>
        </div>
      </aside>

      <main className="admin-main">
        {activeTab === 'dashboard' && (
          <div className="dashboard-view animate-fade-in">
            <header className="view-header">
              <h1>Project Overview</h1>
              <button className="btn-refresh" onClick={fetchDashboardData}>
                <RefreshCw size={16} />
              </button>
            </header>

            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-header">
                  <Database size={24} color="#3498db" />
                  <span>Gold Products</span>
                </div>
                <div className="stat-value">{stats?.products?.total || 0}</div>
                <div className="stat-subtitle">{stats?.products?.sources || 0} Sources tracked</div>
              </div>

              <div className="stat-card">
                <div className="stat-header">
                  <Clock size={24} color="#f1c40f" />
                  <span>Pending Tasks</span>
                </div>
                <div className="stat-value">{stats?.files?.pending || 0}</div>
                <div className="stat-subtitle">Files waiting in Bronze</div>
              </div>

              <div className="stat-card">
                <div className="stat-header">
                  <CheckCircle2 size={24} color="#2ecc71" />
                  <span>Completed</span>
                </div>
                <div className="stat-value">{stats?.files?.completed || 0}</div>
                <div className="stat-subtitle">Successful AI Extractions</div>
              </div>

              <div className="stat-card">
                <div className="stat-header">
                  <AlertCircle size={24} color="#e74c3c" />
                  <span>Failures</span>
                </div>
                <div className="stat-value">{stats?.files?.failed || 0}</div>
                <div className="stat-subtitle">Requires attention</div>
              </div>

              <div className="stat-card market-highlight">
                <div className="stat-header">
                  <Beer size={24} color="#e67e22" />
                  <span>Avg Market Price</span>
                </div>
                <div className="stat-value">
                  {stats?.market?.avg_price?.toLocaleString()} <span className="currency">{stats?.market?.currency}</span>
                </div>
                <div className="stat-subtitle trend-up">{stats?.market?.trend}</div>
              </div>
            </div>

            <div className="dashboard-grid">
              <section className="data-section trends-card glass-morphism">
                <div className="section-header">
                  <h2>Monthly Price Trends</h2>
                  <span className="badge">Market Insights</span>
                </div>
                <div className="chart-placeholder">
                  <div className="bars-container">
                    {trends.map((t, idx) => (
                      <div key={idx} className="bar-wrapper">
                        <div
                          className="chart-bar"
                          style={{
                            height: `${(t.avg_price / 500000) * 100}%`,
                            opacity: idx === trends.length - 1 ? 1 : 0.6
                          }}
                        >
                          <span className="bar-value">{t.avg_price / 1000}k</span>
                        </div>
                        <span className="bar-label">{t.month}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

              <section className="data-section trends-card glass-morphism">
                <div className="section-header">
                  <h2>Source Price Comparison</h2>
                  <span className="badge">Market Leaderboard</span>
                </div>
                <div className="comparison-container">
                  {comparison.map((c, idx) => (
                    <div key={idx} className="comp-row">
                      <div className="comp-label">{c.source}</div>
                      <div className="comp-bar-wrapper">
                        <div
                          className="comp-bar"
                          style={{ width: `${(c.avg_price / 500000) * 100}%` }}
                        >
                          <span className="comp-value">{c.avg_price?.toLocaleString()}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            <section className="data-section glass-morphism full-width">
              <div className="section-header">
                <h2>Recent Products (Gold Layer)</h2>
                <select className="source-select" value={selectedSource} onChange={(e) => handleSourceChange(e.target.value)}>
                  {sourceOptions.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>

              <div className="table-container">
                <table className="admin-table">
                  <thead>
                    <tr><th>Name</th><th>Price</th><th>Source</th><th>Updated</th></tr>
                  </thead>
                  <tbody>
                    {products.map((p, idx) => (
                      <tr key={idx}>
                        <td className="col-name">{p.name}</td>
                        <td className="col-price">{p.price_numeric} {p.currency}</td>
                        <td className="col-source"><span className="badge">{p.source_site}</span></td>
                        <td className="col-time">{new Date(p.updated_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}

        {activeTab === 'sources' && (
          <div className="sources-view animate-fade-in">
            <header className="view-header">
              <h1>Source Management</h1>
              <div className="header-actions">
                <div className="filter-group">
                  <Filter size={16} />
                  <select
                    className="group-filter"
                    value={selectedSourceGroup}
                    onChange={(e) => setSelectedSourceGroup(e.target.value)}
                  >
                    <option value="all">All Groups</option>
                    <option value="Rượu bia">Rượu bia</option>
                    <option value="Thuốc lá">Thuốc lá</option>
                    <option value="Sữa">Sữa</option>
                  </select>
                </div>
                <button className="btn-add-source" onClick={() => { setEditingSource(null); setIsModalOpen(true); }}>
                  <Plus size={16} /> Add Source
                </button>
              </div>
            </header>

            <div className="sources-grid">
              {filteredSources.map(s => (
                <div className="source-card glass-morphism" key={s.id}>
                  <div className="source-icon">
                    {getSourceIcon(s.group)}
                    {s.saved_locally && (
                      <div className="local-indicator" title="Dữ liệu đã có trên máy">
                        <div className="status-dot online"></div>
                      </div>
                    )}
                  </div>
                  <div className="source-details">
                    <div className="title-row">
                      <h3>{s.name}</h3>
                      <div className="card-actions">
                        <button className="icon-btn" onClick={() => { setEditingSource(s); setIsModalOpen(true); }}><Edit size={14} /></button>
                        <button className="icon-btn delete" onClick={() => handleDeleteSource(s.id)}><Trash2 size={14} /></button>
                      </div>
                    </div>
                    <p className="source-url">{s.url}</p>
                    <div className="source-tags">
                      <span className={`group-tag ${s.group.replace(' ', '-').toLowerCase()}`}>{s.group}</span>
                      <span className="type-tag">{s.type}</span>
                    </div>
                    {s.note && <p className="source-note">"{s.note}"</p>}
                  </div>
                  <div className="source-actions">
                    <button className="btn-visit" onClick={() => window.open(s.url, '_blank')}>
                      Visit <ExternalLink size={12} />
                    </button>
                    <button className="btn-target" onClick={() => { setUrl(s.url); setActiveTab('collector'); }}>
                      Collect
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'products' && (
          <div className="products-view animate-fade-in">
            <header className="view-header">
              <h1>Master Product Explorer</h1>
              <div className="header-actions">
                <div className="search-box">
                  <Search size={16} />
                  <input
                    type="text"
                    placeholder="Search products..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <select className="group-filter" value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
                  <option value="all">All Categories</option>
                  <option value="Rượu bia">Rượu bia</option>
                  <option value="Thuốc lá">Thuốc lá</option>
                  <option value="Sữa">Sữa</option>
                </select>
                <select className="group-filter" value={filterSource} onChange={(e) => setFilterSource(e.target.value)}>
                  {sourceOptions.map(s => <option key={s} value={s}>{s === 'all' ? 'All Sources' : s}</option>)}
                </select>
              </div>
            </header>

            {loading && <div className="loading-spinner">Searching...</div>}

            <div className="products-grid">
              {masterProducts.map((p, idx) => (
                <ProductCard key={idx} product={p} />
              ))}
              {masterProducts.length === 0 && !loading && (
                <div className="empty-state">No products found for these filters.</div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'jobs' && (
          <div className="jobs-view animate-fade-in">
            <header className="view-header">
              <h1>AI Processing Monitor</h1>
              <div className="job-summary-badges">
                <span className="job-badge pending">Pending: {jobStats.pending}</span>
                <span className="job-badge completed">Completed: {jobStats.completed}</span>
                <span className="job-badge failed">Failed: {jobStats.failed}</span>
              </div>
            </header>

            <div className="table-container glass-morphism">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>File ID</th>
                    <th>Source</th>
                    <th>Status</th>
                    <th>Last Updated</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map(job => (
                    <tr key={job.id}>
                      <td className="col-id"><FileText size={14} /> {job.filename}</td>
                      <td><span className="source-tag">{job.source}</span></td>
                      <td>
                        <span className={`status-pill ${job.status.toLowerCase()}`}>
                          {job.status}
                        </span>
                      </td>
                      <td className="col-time">{new Date(job.timestamp).toLocaleString()}</td>
                      <td>
                        <div className="job-actions">
                          <button
                            className="btn-small logs"
                            onClick={() => handleViewLogs(job.id)}
                          >
                            Logs
                          </button>
                          <button
                            className="btn-small retry"
                            onClick={() => handleRetryJob(job.id)}
                          >
                            Retry
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {jobs.length === 0 && (
                    <tr><td colSpan="5" className="empty-row">No active or historic jobs found in store/raw.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'collector' && (
          <div className="collector-view animate-fade-in">
            <UrlBar
              url={url}
              setUrl={setUrl}
              handleNavigate={handleNavigate}
              loading={loading}
              browserActive={browserActive}
              handleLaunchBrowser={handleLaunchBrowser}
              loadTime={loadTime}
              pageType={pageType}
            />

            <div className="collector-content">
              {browserActive ? (
                <div className="browser-active-panel glass-morphism">
                  <div className="browser-info">
                    <Monitor size={48} className="pulse-icon" />
                    <h2>Trình duyệt đang hoạt động độc lập</h2>
                    <p>Bạn có thể điều khiển trực tiếp tại cửa sổ Chrome vừa mở.</p>
                  </div>
                  <div className="browser-actions">
                    <button className="btn-collect" onClick={handleCollect} disabled={loading}>
                      {loading ? <RefreshCw className="animate-spin" /> : <Layers />}
                      Hút dữ liệu (Capture MHTML)
                    </button>
                    <button className="btn-close-browser" onClick={handleCloseBrowser}>
                      Đóng trình duyệt
                    </button>
                  </div>
                </div>
              ) : (
                <div className="collector-placeholder">
                  <MousePointer2 size={48} color="#8b949e" />
                  <h2>Interactive Collector</h2>
                  <p>Sử dụng trình duyệt độc lập để vượt qua các cơ chế chặn robot và hút dữ liệu chính xác.</p>
                  <div className="collector-links">
                    {sources.slice(0, 8).map(s => (
                      <a key={s.id} href={s.url} target="_blank" rel="noreferrer" className="collector-link">
                        {s.name}
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Log Modal */}
        {selectedJobLog && (
          <div className="modal-overlay">
            <div className="modal-content log-modal glass-morphism">
              <header className="modal-header">
                <h2>Job Logs: {selectedJobLog.job_id}</h2>
                <button className="close-btn" onClick={() => setSelectedJobLog(null)}><X /></button>
              </header>
              <div className="modal-body">
                <div className="log-section">
                  <h3>Execution Timeline</h3>
                  <div className="log-events">
                    {selectedJobLog.events.map((e, idx) => <p key={idx} className="log-line">{e}</p>)}
                  </div>
                </div>

                {selectedJobLog.error && (
                  <div className="log-section error">
                    <h3>Error Report</h3>
                    <pre className="error-content">{selectedJobLog.error}</pre>
                  </div>
                )}

                {selectedJobLog.output_summary && (
                  <div className="log-section success">
                    <h3>Extraction Summary</h3>
                    <div className="summary-grid">
                      <div className="sum-item">
                        <label>Extracted Products:</label>
                        <span>{selectedJobLog.output_summary.product_count}</span>
                      </div>
                      <div className="sum-item">
                        <label>Source Site:</label>
                        <span>{selectedJobLog.output_summary.source}</span>
                      </div>
                    </div>
                  </div>
                )}

                <div className="log-section">
                  <h3>Metadata</h3>
                  <pre className="meta-content">{JSON.stringify(selectedJobLog.metadata, null, 2)}</pre>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      <SourceModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSaveSource}
        editingSource={editingSource}
      />

      <Toast message={message} />

      <style>{`
        :root {
          --bg-dark: #0a0c10;
          --panel-dark: #161b22;
          --accent-cyan: #58a6ff;
          --accent-green: #23d38a;
          --accent-amber: #e67e22;
          --text-main: #c9d1d9;
          --border-color: #30363d;
        }

        .admin-container { display: flex; height: 100vh; background: var(--bg-dark); color: var(--text-main); font-family: 'Outfit', sans-serif; }
        .admin-sidebar { width: 260px; border-right: 1px solid var(--border-color); display: flex; flex-direction: column; padding: 20px; background: rgba(22, 27, 34, 0.7); backdrop-filter: blur(10px); }
        .brand { display: flex; align-items: center; gap: 12px; font-size: 20px; font-weight: bold; margin-bottom: 40px; color: white; }
        .nav-menu { display: flex; flex-direction: column; gap: 8px; flex: 1; }
        .nav-item { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border: none; background: transparent; color: #8b949e; border-radius: 8px; cursor: pointer; transition: all 0.2s; text-align: left; }
        .nav-item:hover { background: rgba(255, 255, 255, 0.05); color: white; }
        .nav-item.active { background: rgba(88, 166, 255, 0.15); color: var(--accent-cyan); font-weight: 600; }
        .admin-main { flex: 1; padding: 40px; overflow-y: auto; }
        .view-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 40px; }
        .stat-card { background: var(--panel-dark); border: 1px solid var(--border-color); padding: 24px; border-radius: 12px; }
        .stat-header { display: flex; align-items: center; gap: 10px; color: #8b949e; font-size: 14px; margin-bottom: 12px; }
        .stat-value { font-size: 32px; font-weight: bold; color: white; margin-bottom: 4px; }
        .stat-subtitle { font-size: 12px; color: #6e7681; }

        /* Sources Styles */
        .sources-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; }
        .source-card { padding: 20px; border-radius: 12px; display: flex; gap: 20px; border: 1px solid var(--border-color); background: rgba(22, 27, 34, 0.5); }
        .source-icon { display: flex; align-items: center; justify-content: center; width: 50px; height: 50px; background: rgba(255,255,255,0.05); border-radius: 10px; flex-shrink: 0; }
        .source-details { flex: 1; }
        .source-details h3 { font-size: 18px; margin: 0 0 4px 0; color: white; }
        .source-url { font-size: 12px; color: var(--accent-cyan); margin: 0 0 12px 0; word-break: break-all; opacity: 0.8; }
        .source-tags { display: flex; gap: 8px; margin-bottom: 10px; }
        .group-tag { font-size: 10px; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
        .group-tag.rượu-bia { background: rgba(230, 126, 34, 0.15); color: #e67e22; }
        .group-tag.thuốc-lá { background: rgba(149, 165, 166, 0.15); color: #95a5a6; }
        .group-tag.sữa { background: rgba(52, 152, 219, 0.15); color: #3498db; }
        .type-tag { font-size: 10px; border: 1px solid #30363d; padding: 1px 6px; border-radius: 4px; color: #8b949e; }
        .source-note { font-size: 11px; color: #6e7681; font-style: italic; margin: 4px 0; }
        .source-actions { display: flex; flex-direction: column; gap: 8px; }
        .btn-visit, .btn-target { font-size: 12px; padding: 6px 12px; border-radius: 6px; cursor: pointer; border: 1px solid var(--border-color); background: transparent; color: white; display: flex; align-items: center; gap: 4px; }
        .btn-target { background: var(--accent-cyan); border-color: var(--accent-cyan); color: #0d1117; font-weight: bold; }

        .group-filter { background: var(--panel-dark); border: 1px solid var(--border-color); color: white; padding: 6px 12px; border-radius: 6px; }
        .filter-group { display: flex; align-items: center; gap: 10px; color: #8b949e; }
        .header-actions { display: flex; align-items: center; gap: 16px; }
        .btn-add-source { background: #2ecc71; border: none; color: #0d1117; padding: 8px 16px; border-radius: 6px; font-weight: bold; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 14px; }
        .btn-add-source:hover { filter: brightness(1.1); }

        /* Master Data Styles */
        .products-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
          gap: 20px;
        }
        .search-box {
          display: flex;
          align-items: center;
          background: var(--panel-dark);
          border: 1px solid var(--border-color);
          padding: 8px 16px;
          border-radius: 8px;
          gap: 12px;
          flex: 1;
          min-width: 300px;
        }
        .search-box input {
          background: transparent;
          border: none;
          color: white;
          outline: none;
          width: 100%;
        }
        .loading-spinner { color: var(--accent-cyan); margin: 20px 0; font-style: italic; }
        .empty-state { grid-column: 1 / -1; text-align: center; color: #484f58; padding: 60px; }

        /* Job Monitor Styles */
        .job-summary-badges { display: flex; gap: 12px; }
        .job-badge { padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; border: 1px solid transparent; }
        .job-badge.pending { background: rgba(241, 194, 15, 0.1); color: #f1c40f; border-color: rgba(241, 194, 15, 0.3); }
        .job-badge.completed { background: rgba(35, 211, 138, 0.1); color: #23d38a; border-color: rgba(35, 211, 138, 0.3); }
        .job-badge.failed { background: rgba(231, 76, 60, 0.1); color: #e74c3c; border-color: rgba(231, 76, 60, 0.3); }

        .status-pill { padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: bold; text-transform: uppercase; }
        .status-pill.pending { background: #3e3507; color: #f1c40f; }
        .status-pill.completed { background: #0c3d25; color: #23d38a; }
        .status-pill.failed { background: #441511; color: #e74c3c; }

        .col-id { color: #8b949e; font-family: monospace; display: flex; align-items: center; gap: 8px; }
        .empty-row { text-align: center; padding: 40px !important; color: #484f58; }
        .job-actions { display: flex; gap: 6px; }
        .btn-small { background: transparent; border: 1px solid var(--border-color); color: #8b949e; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; }
        .btn-small:hover { color: white; border-color: #58a6ff; }
        .btn-small.logs:hover { background: rgba(88, 166, 255, 0.1); }
        .btn-small.retry:hover { background: rgba(46, 204, 113, 0.1); border-color: #2ecc71; color: #2ecc71; }

        /* Log Modal Specifics */
        .log-modal { max-width: 800px; max-height: 85vh; overflow-y: auto; }
        .log-section { margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #30363d; }
        .log-section:last-child { border-bottom: none; }
        .log-section h3 { font-size: 14px; color: #58a6ff; margin-bottom: 12px; }
        .log-events { background: #0d1117; padding: 12px; border-radius: 8px; }
        .log-line { font-family: monospace; font-size: 12px; color: #8b949e; margin: 4px 0; }
        .error-content { background: #441511; color: #ff7b72; padding: 12px; border-radius: 8px; font-size: 12px; overflow-x: auto; white-space: pre-wrap; }
        .meta-content { background: #161b22; padding: 12px; border-radius: 8px; font-size: 11px; color: #c9d1d9; }
        .summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .sum-item { display: flex; flex-direction: column; }
        .sum-item label { font-size: 11px; color: #484f58; margin-bottom: 4px; }
        .sum-item span { font-size: 16px; font-weight: bold; color: #23d38a; }

        /* Dashboard Market Extensions */
        .market-highlight { border-color: rgba(230, 126, 34, 0.4) !important; background: linear-gradient(145deg, rgba(230, 126, 34, 0.05), rgba(22, 27, 34, 1)) !important; }
        .trend-up { color: #2ecc71 !important; font-weight: bold; }
        .dashboard-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-top: 10px; }
        .trends-card { min-height: 400px; display: flex; flex-direction: column; }
        .chart-placeholder { flex: 1; display: flex; align-items: flex-end; padding: 20px 0; border-top: 1px solid #30363d; margin-top: 20px; }
        .bars-container { display: flex; justify-content: space-around; align-items: flex-end; width: 100%; height: 200px; gap: 12px; }
        .bar-wrapper { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 10px; }
        .chart-bar { width: 100%; background: linear-gradient(to top, var(--accent-cyan), #2ecc71); border-radius: 4px 4px 0 0; position: relative; display: flex; align-items: flex-start; justify-content: center; transition: height 0.3s ease; min-height: 20px; }
        .bar-value { position: absolute; top: -20px; font-size: 10px; color: #8b949e; }
        .bar-label { font-size: 12px; color: #484f58; font-weight: bold; }

        /* Collector Refinements */
        .collector-view { display: flex; flex-direction: column; gap: 20px; height: 100%; }
        .browser-active-panel { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(88, 166, 255, 0.05); border: 1px dashed var(--accent-cyan); border-radius: 20px; text-align: center; gap: 30px; }
        .browser-info h2 { color: var(--accent-cyan); margin: 10px 0; }
        .browser-actions { display: flex; gap: 16px; }
        .btn-collect { background: var(--accent-green); color: #0d1117; border: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; cursor: pointer; display: flex; align-items: center; gap: 10px; font-size: 16px; }
        .btn-close-browser { background: transparent; border: 1px solid #ff7b72; color: #ff7b72; padding: 12px 24px; border-radius: 8px; cursor: pointer; }
        .pulse-icon { color: var(--accent-cyan); filter: drop-shadow(0 0 10px var(--accent-cyan)); animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 0.6; transform: scale(1); } 50% { opacity: 1; transform: scale(1.1); } 100% { opacity: 0.6; transform: scale(1); } }

        /* Card refinements */
        .title-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px; }
        .card-actions { display: flex; gap: 4px; opacity: 0; transition: opacity 0.2s; }
        .source-card:hover .card-actions { opacity: 1; }
        .icon-btn { background: transparent; border: none; color: #8b949e; cursor: pointer; padding: 4px; border-radius: 4px; }
        .icon-btn:hover { background: rgba(255,255,255,0.05); color: white; }
        .icon-btn.delete:hover { color: #e74c3c; background: rgba(231, 76, 60, 0.1); }
        
        .source-icon { position: relative; }
        .local-indicator { position: absolute; bottom: -2px; right: -2px; background: #0a0c10; border-radius: 50%; padding: 2px; }

        .admin-table { width: 100%; border-collapse: collapse; }
        .admin-table th { text-align: left; padding: 12px; border-bottom: 1px solid var(--border-color); color: #8b949e; }
        .admin-table td { padding: 16px 12px; border-bottom: 1px solid #21262d; }
        .badge { background: rgba(35, 211, 138, 0.1); color: var(--accent-green); padding: 2px 8px; border-radius: 4px; font-size: 11px; }

        .glass-morphism { backdrop-filter: blur(10px); }
        .animate-fade-in { animation: fadeIn 0.4s ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
}

export default App;
