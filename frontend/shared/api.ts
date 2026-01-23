export type UserRole = "Analista de negócios" | "Analista de criação" | "Analista de campanhas";

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

export interface AnalyzePieceRequest {
  campaignId: string;
  channel: TextChannel;
  content: {
    text?: string;
    title?: string;
    body?: string;
  };
}

export interface AnalyzePieceResponse {
  id: string;
  campaign_id: string;
  channel: TextChannel;
  is_valid: "valid" | "invalid" | "warning";
  analysis_text: string;
  analyzed_by: string;
  created_at: string;
}

export interface SubmitCreativePieceRequest {
  pieceType: "SMS" | "Push";
  text?: string;
  title?: string;
  body?: string;
}

export interface CampaignsResponse {
  campaigns: Campaign[];
}

export type CampaignResponse = Campaign;
