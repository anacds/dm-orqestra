"""Add default campaigns

Revision ID: 002
Revises: 001
Create Date: 2024-01-02

"""
import sys
import os
import uuid
from datetime import date, timedelta
from alembic import op
import sqlalchemy as sa
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def get_user_id_from_auth_service(email: str) -> str:
    """
    Get user ID from auth-service database by email.
    Since both services use the same PostgreSQL instance, we can query directly.
    Returns empty string if not found or connection fails.
    """
    try:
        
        db_host = os.getenv("DB_HOST", "db")
        db_user = os.getenv("POSTGRES_USER", "orqestra")
        db_password = os.getenv("POSTGRES_PASSWORD", "orqestra_password")
        db_port = os.getenv("DB_PORT", "5432")
        
        conn = psycopg2.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            port=db_port,
            database="auth_service"
        )
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return result[0]
        return ""
    except Exception:
        return ""


def upgrade() -> None:
    ana_email = "ana@email.com"
    user_id = get_user_id_from_auth_service(ana_email)
    
    if not user_id:
        print(f"Warning: Could not find user {ana_email} in auth-service. Skipping campaign creation.")
        return
    
    connection = op.get_bind()

    campaign1_exists = connection.execute(
        sa.text("SELECT 1 FROM campaigns WHERE name = :name"),
        {"name": "Campanha de Aquisição - Conta Corrente Digital"}
    ).first()
    
    if not campaign1_exists:
        start_date = date.today() + timedelta(days=7)
        end_date = start_date + timedelta(days=60)
        
        campaign1_id = str(uuid.uuid4())
        connection.execute(
            sa.text("""
                INSERT INTO campaigns (
                    id, name, category, business_objective, expected_result,
                    requesting_area, start_date, end_date, priority,
                    communication_channels, commercial_spaces,
                    target_audience_description, exclusion_criteria,
                    estimated_impact_volume, communication_tone,
                    execution_model, trigger_event, recency_rule_days,
                    status, created_by
                ) VALUES (
                    :id, :name, :category, :business_objective, :expected_result,
                    :requesting_area, :start_date, :end_date, :priority,
                    :communication_channels, :commercial_spaces,
                    :target_audience_description, :exclusion_criteria,
                    :estimated_impact_volume, :communication_tone,
                    :execution_model, :trigger_event, :recency_rule_days,
                    :status, :created_by
                )
            """),
            {
                "id": campaign1_id,
                "name": "Campanha de Aquisição - Conta Corrente Digital",
                "category": "Aquisição",
                "business_objective": "Aumentar a base de clientes com conta corrente digital através de ofertas atrativas e experiência simplificada de abertura",
                "expected_result": "Aquisição de 5.000 novos clientes e aumento de 15% na base de contas correntes digitais no período da campanha",
                "requesting_area": "Produtos PF",
                "start_date": start_date,
                "end_date": end_date,
                "priority": "Normal",
                "communication_channels": ["SMS", "Push", "E-mail", "App"],
                "commercial_spaces": ["Banner superior da Home", "Área do Cliente"],
                "target_audience_description": "Pessoas físicas entre 25 e 55 anos, sem vínculo bancário atual ou com necessidade de serviços financeiros digitais, residentes em áreas urbanas",
                "exclusion_criteria": "Clientes já ativos, menores de 18 anos, clientes com restrições no CPF, funcionários do banco",
                "estimated_impact_volume": 2500000.00,  
                "communication_tone": "Informal",
                "execution_model": "Batch (agendada)",
                "trigger_event": None,
                "recency_rule_days": 30,
                "status": "CREATIVE_STAGE",
                "created_by": user_id
            }
        )
    
    campaign2_exists = connection.execute(
        sa.text("SELECT 1 FROM campaigns WHERE name = :name"),
        {"name": "Campanha de Retenção - Conta PJ Premium"}
    ).first()
    
    if not campaign2_exists:
        start_date = date.today() + timedelta(days=14)
        end_date = start_date + timedelta(days=90)
        
        campaign2_id = str(uuid.uuid4())
        connection.execute(
            sa.text("""
                INSERT INTO campaigns (
                    id, name, category, business_objective, expected_result,
                    requesting_area, start_date, end_date, priority,
                    communication_channels, commercial_spaces,
                    target_audience_description, exclusion_criteria,
                    estimated_impact_volume, communication_tone,
                    execution_model, trigger_event, recency_rule_days,
                    status, created_by
                ) VALUES (
                    :id, :name, :category, :business_objective, :expected_result,
                    :requesting_area, :start_date, :end_date, :priority,
                    :communication_channels, :commercial_spaces,
                    :target_audience_description, :exclusion_criteria,
                    :estimated_impact_volume, :communication_tone,
                    :execution_model, :trigger_event, :recency_rule_days,
                    :status, :created_by
                )
            """),
            {
                "id": campaign2_id,
                "name": "Campanha de Retenção - Conta PJ Premium",
                "category": "Retenção",
                "business_objective": "Reduzir a taxa de encerramento de contas PJ e aumentar a retenção através de benefícios exclusivos e atendimento diferenciado",
                "expected_result": "Redução de 20% na taxa de churn de clientes PJ e aumento de 10% na satisfação do cliente medido através de NPS",
                "requesting_area": "Produtos PJ",
                "start_date": start_date,
                "end_date": end_date,
                "priority": "Alta",
                "communication_channels": ["E-mail", "App"],
                "commercial_spaces": ["Área do Cliente", "Página de ofertas"],
                "target_audience_description": "Empresas com faturamento anual entre R$ 500 mil e R$ 10 milhões, clientes ativos há mais de 6 meses com histórico de uso regular dos serviços",
                "exclusion_criteria": "Empresas em processo de encerramento, clientes com pendências financeiras, empresas inativas há mais de 3 meses",
                "estimated_impact_volume": 5000000.00,  
                "communication_tone": "Formal",
                "execution_model": "Event-driven (por evento)",
                "trigger_event": "Inatividade por 30 dias",
                "recency_rule_days": 60,
                "status": "DRAFT",
                "created_by": user_id
            }
        )
    
    if not campaign1_exists or not campaign2_exists:
        connection.commit()


def downgrade() -> None:
    connection = op.get_bind()
    
    default_campaign_names = [
        "Campanha de Aquisição - Conta Corrente Digital",
        "Campanha de Retenção - Conta PJ Premium"
    ]
    
    for name in default_campaign_names:
        connection.execute(
            sa.text("DELETE FROM campaigns WHERE name = :name"),
            {"name": name}
        )
    
    connection.commit()

