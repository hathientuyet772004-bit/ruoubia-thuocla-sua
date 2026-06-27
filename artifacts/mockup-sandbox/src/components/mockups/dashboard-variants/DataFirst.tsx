import React, { useState } from "react";
import { 
  Search, 
  Filter, 
  Activity, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  Play, 
  MoreHorizontal, 
  Server, 
  Database, 
  Settings, 
  LayoutDashboard,
  ExternalLink,
  ChevronDown,
  RefreshCw,
  Box
} from "lucide-react";

export function DataFirst() {
  const [selectedSources, setSelectedSources] = useState<string[]>([]);

  const sources = [
    { id: "s1", name: "thegioididong.com", status: "online", count: 12500 },
    { id: "s2", name: "fptshop.com.vn", status: "online", count: 8300 },
    { id: "s3", name: "cellphones.com.vn", status: "warning", count: 5400 },
    { id: "s4", name: "hoanghamobile.com", status: "online", count: 6200 },
    { id: "s5", name: "dienmayxanh.com", status: "offline", count: 15800 },
    { id: "s6", name: "nguyenkim.com", status: "warning", count: 4100 },
    { id: "s7", name: "mediamart.vn", status: "online", count: 3900 },
    { id: "s8", name: "phongvu.vn", status: "online", count: 9200 },
    { id: "s9", name: "gearvn.com", status: "offline", count: 2100 },
    { id: "s10", name: "hacom.vn", status: "online", count: 3400 },
  ];

  const jobs = [
    { id: "JOB-9842", source: "thegioididong.com", type: "Full Crawl", status: "success", duration: "45m 12s", items: 12500, time: "10 phút trước" },
    { id: "JOB-9841", source: "fptshop.com.vn", type: "Delta Update", status: "running", duration: "12m 05s", items: 3420, time: "Đang chạy..." },
    { id: "JOB-9840", source: "cellphones.com.vn", type: "Price Sync", status: "warning", duration: "08m 30s", items: 5400, time: "25 phút trước" },
    { id: "JOB-9839", source: "dienmayxanh.com", type: "Full Crawl", status: "failed", duration: "02m 14s", items: 0, time: "1 giờ trước" },
    { id: "JOB-9838", source: "hoanghamobile.com", type: "Delta Update", status: "success", duration: "15m 22s", items: 1250, time: "2 giờ trước" },
    { id: "JOB-9837", source: "phongvu.vn", type: "Price Sync", status: "success", duration: "05m 45s", items: 9200, time: "3 giờ trước" },
    { id: "JOB-9836", source: "nguyenkim.com", type: "Full Crawl", status: "warning", duration: "52m 10s", items: 4050, time: "4 giờ trước" },
    { id: "JOB-9835", source: "gearvn.com", type: "Price Sync", status: "failed", duration: "01m 05s", items: 0, time: "5 giờ trước" },
    { id: "JOB-9834", source: "mediamart.vn", type: "Delta Update", status: "success", duration: "11m 30s", items: 840, time: "6 giờ trước" },
    { id: "JOB-9833", source: "hacom.vn", type: "Full Crawl", status: "success", duration: "28m 15s", items: 3400, time: "7 giờ trước" },
    { id: "JOB-9832", source: "thegioididong.com", type: "Price Sync", status: "success", duration: "06m 20s", items: 12500, time: "8 giờ trước" },
  ];

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "online":
      case "success":
        return <CheckCircle2 className="w-4 h-4 text-[#10B981]" />;
      case "offline":
      case "failed":
        return <XCircle className="w-4 h-4 text-red-500" />;
      case "warning":
        return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      case "running":
        return <RefreshCw className="w-4 h-4 text-blue-400 animate-spin" />;
      default:
        return <Activity className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "online":
      case "success":
        return "text-[#10B981] bg-[#10B981]/10 border-[#10B981]/20";
      case "offline":
      case "failed":
        return "text-red-400 bg-red-400/10 border-red-400/20";
      case "warning":
        return "text-yellow-400 bg-yellow-400/10 border-yellow-400/20";
      case "running":
        return "text-blue-400 bg-blue-400/10 border-blue-400/20";
      default:
        return "text-gray-400 bg-gray-400/10 border-gray-400/20";
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case "success": return "Hoàn thành";
      case "failed": return "Thất bại";
      case "warning": return "Cảnh báo";
      case "running": return "Đang chạy";
      default: return status;
    }
  };

  const toggleSource = (id: string) => {
    setSelectedSources(prev => 
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    );
  };

  return (
    <div className="flex h-screen w-full bg-[#0A0A0F] text-gray-300 font-sans overflow-hidden selection:bg-[#10B981]/30">
      
      {/* Minimal Sidebar */}
      <div className="w-14 border-r border-[#1C1C24] bg-[#0D0D12] flex flex-col items-center py-4 gap-6 shrink-0 z-10">
        <div className="w-8 h-8 rounded bg-[#10B981]/20 flex items-center justify-center text-[#10B981] mb-4">
          <Database className="w-5 h-5" />
        </div>
        <button className="p-2 rounded-lg bg-[#1C1C24] text-white hover:bg-[#2A2A35] transition-colors group relative">
          <LayoutDashboard className="w-5 h-5" />
          <span className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-xs rounded opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-50">Tổng quan</span>
        </button>
        <button className="p-2 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-[#1C1C24] transition-colors group relative">
          <Server className="w-5 h-5" />
          <span className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-xs rounded opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-50">Nguồn dữ liệu</span>
        </button>
        <button className="p-2 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-[#1C1C24] transition-colors group relative">
          <Box className="w-5 h-5" />
          <span className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-xs rounded opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-50">Sản phẩm</span>
        </button>
        <div className="mt-auto">
          <button className="p-2 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-[#1C1C24] transition-colors group relative">
            <Settings className="w-5 h-5" />
            <span className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-xs rounded opacity-0 group-hover:opacity-100 whitespace-nowrap pointer-events-none z-50">Cài đặt</span>
          </button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        
        {/* Left Column: Persistent Sources Filter Panel */}
        <div className="w-72 border-r border-[#1C1C24] bg-[#0D0D12] flex flex-col shrink-0">
          <div className="p-4 border-b border-[#1C1C24]">
            <h2 className="text-sm font-semibold text-white uppercase tracking-wider flex items-center gap-2">
              <Filter className="w-4 h-4 text-[#10B981]" />
              Lọc theo nguồn
            </h2>
          </div>
          
          <div className="p-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input 
                type="text" 
                placeholder="Tìm nguồn..." 
                className="w-full bg-[#1C1C24] border border-[#2A2A35] rounded-md py-1.5 pl-9 pr-3 text-sm text-gray-200 placeholder:text-gray-500 focus:outline-none focus:border-[#10B981] focus:ring-1 focus:ring-[#10B981] transition-all"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar p-2">
            <div className="space-y-1">
              {sources.map(source => (
                <label 
                  key={source.id} 
                  className={`flex items-center justify-between p-2 rounded cursor-pointer transition-colors ${
                    selectedSources.includes(source.id) ? 'bg-[#1C1C24]' : 'hover:bg-[#1C1C24]/50'
                  }`}
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    <div className="relative flex items-center justify-center">
                      <input 
                        type="checkbox" 
                        className="peer sr-only"
                        checked={selectedSources.includes(source.id)}
                        onChange={() => toggleSource(source.id)}
                      />
                      <div className="w-4 h-4 rounded border border-gray-600 bg-transparent peer-checked:bg-[#10B981] peer-checked:border-[#10B981] flex items-center justify-center transition-colors">
                        {selectedSources.includes(source.id) && <CheckCircle2 className="w-3 h-3 text-[#0A0A0F]" />}
                      </div>
                    </div>
                    <div className="flex flex-col overflow-hidden">
                      <span className="text-sm font-medium text-gray-200 truncate">{source.name}</span>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        {getStatusIcon(source.status)}
                        <span className="text-[10px] text-gray-500 uppercase">{source.status}</span>
                      </div>
                    </div>
                  </div>
                  <span className="text-xs text-gray-500 font-mono bg-[#0A0A0F] px-1.5 py-0.5 rounded border border-[#1C1C24]">
                    {(source.count / 1000).toFixed(1)}k
                  </span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Main Content */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
          
          {/* Top Bar */}
          <div className="h-16 border-b border-[#1C1C24] bg-[#0A0A0F] flex items-center justify-between px-6 shrink-0 z-10">
            <div className="flex items-center gap-4 flex-1">
              <div className="relative w-96 max-w-full">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input 
                  type="text" 
                  placeholder="Tìm kiếm Job ID, Nguồn, hoặc Trạng thái..." 
                  className="w-full bg-[#111116] border border-[#2A2A35] rounded-md py-2 pl-9 pr-4 text-sm text-gray-200 placeholder:text-gray-500 focus:outline-none focus:border-[#10B981] focus:ring-1 focus:ring-[#10B981] transition-all"
                />
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 border border-[#2A2A35] rounded-md bg-[#111116] px-3 py-1.5 text-sm cursor-pointer hover:border-gray-500 transition-colors">
                <span className="text-gray-400">Trạng thái:</span>
                <span className="text-gray-200 font-medium">Tất cả</span>
                <ChevronDown className="w-4 h-4 text-gray-500" />
              </div>
              <div className="flex items-center gap-2 border border-[#2A2A35] rounded-md bg-[#111116] px-3 py-1.5 text-sm cursor-pointer hover:border-gray-500 transition-colors">
                <span className="text-gray-400">Loại Job:</span>
                <span className="text-gray-200 font-medium">Tất cả</span>
                <ChevronDown className="w-4 h-4 text-gray-500" />
              </div>
              <div className="flex items-center gap-2 border border-[#2A2A35] rounded-md bg-[#111116] px-3 py-1.5 text-sm cursor-pointer hover:border-gray-500 transition-colors">
                <span className="text-gray-400">Thời gian:</span>
                <span className="text-gray-200 font-medium">24h qua</span>
                <ChevronDown className="w-4 h-4 text-gray-500" />
              </div>
              <button className="bg-[#10B981] hover:bg-[#059669] text-[#0A0A0F] px-4 py-1.5 rounded-md text-sm font-semibold transition-colors flex items-center gap-2 ml-2 shadow-[0_0_15px_rgba(16,185,129,0.2)]">
                <Play className="w-4 h-4" />
                Chạy Crawl
              </button>
            </div>
          </div>

          {/* Table Container */}
          <div className="flex-1 overflow-auto bg-[#0A0A0F]">
            <table className="w-full text-left border-collapse min-w-[800px]">
              <thead className="sticky top-0 bg-[#0A0A0F] z-10 border-b border-[#1C1C24] shadow-sm">
                <tr>
                  <th className="py-3 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider">Job ID</th>
                  <th className="py-3 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider">Nguồn</th>
                  <th className="py-3 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider">Loại Job</th>
                  <th className="py-3 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider">Trạng thái</th>
                  <th className="py-3 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider text-right">Sản phẩm</th>
                  <th className="py-3 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider text-right">Thời gian chạy</th>
                  <th className="py-3 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider text-right">Khởi tạo</th>
                  <th className="py-3 px-6 text-xs font-semibold text-gray-400 uppercase tracking-wider text-center">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1C1C24]">
                {jobs.map((job, idx) => (
                  <tr 
                    key={job.id} 
                    className={`${idx % 2 === 0 ? 'bg-[#111116]' : 'bg-[#0D0D12]'} hover:bg-[#1C1C24] transition-colors group`}
                  >
                    <td className="py-3 px-6 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm text-[#10B981]">{job.id}</span>
                      </div>
                    </td>
                    <td className="py-3 px-6 whitespace-nowrap">
                      <span className="text-sm font-medium text-gray-200">{job.source}</span>
                    </td>
                    <td className="py-3 px-6 whitespace-nowrap">
                      <span className="text-sm text-gray-400">{job.type}</span>
                    </td>
                    <td className="py-3 px-6 whitespace-nowrap">
                      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${getStatusColor(job.status)}`}>
                        {getStatusIcon(job.status)}
                        {getStatusText(job.status)}
                      </div>
                    </td>
                    <td className="py-3 px-6 whitespace-nowrap text-right">
                      <span className="text-sm font-mono text-gray-300">{job.items.toLocaleString()}</span>
                    </td>
                    <td className="py-3 px-6 whitespace-nowrap text-right">
                      <span className="text-sm font-mono text-gray-400">{job.duration}</span>
                    </td>
                    <td className="py-3 px-6 whitespace-nowrap text-right">
                      <span className="text-sm text-gray-400">{job.time}</span>
                    </td>
                    <td className="py-3 px-6 whitespace-nowrap text-center">
                      <div className="flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button className="p-1.5 text-gray-400 hover:text-[#10B981] hover:bg-[#10B981]/10 rounded transition-colors" title="Chi tiết">
                          <ExternalLink className="w-4 h-4" />
                        </button>
                        <button className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors" title="Thêm">
                          <MoreHorizontal className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Compact KPI Strip at Bottom */}
          <div className="h-12 bg-[#0D0D12] border-t border-[#1C1C24] flex items-center px-6 shrink-0 z-20">
            <div className="flex items-center gap-8 w-full">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 uppercase font-semibold">Tổng sản phẩm</span>
                <span className="text-sm font-mono font-bold text-white">70,590</span>
              </div>
              <div className="w-px h-4 bg-[#2A2A35]"></div>
              
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 uppercase font-semibold">Nguồn</span>
                <span className="text-sm font-mono font-bold text-white">10</span>
                <span className="text-xs text-[#10B981] bg-[#10B981]/10 px-1 rounded">7 Online</span>
              </div>
              <div className="w-px h-4 bg-[#2A2A35]"></div>
              
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 uppercase font-semibold">Tỷ lệ thành công</span>
                <span className="text-sm font-mono font-bold text-[#10B981]">94.2%</span>
              </div>
              <div className="w-px h-4 bg-[#2A2A35]"></div>
              
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 uppercase font-semibold">Lỗi (24h)</span>
                <span className="text-sm font-mono font-bold text-red-400">12</span>
              </div>
              <div className="w-px h-4 bg-[#2A2A35]"></div>
              
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 uppercase font-semibold">Đang chờ</span>
                <span className="text-sm font-mono font-bold text-blue-400">4</span>
              </div>

              <div className="ml-auto flex items-center gap-2 text-xs text-gray-500">
                <div className="w-2 h-2 rounded-full bg-[#10B981] animate-pulse"></div>
                Cập nhật lần cuối: Vừa xong
              </div>
            </div>
          </div>

        </div>
      </div>

      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar {
          width: 6px;
          height: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #2A2A35;
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #3F3F4E;
        }
      `}} />
    </div>
  );
}
