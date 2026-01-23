"""Initial schema for auth service

Revision ID: 001
Revises: 
Create Date: 2024-01-01

"""
import sys
import os
import uuid
from alembic import op
import sqlalchemy as sa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('role', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=True, server_default='false'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    # Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_token'), 'refresh_tokens', ['token'], unique=True)
    
    # Create login_audits table
    op.create_table(
        'login_audits',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('failure_reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_login_audits_user_id'), 'login_audits', ['user_id'], unique=False)
    op.create_index(op.f('ix_login_audits_email'), 'login_audits', ['email'], unique=False)
    op.create_index(op.f('ix_login_audits_created_at'), 'login_audits', ['created_at'], unique=False)
    
    # Generate password hash (same for all test users)
    if HAS_BCRYPT:
        hashed_password = bcrypt.hashpw(b'123', bcrypt.gensalt()).decode('utf-8')
    else:
        # Fallback: pre-generated bcrypt hash for password "123"
        hashed_password = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqTqL2f8TC'
    
    # Create default users for testing
    # All users have password: 123
    default_users = [
        {
            "email": "ana@email.com",
            "full_name": "Ana",
            "role": "Analista de negócios"
        },
        {
            "email": "maria@email.com",
            "full_name": "Maria",
            "role": "Analista de criação"
        },
        {
            "email": "jose@email.com",
            "full_name": "José",
            "role": "Analista de campanhas"
        }
    ]
    
    connection = op.get_bind()
    
    for user_data in default_users:
        # Check if user already exists
        result = connection.execute(
            sa.text("SELECT id FROM users WHERE email = :email"),
            {"email": user_data["email"]}
        ).first()
        
        if not result:
            user_id = str(uuid.uuid4())
            connection.execute(
                sa.text("""
                    INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_superuser)
                    VALUES (:id, :email, :hashed_password, :full_name, :role, :is_active, :is_superuser)
                """),
                {
                    "id": user_id,
                    "email": user_data["email"],
                    "hashed_password": hashed_password,
                    "full_name": user_data["full_name"],
                    "role": user_data["role"],
                    "is_active": True,
                    "is_superuser": False
                }
            )
    
    connection.commit()


def downgrade() -> None:
    op.drop_index(op.f('ix_login_audits_created_at'), table_name='login_audits')
    op.drop_index(op.f('ix_login_audits_email'), table_name='login_audits')
    op.drop_index(op.f('ix_login_audits_user_id'), table_name='login_audits')
    op.drop_table('login_audits')
    op.drop_index(op.f('ix_refresh_tokens_token'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

