from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base




class Case(Base):
    __tablename__ = "cases"

    case_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    aoi: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    aoi_geometry = mapped_column(
        Geometry(
            geometry_type="POLYGON",
            srid=4326,
            dimension=2,
        ),
        nullable=True,
    )

    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="created",
        nullable=False,
    )

    config_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    model_versions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )