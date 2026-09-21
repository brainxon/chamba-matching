import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    jobs_db_host: str
    jobs_db_port: int
    jobs_db_user: str
    jobs_db_password: str
    jobs_db_name: str

    # DB REAL del backend (chamba-ai-backend-fastapi) - accedida solo
    # lectura, vía un rol Postgres dedicado (app_reader en staging,
    # poc_pgvector_reader en dev-infra) con GRANT SELECT únicamente. Nunca
    # se escribe nada acá - ver ../deploy/ec2-code-deploy-manual.md.
    backend_db_host: str
    backend_db_port: int
    backend_db_user: str
    backend_db_password: str
    backend_db_name: str

    embed_dim: int

    # Esquema `matching` dentro de la MISMA base de datos real - rol
    # DISTINTO al de solo lectura de arriba (matching_service), con
    # permisos únicamente sobre el esquema `matching`, nunca sobre
    # `public`. Ver ../deploy/sql/001-create-matching-service-role.sql.
    matching_db_host: str
    matching_db_port: int
    matching_db_user: str
    matching_db_password: str
    matching_db_name: str


def _load() -> Settings:
    return Settings(
        jobs_db_host=os.getenv("JOBS_DB_HOST", "db"),
        jobs_db_port=int(os.getenv("JOBS_DB_PORT", "5432")),
        jobs_db_user=os.getenv("JOBS_DB_USER", "poc_app"),
        jobs_db_password=os.getenv("JOBS_DB_PASSWORD", "poc_pass"),
        jobs_db_name=os.getenv("JOBS_DB_NAME", "chamba_jobs_hot"),

        backend_db_host=os.getenv("BACKEND_DB_HOST", "host.docker.internal"),
        backend_db_port=int(os.getenv("BACKEND_DB_PORT", "5434")),
        backend_db_user=os.getenv("BACKEND_DB_USER", "poc_pgvector_reader"),
        backend_db_password=os.getenv("BACKEND_DB_PASSWORD", ""),
        backend_db_name=os.getenv("BACKEND_DB_NAME", "chambai"),

        embed_dim=int(os.getenv("EMBED_DIM", "384")),

        matching_db_host=os.getenv("MATCHING_DB_HOST", "host.docker.internal"),
        matching_db_port=int(os.getenv("MATCHING_DB_PORT", "5434")),
        matching_db_user=os.getenv("MATCHING_DB_USER", "matching_service"),
        matching_db_password=os.getenv("MATCHING_DB_PASSWORD", ""),
        matching_db_name=os.getenv("MATCHING_DB_NAME", "chambai"),
    )


settings = _load()


def jobs_dsn() -> str:
    s = settings
    return f"host={s.jobs_db_host} port={s.jobs_db_port} user={s.jobs_db_user} password={s.jobs_db_password} dbname={s.jobs_db_name}"


def backend_dsn() -> str:
    s = settings
    return f"host={s.backend_db_host} port={s.backend_db_port} user={s.backend_db_user} password={s.backend_db_password} dbname={s.backend_db_name}"


def matching_dsn() -> str:
    s = settings
    return f"host={s.matching_db_host} port={s.matching_db_port} user={s.matching_db_user} password={s.matching_db_password} dbname={s.matching_db_name}"
