import React, { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  FileDown,
  Printer,
  ExternalLink,
  BookmarkCheck,
  Sparkles,
  BookOpen,
  FileText,
  Globe,
  X,
  Calendar,
  Users,
  Award,
  Layers,
  ChevronRight,
  Microscope,
  ShieldCheck,
} from "lucide-react";

import {
  ReportResponse,
  AcademicPaperDetail,
  WebSourceDetail,
} from "../../types/research";

interface ReportViewerProps {
  report: ReportResponse;
}

/* -------------------------------------------------------------------------- */
/* Text helpers                                                               */
/* -------------------------------------------------------------------------- */

/**
 * Yalnızca desteklenen LaTeX biçimlendirme komutlarını görsel metne çevirir.
 * Atıf numaralarına ([1], [2]) dokunmaz.
 */
export function cleanLatexText(text: string): string {
  if (!text) return "";

  let cleaned = text;

  for (let i = 0; i < 3; i++) {
    cleaned = cleaned.replace(
      /\\(?:textbf|textit|emph|underline|textsc|texttt|text|mathrm|mathbf|mathit)\{([^{}]*)\}/g,
      "$1",
    );
  }

  cleaned = cleaned
    .replace(/\\href\{([^}]+)\}\{([^}]+)\}/g, "$2 ($1)")
    .replace(/\\url\{([^}]+)\}/g, "$1")
    .replace(/\\cite\{([^}]+)\}/g, "[$1]")
    .replace(/\\ref\{([^}]+)\}/g, "$1")
    .replace(/\\([#$%&_{}])/g, "$1")
    .replace(/\\~/g, " ")
    .replace(/\$([^$]+)\$/g, "$1")
    .replace(/[ \t]+/g, " ")
    .trim();

  return cleaned;
}

/**
 * Kaynak numaralarını silmez veya yeniden yazmaz.
 * Eski fonksiyon isimleri başka bileşenlerde kullanılıyorsa uyumluluk sağlar.
 */
export function cleanExecutiveSummary(text: string): string {
  return cleanLatexText(text);
}

export function cleanReportCitations(text: string): string {
  return cleanLatexText(text);
}

/* -------------------------------------------------------------------------- */
/* Markdown renderer                                                         */
/* -------------------------------------------------------------------------- */

const MarkdownContent: React.FC<{ content: string }> = ({ content }) => (
  <div
    className="prose prose-invert print:prose-neutral max-w-none
    text-slate-300 print:text-slate-800 text-sm sm:text-base
    leading-relaxed
    prose-headings:text-slate-100 print:prose-headings:text-black
    prose-strong:text-slate-100 print:prose-strong:text-black
    prose-a:text-cyan-400 prose-a:break-all
    prose-code:text-cyan-300
    prose-blockquote:border-cyan-500/50
    prose-th:text-slate-200
    prose-td:text-slate-300
    prose-table:text-sm"
  >
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || ""}</ReactMarkdown>
  </div>
);

/* -------------------------------------------------------------------------- */
/* Section                                                                    */
/* -------------------------------------------------------------------------- */

interface ReportSectionProps {
  number: string;
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

const ReportSection: React.FC<ReportSectionProps> = ({
  number,
  title,
  icon,
  children,
  className = "",
}) => (
  <section
    className={`space-y-5 border-t border-slate-800/80 pt-8 ${className}`}
  >
    <div className="flex items-start gap-3">
      <div
        className="h-10 w-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20
        flex items-center justify-center text-cyan-400 shrink-0"
      >
        {icon}
      </div>

      <div className="min-w-0">
        <p
          className="text-[10px] uppercase tracking-[0.2em] text-cyan-500
          font-semibold mb-1"
        >
          {number}
        </p>

        <h2
          className="text-lg sm:text-xl font-bold text-white print:text-black
          tracking-tight"
        >
          {title}
        </h2>
      </div>
    </div>

    {children}
  </section>
);

/* -------------------------------------------------------------------------- */
/* Main Component                                                             */
/* -------------------------------------------------------------------------- */

export const ReportViewer: React.FC<ReportViewerProps> = ({ report }) => {
  const [selectedPaper, setSelectedPaper] =
    useState<AcademicPaperDetail | null>(null);

  const [selectedWeb, setSelectedWeb] = useState<WebSourceDetail | null>(null);

  const [activeSourceTab, setActiveSourceTab] = useState<"papers" | "web">(
    "papers",
  );

  const papers = report.academic_papers || [];
  const webSources = report.web_sources || [];
  const sections = report.sections || [];
  const bibliography = report.bibliography || [];

  const executiveSummary = cleanLatexText(report.executive_summary || "");

  const closeModals = () => {
    setSelectedPaper(null);
    setSelectedWeb(null);
  };

  /* Modal scroll lock */
  useEffect(() => {
    const isModalOpen = Boolean(selectedPaper || selectedWeb);

    document.body.style.overflow = isModalOpen ? "hidden" : "";

    return () => {
      document.body.style.overflow = "";
    };
  }, [selectedPaper, selectedWeb]);

  /* Escape key */
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeModals();
      }
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  /* ---------------------------------------------------------------------- */
  /* Markdown export                                                        */
  /* ---------------------------------------------------------------------- */

  const handleDownloadMarkdown = () => {
    let content = `# ${cleanLatexText(report.title)}\n\n`;

    content += `## 1. Executive Summary\n\n${executiveSummary}\n\n`;

    if (sections.length > 0) {
      content += `## 2. Research Findings\n\n`;

      sections.forEach((section) => {
        content += `### ${section.heading}\n\n`;
        content += `${section.content || section.content_preview || ""}\n\n`;
      });
    }

    if (report.comparative_analysis_markdown) {
      content += `## 3. Comparative Analysis\n\n`;
      content += `${report.comparative_analysis_markdown}\n\n`;
    }

    if (report.limitations_and_future_directions) {
      content += `## 4. Limitations and Future Directions\n\n`;
      content += `${report.limitations_and_future_directions}\n\n`;
    }

    if (bibliography.length > 0) {
      content += `## 5. References\n\n`;

      bibliography.forEach((item, index) => {
        content += `- ${cleanLatexText(item.citation)}\n`;
      });

      content += "\n";
    }

    if (report.verification_matrix_markdown) {
      content += `## 6. Evidence Verification\n\n`;
      content += `${report.verification_matrix_markdown}\n\n`;
    }

    const blob = new Blob([content], {
      type: "text/markdown;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = `ResearchMind_Report_${(report.session_id || "report").slice(
      0,
      8,
    )}.md`;

    link.click();

    URL.revokeObjectURL(url);
  };

  const handlePrintPDF = () => {
    window.print();
  };

  const totalSources =
    report.total_sources || papers.length + webSources.length;

  /* ---------------------------------------------------------------------- */
  /* Render                                                                 */
  /* ---------------------------------------------------------------------- */

  return (
    <div className="w-full max-w-5xl mx-auto space-y-8 pb-20 min-w-0">
      {/* ---------------------------------------------------------------- */}
      {/* Header                                                           */}
      {/* ---------------------------------------------------------------- */}

      <header
        className="bg-[#0c121e] border border-slate-800 rounded-3xl
        p-6 sm:p-8 flex flex-col sm:flex-row sm:items-center
        justify-between gap-6 shadow-2xl no-print"
      >
        <div className="space-y-3 min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="px-2.5 py-1 text-xs font-bold
              bg-cyan-500/10 text-cyan-300 border border-cyan-500/30
              rounded-full flex items-center gap-1.5"
            >
              <Sparkles className="h-3 w-3" />
              Research Report
            </span>

            <span className="text-xs text-slate-400 font-mono">
              Session: {(report.session_id || "").slice(0, 8)}
            </span>
          </div>

          <h1
            className="text-xl sm:text-2xl font-extrabold text-white
            tracking-tight leading-snug break-words"
          >
            {cleanLatexText(report.title)}
          </h1>

          <div className="flex items-center gap-2 text-xs text-slate-400">
            <BookOpen className="h-3.5 w-3.5 text-cyan-400" />
            <span>{totalSources} sources</span>
            <span className="text-slate-600">•</span>
            <span>{papers.length} academic papers</span>
            <span className="text-slate-600">•</span>
            <span>{webSources.length} web sources</span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0 flex-wrap">
          <button
            onClick={handleDownloadMarkdown}
            className="px-4 py-2.5 rounded-xl bg-slate-800
              hover:bg-slate-700 text-slate-200 hover:text-white
              border border-slate-700 text-xs font-semibold
              flex items-center gap-2 transition-all"
            title="Download Markdown"
          >
            <FileDown className="h-4 w-4 text-cyan-400" />
            <span>Download .MD</span>
          </button>

          <button
            onClick={handlePrintPDF}
            className="px-4 py-2.5 rounded-xl bg-cyan-600
              hover:bg-cyan-500 text-white text-xs font-semibold
              flex items-center gap-2 transition-all"
            title="Export report as PDF"
          >
            <Printer className="h-4 w-4" />
            <span>Print / Save as PDF</span>
          </button>

        </div>
      </header>

      {/* ---------------------------------------------------------------- */}
      {/* Report Paper                                                     */}
      {/* ---------------------------------------------------------------- */}

      <article
        id="report-print-root"
        className="bg-[#0c121e] border border-slate-800
        rounded-3xl p-6 sm:p-12 shadow-2xl space-y-10
        print:bg-white print:text-black print:border-none
        print:p-0 min-w-0"
      >
        {/* 1. Executive Summary */}

        <section
          className="bg-gradient-to-br from-cyan-950/30
          via-[#0a0f18] to-indigo-950/20
          border border-cyan-500/30 rounded-2xl
          p-6 sm:p-8 space-y-4 relative overflow-hidden
          print:border-slate-300 print:bg-slate-50 shadow-lg"
        >
          <div
            className="flex items-center gap-2 text-cyan-400
            print:text-cyan-800 font-bold text-xs
            tracking-[0.16em] uppercase"
          >
            <BookmarkCheck className="h-4 w-4" />
            <span>Executive Summary</span>
          </div>

          <h2
            className="text-xl sm:text-2xl font-bold text-white
            print:text-black"
          >
            Executive Summary
          </h2>

          <div
            className="text-sm sm:text-base text-slate-200
            print:text-slate-900 leading-[1.85]"
          >
            {executiveSummary || "No executive summary is available."}
          </div>
        </section>

        {/* 2. Research Findings / Thematic Sections */}

        {sections.length > 0 && (
          <section className="space-y-8">
            <div className="flex items-center gap-3">
              <div
                className="h-10 w-10 rounded-xl bg-cyan-500/10
                border border-cyan-500/20 flex items-center
                justify-center text-cyan-400"
              >
                <Microscope className="h-5 w-5" />
              </div>

              <div>
                <p
                  className="text-[10px] uppercase tracking-[0.2em]
                  text-cyan-500 font-semibold mb-1"
                >
                  Research Findings
                </p>

                <h2
                  className="text-lg sm:text-xl font-bold
                  text-white print:text-black"
                >
                  Research Findings
                </h2>
              </div>
            </div>

            <div className="space-y-10">
              {sections.map((section, index) => (
                <div
                  key={`${section.heading}-${index}`}
                  className="space-y-4 border-b border-slate-800/80
                    pb-8 last:border-none"
                >
                  <h3
                    className="text-base sm:text-lg font-bold
                    text-white print:text-black tracking-tight
                    flex items-start gap-3"
                  >
                    <span
                      className="text-cyan-400 print:text-cyan-700
                      font-mono text-xs mt-1 shrink-0"
                    >
                      {String(index + 1).padStart(2, "0")}
                    </span>

                    <span>{section.heading}</span>
                  </h3>

                  <MarkdownContent
                    content={section.content || section.content_preview || ""}
                  />
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 3. Comparative Analysis */}

        {report.comparative_analysis_markdown && (
          <ReportSection
            number="03 / COMPARATIVE ANALYSIS"
            title="Comparative Analysis"
            icon={<Layers className="h-5 w-5" />}
          >
            <div
              className="overflow-x-auto rounded-xl
              border border-slate-800 print:border-slate-300
              p-4 sm:p-5 bg-[#080d16] print:bg-white
              text-xs sm:text-sm custom-scrollbar"
            >
              <MarkdownContent content={report.comparative_analysis_markdown} />
            </div>
          </ReportSection>
        )}

        {/* 4. Critical Discussion and Limitations */}

        {report.limitations_and_future_directions && (
          <ReportSection
            number="04 / CRITICAL DISCUSSION"
            title="Limitations and Future Directions"
            icon={<Award className="h-5 w-5" />}
          >
            <div
              className="rounded-2xl bg-[#080d16]
              border border-slate-800 p-5 sm:p-6
              print:bg-white print:border-slate-300"
            >
              <MarkdownContent
                content={report.limitations_and_future_directions}
              />
            </div>
          </ReportSection>
        )}

        {/* 5. Bibliography */}

        {bibliography.length > 0 && (
          <ReportSection
            number="05 / REFERENCES"
            title="References"
            icon={<BookOpen className="h-5 w-5" />}
          >
            <div className="space-y-3">
              {bibliography.map((item, index) => (
                <div
                  key={`${item.index || index}-${index}`}
                  className="p-4 rounded-xl bg-[#080d16]
                    border border-slate-800/80 flex items-start
                    gap-3 text-xs sm:text-sm leading-relaxed
                    print:bg-white print:border-slate-200"
                >
                  <span
                    className="text-cyan-400 font-bold
                    font-mono shrink-0"
                  >
                    [{item.index || index + 1}]
                  </span>

                  <span
                    className="flex-1 text-slate-300
                    print:text-slate-900 break-words"
                  >
                    {cleanLatexText(item.citation)}
                  </span>
                </div>
              ))}
            </div>
          </ReportSection>
        )}

        {/* 6. Evidence Verification Appendix */}

        {report.verification_matrix_markdown && (
          <ReportSection
            number="APPENDIX A / EVIDENCE VERIFICATION"
            title="Evidence Verification Matrix"
            icon={<ShieldCheck className="h-5 w-5" />}
          >
            <p className="text-xs text-slate-400 leading-relaxed">
              This appendix shows the available verification records and supporting
              evidence for claims used in the report. Interpret each status in the
              context of the evidence available for that claim.
            </p>

            <div
              className="overflow-x-auto rounded-xl
              border border-slate-800 print:border-slate-300
              p-4 sm:p-5 bg-[#080d16] print:bg-white
              text-xs custom-scrollbar"
            >
              <MarkdownContent content={report.verification_matrix_markdown} />
            </div>
          </ReportSection>
        )}

        {/* 7. Interactive Source Library */}

        {(papers.length > 0 || webSources.length > 0) && (
          <section
            className="space-y-6 border-t border-slate-800/80
            pt-10 no-print"
          >
            <div
              className="flex flex-col sm:flex-row
              sm:items-center justify-between gap-4"
            >
              <div>
                <div className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-cyan-400" />

                  <h2 className="text-lg font-bold text-white">
                    Source Library
                  </h2>
                </div>

                <p className="text-xs text-slate-400 mt-1">
                  Browse the academic and web sources used in this research.
                </p>
              </div>

              <div
                className="flex items-center gap-1 p-1
                bg-slate-900 border border-slate-800
                rounded-xl self-start shrink-0"
              >
                <button
                  onClick={() => setActiveSourceTab("papers")}
                  className={`px-3 py-2 rounded-lg text-xs
                    font-semibold transition-colors flex
                    items-center gap-1.5 ${
                      activeSourceTab === "papers"
                        ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                        : "text-slate-400 hover:text-white"
                    }`}
                >
                  <FileText className="h-3.5 w-3.5" />
                  Papers ({papers.length})
                </button>

                <button
                  onClick={() => setActiveSourceTab("web")}
                  className={`px-3 py-2 rounded-lg text-xs
                    font-semibold transition-colors flex
                    items-center gap-1.5 ${
                      activeSourceTab === "web"
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                        : "text-slate-400 hover:text-white"
                    }`}
                >
                  <Globe className="h-3.5 w-3.5" />
                  Web ({webSources.length})
                </button>
              </div>
            </div>

            {/* Academic source cards */}

            {activeSourceTab === "papers" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {papers.map((paper, index) => (
                  <button
                    type="button"
                    key={paper.paper_id || index}
                    onClick={() => setSelectedPaper(paper)}
                    className="text-left p-4 rounded-2xl
                      bg-[#080d16] border border-slate-800/80
                      hover:border-cyan-500/50 hover:bg-[#0c121f]
                      transition-all group space-y-3 shadow-md
                      flex flex-col justify-between"
                  >
                    <div className="space-y-2.5">
                      <div
                        className="flex items-center
                        justify-between gap-2"
                      >
                        <span
                          className="text-[10px] font-mono
                          font-bold bg-cyan-950 text-cyan-300
                          px-2 py-1 rounded border border-cyan-800/50"
                        >
                          {paper.published_year || "Year unavailable"}
                        </span>

                        {paper.relevance_score != null && (
                          <span
                            className="text-[10px] font-mono
                            text-emerald-400 font-semibold"
                          >
                            {(paper.relevance_score * 100).toFixed(0)}% relevance
                          </span>
                        )}
                      </div>

                      <h3
                        className="text-sm font-bold text-slate-100
                        group-hover:text-cyan-300 transition-colors
                        line-clamp-2 leading-snug"
                      >
                        {cleanLatexText(paper.title)}
                      </h3>

                      {paper.authors?.length > 0 && (
                        <p
                          className="text-xs text-slate-400
                          flex items-center gap-1.5 line-clamp-1"
                        >
                          <Users className="h-3 w-3 shrink-0" />
                          {paper.authors.slice(0, 3).join(", ")}
                          {paper.authors.length > 3 ? " et al." : ""}
                        </p>
                      )}
                    </div>

                    <div
                      className="pt-3 flex items-center
                      justify-between text-xs text-cyan-400
                      font-medium border-t border-slate-800/50"
                    >
                      <span>View paper details</span>
                      <ChevronRight
                        className="h-4 w-4
                        group-hover:translate-x-1 transition-transform"
                      />
                    </div>
                  </button>
                ))}
              </div>
            )}

            {/* Web source cards */}

            {activeSourceTab === "web" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {webSources.map((web, index) => (
                  <button
                    type="button"
                    key={`${web.url}-${index}`}
                    onClick={() => setSelectedWeb(web)}
                    className="text-left p-4 rounded-2xl
                      bg-[#080d16] border border-slate-800/80
                      hover:border-amber-500/50 hover:bg-[#0c121f]
                      transition-all group space-y-3 shadow-md
                      flex flex-col justify-between"
                  >
                    <div className="space-y-2.5">
                      <div
                        className="flex items-center
                        justify-between gap-2"
                      >
                        <span
                          className="text-[10px] font-mono
                          font-bold bg-amber-950 text-amber-300
                          px-2 py-1 rounded border border-amber-800/50
                          flex items-center gap-1"
                        >
                          <Globe className="h-3 w-3" />
                          Web source
                        </span>

                        {web.published_date && (
                          <span
                            className="text-[10px] font-mono
                            text-slate-400"
                          >
                            {web.published_date}
                          </span>
                        )}
                      </div>

                      <h3
                        className="text-sm font-bold text-slate-100
                        group-hover:text-amber-300 transition-colors
                        line-clamp-2 leading-snug"
                      >
                        {cleanLatexText(web.title)}
                      </h3>

                      {web.snippet && (
                        <p
                          className="text-xs text-slate-400
                          line-clamp-2 leading-relaxed"
                        >
                          {cleanLatexText(web.snippet)}
                        </p>
                      )}
                    </div>

                    <div
                      className="pt-3 flex items-center
                      justify-between text-xs text-amber-400
                      font-medium border-t border-slate-800/50"
                    >
                      <span>View source details</span>
                      <ChevronRight
                        className="h-4 w-4
                        group-hover:translate-x-1 transition-transform"
                      />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </section>
        )}
      </article>

      {/* ---------------------------------------------------------------- */}
      {/* Academic Paper Modal                                             */}
      {/* ---------------------------------------------------------------- */}

      {selectedPaper && (
        <div
          className="fixed inset-0 z-50 bg-black/85
            backdrop-blur-md flex items-center justify-center
            p-3 sm:p-6 overflow-hidden no-print"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              setSelectedPaper(null);
            }
          }}
        >
          <div
            className="bg-[#0c121e] border border-slate-700/90
            rounded-3xl max-w-2xl w-full max-h-[85vh]
            flex flex-col shadow-2xl overflow-hidden"
          >
            {/* Modal header */}

            <div
              className="p-5 sm:p-6 border-b border-slate-800/80
              flex items-start justify-between gap-4 shrink-0"
            >
              <div className="space-y-3 min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className="px-2.5 py-1 text-xs font-bold
                    bg-cyan-500/10 text-cyan-300
                    border border-cyan-500/30 rounded-full
                    flex items-center gap-1.5"
                  >
                    <FileText className="h-3 w-3" />
                    Academic Paper
                  </span>

                  {selectedPaper.published_year && (
                    <span
                      className="text-xs text-slate-300
                      font-mono bg-slate-800 px-2 py-1 rounded
                      flex items-center gap-1"
                    >
                      <Calendar className="h-3 w-3 text-cyan-400" />
                      {selectedPaper.published_year}
                    </span>
                  )}

                  {selectedPaper.relevance_score != null && (
                    <span
                      className="text-xs text-emerald-400
                      font-mono bg-emerald-950/60
                      border border-emerald-800/50 px-2 py-1 rounded"
                    >
                      {(selectedPaper.relevance_score * 100).toFixed(0)}% relevance
                    </span>
                  )}
                </div>

                <h3
                  className="text-base sm:text-lg font-extrabold
                  text-white leading-snug break-words"
                >
                  {cleanLatexText(selectedPaper.title)}
                </h3>

                {selectedPaper.authors?.length > 0 && (
                  <p
                    className="text-xs text-slate-300
                    flex items-start gap-2"
                  >
                    <Users
                      className="h-3.5 w-3.5
                      text-slate-400 shrink-0 mt-0.5"
                    />
                    <span>
                      <span className="text-slate-400">Authors: </span>
                      {selectedPaper.authors.join(", ")}
                    </span>
                  </p>
                )}
              </div>

              <button
                onClick={() => setSelectedPaper(null)}
                className="p-2 rounded-xl text-slate-400
                  hover:text-white bg-slate-800 hover:bg-slate-700
                  transition-colors shrink-0"
                title="Close (Esc)"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal body */}

            <div
              className="p-5 sm:p-6 overflow-y-auto
              space-y-5 flex-1 min-h-0 custom-scrollbar"
            >
              {selectedPaper.abstract && (
                <div
                  className="space-y-3 bg-[#080d16]
                  border border-slate-800/90 p-4 sm:p-5 rounded-2xl"
                >
                  <h4
                    className="text-xs font-bold uppercase
                    tracking-wider text-cyan-400 flex items-center gap-1.5"
                  >
                    <FileText className="h-3.5 w-3.5" />
                    Paper Abstract
                  </h4>

                  <p
                    className="text-xs sm:text-sm text-slate-300
                    leading-relaxed whitespace-pre-line select-text"
                  >
                    {cleanLatexText(selectedPaper.abstract)}
                  </p>
                </div>
              )}

              {selectedPaper.extracted_intel && (
                <div
                  className="bg-[#080d16] border border-slate-800/90
                  p-4 sm:p-5 rounded-2xl space-y-3"
                >
                  <h4
                    className="text-xs font-bold uppercase
                    tracking-wider text-emerald-400 flex items-center gap-1.5"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    Extracted Research Findings
                  </h4>

                  <div className="space-y-3 text-xs">
                    {selectedPaper.extracted_intel.models_used?.length > 0 && (
                      <div
                        className="p-3 bg-cyan-950/40
                        text-cyan-300 border border-cyan-800/40 rounded-lg"
                      >
                        <span className="font-semibold">Models: </span>
                        {selectedPaper.extracted_intel.models_used.join(", ")}
                      </div>
                    )}

                    {selectedPaper.extracted_intel.datasets_used?.length >
                      0 && (
                      <div
                        className="p-3 bg-purple-950/40
                        text-purple-300 border border-purple-800/40 rounded-lg"
                      >
                        <span className="font-semibold">Datasets: </span>
                        {selectedPaper.extracted_intel.datasets_used.join(", ")}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Modal footer */}

            <div
              className="p-4 sm:p-5 border-t border-slate-800/80
              flex flex-col sm:flex-row items-center gap-3 shrink-0
              bg-[#080d16]/80"
            >
              {selectedPaper.url && (
                <a
                  href={selectedPaper.url}
                  target="_blank"
                  rel="noreferrer"
                  className="w-full py-2.5 px-4 rounded-xl
                    bg-slate-800 hover:bg-slate-700 text-white
                    text-xs font-semibold flex items-center
                    justify-center gap-2 border border-slate-700"
                >
                  <ExternalLink className="h-4 w-4 text-cyan-400" />
                  Open Paper
                </a>
              )}

              {selectedPaper.pdf_url && (
                <a
                  href={selectedPaper.pdf_url}
                  target="_blank"
                  rel="noreferrer"
                  className="w-full py-2.5 px-4 rounded-xl
                    bg-cyan-600 hover:bg-cyan-500 text-white
                    text-xs font-semibold flex items-center
                    justify-center gap-2"
                >
                  <FileDown className="h-4 w-4" />
                  Open PDF
                </a>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Web Source Modal                                                 */}
      {/* ---------------------------------------------------------------- */}

      {selectedWeb && (
        <div
          className="fixed inset-0 z-50 bg-black/85
            backdrop-blur-md flex items-center justify-center
            p-3 sm:p-6 overflow-hidden no-print"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              setSelectedWeb(null);
            }
          }}
        >
          <div
            className="bg-[#0c121e] border border-slate-700/90
            rounded-3xl max-w-xl w-full max-h-[85vh]
            flex flex-col shadow-2xl overflow-hidden"
          >
            {/* Header */}

            <div
              className="p-5 sm:p-6 border-b border-slate-800/80
              flex items-start justify-between gap-4 shrink-0"
            >
              <div className="space-y-3 min-w-0 flex-1">
                <span
                  className="px-2.5 py-1 text-xs font-bold
                  bg-amber-500/10 text-amber-300
                  border border-amber-500/30 rounded-full
                  flex items-center gap-1.5 w-fit"
                >
                  <Globe className="h-3 w-3" />
                  Web Research Source
                </span>

                <h3
                  className="text-base sm:text-lg font-bold
                  text-white leading-snug break-words"
                >
                  {cleanLatexText(selectedWeb.title)}
                </h3>

                <p
                  className="text-xs text-slate-400 font-mono
                  break-all"
                >
                  {selectedWeb.url}
                </p>
              </div>

              <button
                onClick={() => setSelectedWeb(null)}
                className="p-2 rounded-xl text-slate-400
                  hover:text-white bg-slate-800 hover:bg-slate-700
                  transition-colors shrink-0"
                title="Close (Esc)"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Body */}

            <div
              className="p-5 sm:p-6 overflow-y-auto
              space-y-4 flex-1 min-h-0 custom-scrollbar"
            >
              {selectedWeb.snippet && (
                <div
                  className="bg-[#080d16]
                  border border-slate-800/90 p-4 sm:p-5
                  rounded-2xl space-y-3"
                >
                  <h4
                    className="text-xs font-bold uppercase
                    tracking-wider text-amber-400 flex items-center gap-1.5"
                  >
                    <Globe className="h-3.5 w-3.5" />
                    Source Content
                  </h4>

                  <p
                    className="text-xs sm:text-sm text-slate-300
                    leading-relaxed whitespace-pre-line select-text"
                  >
                    {cleanLatexText(selectedWeb.snippet)}
                  </p>
                </div>
              )}
            </div>

            {/* Footer */}

            <div
              className="p-4 sm:p-5 border-t border-slate-800/80
              shrink-0 bg-[#080d16]/80"
            >
              <a
                href={selectedWeb.url}
                target="_blank"
                rel="noreferrer"
                className="w-full py-2.5 px-4 rounded-xl
                  bg-amber-600 hover:bg-amber-500 text-white
                  text-xs font-semibold flex items-center
                  justify-center gap-2 transition-all"
              >
                <ExternalLink className="h-4 w-4" />
                Web Sitesine Git
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
