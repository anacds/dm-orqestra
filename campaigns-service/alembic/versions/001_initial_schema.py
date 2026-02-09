from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE campaign_status AS ENUM (
                'DRAFT', 
                'CREATIVE_STAGE', 
                'CONTENT_REVIEW', 
                'CONTENT_ADJUSTMENT', 
                'CAMPAIGN_BUILDING', 
                'CAMPAIGN_PUBLISHED'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE campaign_category AS ENUM (
                'Aquisição',
                'Cross-sell',
                'Upsell',
                'Retenção',
                'Relacionamento',
                'Regulatório',
                'Educacional'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE requesting_area AS ENUM (
                'Produtos PF',
                'Produtos PJ',
                'Compliance',
                'Canais Digitais',
                'Marketing Institucional'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE campaign_priority AS ENUM (
                'Normal',
                'Alta',
                'Regulatório / Obrigatório'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE communication_tone AS ENUM (
                'Formal',
                'Informal',
                'Urgente',
                'Educativo',
                'Consultivo'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE execution_model AS ENUM (
                'Batch (agendada)',
                'Event-driven (por evento)'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE trigger_event AS ENUM (
                'Fatura fechada',
                'Cliente ultrapassa limite do cartão',
                'Login no app',
                'Inatividade por 30 dias'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create campaigns table
    op.create_table(
        'campaigns',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('business_objective', sa.String(), nullable=False),
        sa.Column('expected_result', sa.String(), nullable=False),
        sa.Column('requesting_area', sa.String(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('priority', sa.String(), nullable=False),
        sa.Column('communication_channels', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('commercial_spaces', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('target_audience_description', sa.String(), nullable=False),
        sa.Column('exclusion_criteria', sa.String(), nullable=False),
        sa.Column('estimated_impact_volume', sa.Numeric(12, 2), nullable=False),
        sa.Column('communication_tone', sa.String(), nullable=False),
        sa.Column('execution_model', sa.String(), nullable=False),
        sa.Column('trigger_event', sa.String(), nullable=True),
        sa.Column('recency_rule_days', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='DRAFT'),
        sa.Column('created_by', sa.String(), nullable=False),  # References user.id in auth-service
        sa.Column('created_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create comments table
    op.create_table(
        'comments',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('campaign_id', sa.String(), nullable=False),
        sa.Column('author', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comments_campaign_id'), 'comments', ['campaign_id'], unique=False)
    
    # Create creative_pieces table
    op.create_table(
        'creative_pieces',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('campaign_id', sa.String(), nullable=False),
        sa.Column('piece_type', sa.String(), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('file_urls', sa.Text(), nullable=True),
        sa.Column('html_file_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_creative_pieces_campaign_id'), 'creative_pieces', ['campaign_id'], unique=False)
    
    # Create piece_review table (for CONTENT_REVIEW workflow)
    op.create_table(
        'piece_review',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('campaign_id', sa.String(), nullable=False),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('piece_id', sa.String(), nullable=False),
        sa.Column('commercial_space', sa.String(), nullable=False, server_default=''),
        sa.Column('ia_verdict', sa.String(), nullable=True),  # null = não validado por IA
        sa.Column('human_verdict', sa.String(), nullable=False, server_default='pending'),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by', sa.String(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_piece_review_campaign_id', 'piece_review', ['campaign_id'], unique=False)
    op.create_index('ix_piece_review_channel', 'piece_review', ['channel'], unique=False)
    op.create_index('ix_piece_review_piece_id', 'piece_review', ['piece_id'], unique=False)
    op.create_index(
        'ix_piece_review_lookup',
        'piece_review',
        ['campaign_id', 'channel', 'piece_id', 'commercial_space'],
        unique=True,
    )
    
    # Create piece_review_event table (immutable audit log)
    op.create_table(
        'piece_review_event',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('campaign_id', sa.String(), nullable=False),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('piece_id', sa.String(), nullable=False),
        sa.Column('commercial_space', sa.String(), nullable=False, server_default=''),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('ia_verdict', sa.String(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('actor_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_piece_review_event_campaign_id', 'piece_review_event', ['campaign_id'], unique=False)
    op.create_index(
        'ix_piece_review_event_piece_lookup',
        'piece_review_event',
        ['campaign_id', 'channel', 'piece_id', 'commercial_space'],
        unique=False,
    )
    
    # Create campaign_status_event table (immutable audit log of status transitions)
    op.create_table(
        'campaign_status_event',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('campaign_id', sa.String(), nullable=False),
        sa.Column('from_status', sa.String(), nullable=True),
        sa.Column('to_status', sa.String(), nullable=False),
        sa.Column('actor_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_campaign_status_event_campaign_id', 'campaign_status_event', ['campaign_id'], unique=False)
    op.create_index('ix_campaign_status_event_campaign_created', 'campaign_status_event', ['campaign_id', 'created_at'], unique=False)

    # Create channel_specs table (specs técnicos por canal/espaço comercial)
    op.create_table(
        'channel_specs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('commercial_space', sa.String(), nullable=True),
        sa.Column('field_name', sa.String(), nullable=False),
        sa.Column('min_chars', sa.Integer(), nullable=True),
        sa.Column('max_chars', sa.Integer(), nullable=True),
        sa.Column('warn_chars', sa.Integer(), nullable=True),
        sa.Column('max_weight_kb', sa.Integer(), nullable=True),
        sa.Column('min_width', sa.Integer(), nullable=True),
        sa.Column('min_height', sa.Integer(), nullable=True),
        sa.Column('max_width', sa.Integer(), nullable=True),
        sa.Column('max_height', sa.Integer(), nullable=True),
        sa.Column('expected_width', sa.Integer(), nullable=True),
        sa.Column('expected_height', sa.Integer(), nullable=True),
        sa.Column('tolerance_pct', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_channel_specs_channel', 'channel_specs', ['channel'], unique=False)
    op.create_index('ix_channel_specs_commercial_space', 'channel_specs', ['commercial_space'], unique=False)
    op.create_index(
        'ix_channel_specs_lookup',
        'channel_specs',
        ['channel', 'commercial_space', 'field_name'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_channel_specs_lookup', table_name='channel_specs')
    op.drop_index('ix_channel_specs_commercial_space', table_name='channel_specs')
    op.drop_index('ix_channel_specs_channel', table_name='channel_specs')
    op.drop_table('channel_specs')
    op.drop_index('ix_campaign_status_event_campaign_created', table_name='campaign_status_event')
    op.drop_index('ix_campaign_status_event_campaign_id', table_name='campaign_status_event')
    op.drop_table('campaign_status_event')
    op.drop_index('ix_piece_review_event_piece_lookup', table_name='piece_review_event')
    op.drop_index('ix_piece_review_event_campaign_id', table_name='piece_review_event')
    op.drop_table('piece_review_event')
    op.drop_index('ix_piece_review_lookup', table_name='piece_review')
    op.drop_index('ix_piece_review_piece_id', table_name='piece_review')
    op.drop_index('ix_piece_review_channel', table_name='piece_review')
    op.drop_index('ix_piece_review_campaign_id', table_name='piece_review')
    op.drop_table('piece_review')
    op.drop_index(op.f('ix_creative_pieces_campaign_id'), table_name='creative_pieces')
    op.drop_table('creative_pieces')
    op.drop_index(op.f('ix_comments_campaign_id'), table_name='comments')
    op.drop_table('comments')
    op.drop_table('campaigns')
    
    op.execute("DROP TYPE IF EXISTS trigger_event")
    op.execute("DROP TYPE IF EXISTS execution_model")
    op.execute("DROP TYPE IF EXISTS communication_tone")
    op.execute("DROP TYPE IF EXISTS campaign_priority")
    op.execute("DROP TYPE IF EXISTS requesting_area")
    op.execute("DROP TYPE IF EXISTS campaign_category")
    op.execute("DROP TYPE IF EXISTS campaign_status")
