import React from 'react';
import { 
  ShieldCheck, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Award,
  Sparkles,
  Layers,
  Search,
  Quote
} from 'lucide-react';
import { EvaluationMetrics, ClaimVerificationSummary } from '../../types/research';

interface QualityMetricsProps {
  metrics: EvaluationMetrics | null;
  claims: ClaimVerificationSummary[];
}

export const QualityMetrics: React.FC<QualityMetricsProps> = ({ metrics, claims }) => {
  if (!metrics) {
    return (
      <div className="w-full max-w-5xl mx-auto py-16 text-center text-slate-400 space-y-3">
        <Sparkles className="h-8 w-8 mx-auto text-slate-500 stroke-1" />
        <p className="text-base font-medium">Metrics Not Available Yet</p>
        <p className="text-xs text-slate-500">Seven quality metrics will be calculated when research is complete.</p>
      </div>
    );
  }

  const metricCards = [
    {
      label: 'Research Coverage',
      score: metrics.research_coverage_score,
      desc: 'How thoroughly the planned research questions and dimensions were addressed.',
    },
    {
      label: 'Citation Accuracy',
      score: metrics.citation_accuracy_score,
      desc: 'How well report findings and claims are supported by their cited sources.',
    },
    {
      label: 'Source Quality',
      score: metrics.source_quality_score,
      desc: 'The quality of peer-reviewed research and authoritative web sources used.',
    },
    {
      label: 'Factual Consistency',
      score: metrics.factual_consistency_score,
      desc: 'The share of claims verified against evidence without contradictions.',
    },
    {
      label: 'Retrieval Recall',
      score: metrics.retrieval_recall,
      desc: 'How many critical references from the literature were retrieved.',
    },
    {
      label: 'Completion Rate',
      score: metrics.research_completion_rate,
      desc: 'Whether the full agent workflow completed as planned.',
    },
  ];

  // Helper for status badge in fact-checker matrix
  const getClaimBadge = (status: string) => {
    switch (status) {
      case 'VERIFIED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
            <CheckCircle2 className="h-3.5 w-3.5" /> Verified
          </span>
        );
      case 'CONTRADICTED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-red-500/10 text-red-300 border border-red-500/30">
            <XCircle className="h-3.5 w-3.5" /> Contradicted
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-300 border border-amber-500/30">
            <AlertTriangle className="h-3.5 w-3.5" /> Needs Verification
          </span>
        );
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-8 pb-16">
      {/* Overall Score Hero Card */}
      <div className="bg-[#0c121e] border border-slate-800 rounded-3xl p-8 shadow-2xl relative overflow-hidden flex flex-col sm:flex-row items-center justify-between gap-6">
        <div className="space-y-2 text-center sm:text-left z-10">
          <div className="flex items-center justify-center sm:justify-start gap-2 text-cyan-400 text-xs font-mono font-bold uppercase tracking-wider">
            <Award className="h-4 w-4" />
            <span>Research Evaluation & Quality Score</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Research Reliability Index
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 max-w-xl">
            A weighted assessment of claim verification, source quality, citation accuracy, and fact-check results.
          </p>
        </div>

        {/* Big Circular Score */}
        <div className="flex flex-col items-center justify-center p-6 rounded-2xl bg-gradient-to-br from-cyan-950/60 to-indigo-950/40 border border-cyan-500/40 shadow-xl shadow-cyan-950/30 glow-cyan shrink-0">
          <div className="text-4xl sm:text-5xl font-extrabold font-mono text-cyan-300 tracking-tight">
            {(metrics.overall_score * 100).toFixed(0)}<span className="text-xl text-cyan-400/70">%</span>
          </div>
          <span className="text-[11px] text-cyan-200/80 font-semibold tracking-wider uppercase mt-1">
            Overall Quality
          </span>
        </div>
      </div>

      {/* 6 Dimension Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {metricCards.map((card, idx) => {
          const pct = Math.round(card.score * 100);
          return (
            <div
              key={idx}
              className="bg-[#0c121e] border border-slate-800 rounded-2xl p-5 space-y-3 hover:border-slate-700 transition-colors shadow-lg"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-200 leading-snug">
                  {card.label}
                </span>
                <span className="text-sm font-extrabold font-mono text-cyan-400">
                  {pct}%
                </span>
              </div>

              {/* Progress Bar */}
              <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-indigo-500 rounded-full transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>

              <p className="text-[11px] text-slate-400 leading-relaxed font-normal">
                {card.desc}
              </p>
            </div>
          );
        })}
      </div>

      {/* Fact Checker Evidence Matrix */}
      <div className="bg-[#0c121e] border border-slate-800 rounded-3xl p-8 space-y-6 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white tracking-tight">
                Fact-Check Verification
              </h3>
              <p className="text-xs text-slate-400">
                Evidence excerpts from sources matched to key claims in the report.
              </p>
            </div>
          </div>
          <span className="text-xs font-mono text-slate-400 bg-slate-900 px-3 py-1 rounded-full border border-slate-800">
            {claims.length} Claims Reviewed
          </span>
        </div>

        {claims.length === 0 ? (
          <div className="py-8 text-center text-slate-400">
            <p className="text-sm">No detailed claim records are available for this session.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {claims.map((claim) => (
              <div
                key={claim.claim_id}
                className="bg-[#080d16] border border-slate-800/80 rounded-2xl p-5 space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800/40 font-bold">
                      {claim.claim_id}
                    </span>
                    <span className="text-xs text-slate-400 font-medium">
                      Source: {claim.source_reference}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {getClaimBadge(claim.verification_status)}
                    <span className="text-xs font-mono font-semibold text-slate-400">
                      Confidence: {(claim.confidence_score * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                <p className="text-sm font-semibold text-slate-200">
                  {claim.claim_text}
                </p>

                {/* Evidence Quote */}
                <div className="bg-[#0b101b] border-l-2 border-cyan-500 rounded-r-xl p-3 text-xs text-slate-300 italic flex items-start gap-2">
                  <Quote className="h-3.5 w-3.5 text-cyan-400 shrink-0 mt-0.5" />
                  <span>"{claim.source_reference}"</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
