import React from 'react';
import { motion } from 'framer-motion';
import { Globe, Clock, Tag, X, Save, Loader2, ExternalLink } from 'lucide-react';
import { getPageTypeBadge, formatLoadTime } from '../utils/helpers';

const StatsBar = ({
    currentUrl,
    pageType,
    loadTime,
    tagInput,
    setTagInput,
    addTag,
    tags,
    removeTag,
    handleSave,
    saving
}) => {
    if (!currentUrl) return null;

    return (
        <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="stats-bar"
        >
            <div className="stat-item">
                <Globe size={12} />
                <span className="truncate" style={{ maxWidth: 400 }}>{currentUrl}</span>
            </div>
            <div className="divider" />
            {pageType && (
                <>
                    <div className="stat-item">
                        {getPageTypeBadge(pageType)}
                    </div>
                    <div className="divider" />
                </>
            )}
            {loadTime !== null && (
                <div className="stat-item">
                    <Clock size={12} />
                    <span className="stat-value">{formatLoadTime(loadTime)}</span>
                </div>
            )}
            <div style={{ flex: 1 }} />

            {/* Tag input + Save button in stats bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ position: 'relative' }}>
                    <input
                        type="text"
                        style={{ width: 100, padding: '4px 24px 4px 8px', fontSize: 11, borderRadius: 8, height: 28 }}
                        placeholder="Tag..."
                        value={tagInput}
                        onChange={(e) => setTagInput(e.target.value)}
                        onKeyDown={addTag}
                    />
                    <Tag size={10} style={{ position: 'absolute', right: 6, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', opacity: 0.5 }} />
                    {tags.length > 0 && (
                        <div style={{ position: 'absolute', right: 0, top: '100%', paddingTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4, zIndex: 30 }}>
                            {tags.map(t => (
                                <span key={t} onClick={() => removeTag(t)}
                                    style={{ padding: '2px 8px', background: 'rgba(99,102,241,0.15)', color: '#818cf8', fontSize: 10, borderRadius: 20, border: '1px solid rgba(99,102,241,0.3)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                                    {t}<X size={8} />
                                </span>
                            ))}
                        </div>
                    )}
                </div>

                <button
                    className="btn-primary"
                    onClick={handleSave}
                    disabled={saving}
                    style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 12px', fontSize: 12, whiteSpace: 'nowrap' }}
                >
                    {saving ? <Loader2 size={13} className="animate-pulse" /> : <Save size={13} />}
                    Lưu MHTML
                </button>

                <div className="stat-item" style={{ cursor: 'pointer', marginLeft: 4 }} onClick={() => { if (currentUrl) window.open(currentUrl, '_blank'); }}>
                    <ExternalLink size={12} />
                    Mở trong tab mới
                </div>
            </div>
        </motion.div>
    );
};

export default StatsBar;
