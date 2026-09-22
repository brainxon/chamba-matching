import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

# Construye la URL desde las mismas JOBS_DB_* que usa api/config.py
# (jobs_dsn()) — sin ORM en este repo, así que no hay Base.metadata para
# autogenerate; las migraciones acá son SQL explícito (op.execute()).
jobs_db_host = os.getenv("JOBS_DB_HOST", "localhost")
jobs_db_port = os.getenv("JOBS_DB_PORT", "5432")
jobs_db_user = os.getenv("JOBS_DB_USER", "poc_app")
jobs_db_password = os.getenv("JOBS_DB_PASSWORD", "poc_pass")
jobs_db_name = os.getenv("JOBS_DB_NAME", "chamba_jobs_hot")

database_url = (
    f"postgresql+psycopg://{jobs_db_user}:{jobs_db_password}"
    f"@{jobs_db_host}:{jobs_db_port}/{jobs_db_name}"
)
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = None

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
