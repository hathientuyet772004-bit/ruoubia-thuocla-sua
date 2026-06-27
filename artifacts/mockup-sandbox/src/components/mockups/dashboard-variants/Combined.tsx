import { useState } from "react";
import {
  Activity, AlertCircle, AlertTriangle, BarChart3, Bell,
  Bot, CheckCircle2, ChevronRight, Clock, Cpu, Database,
  Filter, Globe, Grid3X3, LayoutDashboard, Layers,
  Play, RefreshCw, Search, Settings, Shield, Shuffle,
  Terminal, TrendingDown, TrendingUp, Zap, X, Eye,
  ChevronDown, ArrowRight, FileSearch, Copy
} from "lucide-react";

const SOURCES = [
  { name: "thegioididong.com", status: "online", count: "12.5k", health: 98 },
  { name: "fptshop.com.vn", status: "online", count: "8.3k", health: 95 },
  { name: "cellphones.com.vn", status: "warning", count: "5.4k", health: 71 },
  { name: "hoanghamobile.com", status: "online", count: "6.2k", health: 99 },
  { name: "dienmayxanh.com", status: "offline", count: "15.8k", health: 0 },
  { name: "nguyenkim.com", status: "warning", count: "4.1k", health: 62 },
  { name: "mediamart.vn", status: "online", count: "3.9k", health: 88 },
  { name: "phongvu.vn", status: "online", count: "9.2k", health: 94 },
  { name: "gearvn.com", status: "online", count: "2.1k", health: 91 },
  { name: "hacom.vn", status: "online", count: "3.4k", health: 87 },
];

const JOBS = [
  { id: "JOB-9842", source: "thegioididong.com", type: "Full Crawl", status: "done", count: 12500, time: "45m 12s", ago: "10p trước" },
  { id: "JOB-9841", source: "fptshop.com.vn", type: "Delta Update", status: "running", count: 3420, time: "12m 05s", ago: "Đang chạy..." },
  { id: "JOB-9840", source: "cellphones.com.vn", type: "Price Sync", status: "warn", count: 5400, time: "08m 30s", ago: "25p trước" },
  { id: "JOB-9839", source: "dienmayxanh.com", type: "Full Crawl", status: "error", count: 0, time: "02m 14s", ago: "1 giờ trước" },
  { id: "JOB-9838", source: "hoanghamobile.com", type: "Delta Update", status: "done", count: 1250, time: "15m 22s", ago: "2 giờ trước" },
  { id: "JOB-9837", source: "phongvu.vn", type: "Price Sync", status: "done", count: 9200, time: "05m 45s", ago: "3 giờ trước" },
  { id: "JOB-9836", source: "nguyenkim.com", type: "Full Crawl", status: "warn", count: 4050, time: "52m 10s", ago: "4 giờ trước" },
  { id: "JOB-9835", source: "gearvn.com", type: "Price Sync", status: "error", count: 0, time: "01m 05s", ago: "5 giờ trước" },
  { id: "JOB-9834", source: "mediamart.vn", type: "Delta Update", status: "done", count: 840, time: "11m 30s", ago: "6 giờ trước" },
  { id: "JOB-9833", source: "hacom.vn", type: "Full Crawl", status: "done", count: 3400, time: "28m 15s", ago: "7 giờ trước" },
];

const AI_ITEMS = [
  { id: "AI-221", source: "cellphones.com.vn", field: "Giá", confidence: 42, issue: "Giá bất thường +340%" },
  { id: "AI-220", source: "nguyenkim.com", field: "Tên SP", confidence: 58, issue: "Tên sản phẩm bị cắt" },
  { id: "AI-219", source: "dienmayxanh.com", field: "Category", confidence: 33, issue: "Danh mục không khớp" },
  { id: "AI-218", source: "hoanghamobile.com", field: "Ảnh", confidence: 65, issue: "URL ảnh 404" },
];

const PIPELINE_STAGES = [
  { id: "crawl", label: "Thu thập", active: true, count: 8, icon: Globe },
  { id: "extract", label: "Trích xuất", active: true, count: 3, icon: FileSearch },
  { id: "ai", label: "AI Review", active: false, count: 89, icon: Bot },
  { id: "dedup", label: "Dedup", active: false, count: 24, icon: Copy },
  { id: "store", label: "Lưu trữ", active: true, count: 0, icon: Database },
];

const NAV_GROUPS = [
  {
    label: "Tổng Quan", items: [
      { icon: LayoutDashboard, label: "Dashboard", badge: null, active: true },
      { icon: Activity, label: "Hoạt động", badge: 12, active: false },
    ]
  },
  {
    label: "Thu Thập", items: [
      { icon: Globe, label: "Nguồn dữ liệu", badge: "10", active: false },
      { icon: Grid3X3, label: "Pipeline", badge: null, active: false },
      { icon: Terminal, label: "Lượt chạy", badge: "2 lỗi", badgeRed: true, active: false },
      { icon: Layers, label: "Sản phẩm & giá", badge: null, active: false },
    ]
  },
  {
    label: "Quản Trị Dữ Liệu", items: [
      { icon: FileSearch, label: "Quy tắc trích xuất", badge: null, active: false },
      { icon: Shield, label: "Duyệt Rule AI", badge: null, active: false },
      { icon: Bot, label: "AI duyệt", badge: 89, badgeYellow: true, active: false },
      { icon: Copy, label: "Rà soát trùng lặp", badge: 24, active: false },
      { icon: Database, label: "Tạo dữ liệu", badge: null, active: false },
    ]
  },
  {
    label: "Hệ Thống", items: [
      { icon: Settings, label: "Cài đặt", badge: null, active: false },
      { icon: BarChart3, label: "Xem trang thô", badge: null, active: false },
    ]
  },
];

type Tab = "jobs" | "ai" | "dedup";

function sparkline(vals: number[], color: string) {
  const max = Math.max(...vals);
  const h = 36;
  const w = 80;
  const pts = vals.map((v, i) => `${(i / (vals.length - 1)) * w},${h - (v / max) * h}`).join(" ");
  return (
    <svg width={w} height={h} className="opacity-80">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

const rand = (min: number, max: number) => Math.floor(min + Math.random() * (max - min));
const throughputData = Array.from({ length: 24 }, (_, i) => rand(1200 + i * 40, 3800 + i * 60));

export function Combined() {
  const [activeTab, setActiveTab] = useState<Tab>("jobs");
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQ, setSearchQ] = useState("");
  const [sidebarOpen] = useState(true);
  const [selectedSource, setSelectedSource] = useState<string | null>(null);

  const filteredJobs = JOBS.filter(j => {
    const matchStatus = statusFilter === "all" || j.status === statusFilter;
    const matchSearch = j.id.toLowerCase().includes(searchQ.toLowerCase()) ||
      j.source.toLowerCase().includes(searchQ.toLowerCase());
    const matchSource = !selectedSource || j.source === selectedSource;
    return matchStatus && matchSearch && matchSource;
  });

  const statusDot = (s: string) => {
    if (s === "online") return "bg-emerald-500";
    if (s === "warning") return "bg-amber-400";
    return "bg-red-500";
  };

  const statusBadge = (s: string) => {
    if (s === "done") return { cls: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30", icon: <CheckCircle2 size={10} />, label: "Hoàn thành" };
    if (s === "running") return { cls: "bg-blue-500/15 text-blue-400 border-blue-500/30", icon: <RefreshCw size={10} className="animate-spin" />, label: "Đang chạy" };
    if (s === "warn") return { cls: "bg-amber-500/15 text-amber-400 border-amber-500/30", icon: <AlertTriangle size={10} />, label: "Cảnh báo" };
    return { cls: "bg-red-500/15 text-red-400 border-red-500/30", icon: <X size={10} />, label: "Thất bại" };
  };

  return (
    <div className="flex h-screen w-full overflow-hidden text-sm" style={{ background: "#060A12", color: "#E2E8F0", fontFamily: "Inter, sans-serif" }}>

      {/* ─── SIDEBAR ─── */}
      <aside className="w-[220px] shrink-0 flex flex-col border-r border-slate-800/60" style={{ background: "#0A101C" }}>
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-3.5 border-b border-slate-800/60">
          <div className="w-7 h-7 rounded bg-blue-600 flex items-center justify-center shrink-0">
            <Zap size={14} className="text-white" />
          </div>
          <div>
            <div className="text-xs font-semibold text-white leading-tight">Nền tảng thu thập</div>
            <div className="text-[10px] text-slate-500">Admin Center v2</div>
          </div>
        </div>

        {/* Pipeline Flow Status */}
        <div className="px-3 py-2 border-b border-slate-800/60">
          <div className="text-[10px] uppercase text-slate-600 font-medium mb-1.5 tracking-wider">Luồng Pipeline</div>
          <div className="flex items-center gap-1">
            {PIPELINE_STAGES.map((stage, i) => {
              const Icon = stage.icon;
              return (
                <div key={stage.id} className="flex items-center gap-1">
                  <div className={`flex flex-col items-center gap-0.5 ${stage.active ? "opacity-100" : "opacity-40"}`}>
                    <div className={`w-5 h-5 rounded flex items-center justify-center ${stage.active ? "bg-blue-600/20 border border-blue-500/40" : "bg-slate-800"}`}>
                      <Icon size={10} className={stage.active ? "text-blue-400" : "text-slate-500"} />
                    </div>
                    {stage.count > 0 && (
                      <span className="text-[8px] text-slate-500">{stage.count}</span>
                    )}
                  </div>
                  {i < PIPELINE_STAGES.length - 1 && (
                    <ArrowRight size={8} className="text-slate-700 shrink-0" />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Nav Groups */}
        <nav className="flex-1 overflow-y-auto py-2 px-2">
          {NAV_GROUPS.map(group => (
            <div key={group.label} className="mb-3">
              <div className="text-[10px] uppercase text-slate-600 font-medium tracking-wider px-2 mb-1">{group.label}</div>
              {group.items.map(item => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.label}
                    className={`w-full flex items-center gap-2.5 px-2 py-1.5 rounded text-left transition-colors text-xs
                      ${item.active
                        ? "bg-blue-600/15 text-blue-300 border border-blue-500/20"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"}`}
                  >
                    <Icon size={13} className="shrink-0" />
                    <span className="flex-1 truncate">{item.label}</span>
                    {item.badge !== null && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full leading-none
                        ${(item as any).badgeRed ? "bg-red-500/20 text-red-400" :
                          (item as any).badgeYellow ? "bg-amber-500/20 text-amber-400" :
                          "bg-slate-700 text-slate-400"}`}>
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Source List */}
        <div className="border-t border-slate-800/60 p-2">
          <div className="text-[10px] uppercase text-slate-600 font-medium tracking-wider px-1 mb-1.5">
            Nguồn ({SOURCES.filter(s => s.status === "online").length}/{SOURCES.length} online)
          </div>
          <div className="space-y-0.5 max-h-36 overflow-y-auto">
            {SOURCES.map(src => (
              <button
                key={src.name}
                onClick={() => setSelectedSource(selectedSource === src.name ? null : src.name)}
                className={`w-full flex items-center gap-2 px-1.5 py-1 rounded text-left transition-colors
                  ${selectedSource === src.name ? "bg-blue-600/15 text-blue-300" : "hover:bg-slate-800/40 text-slate-400"}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${statusDot(src.status)}`} />
                <span className="flex-1 text-[10px] truncate">{src.name}</span>
                <span className="text-[10px] text-slate-600">{src.count}</span>
              </button>
            ))}
          </div>
        </div>

        {/* User footer */}
        <div className="border-t border-slate-800/60 px-3 py-2 flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center text-[10px] font-bold text-white">A</div>
          <div className="flex-1 min-w-0">
            <div className="text-[10px] text-slate-300 font-medium truncate">Admin User</div>
            <div className="text-[9px] text-slate-600">Super Admin</div>
          </div>
          <Settings size={12} className="text-slate-600 hover:text-slate-300 cursor-pointer" />
        </div>
      </aside>

      {/* ─── MAIN AREA ─── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* Top bar */}
        <header className="shrink-0 flex items-center gap-3 px-4 py-2.5 border-b border-slate-800/60" style={{ background: "#0A101C" }}>
          <div className="flex items-center gap-1.5 text-slate-500 text-xs">
            <LayoutDashboard size={12} />
            <span>Dashboard</span>
          </div>
          <ChevronRight size={12} className="text-slate-700" />
          <span className="text-xs text-slate-300 font-medium">Tổng Quan</span>

          <div className="flex-1 mx-4">
            <div className="relative max-w-sm">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                value={searchQ}
                onChange={e => setSearchQ(e.target.value)}
                placeholder="Tìm Job ID, nguồn..."
                className="w-full bg-slate-800/60 border border-slate-700/50 rounded pl-7 pr-3 py-1.5 text-xs text-slate-300 placeholder-slate-600 focus:outline-none focus:border-blue-500/50"
              />
            </div>
          </div>

          {/* System health */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="flex items-center gap-1.5 text-xs">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-emerald-400 text-[11px]">Hệ thống OK</span>
            </div>
            <div className="flex items-center gap-1 text-slate-500 text-[11px]">
              <Cpu size={11} />
              <span>CPU 42%</span>
            </div>
            <div className="flex items-center gap-1 text-amber-400 text-[11px]">
              <AlertTriangle size={11} />
              <span>RAM 78%</span>
            </div>
            <button className="relative text-slate-500 hover:text-slate-300">
              <Bell size={14} />
              <span className="absolute -top-0.5 -right-0.5 w-3 h-3 bg-red-500 rounded-full text-[8px] text-white flex items-center justify-center">3</span>
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-hidden flex flex-col p-3 gap-3">

          {/* ─── KPI STRIP ─── */}
          <div className="shrink-0 grid grid-cols-6 gap-2">
            {[
              { label: "Tổng Sản Phẩm", value: "1,245,892", trend: "+1.2%", up: true, icon: Database, color: "#3B82F6" },
              { label: "Nguồn Quét", value: "142", trend: "+3 hôm nay", up: true, icon: Globe, color: "#06B6D4" },
              { label: "Job Đang Chạy", value: "8", trend: "3 Queue", up: null, icon: RefreshCw, color: "#8B5CF6" },
              { label: "Đang Chờ", value: "45", trend: "↓ 12 so hôm qua", up: false, icon: Clock, color: "#F59E0B" },
              { label: "Lỗi (24h)", value: "12", trend: "+2 mới", up: false, icon: AlertCircle, color: "#EF4444", alert: true },
              { label: "AI Review", value: "89", trend: "Cần xử lý", up: null, icon: Bot, color: "#A78BFA", alert: true },
            ].map(kpi => {
              const Icon = kpi.icon;
              return (
                <div key={kpi.label} className="border border-slate-800/60 rounded-lg p-2.5 flex flex-col gap-1.5 relative overflow-hidden"
                  style={{ background: "#0A101C" }}>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider leading-tight">{kpi.label}</span>
                    <div className="w-5 h-5 rounded flex items-center justify-center" style={{ background: kpi.color + "22" }}>
                      <Icon size={10} style={{ color: kpi.color }} />
                    </div>
                  </div>
                  <div className="text-xl font-semibold text-white leading-none">{kpi.value}</div>
                  <div className={`text-[10px] flex items-center gap-0.5 ${kpi.alert ? "text-red-400" : kpi.up === null ? "text-slate-500" : kpi.up ? "text-emerald-400" : "text-amber-400"}`}>
                    {kpi.up === true && <TrendingUp size={9} />}
                    {kpi.up === false && <TrendingDown size={9} />}
                    {kpi.trend}
                  </div>
                </div>
              );
            })}
          </div>

          {/* ─── MAIN BODY ─── */}
          <div className="flex-1 flex gap-3 min-h-0">

            {/* Left: Job Table + Tabs */}
            <div className="flex-1 flex flex-col border border-slate-800/60 rounded-lg overflow-hidden" style={{ background: "#0A101C" }}>
              {/* Table toolbar */}
              <div className="shrink-0 flex items-center gap-2 px-3 py-2 border-b border-slate-800/60">
                {/* Tabs */}
                <div className="flex gap-1">
                  {([
                    { id: "jobs", label: "Lượt Chạy", badge: JOBS.length },
                    { id: "ai", label: "AI Review", badge: 89, warn: true },
                    { id: "dedup", label: "Dedup", badge: 24 },
                  ] as { id: Tab, label: string, badge: number, warn?: boolean }[]).map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors
                        ${activeTab === tab.id ? "bg-blue-600/20 text-blue-300 border border-blue-500/30" : "text-slate-400 hover:text-slate-200"}`}
                    >
                      {tab.label}
                      <span className={`text-[10px] px-1 py-0.5 rounded leading-none
                        ${tab.warn ? "bg-amber-500/20 text-amber-400" : "bg-slate-700/70 text-slate-400"}`}>
                        {tab.badge}
                      </span>
                    </button>
                  ))}
                </div>

                <div className="flex-1" />

                {/* Status filter */}
                <div className="flex items-center gap-1">
                  {[
                    { v: "all", label: "Tất cả" },
                    { v: "running", label: "Đang chạy" },
                    { v: "error", label: "Lỗi" },
                    { v: "warn", label: "Cảnh báo" },
                  ].map(f => (
                    <button
                      key={f.v}
                      onClick={() => setStatusFilter(f.v)}
                      className={`px-2 py-0.5 rounded text-[10px] transition-colors
                        ${statusFilter === f.v ? "bg-slate-700 text-slate-200" : "text-slate-500 hover:text-slate-300"}`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>

                <button className="flex items-center gap-1 text-[10px] text-slate-500 hover:text-slate-300 px-2 py-1 rounded border border-slate-700/50 hover:border-slate-600">
                  <Filter size={10} /> Lọc
                </button>
                <button className="text-slate-500 hover:text-slate-300">
                  <RefreshCw size={12} />
                </button>
              </div>

              {/* Table */}
              {activeTab === "jobs" && (
                <div className="flex-1 overflow-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0" style={{ background: "#070B14" }}>
                      <tr className="text-[10px] uppercase text-slate-600">
                        <th className="px-3 py-2 text-left font-medium">Job ID</th>
                        <th className="px-3 py-2 text-left font-medium">Nguồn</th>
                        <th className="px-3 py-2 text-left font-medium">Loại</th>
                        <th className="px-3 py-2 text-left font-medium">Trạng Thái</th>
                        <th className="px-3 py-2 text-right font-medium">Sản Phẩm</th>
                        <th className="px-3 py-2 text-right font-medium">Thời Gian</th>
                        <th className="px-3 py-2 text-right font-medium">Bắt Đầu</th>
                        <th className="px-3 py-2 text-right font-medium">Hành Động</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/40">
                      {filteredJobs.map(job => {
                        const badge = statusBadge(job.status);
                        return (
                          <tr key={job.id} className="hover:bg-slate-800/20 transition-colors group">
                            <td className="px-3 py-2 text-blue-400 font-medium">{job.id}</td>
                            <td className="px-3 py-2 text-slate-300">{job.source}</td>
                            <td className="px-3 py-2 text-slate-500">{job.type}</td>
                            <td className="px-3 py-2">
                              <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] leading-none ${badge.cls}`}>
                                {badge.icon} {badge.label}
                              </span>
                            </td>
                            <td className="px-3 py-2 text-right font-medium text-slate-200">
                              {job.count > 0 ? job.count.toLocaleString("vi") : <span className="text-slate-600">—</span>}
                            </td>
                            <td className="px-3 py-2 text-right text-slate-500">{job.time}</td>
                            <td className="px-3 py-2 text-right text-slate-600 text-[10px]">{job.ago}</td>
                            <td className="px-3 py-2 text-right">
                              <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button className="px-1.5 py-0.5 rounded bg-blue-600/15 text-blue-400 border border-blue-500/20 text-[10px] hover:bg-blue-600/25">Mở</button>
                                <button className="px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-400 border border-slate-600/30 text-[10px] hover:bg-slate-700">Log</button>
                                {job.status === "error" && (
                                  <button className="px-1.5 py-0.5 rounded bg-red-600/15 text-red-400 border border-red-500/20 text-[10px] hover:bg-red-600/25">Chạy lại</button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                      {filteredJobs.length === 0 && (
                        <tr><td colSpan={8} className="text-center py-8 text-slate-600 text-xs">Không có kết quả phù hợp</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {activeTab === "ai" && (
                <div className="flex-1 overflow-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0" style={{ background: "#070B14" }}>
                      <tr className="text-[10px] uppercase text-slate-600">
                        <th className="px-3 py-2 text-left font-medium">Item ID</th>
                        <th className="px-3 py-2 text-left font-medium">Nguồn</th>
                        <th className="px-3 py-2 text-left font-medium">Trường</th>
                        <th className="px-3 py-2 text-left font-medium">Vấn đề</th>
                        <th className="px-3 py-2 text-right font-medium">Độ tin cậy AI</th>
                        <th className="px-3 py-2 text-right font-medium">Hành Động</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/40">
                      {AI_ITEMS.map(item => (
                        <tr key={item.id} className="hover:bg-slate-800/20 group">
                          <td className="px-3 py-2.5 text-purple-400 font-medium">{item.id}</td>
                          <td className="px-3 py-2.5 text-slate-300">{item.source}</td>
                          <td className="px-3 py-2.5 text-slate-400">{item.field}</td>
                          <td className="px-3 py-2.5 text-amber-400/80 text-[11px]">{item.issue}</td>
                          <td className="px-3 py-2.5 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <div className="w-16 bg-slate-800 rounded-full h-1">
                                <div className={`h-full rounded-full ${item.confidence < 50 ? "bg-red-500" : "bg-amber-400"}`} style={{ width: `${item.confidence}%` }} />
                              </div>
                              <span className={`text-[10px] ${item.confidence < 50 ? "text-red-400" : "text-amber-400"}`}>{item.confidence}%</span>
                            </div>
                          </td>
                          <td className="px-3 py-2.5 text-right">
                            <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100">
                              <button className="px-1.5 py-0.5 rounded bg-emerald-600/15 text-emerald-400 border border-emerald-500/20 text-[10px]">Chấp nhận</button>
                              <button className="px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-400 border border-slate-600/30 text-[10px]">Sửa</button>
                              <button className="px-1.5 py-0.5 rounded bg-red-600/15 text-red-400 border border-red-500/20 text-[10px]">Từ chối</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {activeTab === "dedup" && (
                <div className="flex-1 overflow-auto flex items-center justify-center">
                  <div className="text-center text-slate-600">
                    <Shuffle size={32} className="mx-auto mb-2 opacity-30" />
                    <p className="text-xs">24 cặp sản phẩm trùng lặp đang chờ xét duyệt</p>
                    <button className="mt-3 px-3 py-1.5 bg-blue-600/15 text-blue-400 border border-blue-500/30 rounded text-xs hover:bg-blue-600/25">
                      Xem danh sách Dedup →
                    </button>
                  </div>
                </div>
              )}

              {/* Table footer aggregate */}
              <div className="shrink-0 border-t border-slate-800/60 px-3 py-1.5 flex items-center gap-4 text-[10px] text-slate-600">
                <span>Tổng sản phẩm: <b className="text-slate-400">70,590</b></span>
                <span>Nguồn: <b className="text-slate-400">{SOURCES.filter(s => s.status === "online").length} online</b></span>
                <span>Tỷ lệ thành công: <b className="text-emerald-500">94.2%</b></span>
                <span>Lỗi (24h): <b className="text-red-400">12</b></span>
                <span className="ml-auto flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Cập nhật: vừa xong
                </span>
              </div>
            </div>

            {/* Right sidebar panels */}
            <div className="w-64 shrink-0 flex flex-col gap-2">

              {/* Throughput chart */}
              <div className="border border-slate-800/60 rounded-lg p-3 flex flex-col" style={{ background: "#0A101C" }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] uppercase text-slate-500 tracking-wider font-medium">Thông Lượng (24h)</span>
                  <span className="text-[#06B6D4] text-[10px] flex items-center gap-0.5"><Zap size={9} /> 4.2k req/s</span>
                </div>
                <div className="flex items-end gap-px" style={{ height: 48 }}>
                  {throughputData.map((v, i) => {
                    const max = Math.max(...throughputData);
                    const pct = (v / max) * 100;
                    return (
                      <div key={i} className="flex-1 rounded-t-sm bg-blue-500/30 hover:bg-blue-400/60 transition-colors" style={{ height: `${pct}%` }} />
                    );
                  })}
                </div>
                <div className="flex justify-between mt-1.5 text-[9px] text-slate-600">
                  <span>00:00</span><span>12:00</span><span>Bây giờ</span>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="border border-slate-800/60 rounded-lg p-3" style={{ background: "#0A101C" }}>
                <div className="text-[10px] uppercase text-slate-500 tracking-wider font-medium mb-2">Hành Động Nhanh</div>
                <div className="flex flex-col gap-1.5">
                  {[
                    { icon: Play, label: "Khởi động quét nhanh", color: "text-blue-400", bg: "bg-blue-600/10 border-blue-500/20 hover:bg-blue-600/20" },
                    { icon: Bot, label: "Chạy AI Review batch", color: "text-purple-400", bg: "bg-purple-600/10 border-purple-500/20 hover:bg-purple-600/20" },
                    { icon: Shuffle, label: "Xử lý dedup queue", color: "text-cyan-400", bg: "bg-cyan-600/10 border-cyan-500/20 hover:bg-cyan-600/20" },
                    { icon: AlertCircle, label: "Xem log lỗi", color: "text-red-400", bg: "bg-red-600/10 border-red-500/20 hover:bg-red-600/20" },
                    { icon: Database, label: "Dọn dẹp Cache", color: "text-slate-400", bg: "bg-slate-700/30 border-slate-600/30 hover:bg-slate-700/50" },
                  ].map(a => {
                    const Icon = a.icon;
                    return (
                      <button key={a.label} className={`flex items-center gap-2 px-2 py-1.5 rounded border text-xs transition-colors ${a.bg} ${a.color}`}>
                        <Icon size={12} className="shrink-0" />
                        <span className="text-[11px]">{a.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* System resources */}
              <div className="border border-slate-800/60 rounded-lg p-3 flex flex-col gap-2" style={{ background: "#0A101C" }}>
                <div className="text-[10px] uppercase text-slate-500 tracking-wider font-medium">Tài Nguyên Hệ Thống</div>
                {[
                  { label: "CPU", value: 42, color: "bg-blue-500" },
                  { label: "RAM", value: 78, color: "bg-amber-400" },
                  { label: "Disk I/O", value: 31, color: "bg-emerald-500" },
                  { label: "Network", value: 55, color: "bg-purple-500" },
                ].map(r => (
                  <div key={r.label}>
                    <div className="flex justify-between mb-1">
                      <span className="text-[10px] text-slate-500">{r.label}</span>
                      <span className="text-[10px] text-slate-300">{r.value}%</span>
                    </div>
                    <div className="w-full bg-slate-800 rounded-full h-1 overflow-hidden">
                      <div className={`h-full rounded-full ${r.color}`} style={{ width: `${r.value}%` }} />
                    </div>
                  </div>
                ))}
              </div>

              {/* AI Review mini panel */}
              <div className="border border-purple-500/20 rounded-lg p-3 flex-1 min-h-0" style={{ background: "#0D0B1A" }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] uppercase text-purple-400/70 tracking-wider font-medium flex items-center gap-1">
                    <Bot size={9} /> AI Review
                  </span>
                  <span className="bg-amber-500/20 text-amber-400 text-[10px] px-1.5 py-0.5 rounded-full">89 chờ</span>
                </div>
                <div className="space-y-1.5">
                  {AI_ITEMS.slice(0, 3).map(item => (
                    <div key={item.id} className="flex items-start gap-2 text-[10px]">
                      <AlertTriangle size={9} className="text-amber-400 mt-0.5 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="text-slate-400 truncate">{item.source}</div>
                        <div className="text-slate-600 truncate">{item.issue}</div>
                      </div>
                      <span className={`${item.confidence < 50 ? "text-red-400" : "text-amber-400"} shrink-0`}>{item.confidence}%</span>
                    </div>
                  ))}
                </div>
                <button className="mt-2 w-full text-center text-[10px] text-purple-400 hover:text-purple-300">
                  Xem tất cả 89 mục →
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
