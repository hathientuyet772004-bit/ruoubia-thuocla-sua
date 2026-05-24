import { useEffect, useState } from 'react';
import { Activity, Boxes, FileSearch, Files, Globe, LayoutDashboard, MapPin, PackageSearch } from 'lucide-react';

export const navGroups = [
  { label: 'Vận hành', items: [['/dashboard', 'Tổng quan', LayoutDashboard], ['/sources', 'Nguồn dữ liệu', Globe], ['/runs', 'Lượt chạy', Activity], ['/products', 'Sản phẩm & giá bán', PackageSearch], ['/stores', 'Cửa hàng', MapPin], ['/dedup', 'Rà soát trùng lặp', Boxes]] },
  { label: 'Thiết lập', items: [['/extraction/rules', 'Quy tắc trích xuất', FileSearch], ['/tasks/latest/raw', 'Xem trang thô', Files]] }
];

function routeFromWindow() {
  return window.location.pathname === '/' ? '/dashboard' : window.location.pathname;
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
  if (!path.startsWith(prefix)) return null;
  return decodeURIComponent(path.slice(prefix.length).split('/')[0] || '');
}

export function routeId(value) {
  return encodeURIComponent(String(value)).replace(/\./g, '%2E');
}
