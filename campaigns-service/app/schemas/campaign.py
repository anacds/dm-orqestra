from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal
from app.models.campaign import (
    CampaignStatus,
    CampaignCategory,
    RequestingArea,
    CampaignPriority,
    CommunicationTone,
    ExecutionModel,
    TriggerEvent,
)


class CommentCreate(BaseModel):
    text: str
    author: str
    role: Optional[str] = "User"


class CommentResponse(BaseModel):
    id: str
    author: str
    role: str
    text: str
    timestamp: datetime
    
    model_config = {"from_attributes": True}


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: CampaignCategory
    business_objective: str = Field(..., alias="businessObjective", min_length=1)
    expected_result: str = Field(..., alias="expectedResult", min_length=1)
    requesting_area: RequestingArea = Field(..., alias="requestingArea")
    start_date: date = Field(..., alias="startDate")
    end_date: date = Field(..., alias="endDate")
    priority: CampaignPriority
    communication_channels: List[str] = Field(..., alias="communicationChannels", min_length=1)
    commercial_spaces: Optional[List[str]] = Field(None, alias="commercialSpaces")
    target_audience_description: str = Field(..., alias="targetAudienceDescription", min_length=1)
    exclusion_criteria: str = Field(..., alias="exclusionCriteria", min_length=1)
    estimated_impact_volume: Decimal = Field(..., alias="estimatedImpactVolume", ge=0)
    communication_tone: CommunicationTone = Field(..., alias="communicationTone")
    execution_model: ExecutionModel = Field(..., alias="executionModel")
    trigger_event: Optional[TriggerEvent] = Field(None, alias="triggerEvent")
    recency_rule_days: int = Field(..., alias="recencyRuleDays", ge=0)
    
    model_config = {"populate_by_name": True}
    
    @model_validator(mode="after")
    def validate_trigger_event(self):
        """Validate that trigger_event is provided when execution_model is Event-driven"""
        if self.execution_model == ExecutionModel.EVENT_DRIVEN and not self.trigger_event:
            raise ValueError("trigger_event é obrigatório quando execution_model é Event-driven (por evento)")
        if self.execution_model != ExecutionModel.EVENT_DRIVEN and self.trigger_event:
            raise ValueError("trigger_event só pode ser especificado quando execution_model é Event-driven (por evento)")
        return self


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[CampaignCategory] = None
    business_objective: Optional[str] = Field(None, alias="businessObjective", min_length=1)
    expected_result: Optional[str] = Field(None, alias="expectedResult", min_length=1)
    requesting_area: Optional[RequestingArea] = Field(None, alias="requestingArea")
    start_date: Optional[date] = Field(None, alias="startDate")
    end_date: Optional[date] = Field(None, alias="endDate")
    priority: Optional[CampaignPriority] = None
    communication_channels: Optional[List[str]] = Field(None, alias="communicationChannels", min_length=1)
    commercial_spaces: Optional[List[str]] = Field(None, alias="commercialSpaces")
    target_audience_description: Optional[str] = Field(None, alias="targetAudienceDescription", min_length=1)
    exclusion_criteria: Optional[str] = Field(None, alias="exclusionCriteria", min_length=1)
    estimated_impact_volume: Optional[Decimal] = Field(None, alias="estimatedImpactVolume", ge=0)
    communication_tone: Optional[CommunicationTone] = Field(None, alias="communicationTone")
    execution_model: Optional[ExecutionModel] = Field(None, alias="executionModel")
    trigger_event: Optional[TriggerEvent] = Field(None, alias="triggerEvent")
    recency_rule_days: Optional[int] = Field(None, alias="recencyRuleDays", ge=0)
    status: Optional[CampaignStatus] = None
    
    model_config = {"populate_by_name": True}

class CreativePieceResponse(BaseModel):
    id: str
    piece_type: str = Field(alias="pieceType")
    text: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    file_urls: Optional[str] = Field(None, alias="fileUrls")  # JSON string for App files
    html_file_url: Optional[str] = Field(None, alias="htmlFileUrl")  # URL for E-mail HTML
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    model_config = {"from_attributes": True, "populate_by_name": True}


class PieceContentResponse(BaseModel):
    """Response for GET .../creative-pieces/{piece_id}/content."""

    content_type: str = Field(..., alias="contentType", description="e.g. text/html or image/png")
    content: str = Field(
        ...,
        description="HTML as UTF-8 string (JSON-safe) or image as data URL (data:image/png;base64,...)",
    )

    model_config = {"populate_by_name": True}


class CreativePieceCreate(BaseModel):
    piece_type: str = Field(..., alias="pieceType", description="'SMS' or 'Push'")
    text: Optional[str] = Field(None, description="Text content for SMS")
    title: Optional[str] = Field(None, max_length=50, description="Title for Push (max 50 chars)")
    body: Optional[str] = Field(None, max_length=120, description="Body for Push (max 120 chars)")
    
    model_config = {"populate_by_name": True}
    
    @model_validator(mode="after")
    def validate_piece_fields(self):
        """Validate that the correct fields are provided based on piece type"""
        if self.piece_type == "SMS":
            if not self.text:
                raise ValueError("text is required for SMS piece type")
            if self.title or self.body:
                raise ValueError("title and body should not be provided for SMS piece type")
        elif self.piece_type == "Push":
            if not self.title or not self.body:
                raise ValueError("title and body are required for Push piece type")
            if self.text:
                raise ValueError("text should not be provided for Push piece type")
        return self


class CampaignResponse(BaseModel):
    id: str
    name: str
    category: CampaignCategory
    business_objective: str = Field(alias="businessObjective")
    expected_result: str = Field(alias="expectedResult")
    requesting_area: RequestingArea = Field(alias="requestingArea")
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    priority: CampaignPriority
    communication_channels: List[str] = Field(alias="communicationChannels")
    commercial_spaces: Optional[List[str]] = Field(None, alias="commercialSpaces")
    target_audience_description: str = Field(alias="targetAudienceDescription")
    exclusion_criteria: str = Field(alias="exclusionCriteria")
    estimated_impact_volume: Decimal = Field(alias="estimatedImpactVolume")
    communication_tone: CommunicationTone = Field(alias="communicationTone")
    execution_model: ExecutionModel = Field(alias="executionModel")
    trigger_event: Optional[TriggerEvent] = Field(None, alias="triggerEvent")
    recency_rule_days: int = Field(alias="recencyRuleDays")
    status: CampaignStatus
    created_by: str = Field(alias="createdBy")
    created_by_name: Optional[str] = Field(None, alias="createdByName")
    created_date: datetime = Field(alias="createdDate")
    comments: Optional[List[CommentResponse]] = None
    creative_pieces: Optional[List[CreativePieceResponse]] = Field(None, alias="creativePieces")
    piece_reviews: Optional[List["PieceReviewResponse"]] = Field(None, alias="pieceReviews")

    model_config = {"from_attributes": True, "populate_by_name": True}


class CampaignsResponse(BaseModel):
    campaigns: List[CampaignResponse]


# --- CONTENT_REVIEW workflow (submit-for-review, piece review) ---


class PieceReviewItem(BaseModel):
    """One reviewable unit: IA verdict snapshot when submitting for review."""

    channel: str = Field(..., description="SMS | PUSH | EMAIL | APP")
    piece_id: str = Field(..., alias="pieceId")
    commercial_space: Optional[str] = Field(None, alias="commercialSpace")
    ia_verdict: str = Field(..., alias="iaVerdict", description="approved | rejected | warning")

    model_config = {"populate_by_name": True}


class SubmitForReviewRequest(BaseModel):
    """Request body for POST /campaigns/{id}/submit-for-review."""

    piece_reviews: List[PieceReviewItem] = Field(..., alias="pieceReviews", min_length=1)

    model_config = {"populate_by_name": True}


class PieceReviewResponse(BaseModel):
    """Per-piece review state returned in GET campaign when status is CONTENT_REVIEW."""

    id: str
    campaign_id: str = Field(alias="campaignId")
    channel: str
    piece_id: str = Field(alias="pieceId")
    commercial_space: str = Field(alias="commercialSpace", default="")
    ia_verdict: str = Field(alias="iaVerdict")
    human_verdict: str = Field(alias="humanVerdict")
    reviewed_at: Optional[datetime] = Field(None, alias="reviewedAt")
    reviewed_by: Optional[str] = Field(None, alias="reviewedBy")
    reviewed_by_name: Optional[str] = Field(None, alias="reviewedByName")
    rejection_reason: Optional[str] = Field(None, alias="rejectionReason")

    model_config = {"from_attributes": True, "populate_by_name": True}


class ReviewPieceRequest(BaseModel):
    """Request body for POST /campaigns/{id}/pieces/review."""

    channel: str = Field(..., description="SMS | PUSH | EMAIL | APP")
    piece_id: str = Field(..., alias="pieceId")
    commercial_space: Optional[str] = Field(None, alias="commercialSpace")
    action: str = Field(..., description="approve | reject | manually_reject")
    rejection_reason: Optional[str] = Field(None, alias="rejectionReason", max_length=2000)

    model_config = {"populate_by_name": True}


class EnhanceObjectiveRequest(BaseModel):
    text: str = Field(..., min_length=1)
    field_name: str = Field(..., description="Name of the field to enhance (e.g., 'businessObjective', 'expectedResult', 'targetAudienceDescription', 'exclusionCriteria')")


class EnhanceObjectiveResponse(BaseModel):
    enhanced_text: str = Field(alias="enhancedText")
    explanation: str
    
    model_config = {"populate_by_name": True}


class GenerateTextRequest(BaseModel):
    campaign_id: str = Field(..., alias="campaignId")
    channel: str = Field(..., description="Channel type: 'SMS' or 'Push'")
    
    model_config = {"populate_by_name": True}


class GenerateTextResponse(BaseModel):
    text: Optional[str] = None  # For SMS
    title: Optional[str] = None  # For Push
    body: Optional[str] = None  # For Push
    channel: str
    
    model_config = {"populate_by_name": True}
    
    @model_validator(mode="after")
    def validate_channel_fields(self):
        """Validate that the correct fields are provided based on channel"""
        if self.channel == "SMS":
            if self.text is None:
                raise ValueError("text is required for SMS channel")
            if self.title is not None or self.body is not None:
                raise ValueError("title and body should not be provided for SMS channel")
        elif self.channel == "Push":
            if self.title is None or self.body is None:
                raise ValueError("title and body are required for Push channel")
            if self.text is not None:
                raise ValueError("text should not be provided for Push channel")
        return self
