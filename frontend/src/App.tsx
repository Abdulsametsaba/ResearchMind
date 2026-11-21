import React, { useState, useEffect, useRef } from "react";
import { ArrowUpRight } from "lucide-react";
import { Sidebar } from "./components/Navigation/Sidebar";
import { ResearchInput } from "./components/Dashboard/ResearchInput";
import { ScopeGateBanner } from "./components/Dashboard/ScopeGateBanner";
import { HistoryList } from "./components/Dashboard/HistoryList";
import { AgentCanvas } from "./components/LiveExecution/AgentCanvas";
import { ActivityFeed } from "./components/LiveExecution/ActivityFeed";
import { ReportViewer } from "./components/Report/ReportViewer";
import { QualityMetrics } from "./components/Metrics/QualityMetrics";

import {
  startResearch,
  getResearchStatus,
  listResearchSessions,
  getResearchReport,
  getResearchMetrics,
  cancelResearch,
} from "./api/client";

import {
  TabType,
  ScopeGateResponse,
  ResearchStatusResponse,
  ResearchSessionSummary,
  ReportResponse,
  EvaluationMetrics,
  AgentStatus,
} from "./types/research";

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<TabType>("dashboard");
  const [isLoading, setIsLoading] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);

  // Active Research State
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [statusData, setStatusData] = useState<ResearchStatusResponse | null>(
    null,
  );
  const [scopeGateFeedback, setScopeGateFeedback] =
    useState<ScopeGateResponse | null>(null);
  const [reportData, setReportData] = useState<ReportResponse | null>(null);
  const [metricsData, setMetricsData] = useState<EvaluationMetrics | null>(
    null,
  );
  const [sessionsList, setSessionsList] = useState<ResearchSessionSummary[]>(
    [],
  );
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [isLogOpen, setIsLogOpen] = useState(false);

  const pollingRef = useRef<number | null>(null);
  const seenAgentEventCountRef = useRef(0);

  // Load past sessions on mount
  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    setIsHistoryLoading(true);
    try {
      const data = await listResearchSessions(30);
      setSessionsList(data);
    } catch {
      // API offline or booting
    } finally {
      setIsHistoryLoading(false);
    }
  };

  // 1. Submit Query from Dashboard
  const handleStartResearch = async (query: string, guidance?: string) => {
    setIsLoading(true);
    setScopeGateFeedback(null);

    try {
      const result = await startResearch(query, guidance);

      if (!result.success) {
        // Scope Gate: OUT_OF_SCOPE veya NEEDS_CLARIFICATION
        // Stay on the dashboard and show the scope feedback.
        setScopeGateFeedback(result.data);
      } else {
        // IN_SCOPE: Araştırma başarıyla başlatıldı
        const session = result.data;
        setStatusData(null);
        seenAgentEventCountRef.current = 0;
        setActiveSessionId(session.session_id);
        setReportData(null);
        setMetricsData(null);
        setLiveLogs([
          `[${new Date().toLocaleTimeString()}] Session created: ${session.session_id.slice(0, 8)}`,
          `[${new Date().toLocaleTimeString()}] Scope check: IN_SCOPE (approved)`,
        ]);

        // Otomatik olarak Live Execution ekranına kaydır!
        setCurrentTab("live");

        // Canlı polling başlat
        startPolling(session.session_id);
      }
    } catch (err: any) {
      alert(err.message || "Could not start research.");
    } finally {
      setIsLoading(false);
      fetchHistory();
    }
  };

  // 2. Polling for Live Status
  const startPolling = (sessionId: string) => {
    if (pollingRef.current !== null) {
      clearTimeout(pollingRef.current);
    }

    const pollStatus = async () => {
      if (pollingRef.current === null) return;
      try {
        const status = await getResearchStatus(sessionId);
        setStatusData(status);

        const agentLabels: Record<string, string> = {
          planner: "Research Planner",
          paper_researcher: "Paper Researcher",
          web_researcher: "Web Researcher",
          analysis_agent: "Analysis Agent",
          gap_reframer: "Research Gap Agent",
          fact_checker: "Fact Checker",
          report_agent: "Narrative & Report Agent",
        };
        const newAgentEvents = status.agent_events.filter(
          (event) => event.sequence > seenAgentEventCountRef.current,
        );
        if (newAgentEvents.length > 0) {
          seenAgentEventCountRef.current = Math.max(
            ...newAgentEvents.map((event) => event.sequence),
          );
          setLiveLogs((prev) => [
            ...prev,
            ...newAgentEvents.map((event) => {
              const eventText =
                event.status === "running"
                  ? "started"
                  : event.status === "completed"
                    ? "completed"
                    : "failed";
              return `[${new Date(event.occurred_at).toLocaleTimeString()}] ${agentLabels[event.agent_key] || event.agent_key} ${eventText}.`;
            }),
          ]);
        }

        // Araştırma tamamlandı veya sonlandı
        if (
          status.status === "completed" ||
          status.status === "cancelled" ||
          status.status === "failed"
        ) {
          clearTimeout(pollingRef.current);
          pollingRef.current = null;

          if (status.status === "completed") {
            setLiveLogs((prev) => [
              ...prev,
              `[${new Date().toLocaleTimeString()}] Research workflow completed.`,
            ]);
            // Rapor ve metrikleri çek
            try {
              const rep = await getResearchReport(sessionId);
              setReportData(rep);
              const met = await getResearchMetrics(sessionId);
              setMetricsData(met);
            } catch {
              // Rapor yükleme hatası
            }
          }

          fetchHistory();
        }
      } catch {
        // Hata
      } finally {
        if (pollingRef.current !== null) {
          pollingRef.current = window.setTimeout(pollStatus, 2500);
        }
      }
    };

    pollingRef.current = window.setTimeout(pollStatus, 0);
  };

  // Clean polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current !== null) clearTimeout(pollingRef.current);
    };
  }, []);

  // 3. Cancel Research
  const handleCancelResearch = async () => {
    if (!activeSessionId) return;
    setIsCancelling(true);
    try {
      await cancelResearch(activeSessionId);
      setLiveLogs((prev) => [
        ...prev,
        `[${new Date().toLocaleTimeString()}] Cancellation requested. The current agent step will finish before the workflow stops.`,
      ]);
      fetchHistory();
    } catch (err: any) {
      alert(err.message || "Could not cancel the research session.");
    } finally {
      setIsCancelling(false);
    }
  };

  // 4. Select Session from History
  const handleSelectSession = async (sessionId: string) => {
    seenAgentEventCountRef.current = 0;
    setActiveSessionId(sessionId);
    try {
      const status = await getResearchStatus(sessionId);
      setStatusData(status);

      if (status.status === "running" || status.status === "cancelling") {
        setLiveLogs([
          `[${new Date().toLocaleTimeString()}] Reconnected to active research session.`,
        ]);
        setCurrentTab("live");
        startPolling(sessionId);
      } else if (status.status === "completed") {
        try {
          const rep = await getResearchReport(sessionId);
          setReportData(rep);
          const met = await getResearchMetrics(sessionId);
          setMetricsData(met);
          setCurrentTab("report");
        } catch {
          setCurrentTab("dashboard");
        }
      } else {
        // İptal edilmiş veya hata almış oturumlar için işlem yapılmaz
        return;
      }
    } catch (err: any) {
      alert(err.message || "Could not load the research session.");
    }
  };

  // Derive dynamic agent states for the Visual Canvas (Core Agents Only)
  const isRunning =
    statusData?.status === "running" ||
    statusData?.status === "cancelling" ||
    isLoading;
  const isAnyResearchRunning =
    isLoading ||
    statusData?.status === "running" ||
    statusData?.status === "cancelling" ||
    sessionsList.some(
      (session) =>
        session.is_active ||
        session.status === "running" ||
        session.status === "cancelling",
    );
  const isCompleted = statusData?.status === "completed";
  const isCancelled = statusData?.status === "cancelled";
  const isFailed = statusData?.status === "failed";

  // Agent State mapping
  const getAgentStates = () => {
    // 1. Henüz bir araştırma başlatılmadıysa veya beklemedeyse tümü pasif (waiting)
    if (!activeSessionId && !isLoading) {
      return {
        planner: "waiting" as AgentStatus,
        paper_researcher: "waiting" as AgentStatus,
        web_researcher: "waiting" as AgentStatus,
        analysis_agent: "waiting" as AgentStatus,
        gap_reframer: "waiting" as AgentStatus,
        fact_checker: "waiting" as AgentStatus,
        report_agent: "waiting" as AgentStatus,
      };
    }

    // 2. Araştırma tamamlandığında tüm ajanlar yeşil (completed)
    if (isCompleted) {
      return {
        planner: "completed" as AgentStatus,
        paper_researcher: "completed" as AgentStatus,
        web_researcher: "completed" as AgentStatus,
        analysis_agent: "completed" as AgentStatus,
        gap_reframer: "completed" as AgentStatus,
        fact_checker: "completed" as AgentStatus,
        report_agent: "completed" as AgentStatus,
      };
    }

    // 3. Çalışma süreci (Orchestrator LangGraph İş Hattı Uyumu)
    if (isRunning) {
      return {
        planner: statusData?.agent_statuses?.planner || "waiting",
        paper_researcher: statusData?.agent_statuses?.paper_researcher || "waiting",
        web_researcher: statusData?.agent_statuses?.web_researcher || "waiting",
        analysis_agent: statusData?.agent_statuses?.analysis_agent || "waiting",
        gap_reframer: statusData?.agent_statuses?.gap_reframer || "waiting",
        fact_checker: statusData?.agent_statuses?.fact_checker || "waiting",
        report_agent: statusData?.agent_statuses?.report_agent || "waiting",
      };
    }

    if (isCancelled || isFailed) {
      return {
        planner: "completed" as AgentStatus,
        paper_researcher: "failed" as AgentStatus,
        web_researcher: "failed" as AgentStatus,
        analysis_agent: "failed" as AgentStatus,
        gap_reframer: "failed" as AgentStatus,
        fact_checker: "failed" as AgentStatus,
        report_agent: "failed" as AgentStatus,
      };
    }

    // Default waiting states
    return {
      planner: "waiting" as AgentStatus,
      paper_researcher: "waiting" as AgentStatus,
      web_researcher: "waiting" as AgentStatus,
      analysis_agent: "waiting" as AgentStatus,
      gap_reframer: "waiting" as AgentStatus,
      fact_checker: "waiting" as AgentStatus,
      report_agent: "waiting" as AgentStatus,
    };
  };

  return (
    <div className="flex h-screen w-full min-w-0 overflow-hidden bg-[#090d16] text-slate-100">
      {/* 1. Left Navigation Sidebar */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={(tab) => setCurrentTab(tab)}
        isRunning={isRunning}
        hasReport={Boolean(reportData || statusData?.has_report)}
      />

      {/* 2. Main Content View Area */}
      <main className="flex-1 min-w-0 h-full overflow-y-auto p-6 sm:p-10 flex flex-col justify-between custom-scrollbar">
        <div className="w-full">
          {/* TAB 1: DASHBOARD */}
          {currentTab === "dashboard" && (
            <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-300">
              {/* Header */}
              <div className="space-y-2">
                <h1 className="text-3xl font-extrabold text-white tracking-tight">
                  Research<span className="text-cyan-400">Mind</span> Workspace
                </h1>
                <p className="text-sm text-slate-400">
                  An AI-powered workspace for deep research and evidence verification.
                </p>
              </div>

              {/* Scope Gate Banner (Out of Scope / Clarification) */}
              {scopeGateFeedback && (
                <ScopeGateBanner
                  data={scopeGateFeedback}
                  onDismiss={() => setScopeGateFeedback(null)}
                />
              )}

              {/* Research Input Form */}
              <ResearchInput
                onSubmit={handleStartResearch}
                isLoading={isLoading}
              />

              {/* History Table */}
              <HistoryList
                sessions={sessionsList}
                onSelectSession={handleSelectSession}
                onRefresh={fetchHistory}
                isLoading={isHistoryLoading}
                isAnyResearchRunning={isAnyResearchRunning}
              />
            </div>
          )}

          {/* TAB 2: LIVE EXECUTION (Agent Canvas) */}
          {currentTab === "live" && (
            <div className="w-full h-full space-y-6 animate-in fade-in duration-300">
              {/* Active Session Info Bar */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#0c121e] border border-slate-800 p-4 sm:p-5 rounded-2xl shadow-xl">
                <div className="space-y-1 min-w-0 flex-1">
                  {/* Status Badges & Counters */}
                  <div className="flex items-center gap-2.5 flex-wrap">
                    {!activeSessionId && !isLoading ? (
                      <>
                        <span className="h-2.5 w-2.5 rounded-full bg-slate-500" />
                        <span className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider">
                          Research Workflow — Idle
                        </span>
                      </>
                    ) : isRunning ? (
                      <>
                        <span className="flex h-2.5 w-2.5 relative">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500" />
                        </span>
                        <span className="text-xs font-mono font-bold text-cyan-300 uppercase tracking-wider">
                          Research Workflow — In Progress
                        </span>
                      </>
                    ) : isCompleted ? (
                      <>
                        <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                        <span className="text-xs font-mono font-bold text-emerald-300 uppercase tracking-wider">
                          Research Workflow — Completed
                        </span>
                      </>
                    ) : isCancelled ? (
                      <>
                        <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                        <span className="text-xs font-mono font-bold text-amber-300 uppercase tracking-wider">
                          Research Workflow — Cancelled
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="h-2.5 w-2.5 rounded-full bg-red-400" />
                        <span className="text-xs font-mono font-bold text-red-300 uppercase tracking-wider">
                          Research Workflow — Failed
                        </span>
                      </>
                    )}

                    {activeSessionId && (
                      <span className="text-[11px] font-mono text-slate-400 bg-slate-800/90 border border-slate-700/60 px-2 py-0.5 rounded">
                        ID: {activeSessionId.slice(0, 8)}
                      </span>
                    )}

                    {/* Progress chips if active */}
                    {statusData && (isRunning || isCompleted) && (
                      <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400">
                        {statusData.academic_sources_count > 0 && (
                          <span className="bg-cyan-950/60 text-cyan-300 border border-cyan-800/40 px-2 py-0.5 rounded">
                            {statusData.academic_sources_count} Papers
                          </span>
                        )}
                        {statusData.web_sources_count > 0 && (
                          <span className="bg-amber-950/60 text-amber-300 border border-amber-800/40 px-2 py-0.5 rounded">
                            {statusData.web_sources_count} Web
                          </span>
                        )}
                        {statusData.claim_verifications_count > 0 && (
                          <span className="bg-emerald-950/60 text-emerald-300 border border-emerald-800/40 px-2 py-0.5 rounded">
                            {statusData.claim_verifications_count} Claims
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Main Title & Subtitle */}
                  {!activeSessionId && !isLoading ? (
                    <div>
                      <h3 className="text-sm sm:text-base font-semibold text-slate-200 mt-1">
                        No active research session
                      </h3>
                      <p className="text-xs text-slate-400">
                        Enter a research question on the Dashboard to watch the agents work.
                      </p>
                    </div>
                  ) : isRunning ? (
                    <div>
                      <h3 className="text-sm sm:text-base font-bold text-white mt-1 line-clamp-1">
                        {statusData?.query || "Starting research..."}
                      </h3>
                      <p className="text-xs text-cyan-400/90 font-medium">
                        {statusData?.query
                          ? "Agents are searching the literature, synthesizing findings, and verifying evidence..."
                          : "Preparing the research plan..."}
                      </p>
                    </div>
                  ) : isCompleted ? (
                    <div>
                      <h3 className="text-sm sm:text-base font-bold text-white mt-1 line-clamp-1">
                        {statusData?.query}
                      </h3>
                      <p className="text-xs text-emerald-400/90 font-medium">
                        Academic and web evidence has been cross-checked, and the final research report is ready.
                      </p>
                    </div>
                  ) : (
                    <div>
                      <h3 className="text-sm sm:text-base font-bold text-white mt-1 line-clamp-1">
                        {statusData?.query || "Session ended"}
                      </h3>
                      <p className="text-xs text-slate-400">
                        {isCancelled
                          ? "The research session was cancelled."
                          : "An error occurred during the session."}
                      </p>
                    </div>
                  )}
                </div>

                {/* Right Action Button */}
                <div className="shrink-0 flex items-center gap-2">
                  {!activeSessionId && !isLoading ? (
                    <button
                      onClick={() => setCurrentTab("dashboard")}
                      className="px-4 py-2 rounded-xl bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/40 text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md active:scale-95"
                    >
                      <span>Start New Research</span>
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </button>
                  ) : isCompleted ? (
                    <button
                      onClick={() => setCurrentTab("report")}
                      className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-semibold text-xs transition-all shadow-lg shadow-emerald-500/20 active:scale-95 flex items-center gap-1.5"
                    >
                      <span>View Report</span>
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </button>
                  ) : null}
                </div>
              </div>

              {/* Visual Canvas + Activity Feed Split (Açılır / Kapanır Panel) */}
              <div className="flex flex-col lg:flex-row items-stretch gap-4 sm:gap-6 h-full min-h-[580px]">
                <div className="flex-1 min-w-0">
                  <AgentCanvas
                    agentStates={getAgentStates()}
                    paperCount={statusData?.academic_sources_count || 0}
                    webCount={statusData?.web_sources_count || 0}
                    claimCount={statusData?.claim_verifications_count || 0}
                    iterationCount={statusData?.iteration_count || 0}
                  />
                </div>

                <ActivityFeed
                  logs={liveLogs}
                  isRunning={isRunning}
                  onCancel={handleCancelResearch}
                  isCancelling={isCancelling}
                  isOpen={isLogOpen}
                  onToggle={() => setIsLogOpen(!isLogOpen)}
                />
              </div>
            </div>
          )}

          {/* TAB 3: RESEARCH REPORT */}
          {currentTab === "report" && (
            <div className="w-full animate-in fade-in duration-300">
              {reportData ? (
                <ReportViewer report={reportData} />
              ) : (
                <div className="max-w-xl mx-auto py-24 text-center text-slate-400 space-y-4">
                  <p className="text-base font-semibold">
                    No Report to Display
                  </p>
                  <p className="text-xs text-slate-500">
                    Select a completed research session or start a new one from the Dashboard.
                  </p>
                  <button
                    onClick={() => setCurrentTab("dashboard")}
                    className="px-4 py-2 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl transition-colors"
                  >
                    Back to Dashboard
                  </button>
                </div>
              )}
            </div>
          )}

          {/* TAB 4: QUALITY & METRICS */}
          {currentTab === "metrics" && (
            <div className="w-full animate-in fade-in duration-300">
              <QualityMetrics
                metrics={metricsData}
                claims={reportData?.claim_verifications || []}
              />
            </div>
          )}
        </div>

        {/* Global Footer */}
        <footer className="mt-12 text-center text-[11px] text-slate-500 font-mono no-print">
          ResearchMind • Autonomous Research Workspace
        </footer>
      </main>
    </div>
  );
};

export default App;
