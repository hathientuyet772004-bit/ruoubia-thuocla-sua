import React from 'react';
import { Globe, Zap, Search } from 'lucide-react';

const BrowserFrame = ({
    activeHtml,
    iframeRef,
    iframeSrc,
    setUrl
}) => {
    if (!activeHtml) {
        return (
            <div className="empty-state">
                <div className="icon-bg">
                    <Globe size={36} />
                </div>
                <h3 className="font-outfit">Trình duyệt thu thập</h3>
                <p>
                    Nhập URL sản phẩm hoặc từ khóa tìm kiếm để bắt đầu.
                    Hệ thống sẽ tự động kiểm tra trùng lặp và ghi nhận thông tin truy cập.
                </p>
                <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
                    <div className="glass-subtle" style={{ padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, cursor: 'pointer' }}
                        onClick={() => setUrl('shopee.vn')}>
                        <Zap size={14} style={{ color: 'var(--accent-amber)' }} />
                        shopee.vn
                    </div>
                    <div className="glass-subtle" style={{ padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, cursor: 'pointer' }}
                        onClick={() => setUrl('sữa ensure')}>
                        <Search size={14} style={{ color: 'var(--accent-cyan)' }} />
                        "sữa ensure"
                    </div>
                    <div className="glass-subtle" style={{ padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, cursor: 'pointer' }}
                        onClick={() => setUrl('tiki.vn')}>
                        <Zap size={14} style={{ color: 'var(--accent-emerald)' }} />
                        tiki.vn
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div style={{ width: '100%', height: '100%', padding: 0 }}>
            <iframe
                ref={iframeRef}
                src={iframeSrc || undefined}
                style={{ width: '100%', height: '100%', border: 'none', background: 'white' }}
                title="Browser Preview"
            />
        </div>
    );
};

export default BrowserFrame;
