from logging.config import fileConfig
import os
import sys
from pathlib import Path
from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv
load_dotenv()

# Add the project root to Python path so `app` is importable
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Alembic Config object
config = context.config

# Logging configuration
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base and models so Alembic detects all tables
try:
    from app.models.models import Base
    import app.models.models  # This ensures all classes are registered with Base.metadata

    target_metadata = Base.metadata
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Current Python path:")
    for path in sys.path:
        print(f"  {path}")
    target_metadata = None

def get_database_url():
    """Get database URL from env or alembic.ini"""
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url
    return config.get_main_option("sqlalchemy.url")

def run_migrations_offline() -> None:
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    db_url = get_database_url()
    if db_url:
        configuration['sqlalchemy.url'] = db_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
