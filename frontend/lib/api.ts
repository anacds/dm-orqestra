import {
  Campaign,
  CampaignsResponse,
  CampaignResponse,
  CreateCampaignRequest,
  UpdateCampaignRequest,
  AddCommentRequest,
  UserResponse,
  EnhanceObjectiveRequest,
  EnhanceObjectiveResponse,
  UpdateInteractionDecisionRequest,
  AnalyzePieceRequest,
  AnalyzePieceResponse,
  ContentValidationAnalyzePieceResponse,
  ContentValidationChannel,
  SubmitCreativePieceRequest,
  CreativePiece,
  PieceReviewHistoryResponse,
  PieceReviewEvent,
  CampaignStatusHistoryResponse,
  CampaignStatusEvent,
  MyTasksResponse,
  TaskGroup,
} from "@shared/api";

const API_BASE = "/api";

async function fetchAPI<T>(endpoint: string, options?: RequestInit, retryOn401: boolean = true): Promise<T> {
  const headers: HeadersInit = {
    ...options?.headers,
  };

  if (!(options?.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    if (response.status === 401 && retryOn401) {
      const currentPath = window.location.pathname;

      if (currentPath.includes("/login") || currentPath.includes("/register")) {
        const error = await response.json().catch(() => ({ detail: "Unauthorized" }));
        throw new Error(error.detail || error.error || `HTTP error! status: ${response.status}`);
      }

      try {
        await authAPI.refreshAccessToken();
        return fetchAPI<T>(endpoint, options, false);
      } catch (refreshError) {
        if (!currentPath.includes("/login") && !currentPath.includes("/register")) {
          window.location.href = "/login";
        }
        throw new Error("Session expired. Please login again.");
      }
    } else if (response.status === 401) {
      const currentPath = window.location.pathname;
      if (!currentPath.includes("/login") && !currentPath.includes("/register")) {
        window.location.href = "/login";
      }
    }
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || error.error || `HTTP error! status: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type");
  if (!contentType || !contentType.includes("application/json")) {
    return undefined as T;
  }

  const text = await response.text();
  if (!text || text.trim() === "") {
    return undefined as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch (e) {
    return undefined as T;
  }
}

export const authAPI = {
  login: async (email: string, password: string): Promise<{ access_token: string; refresh_token: string; token_type: string }> => {
    const formData = new FormData();
    formData.append("username", email);
    formData.append("password", password);

    const response = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      body: formData,
      credentials: "include",
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(error.detail || "Login failed");
    }

    return await response.json();
  },

  refreshAccessToken: async (): Promise<string> => {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error("No refresh token available");
      }
      throw new Error("Failed to refresh token");
    }

    const data = await response.json();
    return data.access_token;
  },

  register: async (email: string, password: string, fullName?: string): Promise<void> => {
    const response = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, full_name: fullName }),
      credentials: "include",
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Registration failed" }));
      throw new Error(error.detail || "Registration failed");
    }
  },

  logout: async (): Promise<void> => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
      });
    } catch (error) {
    }
  },

  getCurrentUser: async (): Promise<UserResponse | null> => {
    try {
      return await fetchAPI<UserResponse>("/auth/me");
    } catch (error) {
      if (error instanceof Error && error.message.includes("401")) {
        return null;
      }
      throw error;
    }
  },
};

export const campaignsAPI = {
  getAll: async (): Promise<Campaign[]> => {
    const response = await fetchAPI<CampaignsResponse>("/campaigns");
    return response.campaigns;
  },

  getById: async (id: string): Promise<Campaign> => {
    return await fetchAPI<CampaignResponse>(`/campaigns/${id}`);
  },

  create: async (data: CreateCampaignRequest): Promise<Campaign> => {
    return await fetchAPI<CampaignResponse>("/campaigns", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  update: async (id: string, data: UpdateCampaignRequest): Promise<Campaign> => {
    return await fetchAPI<CampaignResponse>(`/campaigns/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  addComment: async (campaignId: string, data: AddCommentRequest): Promise<void> => {
    await fetchAPI(`/campaigns/${campaignId}/comments`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  submitForReview: async (
    campaignId: string,
    pieceReviews: { channel: string; pieceId: string; commercialSpace?: string }[]
  ): Promise<Campaign> => {
    return await fetchAPI<CampaignResponse>(`/campaigns/${campaignId}/submit-for-review`, {
      method: "POST",
      body: JSON.stringify({ pieceReviews }),
    });
  },

  reviewPiece: async (
    campaignId: string,
    params: { channel: string; pieceId: string; commercialSpace?: string; action: "approve" | "reject" | "manually_reject"; rejectionReason?: string }
  ): Promise<Campaign> => {
    const body: Record<string, unknown> = {
      channel: params.channel,
      pieceId: params.pieceId,
      action: params.action,
    };
    if (params.commercialSpace != null) body.commercialSpace = params.commercialSpace;
    if (params.rejectionReason != null) body.rejectionReason = params.rejectionReason;
    return await fetchAPI<CampaignResponse>(`/campaigns/${campaignId}/pieces/review`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  updateIaVerdict: async (
    campaignId: string,
    params: { channel: string; pieceId: string; commercialSpace?: string; iaVerdict: "approved" | "rejected"; iaAnalysisText?: string }
  ): Promise<Campaign> => {
    const body: Record<string, unknown> = {
      channel: params.channel,
      pieceId: params.pieceId,
      iaVerdict: params.iaVerdict,
    };
    if (params.commercialSpace != null) body.commercialSpace = params.commercialSpace;
    if (params.iaAnalysisText != null) body.iaAnalysisText = params.iaAnalysisText;
    return await fetchAPI<CampaignResponse>(`/campaigns/${campaignId}/piece-reviews/ia-verdict`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  getPieceReviewHistory: async (campaignId: string): Promise<PieceReviewEvent[]> => {
    const response = await fetchAPI<PieceReviewHistoryResponse>(`/campaigns/${campaignId}/piece-review-history`);
    return response.events;
  },

  getStatusHistory: async (campaignId: string): Promise<{ events: CampaignStatusEvent[]; currentStatus: string }> => {
    const response = await fetchAPI<CampaignStatusHistoryResponse>(`/campaigns/${campaignId}/status-history`);
    return { events: response.events, currentStatus: response.currentStatus };
  },

  getMyTasks: async (): Promise<MyTasksResponse> => {
    return await fetchAPI<MyTasksResponse>("/campaigns/my-tasks");
  },

  enhanceObjective: async (
    text: string,
    fieldName: string,
    campaignId?: string,
    sessionId?: string,
    campaignName?: string
  ): Promise<EnhanceObjectiveResponse> => {
    return await fetchAPI<EnhanceObjectiveResponse>("/enhance-objective", {
      method: "POST",
      body: JSON.stringify({
        text,
        field_name: fieldName,
        campaign_id: campaignId,
        session_id: sessionId,
        campaign_name: campaignName,
      } as EnhanceObjectiveRequest),
    });
  },

  updateInteractionDecision: async (interactionId: string, decision: "approved" | "rejected"): Promise<void> => {
    await fetchAPI<void>(`/ai-interactions/${interactionId}/decision`, {
      method: "PATCH",
      body: JSON.stringify({ decision } as UpdateInteractionDecisionRequest),
    });
  },
};

const INTERNAL_ROUTING_MESSAGE = /^Canal (SMS|PUSH|EMAIL|APP) -> retrieve_content$/i;

function mapContentValidationToAnalyzePieceResponse(
  raw: ContentValidationAnalyzePieceResponse,
  campaignId: string,
  channel: "SMS" | "Push" | "E-mail" | "App"
): AnalyzePieceResponse {
  // O backend retorna final_verdict.decision: APROVADO | REPROVADO (binário)
  const verdictDecision = raw.final_verdict?.decision;
  const comp = raw.compliance_result as { summary?: string; decision?: string } | undefined;

  let is_valid: "valid" | "invalid" = "invalid";
  if (verdictDecision === "APROVADO") {
    is_valid = "valid";
  } else if (comp?.decision === "APROVADO" && !verdictDecision) {
    // Fallback: se final_verdict não definido, usa compliance
    is_valid = "valid";
  }

  // Texto: prioriza final_verdict.summary > compliance.summary > specs errors > validation_result.message
  const verdictSummary = raw.final_verdict?.summary;
  const compSummary = comp?.summary;
  const val = raw.validation_result as { message?: string } | undefined;
  const valMsg = typeof val?.message === "string" ? val.message : null;
  const useValMessage = valMsg && !INTERNAL_ROUTING_MESSAGE.test(valMsg.trim());

  const analysis_text =
    (typeof verdictSummary === "string" && verdictSummary.length > 0 ? verdictSummary : null) ??
    (typeof compSummary === "string" && compSummary.length > 0 ? compSummary : null) ??
    (typeof raw.human_approval_reason === "string" && raw.human_approval_reason.length > 0
      ? raw.human_approval_reason
      : null) ??
    (useValMessage ? valMsg : null) ??
    "—";

  const sources =
    raw.final_verdict?.sources ??
    (raw.compliance_result as { sources?: string[] } | undefined)?.sources ??
    undefined;

  return {
    id: crypto.randomUUID(),
    campaign_id: campaignId,
    channel,
    is_valid,
    analysis_text,
    sources: sources && sources.length > 0 ? sources : undefined,
    analyzed_by: "Content Validation Service",
    created_at: new Date().toISOString(),
  };
}

export type AnalyzePieceInput =
  | { channel: "SMS"; content: { body: string } }
  | { channel: "Push"; content: { title: string; body: string } }
  | { channel: "EMAIL"; content: { campaign_id: string; piece_id: string } }
  | { channel: "APP"; content: { campaign_id: string; piece_id: string; commercial_space: string } };

function toApiChannel(ch: AnalyzePieceInput["channel"]): ContentValidationChannel {
  if (ch === "Push") return "PUSH";
  if (ch === "EMAIL") return "EMAIL";
  if (ch === "APP") return "APP";
  return "SMS";
}

function toUiChannel(ch: AnalyzePieceInput["channel"]): "SMS" | "Push" | "E-mail" | "App" {
  if (ch === "EMAIL") return "E-mail";
  if (ch === "APP") return "App";
  if (ch === "Push") return "Push";
  return "SMS";
}

export interface ValidationStepEvent {
  node: string;
  status: "started" | "done";
  label?: string;
}

export const aiAPI = {
  analyzePiece: async (
    campaignId: string,
    input: AnalyzePieceInput
  ): Promise<AnalyzePieceResponse> => {
    const body: AnalyzePieceRequest = {
      task: "VALIDATE_COMMUNICATION",
      channel: toApiChannel(input.channel),
      content: input.content as Record<string, unknown>,
      campaign_id: campaignId,
    };
    const raw = await fetchAPI<ContentValidationAnalyzePieceResponse>("/ai/analyze-piece", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return mapContentValidationToAnalyzePieceResponse(raw, campaignId, toUiChannel(input.channel));
  },

  analyzePieceStream: async (
    campaignId: string,
    input: AnalyzePieceInput,
    onStep: (step: ValidationStepEvent) => void,
  ): Promise<AnalyzePieceResponse> => {
    const body: AnalyzePieceRequest = {
      task: "VALIDATE_COMMUNICATION",
      channel: toApiChannel(input.channel),
      content: input.content as Record<string, unknown>,
      campaign_id: campaignId,
    };

    const response = await fetch(`${API_BASE}/ai/analyze-piece/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`Erro na validação streaming: ${response.status}`);
    }

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let result: ContentValidationAnalyzePieceResponse | null = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let currentEvent = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          const data = line.slice(6);
          try {
            const parsed = JSON.parse(data);
            if (currentEvent === "step") {
              onStep(parsed as ValidationStepEvent);
            } else if (currentEvent === "result") {
              result = parsed as ContentValidationAnalyzePieceResponse;
            } else if (currentEvent === "error") {
              throw new Error(parsed.error || "Erro desconhecido no streaming");
            }
          } catch (e) {
            if (e instanceof SyntaxError) continue;
            throw e;
          }
          currentEvent = "";
        }
      }
    }

    if (!result) {
      throw new Error("Stream encerrado sem resultado");
    }

    return mapContentValidationToAnalyzePieceResponse(result, campaignId, toUiChannel(input.channel));
  },

};

export const creativePiecesAPI = {
  submitCreativePiece: async (campaignId: string, pieceData: SubmitCreativePieceRequest): Promise<CreativePiece> => {
    return await fetchAPI<CreativePiece>(`/campaigns/${campaignId}/creative-pieces`, {
      method: "POST",
      body: JSON.stringify(pieceData),
    });
  },

  uploadAppFile: async (campaignId: string, commercialSpace: string, file: File): Promise<CreativePiece> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("commercial_space", commercialSpace);

    return await fetchAPI<CreativePiece>(`/campaigns/${campaignId}/creative-pieces/upload-app`, {
      method: "POST",
      body: formData,
    });
  },

  uploadEmailFile: async (campaignId: string, file: File): Promise<CreativePiece> => {
    const formData = new FormData();
    formData.append("file", file);

    return await fetchAPI<CreativePiece>(`/campaigns/${campaignId}/creative-pieces/upload-email`, {
      method: "POST",
      body: formData,
    });
  },

  deleteAppFile: async (campaignId: string, commercialSpace: string): Promise<void> => {
    const encodedSpace = encodeURIComponent(commercialSpace);
    await fetchAPI(`/campaigns/${campaignId}/creative-pieces/app/${encodedSpace}`, {
      method: "DELETE",
    });
  },

  deleteEmailFile: async (campaignId: string): Promise<void> => {
    await fetchAPI(`/campaigns/${campaignId}/creative-pieces/email`, {
      method: "DELETE",
    });
  },

  updatePieceIaAnalysis: async (
    campaignId: string,
    pieceId: string,
    iaVerdict: "approved" | "rejected",
    iaAnalysisText?: string,
  ): Promise<CreativePiece> => {
    const body: Record<string, unknown> = { iaVerdict };
    if (iaAnalysisText != null) body.iaAnalysisText = iaAnalysisText;
    return await fetchAPI<CreativePiece>(`/campaigns/${campaignId}/creative-pieces/${pieceId}/ia-analysis`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },
};
