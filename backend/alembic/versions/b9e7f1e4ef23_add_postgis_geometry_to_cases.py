"""add PostGIS geometry to cases

Revision ID: b9e7f1e4ef23
Revises: 8e834fb8afc5
Create Date: 2026-09-07 18:31:24.807569

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


# revision identifiers, used by Alembic.
revision: str = "b9e7f1e4ef23"
down_revision: Union[str, Sequence[str], None] = "8e834fb8afc5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Add PostGIS geometry column
    op.add_column(
        "cases",
        sa.Column(
            "aoi_geometry",
            Geometry(
                geometry_type="POLYGON",
                srid=4326,
                dimension=2,
            ),
            nullable=True,
        ),
    )

    # Create spatial GiST index safely
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cases_aoi_geometry
        ON cases
        USING GIST (aoi_geometry)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Remove spatial index safely
    op.execute(
        """
        DROP INDEX IF EXISTS idx_cases_aoi_geometry
        """
    )

    # Remove geometry column
    op.drop_column("cases", "aoi_geometry")