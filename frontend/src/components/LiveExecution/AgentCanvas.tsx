import React, { useState, useEffect } from "react";
import { ZoomIn, ZoomOut, RotateCcw, Maximize2 } from "lucide-react";
import { AgentNode } from "./AgentNode";
import { AgentStatus } from "../../types/research";

export interface CoreAgentStateMap {
  planner: AgentStatus;
  paper_researcher: AgentStatus;
  web_researcher: AgentStatus;
  analysis_agent: AgentStatus;
  gap_reframer: AgentStatus;
  fact_checker: AgentStatus;
  report_agent: AgentStatus;
}

interface AgentCanvasProps {
  agentStates: CoreAgentStateMap;
  paperCount: number;
  webCount: number;
  claimCount: number;
  iterationCount: number;
}

export const AgentCanvas: React.FC<AgentCanvasProps> = ({
  agentStates,
  paperCount,
  webCount,
  claimCount,
  iterationCount,
}) => {
  // Laptop ve küçük ekranlar için dinamik ölçekleme state'i
  const [zoomLevel, setZoomLevel] = useState<number>(() => {
    if (typeof window !== "undefined" && window.innerWidth < 1536) {
      return 0.85; // Laptop ekranlarında tüm ajanların ekrana tam sığması için optimize
    }
    return 1.0;
  });

  // Ekran boyutu değiştiğinde otomatik uyarlama (opsiyonel resize dinleyici)
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1280) {
        setZoomLevel(0.8);
      } else if (window.innerWidth < 1536) {
        setZoomLevel(0.85);
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const handleZoomIn = () => {
    setZoomLevel((prev) => Math.min(Number((prev + 0.1).toFixed(2)), 1.3));
  };

  const handleZoomOut = () => {
    setZoomLevel((prev) => Math.max(Number((prev - 0.1).toFixed(2)), 0.65));
  };

  const handleResetZoom = () => {
    if (window.innerWidth < 1536) {
      setZoomLevel(0.85);
    } else {
      setZoomLevel(1.0);
    }
  };

  // Connector line helper between two points (bezier curve with traveling pulse)
  const renderConnector = (
    id: string,
    x1: number,
    y1: number,
    x2: number,
    y2: number,
    isActive: boolean,
    color = "#06b6d4",
  ) => {
    const dx = Math.abs(x2 - x1) * 0.55;
    const pathD = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;

    return (
      <g key={id}>
        {/* Base inactive line */}
        <path
          d={pathD}
          fill="none"
          stroke="#1e293b"
          strokeWidth="2.5"
          strokeDasharray="4 4"
        />

        {/* Active glowing animated line */}
        {isActive && (
          <>
            <path
              d={pathD}
              fill="none"
              stroke={color}
              strokeWidth="3.5"
              strokeOpacity="0.9"
              className="animate-pulse"
              style={{
                filter: `drop-shadow(0 0 10px ${color})`,
              }}
            />
            {/* Animated traveling light particle */}
            <circle r="4.5" fill="#ffffff">
              <animateMotion path={pathD} dur="2s" repeatCount="indefinite" />
            </circle>
          </>
        )}
      </g>
    );
  };

  return (
    <div className="w-full h-full min-h-[580px] canvas-grid relative rounded-3xl border border-slate-800/80 p-4 sm:p-6 overflow-x-auto overflow-y-hidden flex items-center justify-center select-none shadow-2xl custom-scrollbar min-w-0">
      {/* Canvas zoom and scale controls */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-1.5 bg-[#0c121e]/90 border border-slate-800/90 backdrop-blur-md px-2 py-1.5 rounded-xl shadow-lg">
        <button
          onClick={handleZoomOut}
          className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title="Zoom out"
        >
          <ZoomOut className="h-3.5 w-3.5" />
        </button>

        <span className="text-[11px] font-mono text-cyan-300 font-semibold px-1 min-w-[38px] text-center">
          %{Math.round(zoomLevel * 100)}
        </span>

        <button
          onClick={handleZoomIn}
          className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title="Zoom in"
        >
          <ZoomIn className="h-3.5 w-3.5" />
        </button>

        <div className="w-[1px] h-3 bg-slate-800 mx-0.5" />

        <button
          onClick={handleResetZoom}
          className="p-1 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-slate-800 transition-colors"
          title="Reset zoom"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Scalable canvas container */}
      <div
        className="relative shrink-0 flex items-center justify-center transition-transform duration-200"
        style={{
          width: "1320px",
          height: "560px",
          transform: `scale(${zoomLevel})`,
          transformOrigin: "center center",
        }}
      >
        {/* SVG Canvas for Bezier Connectors */}
        <svg
          className="absolute inset-0 pointer-events-none"
          style={{ width: "1320px", height: "560px" }}
        >
          {/* 1. Planning -> Paper Research -> Web Research */}
          {renderConnector(
            "c-planner-paper",
            270,
            280,
            430,
            180,
            agentStates.planner === "completed" ||
              agentStates.paper_researcher === "running",
            "#06b6d4",
          )}
          {renderConnector(
            "c-paper-web",
            560,
            240,
            560,
            320,
            agentStates.paper_researcher === "completed" ||
              agentStates.web_researcher === "running",
            "#06b6d4",
          )}

          {/* 2. Web Research -> Analysis */}
          {renderConnector(
            "c-web-analysis",
            690,
            380,
            780,
            280,
            agentStates.web_researcher === "completed" ||
              agentStates.analysis_agent === "running",
            "#f59e0b",
          )}

          {/* 3. Analysis -> Gap Reframer (Döngü Kolu) */}
          {renderConnector(
            "c-analysis-gap",
            910,
            310,
            910,
            410,
            agentStates.gap_reframer === "running",
            "#ef4444",
          )}

          {/* 4. Gap Reframer back to Researchers (Iterative Loop) */}
          {agentStates.gap_reframer === "running" && (
            <path
              d="M 780 440 C 600 480, 480 340, 560 220"
              fill="none"
              stroke="#ef4444"
              strokeWidth="3"
              strokeDasharray="6 6"
              className="animate-pulse"
            />
          )}

          {/* 5. Analysis -> Fact Checker */}
          {renderConnector(
            "c-analysis-fact",
            1040,
            250,
            1120,
            180,
            agentStates.analysis_agent === "completed" ||
              agentStates.fact_checker === "running",
            "#10b981",
          )}

          {/* 6. Fact Checker -> Report Generator (YALNIZCA en son aşamada yanar!) */}
          {renderConnector(
            "c-fact-report",
            1250,
            230,
            1250,
            340,
            agentStates.report_agent === "running" ||
              agentStates.report_agent === "completed",
            "#38bdf8",
          )}
        </svg>

        {/* Nodes Grid Container (4 Columns - Clean Main Agents Only) */}
        <div
          className="relative z-10 grid grid-cols-4 gap-x-24 gap-y-12 items-center"
          style={{ width: "1320px", padding: "0 30px" }}
        >
          {/* Column 1: Research Planner */}
          <div className="flex flex-col items-center justify-center">
            <AgentNode
              id="planner"
              name="Research Planner"
              role="Research Planning & Hypothesis Design"
              status={agentStates.planner}
              accentColor="blue"
              iconName="brain"
            />
          </div>

          {/* Column 2: Dual Parallel Researchers */}
          <div className="space-y-20 flex flex-col items-center justify-center">
            <AgentNode
              id="paper_researcher"
              name="Paper Researcher"
              role="Academic Literature & PDF Analysis"
              status={agentStates.paper_researcher}
              accentColor="cyan"
              iconName="paper"
              countLabel={paperCount > 0 ? `${paperCount} papers` : undefined}
            />
            <AgentNode
              id="web_researcher"
              name="Web Researcher"
              role="Web Research & Source Review"
              status={agentStates.web_researcher}
              accentColor="amber"
              iconName="web"
              countLabel={webCount > 0 ? `${webCount} sources` : undefined}
            />
          </div>

          {/* Column 3: Analysis & Iteration Loop */}
          <div className="space-y-16 flex flex-col items-center justify-center">
            <AgentNode
              id="analysis_agent"
              name="Analysis Agent"
              role="Comparative Synthesis"
              status={agentStates.analysis_agent}
              accentColor="indigo"
              iconName="analysis"
              countLabel={
                iterationCount > 0 ? `${iterationCount} iterations` : undefined
              }
            />
            <AgentNode
              id="gap_reframer"
              name="Gap Reframer"
              role="Research Gap Analysis"
              status={agentStates.gap_reframer}
              accentColor="amber"
              iconName="loop"
            />
          </div>

          {/* Column 4: Fact Checker & Final Report Generator */}
          <div className="space-y-16 flex flex-col items-center justify-center">
            <AgentNode
              id="fact_checker"
              name="Fact Checker"
              role="Evidence Verification"
              status={agentStates.fact_checker}
              accentColor="emerald"
              iconName="fact"
              countLabel={claimCount > 0 ? `${claimCount} claims` : undefined}
            />
            <AgentNode
              id="report_agent"
              name="Report Generator"
              role="Final Research Report"
              status={agentStates.report_agent}
              accentColor="cyan"
              iconName="report"
              countLabel="Report"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
