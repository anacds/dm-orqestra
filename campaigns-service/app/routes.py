import base64
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query, Response
from sqlalchemy.orm import Session
from typing import Dict, Optional
from uuid import uuid4
import json
import logging

from app.core.database import get_db
from app.dependencies import get_current_user, get_token_from_cookie_or_header
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignsResponse,
    CampaignStatusHistoryResponse,
    CommentCreate,
    CommentResponse,
    CreativePieceCreate,
    CreativePieceResponse,
    MyTasksResponse,
    PieceContentResponse,
    PieceReviewHistoryResponse,
    ReviewPieceRequest,
    SubmitForReviewRequest,
    UpdateIaVerdictRequest,
)
from app.models.user_role import UserRole
from app.models.campaign import Campaign, CampaignStatus
from app.models.creative_piece import CreativePiece
from app.core.permissions import require_business_analyst, require_marketing_manager
from app.services.services import CampaignService
from app.services.file_upload import (
    upload_app_file,
    upload_email_file,
    update_app_file_urls,
    extract_file_key_from_url,
    get_app_file_urls_dict,
    download_file_from_url,
)
from app.core.s3_client import normalize_file_url, delete_file, get_file
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_creative_analyst(current_user: Dict) -> None:
    """Raise 403 if user is not a creative analyst."""
    if current_user.get("role") != UserRole.CREATIVE_ANALYST.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only creative analysts can perform this action"
        )


def _require_campaign_status_for_creative_work(campaign: Campaign) -> None:
    """Raise 403 if campaign is not in creative stage."""
    if campaign.status not in [CampaignStatus.CREATIVE_STAGE, CampaignStatus.CONTENT_ADJUSTMENT]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action is only allowed when campaign is in CREATIVE_STAGE or CONTENT_ADJUSTMENT status"
        )


def _get_campaign_or_404(db: Session, campaign_id: str) -> Campaign:
    """Get campaign by ID or raise 404."""
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    return campaign


def normalize_creative_piece_response(piece) -> dict:
    """Normalize creative piece file URLs for response."""
    data = {
        "id": piece.id,
        "pieceType": piece.piece_type,
        "text": piece.text,
        "title": piece.title,
        "body": piece.body,
        "createdAt": piece.created_at,
        "updatedAt": piece.updated_at,
    }
    
    if piece.file_urls:
        try:
            file_urls_dict = json.loads(piece.file_urls)
            normalized_urls = {k: normalize_file_url(v) for k, v in file_urls_dict.items()}
            data["fileUrls"] = json.dumps(normalized_urls)
        except json.JSONDecodeError:
            data["fileUrls"] = piece.file_urls
    else:
        data["fileUrls"] = None
    
    if piece.html_file_url:
        data["htmlFileUrl"] = normalize_file_url(piece.html_file_url)
    else:
        data["htmlFileUrl"] = None
    
    return data


@router.get("", response_model=CampaignsResponse)
async def get_campaigns(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    auth_token: str = Depends(get_token_from_cookie_or_header),
):
    return await CampaignService.get_campaigns(db, current_user, auth_token, skip, limit)


@router.get("/my-tasks", response_model=MyTasksResponse)
async def get_my_tasks(
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    """Get personalized task list for the current user based on their role."""
    return await CampaignService.get_my_tasks(db, current_user)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    auth_token: str = Depends(get_token_from_cookie_or_header),
):
    return await CampaignService.get_campaign(db, campaign_id, current_user, auth_token)


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    campaign_data: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    auth_token: str = Depends(get_token_from_cookie_or_header),
):
    require_business_analyst(current_user)
    return await CampaignService.create_campaign(db, campaign_data, current_user, auth_token)


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    campaign_data: CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    auth_token: str = Depends(get_token_from_cookie_or_header),
):
    return await CampaignService.update_campaign(db, campaign_id, campaign_data, current_user, auth_token)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    CampaignService.delete_campaign(db, campaign_id, current_user)
    return None


@router.post("/{campaign_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    campaign_id: str,
    comment_data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    return CampaignService.add_comment(db, campaign_id, comment_data, current_user)


@router.post("/{campaign_id}/submit-for-review", response_model=CampaignResponse)
async def submit_for_review(
    campaign_id: str,
    body: SubmitForReviewRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    auth_token: str = Depends(get_token_from_cookie_or_header),
):
    """Creation analyst submits campaign for review. Sends IA verdict snapshot per piece and transitions to CONTENT_REVIEW."""
    _require_creative_analyst(current_user)
    _get_campaign_or_404(db, campaign_id)
    return await CampaignService.submit_for_review(db, campaign_id, body, current_user, auth_token)


@router.post("/{campaign_id}/pieces/review", response_model=CampaignResponse)
async def review_piece(
    campaign_id: str,
    body: ReviewPieceRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    auth_token: str = Depends(get_token_from_cookie_or_header),
):
    """Marketing manager approves/rejects a piece (or manually rejects an IA-approved piece)."""
    require_marketing_manager(current_user)
    _get_campaign_or_404(db, campaign_id)
    return await CampaignService.review_piece(db, campaign_id, body, current_user, auth_token)


@router.patch("/{campaign_id}/piece-reviews/ia-verdict", response_model=CampaignResponse)
async def update_ia_verdict(
    campaign_id: str,
    body: UpdateIaVerdictRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    auth_token: str = Depends(get_token_from_cookie_or_header),
):
    """Marketing manager updates IA verdict for a piece that was submitted without AI validation."""
    require_marketing_manager(current_user)
    _get_campaign_or_404(db, campaign_id)
    return await CampaignService.update_ia_verdict(db, campaign_id, body, current_user, auth_token)


@router.get("/{campaign_id}/piece-review-history", response_model=PieceReviewHistoryResponse)
async def get_piece_review_history(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    auth_token: str = Depends(get_token_from_cookie_or_header),
):
    """Get the full history of piece review events for a campaign (timeline)."""
    _get_campaign_or_404(db, campaign_id)
    events = await CampaignService.get_piece_review_history(db, campaign_id, auth_token)
    return PieceReviewHistoryResponse(events=events)


@router.get("/{campaign_id}/status-history", response_model=CampaignStatusHistoryResponse)
async def get_status_history(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
    auth_token: str = Depends(get_token_from_cookie_or_header),
):
    """Get the full history of status transitions for a campaign (horizontal timeline)."""
    campaign = _get_campaign_or_404(db, campaign_id)
    events = await CampaignService.get_status_history(db, campaign_id, auth_token)
    return CampaignStatusHistoryResponse(events=events, currentStatus=campaign.status)


@router.post("/{campaign_id}/creative-pieces", response_model=CreativePieceResponse, status_code=status.HTTP_201_CREATED)
async def submit_creative_piece(
    campaign_id: str,
    piece_data: CreativePieceCreate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    _require_creative_analyst(current_user)
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_campaign_status_for_creative_work(campaign)
    return CampaignService.submit_creative_piece(db, campaign_id, piece_data, current_user)


@router.post("/{campaign_id}/creative-pieces/upload-app", response_model=CreativePieceResponse, status_code=status.HTTP_201_CREATED)
async def upload_app_creative_piece(
    campaign_id: str,
    commercial_space: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    _require_creative_analyst(current_user)
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_campaign_status_for_creative_work(campaign)
    
    existing_piece = (
        db.query(CreativePiece)
        .filter(
            CreativePiece.campaign_id == campaign_id,
            CreativePiece.piece_type == "App"
        )
        .first()
    )
    
    if existing_piece and existing_piece.file_urls:
        try:
            current_file_urls = json.loads(existing_piece.file_urls)
            if commercial_space in current_file_urls:
                old_file_url = current_file_urls[commercial_space]
                file_key = extract_file_key_from_url(old_file_url, settings.S3_BUCKET_NAME)
                if file_key:
                    try:
                        delete_file(file_key)
                    except Exception as e:
                        logger.warning(f"failed to delete old file: {e}")
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"error processing old file urls: {e}")
    
    file_url = await upload_app_file(campaign, commercial_space, file, db)
    current_file_urls = existing_piece.file_urls if existing_piece else None
    updated_file_urls = update_app_file_urls(current_file_urls, commercial_space, file_url)
    
    if existing_piece:
        existing_piece.file_urls = updated_file_urls
        db.commit()
        db.refresh(existing_piece)
        return CreativePieceResponse.model_validate(normalize_creative_piece_response(existing_piece))
    else:
        creative_piece = CreativePiece(
            id=str(uuid4()),
            campaign_id=campaign_id,
            piece_type="App",
            file_urls=updated_file_urls,
        )
        db.add(creative_piece)
        db.commit()
        db.refresh(creative_piece)
        return CreativePieceResponse.model_validate(normalize_creative_piece_response(creative_piece))


@router.post("/{campaign_id}/creative-pieces/upload-email", response_model=CreativePieceResponse, status_code=status.HTTP_201_CREATED)
async def upload_email_creative_piece(
    campaign_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    _require_creative_analyst(current_user)
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_campaign_status_for_creative_work(campaign)
    
    existing_piece = (
        db.query(CreativePiece)
        .filter(
            CreativePiece.campaign_id == campaign_id,
            CreativePiece.piece_type == "E-mail"
        )
        .first()
    )
    
    if existing_piece and existing_piece.html_file_url:
        try:
            file_key = extract_file_key_from_url(existing_piece.html_file_url, settings.S3_BUCKET_NAME)
            if file_key:
                delete_file(file_key)
        except Exception as e:
            logger.warning(f"failed to delete old file: {e}")
    
    file_url = await upload_email_file(campaign, file, db)
    
    if existing_piece:
        existing_piece.html_file_url = file_url
        db.commit()
        db.refresh(existing_piece)
        return CreativePieceResponse.model_validate(normalize_creative_piece_response(existing_piece))
    else:
        creative_piece = CreativePiece(
            id=str(uuid4()),
            campaign_id=campaign_id,
            piece_type="E-mail",
            html_file_url=file_url,
        )
        db.add(creative_piece)
        db.commit()
        db.refresh(creative_piece)
        return CreativePieceResponse.model_validate(normalize_creative_piece_response(creative_piece))


@router.get(
    "/{campaign_id}/creative-pieces/{piece_id}/content",
    response_model=PieceContentResponse,
    summary="Download piece content",
    description="Returns HTML (JSON-safe string) or image (base64 data URL). For App pieces, use ?commercial_space=.",
)
async def download_piece_content(
    campaign_id: str,
    piece_id: str,
    commercial_space: Optional[str] = Query(None, description="Required for App pieces; use the commercial space key"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    """Download creative piece content from S3. E-mail -> HTML (escaped for JSON). App -> image as base64 data URL."""
    _get_campaign_or_404(db, campaign_id)
    piece = (
        db.query(CreativePiece)
        .filter(
            CreativePiece.campaign_id == campaign_id,
            CreativePiece.id == piece_id,
        )
        .first()
    )
    if not piece:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative piece not found")

    if piece.piece_type == "E-mail":
        if not piece.html_file_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="E-mail piece has no HTML file",
            )
        file_key = extract_file_key_from_url(piece.html_file_url, settings.S3_BUCKET_NAME)
        if not file_key:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid HTML file URL")
        try:
            body, content_type = get_file(file_key)
        except Exception as e:
            logger.exception("download piece content: get_file failed for %s: %s", file_key, e)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch file from storage") from e
        try:
            html = body.decode("utf-8")
        except UnicodeDecodeError:
            try:
                html = body.decode("latin-1")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="HTML file could not be decoded as UTF-8 or Latin-1",
                )
        return PieceContentResponse(content_type=content_type, content=html)

    if piece.piece_type == "App":
        if not commercial_space:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="commercial_space query param is required for App pieces",
            )
        urls = get_app_file_urls_dict(piece.file_urls)
        file_url = urls.get(commercial_space)
        if not file_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No file for commercial space '{commercial_space}'",
            )
        file_key = extract_file_key_from_url(file_url, settings.S3_BUCKET_NAME)
        if not file_key:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid file URL")
        try:
            body, content_type = get_file(file_key)
        except Exception as e:
            logger.exception("download piece content: get_file failed for %s: %s", file_key, e)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch file from storage") from e
        b64 = base64.b64encode(body).decode("ascii")
        data_url = f"data:{content_type};base64,{b64}"
        return PieceContentResponse(content_type=content_type, content=data_url)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Download not supported for SMS or Push pieces",
    )


@router.delete("/{campaign_id}/creative-pieces/app/{commercial_space}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app_creative_piece(
    campaign_id: str,
    commercial_space: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    _require_creative_analyst(current_user)
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_campaign_status_for_creative_work(campaign)
    
    app_piece = (
        db.query(CreativePiece)
        .filter(
            CreativePiece.campaign_id == campaign_id,
            CreativePiece.piece_type == "App"
        )
        .first()
    )
    
    if not app_piece or not app_piece.file_urls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creative piece not found"
        )
    
    try:
        file_urls = json.loads(app_piece.file_urls)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file URLs format"
        )
    
    if commercial_space not in file_urls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found for commercial space: {commercial_space}"
        )
    
    try:
        file_url = file_urls[commercial_space]
        file_key = extract_file_key_from_url(file_url, settings.S3_BUCKET_NAME)
        if file_key:
            delete_file(file_key)
            logger.info(f"successfully deleted file from s3: {file_key}")
        else:
            logger.warning(f"could not extract file key from url: {file_url}")
    except Exception as e:
        logger.error(f"failed to delete file from s3: {e}", exc_info=True)
    
    del file_urls[commercial_space]
    
    if len(file_urls) == 0:
        db.delete(app_piece)
    else:
        app_piece.file_urls = json.dumps(file_urls)
    
    db.commit()
    return None


@router.delete("/{campaign_id}/creative-pieces/email", status_code=status.HTTP_204_NO_CONTENT)
async def delete_email_creative_piece(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    _require_creative_analyst(current_user)
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_campaign_status_for_creative_work(campaign)
    
    email_piece = (
        db.query(CreativePiece)
        .filter(
            CreativePiece.campaign_id == campaign_id,
            CreativePiece.piece_type == "E-mail"
        )
        .first()
    )
    
    if not email_piece or not email_piece.html_file_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="E-mail creative piece not found"
        )
    
    try:
        file_key = extract_file_key_from_url(email_piece.html_file_url, settings.S3_BUCKET_NAME)
        if file_key:
            delete_file(file_key)
            logger.info(f"successfully deleted file from s3: {file_key}")
        else:
            logger.warning(f"could not extract file key from url: {email_piece.html_file_url}")
    except Exception as e:
        logger.error(f"failed to delete file from s3: {e}", exc_info=True)
    
    db.delete(email_piece)
    db.commit()
    return None


@router.get("/{campaign_id}/download-piece")
async def download_creative_piece(
    campaign_id: str,
    channel: str = Query(..., description="Channel: EMAIL or APP"),
    commercial_space: Optional[str] = Query(None, description="Commercial space (required for APP)"),
    filename: Optional[str] = Query(None, description="Suggested filename for download"),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user),
):
    """
    Download a creative piece file. 
    Available only for business analysts and campaign analysts.
    """
    # Check role
    if current_user.get("role") not in [UserRole.BUSINESS_ANALYST.value, UserRole.CAMPAIGN_ANALYST.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business analysts and campaign analysts can download pieces"
        )
    
    campaign = _get_campaign_or_404(db, campaign_id)
    
    channel_upper = channel.upper().replace("-", "").replace(" ", "")
    if channel_upper == "E-MAIL":
        channel_upper = "EMAIL"
    
    if channel_upper == "EMAIL":
        # Download email HTML
        piece = (
            db.query(CreativePiece)
            .filter(
                CreativePiece.campaign_id == campaign_id,
                CreativePiece.piece_type == "E-mail"
            )
            .first()
        )
        if not piece or not piece.html_file_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email creative piece not found"
            )
        
        content, content_type = download_file_from_url(piece.html_file_url, settings.S3_BUCKET_NAME)
        download_filename = filename or f"email-{campaign.name.replace(' ', '_')}.html"
        
    elif channel_upper == "APP":
        if not commercial_space:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="commercial_space is required for APP channel"
            )
        
        piece = (
            db.query(CreativePiece)
            .filter(
                CreativePiece.campaign_id == campaign_id,
                CreativePiece.piece_type == "App"
            )
            .first()
        )
        if not piece or not piece.file_urls:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="App creative piece not found"
            )
        
        file_urls = get_app_file_urls_dict(piece.file_urls)
        file_url = file_urls.get(commercial_space)
        if not file_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No file found for commercial space: {commercial_space}"
            )
        
        content, content_type = download_file_from_url(file_url, settings.S3_BUCKET_NAME)
        safe_space = commercial_space.replace(" ", "_").replace("/", "_")
        download_filename = filename or f"app-{campaign.name.replace(' ', '_')}-{safe_space}.png"
        
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only EMAIL and APP channels support file download"
        )
    
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{download_filename}"'
        }
    )

