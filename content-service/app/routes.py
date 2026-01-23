from fastapi import APIRouter, HTTPException, status, Depends, Request
from typing import Dict, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.auth_client import get_current_user
from app.core.database import get_db
from app.services import CreativePieceAnalysisService
from app.models.creative_piece_analysis import CreativePieceAnalysis

router = APIRouter()


class AnalyzePieceRequest(BaseModel):
    campaignId: str
    channel: str  # "SMS" | "Push"
    content: Dict[str, str]  # For SMS: {"text": "..."}, For Push: {"title": "...", "body": "..."}


class AnalyzePieceResponse(BaseModel):
    id: str
    campaign_id: str
    channel: str
    is_valid: str  # "valid" | "invalid" | "warning"
    analysis_text: str
    analyzed_by: str
    created_at: str
    
    class Config:
        from_attributes = True


@router.post("/ai/analyze-piece", response_model=AnalyzePieceResponse)
async def analyze_piece(
    request: Request,
    request_data: AnalyzePieceRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):
    """
    Analyze a creative piece against campaign briefing and guidelines.
    
    If analysis already exists for the same content (detected by hash),
    returns existing analysis. Otherwise, creates a new analysis.
    
    Request body:
        - campaignId: string (required)
        - channel: "SMS" | "Push" (required)
        - content: object (required)
            - For SMS: {"text": "message text"}
            - For Push: {"title": "title", "body": "body text"}
    
    Returns:
        Analysis result with validation status and comments
    """
    try:
        campaign_id = request_data.campaignId
        channel = request_data.channel
        content = request_data.content
        
        if channel not in ["SMS", "Push"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="channel must be 'SMS' or 'Push'"
            )
        
        # Validate content structure
        if channel == "SMS" and "text" not in content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="content must contain 'text' field for SMS channel"
            )
        
        if channel == "Push" and ("title" not in content or "body" not in content):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="content must contain 'title' and 'body' fields for Push channel"
            )
        
        # Get authorization token from cookie or header
        auth_token = None
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            auth_token = cookie_token
        else:
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                auth_token = auth_header.replace("Bearer ", "")
        
        if not auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token required"
            )
        
        # Perform analysis
        analysis = await CreativePieceAnalysisService.analyze_piece(
            db=db,
            campaign_id=campaign_id,
            channel=channel,
            content=content,
            user_id=current_user["id"],
            auth_token=f"Bearer {auth_token}"
        )
        
        return AnalyzePieceResponse(
            id=analysis.id,
            campaign_id=analysis.campaign_id,
            channel=analysis.channel,
            is_valid=analysis.is_valid,
            analysis_text=analysis.analysis_text,
            analyzed_by=analysis.analyzed_by,
            created_at=analysis.created_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing piece: {str(e)}"
        )


@router.get("/ai/analyze-piece/{campaign_id}/{channel}", response_model=AnalyzePieceResponse)
async def get_analysis(
    request: Request,
    campaign_id: str,
    channel: str,
    content_hash: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get existing analysis for a creative piece.
    
    Query params:
        - campaign_id: Campaign ID (path parameter)
        - channel: "SMS" | "Push" (path parameter)
        - content_hash: Hash of content (query parameter, optional)
            If provided, returns analysis only if hash matches
            If not provided, returns most recent analysis for campaign+channel
    
    Returns:
        Analysis result or None if not found
    """
    try:
        if channel not in ["SMS", "Push"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="channel must be 'SMS' or 'Push'"
            )
        
        if content_hash:
            # Get analysis by content hash
            analysis = CreativePieceAnalysisService.get_existing_analysis(
                db, campaign_id, channel, content_hash
            )
        else:
            # Get most recent analysis for campaign+channel
            analysis = db.query(CreativePieceAnalysis).filter(
                CreativePieceAnalysis.campaign_id == campaign_id,
                CreativePieceAnalysis.channel == channel
            ).order_by(CreativePieceAnalysis.created_at.desc()).first()
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )
        
        return AnalyzePieceResponse(
            id=analysis.id,
            campaign_id=analysis.campaign_id,
            channel=analysis.channel,
            is_valid=analysis.is_valid,
            analysis_text=analysis.analysis_text,
            analyzed_by=analysis.analyzed_by,
            created_at=analysis.created_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching analysis: {str(e)}"
        )
