from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from dotenv import load_dotenv


# ---------------------------------------------------------
# Add backend directory to Python import path
# ---------------------------------------------------------

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


# ---------------------------------------------------------
# Import database Base and models
# ---------------------------------------------------------

from app.database import Base
from app.models import Case


# ---------------------------------------------------------
# Load environment variables from .env
# ---------------------------------------------------------

load_dotenv()


# ---------------------------------------------------------
# Alembic Config object
# ---------------------------------------------------------

config = context.config


# ---------------------------------------------------------
# Get DATABASE_URL from .env
# ---------------------------------------------------------

database_url = os.getenv("DATABASE_URL")

if database_url:
    config.set_main_option(
        "sqlalchemy.url",
        database_url
    )


# ---------------------------------------------------------
# Configure Python logging
# ---------------------------------------------------------

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# ---------------------------------------------------------
# SQLAlchemy metadata
# ---------------------------------------------------------

target_metadata = Base.metadata


# ---------------------------------------------------------
# Prevent Alembic from modifying PostGIS system tables
# ---------------------------------------------------------

def include_object(
    object,
    name,
    type_,
    reflected,
    compare_to
):
    """
    Prevent Alembic from modifying PostGIS
    system tables such as spatial_ref_sys.
    """

    if type_ == "table" and name == "spatial_ref_sys":
        return False

    return True


# ---------------------------------------------------------
# Offline migrations
# ---------------------------------------------------------

def run_migrations_offline() -> None:
    """
    Run migrations in offline mode.

    This generates SQL without creating
    a live database connection.
    """

    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------
# Online migrations
# ---------------------------------------------------------

def run_migrations_online() -> None:
    """
    Run migrations in online mode.

    This connects directly to PostgreSQL
    and applies the migrations.
    """

    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section,
            {}
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------
# Run migration mode
# ---------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()