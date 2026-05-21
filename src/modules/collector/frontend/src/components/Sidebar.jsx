import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Globe, BarChart3, History, User } from 'lucide-react';
import { formatLoadTime, getPageTypeBadge } from '../utils/helpers';

const Sidebar = ({
    sidebarOpen,
    stats,
    searchFilter,
    setSearchFilter,
    filteredItems,
    setUrl,
    userId,
    setUserId
}) => {
    return (
        <AnimatePresence>
            {sidebarOpen && (
                <motion.div
                    initial={{ width: 0, opacity: 0 }}
                    animate={{ width: 310, opacity: 1 }}
                    exit={{ width: 0, opacity: 0 }}
                    transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
                    className="sidebar"
                    style={{ flexShrink: 0 }}
                >
                    <div className="sidebar-header">
                        <div className="sidebar-title">
                            <div className="logo">
                                <Globe size={22} color="white" />
                            </div>
                            <div>
                                <h1>Browser</h1>
                                <div className="subtitle">Trình duyệt thu thập dữ liệu</div>
                            </div>
                        </div>

                        <div className="sidebar-search">
                            <Search size={14} className="icon" />
                            <input
                                type="text"
                                placeholder="Tìm trang đã lưu..."
                                value={searchFilter}
                                onChange={(e) => setSearchFilter(e.target.value)}
                            />
                        </div>
                    </div>

                    {/* Stats summary */}
                    {stats && (
                        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-color)' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, fontSize: 12, color: 'var(--text-dim)' }}>
                                <BarChart3 size={14} />
                                <span style={{ fontWeight: 600 }}>Tháng {stats.month}</span>
                            </div>
                            <div style={{ display: 'flex', gap: 8 }}>
                                <div className="glass-subtle" style={{ flex: 1, padding: '10px 12px', textAlign: 'center' }}>
                                    <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'Outfit', color: 'var(--accent-primary)' }}>
                                        {stats.total_urls}
                                    </div>
                                    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>URL</div>
                                </div>
                                <div className="glass-subtle" style={{ flex: 1, padding: '10px 12px', textAlign: 'center' }}>
                                    <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'Outfit', color: 'var(--accent-emerald)' }}>
                                        {stats.by_page_type?.product || 0}
                                    </div>
                                    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>Sản phẩm</div>
                                </div>
                                <div className="glass-subtle" style={{ flex: 1, padding: '10px 12px', textAlign: 'center' }}>
                                    <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'Outfit', color: 'var(--accent-cyan)' }}>
                                        {stats.avg_load_time_ms ? formatLoadTime(stats.avg_load_time_ms) : '—'}
                                    </div>
                                    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>Avg Load</div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* History items */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '12px 16px 4px', fontSize: 12, fontWeight: 600, color: 'var(--text-dim)' }}>
                        <History size={14} />
                        Trang đã lưu ({filteredItems.length})
                    </div>

                    <div className="sidebar-content">
                        {filteredItems.length === 0 ? (
                            <div style={{ textAlign: 'center', padding: '40px 0', opacity: 0.3, fontSize: 13, fontStyle: 'italic' }}>
                                {searchFilter ? 'Không tìm thấy kết quả' : 'Chưa có trang nào được lưu'}
                            </div>
                        ) : (
                            filteredItems.map((item, idx) => (
                                <motion.div
                                    key={item.filename}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: idx * 0.03 }}
                                    className="sidebar-item"
                                    onClick={() => {
                                        if (item.url !== 'Unknown') {
                                            setUrl(item.url);
                                        }
                                    }}
                                >
                                    <div className="item-name">{item.display_name || item.filename.split('_202')[0]}</div>
                                    <div className="item-url">{item.url}</div>
                                    <div className="item-meta">
                                        <span>{item.date}</span>
                                        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                            {item.page_type && getPageTypeBadge(item.page_type)}
                                            <span>{(item.size / 1024).toFixed(1)} KB</span>
                                        </span>
                                    </div>
                                </motion.div>
                            ))
                        )}
                    </div>

                    {/* User ID */}
                    <div className="user-settings">
                        <div className="avatar">
                            {userId ? userId.charAt(0).toUpperCase() : <User size={16} />}
                        </div>
                        <input
                            type="text"
                            placeholder="Nhập User ID..."
                            value={userId}
                            onChange={(e) => setUserId(e.target.value)}
                            style={{ flex: 1 }}
                        />
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default Sidebar;
