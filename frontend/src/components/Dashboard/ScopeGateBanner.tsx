import React from 'react';
import { AlertCircle, HelpCircle, Lightbulb, ArrowRight, X } from 'lucide-react';
import { ScopeGateResponse } from '../../types/research';

interface ScopeGateBannerProps {
  data: ScopeGateResponse;
  onApplyHint?: (hintText: string) => void;
  onDismiss: () => void;
}

export const ScopeGateBanner: React.FC<ScopeGateBannerProps> = ({
  data,
  onApplyHint,
  onDismiss,
}) => {
  const isOutOfScope = data.status === 'out_of_scope';

  return (
    <div
      className={`relative w-full rounded-2xl p-5 border transition-all duration-300 shadow-xl ${
        isOutOfScope
          ? 'bg-gradient-to-r from-amber-950/40 via-amber-900/20 to-slate-900/60 border-amber-500/40 shadow-amber-500/10'
          : 'bg-gradient-to-r from-sky-950/40 via-indigo-900/20 to-slate-900/60 border-sky-500/40 shadow-sky-500/10'
      }`}
    >
      {/* Dismiss button */}
      <button
        onClick={onDismiss}
        className="absolute top-4 right-4 text-slate-400 hover:text-slate-200 p-1 rounded-lg hover:bg-slate-800/60 transition-colors"
      >
        <X className="h-4 w-4" />
      </button>

      <div className="flex items-start gap-4 pr-8">
        <div
          className={`p-2.5 rounded-xl shrink-0 mt-0.5 ${
            isOutOfScope
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
              : 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
          }`}
        >
          {isOutOfScope ? (
            <AlertCircle className="h-5 w-5" />
          ) : (
            <HelpCircle className="h-5 w-5" />
          )}
        </div>

        <div className="space-y-3 flex-1">
          <div>
            <div className="flex items-center gap-2">
              <span
                className={`text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                  isOutOfScope
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                    : 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                }`}
              >
                {isOutOfScope ? 'Out of Scope' : 'Clarification Needed'}
              </span>
              <span className="text-xs text-slate-400 font-medium">Research Scope Gate</span>
            </div>
            <p className="text-slate-200 text-sm mt-2 leading-relaxed">
              {data.message}
            </p>
          </div>

          {/* Hint suggestion block */}
          {data.hint && (
            <div className="bg-[#0b101b]/90 border border-slate-700/60 rounded-xl p-3.5 space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-amber-300">
                <Lightbulb className="h-3.5 w-3.5 text-amber-400" />
                <span>How to Refine This into a Research Question</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed font-mono">
                {data.hint}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
