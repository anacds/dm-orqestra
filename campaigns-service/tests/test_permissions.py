from app.models.campaign import CampaignStatus
from app.models.user_role import UserRole
from app.core.permissions import (
    can_transition_status,
    get_visible_statuses_for_role,
)
from app.services.services import (
    _is_piece_finally_approved,
    _is_piece_finally_rejected,
)


# ── Transições de status ──────────────────────────────────────────────────

class TestStatusTransitions:
    """Testa transições permitidas e bloqueadas por papel."""

    def test_ba_draft_to_creative(self):
        user = {"role": UserRole.BUSINESS_ANALYST.value}
        ok, _ = can_transition_status(user, CampaignStatus.DRAFT, CampaignStatus.CREATIVE_STAGE)
        assert ok is True

    def test_ba_cannot_skip_to_published(self):
        user = {"role": UserRole.BUSINESS_ANALYST.value}
        ok, msg = can_transition_status(user, CampaignStatus.DRAFT, CampaignStatus.CAMPAIGN_PUBLISHED)
        assert ok is False

    def test_creative_to_review(self):
        user = {"role": UserRole.CREATIVE_ANALYST.value}
        ok, _ = can_transition_status(user, CampaignStatus.CREATIVE_STAGE, CampaignStatus.CONTENT_REVIEW)
        assert ok is True

    def test_creative_adjustment_to_review(self):
        user = {"role": UserRole.CREATIVE_ANALYST.value}
        ok, _ = can_transition_status(user, CampaignStatus.CONTENT_ADJUSTMENT, CampaignStatus.CONTENT_REVIEW)
        assert ok is True

    def test_mm_review_to_building(self):
        user = {"role": UserRole.MARKETING_MANAGER.value}
        ok, _ = can_transition_status(user, CampaignStatus.CONTENT_REVIEW, CampaignStatus.CAMPAIGN_BUILDING)
        assert ok is True

    def test_mm_review_to_adjustment(self):
        user = {"role": UserRole.MARKETING_MANAGER.value}
        ok, _ = can_transition_status(user, CampaignStatus.CONTENT_REVIEW, CampaignStatus.CONTENT_ADJUSTMENT)
        assert ok is True

    def test_mm_cannot_publish(self):
        user = {"role": UserRole.MARKETING_MANAGER.value}
        ok, _ = can_transition_status(user, CampaignStatus.CONTENT_REVIEW, CampaignStatus.CAMPAIGN_PUBLISHED)
        assert ok is False

    def test_campaign_analyst_building_to_published(self):
        user = {"role": UserRole.CAMPAIGN_ANALYST.value}
        ok, _ = can_transition_status(user, CampaignStatus.CAMPAIGN_BUILDING, CampaignStatus.CAMPAIGN_PUBLISHED)
        assert ok is True

    def test_invalid_role(self):
        user = {"role": "Papel Inexistente"}
        ok, msg = can_transition_status(user, CampaignStatus.DRAFT, CampaignStatus.CREATIVE_STAGE)
        assert ok is False
        assert "role" in msg.lower()


# ── Visibilidade por papel ────────────────────────────────────────────────

class TestVisibility:
    """Testa quais status cada papel pode visualizar."""

    def test_ba_sees_all_stages(self):
        statuses = get_visible_statuses_for_role(UserRole.BUSINESS_ANALYST)
        assert CampaignStatus.DRAFT in statuses
        assert CampaignStatus.CAMPAIGN_PUBLISHED in statuses
        assert len(statuses) == 6

    def test_creative_sees_only_creative_stages(self):
        statuses = get_visible_statuses_for_role(UserRole.CREATIVE_ANALYST)
        assert CampaignStatus.CREATIVE_STAGE in statuses
        assert CampaignStatus.DRAFT not in statuses
        assert CampaignStatus.CAMPAIGN_PUBLISHED not in statuses

    def test_campaign_analyst_sees_building_and_published(self):
        statuses = get_visible_statuses_for_role(UserRole.CAMPAIGN_ANALYST)
        assert CampaignStatus.CAMPAIGN_BUILDING in statuses
        assert CampaignStatus.CAMPAIGN_PUBLISHED in statuses
        assert CampaignStatus.DRAFT not in statuses

    def test_invalid_role_returns_empty(self):
        statuses = get_visible_statuses_for_role("Papel Fake")
        assert statuses == []


# ── Lógica de aprovação/rejeição de peças ─────────────────────────────────

class TestPieceVerdicts:
    """Testa a lógica de veredito final (IA + humano)."""

    def test_ia_approved_human_pending_is_approved(self):
        # IA aprovou e humano não rejeitou manualmente → peça aprovada
        assert _is_piece_finally_approved("approved", "pending") is True

    def test_ia_approved_human_approved_is_approved(self):
        # human_verdict != "manually_rejected" → approved
        assert _is_piece_finally_approved("approved", "approved") is True

    def test_ia_approved_human_manually_rejected(self):
        assert _is_piece_finally_approved("approved", "manually_rejected") is False
        assert _is_piece_finally_rejected("approved", "manually_rejected") is True

    def test_ia_rejected_human_approved_overrides(self):
        assert _is_piece_finally_approved("rejected", "approved") is True
        assert _is_piece_finally_rejected("rejected", "approved") is False

    def test_ia_rejected_human_rejected(self):
        assert _is_piece_finally_rejected("rejected", "rejected") is True
        assert _is_piece_finally_approved("rejected", "rejected") is False

    def test_ia_none_human_approved(self):
        assert _is_piece_finally_approved(None, "approved") is True

    def test_ia_none_human_rejected(self):
        assert _is_piece_finally_rejected(None, "rejected") is True
