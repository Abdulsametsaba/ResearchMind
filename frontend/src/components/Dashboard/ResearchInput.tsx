import React, { useState } from 'react';
import { Send, Sparkles, SlidersHorizontal, BookOpen, Layers } from 'lucide-react';

interface ResearchInputProps {
  onSubmit: (query: string, guidance?: string) => void;
  isLoading: boolean;
}

export const ResearchInput: React.FC<ResearchInputProps> = ({ onSubmit, isLoading }) => {
  const [query, setQuery] = useState('');
  const [guidance, setGuidance] = useState('');
  const [showGuidance, setShowGuidance] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;
    onSubmit(query.trim(), guidance.trim() || undefined);
  };

  const samplePresets = [
    {
      label: 'Vision-Language Models',
      query: 'Compare vision-language models developed between 2023 and 2026 (including LLaVA, Qwen-VL, and PaliGemma) in terms of architecture and benchmark performance.',
    },
    {
      label: 'Post-Quantum Cryptography',
      query: "Analyze post-quantum cryptography standards (NIST FIPS 203/204) and their security implications compared with classical cryptographic algorithms, using academic literature.",
    },
    {
      label: 'Medical Diffusion Models',
      query: 'Evaluate the accuracy of diffusion models (DDPM and Latent Diffusion) for generating synthetic MRI and CT data in medical imaging.',
    },
  ];

  return (
    <div className="w-full bg-[#0c121e] border border-slate-800 rounded-3xl p-6 shadow-2xl shadow-cyan-950/20 backdrop-blur-xl relative overflow-hidden">
      {/* Decorative gradient blur in background */}
      <div className="absolute -top-24 -right-24 w-72 h-72 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-24 -left-24 w-72 h-72 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

      <form onSubmit={handleSubmit} className="space-y-4 relative z-10">
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-cyan-400" />
              Research Question or Hypothesis
            </label>
            <span className="text-[11px] text-cyan-400/80 font-medium">
              Multi-Agent Deep Research
            </span>
          </div>

          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="For example: Compare the architecture and parameter efficiency of small language models released in 2024, such as Phi-3, Gemma 2, and Llama 3 8B..."
            rows={4}
            className="w-full bg-[#080d16] border border-slate-700/80 rounded-2xl p-4 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500/80 focus:ring-2 focus:ring-cyan-500/20 text-sm leading-relaxed transition-all resize-none font-medium"
          />
        </div>

        {/* Guidance Toggle & Textarea */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setShowGuidance(!showGuidance)}
              className="text-xs text-slate-400 hover:text-cyan-300 flex items-center gap-1.5 transition-colors font-medium py-1"
            >
              <SlidersHorizontal className="h-3.5 w-3.5 text-cyan-400" />
              <span>{showGuidance ? 'Hide Research Guidance' : '+ Add Research Guidance'}</span>
            </button>
            <span className="text-[11px] text-slate-400">Optional scope and focus</span>
          </div>

          {showGuidance && (
            <input
              type="text"
              value={guidance}
              onChange={(e) => setGuidance(e.target.value)}
              placeholder="For example: Focus on peer-reviewed publications since 2023 and emphasize benchmark tables..."
              className="w-full bg-[#080d16] border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/80 focus:ring-1 focus:ring-cyan-500/20 transition-all font-medium"
            />
          )}
        </div>

        {/* Preset suggestions & Action button */}
        <div className="pt-2 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] text-slate-400 font-semibold mr-1 flex items-center gap-1">
              <Layers className="h-3 w-3 text-cyan-400" /> Examples:
            </span>
            {samplePresets.map((preset, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setQuery(preset.query)}
                className="px-2.5 py-1 text-[11px] font-medium bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 hover:text-white border border-slate-700/60 rounded-lg transition-colors"
              >
                {preset.label}
              </button>
            ))}
          </div>

          <button
            type="submit"
            disabled={!query.trim() || isLoading}
            className={`px-6 py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all duration-200 shrink-0 ${
              !query.trim() || isLoading
                ? 'bg-slate-800 text-slate-400 cursor-not-allowed border border-slate-700/50'
                : 'bg-gradient-to-r from-cyan-500 via-sky-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white shadow-lg shadow-cyan-500/25 border border-cyan-400/40 glow-cyan active:scale-[0.98]'
            }`}
          >
            {isLoading ? (
              <>
                <Sparkles className="h-4 w-4 animate-spin text-cyan-200" />
                <span>Validating Research Scope...</span>
              </>
            ) : (
              <>
                <Send className="h-4 w-4 text-cyan-100" />
                <span>Start Deep Research</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
