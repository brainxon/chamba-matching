# chamba-matching

Servicio de **matching CV ↔ ofertas de trabajo** vía embeddings + búsqueda por
similitud (pgvector), autohospedado (sin depender de un servicio de vectores
administrado de AWS). Nace del spike de la issue
[chamba-ai#355](https://github.com/brainxon/chamba-ai/issues/355) — el
seguimiento del análisis, la comparativa de costos y las decisiones de
arquitectura vive en el workspace principal
(`.issues/355-pgvector-matching-poc/feature_spec.md`), no en este repo.

## Qué hace

1. **Ingesta de "hot jobs"** — ofertas de trabajo scrapeadas de fuentes
   externas (`poc-job-posting-fetch/`), guardadas con su embedding en una
   base de datos Postgres+pgvector **propia y separada** de la base de datos
   de usuarios — decisión de arquitectura explícita del issue #355: si la
   fuente externa se ve comprometida, el radio de impacto no llega a datos de
   usuarios.
2. **Matching** — dado un CV (leído solo-lectura desde la base de datos real
   del backend), calcula su embedding y busca las ofertas más similares por
   distancia coseno (`<=>` de pgvector, índice HNSW).
3. **Resultados** — se escriben en un esquema `matching` dentro de la misma
   base de datos real del backend (`cv_embeddings_cache`, `match_results`),
   para que el backend los pueda servir aunque la máquina de matching esté
   apagada (ver `deployment-cost-proposal.md` en el workspace principal para
   el razonamiento completo de por qué ahí y no en la DB separada).

## Estructura de este repo

```
chamba-matching/
├── poc-pgvector-matching/   ← el servicio en sí (API, batch de matching, demo interactiva)
├── poc-job-posting-fetch/   ← copia empaquetada del scraper (issue #229) — ver nota abajo
└── deploy/                  ← manuales + scripts para levantar esto en AWS (EC2 + Lambda + EventBridge)
```

Detalle de cada carpeta en su propio `README.md`.

⚠️ **`poc-job-posting-fetch/` es una copia, no la fuente de verdad.** El PoC
original de scraping (issue #229) evoluciona por su cuenta fuera de este
repo. Se empaquetó una copia acá para que `git clone` de este repo sea
autocontenido en la EC2 de producción (sin depender de rutas relativas hacia
otras carpetas del workspace, que no existen ahí). Si el scraper original
cambia, esta copia puede quedar desactualizada — revisar antes de asumir que
están sincronizados.

## Cómo se despliega

Ver `deploy/aws-services-manual.md` (crea EC2 + Lambda + EventBridge desde
AWS CloudShell) y `deploy/ec2-code-deploy-manual.md` (clona este repo en esa
EC2 y levanta el stack) — ambos pensados para copiar y pegar comando por
comando, sin instalar nada localmente más que el AWS CLI.

## Estado

PoC/piloto en validación contra el entorno de staging real (issue #355) —
**no** es todavía la solución final confirmada para producción (ver
`deployment-cost-proposal.md` para las alternativas aún abiertas, ej. Fargate
vs. esta EC2 con Lambda+EventBridge). No mergear a `develop`/`main` de
`chamba-ai-backend-fastapi` — este repo es independiente por diseño mientras
dure la validación.
