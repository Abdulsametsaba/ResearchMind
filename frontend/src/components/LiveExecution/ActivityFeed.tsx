import React, { useState } from "react";
import {
  Terminal,
  ShieldAlert,
  CheckCircle2,
  Clock,
  ChevronLeft,
  ChevronRight,
  X,
} from "lucide-react";

interface ActivityFeedProps {
  logs: string[];
  isRunning: boolean;
  onCancel: () => void;
  isCancelling: boolean;
  isOpen?: boolean;
  onToggle?: () => void;
}

export const ActivityFeed: React.FC<ActivityFeedProps> = ({
  logs,
  isRunning,
  onCancel,
  isCancelling,
  isOpen: controlledIsOpen,
  onToggle: controlledOnToggle,
}) => {
  // Eğer parent prop vermezse kendi state'ini kullanır (varsayılan: kapalı)
  const [internalIsOpen, setInternalIsOpen] = useState(false);
  const isOpen =
    controlledIsOpen !== undefined ? controlledIsOpen : internalIsOpen;
  const toggleOpen =
    controlledOnToggle || (() => setInternalIsOpen(!internalIsOpen));

  // 1. KAPALI (COLLAPSED) DURUM: Sadece dar başlık çubuğu görünür
  if (!isOpen) {
    return (
      <div
        onClick={toggleOpen}
        className="w-12 sm:w-14 bg-[#0c121e] border border-slate-800 hover:border-cyan-500/50 rounded-3xl p-3 flex flex-col items-center justify-between shrink-0 h-full min-h-[580px] max-h-[640px] cursor-pointer group transition-all duration-300 shadow-xl hover:shadow-cyan-950/20 select-none"
        title="Click to open the activity log"
      >
        {/* Üst İkon & Açma Oku */}
        <div className="flex flex-col items-center gap-2 pt-2">
          <div className="p-2 rounded-xl bg-slate-800/80 group-hover:bg-cyan-500/20 text-slate-300 group-hover:text-cyan-300 transition-colors">
            <Terminal className="h-4 w-4" />
          </div>
          <ChevronLeft className="h-4 w-4 text-slate-500 group-hover:text-cyan-400 group-hover:-translate-x-0.5 transition-transform" />
        </div>

        {/* Dikey Yazı (Laptop ekranlarında minimum yer kaplar) */}
        <div className="flex items-center justify-center [writing-mode:vertical-rl] rotate-180 select-none py-6">
          <span className="text-xs font-bold text-slate-400 group-hover:text-cyan-300 tracking-widest uppercase font-mono transition-colors">
            Activity Log
          </span>
        </div>

        {/* Alt Olay Sayacı Rozeti */}
        <div className="pb-2">
          <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-slate-800/90 group-hover:bg-cyan-950 text-slate-400 group-hover:text-cyan-300 border border-slate-700/80 group-hover:border-cyan-800/60 rounded-full transition-colors shadow-sm">
            {logs.length}
          </span>
        </div>
      </div>
    );
  }

  // 2. AÇIK (EXPANDED) DURUM: Tam detaylı log paneli
  return (
    <div className="w-full lg:w-80 xl:w-96 bg-[#0c121e] border border-slate-800 rounded-3xl p-5 flex flex-col justify-between shrink-0 h-full min-h-[580px] max-h-[640px] shadow-2xl transition-all duration-300 animate-in fade-in zoom-in-95 duration-200">
      <div>
        {/* Başlık ve Kapatma Butonu */}
        <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-cyan-400" />
            <h4 className="text-sm font-bold text-white tracking-tight">
              Activity Log
            </h4>
            <span className="text-[10px] font-mono bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
              {logs.length} events
            </span>
          </div>

          <button
            onClick={toggleOpen}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white bg-slate-800/80 hover:bg-slate-700 border border-slate-700/60 transition-colors flex items-center gap-1 text-[11px] font-medium"
            title="Collapse activity log"
          >
            <span>Collapse</span>
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Kaydırılabilir Olay Günlüğü */}
        <div className="space-y-2.5 overflow-y-auto max-h-[460px] pr-1 font-mono text-xs text-slate-300 custom-scrollbar">
          {logs.length === 0 ? (
            <div className="py-16 text-center text-slate-400 space-y-2">
              <Clock className="h-6 w-6 mx-auto text-slate-500" />
              <p className="text-xs">Waiting for activity...</p>
              <p className="text-[11px] text-slate-400">
                Agent activity will appear here once research starts.
              </p>
            </div>
          ) : (
            logs.map((log, index) => {
              const isSuccess =
                log.includes("successfully") ||
                log.includes("completed") ||
                log.includes("ready");
              const isError =
                log.includes("error") ||
                log.includes("failed") ||
                log.includes("cancel");
              return (
                <div
                  key={index}
                  className="p-2.5 rounded-xl bg-[#080d16] border border-slate-800/80 leading-relaxed text-[11px]"
                >
                  <div className="flex items-start gap-2">
                    {isSuccess ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    ) : isError ? (
                      <span className="h-1.5 w-1.5 rounded-full bg-red-400 shrink-0 mt-1.5" />
                    ) : (
                      <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 shrink-0 mt-1.5" />
                    )}
                    <span
                      className={
                        isError
                          ? "text-red-300"
                          : isSuccess
                            ? "text-emerald-300"
                            : "text-slate-200"
                      }
                    >
                      {log}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Acil İptal Butonu */}
      {isRunning && (
        <div className="pt-4 border-t border-slate-800 mt-4">
          <button
            onClick={onCancel}
            disabled={isCancelling}
            className="w-full py-2.5 px-4 rounded-xl text-xs font-semibold text-red-300 bg-red-950/40 hover:bg-red-900/50 border border-red-500/40 hover:border-red-400 transition-all flex items-center justify-center gap-2 shadow-lg shadow-red-950/30 active:scale-98"
          >
            <ShieldAlert className="h-4 w-4" />
            <span>
              {isCancelling ? "Cancelling..." : "Cancel Research"}
            </span>
          </button>
        </div>
      )}
    </div>
  );
};
