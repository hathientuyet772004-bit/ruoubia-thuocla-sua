import React from "react";
import { 
  Activity, 
  AlertCircle, 
  BarChart2, 
  CheckCircle2, 
  Clock, 
  Cpu, 
  Database, 
  Globe, 
  LayoutDashboard, 
  Play, 
  RefreshCw, 
  Settings, 
  ShoppingCart, 
  Terminal, 
  Zap 
} from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function Compact() {
  return (
    <div className="flex h-screen w-full overflow-hidden text-slate-300 font-mono text-sm" style={{ backgroundColor: "#060A12" }}>
      {/* Sidebar - Narrow 48px Icon Rail */}
      <aside className="w-12 h-full flex flex-col items-center py-4 border-r border-slate-800/50" style={{ backgroundColor: "#0A101C" }}>
        <div className="text-[#06B6D4] mb-8">
          <Terminal size={20} />
        </div>
        
        <nav className="flex-1 flex flex-col gap-6 w-full items-center">
          <button className="text-[#06B6D4] hover:text-[#06B6D4]/80 transition-colors">
            <LayoutDashboard size={18} />
          </button>
          <button className="text-slate-500 hover:text-slate-300 transition-colors">
            <Database size={18} />
          </button>
          <button className="text-slate-500 hover:text-slate-300 transition-colors">
            <Globe size={18} />
          </button>
          <button className="text-slate-500 hover:text-slate-300 transition-colors">
            <ShoppingCart size={18} />
          </button>
          <button className="text-slate-500 hover:text-slate-300 transition-colors">
            <Activity size={18} />
          </button>
        </nav>
        
        <div className="mt-auto flex flex-col gap-6 w-full items-center">
          <button className="text-slate-500 hover:text-slate-300 transition-colors">
            <Settings size={18} />
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-full p-4 overflow-hidden">
        {/* Header */}
        <header className="flex justify-between items-end mb-4 shrink-0 border-b border-slate-800/50 pb-2">
          <div>
            <h1 className="text-lg font-semibold text-white tracking-tight flex items-center gap-2">
              Cockpit Tổng Quan <span className="text-xs font-normal text-slate-500 bg-slate-800/50 px-1.5 py-0.5 rounded">VN-PRD-01</span>
            </h1>
            <p className="text-xs text-slate-500 mt-1">Cập nhật lần cuối: 10:42:05 | Tải hệ thống: 12%</p>
          </div>
          <div className="flex gap-2">
            <Badge variant="outline" className="text-[#06B6D4] border-[#06B6D4]/30 bg-[#06B6D4]/10 rounded-sm text-[10px] px-1.5 h-5">TRỰC TUYẾN</Badge>
            <Badge variant="outline" className="text-slate-400 border-slate-700 bg-slate-800/50 rounded-sm text-[10px] px-1.5 h-5">AUTO-SYNC: ON</Badge>
          </div>
        </header>

        {/* 6-col Metrics Grid */}
        <div className="grid grid-cols-6 gap-3 mb-4 shrink-0">
          <MetricCard title="Tổng Sản Phẩm" value="1,245,892" trend="+1.2%" isUp={true} />
          <MetricCard title="Nguồn Quét" value="142" trend="+3" isUp={true} />
          <MetricCard title="Job Đang Chạy" value="8" trend="0" isUp={true} neutral={true} />
          <MetricCard title="Đang Chờ" value="45" trend="-12" isUp={true} />
          <MetricCard title="Lỗi (24h)" value="12" trend="+2" isUp={false} alert={true} />
          <MetricCard title="Hoàn Tất (24h)" value="892" trend="+15%" isUp={true} />
        </div>

        {/* Mid Section: Table & Sparkline */}
        <div className="flex gap-4 flex-1 min-h-0">
          {/* Table */}
          <div className="flex-1 flex flex-col border border-slate-800/50 rounded bg-[#0A101C]/50 overflow-hidden">
            <div className="px-3 py-2 border-b border-slate-800/50 bg-[#0A101C] flex justify-between items-center">
              <h2 className="text-xs font-medium text-slate-300 uppercase tracking-wider">Tiến Trình Gần Đây</h2>
              <button className="text-slate-500 hover:text-white"><RefreshCw size={12} /></button>
            </div>
            <div className="flex-1 overflow-auto p-0">
              <table className="w-full text-xs text-left">
                <thead className="text-[10px] uppercase text-slate-500 sticky top-0 bg-[#0A101C]/90 backdrop-blur">
                  <tr>
                    <th className="px-3 py-1.5 font-medium">Job ID</th>
                    <th className="px-3 py-1.5 font-medium">Nguồn</th>
                    <th className="px-3 py-1.5 font-medium">Trạng Thái</th>
                    <th className="px-3 py-1.5 font-medium text-right">Sản Phẩm</th>
                    <th className="px-3 py-1.5 font-medium text-right">Thời Gian</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  <TableRow id="JOB-8921" source="thegioididong.com" status="Hoàn tất" count="15,420" time="12m 45s" statusType="success" />
                  <TableRow id="JOB-8920" source="fptshop.com.vn" status="Đang chạy" count="8,210" time="05m 12s" statusType="running" />
                  <TableRow id="JOB-8919" source="cellphones.com.vn" status="Lỗi" count="4,102" time="02m 05s" statusType="error" />
                  <TableRow id="JOB-8918" source="hoanghamobile.com" status="Hoàn tất" count="9,850" time="08m 30s" statusType="success" />
                  <TableRow id="JOB-8917" source="diendammay.com" status="Hoàn tất" count="2,140" time="01m 45s" statusType="success" />
                </tbody>
              </table>
            </div>
          </div>

          {/* Sparkline & Status */}
          <div className="w-64 flex flex-col gap-4">
            <div className="flex-1 border border-slate-800/50 rounded bg-[#0A101C]/50 p-3 flex flex-col relative overflow-hidden">
              <h2 className="text-xs font-medium text-slate-300 uppercase tracking-wider mb-2">Thông Lượng (1h)</h2>
              <div className="flex-1 flex items-end gap-1 mt-2">
                {/* Mock Sparkline bars */}
                {[...Array(20)].map((_, i) => (
                  <div 
                    key={i} 
                    className="flex-1 bg-[#06B6D4]/40 hover:bg-[#06B6D4] transition-colors rounded-t-sm"
                    style={{ height: `${Math.max(10, Math.random() * 100)}%` }}
                  />
                ))}
              </div>
              <div className="absolute top-2 right-2 text-[#06B6D4] flex items-center gap-1 text-[10px]">
                <Zap size={10} /> 4.2k req/s
              </div>
            </div>

            <div className="h-24 border border-slate-800/50 rounded bg-[#0A101C]/50 p-3 flex flex-col justify-center">
              <div className="flex justify-between items-center mb-1">
                <span className="text-[10px] text-slate-400">Tài nguyên CPU</span>
                <span className="text-[10px] text-white">42%</span>
              </div>
              <div className="w-full bg-slate-800 h-1.5 rounded-full mb-3 overflow-hidden">
                <div className="bg-[#06B6D4] h-full" style={{ width: '42%' }} />
              </div>
              
              <div className="flex justify-between items-center mb-1">
                <span className="text-[10px] text-slate-400">Bộ nhớ (RAM)</span>
                <span className="text-[10px] text-white">78%</span>
              </div>
              <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                <div className="bg-amber-500 h-full" style={{ width: '78%' }} />
              </div>
            </div>
          </div>
        </div>

        {/* Quick Actions Footer */}
        <div className="mt-4 shrink-0 flex gap-2">
          <ActionButton icon={<Play size={14} />} label="Khởi động quét nhanh" primary />
          <ActionButton icon={<AlertCircle size={14} />} label="Xem log lỗi" />
          <ActionButton icon={<Cpu size={14} />} label="Cấu hình Proxy" />
          <ActionButton icon={<Database size={14} />} label="Dọn dẹp Cache" />
        </div>
      </main>
    </div>
  );
}

function MetricCard({ title, value, trend, isUp, neutral = false, alert = false }: { title: string, value: string, trend: string, isUp: boolean, neutral?: boolean, alert?: boolean }) {
  const trendColor = alert ? "text-red-400" : neutral ? "text-slate-500" : isUp ? "text-[#06B6D4]" : "text-amber-400";
  return (
    <div className="bg-[#0A101C]/50 border border-slate-800/50 rounded p-2 flex flex-col justify-between">
      <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 truncate">{title}</div>
      <div className="flex items-end justify-between">
        <div className="text-lg text-white font-medium leading-none">{value}</div>
        <div className={`text-[10px] ${trendColor} font-medium flex items-center`}>
          {!neutral && (isUp ? '↑' : '↓')} {trend}
        </div>
      </div>
    </div>
  );
}

function TableRow({ id, source, status, count, time, statusType }: { id: string, source: string, status: string, count: string, time: string, statusType: 'success' | 'running' | 'error' }) {
  return (
    <tr className="hover:bg-slate-800/30 transition-colors group">
      <td className="px-3 py-2 text-[#06B6D4] font-medium">{id}</td>
      <td className="px-3 py-2 text-slate-300">{source}</td>
      <td className="px-3 py-2">
        <div className="flex items-center gap-1.5">
          {statusType === 'success' && <CheckCircle2 size={10} className="text-emerald-500" />}
          {statusType === 'running' && <RefreshCw size={10} className="text-[#06B6D4] animate-spin" />}
          {statusType === 'error' && <AlertCircle size={10} className="text-red-500" />}
          <span className={
            statusType === 'success' ? 'text-emerald-500/90' : 
            statusType === 'running' ? 'text-[#06B6D4]/90' : 
            'text-red-500/90'
          }>{status}</span>
        </div>
      </td>
      <td className="px-3 py-2 text-right font-medium">{count}</td>
      <td className="px-3 py-2 text-right text-slate-500 flex items-center justify-end gap-1"><Clock size={10} /> {time}</td>
    </tr>
  );
}

function ActionButton({ icon, label, primary = false }: { icon: React.ReactNode, label: string, primary?: boolean }) {
  return (
    <button 
      className={`
        flex items-center gap-2 px-3 py-1.5 rounded-sm text-xs transition-colors
        ${primary 
          ? 'bg-[#06B6D4]/10 text-[#06B6D4] border border-[#06B6D4]/30 hover:bg-[#06B6D4]/20' 
          : 'bg-slate-800/30 text-slate-400 border border-slate-700/50 hover:bg-slate-800 hover:text-slate-200'
        }
      `}
      title={label}
    >
      {icon}
      <span className="sr-only sm:not-sr-only">{label}</span>
    </button>
  );
}
