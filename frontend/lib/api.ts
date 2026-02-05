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
    pieceReviews: { channel: string; pieceId: string; commercialSpace?: string; iaVerdict: string }[]
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
  const status = raw.final_verdict?.status;
  const comp = raw.compliance_result as { summary?: string; decision?: string } | undefined;
  const decision = comp?.decision;

  let is_valid: "valid" | "invalid" | "warning" = "warning";
  if (status === "approved" || decision === "APROVADO") is_valid = "valid";
  else if (status === "rejected" || decision === "REPROVADO") is_valid = "invalid";
  else if (raw.requires_human_approval) is_valid = "warning";

  const val = raw.validation_result as { message?: string } | undefined;
  const valMsg = typeof val?.message === "string" ? val.message : null;
  const useValMessage = valMsg && !INTERNAL_ROUTING_MESSAGE.test(valMsg.trim());

  const analysis_text =
    (typeof comp?.summary === "string" && comp.summary.length > 0 ? comp.summary : null) ??
    (typeof raw.final_verdict?.message === "string" && raw.final_verdict.message.length > 0
      ? raw.final_verdict.message
      : null) ??
    (useValMessage ? valMsg : null) ??
    (typeof raw.human_approval_reason === "string" && raw.human_approval_reason.length > 0
      ? raw.human_approval_reason
      : null) ??
    "—";

  return {
    id: crypto.randomUUID(),
    campaign_id: campaignId,
    channel,
    is_valid,
    analysis_text,
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

function getApiChannelForFetch(ch: "SMS" | "Push" | "E-mail" | "App"): "SMS" | "PUSH" | "EMAIL" | "APP" {
  if (ch === "E-mail") return "EMAIL";
  if (ch === "App") return "APP";
  if (ch === "Push") return "PUSH";
  return "SMS";
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

  getAnalysis: async (
    campaignId: string,
    channel: "SMS" | "Push" | "E-mail" | "App",
    opts: { contentHash?: string; pieceId?: string; commercialSpace?: string }
  ): Promise<AnalyzePieceResponse | null> => {
    const apiCh = getApiChannelForFetch(channel);
    let params: string;
    if (apiCh === "SMS" || apiCh === "PUSH") {
      if (!opts.contentHash) return null;
      params = `?content_hash=${encodeURIComponent(opts.contentHash)}`;
    } else if (apiCh === "EMAIL") {
      if (!opts.pieceId) return null;
      params = `?piece_id=${encodeURIComponent(opts.pieceId)}`;
    } else {
      if (!opts.pieceId || !opts.commercialSpace) return null;
      params = `?piece_id=${encodeURIComponent(opts.pieceId)}&commercial_space=${encodeURIComponent(opts.commercialSpace)}`;
    }
    try {
      const raw = await fetchAPI<ContentValidationAnalyzePieceResponse>(
        `/ai/analyze-piece/${campaignId}/${apiCh}${params}`,
        { method: "GET" }
      );
      return mapContentValidationToAnalyzePieceResponse(raw, campaignId, channel);
    } catch (error) {
      if (error instanceof Error && (error.message.includes("404") || error.message.includes("not found"))) {
        return null;
      }
      throw error;
    }
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
};
