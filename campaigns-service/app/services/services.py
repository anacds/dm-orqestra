from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status

from app.models.campaign import Campaign, CampaignStatus
from app.models.comment import Comment
from app.models.creative_piece import CreativePiece
from app.models.piece_review import PieceReview, HumanVerdict
from app.models.piece_review_event import PieceReviewEvent, PieceReviewEventType
from app.models.campaign_status_event import CampaignStatusEvent
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
    PieceReviewResponse,
    ReviewPieceRequest,
    SubmitForReviewRequest,
)
from app.core.permissions import (
    get_visible_statuses_for_role,
    can_view_campaign,
    can_transition_status,
)
from app.core.s3_client import normalize_file_url
from app.core.auth_client import auth_client
from app.core.metrics import (
    CAMPAIGN_OPERATIONS,
    STATUS_TRANSITIONS,
    REVIEW_SUBMISSIONS,
    REVIEW_VERDICTS,
)
import json


def _piece_review_to_response(pr: PieceReview) -> dict:
    return {
        "id": pr.id,
        "campaignId": pr.campaign_id,
        "channel": pr.channel,
        "pieceId": pr.piece_id,
        "commercialSpace": pr.commercial_space or "",
        "iaVerdict": pr.ia_verdict,
        "humanVerdict": pr.human_verdict,
        "reviewedAt": pr.reviewed_at,
        "reviewedBy": pr.reviewed_by,
        "rejectionReason": pr.rejection_reason,
    }


def _is_piece_finally_approved(ia: str | None, human: str) -> bool:
    """True if piece is approved.

    - IA approved and not manually rejected → approved
    - IA rejected/None and human approved → approved
    """
    if ia == "approved":
        return human != HumanVerdict.MANUALLY_REJECTED.value
    # ia is rejected, warning, or None (não validado) → depende do humano
    return human == HumanVerdict.APPROVED.value


def _is_piece_finally_rejected(ia: str | None, human: str) -> bool:
    """True if piece is rejected.

    - IA approved and manually rejected → rejected
    - IA rejected/None and human rejected → rejected
    """
    if ia == "approved":
        return human == HumanVerdict.MANUALLY_REJECTED.value
    # ia is rejected, warning, or None (não validado) → depende do humano
    return human == HumanVerdict.REJECTED.value


async def campaign_to_response(
    campaign: Campaign,
    auth_token: Optional[str] = None,
    db: Optional[Session] = None,
) -> CampaignResponse:
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

    piece_reviews_list = None
    _status = getattr(campaign, "status", None)
    _status_val = _status.value if hasattr(_status, "value") else (_status.strip() if isinstance(_status, str) else None)
    if db and _status_val in (
        CampaignStatus.CONTENT_REVIEW.value,
        CampaignStatus.CONTENT_ADJUSTMENT.value,
    ):
        rows = db.query(PieceReview).filter(PieceReview.campaign_id == campaign.id).all()
        if rows:
            out = []
            for r in rows:
                d = _piece_review_to_response(r)
                if r.reviewed_by and auth_token:
                    try:
                        u = await auth_client.get_user_by_id(r.reviewed_by, auth_token)
                        if u:
                            d["reviewedByName"] = u.get("full_name") or u.get("email") or r.reviewed_by
                    except Exception:
                        pass
                out.append(PieceReviewResponse.model_validate(d))
            piece_reviews_list = out
    
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
        "piece_reviews": piece_reviews_list,
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
            response = await campaign_to_response(campaign, auth_token, db)
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
        
        return await campaign_to_response(campaign, auth_token, db)
    
    @staticmethod
    async def create_campaign(
        db: Session,
        campaign_data: CampaignCreate,
        current_user: Dict,
        auth_token: Optional[str] = None
    ) -> CampaignResponse:
        """Create a new campaign."""
        CAMPAIGN_OPERATIONS.labels(operation="create").inc()
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
        
        # Record initial status event
        status_event = CampaignStatusEvent(
            campaign_id=campaign.id,
            from_status=None,
            to_status=CampaignStatus.DRAFT.value,
            actor_id=current_user.get("id") or "",
        )
        db.add(status_event)
        
        db.commit()
        db.refresh(campaign)
        
        return await campaign_to_response(campaign, auth_token, db)
    
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
            
            # CONTENT_REVIEW -> CONTENT_ADJUSTMENT ou CAMPAIGN_BUILDING: validar piece_reviews
            if current_status == CampaignStatus.CONTENT_REVIEW and new_status in (
                CampaignStatus.CONTENT_ADJUSTMENT,
                CampaignStatus.CAMPAIGN_BUILDING,
            ):
                rows = db.query(PieceReview).filter(PieceReview.campaign_id == campaign_id).all()
                if not rows:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Nenhum parecer de peça encontrado. Submeta para revisão antes de alterar o status.",
                    )
                any_rejected = any(
                    _is_piece_finally_rejected(r.ia_verdict, r.human_verdict) for r in rows
                )
                all_approved = all(
                    _is_piece_finally_approved(r.ia_verdict, r.human_verdict) for r in rows
                )
                if new_status == CampaignStatus.CONTENT_ADJUSTMENT and not any_rejected:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Solicitar ajustes só é permitido quando ao menos uma peça está reprovada.",
                    )
                if new_status == CampaignStatus.CAMPAIGN_BUILDING and not all_approved:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Aprovar conteúdo só é permitido quando todas as peças estão aprovadas.",
                    )
            
            update_data['status'] = new_status.value
            
            # Record status change event
            status_event = CampaignStatusEvent(
                campaign_id=campaign_id,
                from_status=current_status.value if hasattr(current_status, 'value') else current_status,
                to_status=new_status.value,
                actor_id=current_user.get("id") or "",
            )
            db.add(status_event)
        
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
        
        return await campaign_to_response(campaign, auth_token, db)
    
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

    @staticmethod
    async def submit_for_review(
        db: Session,
        campaign_id: str,
        body: SubmitForReviewRequest,
        current_user: Dict,
        auth_token: Optional[str] = None,
    ) -> CampaignResponse:
        """Creation analyst submits campaign for review. Inserts piece_reviews (IA verdict snapshot) and transitions to CONTENT_REVIEW."""
        CAMPAIGN_OPERATIONS.labels(operation="submit_for_review").inc()
        if current_user.get("role") != UserRole.CREATIVE_ANALYST.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only creative analysts can submit for review",
            )
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
        if campaign.status not in (CampaignStatus.CREATIVE_STAGE.value, CampaignStatus.CONTENT_ADJUSTMENT.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Submit for review only allowed when campaign is CREATIVE_STAGE or CONTENT_ADJUSTMENT",
            )
        db.query(PieceReview).filter(PieceReview.campaign_id == campaign_id).delete()
        actor_id = current_user.get("id") or ""
        for item in body.piece_reviews:
            ch = (item.channel or "").upper().replace("-", "").replace(" ", "")
            if ch == "E-MAIL":
                ch = "EMAIL"
            space = (item.commercial_space or "").strip() or ""
            ia = item.ia_verdict
            if ia is not None:
                ia = ia.lower()
                if ia not in ("approved", "rejected"):
                    ia = None  # valor inválido → tratar como não validado
            # Create current state record
            pr = PieceReview(
                campaign_id=campaign_id,
                channel=ch,
                piece_id=item.piece_id,
                commercial_space=space,
                ia_verdict=ia,
                human_verdict=HumanVerdict.PENDING.value,
            )
            db.add(pr)
            # Create history event (immutable)
            event = PieceReviewEvent(
                campaign_id=campaign_id,
                channel=ch,
                piece_id=item.piece_id,
                commercial_space=space,
                event_type=PieceReviewEventType.SUBMITTED.value,
                ia_verdict=ia,
                actor_id=actor_id,
            )
            db.add(event)
        
        # Record status change event
        old_status = campaign.status
        campaign.status = CampaignStatus.CONTENT_REVIEW.value
        status_event = CampaignStatusEvent(
            campaign_id=campaign_id,
            from_status=old_status,
            to_status=CampaignStatus.CONTENT_REVIEW.value,
            actor_id=actor_id,
        )
        db.add(status_event)
        STATUS_TRANSITIONS.labels(from_status=old_status, to_status=CampaignStatus.CONTENT_REVIEW.value).inc()

        for item in body.piece_reviews:
            REVIEW_SUBMISSIONS.labels(channel=(item.channel or "").upper()).inc()
        
        db.commit()
        db.refresh(campaign)
        return await campaign_to_response(campaign, auth_token, db)

    @staticmethod
    async def review_piece(
        db: Session,
        campaign_id: str,
        body: ReviewPieceRequest,
        current_user: Dict,
        auth_token: Optional[str] = None,
    ) -> CampaignResponse:
        """Marketing manager approves/rejects a piece (or manually rejects an IA-approved piece)."""
        CAMPAIGN_OPERATIONS.labels(operation="review_piece").inc()
        if current_user.get("role") != UserRole.MARKETING_MANAGER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only marketing managers can review pieces",
            )
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
        if campaign.status != CampaignStatus.CONTENT_REVIEW.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Review only allowed when campaign is CONTENT_REVIEW",
            )
        ch = (body.channel or "").upper().replace("-", "").replace(" ", "")
        if ch == "E-MAIL":
            ch = "EMAIL"
        space = (body.commercial_space or "").strip() or ""
        action = (body.action or "").lower()
        if action not in ("approve", "reject", "manually_reject"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="action must be approve, reject, or manually_reject",
            )
        pr = (
            db.query(PieceReview)
            .filter(
                PieceReview.campaign_id == campaign_id,
                PieceReview.channel == ch,
                PieceReview.piece_id == body.piece_id,
                PieceReview.commercial_space == space,
            )
            .first()
        )
        if not pr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Piece review not found for this campaign/channel/piece",
            )
        human = HumanVerdict.PENDING.value
        event_type = PieceReviewEventType.APPROVED.value
        if action == "approve":
            human = HumanVerdict.APPROVED.value
            event_type = PieceReviewEventType.APPROVED.value
        elif action == "reject":
            human = HumanVerdict.REJECTED.value
            event_type = PieceReviewEventType.REJECTED.value
        else:
            human = HumanVerdict.MANUALLY_REJECTED.value
            event_type = PieceReviewEventType.MANUALLY_REJECTED.value
        
        REVIEW_VERDICTS.labels(channel=ch, verdict=action).inc()

        actor_id = current_user.get("id") or ""
        rejection_reason = None
        if action in ("reject", "manually_reject") and body.rejection_reason is not None:
            reason = (body.rejection_reason or "").strip()
            rejection_reason = reason if reason else None
        
        # Update current state
        pr.human_verdict = human
        pr.reviewed_at = datetime.now(timezone.utc)
        pr.reviewed_by = actor_id
        pr.rejection_reason = rejection_reason
        
        # Create history event (immutable)
        event = PieceReviewEvent(
            campaign_id=campaign_id,
            channel=ch,
            piece_id=body.piece_id,
            commercial_space=space,
            event_type=event_type,
            rejection_reason=rejection_reason,
            actor_id=actor_id,
        )
        db.add(event)
        db.commit()
        db.refresh(campaign)
        return await campaign_to_response(campaign, auth_token, db)

    @staticmethod
    async def update_ia_verdict(
        db: Session,
        campaign_id: str,
        body: "UpdateIaVerdictRequest",
        current_user: Dict,
        auth_token: Optional[str] = None,
    ) -> CampaignResponse:
        """Marketing manager updates ia_verdict for a piece that was submitted without AI validation."""
        from app.schemas.campaign import UpdateIaVerdictRequest  # noqa: F811

        if current_user.get("role") != UserRole.MARKETING_MANAGER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only marketing managers can update IA verdict post-submission",
            )
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
        if campaign.status != CampaignStatus.CONTENT_REVIEW.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="IA verdict update only allowed when campaign is CONTENT_REVIEW",
            )
        ch = (body.channel or "").upper().replace("-", "").replace(" ", "")
        if ch == "E-MAIL":
            ch = "EMAIL"
        space = (body.commercial_space or "").strip() or ""
        ia = (body.ia_verdict or "").lower()
        if ia not in ("approved", "rejected"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ia_verdict must be 'approved' or 'rejected'",
            )
        pr = (
            db.query(PieceReview)
            .filter(
                PieceReview.campaign_id == campaign_id,
                PieceReview.channel == ch,
                PieceReview.piece_id == body.piece_id,
                PieceReview.commercial_space == space,
            )
            .first()
        )
        if not pr:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Piece review not found for this campaign/channel/piece",
            )
        actor_id = current_user.get("id") or ""

        # Update current state
        pr.ia_verdict = ia

        # Create history event (immutable)
        event = PieceReviewEvent(
            campaign_id=campaign_id,
            channel=ch,
            piece_id=body.piece_id,
            commercial_space=space,
            event_type=PieceReviewEventType.IA_VALIDATED.value,
            ia_verdict=ia,
            actor_id=actor_id,
        )
        db.add(event)
        db.commit()
        db.refresh(campaign)
        return await campaign_to_response(campaign, auth_token, db)

    @staticmethod
    async def get_piece_review_history(
        db: Session,
        campaign_id: str,
        auth_token: Optional[str] = None,
    ) -> List[dict]:
        """Get the full history of piece review events for a campaign."""
        from app.schemas.campaign import PieceReviewEventResponse
        
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
        
        events = (
            db.query(PieceReviewEvent)
            .filter(PieceReviewEvent.campaign_id == campaign_id)
            .order_by(PieceReviewEvent.created_at.asc())
            .all()
        )
        
        result = []
        for ev in events:
            ev_dict = {
                "id": ev.id,
                "campaignId": ev.campaign_id,
                "channel": ev.channel,
                "pieceId": ev.piece_id,
                "commercialSpace": ev.commercial_space or "",
                "eventType": ev.event_type,
                "iaVerdict": ev.ia_verdict,
                "rejectionReason": ev.rejection_reason,
                "actorId": ev.actor_id,
                "actorName": None,
                "createdAt": ev.created_at,
            }
            # Fetch actor name from auth service
            if auth_token and ev.actor_id:
                try:
                    user = await auth_client.get_user_by_id(ev.actor_id, auth_token)
                    if user:
                        ev_dict["actorName"] = user.get("full_name") or user.get("email") or ev.actor_id
                except Exception:
                    pass
            result.append(PieceReviewEventResponse.model_validate(ev_dict))
        
        return result

    @staticmethod
    async def get_status_history(
        db: Session,
        campaign_id: str,
        auth_token: Optional[str] = None,
    ) -> List[dict]:
        """Get the full history of status transitions for a campaign."""
        from app.schemas.campaign import CampaignStatusEventResponse
        
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
        
        events = (
            db.query(CampaignStatusEvent)
            .filter(CampaignStatusEvent.campaign_id == campaign_id)
            .order_by(CampaignStatusEvent.created_at.asc())
            .all()
        )
        
        result = []
        for i, ev in enumerate(events):
            # Calculate duration: time until next event, or None if current
            duration_seconds = None
            if i < len(events) - 1:
                next_event = events[i + 1]
                duration_seconds = int((next_event.created_at - ev.created_at).total_seconds())
            
            ev_dict = {
                "id": ev.id,
                "campaignId": ev.campaign_id,
                "fromStatus": ev.from_status,
                "toStatus": ev.to_status,
                "actorId": ev.actor_id,
                "actorName": None,
                "createdAt": ev.created_at,
                "durationSeconds": duration_seconds,
            }
            # Fetch actor name from auth service
            if auth_token and ev.actor_id:
                try:
                    user = await auth_client.get_user_by_id(ev.actor_id, auth_token)
                    if user:
                        ev_dict["actorName"] = user.get("full_name") or user.get("email") or ev.actor_id
                except Exception:
                    pass
            result.append(CampaignStatusEventResponse.model_validate(ev_dict))
        
        return result

    @staticmethod
    async def get_my_tasks(
        db: Session,
        current_user: Dict,
    ) -> Dict:
        """Get personalized task list based on user role."""
        from app.schemas.campaign import TaskItem, TaskGroup
        
        user_id = current_user.get("id") or ""
        role = current_user.get("role") or ""
        
        task_groups = []
        
        if role == UserRole.BUSINESS_ANALYST.value:
            # Drafts created by this user that need to be sent to creative
            drafts = (
                db.query(Campaign)
                .filter(
                    Campaign.status == CampaignStatus.DRAFT.value,
                    Campaign.created_by == user_id
                )
                .order_by(Campaign.created_date.desc())
                .all()
            )
            if drafts:
                task_groups.append(TaskGroup(
                    taskType="send_to_creative",
                    title="Enviar para Criação",
                    description="Campanhas em rascunho prontas para enviar à equipe de criação",
                    count=len(drafts),
                    tasks=[TaskItem(
                        id=f"send_{c.id}",
                        campaignId=c.id,
                        campaignName=c.name,
                        taskType="send_to_creative",
                        description="Enviar para etapa criativa",
                        priority=c.priority or "Normal",
                        createdAt=c.created_date,
                    ) for c in drafts]
                ))

        elif role == UserRole.MARKETING_MANAGER.value:
            # Campaigns in content review that need piece approval
            in_review = (
                db.query(Campaign)
                .filter(Campaign.status == CampaignStatus.CONTENT_REVIEW.value)
                .order_by(Campaign.created_date.desc())
                .all()
            )
            if in_review:
                task_groups.append(TaskGroup(
                    taskType="review_content",
                    title="Aprovar Conteúdo",
                    description="Campanhas com peças criativas aguardando sua aprovação",
                    count=len(in_review),
                    tasks=[TaskItem(
                        id=f"review_{c.id}",
                        campaignId=c.id,
                        campaignName=c.name,
                        taskType="review_content",
                        description="Revisar e aprovar peças criativas",
                        priority=c.priority or "Normal",
                        createdAt=c.created_date,
                    ) for c in in_review]
                ))
        
        elif role == UserRole.CREATIVE_ANALYST.value:
            # 1. Campaigns in creative stage that need pieces
            creative_stage = (
                db.query(Campaign)
                .filter(Campaign.status == CampaignStatus.CREATIVE_STAGE.value)
                .order_by(Campaign.created_date.desc())
                .all()
            )
            if creative_stage:
                task_groups.append(TaskGroup(
                    taskType="create_pieces",
                    title="Criar Peças",
                    description="Campanhas aguardando criação de peças criativas",
                    count=len(creative_stage),
                    tasks=[TaskItem(
                        id=f"create_{c.id}",
                        campaignId=c.id,
                        campaignName=c.name,
                        taskType="create_pieces",
                        description=f"Criar peças para {', '.join(c.communication_channels or [])}",
                        priority=c.priority or "Normal",
                        createdAt=c.created_date,
                    ) for c in creative_stage]
                ))
            
            # 2. Campaigns in content adjustment that need fixes
            adjustments = (
                db.query(Campaign)
                .filter(Campaign.status == CampaignStatus.CONTENT_ADJUSTMENT.value)
                .order_by(Campaign.created_date.desc())
                .all()
            )
            if adjustments:
                task_groups.append(TaskGroup(
                    taskType="adjust_pieces",
                    title="Ajustar Peças",
                    description="Campanhas com peças rejeitadas que precisam de ajustes",
                    count=len(adjustments),
                    tasks=[TaskItem(
                        id=f"adjust_{c.id}",
                        campaignId=c.id,
                        campaignName=c.name,
                        taskType="adjust_pieces",
                        description="Corrigir peças rejeitadas",
                        priority=c.priority or "Normal",
                        createdAt=c.created_date,
                    ) for c in adjustments]
                ))
        
        elif role == UserRole.CAMPAIGN_ANALYST.value:
            # Campaigns ready to publish
            ready_to_publish = (
                db.query(Campaign)
                .filter(Campaign.status == CampaignStatus.CAMPAIGN_BUILDING.value)
                .order_by(Campaign.created_date.desc())
                .all()
            )
            if ready_to_publish:
                task_groups.append(TaskGroup(
                    taskType="publish_campaign",
                    title="Publicar Campanha",
                    description="Campanhas aprovadas prontas para publicação",
                    count=len(ready_to_publish),
                    tasks=[TaskItem(
                        id=f"publish_{c.id}",
                        campaignId=c.id,
                        campaignName=c.name,
                        taskType="publish_campaign",
                        description="Publicar campanha",
                        priority=c.priority or "Normal",
                        createdAt=c.created_date,
                    ) for c in ready_to_publish]
                ))
        
        total_tasks = sum(g.count for g in task_groups)
        
        return {
            "totalTasks": total_tasks,
            "taskGroups": task_groups,
        }

