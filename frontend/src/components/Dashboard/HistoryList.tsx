import React from "react";
import {
  CheckCircle2,
  Clock,
  XCircle,
  AlertTriangle,
  ArrowUpRight,
  RotateCw,
  Search,
} from "lucide-react";
import { ResearchSessionSummary } from "../../types/research";

interface HistoryListProps {
  sessions: ResearchSessionSummary[];
  onSelectSession: (sessionId: string) => void;
  onRefresh: () => void;
  isLoading: boolean;
  isAnyResearchRunning: boolean;
}

export const HistoryList: React.FC<HistoryListProps> = ({
  sessions,
  onSelectSession,
  onRefresh,
  isLoading,
  isAnyResearchRunning,
}) => {
  const getStatusBadge = (status: string, isActive: boolean) => {
    if (isActive || status === "running" || status === "cancelling") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-ping" />
          {status === "cancelling" ? "Cancelling" : "In progress"}
        </span>
      );
    }
    switch (status) {
      case "completed":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
            <CheckCircle2 className="h-3 w-3" /> Completed
          </span>
        );
      case "cancelled":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/30">
            <AlertTriangle className="h-3 w-3" /> Cancelled
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-red-500/10 text-red-300 border border-red-500/30">
            <XCircle className="h-3 w-3" /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-slate-800 text-slate-400">
            <Clock className="h-3 w-3" /> Queued
          </span>
        );
    }
  };

  const formatDate = (isoString: string | null) => {
    if (!isoString) return "-";
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString("en-US", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="w-full bg-[#0c121e] border border-slate-800 rounded-3xl p-6 space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
        <div>
          <h3 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
            <span>Research History</span>
            <span className="px-2 py-0.5 text-xs bg-slate-800 text-slate-300 font-mono rounded-full">
              {sessions.length}
            </span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Archive of completed and in-progress research
          </p>
        </div>

        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="p-2 text-slate-400 hover:text-white bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 rounded-xl transition-all"
          title="Refresh"
        >
          <RotateCw
            className={`h-4 w-4 ${isLoading ? "animate-spin text-cyan-400" : ""}`}
          />
        </button>
      </div>

      {sessions.length === 0 ? (
        <div className="py-12 text-center text-slate-400 space-y-3">
          <Search className="h-8 w-8 mx-auto text-slate-500 stroke-1" />
          <p className="text-sm">No research sessions yet.</p>
          <p className="text-xs text-slate-500">
            Start your first deep research session using the form above.
          </p>
        </div>
      ) : (
        <div className="divide-y divide-slate-800/60 overflow-hidden">
          {sessions.map((session) => {
            const isRunning =
              session.is_active ||
              session.status === "running" ||
              session.status === "cancelling";
            const isCompleted = session.status === "completed";

            // Çalışan araştırma varsa geçmiş raporlar açılamaz.
            // Canlı izleme butonu ise aktif araştırma için kullanılabilir.
            const canViewReport = isCompleted && !isAnyResearchRunning;
            const isClickable = isRunning || canViewReport;

            return (
              <div
                key={session.session_id}
                onClick={() => {
                  if (isClickable) {
                    onSelectSession(session.session_id);
                  }
                }}
                className={`py-3.5 px-3 -mx-3 rounded-xl transition-colors flex items-center justify-between gap-4 ${
                  isClickable
                    ? "hover:bg-slate-800/40 cursor-pointer group"
                    : "opacity-75 cursor-default"
                }`}
              >
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    {getStatusBadge(session.status, session.is_active)}
                    <span className="text-[11px] text-slate-400 font-mono">
                      {formatDate(session.created_at)}
                    </span>
                    {session.iteration_count > 0 && (
                      <span className="text-[10px] font-medium text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/60">
                        {session.iteration_count} iterations
                      </span>
                    )}
                  </div>
                  <p
                    className={`text-sm font-medium line-clamp-1 ${isClickable ? "text-slate-200 group-hover:text-cyan-300" : "text-slate-400"}`}
                  >
                    {session.query}
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {isRunning ? (
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 text-xs font-semibold">
                      <span>View Live</span>
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </div>
                  ) : isCompleted ? (
                    <div
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-colors text-xs font-semibold ${
                        canViewReport
                          ? "bg-slate-800 group-hover:bg-cyan-500/20 text-slate-300 group-hover:text-cyan-300 border-slate-700/60 cursor-pointer"
                          : "bg-slate-800/50 text-slate-500 border-slate-800 cursor-not-allowed opacity-50"
                      }`}
                    >
                      <span>
                        {canViewReport
                          ? "View Report"
                          : "Research in Progress"}
                      </span>
                      {canViewReport && (
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      )}
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
