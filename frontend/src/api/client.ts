/**
 * ResearchMind API Client
 * FastAPI backend endpoint'leriyle doğrudan haberleşen typed istemci.
 */

import {
  ResearchJobResponse,
  ScopeGateResponse,
  ResearchStatusResponse,
  ResearchSessionSummary,
  ReportResponse,
  EvaluationMetrics,
  CancelResearchResponse,
} from "../types/research";

const BASE_URL = import.meta.env.VITE_API_URL || "";

export async function startResearch(
  query: string,
  guidance?: string,
): Promise<
  | { success: true; data: ResearchJobResponse }
  | { success: false; data: ScopeGateResponse }
> {
  const response = await fetch(`${BASE_URL}/api/research`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      query,
      guidance: guidance || null,
    }),
  });

  const json = await response.json();

  if (response.status === 202) {
    // IN_SCOPE: Araştırma başlatıldı
    return { success: true, data: json as ResearchJobResponse };
  } else if (
    response.status === 200 &&
    (json.status === "out_of_scope" || json.status === "needs_clarification")
  ) {
    // OUT_OF_SCOPE veya NEEDS_CLARIFICATION: Scope gate uyarısı
    return { success: false, data: json as ScopeGateResponse };
  } else {
    throw new Error(
      json.detail || "An unexpected error occurred while starting research.",
    );
  }
}

export async function getResearchStatus(
  sessionId: string,
): Promise<ResearchStatusResponse> {
  const response = await fetch(`${BASE_URL}/api/research/${sessionId}`);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Could not retrieve the research status.");
  }
  return response.json();
}

export async function listResearchSessions(
  limit = 30,
): Promise<ResearchSessionSummary[]> {
  const response = await fetch(`${BASE_URL}/api/research?limit=${limit}`);
  if (!response.ok) {
    return [];
  }
  return response.json();
}

export async function getResearchReport(
  sessionId: string,
): Promise<ReportResponse> {
  const response = await fetch(`${BASE_URL}/api/research/${sessionId}/report`);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(
      error.detail || "The report is not ready or could not be loaded.",
    );
  }
  return response.json();
}

export async function getResearchMetrics(
  sessionId: string,
): Promise<EvaluationMetrics> {
  const response = await fetch(`${BASE_URL}/api/research/${sessionId}/metrics`);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Could not load the research metrics.");
  }
  return response.json();
}

export async function cancelResearch(
  sessionId: string,
): Promise<CancelResearchResponse> {
  const response = await fetch(`${BASE_URL}/api/research/${sessionId}/cancel`, {
    method: "POST",
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Could not cancel the research session.");
  }
  return response.json();
}
