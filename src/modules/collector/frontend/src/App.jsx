import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  isValidUrl,
  ensureProtocol,
  toGoogleSearch,
  formatLoadTime
} from './utils/helpers';

// Components
import Sidebar from './components/Sidebar';
import UrlBar from './components/UrlBar';
import StatsBar from './components/StatsBar';
import BrowserFrame from './components/BrowserFrame';
import DuplicateOverlay from './components/DuplicateOverlay';
import Toast from './components/Toast';
import { Monitor, Zap, Power, Download, RefreshCw } from 'lucide-react';

const API_BASE = '/api';

function App() {
  const [url, setUrl] = useState('');
  const [currentUrl, setCurrentUrl] = useState('');
  const [activeHtml, setActiveHtml] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedItems, setSavedItems] = useState([]);
  const [message, setMessage] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [tagInput, setTagInput] = useState('');
  const [tags, setTags] = useState([]);
  const [userId, setUserId] = useState(() => localStorage.getItem('collector_user_id') || '');
  const [pageType, setPageType] = useState(null);
  const [loadTime, setLoadTime] = useState(null);
  const [duplicateInfo, setDuplicateInfo] = useState(null);
  const [showDuplicateOverlay, setShowDuplicateOverlay] = useState(false);
  const [stats, setStats] = useState(null);
  const [searchFilter, setSearchFilter] = useState('');
  const [checking, setChecking] = useState(false);
  const [iframeSrc, setIframeSrc] = useState('');

  // Interactive Mode States
  const [browserActive, setBrowserActive] = useState(false);
  const [browserUrl, setBrowserUrl] = useState('');
  const [browserTitle, setBrowserTitle] = useState('');

  const iframeRef = useRef(null);

  // Persist user ID
  useEffect(() => {
    localStorage.setItem('collector_user_id', userId);
  }, [userId]);

  useEffect(() => {
    fetchSaved();
    fetchStats();
    checkBrowserStatus();

    // Poll status if active
    const timer = setInterval(() => {
      checkBrowserStatus();
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  const fetchSaved = async () => {
    try {
      const res = await axios.get(`${API_BASE}/saved`);
      setSavedItems(res.data);
    } catch (err) {
      console.error("Failed to fetch saved items", err);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API_BASE}/visit-stats`);
      setStats(res.data);
    } catch (err) {
      console.error("Failed to fetch stats", err);
    }
  };

  const checkBrowserStatus = async () => {
    try {
      const res = await axios.get(`${API_BASE}/browser/status`);
      setBrowserActive(res.data.active);
      if (res.data.active) {
        setBrowserUrl(res.data.url);
        setBrowserTitle(res.data.title);

        // Tự động kiểm tra trùng lặp cho URL đang mở trong trình duyệt
        if (res.data.url) {
          const checkRes = await axios.post(`${API_BASE}/check-url`, {
            url: res.data.url,
            user_id: userId || 'anonymous',
          });
          setDuplicateInfo(checkRes.data.duplicate ? checkRes.data : null);
        }
      }
    } catch (err) {
      setBrowserActive(false);
    }
  };

  const handleLaunchBrowser = async () => {
    setLoading(true);
    setMessage({ type: 'info', text: 'Đang khởi động trình duyệt độc lập...' });
    try {
      let target = url.trim() ? (isValidUrl(url.trim()) ? ensureProtocol(url.trim()) : toGoogleSearch(url.trim())) : "https://shopee.vn";
      await axios.post(`${API_BASE}/browser/launch`, { url: target });
      setBrowserActive(true);
      setMessage({ type: 'success', text: 'Trình duyệt đã mở! Bạn có thể thao tác trực tiếp trên đó.' });
    } catch (err) {
      setMessage({ type: 'error', text: 'Không thể mở trình duyệt. Hãy chắc chắn bạn đang chạy local (ngoài Docker).' });
    } finally {
      setLoading(false);
    }
  };

  const handleCollect = async () => {
    setSaving(true);
    setMessage({ type: 'info', text: 'Đang "hút" dữ liệu từ trình duyệt đang mở...' });
    try {
      const res = await axios.post(`${API_BASE}/browser/collect`);
      if (res.data.success) {
        setMessage({ type: 'success', text: `Đã thu thập dữ liệu từ: ${res.data.url}` });
        fetchSaved();
        fetchStats();
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Lỗi khi thu thập dữ liệu.' });
    } finally {
      setSaving(false);
    }
  };

  const handleStopBrowser = async () => {
    try {
      await axios.post(`${API_BASE}/browser/close`);
      setBrowserActive(false);
      setMessage({ type: 'info', text: 'Đã đóng trình duyệt độc lập.' });
    } catch { }
  };

  const checkUrl = async (targetUrl) => {
    setChecking(true);
    try {
      const res = await axios.post(`${API_BASE}/check-url`, {
        url: targetUrl,
        user_id: userId || 'anonymous',
      });
      return res.data;
    } catch (err) {
      console.error("Check URL failed", err);
      return { duplicate: false };
    } finally {
      setChecking(false);
    }
  };

  const logVisit = async (targetUrl, loadTimeMs, classification) => {
    try {
      await axios.post(`${API_BASE}/log-visit`, {
        url: targetUrl,
        user_id: userId || 'anonymous',
        load_time_ms: loadTimeMs,
        page_type: classification,
      });
      fetchStats();
    } catch (err) {
      console.error("Log visit failed", err);
    }
  };

  const classifyUrl = async (targetUrl) => {
    try {
      const res = await axios.get(`${API_BASE}/classify-url?url=${encodeURIComponent(targetUrl)}`);
      return res.data.type;
    } catch {
      return 'other';
    }
  };

  const handleNavigate = async (e) => {
    if (e) e.preventDefault();
    if (!url.trim()) return;

    if (browserActive) {
      // In interactive mode, just tell the browser to go there
      let target = isValidUrl(url.trim()) ? ensureProtocol(url.trim()) : toGoogleSearch(url.trim());
      await axios.post(`${API_BASE}/browser/navigate`, { url: target });
      return;
    }

    let targetUrl;
    if (isValidUrl(url.trim())) {
      targetUrl = ensureProtocol(url.trim());
    } else {
      targetUrl = toGoogleSearch(url.trim());
    }

    const classification = await classifyUrl(targetUrl);
    setPageType(classification);

    const checkResult = await checkUrl(targetUrl);

    if (checkResult.duplicate) {
      setDuplicateInfo(checkResult);
      setShowDuplicateOverlay(true);
      return;
    }

    await loadPage(targetUrl, classification);
  };

  const loadPage = async (targetUrl, classification) => {
    setLoading(true);
    setLoadTime(null);
    const startTime = performance.now();

    try {
      const response = await axios.get(`${API_BASE}/proxy?url=${encodeURIComponent(targetUrl)}`);

      if (!response || !response.data) {
        throw new Error("Không nhận được dữ liệu từ server.");
      }

      const elapsed = Math.round(performance.now() - startTime);
      setLoadTime(elapsed);
      const htmlContent = response.data.html || '';
      setActiveHtml(htmlContent);
      setCurrentUrl(targetUrl);

      setIframeSrc(`/api/view-proxy?url=${encodeURIComponent(targetUrl)}`);
      await logVisit(targetUrl, elapsed, classification || pageType);

      setMessage({ type: 'success', text: `Tải thành công (${formatLoadTime(elapsed)})` });
    } catch (err) {
      console.error("Load page error:", err);
      const errorMsg = err.response?.data?.detail || err.message || 'Không thể tải trang này.';
      setMessage({ type: 'error', text: errorMsg });
    } finally {
      setLoading(false);
    }
  };

  const handleForceLoad = async () => {
    setShowDuplicateOverlay(false);
    const targetUrl = duplicateInfo?.url || currentUrl;
    const classification = await classifyUrl(targetUrl);
    await loadPage(targetUrl, classification);
    setDuplicateInfo(null);
  };

  const handleCancelDuplicate = () => {
    setShowDuplicateOverlay(false);
    setDuplicateInfo(null);
  };

  const handleSave = async () => {
    if (!currentUrl) return;
    setSaving(true);
    setMessage({ type: 'info', text: 'Đang lưu MHTML (bao gồm ảnh, CSS)... Vui lòng đợi.' });
    try {
      const res = await axios.post(`${API_BASE}/save-mhtml`, {
        url: currentUrl,
        tags: tags,
      }, { timeout: 120000 });
      if (res.data.success) {
        const sizeKB = (res.data.size / 1024).toFixed(1);
        setMessage({ type: 'success', text: `Đã lưu MHTML thành công! (${sizeKB} KB)` });
        fetchSaved();
        setTags([]);
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'Lỗi khi lưu MHTML.';
      setMessage({ type: 'error', text: detail });
    } finally {
      setSaving(false);
    }
  };

  const addTag = (e) => {
    if (e.key === 'Enter' && tagInput.trim()) {
      e.preventDefault();
      if (!tags.includes(tagInput.trim())) {
        setTags([...tags, tagInput.trim()]);
      }
      setTagInput('');
    }
  };

  const removeTag = (t) => {
    setTags(tags.filter(tag => tag !== t));
  };

  const filteredItems = savedItems.filter(item => {
    if (!searchFilter) return true;
    const q = searchFilter.toLowerCase();
    return item.filename.toLowerCase().includes(q) || item.url.toLowerCase().includes(q);
  });

  return (
    <div className="app-container">
      <Sidebar
        sidebarOpen={sidebarOpen}
        stats={stats}
        searchFilter={searchFilter}
        setSearchFilter={setSearchFilter}
        filteredItems={filteredItems}
        setUrl={setUrl}
        userId={userId}
        setUserId={setUserId}
      />

      <div className="main-content">
        {loading && <div className="loading-indicator" />}

        <UrlBar
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
          checking={checking}
          url={url}
          setUrl={setUrl}
          currentUrl={currentUrl}
          pageType={pageType}
          loading={loading}
          handleNavigate={handleNavigate}
          loadTime={loadTime}
          browserActive={browserActive}
          handleLaunchBrowser={handleLaunchBrowser}
        />

        {!browserActive && (
          <StatsBar
            currentUrl={currentUrl}
            pageType={pageType}
            loadTime={loadTime}
            tagInput={tagInput}
            setTagInput={setTagInput}
            addTag={addTag}
            tags={tags}
            removeTag={removeTag}
            handleSave={handleSave}
            saving={saving}
          />
        )}

        <main className="browser-area">
          {browserActive ? (
            <div className="interactive-panel glass-morphism">
              <div className="panel-header">
                <div className="pulse-indicator"></div>
                <div style={{ flex: 1 }}>
                  <h3 className="font-outfit" style={{ margin: 0, fontSize: 16 }}>Đang khớp lệnh với trình duyệt thật</h3>
                  <div className="browser-url-display">{browserUrl}</div>
                </div>
                <button className="btn-icon" onClick={checkBrowserStatus} title="Làm mới trạng thái">
                  <RefreshCw size={16} />
                </button>
                <button className="btn-stop" onClick={handleStopBrowser}>
                  <Power size={14} /> Dừng
                </button>
              </div>

              <div className="panel-body">
                <div className="status-card">
                  <div className="status-label">Trang đang mở:</div>
                  <div className="status-value">{browserTitle || "Đang tải..."}</div>
                  {duplicateInfo && (
                    <div className={`duplicate-warning animate-fade-in ${duplicateInfo.is_saved ? 'saved-status' : ''}`}>
                      <Monitor size={16} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 'bold' }}>{duplicateInfo.message}</div>
                        <div style={{ fontSize: '10px', opacity: 0.8 }}>
                          Thu thập bởi: {duplicateInfo.existing_visit.user_id} - {new Date(duplicateInfo.existing_visit.visited_at).toLocaleString()}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                <div className="action-grid">
                  <button
                    className={`btn-collect ${duplicateInfo ? 'btn-duplicate' : ''}`}
                    onClick={handleCollect}
                    disabled={saving}
                  >
                    {saving ? <RefreshCw className="animate-spin" size={20} /> : <Download size={20} />}
                    <span>{duplicateInfo ? 'Thu thập lại trang này' : 'Hút dữ liệu trang này (Lưu MHTML)'}</span>
                  </button>
                </div>

                <div className="panel-hint">
                  <Zap size={14} style={{ color: 'var(--accent-amber)' }} />
                  Mẹo: Bạn có thể đăng nhập, lướt web trên cửa sổ Chrome vừa hiện ra. Nhấn nút <b>"Hút dữ liệu"</b> mỗi khi muốn lưu một sản phẩm.
                </div>
              </div>
            </div>
          ) : (
            <BrowserFrame
              activeHtml={activeHtml}
              iframeRef={iframeRef}
              iframeSrc={iframeSrc}
              setUrl={setUrl}
            />
          )}

          <DuplicateOverlay
            showDuplicateOverlay={showDuplicateOverlay}
            duplicateInfo={duplicateInfo}
            handleCancelDuplicate={handleCancelDuplicate}
            handleForceLoad={handleForceLoad}
          />

          <Toast message={message} />
        </main>
      </div>
    </div>
  );
}

export default App;
