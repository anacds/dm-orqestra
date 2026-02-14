"""Seed default campaigns, pieces, reviews and channel specs.

Revision ID: 002
Revises: 001
"""
import sys
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from alembic import op
import sqlalchemy as sa
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def _uid() -> str:
    return str(uuid.uuid4())


def _get_user_id(email: str) -> str:
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


def _insert_campaign(conn, cid, data, user_id, days_ago):
    """Insert a campaign with created_date in the past."""
    created = datetime.now(timezone.utc) - timedelta(days=days_ago)
    start = date.today() + timedelta(days=data.get("start_offset", 7))
    end = start + timedelta(days=data.get("duration", 60))

    conn.execute(
        sa.text("""
            INSERT INTO campaigns (
                id, name, category, business_objective, expected_result,
                requesting_area, start_date, end_date, priority,
                communication_channels, commercial_spaces,
                target_audience_description, exclusion_criteria,
                estimated_impact_volume, communication_tone,
                execution_model, trigger_event, recency_rule_days,
                status, created_by, created_date
            ) VALUES (
                :id, :name, :category, :business_objective, :expected_result,
                :requesting_area, :start_date, :end_date, :priority,
                :communication_channels, :commercial_spaces,
                :target_audience_description, :exclusion_criteria,
                :estimated_impact_volume, :communication_tone,
                :execution_model, :trigger_event, :recency_rule_days,
                :status, :created_by, :created_date
            )
        """),
        {
            "id": cid,
            "name": data["name"],
            "category": data["category"],
            "business_objective": data["objective"],
            "expected_result": data["result"],
            "requesting_area": data.get("area", "Produtos PF"),
            "start_date": start,
            "end_date": end,
            "priority": data.get("priority", "Normal"),
            "communication_channels": data.get("channels", ["SMS", "Push"]),
            "commercial_spaces": data.get("spaces"),
            "target_audience_description": data["audience"],
            "exclusion_criteria": data["exclusion"],
            "estimated_impact_volume": data.get("volume", 1000000),
            "communication_tone": data.get("tone", "Informal"),
            "execution_model": data.get("execution", "Batch (agendada)"),
            "trigger_event": data.get("trigger"),
            "recency_rule_days": data.get("recency", 30),
            "status": data["status"],
            "created_by": user_id,
            "created_date": created,
        },
    )


def _insert_status_events(conn, cid, transitions, actor_id, base_days_ago):
    """Insert status transition events spread over time."""
    for i, (from_s, to_s) in enumerate(transitions):
        ts = datetime.now(timezone.utc) - timedelta(days=base_days_ago - i, hours=i * 3)
        conn.execute(
            sa.text("""
                INSERT INTO campaign_status_event
                    (id, campaign_id, from_status, to_status, actor_id, created_at)
                VALUES (:id, :cid, :from_s, :to_s, :actor_id, :ts)
            """),
            {"id": _uid(), "cid": cid, "from_s": from_s, "to_s": to_s, "actor_id": actor_id, "ts": ts},
        )


def _insert_piece(conn, pid, cid, piece_type, title, body, days_ago):
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    conn.execute(
        sa.text("""
            INSERT INTO creative_pieces (id, campaign_id, piece_type, title, body, created_at, updated_at)
            VALUES (:id, :cid, :pt, :title, :body, :ts, :ts)
        """),
        {"id": pid, "cid": cid, "pt": piece_type, "title": title, "body": body, "ts": ts},
    )


def _insert_review(conn, cid, channel, pid, human_verdict, reviewed_by, reviewed_at, ia_verdict=None, reason=None):
    conn.execute(
        sa.text("""
            INSERT INTO piece_review
                (id, campaign_id, channel, piece_id, commercial_space,
                 ia_verdict, human_verdict, reviewed_at, reviewed_by, rejection_reason)
            VALUES (:id, :cid, :ch, :pid, '', :ia, :hv, :rat, :rb, :rr)
        """),
        {
            "id": _uid(), "cid": cid, "ch": channel, "pid": pid,
            "ia": ia_verdict, "hv": human_verdict, "rat": reviewed_at,
            "rb": reviewed_by, "rr": reason,
        },
    )


def _insert_review_event(conn, cid, channel, pid, event_type, actor_id, ts, ia_verdict=None, reason=None):
    conn.execute(
        sa.text("""
            INSERT INTO piece_review_event
                (id, campaign_id, channel, piece_id, commercial_space,
                 event_type, ia_verdict, rejection_reason, actor_id, created_at)
            VALUES (:id, :cid, :ch, :pid, '', :et, :ia, :rr, :actor, :ts)
        """),
        {
            "id": _uid(), "cid": cid, "ch": channel, "pid": pid,
            "et": event_type, "ia": ia_verdict, "rr": reason,
            "actor": actor_id, "ts": ts,
        },
    )


def _insert_comment(conn, cid, author, role, text, days_ago):
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=2)
    conn.execute(
        sa.text("""
            INSERT INTO comments (id, campaign_id, author, role, text, timestamp)
            VALUES (:id, :cid, :author, :role, :text, :ts)
        """),
        {"id": _uid(), "cid": cid, "author": author, "role": role, "text": text, "ts": ts},
    )


# ── Campaign definitions ──────────────────────────────────────────────
CAMPAIGNS = [
    # 1 — CREATIVE_STAGE (existing, enhanced)
    {
        "name": "Campanha de Aquisição - Conta Corrente Digital",
        "category": "Aquisição",
        "objective": "Aumentar a base de clientes com conta corrente digital através de ofertas atrativas e experiência simplificada de abertura",
        "result": "Aquisição de 5.000 novos clientes e aumento de 15% na base de contas correntes digitais",
        "area": "Produtos PF",
        "audience": "Pessoas físicas entre 25 e 55 anos, sem vínculo bancário atual, residentes em áreas urbanas",
        "exclusion": "Clientes já ativos, menores de 18 anos, clientes com restrições no CPF",
        "volume": 2500000,
        "tone": "Informal",
        "priority": "Normal",
        "status": "CREATIVE_STAGE",
        "days_ago": 5,
        "transitions": [(None, "DRAFT"), ("DRAFT", "CREATIVE_STAGE")],
        "pieces": [
            ("SMS", None, "Orqestra: sua conta digital te espera! Abra em 3 min, sem burocracia. Acesse: orqestra.com.br/conta"),
            ("Push", "Conta Digital Orqestra", "Abra sua conta em 3 minutos. Sem taxas no primeiro ano!"),
        ],
    },
    # 2 — DRAFT (existing, enhanced)
    {
        "name": "Campanha de Retenção - Conta PJ Premium",
        "category": "Retenção",
        "objective": "Reduzir a taxa de encerramento de contas PJ e aumentar a retenção com benefícios exclusivos",
        "result": "Redução de 20% na taxa de churn de clientes PJ e aumento de 10% no NPS",
        "area": "Produtos PJ",
        "audience": "Empresas com faturamento entre R$ 500 mil e R$ 10 milhões, clientes há mais de 6 meses",
        "exclusion": "Empresas em processo de encerramento, clientes com pendências financeiras",
        "volume": 5000000,
        "tone": "Formal",
        "priority": "Alta",
        "execution": "Event-driven (por evento)",
        "trigger": "Inatividade por 30 dias",
        "recency": 60,
        "status": "DRAFT",
        "days_ago": 2,
        "transitions": [(None, "DRAFT")],
    },
    # 3 — CONTENT_REVIEW
    {
        "name": "Promoção Cartão Gold - Cross-sell",
        "category": "Cross-sell",
        "objective": "Converter clientes de conta corrente para o cartão Gold com anuidade promocional",
        "result": "Emissão de 3.000 novos cartões Gold e aumento de 25% na receita de anuidades",
        "audience": "Correntistas PF com renda acima de R$ 5.000 e sem cartão de crédito ativo",
        "exclusion": "Clientes com score abaixo de 600, inadimplentes, já titulares do Gold",
        "volume": 800000,
        "tone": "Consultivo",
        "priority": "Alta",
        "status": "CONTENT_REVIEW",
        "days_ago": 12,
        "transitions": [(None, "DRAFT"), ("DRAFT", "CREATIVE_STAGE"), ("CREATIVE_STAGE", "CONTENT_REVIEW")],
        "pieces": [
            ("SMS", None, "Cartão Gold Orqestra: anuidade GRÁTIS no 1º ano! Peça o seu: orqestra.com.br/gold"),
            ("Push", "Cartão Gold pra você", "Anuidade zero no primeiro ano. Solicite agora e aproveite os benefícios exclusivos."),
        ],
        "reviews_pending": True,
    },
    # 4 — CAMPAIGN_PUBLISHED
    {
        "name": "Programa Fidelidade Diamante",
        "category": "Relacionamento",
        "objective": "Engajar clientes de alta renda com programa de pontos exclusivo",
        "result": "Adesão de 10.000 clientes ao programa e aumento de 30% no engajamento digital",
        "audience": "Clientes PF com renda acima de R$ 15.000 e histórico de pelo menos 12 meses",
        "exclusion": "Clientes inativos há mais de 90 dias, funcionários do banco",
        "volume": 3000000,
        "tone": "Formal",
        "priority": "Alta",
        "status": "CAMPAIGN_PUBLISHED",
        "days_ago": 30,
        "transitions": [
            (None, "DRAFT"),
            ("DRAFT", "CREATIVE_STAGE"),
            ("CREATIVE_STAGE", "CONTENT_REVIEW"),
            ("CONTENT_REVIEW", "CAMPAIGN_BUILDING"),
            ("CAMPAIGN_BUILDING", "CAMPAIGN_PUBLISHED"),
        ],
        "pieces": [
            ("SMS", None, "Você foi selecionado para o Programa Diamante Orqestra. Acumule pontos e troque por viagens. Saiba mais: orqestra.com.br/diamante"),
            ("Push", "Programa Diamante", "Acumule pontos em cada transação e troque por experiências exclusivas."),
        ],
        "reviews_approved": True,
        "comments": [
            ("ana@email.com", "Analista de negócios", "Campanha publicada com sucesso. Monitorar métricas semanalmente."),
        ],
    },
    # 5 — CONTENT_ADJUSTMENT
    {
        "name": "Alerta de Segurança Digital",
        "category": "Regulatório",
        "objective": "Notificar clientes sobre novas medidas de segurança e autenticação em dois fatores",
        "result": "Ativação de 2FA por 80% dos clientes notificados dentro de 15 dias",
        "area": "Compliance",
        "audience": "Todos os clientes PF e PJ ativos que ainda não ativaram a autenticação em dois fatores",
        "exclusion": "Clientes que já possuem 2FA ativo, contas encerradas",
        "volume": 8000000,
        "tone": "Urgente",
        "priority": "Regulatório / Obrigatório",
        "status": "CONTENT_ADJUSTMENT",
        "days_ago": 15,
        "transitions": [
            (None, "DRAFT"),
            ("DRAFT", "CREATIVE_STAGE"),
            ("CREATIVE_STAGE", "CONTENT_REVIEW"),
            ("CONTENT_REVIEW", "CONTENT_ADJUSTMENT"),
        ],
        "pieces": [
            ("SMS", None, "URGENTE: Ative sua verificação em 2 etapas agora. Acesse: orqestra.com.br/seguranca"),
        ],
        "reviews_rejected": True,
        "rejection_reason": "O texto transmite urgência excessiva e pode ser confundido com phishing. Reformular linguagem.",
        "comments": [
            ("eric@email.com", "Gestor de marketing", "Ajustar tom da mensagem. Está parecendo alarmista demais."),
        ],
    },
    # 6 — CAMPAIGN_BUILDING
    {
        "name": "Campanha Pix Sem Limites",
        "category": "Upsell",
        "objective": "Estimular a adoção do Pix para transferências de alto valor com limites ampliados",
        "result": "Aumento de 40% no volume de Pix acima de R$ 5.000 e incremento de 15% na receita de tarifas premium",
        "audience": "Clientes PF e PJ com movimentação mensal superior a R$ 10.000",
        "exclusion": "Contas com restrição de movimentação, clientes em análise de compliance",
        "volume": 4000000,
        "tone": "Informal",
        "priority": "Normal",
        "status": "CAMPAIGN_BUILDING",
        "days_ago": 20,
        "transitions": [
            (None, "DRAFT"),
            ("DRAFT", "CREATIVE_STAGE"),
            ("CREATIVE_STAGE", "CONTENT_REVIEW"),
            ("CONTENT_REVIEW", "CAMPAIGN_BUILDING"),
        ],
        "pieces": [
            ("SMS", None, "Pix sem limites no Orqestra! Transfira valores altos com segurança. Ative: orqestra.com.br/pix"),
            ("Push", "Pix ilimitado", "Seus limites de Pix foram ampliados. Confira as novas condições no app."),
        ],
        "reviews_approved": True,
    },
    # 7 — CREATIVE_STAGE (with SMS piece)
    {
        "name": "Educação Financeira para Jovens",
        "category": "Educacional",
        "objective": "Engajar público jovem com conteúdo educativo sobre finanças pessoais",
        "result": "Alcançar 50.000 jovens e aumentar abertura de contas na faixa 18-25 em 10%",
        "area": "Marketing Institucional",
        "audience": "Pessoas de 18 a 25 anos, estudantes universitários ou recém-formados",
        "exclusion": "Menores de 18 anos",
        "volume": 500000,
        "tone": "Informal",
        "status": "CREATIVE_STAGE",
        "days_ago": 8,
        "transitions": [(None, "DRAFT"), ("DRAFT", "CREATIVE_STAGE")],
        "pieces": [
            ("SMS", None, "Orqestra Educa: aprenda a investir com R$ 10. Assista agora: orqestra.com.br/educa"),
        ],
    },
    # 8 — CONTENT_REVIEW (with PUSH piece)
    {
        "name": "Renegociação de Dívidas - Recuperação",
        "category": "Retenção",
        "objective": "Oferecer condições especiais para renegociação de dívidas em atraso",
        "result": "Recuperação de 30% dos valores inadimplentes e redução de 15% na carteira em atraso",
        "audience": "Clientes PF com parcelas em atraso entre 30 e 180 dias",
        "exclusion": "Dívidas judicializadas, clientes em processo de falência",
        "volume": 6000000,
        "tone": "Consultivo",
        "priority": "Alta",
        "execution": "Event-driven (por evento)",
        "trigger": "Fatura fechada",
        "status": "CONTENT_REVIEW",
        "days_ago": 10,
        "transitions": [
            (None, "DRAFT"),
            ("DRAFT", "CREATIVE_STAGE"),
            ("CREATIVE_STAGE", "CONTENT_REVIEW"),
        ],
        "pieces": [
            ("Push", "Condições especiais pra você", "Negocie suas pendências com até 90% de desconto nos juros. Só até sexta!"),
        ],
        "reviews_pending": True,
    },
    # 9 — CAMPAIGN_PUBLISHED
    {
        "name": "Black Friday Investimentos",
        "category": "Cross-sell",
        "objective": "Atrair novos investidores com taxas promocionais em CDB e fundos durante a Black Friday",
        "result": "Captação de R$ 50 milhões em novos investimentos e 8.000 novos investidores",
        "area": "Produtos PF",
        "audience": "Correntistas com saldo em conta acima de R$ 1.000 que nunca investiram pelo banco",
        "exclusion": "Clientes com perfil de investidor já ativo, funcionários",
        "volume": 2000000,
        "tone": "Informal",
        "priority": "Alta",
        "status": "CAMPAIGN_PUBLISHED",
        "days_ago": 45,
        "transitions": [
            (None, "DRAFT"),
            ("DRAFT", "CREATIVE_STAGE"),
            ("CREATIVE_STAGE", "CONTENT_REVIEW"),
            ("CONTENT_REVIEW", "CAMPAIGN_BUILDING"),
            ("CAMPAIGN_BUILDING", "CAMPAIGN_PUBLISHED"),
        ],
        "pieces": [
            ("SMS", None, "Black Friday Orqestra: CDB a 120% do CDI! Só até domingo. Invista: orqestra.com.br/bf"),
            ("Push", "Investimentos Black Friday", "CDB rendendo 120% do CDI. Oferta limitada!"),
        ],
        "reviews_approved": True,
        "comments": [
            ("ana@email.com", "Analista de negócios", "Campanha encerrada. Superamos a meta em 12%."),
            ("jose@email.com", "Analista de campanhas", "Métricas finais enviadas ao board."),
        ],
    },
    # 10 — DRAFT (very recent)
    {
        "name": "Abertura de Conta MEI",
        "category": "Aquisição",
        "objective": "Facilitar abertura de conta PJ para microempreendedores individuais com processo 100% digital",
        "result": "Abertura de 2.000 contas MEI no primeiro mês e crescimento de 20% na base PJ",
        "area": "Produtos PJ",
        "audience": "Microempreendedores individuais sem conta PJ ativa",
        "exclusion": "MEIs com restrição cadastral, CNPJ inativo",
        "volume": 300000,
        "tone": "Informal",
        "priority": "Normal",
        "status": "DRAFT",
        "days_ago": 1,
        "transitions": [(None, "DRAFT")],
    },
    # 11 — CREATIVE_STAGE — todos os canais + 2 espaços comerciais APP (campanha-exemplo)
    {
        "name": "Campanha Multicanal - Crédito Consignado",
        "category": "Cross-sell",
        "objective": "Oferecer crédito consignado com taxas competitivas em todos os canais de comunicação, incluindo banners in-app em dois espaços comerciais distintos",
        "result": "Contratação de 4.000 novos consignados e aumento de 18% na carteira de crédito PF",
        "area": "Produtos PF",
        "audience": "Servidores públicos e aposentados com margem consignável disponível, correntistas há mais de 3 meses",
        "exclusion": "Clientes com score abaixo de 500, inadimplentes, já com consignado ativo no banco",
        "volume": 3500000,
        "tone": "Consultivo",
        "priority": "Alta",
        "channels": ["SMS", "Push", "E-mail", "App"],
        "spaces": ["Banner superior da Home", "Página de ofertas"],
        "status": "CREATIVE_STAGE",
        "days_ago": 3,
        "transitions": [(None, "DRAFT"), ("DRAFT", "CREATIVE_STAGE")],
        "pieces": [
            ("SMS", None, "Orqestra: crédito consignado a partir de 1,49% a.m. Simule agora: orqestra.com.br/consignado"),
            ("Push", "Crédito Consignado Orqestra", "Taxas a partir de 1,49% a.m. com parcelas que cabem no seu bolso. Simule!"),
            ("E-mail", "Crédito Consignado - Condições Exclusivas", None),
            ("App", "Banner Consignado Home", None),
            ("App", "Banner Consignado Ofertas", None),
        ],
    },
]


def upgrade() -> None:
    # ── Resolve user IDs ──────────────────────────────────────────────
    ana_id = _get_user_id("ana@email.com")
    maria_id = _get_user_id("maria@email.com")
    eric_id = _get_user_id("eric@email.com")
    jose_id = _get_user_id("jose@email.com")

    if not ana_id:
        print("Warning: Could not find ana@email.com. Skipping campaign seeding.")
        return

    conn = op.get_bind()

    # ── Skip if campaigns already exist ───────────────────────────────
    existing = conn.execute(sa.text("SELECT count(*) FROM campaigns")).scalar()
    if existing and existing > 0:
        print(f"Campaigns already exist ({existing}). Skipping campaign seeding.")
    else:
        now = datetime.now(timezone.utc)

        for camp_def in CAMPAIGNS:
            cid = _uid()

            _insert_campaign(conn, cid, camp_def, ana_id, camp_def["days_ago"])

            _insert_status_events(
                conn, cid,
                camp_def["transitions"],
                ana_id,
                camp_def["days_ago"],
            )

            # ── Creative pieces ───────────────────────────────────────
            piece_entries: list[tuple[str, str]] = []  # (channel, piece_id)
            for piece_def in camp_def.get("pieces", []):
                ptype = piece_def[0]
                title = piece_def[1]
                body = piece_def[2] if len(piece_def) > 2 else piece_def[1]
                pid = _uid()
                piece_days = max(1, camp_def["days_ago"] - 2)
                _insert_piece(conn, pid, cid, ptype, title, body, piece_days)
                piece_entries.append((ptype, pid))

            # ── Piece reviews (approved) ──────────────────────────────
            if camp_def.get("reviews_approved") and eric_id:
                review_time = now - timedelta(days=max(1, camp_def["days_ago"] - 4), hours=1)
                for ch, pid in piece_entries:
                    _insert_review(
                        conn, cid, ch, pid,
                        human_verdict="approved",
                        reviewed_by=eric_id,
                        reviewed_at=review_time,
                        ia_verdict="APROVADO",
                    )
                    _insert_review_event(
                        conn, cid, ch, pid,
                        event_type="approved",
                        actor_id=eric_id,
                        ts=review_time,
                        ia_verdict="APROVADO",
                    )

            # ── Piece reviews (pending) ───────────────────────────────
            if camp_def.get("reviews_pending") and eric_id:
                for ch, pid in piece_entries:
                    _insert_review(
                        conn, cid, ch, pid,
                        human_verdict="pending",
                        reviewed_by=None,
                        reviewed_at=None,
                        ia_verdict="APROVADO",
                    )

            # ── Piece reviews (rejected) ──────────────────────────────
            if camp_def.get("reviews_rejected") and eric_id:
                review_time = now - timedelta(days=max(1, camp_def["days_ago"] - 5))
                reason = camp_def.get("rejection_reason", "Ajustes necessários")
                for ch, pid in piece_entries:
                    _insert_review(
                        conn, cid, ch, pid,
                        human_verdict="rejected",
                        reviewed_by=eric_id,
                        reviewed_at=review_time,
                        reason=reason,
                    )
                    _insert_review_event(
                        conn, cid, ch, pid,
                        event_type="rejected",
                        actor_id=eric_id,
                        ts=review_time,
                        reason=reason,
                    )

            # ── Comments ──────────────────────────────────────────────
            for comment_def in camp_def.get("comments", []):
                email, role, text = comment_def
                author_id = _get_user_id(email)
                if author_id:
                    _insert_comment(conn, cid, author_id, role, text, max(0, camp_def["days_ago"] - 3))

        conn.commit()
        print(f"Seeded {len(CAMPAIGNS)} default campaigns with pieces, reviews and comments.")

    # ── Seed default channel specs ────────────────────────────────────
    specs_exist = conn.execute(sa.text("SELECT 1 FROM channel_specs LIMIT 1")).first()

    if not specs_exist:
        default_specs = [
            # SMS
            {"id": _uid(), "channel": "SMS", "commercial_space": None, "field_name": "body",
             "min_chars": 1, "max_chars": 160, "warn_chars": None,
             "max_weight_kb": None, "min_width": None, "min_height": None,
             "max_width": None, "max_height": None, "expected_width": None, "expected_height": None,
             "tolerance_pct": None},
            # PUSH
            {"id": _uid(), "channel": "PUSH", "commercial_space": None, "field_name": "title",
             "min_chars": 1, "max_chars": 50, "warn_chars": None,
             "max_weight_kb": None, "min_width": None, "min_height": None,
             "max_width": None, "max_height": None, "expected_width": None, "expected_height": None,
             "tolerance_pct": None},
            {"id": _uid(), "channel": "PUSH", "commercial_space": None, "field_name": "body",
             "min_chars": 1, "max_chars": 120, "warn_chars": None,
             "max_weight_kb": None, "min_width": None, "min_height": None,
             "max_width": None, "max_height": None, "expected_width": None, "expected_height": None,
             "tolerance_pct": None},
            # EMAIL
            {"id": _uid(), "channel": "EMAIL", "commercial_space": None, "field_name": "html",
             "min_chars": 1, "max_chars": None, "warn_chars": None,
             "max_weight_kb": 100, "min_width": None, "min_height": None,
             "max_width": None, "max_height": None, "expected_width": None, "expected_height": None,
             "tolerance_pct": None},
            {"id": _uid(), "channel": "EMAIL", "commercial_space": None, "field_name": "rendered_image",
             "min_chars": None, "max_chars": None, "warn_chars": None,
             "max_weight_kb": 500, "min_width": None, "min_height": None,
             "max_width": None, "max_height": None, "expected_width": None, "expected_height": None,
             "tolerance_pct": None},
            # APP — genérico
            {"id": _uid(), "channel": "APP", "commercial_space": None, "field_name": "image",
             "min_chars": None, "max_chars": None, "warn_chars": None,
             "max_weight_kb": 1024, "min_width": 300, "min_height": 300,
             "max_width": 4096, "max_height": 4096, "expected_width": None, "expected_height": None,
             "tolerance_pct": None},
            # APP — espaços comerciais
            {"id": _uid(), "channel": "APP", "commercial_space": "Banner superior da Home", "field_name": "image",
             "min_chars": None, "max_chars": None, "warn_chars": None,
             "max_weight_kb": 300, "min_width": None, "min_height": None,
             "max_width": None, "max_height": None, "expected_width": 1200, "expected_height": 628,
             "tolerance_pct": 5},
            {"id": _uid(), "channel": "APP", "commercial_space": "Área do Cliente", "field_name": "image",
             "min_chars": None, "max_chars": None, "warn_chars": None,
             "max_weight_kb": 500, "min_width": None, "min_height": None,
             "max_width": None, "max_height": None, "expected_width": 1080, "expected_height": 1920,
             "tolerance_pct": 5},
            {"id": _uid(), "channel": "APP", "commercial_space": "Página de ofertas", "field_name": "image",
             "min_chars": None, "max_chars": None, "warn_chars": None,
             "max_weight_kb": 300, "min_width": None, "min_height": None,
             "max_width": None, "max_height": None, "expected_width": 600, "expected_height": 314,
             "tolerance_pct": 5},
            {"id": _uid(), "channel": "APP", "commercial_space": "Comprovante do Pix", "field_name": "image",
             "min_chars": None, "max_chars": None, "warn_chars": None,
             "max_weight_kb": 400, "min_width": None, "min_height": None,
             "max_width": None, "max_height": None, "expected_width": 800, "expected_height": 600,
             "tolerance_pct": 10},
        ]

        for spec in default_specs:
            conn.execute(
                sa.text("""
                    INSERT INTO channel_specs (
                        id, channel, commercial_space, field_name,
                        min_chars, max_chars, warn_chars, max_weight_kb,
                        min_width, min_height, max_width, max_height,
                        expected_width, expected_height, tolerance_pct
                    ) VALUES (
                        :id, :channel, :commercial_space, :field_name,
                        :min_chars, :max_chars, :warn_chars, :max_weight_kb,
                        :min_width, :min_height, :max_width, :max_height,
                        :expected_width, :expected_height, :tolerance_pct
                    )
                """),
                spec,
            )
        conn.commit()
        print(f"Seeded {len(default_specs)} default channel specs")


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("DELETE FROM channel_specs"))

    for camp_def in CAMPAIGNS:
        result = conn.execute(
            sa.text("SELECT id FROM campaigns WHERE name = :name"),
            {"name": camp_def["name"]},
        ).first()

        if result:
            cid = result[0]
            conn.execute(sa.text("DELETE FROM piece_review_event WHERE campaign_id = :cid"), {"cid": cid})
            conn.execute(sa.text("DELETE FROM piece_review WHERE campaign_id = :cid"), {"cid": cid})
            conn.execute(sa.text("DELETE FROM creative_pieces WHERE campaign_id = :cid"), {"cid": cid})
            conn.execute(sa.text("DELETE FROM comments WHERE campaign_id = :cid"), {"cid": cid})
            conn.execute(sa.text("DELETE FROM campaign_status_event WHERE campaign_id = :cid"), {"cid": cid})
            conn.execute(sa.text("DELETE FROM campaigns WHERE id = :cid"), {"cid": cid})

    conn.commit()
