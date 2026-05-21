import React from 'react';
import { motion } from 'framer-motion';
import { Layout, Loader2, Search, ArrowRight, Timer, Monitor } from 'lucide-react';
import { getPageTypeBadge, formatLoadTime, getLoadTimeClass } from '../utils/helpers';

const UrlBar = ({
    sidebarOpen,
    setSidebarOpen,
    checking,
    url,
    setUrl,
    currentUrl,
    pageType,
    loading,
    handleNavigate,
    loadTime,
    browserActive,
    handleLaunchBrowser
}) => {
    return (
        <header className="main-header">
            <button
                className={`btn-icon ${sidebarOpen ? 'active' : ''}`}
                onClick={() => setSidebarOpen(!sidebarOpen)}
                title="Toggle sidebar"
            >
                <Layout size={18} />
            </button>

            <form onSubmit={handleNavigate} style={{ flex: 1, display: 'flex' }}>
                <div className="url-bar">
                    <div className="url-icon">
                        {checking ? (
                            <Loader2 size={16} className="animate-pulse" style={{ color: 'var(--accent-primary)' }} />
                        ) : (
                            <Search size={16} />
                        )}
                    </div>
                    <input
                        type="text"
                        placeholder="Nhập URL hoặc từ khóa... (Sử dụng trình duyệt độc lập để tránh bị chặn)"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                    />

                    {/* Page type badge inline */}
                    {pageType && currentUrl && !browserActive && (
                        <div style={{ display: 'flex', alignItems: 'center', paddingRight: 8 }}>
                            {getPageTypeBadge(pageType)}
                        </div>
                    )}

                    <button type="submit" className="url-submit" disabled={loading || !url.trim()}>
                        {loading ? (
                            <Loader2 size={16} className="animate-pulse" />
                        ) : (
                            <>
                                <ArrowRight size={16} />
                                {browserActive ? 'Chuyển trang' : 'Truy cập'}
                            </>
                        )}
                    </button>
                </div>
            </form>

            {/* Action buttons */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {!browserActive && (
                    <button className="btn-primary" onClick={handleLaunchBrowser} style={{ padding: '8px 16px', gap: 8 }}>
                        <Monitor size={16} />
                        Mở trình duyệt độc lập
                    </button>
                )}

                {/* Load time indicator */}
                {loadTime !== null && !browserActive && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className={`load-time ${getLoadTimeClass(loadTime)}`}
                    >
                        <Timer size={12} />
                        {formatLoadTime(loadTime)}
                    </motion.div>
                )}
            </div>
        </header>
    );
};

export default UrlBar;
