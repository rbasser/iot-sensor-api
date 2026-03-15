"""reboot_flag_string_to_boolean

Revision ID: e75b70123a4a
Revises: ef6f789c4789
Create Date: 2026-03-15 21:11:39.533200

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e75b70123a4a'
down_revision: Union[str, Sequence[str], None] = 'ef6f789c4789'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Convert existing string values to boolean before changing type
    op.execute("UPDATE sensor_readings SET reboot_flag = 'true' WHERE reboot_flag IS NOT NULL")
    
    op.alter_column('sensor_readings', 'reboot_flag',
        existing_type=sa.String(),
        type_=sa.Boolean(),
        existing_nullable=True,
        postgresql_using='reboot_flag IS NOT NULL'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('sensor_readings', 'reboot_flag',
               existing_type=sa.Boolean(),
               type_=sa.VARCHAR(),
               existing_nullable=True)
