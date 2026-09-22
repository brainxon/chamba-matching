-- Issue #355/#379 — correr contra la DB REAL de staging (cover_letter_db_stg),
-- en la EC2 que YA EXISTE hoy (la del backend real).
--
-- Por qué este cambio: `curriculum_vitae_versions` (el GRANT original de
-- app_reader) no tiene ningún flag de "actual" — un usuario puede tener
-- muchas filas ahí (una por aplicación/versión, más variantes por
-- idioma), así que no había forma de saber cuál es "el" CV completo de
-- la persona sin adivinar. `users.current_user_cv_id -> user_cvs.latest_version_id
-- -> user_cv_versions.id` sí tiene un puntero explícito al CV BASE
-- vigente, mantenido por la app real cada vez que el usuario lo edita —
-- es la fuente correcta para representar "el perfil completo" de
-- alguien en el matching.
--
-- GRANTs por COLUMNA, no por tabla completa — a propósito, para cumplir
-- con la restricción explícita de este proyecto: nunca exponer
-- información personal de la persona (nombre, email, etc.), solo el
-- contenido de su CV para poder calcular el embedding.
--   - users: SOLO id + current_user_cv_id (nunca email/nombre/password_hash/...)
--   - user_cvs: SOLO id + user_id + latest_version_id
--   - user_cv_versions: id, user_cv_id, version_number, language, cv_json, created_at
--     (cv_json es contenido del CV, no dato personal por sí mismo)
--
-- Ejecutar (ajustar rol/DB si el nombre real difiere):
--   psql -h <host> -U <admin> -d cover_letter_db_stg < 003-grant-user-cv-versions-read.sql
-- o vía docker exec -i chamba-db psql -U chamba_app -d cover_letter_db_stg < 003-...sql

GRANT SELECT (id, current_user_cv_id) ON public.users TO app_reader;
GRANT SELECT (id, user_id, latest_version_id) ON public.user_cvs TO app_reader;
GRANT SELECT (id, user_cv_id, version_number, language, cv_json, created_at) ON public.user_cv_versions TO app_reader;

-- Limpieza: ya no se usa curriculum_vitae_versions como fuente del
-- matching (ver arriba) — sacamos el acceso que ya no hace falta,
-- siguiendo el mismo principio de mínimo privilegio. Comentar esta
-- línea si algo más todavía depende de ese SELECT.
REVOKE SELECT ON public.curriculum_vitae_versions FROM app_reader;

-- Verificación sugerida (correr después, conectado como app_reader):
--   SELECT u.id, ucv2.language, length(ucv2.cv_json)
--   FROM users u
--   JOIN user_cvs ucv ON u.current_user_cv_id = ucv.id
--   JOIN user_cv_versions ucv2 ON ucv.latest_version_id = ucv2.id
--   LIMIT 5;                                                    -- debe funcionar
--   SELECT email FROM users LIMIT 1;                             -- debe fallar: permission denied for table users
