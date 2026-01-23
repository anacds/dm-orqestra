"""Add default users

Revision ID: 002
Revises: 001
Create Date: 2024-01-02

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
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    # Remove default users (optional - can be left empty if you don't want to remove users on downgrade)
    connection = op.get_bind()
    
    default_emails = ["ana@email.com", "maria@email.com", "jose@email.com"]
    
    for email in default_emails:
        connection.execute(
            sa.text("DELETE FROM users WHERE email = :email"),
            {"email": email}
        )
    
    connection.commit()

