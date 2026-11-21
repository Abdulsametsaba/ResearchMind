import React from 'react';
import { 
  Compass, 
  Activity, 
  FileText, 
  BarChart3, 
  Sparkles,
  Database,
  Cpu
} from 'lucide-react';
import { TabType } from '../../types/research';

interface SidebarProps {
  currentTab: TabType;
  onSelectTab: (tab: TabType) => void;
  isRunning: boolean;
  hasReport: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  isRunning,
  hasReport,
}) => {
  const navItems = [
    {
      id: 'dashboard' as TabType,
      label: 'Dashboard',
      sublabel: 'New Research & History',
      icon: Compass,
      badge: null,
    },
    {
      id: 'live' as TabType,
      label: 'Live Execution',
      sublabel: 'Live Agent Workflow',
      icon: Activity,
      badge: isRunning ? (
        <span className="flex h-2.5 w-2.5 relative">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500"></span>
        </span>
      ) : null,
    },
    {
      id: 'report' as TabType,
      label: 'Research Report',
      sublabel: 'Research Report & Export',
      icon: FileText,
      badge: hasReport ? (
        <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded">
          Ready
        </span>
      ) : null,
    },
    {
      id: 'metrics' as TabType,
      label: 'Quality & Metrics',
      sublabel: '7-Dimension Quality Metrics',
      icon: BarChart3,
      badge: null,
    },
  ];

  return (
    <aside className="w-72 bg-[#080c14] border-r border-slate-800/80 flex flex-col justify-between p-4 z-20 shrink-0">
      <div>
        {/* Logo & Header */}
        <div className="flex items-center gap-3 px-3 py-4 mb-6 border-b border-slate-800/60">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-cyan-500 via-sky-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Cpu className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-extrabold text-lg tracking-tight text-white font-mono">Research<span className="text-cyan-400">Mind</span></span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium">Autonomous Research Workspace</p>
          </div>
        </div>

        {/* Navigation Section */}
        <div className="space-y-1.5">
          <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider uppercase text-slate-400">
            Workspace
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-3 rounded-xl transition-all duration-200 text-left group ${
                  isActive
                    ? 'bg-slate-800/90 text-white shadow-md border border-cyan-500/30 glow-cyan'
                    : 'text-slate-300 hover:bg-slate-800/50 hover:text-slate-100'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`p-2 rounded-lg transition-colors ${
                      isActive
                        ? 'bg-cyan-500/20 text-cyan-300'
                        : 'bg-slate-800/60 text-slate-400 group-hover:text-slate-200'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold leading-none">{item.label}</div>
                    <div className="text-[11px] text-slate-400 mt-1 leading-none">{item.sublabel}</div>
                  </div>
                </div>
                {item.badge}
              </button>
            );
          })}
        </div>
      </div>

      {/* Footer Info Box */}
      <div className="bg-[#0c121e] border border-slate-800/80 rounded-xl p-3.5 space-y-2">
        <div className="flex items-center justify-between text-xs text-slate-300">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
            System Status
          </span>
          <span className="text-[10px] text-emerald-400/90 font-mono font-bold">ACTIVE</span>
        </div>
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span className="flex items-center gap-1.5">
            <Sparkles className="h-3 w-3 text-cyan-400" />
            Research Engine
          </span>
          <span className="text-[10px] text-cyan-400/80 font-mono">ONLINE</span>
        </div>
      </div>
    </aside>
  );
};
