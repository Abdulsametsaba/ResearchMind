/**
 * ResearchMind Frontend Types
 * FastAPI backend modelleriyle tam uyumlu tip tanımlamaları.
 */

export type TabType = 'dashboard' | 'live' | 'report' | 'metrics';

export type AgentStatus = 'waiting' | 'running' | 'completed' | 'failed';

export interface AgentNodeData {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  accentColor: string; // 'cyan' | 'purple' | 'amber' | 'emerald' | 'blue'
  iconName: string;
  description: string;
  activeCount?: number;
}

export interface ScopeGateResponse {
  status: 'out_of_scope' | 'needs_clarification';
  message: string;
  session_id: null;
  hint?: string | null;
}

export interface ResearchJobResponse {
  session_id: string;
  status: string;
  message: string;
  created_at: string;
}

export interface ResearchSessionSummary {
  session_id: string;
  query: string;
  status: 'pending' | 'running' | 'cancelling' | 'completed' | 'failed' | 'cancelled';
  is_active: boolean;
  iteration_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface ResearchStatusResponse {
  session_id: string;
  status: 'pending' | 'running' | 'cancelling' | 'completed' | 'failed' | 'cancelled';
  query: string;
  iteration_count: number;
  academic_sources_count: number;
  web_sources_count: number;
  claim_verifications_count: number;
  is_research_sufficient: boolean;
  created_at: string;
  completed_at: string | null;
  audit_log_count: number;
  has_report: boolean;
  agent_statuses: {
    planner: AgentStatus;
    paper_researcher: AgentStatus;
    web_researcher: AgentStatus;
    analysis_agent: AgentStatus;
    gap_reframer: AgentStatus;
    fact_checker: AgentStatus;
    report_agent: AgentStatus;
  };
  agent_events: Array<{
    sequence: number;
    agent_key: string;
    status: 'running' | 'completed' | 'failed';
    occurred_at: string;
  }>;
}

export interface ReportSectionSummary {
  heading: string;
  content_preview: string;
}

export interface ClaimVerificationSummary {
  claim_id: string;
  claim_text: string;
  verification_status: 'VERIFIED' | 'PARTIALLY_VERIFIED' | 'INSUFFICIENT_EVIDENCE' | 'CONTRADICTED' | 'NEEDS_VERIFICATION';
  confidence_score: number;
  source_reference: string;
  notes?: string | null;
}

export interface BibliographyEntry {
  index: string;
  citation: string;
}

export interface AcademicPaperDetail {
  paper_id: string;
  title: string;
  authors: string[];
  published_year?: string | null;
  url?: string | null;
  pdf_url?: string | null;
  abstract?: string | null;
  extracted_intel?: Record<string, any> | null;
  relevance_score?: number | null;
}

export interface WebSourceDetail {
  url: string;
  title: string;
  snippet?: string | null;
  relevance_score?: number | null;
  published_date?: string | null;
}

export interface ReportResponse {
  session_id: string;
  title: string;
  executive_summary: string;
  sections: Array<{ heading: string; content?: string; content_preview?: string }>;
  report_markdown?: string | null;
  comparative_analysis_markdown: string | null;
  verification_matrix_markdown: string | null;
  limitations_and_future_directions: string;
  bibliography: BibliographyEntry[];
  claim_verifications: ClaimVerificationSummary[];
  academic_papers?: AcademicPaperDetail[];
  web_sources?: WebSourceDetail[];
  total_sources: number;
  created_at: string;
}

export interface EvaluationMetrics {
  session_id: string;
  research_coverage_score: number;
  citation_accuracy_score: number;
  source_quality_score: number;
  factual_consistency_score: number;
  retrieval_recall: number;
  research_completion_rate: number;
  total_sources: number;
  total_claims_verified: number;
  iteration_count: number;
  overall_score: number;
}

export interface CancelResearchResponse {
  session_id: string;
  status: 'cancelling' | 'cancelled';
  message: string;
  cancelled_at: string;
}
