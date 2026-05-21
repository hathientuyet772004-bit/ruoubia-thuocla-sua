import React from 'react';
import { Package, Search, ListFilter, Globe } from 'lucide-react';

export function isValidUrl(str) {
    if (/^https?:\/\//i.test(str)) return true;
    if (/^[\w.-]+\.(com|vn|net|org|io|co|shop|store|online)(\/.*)?$/i.test(str)) return true;
    return false;
}

export function ensureProtocol(url) {
    if (!/^https?:\/\//i.test(url)) {
        return 'https://' + url;
    }
    return url;
}

export function toGoogleSearch(query) {
    return `https://www.google.com/search?q=${encodeURIComponent(query)}`;
}

export function formatLoadTime(ms) {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
}

export function getLoadTimeClass(ms) {
    if (ms < 2000) return 'fast';
    if (ms < 5000) return 'medium';
    return 'slow';
}

export function getPageTypeIcon(type) {
    switch (type) {
        case 'product': return <Package size={12} />;
        case 'search': return <Search size={12} />;
        case 'category': return <ListFilter size={12} />;
        default: return <Globe size={12} />;
    }
}

export function getPageTypeBadge(type) {
    const labels = { product: 'Sản phẩm', search: 'Tìm kiếm', category: 'Danh mục', other: 'Khác' };
    return (
        <span className={`badge badge-${type}`}>
            {getPageTypeIcon(type)}
            {labels[type] || type}
        </span>
    );
}
