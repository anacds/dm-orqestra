"""Initial schema - enhanceable_fields table

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'enhanceable_fields',
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('expectations', sa.Text(), nullable=False),
        sa.Column('improvement_guidelines', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('field_name')
    )
    
    op.execute("""
        INSERT INTO enhanceable_fields (field_name, display_name, expectations, improvement_guidelines) VALUES
        ('businessObjective', 'Objetivo de Negócio', 
         'O objetivo de negócio deve ser claro e alinhado com as metas estratégicas da empresa. Deve descrever o que se pretende alcançar com a campanha e como os clientes serão tocados, evitando termos vagos ou genéricos.',
         'Aprimore tornando o objetivo mais específico, eliminando ambiguidades e garantindo que seja acionável. Evite objetivos muito amplos que não possam ser medidos.'),
        
        ('expectedResult', 'Resultado Esperado / KPI Principal',
         'O resultado esperado deve ser mensurável e relacionado diretamente ao objetivo de negócio. Deve incluir métricas claras (porcentagens, valores, prazos) e ser realista.',
         'Aprimore especificando placeholders para métricas concretas e prazos claros, garantindo que o resultado seja mensurável e diretamente relacionado ao objetivo de negócio definido.'),
        
        ('targetAudienceDescription', 'Descrição do Público-Alvo',
         'A descrição do público-alvo deve ser específica e detalhada, incluindo características demográficas, psicográficas, comportamentais e de necessidade. Deve ser suficientemente segmentada para permitir estratégias eficazes.',
         'Aprimore adicionando placeholders para que o usuário especifique detalhes demográficos específicos (idade, gênero, localização), características psicográficas (interesses, valores), comportamentos e necessidades claras. Evite descrições muito genéricas ou amplas demais. Transforme em bullets.'),
        
        ('exclusionCriteria', 'Critérios de Exclusão',
         'Os critérios de exclusão devem ser claros e específicos, definindo quem não deve ser incluído na campanha. Devem ser complementares à descrição do público-alvo e ajudar a refinar o segmento. Os critérios obrigatórios são: excluir clientes menores de 18 anos e com restrições na base de Riscos.',
         'Aprimore tornando os critérios mais específicos e mensuráveis. Garanta que os critérios sejam complementares ao público-alvo definido e ajudem a evitar desperdício de recursos em audiências não relevantes. Adicione os critérios obrigatórios se já não estiverem no texto. Transforme em bullets.') 
    """)


def downgrade() -> None:
    op.drop_table('enhanceable_fields')

