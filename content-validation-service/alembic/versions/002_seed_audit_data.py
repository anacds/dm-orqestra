"""Seed piece validation audit data for dashboard visualization.

Revision ID: 002
Revises: 001
"""
import json
import uuid
import hashlib
from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def _uid():
    return str(uuid.uuid4())


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Simulated full validation responses matching AnalyzePieceResponse structure
SEED_AUDITS = [
    # 1 — SMS Cartão Gold (approved)
    {
        "campaign_name": "Promoção Cartão Gold",
        "channel": "SMS",
        "content_key": "Cartão Gold Orqestra: anuidade GRÁTIS no 1º ano!",
        "days_ago": 10,
        "response": {
            "validation_result": {"status": "valid", "channel": "SMS"},
            "specs_result": {"status": "APROVADO", "violations": []},
            "orchestration_result": None,
            "compliance_result": {
                "decision": "APROVADO",
                "summary": "SMS em conformidade com normas regulatórias.",
                "requires_human_review": False,
            },
            "branding_result": None,
            "requires_human_approval": False,
            "human_approval_reason": None,
            "failure_stage": None,
            "stages_completed": ["validate_specs", "validate_legal", "issue_final_verdict"],
            "final_verdict": {
                "verdict": "APROVADO",
                "summary": "Peça SMS aprovada. Specs dentro dos limites (78/160 caracteres). Validação legal aprovada sem ressalvas.",
                "specs_verdict": "APROVADO",
                "legal_verdict": "APROVADO",
                "branding_verdict": None,
            },
        },
    },
    # 2 — PUSH Fidelidade Diamante (approved)
    {
        "campaign_name": "Programa Fidelidade Diamante",
        "channel": "PUSH",
        "content_key": "Programa Diamante: Acumule pontos em cada transação",
        "days_ago": 28,
        "response": {
            "validation_result": {"status": "valid", "channel": "PUSH"},
            "specs_result": {"status": "APROVADO", "violations": []},
            "orchestration_result": None,
            "compliance_result": {
                "decision": "APROVADO",
                "summary": "Push notification em conformidade.",
                "requires_human_review": False,
            },
            "branding_result": None,
            "requires_human_approval": False,
            "human_approval_reason": None,
            "failure_stage": None,
            "stages_completed": ["validate_specs", "validate_legal", "issue_final_verdict"],
            "final_verdict": {
                "verdict": "APROVADO",
                "summary": "Peça PUSH aprovada. Título (17/50 chars) e corpo (74/120 chars) dentro dos limites. Validação legal sem restrições.",
                "specs_verdict": "APROVADO",
                "legal_verdict": "APROVADO",
                "branding_verdict": None,
            },
        },
    },
    # 3 — SMS Alerta Segurança (rejected)
    {
        "campaign_name": "Alerta de Segurança Digital",
        "channel": "SMS",
        "content_key": "URGENTE: Ative sua verificação em 2 etapas agora",
        "days_ago": 13,
        "response": {
            "validation_result": {"status": "valid", "channel": "SMS"},
            "specs_result": {"status": "APROVADO", "violations": []},
            "orchestration_result": None,
            "compliance_result": {
                "decision": "REPROVADO",
                "summary": "Tom alarmista pode ser confundido com phishing.",
                "requires_human_review": True,
            },
            "branding_result": None,
            "requires_human_approval": True,
            "human_approval_reason": "Validação legal reprovou a peça.",
            "failure_stage": None,
            "stages_completed": ["validate_specs", "validate_legal", "issue_final_verdict"],
            "final_verdict": {
                "verdict": "REPROVADO",
                "summary": "Peça SMS reprovada na validação legal. O tom alarmista ('URGENTE') pode ser interpretado como engenharia social. Reformular linguagem para tom informativo.",
                "specs_verdict": "APROVADO",
                "legal_verdict": "REPROVADO",
                "branding_verdict": None,
            },
        },
    },
    # 4 — SMS Pix Sem Limites (approved)
    {
        "campaign_name": "Campanha Pix Sem Limites",
        "channel": "SMS",
        "content_key": "Pix sem limites no Orqestra! Transfira valores altos",
        "days_ago": 18,
        "response": {
            "validation_result": {"status": "valid", "channel": "SMS"},
            "specs_result": {"status": "APROVADO", "violations": []},
            "orchestration_result": None,
            "compliance_result": {
                "decision": "APROVADO",
                "summary": "Mensagem em conformidade com regulamentação do Pix.",
                "requires_human_review": False,
            },
            "branding_result": None,
            "requires_human_approval": False,
            "human_approval_reason": None,
            "failure_stage": None,
            "stages_completed": ["validate_specs", "validate_legal", "issue_final_verdict"],
            "final_verdict": {
                "verdict": "APROVADO",
                "summary": "Peça SMS aprovada. Specs ok (91/160 chars). Validação legal aprovada — comunicação sobre Pix em conformidade com Resolução BCB nº 1.",
                "specs_verdict": "APROVADO",
                "legal_verdict": "APROVADO",
                "branding_verdict": None,
            },
        },
    },
    # 5 — PUSH Black Friday (approved)
    {
        "campaign_name": "Black Friday Investimentos",
        "channel": "PUSH",
        "content_key": "CDB rendendo 120% do CDI. Oferta limitada!",
        "days_ago": 40,
        "response": {
            "validation_result": {"status": "valid", "channel": "PUSH"},
            "specs_result": {"status": "APROVADO", "violations": []},
            "orchestration_result": None,
            "compliance_result": {
                "decision": "APROVADO",
                "summary": "Comunicação de CDB com taxa informada de forma objetiva.",
                "requires_human_review": False,
            },
            "branding_result": None,
            "requires_human_approval": False,
            "human_approval_reason": None,
            "failure_stage": None,
            "stages_completed": ["validate_specs", "validate_legal", "issue_final_verdict"],
            "final_verdict": {
                "verdict": "APROVADO",
                "summary": "Peça PUSH aprovada. Título (28/50 chars) e corpo (46/120 chars) ok. Comunicação sobre CDB em conformidade com normas CVM para renda fixa.",
                "specs_verdict": "APROVADO",
                "legal_verdict": "APROVADO",
                "branding_verdict": None,
            },
        },
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    existing = conn.execute(
        sa.text("SELECT count(*) FROM piece_validation_audit")
    ).scalar()
    if existing and existing > 0:
        print(f"Validation audits already exist ({existing}). Skipping seed.")
        return

    now = datetime.now(timezone.utc)

    for audit in SEED_AUDITS:
        # Use a deterministic campaign_id based on campaign name (for repeatability)
        campaign_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, audit["campaign_name"]))
        conn.execute(
            sa.text("""
                INSERT INTO piece_validation_audit
                    (id, campaign_id, channel, content_hash, response_json, created_at)
                VALUES
                    (:id, :cid, :channel, :hash, :response, :ts)
            """),
            {
                "id": _uid(),
                "cid": campaign_id,
                "channel": audit["channel"],
                "hash": _hash(audit["content_key"]),
                "response": json.dumps(audit["response"]),
                "ts": now - timedelta(days=audit["days_ago"]),
            },
        )

    conn.commit()
    print(f"Seeded {len(SEED_AUDITS)} piece validation audit records.")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM piece_validation_audit"))
    conn.commit()
