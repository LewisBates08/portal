"""Store reviewed candidate contact details and skills."""

from alembic import op
import sqlalchemy as sa


revision = "candidate_contact_skills"
down_revision = "readiness_20260913"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("candidates", sa.Column("email", sa.String(length=254)))
    op.add_column(
        "candidates",
        sa.Column("phone", sa.String(length=40), nullable=False, server_default=""),
    )
    op.add_column(
        "candidates",
        sa.Column(
            "skills", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
    )


def downgrade():
    op.drop_column("candidates", "skills")
    op.drop_column("candidates", "phone")
    op.drop_column("candidates", "email")
