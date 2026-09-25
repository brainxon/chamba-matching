-- Issue #355/#379 — correr contra la DB REAL de staging (cover_letter_db_stg),
-- en la EC2 que YA EXISTE hoy (la del backend real).
--
-- Corrige el GRANT anterior (003-grant-user-cv-versions-read.sql): se
-- verificó con una cuenta real que "CV Maestro" (la feature real de la
-- UI, con completitud 40%/100% por idioma) NO está respaldada por
-- `user_cvs`/`user_cv_versions` — esa cuenta tenía CERO filas ahí, y
-- `users.current_user_cv_id` en NULL, a pesar de tener 4 CVs reales
-- visibles en la UI. La fuente real es `root_curriculum_vitaes` (una
-- fila POR IDIOMA por usuario) + `root_curriculum_vitae_versions`
-- (versionado dentro de cada idioma) — ver
-- ../../poc-pgvector-matching/api/users_repo.py.
--
-- GRANTs por COLUMNA, no por tabla completa — mismo criterio de mínimo
-- privilegio que el resto del proyecto. Esta vez NI SIQUIERA hace falta
-- tocar `users` — `root_curriculum_vitaes.user_id` ya alcanza para
-- identificar de quién es cada CV, sin acceso a email/nombre/etc.
--
-- Ejecutar (ajustar rol/DB si el nombre real difiere):
--   psql -h <host> -U <admin> -d cover_letter_db_stg < 004-grant-root-cv-versions-read.sql

GRANT SELECT (id, user_id, language, latest_version_id, created_at) ON public.root_curriculum_vitaes TO app_reader;
GRANT SELECT (id, root_cv_id, version_number, cv_json, created_at) ON public.root_curriculum_vitae_versions TO app_reader;

-- Limpieza: revertir el GRANT anterior sobre las tablas que resultaron
-- ser la feature equivocada (sin datos reales de usuarios) — mínimo
-- privilegio, sacamos lo que no hace falta.
REVOKE SELECT ON public.users FROM app_reader;
REVOKE SELECT ON public.user_cvs FROM app_reader;
REVOKE SELECT ON public.user_cv_versions FROM app_reader;

-- Verificación sugerida (correr después, conectado como app_reader):
--   SELECT rcv.language, length(rcvv.cv_json)
--   FROM root_curriculum_vitaes rcv
--   JOIN root_curriculum_vitae_versions rcvv ON rcvv.root_cv_id = rcv.id
--   LIMIT 5;                                            -- debe funcionar
--   SELECT email FROM users LIMIT 1;                     -- debe fallar: permission denied for table users
