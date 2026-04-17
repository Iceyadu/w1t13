# HarborView Property Operations Portal

A full-stack property management portal for HOA and multifamily teams to manage resident billing, community listings, and service orders in a single offline-capable application.

## What It Does

- **Resident Self-Service**: View statements, submit payment evidence, request credits, track service orders
- **Billing Engine**: Configurable fee items, automated bill generation, tax calculation, late fees, reconciliation
- **Service Orders**: Strict state machine workflow (created > payment recorded > accepted > dispatched > arrived > in-service > completed)
- **Marketplace Listings**: Staff-managed listings with draft/publish controls, media uploads, bulk operations
- **Content Management**: Configurable homepage with carousel, tiles, banners; preview mode and 10% canary rollout
- **Offline Support**: Encrypted IndexedDB cache, FIFO retry queue, optimistic locking with conflict resolution
- **Security**: Local-only auth, bcrypt password hashing, field-level encryption, role-based data masking
- **Backup**: Encrypted backups (triggered via API or scheduled externally via cron) to local filesystem with 30-day retention and offline restore

## Architecture

```
Frontend (Vue 3 + TypeScript)  -->  Backend (FastAPI)  -->  PostgreSQL
     |                                    |
  Service Worker               Background Tasks
  IndexedDB Cache              (billing, backups)
  Retry Queue                  PDF Generation
```

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3, TypeScript, Pinia, Axios, Dexie.js, Vite |
| Backend | FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 |
| Database | PostgreSQL 15 |
| PDF | ReportLab |
| Containerization | Docker, Docker Compose |

### Roles

| Role | Access |
|------|--------|
| Administrator | Full system access, user management, content, backups |
| Property Manager | Operations: orders, listings, resident oversight |
| Accounting Clerk | Billing, payment verification, reconciliation, exports |
| Maintenance/Dispatcher | Service order processing and state transitions |
| Resident | Self-service: profile, statements, payments, orders |

## Startup

### Prerequisites

- Docker and Docker Compose installed
- Ports 8080, 8001, 5434 available (override `DB_PORT` in `.env` if that host port is taken)

### Quick Start

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start all services
docker compose up --build -d

# 3. Wait for services to be ready (backend creates tables via SQLAlchemy on startup)
docker compose logs -f backend

# 4. Access the application
#    Frontend: http://localhost:8080
#    Backend API: http://localhost:8001
#    API docs: http://localhost:8001/docs
```

### Stopping

```bash
docker compose down          # Stop services (keep data)
docker compose down -v       # Stop and remove volumes (reset data)
```

## Service URLs

| Service | URL |
|---------|-----|
| Frontend (web app) | http://localhost:8080 |
| Backend API | http://localhost:8001 |
| Swagger/OpenAPI docs | http://localhost:8001/docs |
| Health check | http://localhost:8001/api/v1/health |
| PostgreSQL | localhost:5434 |

## Seed Credentials

On first startup, if no users exist, five role-based user accounts (admin, property_manager, accounting_clerk, maintenance_dispatcher, resident) plus a property with units and a sample resident are created:

| Username | Password | Role |
|----------|----------|------|
| `admin` | `Admin@Harbor2026` | Administrator |
| `manager` | `Manager@Hbr2026` | Property Manager |
| `clerk` | `Clerk@@Harbor2026` | Accounting Clerk |
| `maintenance` | `Maint@@Harbor2026` | Maintenance / Dispatcher |
| `resident1` | `Resident@Hbr2026` | Resident |

**Change these passwords immediately in production.**

## Testing

### Run All Tests

```bash
./run_tests.sh
```

### Run Unit Tests Only

```bash
./run_tests.sh unit
```

### Run API Tests Only

Requires the backend to be running:

```bash
docker compose up -d
./run_tests.sh api
```

### Test Dependencies

```bash
# For unit tests (from repo root)
pip install -r backend/requirements.txt
pip install pytest

# For API tests
pip install -r API_tests/requirements.txt
```

## Project Structure

```
repo/
  docker-compose.yml        # Orchestration for all services
  run_tests.sh              # Unified test runner
  .env.example              # Environment variable template
  backend/
    Dockerfile              # Python 3.11 + FastAPI
    requirements.txt        # Python dependencies
    app/
      main.py               # FastAPI entry point (create_all + seed on startup)
      config.py             # Settings from environment (SECRET_KEY required)
      database.py           # SQLAlchemy async engine and session
      dependencies.py       # Auth and role dependency injection
      models/               # SQLAlchemy ORM models (10 files)
      schemas/              # Pydantic request/response schemas (13 files)
      routers/              # API route handlers (16 modules)
      services/             # Business logic services (9 modules)
      middleware/            # Idempotency middleware
      utils/                # Pagination, conflict, ownership helpers
  frontend/
    Dockerfile              # Multi-stage: Node build + Nginx serve
    nginx.conf              # Reverse proxy and SPA config
    package.json            # Node dependencies
    src/
      main.ts               # Vue app bootstrap
      App.vue               # Root component
      router/               # Vue Router with auth guards
      stores/               # Pinia stores (auth, offline)
      services/             # API client, offline cache, retry queue, sync
      views/                # 8 page components
      components/           # Layout components (navbar, sidebar)
      types/                # TypeScript interfaces
      assets/               # CSS styles
  unit_tests/
    backend/                # Python unit tests (6 test files)
    frontend/               # Frontend test setup
  API_tests/                # Integration tests against running backend (6 test files)
```

## API Endpoints

All API endpoints are prefixed with `/api/v1`. Full specification is in `docs/api-spec.md`.

| Group | Prefix | Key Endpoints |
|-------|--------|--------------|
| Health | `/health` | Liveness, readiness checks |
| Auth | `/auth` | Login, refresh, logout, password change |
| Users | `/users` | CRUD, role management |
| Residents | `/residents` | Profile, addresses |
| Properties | `/properties` | Property and unit management |
| Billing | `/billing` | Fee items, bills, generation, reconciliation |
| Payments | `/payments` | Evidence upload, verification |
| Credits | `/credits` | Credit memos, approval |
| Orders | `/orders` | CRUD, state transitions |
| Listings | `/listings` | CRUD, publish controls, bulk status |
| Media | `/media` | Upload, download, validation |
| Content | `/content` | Homepage config, sections, preview |
| Rollout | `/rollout` | Canary user management |
| Reports | `/reports` | PDF receipts, CSV exports |
| Backup | `/backup` | Trigger, restore, records |
| Audit | `/audit` | Query audit logs |

## Environment Variables

See `.env.example` for all configurable values. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | `harborview_secret` | Database password |
| `SECRET_KEY` | **required** | JWT signing key (app refuses to start if empty) |
| `ENCRYPTION_KEY` | (auto-generated) | Fernet key for resident contact encryption |
| `BACKUP_PASSPHRASE` | (must change) | Backup file encryption passphrase |

**`SECRET_KEY` is mandatory.** The application will fail to start with a clear error if it is not set. Use a random string of at least 32 characters.

**Database schema** is created automatically via `Base.metadata.create_all()` on startup. A default admin user is seeded if the users table is empty.
