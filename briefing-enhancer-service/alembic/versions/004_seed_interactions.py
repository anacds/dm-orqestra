"""Seed AI interaction audit data for dashboard visualization.

Revision ID: 004
Revises: 003
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def _uid():
    return str(uuid.uuid4())


def _get_user_id(email):
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "db"),
            user=os.getenv("POSTGRES_USER", "orqestra"),
            password=os.getenv("POSTGRES_PASSWORD", "orqestra_password"),
            port=os.getenv("DB_PORT", "5432"),
            database="auth_service",
        )
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else ""
    except Exception:
        return ""


SEED_INTERACTIONS = [
    # Ana (Analista de Negócios) aprimorando briefings
    {
        "user_email": "ana@email.com",
        "field_name": "businessObjective",
        "input_text": "Vender mais cartões gold pra quem já é cliente",
        "output_text": "Converter correntistas pessoa física em titulares do cartão Gold, utilizando oferta de anuidade promocional gratuita no primeiro ano como principal alavanca de aquisição, com foco em clientes de alta renda que ainda não possuem cartão de crédito ativo no banco.",
        "explanation": "O texto original era genérico e coloquial. A versão aprimorada especifica o público-alvo (correntistas PF), a estratégia (anuidade gratuita), o produto (Gold) e o critério de segmentação (alta renda sem cartão ativo), tornando o objetivo mensurável e acionável.",
        "user_decision": "approved",
        "days_ago": 11,
    },
    {
        "user_email": "ana@email.com",
        "field_name": "expectedResult",
        "input_text": "Espero aumentar a base de clientes com investimentos",
        "output_text": "Captação de R$ 50 milhões em novos investimentos e adesão de 8.000 novos investidores na plataforma durante o período da campanha Black Friday, representando crescimento de 15% na base de investidores ativos.",
        "explanation": "O resultado esperado original não continha metas quantificáveis. A versão aprimorada inclui valor financeiro (R$ 50 milhões), volume de novos clientes (8.000), período (Black Friday) e percentual de crescimento (15%), permitindo avaliação objetiva do sucesso da campanha.",
        "user_decision": "approved",
        "days_ago": 42,
    },
    {
        "user_email": "ana@email.com",
        "field_name": "targetAudienceDescription",
        "input_text": "Jovens que usam celular e querem aprender sobre dinheiro",
        "output_text": "Pessoas de 18 a 25 anos, predominantemente estudantes universitários ou recém-formados, com perfil digital nativo e interesse demonstrado em educação financeira, residentes em regiões metropolitanas com acesso a serviços bancários digitais.",
        "explanation": "A descrição original era vaga e informal. A versão aprimorada delimita faixa etária (18-25), perfil socioeconômico (universitários/recém-formados), comportamento (digital nativo) e localização (regiões metropolitanas), fornecendo critérios claros para segmentação de base.",
        "user_decision": "rejected",
        "days_ago": 7,
    },
    {
        "user_email": "ana@email.com",
        "field_name": "exclusionCriteria",
        "input_text": "Não mandar para inadimplentes e funcionários",
        "output_text": "Excluir da base de impacto: clientes com parcelas em atraso superior a 30 dias, clientes em processo de renegociação ativa, colaboradores internos do banco e suas empresas vinculadas, e contas com restrição cadastral ou bloqueio judicial.",
        "explanation": "Os critérios originais mencionavam apenas dois grupos. A versão aprimorada detalha os critérios de inadimplência (>30 dias de atraso), inclui clientes em renegociação, especifica que a exclusão de funcionários se estende a empresas vinculadas, e adiciona restrições cadastrais/judiciais.",
        "user_decision": "approved",
        "days_ago": 18,
    },
    {
        "user_email": "ana@email.com",
        "field_name": "businessObjective",
        "input_text": "Reter clientes PJ que estão saindo",
        "output_text": "Reduzir a taxa de encerramento de contas PJ Premium em 20% no trimestre, através de ofertas personalizadas de benefícios exclusivos e atendimento diferenciado para empresas com faturamento entre R$ 500 mil e R$ 10 milhões que apresentem sinais de inatividade nos últimos 30 dias.",
        "explanation": "O objetivo original era vago ('reter clientes que estão saindo'). A versão aprimorada quantifica a meta (redução de 20%), define o período (trimestre), especifica o segmento (PJ Premium com faturamento definido), a estratégia (benefícios e atendimento) e o gatilho (inatividade 30 dias).",
        "user_decision": "approved",
        "days_ago": 2,
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    existing = conn.execute(
        sa.text("SELECT count(*) FROM audit_interactions")
    ).scalar()
    if existing and existing > 0:
        print(f"Interactions already exist ({existing}). Skipping seed.")
        return

    now = datetime.now(timezone.utc)

    for interaction in SEED_INTERACTIONS:
        user_id = _get_user_id(interaction["user_email"])
        if not user_id:
            print(f"Warning: user {interaction['user_email']} not found, skipping.")
            continue

        ts = now - timedelta(days=interaction["days_ago"])
        decision_ts = ts + timedelta(minutes=2) if interaction["user_decision"] else None

        conn.execute(
            sa.text("""
                INSERT INTO audit_interactions
                    (id, user_id, campaign_id, field_name,
                     input_text, output_text, explanation,
                     session_id, created_at,
                     user_decision, decision_at)
                VALUES
                    (:id, :uid, :cid, :field,
                     :input, :output, :explanation,
                     :sid, :ts,
                     :decision, :decision_at)
            """),
            {
                "id": _uid(),
                "uid": user_id,
                "cid": None,
                "field": interaction["field_name"],
                "input": interaction["input_text"],
                "output": interaction["output_text"],
                "explanation": interaction["explanation"],
                "sid": _uid(),
                "ts": ts,
                "decision": interaction["user_decision"],
                "decision_at": decision_ts,
            },
        )

    conn.commit()
    print(f"Seeded {len(SEED_INTERACTIONS)} briefing enhancement interaction records.")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM audit_interactions"))
    conn.commit()
