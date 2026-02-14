"""Seed legal validation audit data for dashboard visualization.

Revision ID: 002
Revises: 001
"""
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


SEED_AUDITS = [
    # 1 — SMS aprovado (Cartão Gold)
    {
        "task": "VALIDATE_COMMUNICATION",
        "channel": "SMS",
        "content_preview": "Cartão Gold Orqestra: anuidade GRÁTIS no 1º ano! Peça o seu: orqestra.com.br/gold",
        "decision": "APROVADO",
        "requires_human_review": False,
        "summary": "Mensagem de SMS promocional para o cartão Gold. O conteúdo está em conformidade com as normas do BACEN para comunicações de oferta de crédito. Inclui identificação do remetente, não contém promessas enganosas e respeita o limite de 160 caracteres. Não há violação regulatória identificada.",
        "sources": ["resolucao_bcb_4893.pdf", "codigo_defesa_consumidor.pdf"],
        "num_chunks_retrieved": 6,
        "llm_model": "sabiazinho-4",
        "days_ago": 10,
    },
    # 2 — PUSH aprovado (Fidelidade Diamante)
    {
        "task": "VALIDATE_COMMUNICATION",
        "channel": "PUSH",
        "content_preview": "Programa Diamante: Acumule pontos em cada transação e troque por experiências exclusivas.",
        "decision": "APROVADO",
        "requires_human_review": False,
        "summary": "Notificação push para programa de fidelidade. O conteúdo é informativo, não vinculante, e não configura oferta de crédito ou produto financeiro regulado. Não há linguagem enganosa ou omissão relevante. Comunicação adequada às diretrizes internas.",
        "sources": ["politica_comunicacao_interna.pdf"],
        "num_chunks_retrieved": 4,
        "llm_model": "sabiazinho-4",
        "days_ago": 28,
    },
    # 3 — SMS reprovado (Alerta Segurança)
    {
        "task": "VALIDATE_COMMUNICATION",
        "channel": "SMS",
        "content_preview": "URGENTE: Ative sua verificação em 2 etapas agora. Acesse: orqestra.com.br/seguranca",
        "decision": "REPROVADO",
        "requires_human_review": True,
        "summary": "A mensagem utiliza tom alarmista ('URGENTE') que pode ser interpretado como engenharia social ou phishing. Comunicações de segurança devem seguir as diretrizes do BACEN sobre notificações de segurança, que recomendam tom informativo e não coercitivo. Além disso, o link encurtado sem contexto adicional dificulta a verificação de legitimidade pelo cliente.",
        "sources": ["resolucao_bcb_4893.pdf", "guia_seguranca_cibernetica.pdf", "politica_comunicacao_interna.pdf"],
        "num_chunks_retrieved": 8,
        "llm_model": "sabiazinho-4",
        "days_ago": 13,
    },
    # 4 — SMS aprovado (Pix Sem Limites)
    {
        "task": "VALIDATE_COMMUNICATION",
        "channel": "SMS",
        "content_preview": "Pix sem limites no Orqestra! Transfira valores altos com segurança. Ative: orqestra.com.br/pix",
        "decision": "APROVADO",
        "requires_human_review": False,
        "summary": "Mensagem de SMS sobre ampliação de limites Pix. A comunicação menciona segurança e não promete isenção de responsabilidade. Está em conformidade com a regulamentação do Pix (Resolução BCB nº 1) e com as diretrizes internas de comunicação. O termo 'sem limites' é coloquial mas acompanhado de contexto ('valores altos com segurança').",
        "sources": ["resolucao_bcb_pix.pdf", "politica_comunicacao_interna.pdf"],
        "num_chunks_retrieved": 5,
        "llm_model": "sabiazinho-4",
        "days_ago": 18,
    },
    # 5 — PUSH aprovado (Black Friday)
    {
        "task": "VALIDATE_COMMUNICATION",
        "channel": "PUSH",
        "content_preview": "Investimentos Black Friday: CDB rendendo 120% do CDI. Oferta limitada!",
        "decision": "APROVADO",
        "requires_human_review": False,
        "summary": "Notificação push para campanha de investimentos. A comunicação informa a taxa (120% CDI) de forma objetiva, sem omissão de riscos implícitos para CDB (produto com garantia FGC). A expressão 'oferta limitada' é aceitável pois refere-se a período promocional, não a escassez artificial. Conforme com normas CVM para comunicação de produtos de renda fixa.",
        "sources": ["instrucao_cvm_539.pdf", "resolucao_bcb_4893.pdf"],
        "num_chunks_retrieved": 7,
        "llm_model": "sabiazinho-4",
        "days_ago": 40,
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    existing = conn.execute(
        sa.text("SELECT count(*) FROM legal_validation_audits")
    ).scalar()
    if existing and existing > 0:
        print(f"Legal audits already exist ({existing}). Skipping seed.")
        return

    now = datetime.now(timezone.utc)

    for audit in SEED_AUDITS:
        conn.execute(
            sa.text("""
                INSERT INTO legal_validation_audits
                    (id, task, channel, content_hash, content_preview,
                     decision, requires_human_review, summary, sources,
                     num_chunks_retrieved, llm_model, search_query, created_at)
                VALUES
                    (:id, :task, :channel, :hash, :preview,
                     :decision, :rhr, :summary, :sources,
                     :chunks, :model, :query, :ts)
            """),
            {
                "id": _uid(),
                "task": audit["task"],
                "channel": audit["channel"],
                "hash": _hash(audit["content_preview"]),
                "preview": audit["content_preview"],
                "decision": audit["decision"],
                "rhr": audit["requires_human_review"],
                "summary": audit["summary"],
                "sources": audit["sources"],
                "chunks": audit["num_chunks_retrieved"],
                "model": audit["llm_model"],
                "query": f"VALIDATE_COMMUNICATION para {audit['channel']}: {audit['content_preview'][:80]}",
                "ts": now - timedelta(days=audit["days_ago"]),
            },
        )

    conn.commit()
    print(f"Seeded {len(SEED_AUDITS)} legal validation audit records.")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM legal_validation_audits"))
    conn.commit()
