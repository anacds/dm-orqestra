export type UserRole = "Analista de negócios" | "Analista de criação" | "Analista de campanhas" | "Gestor de marketing";

export interface UserResponse {
  id: string;
  email: string;
  full_name?: string;
  role?: UserRole;
  is_active: boolean;
}

export type CampaignStatus =
  | "DRAFT"
  | "CREATIVE_STAGE"
  | "CONTENT_REVIEW"
  | "CONTENT_ADJUSTMENT"
  | "CAMPAIGN_BUILDING"
  | "CAMPAIGN_PUBLISHED";

export type CampaignCategory =
  | "Aquisição"
  | "Cross-sell"
  | "Upsell"
  | "Retenção"
  | "Relacionamento"
  | "Regulatório"
  | "Educacional";

export type RequestingArea =
  | "Produtos PF"
  | "Produtos PJ"
  | "Compliance"
  | "Canais Digitais"
  | "Marketing Institucional";

export type CampaignPriority = "Normal" | "Alta" | "Regulatório / Obrigatório";

export type CommunicationChannel = "SMS" | "Push" | "E-mail" | "App";

export type CommercialSpace =
  | "Banner superior da Home"
  | "Área do Cliente"
  | "Página de ofertas"
  | "Comprovante do Pix";

export type CommunicationTone = "Formal" | "Informal" | "Urgente" | "Educativo" | "Consultivo";

export type ExecutionModel = "Batch (agendada)" | "Event-driven (por evento)";

export type TriggerEvent =
  | "Fatura fechada"
  | "Cliente ultrapassa limite do cartão"
  | "Login no app"
  | "Inatividade por 30 dias";

export interface Comment {
  id: string;
  author: string;
  role: string;
  text: string;
  timestamp: string;
}

export interface CreativePiece {
  id: string;
  pieceType: "SMS" | "Push" | "App" | "E-mail";
  text?: string;
  title?: string;
  body?: string;
  fileUrls?: string;
  htmlFileUrl?: string;
  iaVerdict?: "approved" | "rejected" | null;
  iaAnalysisText?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Campaign {
  id: string;
  name: string;
  category: CampaignCategory;
  businessObjective: string;
  expectedResult: string;
  requestingArea: RequestingArea;
  startDate: string;
  endDate: string;
  priority: CampaignPriority;
  communicationChannels: CommunicationChannel[];
  commercialSpaces?: CommercialSpace[];
  targetAudienceDescription: string;
  exclusionCriteria: string;
  estimatedImpactVolume: string;
  communicationTone: CommunicationTone;
  executionModel: ExecutionModel;
  triggerEvent?: TriggerEvent;
  recencyRuleDays: number;
  status: CampaignStatus;
  createdBy: string;
  createdByName?: string;
  createdDate: string;
  comments?: Comment[];
  creativePieces?: CreativePiece[];
  /** Set when status is CONTENT_REVIEW (piece review workflow). */
  pieceReviews?: PieceReview[];
  approvedPieceCount?: number;
  totalPieceCount?: number;
  hasRejectedPieces?: boolean;
  allPiecesApproved?: boolean;
}

export type EffectiveStatus = "approved" | "rejected" | "pending" | "not_validated";

export interface PieceReview {
  id: string;
  campaignId: string;
  channel: string;
  pieceId: string;
  commercialSpace: string;
  iaVerdict: "approved" | "rejected" | null;
  iaAnalysisText?: string | null;
  humanVerdict: "pending" | "approved" | "rejected" | "manually_rejected";
  effectiveStatus: EffectiveStatus;
  reviewedAt?: string;
  reviewedBy?: string;
  reviewedByName?: string;
  rejectionReason?: string;
}

export interface CreateCampaignRequest {
  name: string;
  category: CampaignCategory;
  businessObjective: string;
  expectedResult: string;
  requestingArea: RequestingArea;
  startDate: string;
  endDate: string;
  priority: CampaignPriority;
  communicationChannels: CommunicationChannel[];
  commercialSpaces?: CommercialSpace[];
  targetAudienceDescription: string;
  exclusionCriteria: string;
  estimatedImpactVolume: string;
  communicationTone: CommunicationTone;
  executionModel: ExecutionModel;
  triggerEvent?: TriggerEvent;
  recencyRuleDays: number;
}

export interface UpdateCampaignRequest {
  name?: string;
  category?: CampaignCategory;
  businessObjective?: string;
  expectedResult?: string;
  requestingArea?: RequestingArea;
  startDate?: string;
  endDate?: string;
  priority?: CampaignPriority;
  communicationChannels?: CommunicationChannel[];
  commercialSpaces?: CommercialSpace[];
  targetAudienceDescription?: string;
  exclusionCriteria?: string;
  estimatedImpactVolume?: string;
  communicationTone?: CommunicationTone;
  executionModel?: ExecutionModel;
  triggerEvent?: TriggerEvent;
  recencyRuleDays?: number;
  status?: CampaignStatus;
}

export interface AddCommentRequest {
  author: string;
  role: string;
  text: string;
}

export interface EnhanceObjectiveRequest {
  text: string;
  field_name: string;
  campaign_id?: string;
  session_id?: string;
  campaign_name?: string;
}

export interface EnhanceObjectiveResponse {
  enhancedText: string;
  explanation: string;
  interactionId: string;
}

export interface UpdateInteractionDecisionRequest {
  decision: "approved" | "rejected";
}

export type TextChannel = "SMS" | "Push";

export type ContentValidationChannel = "SMS" | "PUSH" | "EMAIL" | "APP";

/** Request body for POST /api/ai/analyze-piece (content-validation-service). */
export interface AnalyzePieceRequest {
  task: "VALIDATE_COMMUNICATION";
  channel: ContentValidationChannel;
  content: Record<string, unknown>;
  /** Obrigatório para SMS/Push se quiser persistir o parecer (GET ao recarregar). */
  campaign_id?: string;
}

/** Raw response from content-validation-service. */
export interface ContentValidationAnalyzePieceResponse {
  validation_result: Record<string, unknown>;
  specs_result?: Record<string, unknown> | null;
  orchestration_result?: Record<string, unknown> | null;
  compliance_result?: Record<string, unknown> | null;
  branding_result?: Record<string, unknown> | null;
  requires_human_approval: boolean;
  human_approval_reason?: string | null;
  failure_stage?: string | null;
  stages_completed?: string[] | null;
  final_verdict?: {
    decision?: string;       // APROVADO | REPROVADO
    summary?: string;
    failure_stage?: string | null;
    stages_completed?: string[];
    requires_human_review?: boolean;
    specs?: Record<string, unknown> | null;
    legal?: { decision?: string | null; summary?: string | null } | null;
    branding?: Record<string, unknown> | null;
    sources?: string[];
  } | null;
}

/** UI-friendly analysis result (mapped from ContentValidationAnalyzePieceResponse). */
export interface AnalyzePieceResponse {
  id: string;
  campaign_id: string;
  channel: TextChannel | "E-mail" | "App";
  is_valid: "valid" | "invalid";
  analysis_text: string;
  sources?: string[];
  analyzed_by: string;
  created_at: string;
}

export interface SubmitCreativePieceRequest {
  pieceType: "SMS" | "Push";
  text?: string;
  title?: string;
  body?: string;
  iaVerdict?: string;
  iaAnalysisText?: string;
}

export interface CampaignsResponse {
  campaigns: Campaign[];
}

export type CampaignResponse = Campaign;

// Piece Review History (Timeline)
export type PieceReviewEventType = "SUBMITTED" | "IA_VALIDATED" | "APPROVED" | "REJECTED" | "MANUALLY_REJECTED";

export interface PieceReviewEvent {
  id: string;
  campaignId: string;
  channel: string;
  pieceId: string;
  commercialSpace: string;
  eventType: PieceReviewEventType;
  iaVerdict?: string;
  rejectionReason?: string;
  actorId: string;
  actorName?: string;
  createdAt: string;
}

export interface PieceReviewHistoryResponse {
  events: PieceReviewEvent[];
}

// Campaign Status History (Horizontal Timeline)
export interface CampaignStatusEvent {
  id: string;
  campaignId: string;
  fromStatus?: string;
  toStatus: string;
  actorId: string;
  actorName?: string;
  createdAt: string;
  durationSeconds?: number;
}

export interface CampaignStatusHistoryResponse {
  events: CampaignStatusEvent[];
  currentStatus: string;
}

// My Tasks (Dashboard)
export interface TaskItem {
  id: string;
  campaignId: string;
  campaignName: string;
  taskType: string;
  description: string;
  priority: string;
  createdAt: string;
}

export interface TaskGroup {
  taskType: string;
  title: string;
  description: string;
  count: number;
  tasks: TaskItem[];
}

export interface MyTasksResponse {
  totalTasks: number;
  taskGroups: TaskGroup[];
}
