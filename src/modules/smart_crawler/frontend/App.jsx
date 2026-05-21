import React, { useState, useEffect } from 'react';
import {
    Globe, Database, Zap, Activity, Shield, Layers,
    Play, RotateCcw, Search, Filter, ChevronRight, CheckCircle,
    AlertCircle, Loader2, ChevronDown, FileText, HardDrive, Cpu
} from 'lucide-react';

// --- Components ---

const StatCard = ({ title, value, icon: Icon, trend, color }) => (
    <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl flex items-center gap-4 hover:border-indigo-500/50 transition-all group overflow-hidden relative">
        <div className={`p-4 rounded-xl ${color} bg-opacity-10 group-hover:scale-110 transition-transform`}>
            <Icon className={`w-8 h-8 ${color.replace('bg-', 'text-')}`} />
        </div>
        <div>
            <p className="text-slate-400 text-sm font-medium">{title}</p>
            <div className="flex items-baseline gap-2">
                <h3 className="text-3xl font-bold text-white tracking-tight">{value}</h3>
                {trend && <span className="text-xs text-emerald-400 font-bold">{trend}</span>}
            </div>
        </div>
        <div className={`absolute -right-4 -bottom-4 w-24 h-24 ${color} opacity-5 rounded-full blur-3xl`}></div>
    </div>
);

const Badge = ({ children, variant = 'info' }) => {
    const styles = {
        info: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
        success: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
        warning: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
        error: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
        purple: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    };
    return (
        <span className={`px-2 py-0.5 rounded-full text-xs font-bold border ${styles[variant]}`}>
            {children}
        </span>
    );
};

// --- Page: Dashboard ---

const DashboardPage = ({ stats }) => (
    <div className="space-y-8 animate-in fade-in duration-700">
        <div>
            <h1 className="text-4xl font-extrabold text-white tracking-tight mb-2">Platform Overview</h1>
            <p className="text-slate-400">Real-time performance metrics and system health monitoring.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard title="Total Domains" value={stats.totalDomains} icon={Globe} color="bg-indigo-500" trend="+12%" />
            <StatCard title="Extraction Rate" value={stats.extractionRate} icon={Zap} color="bg-emerald-500" />
            <StatCard title="Total Products" value={stats.totalProducts} icon={Layers} color="bg-purple-500" trend="+2.4k" />
            <StatCard title="Fallback Rate" value={stats.fallbackRate} icon={Shield} color="bg-amber-500" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-10">
            {/* Activity Timeline */}
            <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl relative overflow-hidden">
                <div className="flex justify-between items-center mb-8 relative z-10">
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <Activity className="text-indigo-500" />
                        Active Processes
                    </h2>
                    <button className="text-sm text-indigo-400 font-bold hover:text-indigo-300 transition-colors">View all logs</button>
                </div>
                <div className="space-y-6 relative z-10">
                    {[1, 2, 3].map((i) => (
                        <div key={i} className="flex gap-4 p-4 rounded-2xl hover:bg-slate-800/50 transition-all border border-transparent hover:border-slate-700 group">
                            <div className="mt-1 h-2 w-2 rounded-full bg-indigo-500 ring-4 ring-indigo-500/10 active:scale-150 transition-transform"></div>
                            <div>
                                <p className="text-slate-200 font-bold group-hover:text-white transition-colors">Crawl job completed for ruoutot.net</p>
                                <p className="text-slate-500 text-sm">Processed 120 pages • 1,420 products extracted • 1.2s avg latency</p>
                                <div className="mt-3 flex gap-2">
                                    <Badge variant="success">STABLE</Badge>
                                    <Badge variant="info">DIRECT</Badge>
                                </div>
                            </div>
                            <p className="ml-auto text-slate-500 text-xs font-mono">2h ago</p>
                        </div>
                    ))}
                </div>
                <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-indigo-500 opacity-5 rounded-full blur-[120px] -mr-64 -mt-64"></div>
            </div>

            {/* System Health */}
            <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl relative overflow-hidden">
                <h2 className="text-xl font-bold text-white mb-8">Node Stats</h2>
                <div className="space-y-8">
                    <div>
                        <div className="flex justify-between mb-2">
                            <span className="text-sm text-slate-400 font-bold">API Performance</span>
                            <span className="text-sm text-white font-bold">94%</span>
                        </div>
                        <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                            <div className="h-full w-[94%] bg-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.5)]"></div>
                        </div>
                    </div>
                    <div>
                        <div className="flex justify-between mb-2">
                            <span className="text-sm text-slate-400 font-bold">LLM Buffer</span>
                            <span className="text-sm text-white font-bold">12/50 req/min</span>
                        </div>
                        <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                            <div className="h-full w-[24%] bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]"></div>
                        </div>
                    </div>
                    <div className="pt-6 border-t border-slate-800">
                        <div className="flex items-center gap-4 mb-4">
                            <div className="h-10 w-10 rounded-full bg-indigo-500 bg-opacity-10 flex items-center justify-center text-indigo-500">
                                <Cpu />
                            </div>
                            <div>
                                <p className="text-white font-bold text-sm">Gemini Flash 2.5</p>
                                <p className="text-slate-500 text-xs uppercase tracking-widest font-black">ACTIVE ENGINE</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
);

// --- Page: Domain Manager ---

const DomainManagerPage = ({ domains, onRunCrawl }) => (
    <div className="space-y-8 animate-in slide-in-from-bottom duration-700">
        <div className="flex justify-between items-end">
            <div>
                <h1 className="text-4xl font-extrabold text-white tracking-tight mb-2">Domain Intelligence</h1>
                <p className="text-slate-400">Manage crawling strategies and analyzer configurations.</p>
            </div>
            <button className="bg-indigo-600 hover:bg-indigo-500 text-white px-8 py-3 rounded-2xl font-black tracking-tight shadow-xl shadow-indigo-500/20 transition-all flex items-center gap-2">
                <Play fill="white" size={18} />
                ADD NEW DOMAIN
            </button>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-[32px] overflow-hidden shadow-2xl">
            <div className="p-8 border-b border-slate-800 flex justify-between items-center bg-slate-900/50 backdrop-blur-xl">
                <div className="relative flex-1 max-w-md">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 w-5 h-5" />
                    <input
                        type="text"
                        placeholder="Search domains..."
                        className="w-full bg-slate-800 border-none rounded-2xl py-3 pl-12 pr-4 text-white placeholder-slate-500 focus:ring-2 focus:ring-indigo-500 transition-all"
                    />
                </div>
                <div className="flex gap-4">
                    <button className="p-3 bg-slate-800 rounded-xl text-slate-400 hover:text-white transition-all">
                        <Filter size={20} />
                    </button>
                </div>
            </div>

            <table className="w-full text-left border-collapse">
                <thead>
                    <tr className="bg-slate-950/50 text-slate-500 text-xs font-black uppercase tracking-widest">
                        <th className="px-8 py-6">Domain</th>
                        <th className="px-8 py-6">Intelligence</th>
                        <th className="px-8 py-6">Last Scanned</th>
                        <th className="px-8 py-6 text-right">Actions</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                    {domains.map((domain, i) => (
                        <tr key={i} className="hover:bg-slate-800/30 transition-colors group">
                            <td className="px-8 py-6">
                                <div className="flex items-center gap-4">
                                    <div className="h-12 w-12 rounded-2xl bg-slate-800 flex items-center justify-center text-indigo-400 font-bold group-hover:bg-indigo-500 group-hover:text-white transition-all">
                                        {domain.name.charAt(0).toUpperCase()}
                                    </div>
                                    <div>
                                        <p className="text-white font-bold text-lg">{domain.name}</p>
                                        <p className="text-slate-500 text-sm">v2.1 extraction template</p>
                                    </div>
                                </div>
                            </td>
                            <td className="px-8 py-6">
                                <div className="flex gap-2">
                                    <Badge variant={domain.strategy === 'DIRECT' ? 'success' : 'purple'}>{domain.strategy}</Badge>
                                    {domain.antiBot && <Badge variant="error">ANTI-BOT</Badge>}
                                    {domain.hasAPI && <Badge variant="info">API</Badge>}
                                </div>
                            </td>
                            <td className="px-8 py-6">
                                <div className="text-slate-300 font-medium">Oct 24, 2026</div>
                                <div className="text-slate-500 text-xs uppercase font-black">11:45 AM</div>
                            </td>
                            <td className="px-8 py-6 text-right">
                                <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button
                                        onClick={() => onRunCrawl(domain.name)}
                                        className="p-3 bg-indigo-500 rounded-xl text-white hover:scale-110 transition-transform shadow-lg shadow-indigo-500/20"
                                    >
                                        <Play fill="white" size={16} />
                                    </button>
                                    <button className="p-3 bg-slate-800 rounded-xl text-slate-400 hover:text-white transition-transform">
                                        <RotateCcw size={16} />
                                    </button>
                                    <button className="p-3 bg-slate-800 rounded-xl text-slate-400 hover:text-white transition-transform">
                                        <ChevronRight size={16} />
                                    </button>
                                </div>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    </div>
);

// --- Page: Lakehouse Browser ---

const LakehouseBrowserPage = ({ categories, onProcess }) => {
    const [selectedCat, setSelectedCat] = useState(null);
    const [selectedDom, setSelectedDom] = useState(null);

    const mockDomains = { 'ruou-bia': ['ruoutot.net', 'winemart.vn'], 'thuoc-la': ['thuocla.com'] };

    return (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 animate-in zoom-in-95 duration-500">
            {/* Sidebar: Categories */}
            <div className="lg:col-span-1 space-y-4">
                <h2 className="text-xs font-black text-slate-500 uppercase tracking-widest px-4">Categories</h2>
                <div className="space-y-1">
                    {categories.map((cat) => (
                        <button
                            key={cat}
                            onClick={() => { setSelectedCat(cat); setSelectedDom(null); }}
                            className={`w-full text-left px-5 py-4 rounded-2xl flex items-center justify-between group transition-all ${selectedCat === cat ? 'bg-indigo-600 text-white shadow-xl shadow-indigo-600/20' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                                }`}
                        >
                            <div className="flex items-center gap-3 font-bold">
                                <HardDrive className={selectedCat === cat ? 'text-indigo-200' : 'text-slate-600 group-hover:text-indigo-400'} />
                                {cat.replace('-', ' ').toUpperCase()}
                            </div>
                            <ChevronRight size={16} className={selectedCat === cat ? 'opacity-100' : 'opacity-0'} />
                        </button>
                    ))}
                </div>
            </div>

            {/* Main: Domain Selection & Files */}
            <div className="lg:col-span-3 space-y-8">
                {!selectedCat ? (
                    <div className="h-[500px] flex flex-col items-center justify-center text-center space-y-4 border-2 border-dashed border-slate-800 rounded-[48px]">
                        <div className="p-8 bg-slate-800 rounded-full text-slate-600">
                            <Database size={64} />
                        </div>
                        <p className="text-slate-400 font-bold max-w-xs">Select a category from the Lakehouse to start batch processing.</p>
                    </div>
                ) : (
                    <div className="space-y-8 animate-in slide-in-from-right duration-500">
                        <div className="bg-slate-900 border border-slate-800 p-8 rounded-[48px]">
                            <h3 className="text-xl font-bold text-white mb-6">Domains in {selectedCat}</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {(mockDomains[selectedCat] || []).map(dom => (
                                    <div
                                        key={dom}
                                        onClick={() => setSelectedDom(dom)}
                                        className={`p-6 rounded-[32px] border-2 cursor-pointer transition-all flex items-center justify-between group ${selectedDom === dom ? 'bg-indigo-600 border-indigo-400' : 'bg-slate-800 border-transparent hover:border-slate-600'
                                            }`}
                                    >
                                        <div className="flex items-center gap-4">
                                            <div className="h-12 w-12 rounded-2xl bg-white/10 flex items-center justify-center">
                                                <Globe className="text-white" />
                                            </div>
                                            <div>
                                                <p className="text-white font-bold">{dom}</p>
                                                <p className="text-white/50 text-xs">420 HTML files discovered</p>
                                            </div>
                                        </div>
                                        <div className={`p-2 rounded-xl transition-all ${selectedDom === dom ? 'bg-white text-indigo-600' : 'bg-slate-700 text-slate-400 group-hover:text-white'}`}>
                                            <CheckCircle size={20} />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {selectedDom && (
                            <div className="bg-slate-900 border border-slate-800 p-10 rounded-[48px] animate-in slide-in-from-bottom duration-500">
                                <div className="flex justify-between items-center mb-8">
                                    <div>
                                        <h3 className="text-2xl font-black text-white">Batch Processor</h3>
                                        <p className="text-slate-400">Ready to ingest <span className="text-indigo-400 font-bold">420 files</span> using Adaptive AI.</p>
                                    </div>
                                    <button
                                        onClick={() => onProcess(selectedCat, selectedDom)}
                                        className="px-10 py-5 bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white rounded-[24px] font-black tracking-widest shadow-2xl shadow-indigo-500/50 transition-all flex items-center gap-4"
                                    >
                                        <Zap fill="white" size={24} />
                                        START ETL JOB
                                    </button>
                                </div>

                                <div className="space-y-3">
                                    {[1, 2, 3].map(i => (
                                        <div key={i} className="flex items-center justify-between p-4 bg-slate-950/50 rounded-2xl border border-slate-800 group hover:border-indigo-500/30 transition-all">
                                            <div className="flex items-center gap-4">
                                                <FileText className="text-slate-600 group-hover:text-indigo-400 transition-colors" />
                                                <span className="text-slate-300 font-medium">product_page_00{i}.html</span>
                                            </div>
                                            <Badge>PENDING</Badge>
                                        </div>
                                    ))}
                                    <div className="pt-4 text-center">
                                        <button className="text-slate-500 font-bold text-sm hover:text-slate-300">View all 420 files...</button>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

// --- App Root ---

export default function SmartPlatform() {
    const [activeTab, setActiveTab] = useState('dashboard');
    const [loading, setLoading] = useState(false);

    const menu = [
        { id: 'dashboard', label: 'DASHBOARD', icon: Activity },
        { id: 'domains', label: 'DOMAINS', icon: Globe },
        { id: 'lakehouse', label: 'LAKEHOUSE', icon: Database },
    ];

    const mockData = {
        stats: { totalDomains: 24, extractionRate: '98.2%', totalProducts: '14,204', fallbackRate: '4.2%' },
        domains: [
            { name: 'ruoutot.net', strategy: 'DIRECT', antiBot: false, hasAPI: true },
            { name: 'winemart.vn', strategy: 'MHTML', antiBot: true, hasAPI: false },
            { name: 'tiki.vn', strategy: 'MHTML', antiBot: true, hasAPI: true },
        ],
        categories: ['ruou-bia', 'thuoc-la', 'sua']
    };

    return (
        <div className="min-h-screen bg-slate-950 text-slate-200 font-['Inter',sans-serif] selection:bg-indigo-500 selection:text-white">
            {/* Sidebar */}
            <aside className="fixed left-0 top-0 bottom-0 w-80 bg-slate-950 border-r border-slate-900 flex flex-col p-8 z-50">
                <div className="flex items-center gap-4 mb-16 px-4">
                    <div className="h-12 w-12 bg-indigo-600 rounded-[18px] shadow-2xl shadow-indigo-600/50 flex items-center justify-center relative overflow-hidden group">
                        <Zap fill="white" className="w-6 h-6 relative z-10 group-hover:scale-125 transition-transform" />
                        <div className="absolute inset-0 bg-white opacity-0 group-hover:opacity-20 transition-opacity"></div>
                    </div>
                    <div>
                        <h1 className="text-xl font-black text-white tracking-widest uppercase">Smart Crawler</h1>
                        <p className="text-[10px] text-indigo-400 font-black tracking-[0.2em] -mt-1">MANAGEMENT PRO</p>
                    </div>
                </div>

                <nav className="flex-1 space-y-3">
                    {menu.map((item) => (
                        <button
                            key={item.id}
                            onClick={() => setActiveTab(item.id)}
                            className={`w-full flex items-center gap-4 px-6 py-4 rounded-2xl font-black tracking-tight transition-all relative ${activeTab === item.id ? 'text-white bg-slate-900 shadow-xl' : 'text-slate-500 hover:text-slate-300 hover:bg-slate-900/50'
                                }`}
                        >
                            {activeTab === item.id && (
                                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1.5 h-8 bg-indigo-600 rounded-r-full shadow-[0_0_20px_rgba(79,70,229,0.8)]"></div>
                            )}
                            <item.icon size={22} className={activeTab === item.id ? 'text-indigo-500' : ''} />
                            {item.label}
                        </button>
                    ))}
                </nav>

                <div className="mt-auto p-6 bg-slate-900/50 rounded-3xl border border-slate-800 border-dashed">
                    <p className="text-[10px] text-slate-500 font-black tracking-widest mb-4">SYSTEM STATUS</p>
                    <div className="flex items-center gap-2 mb-2">
                        <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></div>
                        <span className="text-sm font-bold text-white">All systems operational</span>
                    </div>
                    <p className="text-xs text-slate-500">v2.4.12 stable release</p>
                </div>
            </aside>

            {/* Header & Content */}
            <main className="pl-80 min-h-screen">
                <header className="h-24 px-12 flex items-center justify-between sticky top-0 bg-slate-950/80 backdrop-blur-3xl z-40">
                    <div className="flex items-center gap-2 text-sm">
                        <span className="text-slate-500 font-medium">Home</span>
                        <ChevronRight className="text-slate-700 w-4 h-4" />
                        <span className="text-white font-bold capitalize">{activeTab}</span>
                    </div>
                    <div className="flex items-center gap-6">
                        <div className="h-10 w-px bg-slate-800"></div>
                        <div className="flex items-center gap-4">
                            <div className="text-right hidden sm:block">
                                <p className="text-sm text-white font-bold">Admin User</p>
                                <p className="text-[10px] text-indigo-400 font-extrabold uppercase tracking-widest">Superpower mode</p>
                            </div>
                            <div className="h-12 w-12 rounded-2xl bg-indigo-500/10 text-indigo-500 flex items-center justify-center font-black border border-indigo-500/20 shadow-xl shadow-indigo-500/10">
                                AD
                            </div>
                        </div>
                    </div>
                </header>

                <div className="p-12 pb-32 max-w-7xl mx-auto">
                    {activeTab === 'dashboard' && <DashboardPage stats={mockData.stats} />}
                    {activeTab === 'domains' && (
                        <DomainManagerPage
                            domains={mockData.domains}
                            onRunCrawl={(id) => alert('Starting crawl for ' + id)}
                        />
                    )}
                    {activeTab === 'lakehouse' && (
                        <LakehouseBrowserPage
                            categories={mockData.categories}
                            onProcess={(cat, dom) => alert(`Processing batch: ${cat}/${dom}`)}
                        />
                    )}
                </div>
            </main>

            {loading && (
                <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-[100] flex items-center justify-center">
                    <div className="flex flex-col items-center gap-4">
                        <Loader2 className="w-16 h-16 text-indigo-500 animate-spin" />
                        <p className="text-white font-black tracking-widest uppercase">Processing Session...</p>
                    </div>
                </div>
            )}
        </div>
    );
}
