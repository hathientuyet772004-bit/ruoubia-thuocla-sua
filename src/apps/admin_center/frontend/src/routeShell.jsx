import { useEffect, useState } from 'react';
import { Activity, Boxes, FileSearch, Files, Globe, LayoutDashboard, MapPin, PackageSearch, Sparkles } from 'lucide-react';

export const navGroups = [
  { label: 'Vận hành', items: [['/dashboard', 'Tổng quan', LayoutDashboard], ['/sources', 'Nguồn dữ liệu', Globe], ['/runs', 'Lượt chạy', Activity], ['/products', 'Sản phẩm & giá bán', PackageSearch], ['/stores', 'Cửa hàng', MapPin], ['/dedup', 'Rà soát trùng lặp', Boxes]] },
  { label: 'Thiết lập', items: [['/extraction/rules', 'Quy tắc trích xuất', FileSearch], ['/ai/review', 'AI duyệt tay', Sparkles], ['/tasks/latest/raw', 'Xem trang thô', Files]] }
];

function routeFromWindow() {
  const path = window.location.pathname === '/' ? '/dashboard' : window.location.pathname;
  return `${path}${window.location.search}`;
}

export function useRoute() {
  const [path, setPath] = useState(routeFromWindow);
  useEffect(() => {
    const onPopState = () => setPath(routeFromWindow());
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);
  const navigate = (nextPath) => {
    if (nextPath === path) return;
    window.history.pushState({}, '', nextPath);
    setPath(nextPath);
  };
  return [path, navigate];
}

export function segment(path, prefix) {
  const cleanPath = path.split('?')[0];
  if (!cleanPath.startsWith(prefix)) return null;
  return decodeURIComponent(cleanPath.slice(prefix.length).split('/')[0] || '');
}

export function routeId(value) {
  return encodeURIComponent(String(value)).replace(/\./g, '%2E');
}
