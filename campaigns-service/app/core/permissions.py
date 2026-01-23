from typing import Dict, List, Tuple, Optional
from fastapi import HTTPException, status
from app.models.campaign import Campaign, CampaignStatus
from app.models.user_role import UserRole


def _to_user_role(role: str | UserRole) -> Optional[UserRole]:
    """converte string para UserRole enum, retorna None se inválido"""
    if isinstance(role, UserRole):
        return role
    try:
        return UserRole(role)
    except ValueError:
        return None


def _to_campaign_status(status: str | CampaignStatus) -> Optional[CampaignStatus]:
    """converte string para CampaignStatus enum, retorna None se inválido"""
    if isinstance(status, CampaignStatus):
        return status
    try:
        return CampaignStatus(status)
    except ValueError:
        return None


ROLE_VISIBLE_STATUSES = {
    UserRole.BUSINESS_ANALYST: [
        CampaignStatus.DRAFT,
        CampaignStatus.CREATIVE_STAGE,
        CampaignStatus.CONTENT_REVIEW,
        CampaignStatus.CONTENT_ADJUSTMENT,
        CampaignStatus.CAMPAIGN_BUILDING,
        CampaignStatus.CAMPAIGN_PUBLISHED,
    ],
    UserRole.CREATIVE_ANALYST: [
        CampaignStatus.CREATIVE_STAGE,
        CampaignStatus.CONTENT_REVIEW,
        CampaignStatus.CONTENT_ADJUSTMENT,
    ],
    UserRole.CAMPAIGN_ANALYST: [
        CampaignStatus.CAMPAIGN_BUILDING,
        CampaignStatus.CAMPAIGN_PUBLISHED,
    ],
}

VALID_TRANSITIONS = {
    (UserRole.BUSINESS_ANALYST, CampaignStatus.DRAFT): [
        CampaignStatus.CREATIVE_STAGE,
    ],
    (UserRole.BUSINESS_ANALYST, CampaignStatus.CONTENT_REVIEW): [
        CampaignStatus.CAMPAIGN_BUILDING,
        CampaignStatus.CONTENT_ADJUSTMENT,
    ],
    (UserRole.CREATIVE_ANALYST, CampaignStatus.CREATIVE_STAGE): [
        CampaignStatus.CONTENT_REVIEW,
    ],
    (UserRole.CREATIVE_ANALYST, CampaignStatus.CONTENT_ADJUSTMENT): [
        CampaignStatus.CONTENT_REVIEW,
    ],
    (UserRole.CAMPAIGN_ANALYST, CampaignStatus.CAMPAIGN_BUILDING): [
        CampaignStatus.CAMPAIGN_PUBLISHED,
    ],
}


def require_business_analyst(current_user: Dict) -> None:
    user_role_str = current_user.get("role")
    user_role = _to_user_role(user_role_str)
    
    if user_role != UserRole.BUSINESS_ANALYST:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta funcionalidade é restrita a analistas de negócios"
        )


def get_visible_statuses_for_role(user_role: str | UserRole) -> List[CampaignStatus]:
    role = _to_user_role(user_role)
    if not role:
        return []
    return ROLE_VISIBLE_STATUSES.get(role, [])


def can_view_campaign(current_user: Dict, campaign: Campaign) -> bool:
    user_role_str = current_user.get("role")
    user_role = _to_user_role(user_role_str)
    if not user_role:
        return False
    
    if (user_role == UserRole.BUSINESS_ANALYST and 
        campaign.status == CampaignStatus.DRAFT and
        campaign.created_by == current_user.get("id")):
        return True
    
    visible_statuses = get_visible_statuses_for_role(user_role)
    campaign_status = _to_campaign_status(campaign.status)
    if not campaign_status:
        return False
    
    return campaign_status in visible_statuses


def can_transition_status(
    current_user: Dict,
    current_status: str | CampaignStatus,
    new_status: CampaignStatus,
) -> Tuple[bool, Optional[str]]:
    user_role_str = current_user.get("role")
    user_role = _to_user_role(user_role_str)
    if not user_role:
        return False, "User role not found"
    
    status = _to_campaign_status(current_status)
    if not status:
        return False, "Invalid campaign status"
    
    allowed_transitions = VALID_TRANSITIONS.get((user_role, status), [])
    
    if new_status not in allowed_transitions:
        return False, f"Transition from {status.value} to {new_status.value} is not allowed for {user_role.value}"
    
    return True, None


