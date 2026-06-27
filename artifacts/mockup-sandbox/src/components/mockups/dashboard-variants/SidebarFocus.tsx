import React from "react";
import { 
  LayoutDashboard, 
  Database, 
  Settings, 
  Activity, 
  FolderKanban, 
  Users, 
  Play, 
  ArrowRight, 
  CheckCircle2, 
  XCircle, 
  Clock,
  Server,
  AlertTriangle,
  Zap
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

const SparklineUp = () => (
  <svg className="w-full h-12 stroke-[#8B5CF6] fill-none drop-shadow-[0_0_8px_rgba(139,92,246,0.5)]" viewBox="0 0 100 30" preserveAspectRatio="none">
    <path d="M0 28 Q 10 25, 20 22 T 40 18 T 60 12 T 80 8 T 100 2" strokeWidth="2.5" strokeLinecap="round" />
  </svg>
);

const SparklineDown = () => (
  <svg className="w-full h-12 stroke-pink-500 fill-none drop-shadow-[0_0_8px_rgba(236,72,153,0.5)]" viewBox="0 0 100 30" preserveAspectRatio="none">
    <path d="M0 5 Q 10 8, 20 12 T 40 15 T 60 20 T 80 25 T 100 28" strokeWidth="2.5" strokeLinecap="round" />
  </svg>
);

const SparklineFlat = () => (
  <svg className="w-full h-12 stroke-blue-400 fill-none drop-shadow-[0_0_8px_rgba(96,165,250,0.5)]" viewBox="0 0 100 30" preserveAspectRatio="none">
    <path d="M0 15 Q 15 12, 30 16 T 60 14 T 80 18 T 100 15" strokeWidth="2.5" strokeLinecap="round" />
  </svg>
);

export function SidebarFocus() {
  return (
    <div className="flex h-screen w-full font-sans text-slate-200 overflow-hidden" style={{ backgroundColor: "#0F0C29", fontFamily: "Inter, sans-serif" }}>
      {/* Sidebar - #1E1B4B */}
      <aside className="w-[220px] h-full flex flex-col border-r border-[#8B5CF6]/20 relative z-10" style={{ background: "linear-gradient(180deg, #1E1B4B 0%, #0F0C29 100%)" }}>
        <div className="p-5">
          <div className="flex items-center gap-2 mb-8">
            <div className="w-8 h-8 rounded bg-[#8B5CF6] flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-lg text-white tracking-tight">CrawlAI Pro</span>
          </div>

          <div className="space-y-6">
            {/* Group 1 */}
            <div>
              <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2 px-2">Tổng quan</h3>
              <ul className="space-y-1">
                <li>
                  <a href="#" className="flex items-center justify-between px-2 py-2 rounded bg-[#8B5CF6]/10 text-[#8B5CF6] font-medium transition-colors">
                    <div className="flex items-center gap-2">
                      <LayoutDashboard className="w-4 h-4" />
                      <span className="text-sm">Bảng điều khiển</span>
                    </div>
                  </a>
                </li>
                <li>
                  <a href="#" className="flex items-center justify-between px-2 py-2 rounded text-slate-400 hover:text-white hover:bg-white/5 transition-colors">
                    <div className="flex items-center gap-2">
                      <Activity className="w-4 h-4" />
                      <span className="text-sm">Hoạt động</span>
                    </div>
                    <span className="text-xs bg-[#8B5CF6]/20 text-[#8B5CF6] px-1.5 rounded">12</span>
                  </a>
                </li>
              </ul>
            </div>

            {/* Group 2 */}
            <div>
              <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2 px-2">Thu thập</h3>
              <ul className="space-y-1">
                <li>
                  <a href="#" className="flex items-center justify-between px-2 py-2 rounded text-slate-400 hover:text-white hover:bg-white/5 transition-colors">
                    <div className="flex items-center gap-2">
                      <FolderKanban className="w-4 h-4" />
                      <span className="text-sm">Dự án</span>
                    </div>
                    <span className="text-xs text-slate-500">8</span>
                  </a>
                </li>
                <li>
                  <div className="px-2 py-2 rounded text-slate-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer group">
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <Database className="w-4 h-4" />
                        <span className="text-sm">Nguồn dữ liệu</span>
                      </div>
                      <span className="text-xs text-slate-500">24/30</span>
                    </div>
                    <Progress value={80} className="h-1 bg-slate-800 [&>div]:bg-[#8B5CF6] opacity-50 group-hover:opacity-100 transition-opacity" />
                  </div>
                </li>
                <li>
                  <a href="#" className="flex items-center justify-between px-2 py-2 rounded text-slate-400 hover:text-white hover:bg-white/5 transition-colors">
                    <div className="flex items-center gap-2">
                      <Server className="w-4 h-4" />
                      <span className="text-sm">Proxies</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      <span className="text-xs text-emerald-400">On</span>
                    </div>
                  </a>
                </li>
              </ul>
            </div>

            {/* Group 3 */}
            <div>
              <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2 px-2">Quản trị</h3>
              <ul className="space-y-1">
                <li>
                  <a href="#" className="flex items-center justify-between px-2 py-2 rounded text-slate-400 hover:text-white hover:bg-white/5 transition-colors">
                    <div className="flex items-center gap-2">
                      <Users className="w-4 h-4" />
                      <span className="text-sm">Thành viên</span>
                    </div>
                  </a>
                </li>
                <li>
                  <a href="#" className="flex items-center justify-between px-2 py-2 rounded text-slate-400 hover:text-white hover:bg-white/5 transition-colors">
                    <div className="flex items-center gap-2">
                      <Settings className="w-4 h-4" />
                      <span className="text-sm">Cài đặt</span>
                    </div>
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>
        
        <div className="mt-auto p-4 border-t border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-medium">AD</div>
            <div className="flex flex-col">
              <span className="text-sm text-white font-medium">Admin User</span>
              <span className="text-xs text-slate-500">Premium Plan</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 p-8 overflow-y-auto relative">
        <div className="absolute inset-0 bg-[#8B5CF6]/5 pointer-events-none" style={{ mixBlendMode: 'screen', filter: 'blur(100px)' }} />
        
        <div className="max-w-6xl mx-auto space-y-8 relative z-10">
          
          <header className="flex justify-between items-end">
            <div>
              <h1 className="text-3xl font-bold text-white tracking-tight mb-1">Bảng điều khiển</h1>
              <p className="text-slate-400">Chào mừng trở lại. Hệ thống đang hoạt động ổn định.</p>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 px-3 py-1">
                <CheckCircle2 className="w-3 h-3 mr-1" />
                Hệ thống OK
              </Badge>
              <div className="text-sm text-slate-400 bg-white/5 px-3 py-1 rounded border border-white/10 flex items-center">
                <Clock className="w-4 h-4 mr-2" />
                Cập nhật 2p trước
              </div>
            </div>
          </header>

          {/* KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="bg-[#1E1B4B]/60 border-[#8B5CF6]/30 shadow-[0_0_20px_rgba(139,92,246,0.1)] backdrop-blur-sm relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-32 h-32 bg-[#8B5CF6]/20 rounded-full blur-3xl -mr-10 -mt-10 transition-transform group-hover:scale-150 duration-500" />
              <CardContent className="p-6">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <p className="text-sm font-medium text-slate-400 mb-1">Tổng Sản Phẩm</p>
                    <h3 className="text-3xl font-bold text-white">1,248,392</h3>
                  </div>
                  <div className="p-2 bg-[#8B5CF6]/20 rounded-lg">
                    <Database className="w-5 h-5 text-[#8B5CF6]" />
                  </div>
                </div>
                <div className="mt-4">
                  <SparklineUp />
                </div>
                <div className="mt-4 flex items-center text-xs">
                  <span className="text-emerald-400 font-medium">+12.5%</span>
                  <span className="text-slate-500 ml-2">so với tuần trước</span>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-[#1E1B4B]/60 border-white/10 backdrop-blur-sm relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-3xl -mr-10 -mt-10 transition-transform group-hover:scale-150 duration-500" />
              <CardContent className="p-6">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <p className="text-sm font-medium text-slate-400 mb-1">Nhiệm Vụ Đang Chờ</p>
                    <h3 className="text-3xl font-bold text-white">432</h3>
                  </div>
                  <div className="p-2 bg-blue-500/20 rounded-lg">
                    <Activity className="w-5 h-5 text-blue-400" />
                  </div>
                </div>
                <div className="mt-4">
                  <SparklineFlat />
                </div>
                <div className="mt-4 flex items-center text-xs">
                  <span className="text-blue-400 font-medium">Ổn định</span>
                  <span className="text-slate-500 ml-2">trong giới hạn</span>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-[#1E1B4B]/60 border-white/10 backdrop-blur-sm relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-32 h-32 bg-pink-500/10 rounded-full blur-3xl -mr-10 -mt-10 transition-transform group-hover:scale-150 duration-500" />
              <CardContent className="p-6">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <p className="text-sm font-medium text-slate-400 mb-1">Lỗi Cào Dữ Liệu</p>
                    <h3 className="text-3xl font-bold text-white">89</h3>
                  </div>
                  <div className="p-2 bg-pink-500/20 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-pink-400" />
                  </div>
                </div>
                <div className="mt-4">
                  <SparklineDown />
                </div>
                <div className="mt-4 flex items-center text-xs">
                  <span className="text-emerald-400 font-medium">-4.2%</span>
                  <span className="text-slate-500 ml-2">đã giảm</span>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 min-h-[400px]">
            {/* Lượt chạy gần đây - Takes 2 cols */}
            <Card className="lg:col-span-2 bg-[#1E1B4B]/40 border-white/5 backdrop-blur-sm">
              <CardHeader className="border-b border-white/5 pb-4">
                <CardTitle className="text-lg text-white font-medium flex items-center">
                  <Play className="w-5 h-5 mr-2 text-[#8B5CF6]" />
                  Lượt chạy gần đây
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y divide-white/5">
                  {[
                    { id: 'JOB-9482', source: 'thegioididong.com', status: 'success', time: '10 phút trước', items: 1205 },
                    { id: 'JOB-9481', source: 'dienmayxanh.com', status: 'running', time: 'Đang chạy (45%)', items: 840 },
                    { id: 'JOB-9480', source: 'cellphones.com.vn', status: 'failed', time: '1 giờ trước', items: 0 },
                    { id: 'JOB-9479', source: 'fptshop.com.vn', status: 'success', time: '2 giờ trước', items: 3450 },
                    { id: 'JOB-9478', source: 'hoanghamobile.com', status: 'success', time: '3 giờ trước', items: 920 },
                  ].map((job, i) => (
                    <div key={i} className="p-4 hover:bg-white/[0.02] transition-colors flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className={`p-2 rounded-full ${
                          job.status === 'success' ? 'bg-emerald-500/10 text-emerald-400' :
                          job.status === 'running' ? 'bg-blue-500/10 text-blue-400' :
                          'bg-pink-500/10 text-pink-400'
                        }`}>
                          {job.status === 'success' ? <CheckCircle2 className="w-4 h-4" /> :
                           job.status === 'running' ? <Activity className="w-4 h-4 animate-pulse" /> :
                           <XCircle className="w-4 h-4" />}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-slate-200">{job.source}</span>
                            <span className="text-xs text-slate-500 font-mono">{job.id}</span>
                          </div>
                          <p className="text-xs text-slate-400 mt-0.5">{job.time}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-medium text-slate-300">{job.items.toLocaleString()} mục</div>
                        <div className="text-xs text-slate-500 mt-0.5">đã thu thập</div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Luồng quan trọng shortcuts */}
            <Card className="bg-[#1E1B4B]/40 border-white/5 backdrop-blur-sm flex flex-col">
              <CardHeader className="border-b border-white/5 pb-4">
                <CardTitle className="text-lg text-white font-medium flex items-center">
                  <Zap className="w-5 h-5 mr-2 text-[#8B5CF6]" />
                  Luồng quan trọng
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 flex-1 flex flex-col gap-3">
                <button className="w-full flex items-center p-4 rounded-xl bg-gradient-to-r from-[#8B5CF6]/20 to-transparent border border-[#8B5CF6]/30 hover:border-[#8B5CF6]/60 transition-all group text-left">
                  <div className="p-2 bg-[#8B5CF6]/30 rounded-lg mr-4">
                    <Play className="w-5 h-5 text-[#8B5CF6]" />
                  </div>
                  <div className="flex-1">
                    <h4 className="text-slate-200 font-medium group-hover:text-white transition-colors">Chạy tất cả nguồn</h4>
                    <p className="text-xs text-slate-400 mt-0.5">Khởi động 24 crawler</p>
                  </div>
                  <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-white group-hover:translate-x-1 transition-all" />
                </button>

                <button className="w-full flex items-center p-4 rounded-xl bg-white/5 border border-white/10 hover:border-white/20 transition-all group text-left">
                  <div className="p-2 bg-white/10 rounded-lg mr-4">
                    <Database className="w-5 h-5 text-slate-300" />
                  </div>
                  <div className="flex-1">
                    <h4 className="text-slate-200 font-medium group-hover:text-white transition-colors">Đồng bộ Database</h4>
                    <p className="text-xs text-slate-400 mt-0.5">Cập nhật chỉ mục</p>
                  </div>
                  <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-white group-hover:translate-x-1 transition-all" />
                </button>

                <button className="w-full flex items-center p-4 rounded-xl bg-white/5 border border-white/10 hover:border-white/20 transition-all group text-left">
                  <div className="p-2 bg-white/10 rounded-lg mr-4">
                    <Settings className="w-5 h-5 text-slate-300" />
                  </div>
                  <div className="flex-1">
                    <h4 className="text-slate-200 font-medium group-hover:text-white transition-colors">Sửa lỗi phân tích</h4>
                    <p className="text-xs text-slate-400 mt-0.5">89 lỗi cần xử lý</p>
                  </div>
                  <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-white group-hover:translate-x-1 transition-all" />
                </button>
              </CardContent>
            </Card>
          </div>

        </div>
      </main>
    </div>
  );
}
