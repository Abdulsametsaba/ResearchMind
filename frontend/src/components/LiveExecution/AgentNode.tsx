import React from 'react';
import { 
  CheckCircle2, 
  Loader2, 
  Clock, 
  AlertCircle,
  Brain,
  ShieldCheck,
  FileSearch,
  Globe,
  Database,
  BarChart,
  Repeat,
  CheckSquare,
  BookOpen,
  FileText
} from 'lucide-react';
import { AgentStatus } from '../../types/research';

interface AgentNodeProps {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  accentColor: string; // 'cyan' | 'purple' | 'amber' | 'emerald' | 'blue' | 'indigo'
  iconName: string;
  countLabel?: string;
  x?: number;
  y?: number;
}

export const AgentNode: React.FC<AgentNodeProps> = ({
  name,
  role,
  status,
  accentColor,
  iconName,
  countLabel,
}) => {
  const getIcon = () => {
    switch (iconName) {
      case 'shield': return <ShieldCheck className="h-4 w-4" />;
      case 'brain': return <Brain className="h-4 w-4" />;
      case 'database': return <Database className="h-4 w-4" />;
      case 'paper': return <FileSearch className="h-4 w-4" />;
      case 'web': return <Globe className="h-4 w-4" />;
      case 'analysis': return <BarChart className="h-4 w-4" />;
      case 'loop': return <Repeat className="h-4 w-4" />;
      case 'fact': return <CheckSquare className="h-4 w-4" />;
      case 'narrative': return <BookOpen className="h-4 w-4" />;
      case 'report': return <FileText className="h-4 w-4" />;
      default: return <Brain className="h-4 w-4" />;
    }
  };

  // Color styles mapping based on agent role
  const getColorClass = () => {
    if (status === 'running') {
      switch (accentColor) {
        case 'cyan': return 'border-cyan-400 bg-cyan-950/40 text-cyan-200 glow-cyan ring-1 ring-cyan-400/50';
        case 'purple': return 'border-purple-400 bg-purple-950/40 text-purple-200 glow-purple ring-1 ring-purple-400/50';
        case 'amber': return 'border-amber-400 bg-amber-950/40 text-amber-200 glow-amber ring-1 ring-amber-400/50';
        case 'emerald': return 'border-emerald-400 bg-emerald-950/40 text-emerald-200 glow-emerald ring-1 ring-emerald-400/50';
        case 'indigo': return 'border-indigo-400 bg-indigo-950/40 text-indigo-200 glow-purple ring-1 ring-indigo-400/50';
        default: return 'border-sky-400 bg-sky-950/40 text-sky-200 glow-cyan ring-1 ring-sky-400/50';
      }
    }
    if (status === 'completed') {
      return 'border-emerald-500/60 bg-[#0c1619] text-emerald-300 shadow-lg shadow-emerald-950/20';
    }
    if (status === 'failed') {
      return 'border-red-500/60 bg-red-950/20 text-red-300';
    }
    // Waiting
    return 'border-slate-800/80 bg-[#0d131f]/60 text-slate-400 opacity-60 hover:opacity-80';
  };

  const getStatusBadge = () => {
    switch (status) {
      case 'running':
        return (
          <span className="flex items-center gap-1 text-[10px] font-bold text-cyan-300 bg-cyan-950/80 border border-cyan-500/40 px-2 py-0.5 rounded-full animate-pulse">
            <Loader2 className="h-2.5 w-2.5 animate-spin" /> Running
          </span>
        );
      case 'completed':
        return (
          <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-300 bg-emerald-950/80 border border-emerald-500/40 px-2 py-0.5 rounded-full">
            <CheckCircle2 className="h-2.5 w-2.5" /> Completed
          </span>
        );
      case 'failed':
        return (
          <span className="flex items-center gap-1 text-[10px] font-bold text-red-300 bg-red-950/80 border border-red-500/40 px-2 py-0.5 rounded-full">
            <AlertCircle className="h-2.5 w-2.5" /> Failed
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1 text-[10px] font-medium text-slate-400 bg-slate-900 border border-slate-800 px-2 py-0.5 rounded-full">
            <Clock className="h-2.5 w-2.5" /> Waiting
          </span>
        );
    }
  };

  return (
    <div
      className={`relative w-64 rounded-2xl p-4 border transition-all duration-300 select-none shadow-xl ${getColorClass()}`}
    >
      {/* Top Header */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <div className={`p-2 rounded-xl transition-all ${
            status === 'running' ? 'bg-cyan-500/20 text-cyan-300 scale-110' : 'bg-slate-800/60 text-slate-300'
          }`}>
            {getIcon()}
          </div>
          <div>
            <h4 className="text-sm font-bold tracking-tight text-white leading-none">
              {name}
            </h4>
            <span className="text-[10px] text-slate-400 font-medium leading-none block mt-1">
              {role}
            </span>
          </div>
        </div>
      </div>

      {/* Footer with status pill & optional count */}
      <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center justify-between text-xs">
        {getStatusBadge()}
        {countLabel && (
          <span className="text-[11px] font-mono text-cyan-300/90 font-semibold bg-slate-900/80 px-2 py-0.5 rounded border border-slate-800">
            {countLabel}
          </span>
        )}
      </div>
    </div>
  );
};
