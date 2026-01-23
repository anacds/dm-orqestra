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
  SubmitCreativePieceRequest,
  CreativePiece,
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

export const aiAPI = {
  analyzePiece: async (
    campaignId: string,
    channel: "SMS" | "Push",
    content: { text?: string; title?: string; body?: string }
  ): Promise<AnalyzePieceResponse> => {
    return await fetchAPI<AnalyzePieceResponse>("/ai/analyze-piece", {
      method: "POST",
      body: JSON.stringify({ campaignId, channel, content } as AnalyzePieceRequest),
    });
  },

  getAnalysis: async (campaignId: string, channel: "SMS" | "Push", contentHash?: string): Promise<AnalyzePieceResponse | null> => {
    const params = contentHash ? `?content_hash=${encodeURIComponent(contentHash)}` : "";
    try {
      return await fetchAPI<AnalyzePieceResponse>(`/ai/analyze-piece/${campaignId}/${channel}${params}`);
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
