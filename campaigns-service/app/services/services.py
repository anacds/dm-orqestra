from typing import List, Optional
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status

from typing import Dict
from app.models.campaign import Campaign, CampaignStatus
from app.models.comment import Comment
from app.models.creative_piece import CreativePiece
from app.models.user_role import UserRole
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignsResponse,
    CommentCreate,
    CommentResponse,
    CreativePieceCreate,
    CreativePieceResponse,
)
from app.core.permissions import (
    get_visible_statuses_for_role,
    can_view_campaign,
    can_transition_status,
)
from app.core.s3_client import normalize_file_url
from app.core.auth_client import auth_client
import json


async def campaign_to_response(campaign: Campaign, auth_token: Optional[str] = None) -> CampaignResponse:
    """Convert Campaign model to CampaignResponse schema."""
    comments_list = None
    if campaign.comments:
        comments_list = [
            CommentResponse.model_validate(c) for c in campaign.comments
        ]
    
    creative_pieces_list = None
    if campaign.creative_pieces:
        normalized_pieces = []
        for cp in campaign.creative_pieces:
            piece_data = {
                "id": cp.id,
                "pieceType": cp.piece_type,
                "text": cp.text,
                "title": cp.title,
                "body": cp.body,
                "createdAt": cp.created_at,
                "updatedAt": cp.updated_at,
            }
            
            if cp.file_urls:
                try:
                    file_urls_dict = json.loads(cp.file_urls)
                    normalized_urls = {k: normalize_file_url(v) for k, v in file_urls_dict.items()}
                    piece_data["fileUrls"] = json.dumps(normalized_urls)
                except json.JSONDecodeError:
                    piece_data["fileUrls"] = cp.file_urls
            else:
                piece_data["fileUrls"] = None
            
            # normaliza html_file_url (para e-mail)
            if cp.html_file_url:
                piece_data["htmlFileUrl"] = normalize_file_url(cp.html_file_url)
            else:
                piece_data["htmlFileUrl"] = None
            
            normalized_pieces.append(CreativePieceResponse.model_validate(piece_data))
        creative_pieces_list = normalized_pieces
    
    response_dict = {
        "id": campaign.id,
        "name": campaign.name,
        "category": campaign.category,
        "business_objective": campaign.business_objective,
        "expected_result": campaign.expected_result,
        "requesting_area": campaign.requesting_area,
        "start_date": campaign.start_date,
        "end_date": campaign.end_date,
        "priority": campaign.priority,
        "communication_channels": campaign.communication_channels or [],
        "commercial_spaces": campaign.commercial_spaces or [],
        "target_audience_description": campaign.target_audience_description,
        "exclusion_criteria": campaign.exclusion_criteria,
        "estimated_impact_volume": campaign.estimated_impact_volume,
        "communication_tone": campaign.communication_tone,
        "execution_model": campaign.execution_model,
        "trigger_event": campaign.trigger_event,
        "recency_rule_days": campaign.recency_rule_days,
        "status": campaign.status,
        "created_by": campaign.created_by,
        "created_date": campaign.created_date,
        "comments": comments_list,
        "creative_pieces": creative_pieces_list,
    }
    
    if auth_token and campaign.created_by:
        try:
            creator = await auth_client.get_user_by_id(campaign.created_by, auth_token)
            if creator:
                created_by_name = creator.get("full_name") or creator.get("email", "Usuário")
                if created_by_name:
                    response_dict["created_by_name"] = created_by_name
        except Exception:
            pass
    
    return CampaignResponse.model_validate(response_dict)


class CampaignService:
    """Business logic for campaign operations."""
    
    @staticmethod
    async def get_campaigns(
        db: Session,
        current_user: Dict,
        auth_token: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> CampaignsResponse:
        """Get campaigns visible to user based on role and permissions."""
        user_role = current_user.get("role")
        if not user_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User role not assigned"
            )
        
        if isinstance(user_role, str):
            try:
                user_role = UserRole(user_role)
            except ValueError:
                return CampaignsResponse(campaigns=[])
        
        visible_statuses = get_visible_statuses_for_role(user_role)
        
        if not visible_statuses:
            return CampaignsResponse(campaigns=[])
        
        visible_status_values = [status.value for status in visible_statuses]
        query = db.query(Campaign)
        
        if user_role == UserRole.BUSINESS_ANALYST:
            query = query.filter(
                or_(
                    Campaign.status.in_(visible_status_values),
                    (Campaign.created_by == current_user.get("id")) & (Campaign.status == CampaignStatus.DRAFT.value)
                )
            )
        else:
            query = query.filter(Campaign.status.in_(visible_status_values))
        
        campaigns = (
            query
            .order_by(Campaign.created_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        campaign_responses = []
        for campaign in campaigns:
            response = await campaign_to_response(campaign, auth_token)
            campaign_responses.append(response)
        
        return CampaignsResponse(campaigns=campaign_responses)
    
    @staticmethod
    async def get_campaign(db: Session, campaign_id: str, current_user: Dict, auth_token: Optional[str] = None) -> CampaignResponse:
        """Get single campaign by ID if user has permission."""
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == campaign_id)
            .first()
        )
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        # verifica se usuário pode ver esta campanha baseado no role
        if not can_view_campaign(current_user, campaign):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this campaign"
            )
        
        return await campaign_to_response(campaign, auth_token)
    
    @staticmethod
    async def create_campaign(
        db: Session,
        campaign_data: CampaignCreate,
        current_user: Dict,
        auth_token: Optional[str] = None
    ) -> CampaignResponse:
        """Create a new campaign."""
        campaign = Campaign(
            id=str(uuid4()),
            name=campaign_data.name,
            category=campaign_data.category.value,
            business_objective=campaign_data.business_objective,
            expected_result=campaign_data.expected_result,
            requesting_area=campaign_data.requesting_area.value,
            start_date=campaign_data.start_date,
            end_date=campaign_data.end_date,
            priority=campaign_data.priority.value,
            communication_channels=[ch.value if hasattr(ch, 'value') else ch for ch in campaign_data.communication_channels],
            commercial_spaces=[cs.value if hasattr(cs, 'value') else cs for cs in campaign_data.commercial_spaces] if campaign_data.commercial_spaces else None,
            target_audience_description=campaign_data.target_audience_description,
            exclusion_criteria=campaign_data.exclusion_criteria,
            estimated_impact_volume=campaign_data.estimated_impact_volume,
            communication_tone=campaign_data.communication_tone.value,
            execution_model=campaign_data.execution_model.value,
            trigger_event=campaign_data.trigger_event.value if campaign_data.trigger_event else None,
            recency_rule_days=campaign_data.recency_rule_days,
            created_by=current_user.get("id"),
            status=CampaignStatus.DRAFT.value,
        )
        
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        
        return await campaign_to_response(campaign, auth_token)
    
    @staticmethod
    async def update_campaign(
        db: Session,
        campaign_id: str,
        campaign_data: CampaignUpdate,
        current_user: Dict,
        auth_token: Optional[str] = None
    ) -> CampaignResponse:
        """Update campaign if user has permission."""
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == campaign_id)
            .first()
        )
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        if not can_view_campaign(current_user, campaign):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this campaign"
            )
        
        update_data = campaign_data.model_dump(exclude_unset=True, by_alias=False)
        is_status_only_update = len(update_data) == 1 and 'status' in update_data
        
        if not is_status_only_update and campaign.status == CampaignStatus.DRAFT.value:
            if campaign.created_by != current_user.get("id"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the campaign creator can update draft campaigns"
                )
        
        if 'status' in update_data and update_data['status'] is not None:
            new_status_str = update_data['status']
            try:
                new_status = CampaignStatus(new_status_str) if isinstance(new_status_str, str) else new_status_str
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {new_status_str}"
                )
            
            current_status = campaign.status
            if isinstance(current_status, str):
                try:
                    current_status = CampaignStatus(current_status)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Invalid campaign status in database: {current_status}"
                    )
            
            # verifica se transição é permitida
            is_allowed, error_msg = can_transition_status(
                current_user, 
                current_status, 
                new_status
            )
            if not is_allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=error_msg or f"You cannot transition from {current_status.value} to {new_status.value}"
                )
            
            update_data['status'] = new_status.value
        
        enum_fields = ['category', 'requesting_area', 'priority', 'communication_tone', 'execution_model', 'trigger_event']
        array_enum_fields = ['communication_channels', 'commercial_spaces']
        
        for field, value in update_data.items():
            if field in enum_fields and value is not None:
                setattr(campaign, field, value.value if hasattr(value, 'value') else value)
            elif field in array_enum_fields and value is not None:
                setattr(campaign, field, [v.value if hasattr(v, 'value') else v for v in value])
            elif field == 'status':
                setattr(campaign, field, value)
            else:
                setattr(campaign, field, value)
        
        db.commit()
        db.refresh(campaign)
        
        return await campaign_to_response(campaign, auth_token)
    
    @staticmethod
    def delete_campaign(db: Session, campaign_id: str, current_user: Dict) -> None:
        """Delete campaign (only draft campaigns by creator)."""
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == campaign_id)
            .first()
        )
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        user_role = current_user.get("role")
        if (user_role != UserRole.BUSINESS_ANALYST.value or 
            campaign.created_by != current_user.get("id") or 
            campaign.status != CampaignStatus.DRAFT):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own drafts"
            )
        
        db.delete(campaign)
        db.commit()
    
    @staticmethod
    def add_comment(
        db: Session,
        campaign_id: str,
        comment_data: CommentCreate,
        current_user: Dict
    ) -> CommentResponse:
        """Add comment to campaign."""
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == campaign_id)
            .first()
        )
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        if not can_view_campaign(current_user, campaign):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to comment on this campaign"
            )
        
        comment = Comment(
            id=str(uuid4()),
            campaign_id=campaign_id,
            author=comment_data.author or current_user.get("full_name") or current_user.get("email"),
            role=comment_data.role,
            text=comment_data.text,
        )
        
        db.add(comment)
        db.commit()
        db.refresh(comment)
        
        return CommentResponse.model_validate(comment)
    
    @staticmethod
    def submit_creative_piece(
        db: Session,
        campaign_id: str,
        piece_data: CreativePieceCreate,
        current_user: Dict
    ) -> CreativePieceResponse:
        """Submit creative piece for campaign."""
        user_role = current_user.get("role")
        if user_role != UserRole.CREATIVE_ANALYST.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only creative analysts can submit creative pieces"
            )
        
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == campaign_id)
            .first()
        )
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        if campaign.status not in [CampaignStatus.CREATIVE_STAGE, CampaignStatus.CONTENT_ADJUSTMENT]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Creative pieces can only be submitted when campaign is in CREATIVE_STAGE or CONTENT_ADJUSTMENT"
            )
        
        existing_piece = (
            db.query(CreativePiece)
            .filter(
                CreativePiece.campaign_id == campaign_id,
                CreativePiece.piece_type == piece_data.piece_type
            )
            .first()
        )
        
        if existing_piece:
            if piece_data.piece_type == "SMS":
                existing_piece.text = piece_data.text
                existing_piece.title = None
                existing_piece.body = None
            else:  
                existing_piece.title = piece_data.title
                existing_piece.body = piece_data.body
                existing_piece.text = None
            
            db.commit()
            db.refresh(existing_piece)
            return CreativePieceResponse.model_validate(existing_piece)
        else:
            creative_piece = CreativePiece(
                id=str(uuid4()),
                campaign_id=campaign_id,
                piece_type=piece_data.piece_type,
                text=piece_data.text if piece_data.piece_type == "SMS" else None,
                title=piece_data.title if piece_data.piece_type == "Push" else None,
                body=piece_data.body if piece_data.piece_type == "Push" else None,
            )
            
            db.add(creative_piece)
            db.commit()
            db.refresh(creative_piece)
            
            return CreativePieceResponse.model_validate(creative_piece)

