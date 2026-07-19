import { useEffect, useState } from 'react';
import { Activity, BookOpen, CalendarClock, Database, FileSearch, Files, Globe, LayoutDashboard, PackageSearch, ShieldAlert } from 'lucide-react';

export const navGroups = [
  { label: 'Tổng quan', items: [['/dashboard', 'Tổng quan', LayoutDashboard]] },
  { label: 'Thu thập dữ liệu', items: [['/sources', 'Nguồn dữ liệu', Globe], ['/collection', 'Pipeline', CalendarClock], ['/runs', 'Lượt chạy', Activity], ['/products', 'Sản phẩm & giá bán', PackageSearch]] },
  { label: 'Quản trị dữ liệu', items: [['/extraction/rules', 'Quy tắc trích xuất', FileSearch], ['/extraction/candidates', 'Duyệt Rule AI', ShieldAlert], ['/gen-data', 'Tạo dữ liệu', Database]] },
  { label: 'Hệ thống', items: [['/guide', 'Hướng dẫn sử dụng', BookOpen], ['/tasks/latest/raw', 'Xem trang thô', Files]] }
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
