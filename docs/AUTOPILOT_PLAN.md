# JobPilot Autopilot — Plan Maestro de Implementación

> **Documento de referencia técnica.** Recoge la investigación, decisiones de arquitectura y el plan de implementación completo del sistema de automatización de búsqueda y aplicación de empleo de JobPilot. Diseñado para que cualquier sesión futura (humana o agente) retome el trabajo con contexto completo.

- **Proyecto:** JobPilot — `C:\Users\Miguel\Documents\Cortex\Proyectos\JobPilot`
- **Repositorio:** `https://github.com/megatron54/JobPilot.git`
- **Última actualización:** 2026-06-29
- **Estado:** Planificación completa — pendiente de iniciar implementación (Fase 1)
- **Versión del plan:** 1.0

---

## Tabla de Contenidos

1. [Objetivo y Visión](#1-objetivo-y-visión)
2. [Decisiones del Usuario](#2-decisiones-del-usuario)
3. [Estado Actual del Proyecto](#3-estado-actual-del-proyecto)
4. [Arquitectura General](#4-arquitectura-general)
5. [Estrategia Git (Gitflow)](#5-estrategia-git-gitflow)
6. [Pipeline de Procesamiento](#6-pipeline-de-procesamiento)
7. [LinkedIn Voyager API (Motor de Lectura)](#7-linkedin-voyager-api-motor-de-lectura)
8. [Motor de Matching y LLM](#8-motor-de-matching-y-llm)
9. [Sistema de Cola y Confirmación](#9-sistema-de-cola-y-confirmación)
10. [Ejecución de Acciones (Playwright)](#10-ejecución-de-acciones-playwright)
11. [Aplicaciones Externas (Form Filler Universal)](#11-aplicaciones-externas-form-filler-universal)
12. [Comunicación Tauri ↔ Python](#12-comunicación-tauri--python)
13. [Modelo de Datos (SQLite)](#13-modelo-de-datos-sqlite)
14. [Dependencias](#14-dependencias)
15. [Estructura de Archivos](#15-estructura-de-archivos)
16. [Flujo de Usuario Final](#16-flujo-de-usuario-final)
17. [Plan de Implementación por Fases](#17-plan-de-implementación-por-fases)
18. [Riesgos y Mitigaciones](#18-riesgos-y-mitigaciones)
19. [Consideraciones Legales y Éticas](#19-consideraciones-legales-y-éticas)
20. [Apéndice: Hallazgos de Investigación](#20-apéndice-hallazgos-de-investigación)

---

## 1. Objetivo y Visión

### Petición original del usuario

Automatizar el proceso diario de búsqueda de empleo de forma que el sistema, **cada día**:

1. Abra/consulte LinkedIn
2. Busque los empleos que mejor encajen con el perfil del usuario
3. Verifique que cumplen todos sus requisitos
4. Conecte con los recruiters / personal de RRHH de la empresa
5. Prepare mensajes directos personalizados para ese perfil
6. Aplique a la solicitud (vía LinkedIn o externamente)
7. Rellene los datos, suba los CVs, genere cartas de presentación
8. **Pida confirmación y/o modificaciones del usuario ANTES de ejecutar**

### Requisito de rendimiento (crítico)

> "Cada día hay que ver decenas de posibles empleos, probablemente centenares, preparar los 5-10 mejores cada día, preparar todos los conectar, los mensajes directos, los formularios... Y en caso de que el usuario apruebe, mandar todo."

El proceso debe ser **lo más fluido y rápido posible**. Playwright para cientos de ofertas es demasiado lento (3-8s por página). La solución es un **enfoque híbrido API-first** (ver [sección 4](#4-arquitectura-general)).

### Principio rector

**El usuario siempre tiene el control.** El sistema busca, analiza, puntúa y prepara todo automáticamente, pero **ninguna acción de escritura** (aplicar, conectar, enviar mensaje) se ejecuta sin confirmación explícita del usuario.

---

## 2. Decisiones del Usuario

Decisiones tomadas durante la fase de planificación (vinculantes para la implementación):

| Decisión | Opción elegida | Implicación |
|----------|---------------|-------------|
| **Nivel de riesgo de ban** | **Semi-automático** | El sistema prepara todo, pero las acciones críticas requieren confirmación manual una por una |
| **Modo de ejecución** | **Híbrido** | Python en background para búsqueda/análisis. Tauri muestra resultados y pide confirmación. Acciones críticas en navegador visible |
| **Aplicaciones externas** | **Universal (ambicioso)** | Intentar rellenar cualquier formulario externo con AI, no solo LinkedIn Easy Apply |
| **Motor LLM** | **Solo Ollama (local)** | Todo offline y gratuito. Sin dependencias de API cloud de pago |
| **Orden de implementación** | **Fases 1+2 primero** | Discovery + Matching + Dashboard de confirmación antes de ejecutar acciones |
| **Relación Tauri-Python** | **Proceso hijo + HTTP** | El backend Python arranca como proceso hijo de Tauri; comunicación vía HTTP local |
| **Ámbito del MVP** | **Solo LinkedIn** | Donde están la mayoría de ofertas tech y ya está resuelta la autenticación |

---

## 3. Estado Actual del Proyecto

### Arquitectura dual existente

JobPilot es una aplicación **Tauri 2** (Rust + React webview) con un backend Python FastAPI alternativo (Docker).

```
JobPilot/
├── src-tauri/          # Rust/Tauri (modo principal — desktop)
│   └── src/
│       ├── main.rs         # Entry point, registro de comandos (50 líneas)
│       ├── commands.rs     # TODOS los comandos Tauri (1010 líneas)
│       ├── state.rs        # AppState, Profile, JobOffer (66 líneas)
│       ├── llm.rs          # Ollama streaming/non-streaming (177 líneas)
│       ├── ollama.rs       # Ciclo de vida Ollama: detect, start, pull (122 líneas)
│       ├── scraper.rs      # Scraping de URLs de ofertas (182 líneas)
│       ├── linkedin.rs     # Extracción de cookies LinkedIn + perfil (269 líneas)
│       └── document.rs     # Extracción PDF/DOCX/TXT con fix Unicode (145 líneas)
│
├── frontend/           # React 18 + Vite 5 + TailwindCSS 3 + TypeScript 5
│   └── src/
│       ├── App.tsx         # Router + sidebar + setup flow (148 líneas)
│       ├── services/api.ts # Wrappers de invoke() de Tauri (174 líneas)
│       └── pages/
│           ├── Dashboard.tsx     # Health overview + quick start
│           ├── JobsPage.tsx      # CRUD de ofertas + CV upload + scraping
│           ├── GeneratePage.tsx  # Generación de contenido con streaming
│           └── ProfilePage.tsx   # Form de perfil + CV + import LinkedIn
│
├── backend/            # Python 3.12 FastAPI (modo Docker alternativo)
│   └── app/
│       ├── main.py             # FastAPI app, CORS, lifespan
│       ├── core/
│       │   ├── config.py       # Pydantic Settings
│       │   └── llm.py          # Cliente Ollama: generate/chat/stream
│       ├── api/routes.py       # Todas las rutas REST (405 líneas)
│       ├── services/
│       │   ├── cv_parser.py        # Parsing PDF/DOCX (pdfplumber + markitdown)
│       │   ├── job_manager.py      # CRUD de ofertas en filesystem
│       │   ├── profile_manager.py  # Lectura/escritura de profile.json
│       │   ├── scraper.py          # Scraper HTTP (LinkedIn/InfoJobs/Indeed)
│       │   └── scraper_advanced.py # Scraper Playwright OPCIONAL (104 líneas)
│       └── agents/
│           ├── cover_letter.py      # Agente de carta de presentación
│           ├── recruiter_message.py # Agente de mensaje a recruiter
│           ├── interview_qa.py      # Agente de Q&A de entrevista
│           └── job_analyzer.py      # Análisis AI de ofertas
│
└── data/               # Datos en runtime (contenido en .gitignore)
    ├── cvs/.gitkeep        # CVs del usuario + texto extraído (.txt)
    ├── jobs/.gitkeep       # Ofertas guardadas como JSON
    └── outputs/.gitkeep    # Contenido generado
```

### Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| **Shell desktop** | Tauri 2 (Rust) |
| **Frontend** | React 18.3, Vite 5.4, TailwindCSS 3.4, TypeScript 5.5, React Router 6, Lucide icons |
| **Plugins Tauri** | dialog, fs, shell |
| **Backend alternativo** | Python 3.12, FastAPI 0.115+, Pydantic 2.7, httpx, pdfplumber, BeautifulSoup4, sse-starlette |
| **LLM** | Ollama (local, 100% offline), modelo por defecto `llama3.2`, temperatura 0.7 |
| **Scraping** | `scraper` crate (Rust), httpx+BS4 (Python), Playwright opcional |
| **Almacenamiento** | Filesystem JSON (sin BD tradicional) |

### Funcionalidades ya implementadas

- **Gestión de perfil**: form manual, auto-fill desde CV con AI, import LinkedIn (URL con cookie `li_at` + paste de texto)
- **Gestión de CV/documentos**: upload PDF/DOCX/TXT/MD, extracción de texto, normalización Unicode (acentos)
- **Gestión de ofertas**: añadir por URL (scraping), añadir manual, análisis AI de ofertas
- **Generación de contenido (Ollama, streaming)**: cartas de presentación, mensajes a recruiters (3 subtipos), respuestas de entrevista (método STAR), predicción de preguntas de entrevista

### Autenticación LinkedIn existente (clave para el autopilot)

`src-tauri/src/linkedin.rs` ya implementa la extracción de cookies de LinkedIn:

1. **Descubrimiento de cookies**: prueba Edge primero, luego Chrome (Windows `%LOCALAPPDATA%`)
2. **Master key**: lee `Local State` JSON → obtiene `os_crypt.encrypted_key` (base64, prefijo DPAPI)
3. **Descifrado DPAPI**: Windows `CryptUnprotectData` API
4. **Cookie DB**: copia el SQLite de cookies a temp, consulta `li_at` donde `host_key LIKE '%linkedin.com'`
5. **Descifrado AES-256-GCM**: formato Chrome v10/v20 (prefijo 3 bytes + nonce 12 bytes + ciphertext)
6. **Fetch autenticado**: `reqwest` con header `Cookie: li_at=<value>`

> **Reutilización**: Esta lógica se extenderá para extraer también `JSESSIONID` (necesario para el CSRF token de la Voyager API) y pasar ambas cookies al servicio Python.

### Lo que NO existe (= lo que construye este plan)

- ❌ Búsqueda automatizada de empleos
- ❌ Matching/scoring de ofertas vs perfil
- ❌ Envío de solicitudes automatizado
- ❌ Conexión con recruiters automatizada
- ❌ Rellenado de formularios externos
- ❌ Scheduler/cron diario
- ❌ Flujo de confirmación del usuario
- ❌ Base de datos de estado/historial

---

## 4. Arquitectura General

### Decisión clave: enfoque híbrido de 3 capas

La investigación demostró que la **LinkedIn Voyager API** (API REST interna que usa el propio frontend de LinkedIn) es **5-10x más rápida** que la automatización con navegador (200-500ms/request vs 2-8s/página).

| Capa | Tecnología | Uso | Velocidad | % del flujo |
|------|-----------|-----|-----------|-------------|
| **Lectura** | httpx + LinkedIn Voyager API | Buscar ofertas, detalles, recruiters | 200-500ms/request | ~95% |
| **Análisis** | Ollama (paralelo) + pre-filtros | Scoring, matching, generación | ~40s para 200 ofertas | — |
| **Ejecución** | Playwright (visible) | Apply, conectar, mensajes | 3-8s/acción | ~5% |

**Resultado**: El 95% del flujo (todas las lecturas) usa API directa rápida. Solo las acciones de escritura confirmadas por el usuario usan Playwright visible.

### Diagrama de arquitectura completo

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          TAURI APP (Desktop)                              │
│                                                                          │
│  ┌──────────┐  ┌────────────────┐  ┌────────────┐  ┌──────────────┐   │
│  │ Settings │  │ Autopilot      │  │ Action     │  │ Execution    │   │
│  │ Page     │  │ Dashboard      │  │ Queue      │  │ Monitor      │   │
│  └────┬─────┘  └──────┬─────────┘  └─────┬──────┘  └──────┬───────┘   │
│       │               │                   │                 │           │
│  ─────┴───────────────┴───────────────────┴─────────────────┴─────────  │
│                    Tauri IPC Commands (invoke)                            │
│  ───────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  RUST BRIDGE (autopilot.rs + autopilot_bridge.rs)                 │   │
│  │  - spawn/kill proceso Python                                      │   │
│  │  - health check polling                                           │   │
│  │  - extraer li_at + JSESSIONID → enviar a Python                   │   │
│  │  - proxy HTTP: frontend ↔ Python service                         │   │
│  │  - Windows Job Object (cleanup on exit)                           │   │
│  └────────────────────────────────────┬─────────────────────────────┘   │
└───────────────────────────────────────┼─────────────────────────────────┘
                                        │ HTTP localhost:8765
┌───────────────────────────────────────▼─────────────────────────────────┐
│                      PYTHON AUTOMATION SERVICE                            │
│                      (FastAPI + asyncio + APScheduler)                    │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  API LAYER (FastAPI on :8765)                                       │ │
│  │  POST /autopilot/start       → trigger pipeline manual              │ │
│  │  GET  /autopilot/status      → progreso (SSE stream)                │ │
│  │  POST /autopilot/cancel      → cancelar pipeline                    │ │
│  │  GET  /autopilot/queue       → acciones pendientes de revisión      │ │
│  │  PATCH /autopilot/queue/{id} → aprobar/rechazar/editar              │ │
│  │  POST /autopilot/execute     → ejecutar acciones aprobadas          │ │
│  │  POST /autopilot/session     → recibir cookies de Tauri             │ │
│  │  GET  /autopilot/history     → acciones pasadas                     │ │
│  │  GET/PUT /autopilot/settings → configuración + criterios            │ │
│  │  GET  /health                → health check                         │ │
│  │  POST /shutdown              → apagado graceful                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────────┐ │
│  │  SCHEDULER        │  │  PIPELINE         │  │  EXECUTOR             │ │
│  │  (APScheduler 4)  │  │  (asyncio stages) │  │  (Playwright visible) │ │
│  │  Daily job        │──│  1: Fetch         │  │  Easy Apply           │ │
│  │  Manual trigger   │  │  2: Filter        │  │  Connection requests  │ │
│  │                   │  │  3: Score         │  │  Send messages        │ │
│  │                   │  │  4: Rank          │  │  External form fill   │ │
│  │                   │  │  5: Generate      │  │                       │ │
│  └──────────────────┘  └──────────────────┘  └───────────────────────┘ │
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────────┐ │
│  │  LINKEDIN CLIENT  │  │  LLM ENGINE       │  │  PERSISTENCE          │ │
│  │  (httpx async)    │  │  (Ollama client)  │  │  (SQLite + aiosqlite) │ │
│  │  Voyager API      │  │  Scoring (1B)     │  │  discovered_jobs      │ │
│  │  Job search       │  │  Generation (3B)  │  │  action_queue         │ │
│  │  Job details      │  │  Form analysis    │  │  companies            │ │
│  │  People search    │  │  PARALLEL=4       │  │  recruiters           │ │
│  │  Rate limiter     │  │  Batch prompts    │  │  pipeline_runs        │ │
│  │  Session manager  │  │                   │  │  execution_log        │ │
│  └──────────────────┘  └──────────────────┘  └───────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Estrategia Git (Gitflow)

### Migración inicial: `master` → `main` + `develop`

El repo actualmente tiene **solo** la rama `master` con 5 commits. Migración (ejecutar al iniciar implementación):

```bash
# 1. Renombrar master → main local
git branch -m master main

# 2. Push main al remoto
git push -u origin main

# 3. Crear develop desde main
git checkout -b develop main
git push -u origin develop

# 4. Cambiar rama por defecto en GitHub a develop
gh repo edit megatron54/JobPilot --default-branch develop

# 5. Borrar master en el remoto
git push origin --delete master

# 6. Verificar
git branch -a
# Esperado:
# * develop
#   main
#   remotes/origin/develop
#   remotes/origin/main
```

### Reglas de oro

- **`main`**: rama madre, SIEMPRE estable, releases taggeadas. **NUNCA se desarrolla directamente sobre main.**
- **`develop`**: rama de integración. Las features se mergean aquí.
- **`feature/*`**: ramas de característica, parten de `develop`, se mergean a `develop`.
- **`develop` → `main`**: solo cuando una fase está completa, testeada y estable (vía release branch).

### Convención de nombres de ramas

| Tipo | Patrón | Ejemplo |
|------|--------|---------|
| Feature | `feature/<descripción>` | `feature/autopilot-discovery` |
| Bug fix | `fix/<descripción>` | `fix/linkedin-cookie-expiry` |
| Hotfix | `hotfix/<descripción>` | `hotfix/critical-crash-fix` |
| Release | `release/v<semver>` | `release/v1.1.0` |
| Chore | `chore/<descripción>` | `chore/update-tauri-deps` |

**Reglas**: minúsculas, guiones (no underscores, no camelCase), 2-4 palabras descriptivas.

### Plan de ramas para el Autopilot

Estrategia: **una rama por fase**, con merges secuenciales (cada fase depende de la anterior estando en `develop`).

```
develop
  ├── feature/autopilot-engine        → Fase 1: Servicio Python + bridge Tauri + SQLite
  ├── feature/autopilot-discovery     → Fase 2: LinkedIn Voyager API + búsqueda
  ├── feature/autopilot-matcher       → Fase 3: Pre-filtros + Ollama scoring + pipeline
  ├── feature/autopilot-dashboard     → Fase 4: UI confirmación + cola + SSE
  ├── feature/autopilot-applicator    → Fase 5: Easy Apply + form filler + Greenhouse/Lever
  └── feature/autopilot-connector     → Fase 6: Conexiones + mensajes + tracking
```

**Por qué una rama por fase (no por step, no una gigante):**
- Steps dentro de una fase están acoplados (step 2 depende de step 1)
- Una fase es la unidad "releaseable" natural (funciona end-to-end o no)
- Evita ramas demasiado longevas que derivan de `develop`

### Convención de commits (Conventional Commits)

```
<type>(<scope>): <subject>

[body opcional]

[footer opcional]
```

**Tipos**: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`, `style`

**Scopes del proyecto**: `autopilot`, `scraper`, `matcher`, `applicator`, `connector`, `ui`, `db`, `auth`, `config`, `tauri`

**Ejemplos**:
```
feat(autopilot): add job discovery pipeline via Voyager API
fix(scraper): handle LinkedIn 429 rate limit with backoff
perf(matcher): batch Ollama scoring 5 jobs per prompt
```

**Breaking change**:
```
feat(api)!: change job scoring response format

BREAKING CHANGE: score field is now float 0-1 instead of int 0-100.
```

### Estrategia de merge

| Rama | Método de merge | Razón |
|------|----------------|-------|
| `feature/*` → `develop` | **Squash merge** | Un commit limpio por feature |
| `fix/*` → `develop` | **Squash merge** | Un fix lógico = un commit |
| `develop` → `main` | **Merge commit** (`--no-ff`) | Preserva el punto de integración |
| `release/*` → `main` | **Merge commit** (`--no-ff`) | Límite claro de release |
| `hotfix/*` → `main` | **Merge commit** (`--no-ff`) | Trazabilidad de fixes de producción |

### Workflow de release

```bash
git checkout develop && git pull origin develop
git checkout -b release/v1.1.0
# Bump versión en: src-tauri/Cargo.toml, src-tauri/tauri.conf.json, frontend/package.json
git commit -m "chore(release): bump version to v1.1.0"
git checkout main && git merge release/v1.1.0 --no-ff
git tag -a v1.1.0 -m "Release v1.1.0: Autopilot Discovery + Matching"
git checkout develop && git merge release/v1.1.0 --no-ff
git push origin main develop --tags
git branch -d release/v1.1.0
git push origin --delete release/v1.1.0
```

### Tagging (SemVer)

```
v1.0.0  - Release estable inicial (estado actual)
v1.1.0  - Fase 1+2 completas (Engine + Discovery)
v1.2.0  - Fase 3 completa (Matcher)
v1.3.0  - Fase 4 completa (Dashboard)
v1.4.0  - Fase 5 completa (Applicator)
v2.0.0  - Sistema autopilot completo (Fases 1-6)
```

### Protección de ramas (solo dev)

| Regla | `main` | `develop` |
|-------|--------|-----------|
| Require PR before merge | Sí | Opcional |
| Required approvers | 0 (solo dev) | 0 |
| Allow force push | No | No |
| Allow deletions | No | No |
| Require status checks (si hay CI) | Sí | Sí |

### Archivos GitHub a crear

- `.github/PULL_REQUEST_TEMPLATE.md` — plantilla de PR
- `.github/workflows/ci.yml` — CI: `cargo clippy`, `cargo test`, `tsc`, lint Python

---

## 6. Pipeline de Procesamiento

### Objetivo de rendimiento: 200 ofertas en ~90 segundos

```
 Tiempo   Etapa         Qué hace                          Tecnología
─────────────────────────────────────────────────────────────────────────
  0-12s   FETCH         8 requests × 25 resultados         httpx + Voyager API
                        = 200 ofertas (básicas)            Semaphore(5), delay 2s

 12-13s   PRE-FILTER    200 → ~60 candidatas              Python puro (sets, regex)
                        Elimina duplicados, ubicación,     SQLite dedup lookup
                        experiencia, skills mínimos

 13-38s   SCORE         60 ofertas → puntuadas            Ollama (llama3.2:1b)
                        Batch: 5 ofertas/prompt            OLLAMA_NUM_PARALLEL=4
                        12 batches / 4 paralelos           → ~25 segundos

 38-40s   RANK+SELECT   Top 10 (score >= 70)              Python sort + threshold
                        Extraer info recruiter             httpx (2-3 requests más)

 40-80s   GENERATE      Para top 10:                      Ollama (llama3.2:3b)
          (diferido)    - Cover letter (template+LLM)     Template hybrid (~150 tokens)
                        - Recruiter message                OLLAMA_NUM_PARALLEL=4
                        - Quick summary                    → ~40 segundos

  ~90s    READY         Cola lista para revisión           → Notificar frontend
─────────────────────────────────────────────────────────────────────────
                        TOTAL: ~90 segundos
```

### Arquitectura del pipeline (asyncio producer-consumer)

```
[Fetchers] → Queue1 → [Filter/Parser] → Queue2 → [Scorers] → Queue3 → [Generators]
  (N=15)    maxsize    (N=4)            maxsize   (N=4)                 (N=2)
            100                          60
```

**Primitivas asyncio**:
- `asyncio.Queue(maxsize=N)` — backpressure entre etapas
- `asyncio.Semaphore(N)` — rate-limit de requests HTTP concurrentes
- `asyncio.TaskGroup` (Python 3.11+) — concurrencia estructurada
- `asyncio.gather(*tasks, return_exceptions=True)` — un fallo no bloquea el pipeline

### Pre-filtros (sin LLM, ~140ms para 200 ofertas)

| Filtro | Lógica | Eliminación esperada |
|--------|--------|---------------------|
| Deduplicación | SQLite: `job_id` ya visto | 10-20% |
| Ubicación | `user.remote_pref` vs `job.workplaceType` | 15-25% |
| Experiencia | `job.required_years` > `user.years × 1.5` | 10-15% |
| Skills match | `len(user.skills & job.req_skills) / len(job.req_skills) < 0.3` | 20-30% |
| Idioma | Job en idioma que el usuario no habla | 5-10% |
| Blacklist | Empresa en lista de exclusión | 2-5% |
| **Total compuesto** | | **~65-70%** |

> Aplicados secuencialmente, los filtros componen: 200 → ~170 (dedup) → ~130 (ubicación) → ~110 (experiencia) → ~70 (skills) → ~65 (idioma) → ~60 candidatas.

### Progreso en tiempo real (SSE)

El pipeline emite eventos Server-Sent Events al frontend:

```
event: stage_update
data: {"stage": "fetch", "progress": 45, "total": 200, "message": "Buscando... 45/200"}

event: job_scored
data: {"job_id": "abc123", "score": 0.92, "title": "...", "company": "..."}

event: pipeline_complete
data: {"total_time": 42.3, "scored": 60, "top_jobs": 10}
```

**Cancelación**: flag comprobado entre operaciones. **Resume**: estado guardado en SQLite (`pipeline_runs`, `pipeline_items`).

---

## 7. LinkedIn Voyager API (Motor de Lectura)

> **Base URL**: `https://www.linkedin.com/voyager/api/`

### Autenticación

**Cookies requeridas**:

| Cookie | Propósito | Duración |
|--------|-----------|----------|
| `li_at` | Token de sesión principal | ~1 año |
| `JSESSIONID` | Session ID + fuente del CSRF token | Sesión |

**CSRF**: el header `csrf-token` = valor de la cookie `JSESSIONID` (ej: `ajax:1234567890123456789`), sin comillas. Debe enviarse en CADA request.

### Headers obligatorios

```python
HEADERS = {
    "csrf-token": "{JSESSIONID_value}",
    "x-restli-protocol-version": "2.0.0",
    "x-li-lang": "es_ES",
    "x-li-track": '{"clientVersion":"1.13.xxxx","mpVersion":"1.13.xxxx","osName":"web","timezoneOffset":1,"timezone":"Europe/Madrid","deviceFormFactor":"DESKTOP","mpName":"voyager-web","displayDensity":1,"displayWidth":1920,"displayHeight":1080}',
    "Accept": "application/vnd.linkedin.normalized+json+2.1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "x-li-page-instance": "urn:li:page:d_flagship3_search_srp_jobs;...",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
}
```

> **Nota crítica**: `x-li-track.clientVersion` debe coincidir con la versión del frontend de LinkedIn desplegada. Inspeccionar tráfico de red periódicamente para actualizarla.

### Endpoints clave

| Operación | Endpoint | Velocidad |
|-----------|----------|-----------|
| Buscar ofertas | `GET /voyager/api/search/hits?q=jserpFilters&keywords=...` | 200-400ms |
| Detalle de oferta | `GET /voyager/api/jobs/jobPostings/{id}?decorationId=...WebFullJobPosting-65` | 200-400ms |
| Buscar recruiters | `GET /voyager/api/search/blended?q=all&filters.resultType=PEOPLE&filters.currentCompany=...` | 300-500ms |
| Enviar conexión | `POST /voyager/api/growth/normInvitations` | 300-500ms |
| Enviar mensaje | `POST /voyager/api/messaging/conversations?action=create` | 300-500ms |

### Parámetros de búsqueda de ofertas

| Parámetro | Valores | Descripción |
|-----------|---------|-------------|
| `keywords` | string URL-encoded | Términos de búsqueda |
| `start` | 0, 25, 50... | Paginación (offset) |
| `count` | 10-25 | Resultados por página (máx ~25) |
| `location` / `geoId` | string o `urn:li:geo:103644278` | Filtro geográfico |
| `experience` | `["1".."6"]` | 1=Internship, 2=Entry, 3=Associate, 4=Mid-Senior, 5=Director, 6=Executive |
| `jobType` | `["F","C","P","T","I"]` | F=Full-time, C=Contract, P=Part-time, T=Temp, I=Internship |
| `workRemoteAllowed` | `true` | Solo remoto |
| `listed_at` | segundos (`86400`) | Publicadas en las últimas X (86400 = 24h) |
| `distance` | millas (`25`) | Radio desde la ubicación |

### Detección de método de aplicación

El campo `applyMethod` en el detalle de la oferta indica el tipo:

```json
// Aplicación externa
{"applyMethod": {"com.linkedin.voyager.jobs.OffsiteApply": {"companyApplyUrl": "https://..."}}}

// Easy Apply
{"applyMethod": {"com.linkedin.voyager.jobs.ComplexOnsiteApply": {"easyApplyUrl": "..."}}}
```

### Identificación de recruiters

1. **Campo `hiringTeamCard`** en el detalle de la oferta (más fiable)
2. **Fallback**: búsqueda de empleados de la empresa con títulos de recruitment:
   ```
   /voyager/api/search/blended?filters.resultType=PEOPLE&filters.currentCompany=["{id}"]&filters.title=Talent Acquisition
   ```

### Rate limits seguros

| Acción | Límite/día | Límite/hora |
|--------|-----------|-------------|
| Búsquedas (read) | 400 | 50 |
| Detalles de oferta (read) | 300 | 40 |
| Búsqueda de personas (read) | 100 | 15 |
| **Conexiones (write)** | **15-20** | **5** |
| **Mensajes (write)** | **30** | **10** |

> LinkedIn limita oficialmente las invitaciones a ~100/semana. El umbral de detección de la API ronda los ~900 requests/sesión/hora. Mensaje de conexión: máx 300 caracteres.

### Comparación de velocidad (clave de la decisión)

| Métrica | Playwright Browser | httpx Direct API | Mejora |
|---------|-------------------|------------------|--------|
| Latencia/request | 2-8s | 200-500ms | **5-10x** |
| Throughput | 12-30 jobs/min | 60-120 jobs/min | **4-5x** |
| Memoria | 200-500MB (Chromium) | 10-30MB | **15x** |
| Paralelismo | 1-3 tabs | 5-10 conexiones | **3x** |

### Anti-detección para acceso API

1. **Delays aleatorios**: 2-5s entre requests (no intervalos fijos)
2. **IP estable residencial**: NO rotar IPs (una sola IP es más seguro)
3. **Horario humano**: ejecutar 8am-11pm en la zona horaria de la cuenta
4. **No 24/7**: imitar ventanas de actividad humana
5. **Inicio conservador**: empezar lento, aumentar gradualmente
6. **Headers correctos**: `x-li-track.clientVersion` actualizado
7. **Degradación graceful**: en 429 → backoff exponencial; en CHALLENGE → parar completamente
8. **TLS fingerprinting** (opcional): si es necesario, `curl_cffi` o `tls-client` imitan el TLS de Chrome. El paquete `linkedin-api` usa `requests` plano y funciona, así que no es crítico al inicio.

### Cuándo SÍ usar Playwright (solo escritura)

- **Easy Apply**: formulario multi-paso dinámico, sin API pública fiable
- **CAPTCHAs**: resolución manual con el usuario
- **Refresh de sesión**: si `li_at` expira (mantener un Playwright "warm" como fallback)
- **Aplicaciones externas**: formularios web (Workday, etc.)

> **Decisión**: NO usar el paquete `linkedin-api` (síncrono, sin async). Usar **httpx directo** contra Voyager API — más control, async nativo, sin dependencia de terceros. El paquete sí sirve como referencia de implementación (MIT, v2.3.1, mantenido).

---

## 8. Motor de Matching y LLM

### Estrategia de 2 modelos Ollama

| Modelo | Tamaño | VRAM | Uso |
|--------|--------|------|-----|
| `llama3.2:1b` | Q4_0 | ~700MB | Scoring rápido, output JSON estructurado |
| `llama3.2:3b` | Q4_0 | ~2GB | Generación de contenido de calidad |

### Configuración de Ollama (crítica para rendimiento)

```env
OLLAMA_NUM_PARALLEL=4         # 4 requests simultáneos (default es 1!)
OLLAMA_FLASH_ATTENTION=1      # Menos VRAM por contexto
OLLAMA_KV_CACHE_TYPE=q8_0     # Cache KV comprimido (mitad de memoria)
OLLAMA_KEEP_ALIVE=15m         # Modelo cargado entre batches
OLLAMA_MAX_LOADED_MODELS=2    # 1B (scoring) + 3B (generación) a la vez
OLLAMA_CONTEXT_LENGTH=4096    # Contexto razonable para scoring
```

> **VRAM total estimada**: ~3.5GB (cabe en GPU de 6GB). Base 3B (~2GB) + 4 paralelos × 4096 contexto × q8_0 KV (~1.5GB).

### Latencias estimadas (llama3.2 en RTX 3060/4060)

| Tarea | Input tokens | Output tokens | Latencia |
|-------|-------------|---------------|----------|
| Scoring (respuesta corta) | ~300-500 | ~50 | 2-4s |
| Generación (cover letter) | ~500-800 | ~300-500 | 15-30s |
| Mensaje recruiter | ~400-600 | ~100-200 | 8-15s |

> Con `OLLAMA_NUM_PARALLEL=4`, 4 prompts de scoring completan en la misma ventana de 2-4s.

### Optimizaciones de scoring

1. **Batch de jobs**: "Puntúa estas 5 ofertas. Devuelve JSON: `[{job_id, score, reason}]`"
2. **Output estructurado**: parámetro `format=ScoreResult.model_json_schema()` (fuerza JSON, el modelo para al satisfacer el schema)
3. **Temperature 0**: determinista, potencialmente más rápido
4. **`num_predict=100`**: hard-cap de tokens de salida para scoring
5. **Compresión de prompt**: enviar solo campos clave (título, empresa, requisitos, ubicación, nivel), no la descripción HTML completa. Reduce de ~2000 a ~300-500 tokens

### Modelo de scoring (output)

```json
{
  "score": 87,                              // 0-100
  "match_reasons": ["React 5+ años coincide", "Remoto OK", "Idioma EN/ES"],
  "deal_breakers": [],                      // requisitos que el usuario NO cumple
  "missing_skills": ["GraphQL (deseable)"], // skills que faltan pero no bloquean
  "recommendation": "strong_match"          // strong_match/good/partial/skip
}
```

**Clasificación por score**:
- `80-100`: "Encaja perfectamente" (strong_match)
- `60-79`: "Buen candidato" (good)
- `40-59`: "Parcial" (partial)
- `<40`: "No encaja" (skip — no se muestra)

### Generación de contenido (estrategia híbrida template + LLM)

En lugar de generar todo desde cero:

1. **Esqueleto pre-construido** (sin LLM): apertura/saludo parametrizado, cierre/CTA parametrizado, párrafo de cualificaciones estándar del usuario (estático)
2. **El LLM genera solo las partes variables** (~30-40% del contenido): por qué esta empresa/rol específico, cómo la experiencia del usuario mapea a sus requisitos, un insight personalizado sobre su producto/misión
3. **Ensamblaje**: template + secciones generadas por LLM

> **Resultado**: output del LLM baja de ~400 a ~150 tokens/job. Latencia ~8-12s/job (vs 30-60s). 10 jobs en paralelo: ~30-40s total.

### Generación diferida (recomendado)

La optimización más inteligente: **no generar contenido hasta que el usuario lo pida**:

1. El pipeline puntúa solo → muestra lista rankeada al usuario
2. El usuario revisa el top 10, selecciona 3-5 que realmente quiere
3. Solo entonces se genera contenido para los seleccionados
4. Generación para 3-5 jobs: ~45-90s

Reutilizar los agentes existentes: `cover_letter.py`, `recruiter_message.py`.

---

## 9. Sistema de Cola y Confirmación

### Máquina de estados de una acción

```
DISCOVERED → PRE_FILTERED → SCORED → CONTENT_READY → PENDING_REVIEW
                                                          │
                                          ┌───────────────┼───────────────┐
                                          ▼               ▼               ▼
                                       APPROVED        EDITED          REJECTED
                                          │               │
                                          ▼               ▼
                                       EXECUTING      EXECUTING
                                          │               │
                                    ┌─────┴─────┐   ┌─────┴─────┐
                                    ▼           ▼   ▼           ▼
                                 COMPLETED   FAILED COMPLETED  FAILED
```

### Tipos de acción

| Tipo | Descripción | Ejecución |
|------|-------------|-----------|
| `apply_easy` | LinkedIn Easy Apply | Playwright visible |
| `apply_external` | Formulario externo (Workday, Greenhouse...) | API o Playwright |
| `connect` | Solicitud de conexión a recruiter | Voyager API |
| `message` | Mensaje directo (DM/InMail) | Voyager API |

### Operaciones del usuario

Por cada acción en la cola, el usuario puede:
- **Aprobar**: ejecutar tal cual
- **Editar**: modificar el mensaje/carta antes de ejecutar
- **Rechazar**: descartar la acción
- **Posponer**: dejarla pendiente para más tarde

Operaciones batch: "Aprobar todas", "Rechazar todas", "Revisar una a una".

### Prevención de doble ejecución

- Optimistic locking: `UPDATE ... WHERE id = ? AND status = 'approved'` y comprobar `rowcount`
- Comprobación de estado antes de ejecutar
- Orden de ejecución: por prioridad (score) o FIFO

---

## 10. Ejecución de Acciones (Playwright)

### Browser visible para acciones de escritura

Cuando el usuario aprueba acciones, se abre Playwright **visible** (`headless=False`) para que vea lo que ocurre en tiempo real.

### LinkedIn Easy Apply

```
1. Abrir oferta → click "Easy Apply"
2. Rellenar campos (multi-paso): nombre, email, teléfono, CV upload
3. Preguntas adicionales:
   - Texto libre → respuesta generada por Ollama (contexto: job + CV)
   - Opción múltiple → Ollama elige la mejor opción
4. PAUSA antes del "Submit" final → confirmación visual del usuario
5. Submit → registrar resultado
```

### Conexiones (Voyager API, no browser)

```
1. Identificar perfil del recruiter (del hiringTeamCard o búsqueda)
2. Generar nota personalizada con Ollama (máx 300 chars): menciona la posición, algo de ambos perfiles
3. Usuario confirma la nota (editable)
4. POST /voyager/api/growth/normInvitations
5. Límite: máx 15-20/día
```

### Mensajes directos (Voyager API)

```
1. Si ya conectado (1er grado): mensaje directo
2. Mensaje generado por Ollama (agente recruiter_message.py existente)
3. Usuario edita si quiere
4. POST /voyager/api/messaging/conversations?action=create
5. Tracking: enviado, (futuro) respuesta recibida
```

### Anti-detección Playwright

- `playwright-stealth`: parchea WebDriver flag, propiedades de navigator
- Viewport real (1920×1080), user-agent consistente, locale `es-ES`, timezone correcta
- Delays humanos: typing con delays, scrolls, movimientos de ratón
- Reutilizar contexto/sesión en vez de crear nuevos

---

## 11. Aplicaciones Externas (Form Filler Universal)

### Estrategia por capas (orden de prioridad)

| Prioridad | ATS | Método | Cobertura |
|-----------|-----|--------|-----------|
| 1 | LinkedIn Easy Apply | Playwright visible | ~35% ofertas tech |
| 2 | **Greenhouse** | **API pública** (`POST boards.greenhouse.io/.../applications`) | ~20% |
| 3 | **Lever** | **API pública** / Playwright simple (single-page) | ~15% |
| 4 | **SmartRecruiters** | **API pública** | ~10% |
| 5 | Workday | Playwright + accessibility snapshot + LLM | ~15% |
| 6 | Genérico | Playwright + LLM form detection | ~5% |

> **Insight clave de la investigación**: Greenhouse, Lever y SmartRecruiters tienen **APIs públicas** para enviar aplicaciones sin navegador — más rápido, fiable y evita detección de bots. Workday (40% de grandes empresas) NO tiene API y requiere browser automation lenta.

### Detección del ATS (por URL)

```python
ATS_PATTERNS = {
    "greenhouse":     ["boards.greenhouse.io", "job-boards.greenhouse.io"],
    "lever":          ["jobs.lever.co"],
    "workday":        ["myworkdayjobs.com", "wd5.myworkday.com", "myworkday.com"],
    "smartrecruiters":["jobs.smartrecruiters.com"],
    "bamboohr":       ["bamboohr.com/careers"],
}
```

### Form detection con LLM (para ATSs desconocidos)

1. **Playwright accessibility snapshot**: `page.accessibility.snapshot()` — atraviesa shadow DOM, da significado semántico a los campos (role, name, value, required), funciona independientemente del framework
2. **Ollama clasifica cada campo**:
   ```
   "Dado este formulario, clasifica cada campo en: first_name, last_name,
   email, phone, linkedin_url, resume_upload, cover_letter, current_title,
   experience_years, salary_expectation, work_authorization, custom_question, unknown"
   ```
3. **Auto-fill** desde el perfil para campos conocidos
4. **Ollama genera** respuestas para `custom_question`
5. **PAUSA** antes de submit → confirmación visual del usuario

### Mapeo de campos perfil → formulario

| Campo del formulario | Origen (perfil) |
|---------------------|-----------------|
| First name / Last name | split `profile.name` |
| Email | `profile.email` |
| Phone | `profile.phone` |
| LinkedIn | `profile.linkedin_url` |
| Location / City | `profile.location` |
| Current title | `profile.title` |
| Years of experience | `profile.years_experience` |
| Resume / CV | upload desde `data/cvs/` |
| Cover letter | generar con Ollama (o pre-generado) |
| Salary expectations | configurable en preferencias |
| Work authorization | configurable (sí/no, tipo de visa) |
| Start date | configurable |

### File upload

```python
# Detectar input[type=file]
await page.set_input_files("input[type='file']", cv_path)
# Drag-and-drop: simular con eventos
# "Paste resume" textarea: pegar texto del CV en vez de subir
```

### Recuperación de errores y handoff al usuario

El sistema **pausa y pide ayuda** cuando detecta:
- CAPTCHA (hCaptcha, reCAPTCHA) — no se puede automatizar
- "Account creation required"
- Popups/modales inesperados
- Tipo de campo desconocido
- Confianza baja en el mapeo
- Pregunta que el AI no puede responder con confianza

> Señal al frontend: `manual_intervention_needed` con el motivo. El usuario interviene en el browser visible.

---

## 12. Comunicación Tauri ↔ Python

### Decisión: Proceso hijo + HTTP localhost

Patrón idéntico al que JobPilot ya usa con Ollama (`ollama.rs`), pero **manteniendo el handle del Child** para cleanup.

### Spawn del proceso Python (Rust)

```rust
// Estrategias de búsqueda de Python (en orden):
// 1. Bundled PyInstaller exe (producción)
// 2. .venv local (.venv/Scripts/python.exe)
// 3. VIRTUAL_ENV env var
// 4. which::which("python") / "python3"
// 5. Localizaciones comunes Windows

Command::new(python)
    .args(&["-m", "uvicorn", "app.automation.main:app",
            "--host", "127.0.0.1", "--port", &port.to_string()])
    .env("PYTHONUNBUFFERED", "1")  // CRÍTICO: flush inmediato de stdout
    .current_dir(backend_dir)
    .stdout(Stdio::piped())
    .stderr(Stdio::piped())
    .spawn()
```

### Distribución de Python

| Entorno | Estrategia |
|---------|-----------|
| **Desarrollo** | System Python con venv (fricción cero para desarrollar) |
| **Producción** | PyInstaller exe como Tauri sidecar (Tauri lo recomienda oficialmente) |

> **Playwright browsers**: demasiado grandes para empaquetar (~130-200MB). Estrategia: descargar en primer arranque a `%LOCALAPPDATA%\JobPilot\browsers` (vía `PLAYWRIGHT_BROWSERS_PATH`), O usar Chrome/Edge del sistema.

### Cleanup de procesos huérfanos (Windows Job Objects)

**Problema**: si el usuario cierra Tauri o Task Manager mata la app, el Python queda huérfano ocupando el puerto.

**Solución**: `win32job` crate con `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` — todos los procesos del job mueren cuando el padre sale (incluso por crash).

```rust
use win32job::{Job, ExtendedLimitInfo};
let mut info = ExtendedLimitInfo::new();
info.limit_kill_on_job_close();
let job = Job::create_with_limit_info(&mut info)?;
job.assign_current_process()?;
```

### Shutdown graceful

Windows no tiene SIGTERM. Secuencia:
1. `POST /shutdown` al FastAPI (esperar 2s)
2. Si no sale en 5s → `child.kill()` + `child.wait()` (reap zombie)

Hook en `RunEvent::Exit` de Tauri para ejecutar el shutdown al cerrar.

### Secuencia de arranque

```
App launch
  ├─ Tauri window abre → frontend muestra "Iniciando servicio..."
  ├─ Comando setup() en Rust:
  │   ├─ Encontrar/verificar Python
  │   ├─ Comprobar puerto disponible (auto-detect si 8765 ocupado)
  │   ├─ Spawn Python process
  │   ├─ Poll /health cada 500ms (timeout 15s)
  │   └─ Extraer cookies li_at + JSESSIONID → POST /autopilot/session
  └─ Frontend recibe resultado → UI principal o pantalla de error
```

### Paso de cookies (clave)

Rust extrae `li_at` + `JSESSIONID` (extendiendo `linkedin.rs`) y las envía al servicio Python vía `POST /autopilot/session`. El servicio las inyecta en el cliente httpx para la Voyager API.

### Health check con timeout

```rust
// Poll /health cada 500ms hasta 15s
// Detectar 401 → cookie expirada → notificar usuario para re-login en Chrome
```

---

## 13. Modelo de Datos (SQLite)

> **Ubicación**: `data/autopilot.db`. **Acceso**: `aiosqlite` con WAL mode (`PRAGMA journal_mode=WAL`, `busy_timeout=5000`). **Migraciones**: tabla de versión + scripts de upgrade (o Alembic si se usa SQLAlchemy).

```sql
-- Ofertas descubiertas (deduplicación + historial)
CREATE TABLE discovered_jobs (
    job_id          TEXT PRIMARY KEY,        -- LinkedIn job ID único
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    company_id      TEXT,
    location        TEXT,
    workplace_type  TEXT,                    -- remote/hybrid/onsite
    apply_method    TEXT,                    -- easy_apply/external
    external_url    TEXT,
    description     TEXT,
    requirements    TEXT,                    -- JSON array
    score           REAL,
    score_reasons   TEXT,                    -- JSON
    deal_breakers   TEXT,                    -- JSON array
    missing_skills  TEXT,                    -- JSON array
    recommendation  TEXT,                    -- strong_match/good/partial/skip
    recruiter_name  TEXT,
    recruiter_url   TEXT,
    discovered_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status          TEXT DEFAULT 'discovered'
);
CREATE INDEX idx_discovered_status ON discovered_jobs(status);
CREATE INDEX idx_discovered_score ON discovered_jobs(score DESC);

-- Cola de acciones (pending/approved/executed)
CREATE TABLE action_queue (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id              TEXT REFERENCES discovered_jobs(job_id),
    action_type         TEXT NOT NULL,       -- apply_easy/apply_external/connect/message
    status              TEXT DEFAULT 'pending_review',
    priority            INTEGER DEFAULT 0,
    content_draft       TEXT,                -- mensaje/carta generada
    content_final       TEXT,                -- versión final (tras editar)
    target_profile_url  TEXT,                -- para conexiones/mensajes
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at         TIMESTAMP,
    result              TEXT,                -- success/failure + detalles
    error_message       TEXT
);
CREATE INDEX idx_queue_status ON action_queue(status);

-- Cache de empresas (TTL 30 días)
CREATE TABLE companies (
    company_id      TEXT PRIMARY KEY,
    name            TEXT,
    industry        TEXT,
    size            TEXT,
    tech_stack      TEXT,                    -- JSON array
    last_updated    TIMESTAMP
);

-- Cache de recruiters (persiste entre sesiones)
CREATE TABLE recruiters (
    recruiter_id    TEXT PRIMARY KEY,
    name            TEXT,
    company         TEXT,
    linkedin_url    TEXT,
    title           TEXT,
    last_contact    TIMESTAMP
);

-- Conexiones enviadas (tracking de límites)
CREATE TABLE connections_sent (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recruiter_id    TEXT,
    job_id          TEXT,
    note            TEXT,
    sent_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status          TEXT                     -- sent/accepted/ignored
);

-- Historial de ejecuciones del pipeline
CREATE TABLE pipeline_runs (
    run_id          TEXT PRIMARY KEY,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    status          TEXT,                    -- running/completed/failed/cancelled
    jobs_fetched    INTEGER,
    jobs_filtered   INTEGER,
    jobs_scored     INTEGER,
    jobs_queued     INTEGER,
    config          TEXT                     -- JSON: criterios usados
);

-- Items del pipeline (para resume)
CREATE TABLE pipeline_items (
    run_id          TEXT,
    job_id          TEXT,
    stage_completed TEXT,                    -- fetched/filtered/scored/generated
    score           REAL,
    PRIMARY KEY (run_id, job_id)
);

-- Cache de respuestas LLM (content-hash, TTL 7-14 días)
CREATE TABLE llm_cache (
    cache_key       TEXT PRIMARY KEY,        -- sha256(model + prompt)
    response        TEXT,
    model           TEXT,
    created_at      TIMESTAMP
);

-- Log de ejecución (auditoría)
CREATE TABLE execution_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id       INTEGER REFERENCES action_queue(id),
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event           TEXT,
    details         TEXT
);
```

### Configuración del usuario

```
data/search_criteria.json   — criterios de búsqueda (keywords, ubicación, filtros)
data/autopilot_config.json  — config (hora schedule, límites diarios, on/off)
```

---

## 14. Dependencias

### Python (nuevas para Autopilot)

```toml
[project]
dependencies = [
    # Existentes
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",
    "pdfplumber>=0.11",
    "beautifulsoup4>=4.12",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "sse-starlette>=2.1",
    "markitdown[all]>=0.1",

    # NUEVAS para Autopilot
    "aiosqlite>=0.20",               # SQLite async
    "apscheduler>=4.0.0a6",          # Scheduler (4.x alpha pero async-native)
    "sqlalchemy[asyncio]>=2.0.30",   # ORM/Core + data store de APScheduler
    "playwright>=1.44",              # Browser automation (solo ejecución)
    "playwright-stealth>=1.0",       # Anti-detección
    # opcional si se necesita TLS spoofing:
    # "curl-cffi>=0.7",              # Imitar TLS fingerprint de Chrome
]
```

> **Nota APScheduler**: la 4.x sigue en alpha (`4.0.0a6`) tras 4 años, pero su API async-native con `SQLAlchemyDataStore` es la correcta. Alternativa estable: `3.11.3` con `AsyncIOScheduler` (API menos limpia). **Decisión**: empezar con 4.0.0a6; si hay problemas de estabilidad, fallback a 3.11.3.

> **NO usar** `linkedin-api` (síncrono). Usar httpx directo contra Voyager API.

### Frontend

Sin dependencias nuevas. React + Tailwind + SSE (EventSource nativo) cubren todo.

### Rust/Tauri (nuevas)

```toml
which = "7"          # Encontrar Python en PATH
win32job = "2"       # Windows Job Objects (cleanup de huérfanos)
shared_child = "1"   # Gestión thread-safe del child process
# reqwest, tokio, serde, serde_json ya existen
```

---

## 15. Estructura de Archivos

### Nuevos archivos a crear

```
backend/app/
├── automation/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app del servicio autopilot (:8765)
│   ├── config.py                  # Settings (puerto, límites, schedule)
│   ├── scheduler.py               # APScheduler setup + jobs diarios
│   ├── database.py                # SQLite engine + session factory
│   ├── models.py                  # Modelos (tablas de sección 13)
│   │
│   ├── linkedin/
│   │   ├── __init__.py
│   │   ├── client.py             # httpx AsyncClient con headers LinkedIn
│   │   ├── session.py            # Cookie mgmt, CSRF token, refresh
│   │   ├── search.py             # Job search via Voyager API
│   │   ├── details.py            # Job detail fetching
│   │   ├── people.py             # Recruiter/people search
│   │   ├── connect.py            # Connection requests (API)
│   │   ├── message.py            # Direct messages (API)
│   │   └── rate_limiter.py       # Token bucket rate limiter
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── orchestrator.py       # Coordinación principal del pipeline
│   │   ├── fetcher.py            # Stage 1: fetch desde LinkedIn
│   │   ├── filter.py            # Stage 2: pre-filtros (sin LLM)
│   │   ├── scorer.py             # Stage 3: scoring con LLM
│   │   ├── ranker.py             # Stage 4: rank + select top N
│   │   ├── generator.py          # Stage 5: generación de contenido
│   │   └── progress.py           # Emisor de progreso SSE
│   │
│   ├── executor/
│   │   ├── __init__.py
│   │   ├── browser.py            # Playwright context manager (visible)
│   │   ├── easy_apply.py         # LinkedIn Easy Apply flow
│   │   ├── connector.py          # Enviar conexiones
│   │   ├── messenger.py          # Enviar DMs
│   │   └── form_filler/
│   │       ├── __init__.py
│   │       ├── detector.py       # AI form field detection
│   │       ├── filler.py         # Universal form filler
│   │       ├── greenhouse.py     # Greenhouse API adapter
│   │       ├── lever.py          # Lever adapter
│   │       ├── workday.py        # Workday browser adapter
│   │       └── generic.py        # Generic LLM-based filler
│   │
│   └── queue/
│       ├── __init__.py
│       └── manager.py            # CRUD de la cola de acciones

src-tauri/src/
├── autopilot.rs                   # Spawn/manage del servicio Python
└── autopilot_bridge.rs            # Proxy de comandos al Python HTTP

frontend/src/
├── pages/
│   ├── AutopilotPage.tsx          # Dashboard principal
│   ├── AutopilotQueuePage.tsx     # Cola de revisión
│   └── AutopilotSettingsPage.tsx  # Criterios + configuración
└── components/autopilot/
    ├── PipelineProgress.tsx       # Barra de progreso con SSE
    ├── JobMatchCard.tsx           # Tarjeta de oferta rankeada
    ├── ActionReviewCard.tsx       # Acción pendiente (editable)
    ├── ExecutionMonitor.tsx       # Monitor de ejecución en vivo
    └── SearchCriteriaForm.tsx     # Formulario de criterios

data/
├── autopilot.db                   # SQLite (ofertas, cola, historial)
├── search_criteria.json           # Criterios del usuario
└── autopilot_config.json          # Configuración del autopilot

.github/
├── PULL_REQUEST_TEMPLATE.md
└── workflows/ci.yml
```

---

## 16. Flujo de Usuario Final

### Configuración inicial (una vez)

1. Usuario abre **Settings → Autopilot**
2. Configura criterios: keywords, ubicación, remoto/híbrido, experiencia, exclusiones
3. Configura schedule: hora diaria, límites (máx conexiones/día, máx applies/día)
4. El sistema ya tiene su cookie `li_at` (extraída automáticamente de Chrome/Edge)

### Uso diario

```
09:00  → Schedule dispara pipeline (o usuario pulsa "Buscar ahora")
09:01  → Pipeline: fetch 200 ofertas via API (12s)
09:01  → Pipeline: pre-filter → 60 candidatas (instantáneo)
09:02  → Pipeline: score 60 con Ollama (25s)
09:02  → Pipeline: generar contenido top 10 (40s)
09:03  → Notificación: "10 ofertas listas para revisar"

Usuario abre la app cuando quiera:
  → Dashboard: "10 nuevas recomendaciones hoy"
  → Revisa cada una:
     - Score 92% "Senior React Dev @ Google" → APROBAR (edita el mensaje)
     - Score 87% "Frontend Lead @ Stripe"    → APROBAR
     - Score 71% "Full Stack @ Startup"       → RECHAZAR (no le interesa)

  → Click "Ejecutar 2 acciones aprobadas"
  → Se abre Playwright VISIBLE:
     - Easy Apply a Google (rellena formulario, PAUSA antes de submit)
     - Usuario ve todo, confirma → Submit ✓
     - Conexión con recruiter de Stripe via API (instantáneo) ✓
     - Mensaje DM generado → enviado ✓

  → Dashboard: "2/2 completadas ✓"
```

---

## 17. Plan de Implementación por Fases

| Fase | Feature Branch | Trabajo | Estimación |
|------|---------------|---------|------------|
| **1** | `feature/autopilot-engine` | Servicio Python + bridge Tauri + health + SQLite + paso de cookies | 3-4 días |
| **2** | `feature/autopilot-discovery` | LinkedIn client httpx + Voyager API + rate limiter + session mgmt | 3-4 días |
| **3** | `feature/autopilot-matcher` | Pre-filtros + Ollama scoring + pipeline async + SSE progress | 4-5 días |
| **4** | `feature/autopilot-dashboard` | Frontend: dashboard + cola + settings + criterios + SSE | 4-5 días |
| **5** | `feature/autopilot-applicator` | Easy Apply + form filler + Greenhouse/Lever API + Workday | 5-7 días |
| **6** | `feature/autopilot-connector` | Conexiones + mensajes + tracking + límites | 2-3 días |
| | | **TOTAL** | **~3-4 semanas** |

### MVP (Fases 1+2+3+4)

El MVP entrega: **el usuario configura criterios → el sistema busca y puntúa cientos de ofertas cada día → muestra las mejores con contenido pre-generado → el usuario revisa y aprueba**. Sin ejecución automática todavía (eso es Fase 5+6).

### Detalle Fase 1 — `feature/autopilot-engine`

- [ ] Migración Git: `master` → `main` + `develop`
- [ ] Crear estructura `backend/app/automation/`
- [ ] FastAPI app en `:8765` con `/health` y `/shutdown`
- [ ] SQLite + aiosqlite + schema (sección 13) + WAL mode
- [ ] `autopilot.rs`: spawn Python como child process
- [ ] Health check polling + Windows Job Object
- [ ] Extender `linkedin.rs`: extraer `JSESSIONID` además de `li_at`
- [ ] `POST /autopilot/session`: recibir e inyectar cookies
- [ ] Comandos Tauri: `start_autopilot`, `stop_autopilot`, `autopilot_status`
- [ ] Verificación: app arranca → Python arranca → health OK → cookies pasadas

### Detalle Fase 2 — `feature/autopilot-discovery`

- [ ] `linkedin/client.py`: httpx AsyncClient con headers Voyager
- [ ] `linkedin/session.py`: CSRF token de JSESSIONID, refresh, detección 401
- [ ] `linkedin/search.py`: construir URL de búsqueda + parsear resultados
- [ ] `linkedin/details.py`: fetch de detalle de oferta
- [ ] `linkedin/people.py`: búsqueda de recruiters (hiringTeamCard + fallback)
- [ ] `linkedin/rate_limiter.py`: token bucket + delays aleatorios + backoff
- [ ] Persistir ofertas en `discovered_jobs` (deduplicación)
- [ ] Verificación: buscar "React Developer Madrid" → obtener N ofertas reales con detalles

---

## 18. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|-----------|
| LinkedIn detecta uso de API | Media | Alto | Headers correctos, delays 2-5s, <50 req/hora, cuenta dedicada, horario humano |
| Ollama demasiado lento | Baja | Medio | 2 modelos (1B scoring + 3B gen), `PARALLEL=4`, batch prompts, generación diferida |
| Cookie `li_at` expira | Baja | Bajo | Auto-detectar 401, notificar usuario para re-login en Chrome, Playwright warm fallback |
| Formularios irreconocibles | Media | Bajo | Pausa + handoff al usuario, mejora incremental con el tiempo |
| Cambios en Voyager API | Media | Medio | Abstracción por capa, tests de contrato, fallback a scraping HTML |
| Puerto 8765 ocupado | Baja | Bajo | Auto-detect de puerto disponible |
| Proceso Python huérfano | Media | Bajo | Windows Job Objects (kill on parent close) |
| CAPTCHA en ejecución | Media | Medio | Detección + handoff manual al usuario en browser visible |
| Ban de cuenta LinkedIn | Baja-Media | Alto | Semi-automático (confirmación), límites estrictos, cuenta dedicada recomendada |
| APScheduler 4.x inestable (alpha) | Media | Bajo | Fallback a 3.11.3 estable si hay problemas |

---

## 19. Consideraciones Legales y Éticas

> **Importante**: El uso de la Voyager API con headers de navegador falsos **viola los Términos de Servicio de LinkedIn**. El caso *HiQ vs LinkedIn* estableció que scrapear perfiles *públicos* es legal, pero el acceso autenticado a la API interna está en zona gris.

### Recomendaciones

- **Cuenta dedicada**: considerar usar una cuenta de LinkedIn no-personal para reducir el riesgo sobre la cuenta principal del usuario
- **Límites conservadores**: respetar estrictamente los rate limits (sección 7)
- **Semi-automático por diseño**: el usuario confirma cada acción de escritura — no es un bot 100% autónomo
- **Transparencia**: el usuario es consciente y da consentimiento explícito a cada acción
- **No spam**: mensajes personalizados de calidad, no spam masivo
- **Respeto de horarios**: actividad solo en horario humano

---

## 20. Apéndice: Hallazgos de Investigación

### A. Comparativa de acceso a LinkedIn

| Método | Velocidad | Riesgo detección | Mantenimiento | Veredicto |
|--------|-----------|------------------|---------------|-----------|
| Playwright (browser) | Lento (2-8s) | Medio | Alto (selectores) | Solo escritura |
| **Voyager API (httpx)** | **Rápido (200-500ms)** | **Bajo-Medio** | **Medio (headers)** | **Lectura (95%)** |
| `linkedin-api` package | Rápido | Bajo-Medio | Bajo | Referencia, no usar (síncrono) |
| Guest scraping (no auth) | Medio | Bajo | Medio | Fallback limitado (~1000 results) |

### B. Throughput estimado

| Estrategia | Jobs/hora |
|-----------|-----------|
| Playwright secuencial | 450-900 |
| httpx secuencial (delay 2s) | 1,800 |
| httpx 3-5 concurrente (delay) | 3,600 |

> Para "cientos al día": httpx secuencial con delays conservadores (3s) ya logra 1,200 jobs/hora — más que suficiente con riesgo mínimo.

### C. Timing del pipeline (200 jobs)

| Approach | Tiempo total |
|----------|-------------|
| Fully sequential | ~11.5 min |
| Parallel (`OLLAMA_NUM_PARALLEL=4`) | ~2.5 min |
| **Optimized hybrid (diferido)** | **~40s a primeros resultados, ~1.5 min con generación** |
| Two-model strategy | ~1.2 min |

### D. APScheduler 4.x vs 3.x

| Aspecto | 3.11.3 (estable) | 4.0.0a6 (alpha) |
|---------|-----------------|-----------------|
| Estado | Producción | Alpha (4 años) |
| Async | `AsyncIOScheduler` | Async-native |
| Data store | `SQLAlchemyJobStore` | `SQLAlchemyDataStore` |
| Timezone | pytz | stdlib `zoneinfo` |
| Recomendación | Fallback seguro | Empezar aquí |

### E. Cobertura de ATSs

| ATS | % mercado | API pública | Dificultad |
|-----|-----------|-------------|------------|
| LinkedIn Easy Apply | ~35% | No (browser) | Media |
| Greenhouse | ~20% | **Sí** | Baja |
| Lever | ~15% | **Sí** | Baja |
| SmartRecruiters | ~10% | **Sí** | Baja |
| Workday | ~15% | No (browser) | **Alta** |
| Genérico | ~5% | No (LLM) | Media-Alta |

### F. Referencias técnicas clave

- **LinkedIn Voyager API**: endpoints en sección 7. Base: `/voyager/api/`
- **Paquete de referencia**: `linkedin-api` v2.3.1 (Tom Quirk, MIT) — github.com/tomquirk/linkedin-api
- **Tauri sidecar**: `tauri-plugin-shell` con `externalBin` en `tauri.conf.json`
- **Windows Job Objects**: crate `win32job` con `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`
- **Ollama parallel**: `OLLAMA_NUM_PARALLEL`, `OLLAMA_MAX_LOADED_MODELS`, `OLLAMA_FLASH_ATTENTION`
- **Playwright accessibility snapshot**: `page.accessibility.snapshot()` para form detection universal

---

## Notas de Sesión

> Sección para registrar progreso entre sesiones. Añadir entradas al retomar el trabajo.

### 2026-06-29 — Planificación inicial
- Investigación profunda completada (LinkedIn API, Playwright, Tauri-Python, APScheduler, parallel processing, form filling, Gitflow)
- Decisiones del usuario registradas (sección 2)
- Plan maestro consolidado en este documento
- **Próximo paso**: iniciar Fase 1 (`feature/autopilot-engine`) — migración Git + servicio Python base

### 2026-06-29 — Fase 1 (en progreso): `feature/autopilot-engine`
- **Git**: migración `master`→`main`+`develop` completada. `develop` es default en GitHub. `master` eliminado. Rama `feature/autopilot-engine` creada.
- **Servicio Python** (`backend/app/automation/`): creado y funcional.
  - `config.py` — settings con prefijo `AUTOPILOT_`
  - `database.py` + `schema.sql` — SQLite + aiosqlite, WAL mode, 9 tablas, versionado de schema
  - `models.py` — modelos Pydantic (sesión, criterios, config, cola, pipeline)
  - `session.py` — estado de cookies LinkedIn (li_at + JSESSIONID→csrf)
  - `queue_manager.py` — CRUD de la cola de acciones
  - `store.py` — persistencia JSON de criterios/config
  - `main.py` — FastAPI app en :8765 (health, shutdown, session, settings, queue, status)
- **Tests**: 21 tests pasando (database, queue, session, API). pytest-asyncio.
- **Bridge Rust/Tauri**:
  - `linkedin.rs` extendido — `get_linkedin_cookies()` extrae li_at + JSESSIONID
  - `autopilot.rs` — spawn del proceso Python, health check, pick_port, wait_until_ready, send_cookies, graceful_shutdown
  - `autopilot_bridge.rs` — comandos Tauri (start/stop/status/refresh_cookies + proxy get/send)
  - `main.rs` — módulos registrados, AutopilotService managed, cleanup en RunEvent::Exit
  - `Cargo.toml` — añadido `which = "7"`
  - **cargo check OK**, clippy limpio (en archivos nuevos)
- **Frontend**: `api.ts` extendido con tipos y wrappers del autopilot. `tsc --noEmit` OK.
- **Verificado**: servicio arranca con uvicorn, /health y /autopilot/session responden correctamente.
- **Pendiente Fase 1**: commit + PR a develop.
- **Próximo paso**: Fase 2 (`feature/autopilot-discovery`) — cliente LinkedIn Voyager API con httpx.

### 2026-06-30 — Fase 1 COMPLETADA + Fase 2 COMPLETADA
- **Fase 1** mergeada a `develop` (PR #1, squash). Code review aplicado: fixes de SSRF en proxy, CORS restringido, stdout/stderr a log file.
- **Fase 2** (`feature/autopilot-discovery`) mergeada a `develop` (PR #2, squash):
  - `linkedin/client.py` — cliente httpx autenticado, errores tipados (SessionExpired/RateLimited/Challenge), nunca loguea cookies
  - `linkedin/rate_limiter.py` — token bucket con jitter humano
  - `linkedin/parsing.py` — helpers del formato normalizado Voyager
  - `linkedin/search.py` — búsqueda + parseo de stubs
  - `linkedin/details.py` — detalle + detección de apply method (easy/external)
  - `linkedin/people.py` — búsqueda de recruiters
  - `discovery.py` — orquestador search→dedup→persist→enrich con parada graceful
  - `jobs_repository.py` — persistencia + deduplicación
  - API: `POST /autopilot/discover`, `GET /autopilot/jobs`
  - Frontend: `autopilotDiscover` + `getDiscoveredJobs`
- **Tests**: 45 pasando (database, queue, session, API, parsing, search, details, repo, discovery, rate limiter).
- **Decisión de release**: NO se tagea v1.x en `main` todavía. `main` se reserva para el primer milestone usable por el usuario (tras Fase 4, cuando exista UI). Se acumula en `develop` hasta entonces.
- **Próximo paso**: Fase 3 (`feature/autopilot-matcher`) — pipeline de scoring con Ollama (pre-filtros + scoring + ranking).

### 2026-06-30 — Fase 3 + Fase 4 COMPLETADAS + Release v0.2.0
- **Fase 3** (`feature/autopilot-matcher`, PR #3) mergeada a `develop`:
  - `pipeline/prefilter.py` — eliminación por reglas (blacklist, keywords, workplace, gap de experiencia), sin LLM
  - `pipeline/llm.py` — cliente Ollama con salida JSON estructurada (format=schema, temp 0)
  - `pipeline/scorer.py` — scoring 0-100 con razones, deal-breakers, missing skills
  - `pipeline/orchestrator.py` — discover→filter→score→rank, concurrencia limitada, cancelación
  - `pipeline/state.py` — estado de progreso compartido
  - `profile.py` — carga del perfil del usuario
  - API: `POST /autopilot/pipeline/run` (background), `/cancel`, SSE `/events`, `/status` real
- **Fase 4** (`feature/autopilot-dashboard`, PR #4) mergeada a `develop` (construida con sub-agente):
  - `AutopilotPage.tsx` — banner de estado servicio/sesión, Run Discovery con polling de progreso (1s), matches rankeados
  - `AutopilotSettingsPage.tsx` — formulario de criterios + config (schedule, límites, threshold)
  - `JobMatchCard.tsx` — badge de score por niveles, chips, link a recruiter, expandible
  - `App.tsx` — rutas `/autopilot` + `/autopilot/settings` + nav
- **Tests**: 58 backend (todos pasando), ruff limpio, tsc limpio, vite build OK.
- **Release v0.2.0**: MVP usable (discovery + matching + dashboard). Versiones bumpeadas a 0.2.0. Mergeado a `main` con tag `v0.2.0`.
- **Estado**: MVP funcional. El usuario puede configurar criterios, arrancar el servicio, ejecutar discovery y revisar ofertas rankeadas con AI.
- **Próximo paso**: Fase 5 (`feature/autopilot-applicator`) — ejecución: Easy Apply + form filler universal (Greenhouse/Lever API + Workday browser). Fase 6: conexiones + mensajes.

### 2026-06-30 — Fase 5 + Fase 6 COMPLETADAS + Release v0.3.0 (SISTEMA COMPLETO)
- **Fase 5** (`feature/autopilot-applicator`, PR #5) mergeada a `develop`:
  - `executor/browser.py` — Playwright visible con inyección de cookies LinkedIn
  - `executor/field_mapping.py` — detección de ATS + mapeo perfil→campos (funciones puras)
  - `executor/easy_apply.py` — flujo Easy Apply multi-paso, pausa antes de submit
  - `executor/answers.py` — respuestas LLM a preguntas custom + selección de opciones
  - `executor/form_filler/detector.py` — clasificación de campos (heurística word-boundary + LLM)
  - `executor/form_filler/filler.py` — filler universal con detección de CAPTCHA/account-wall
  - `executor/applicator.py` — enruta Easy Apply vs externo por ATS
  - `cv_locator.py` — localiza CV + texto extraído
  - API: `POST /autopilot/execute/apply`
- **Fase 6** (`feature/autopilot-connector`, PR #6) mergeada a `develop`:
  - `executor/connector.py` — conexiones + mensajes via Voyager API
  - `content.py` — generación de cartas + mensajes a recruiter (Ollama)
  - `limits.py` — límites diarios (conexiones/mensajes/aplicaciones) desde DB
  - `queue_builder.py` — construye cola de acciones + ejecuta aprobadas respetando límites
  - `AutopilotQueuePage.tsx` — UI de revisión/edición/aprobación/ejecución (sub-agente)
  - API: `POST /autopilot/queue/execute`, `GET /autopilot/usage`
- **Security review** (sub-agente security-reviewer) → **fixes críticos aplicados**:
  - C1: `executed_at` ahora se setea (los límites de mensajes/aplicaciones contaban siempre 0 = riesgo de ban)
  - C2: `/execute/apply` exige acción aprobada + check de límite diario
  - H1/H2/H3: race de conexión, parseo robusto de URL, anti-inyección JS
  - M1/M2/M3/M5: timezone localtime, cookies repr=False, dedup recruiters, sanitización de notas
- **Tests**: 89 backend (todos pasando), ruff limpio, tsc + vite build limpios.
- **Release v0.3.0**: SISTEMA AUTOPILOT COMPLETO (Fases 1-6). Versiones a 0.3.0, merge a `main` con tag `v0.3.0`.
- **Estado FINAL**: el sistema completo funciona end-to-end: discovery → matching → generación → cola de revisión → ejecución supervisada (apply/connect/message) con confirmación del usuario y límites de seguridad.
- **Pendiente para producción**: testing real con cuenta fake (POC), instalación de browsers Playwright (`playwright install chromium`), scheduler diario (APScheduler), ajuste de selectores LinkedIn según cambios de UI.

### 2026-06-30 — Integración de ai-job-search (Release v0.4.0)
Análisis e integración del repo `github.com/MadsLorentzen/ai-job-search` (MIT). Es un workflow basado en Claude Code (slash-commands + skills markdown + LaTeX), paradigma distinto al nuestro, pero con técnicas muy valiosas. Adoptadas 4:

- **#1 Guest discovery** (`feature/guest-discovery`, PR #7): endpoints `jobs-guest` de LinkedIn SIN autenticación (portado de TS a Python). **De-risquea el ban** — es la fuente por defecto ahora. Voyager solo enriquece el top-N. Fallback automático a guest si Voyager falla. Verificado en vivo (10 ofertas reales sin cookie).
- **#2 Framework de evaluación 5-dim** (`feature/scoring-framework`, PR #8): scorer con 5 dimensiones ponderadas (technical 30%, experience 25%, behavioral 15%, career 30%) + location pass/fail veto. Overall determinista en Python.
- **#3 ATS keyword coverage** (PR #8): extracción de keywords de la oferta (LLM) + matching determinista word-boundary vs perfil/CV. Endpoint `GET /autopilot/jobs/{id}/ats`. Cartas enfatizan keywords cubiertas reales.
- **#4 Writing style + drafter-reviewer** (`feature/content-quality`, PR #9): reglas de estilo estrictas (sin em-dashes, sin clichés, forward-looking) + patrón drafter-reviewer (draft→crítica→revisión con 2 llamadas Ollama).

**Fuente por defecto de discovery**: `guest` (elección del usuario, mínimo riesgo de ban). Configurable en Settings (guest/voyager/hybrid).

**Atribución**: técnicas y código de `github.com/MadsLorentzen/ai-job-search` bajo licencia MIT. Ver `docs/ATTRIBUTION.md`.

**Estado**: 115 tests backend pasando. Release v0.4.0.

**No adoptado** (incompatible con nuestro stack Tauri+Python+Ollama): arquitectura de slash-commands Claude Code, toolchain LaTeX (lualatex/xelatex para CVs), portales daneses, agentes Claude spawneados. La generación de CV en LaTeX con verificación de PDF queda como posible trabajo futuro si se añade un toolchain LaTeX.

---

*Fin del documento. Mantener actualizado conforme avance la implementación.*
