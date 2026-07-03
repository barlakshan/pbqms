# People's Bank Sri Lanka — Queue Management System

## Project overview

This repository implements a queue management system for branch banking. It supports customer registration through branch QR codes, live queue screens, officer workflows, branch manager and admin dashboards, SMS notifications, and role-based access control.

The current codebase provides a mostly complete MVP with the following fully implemented capabilities:

- Customer registration by scanning branch QR codes
- Token issuance per service type with unique branch/service numbering
- Priority queue handling for elderly, pregnant, and disabled customers
- Officer "call next" workflow with counter assignment and service tracking
- Customer status polling and satisfaction rating submission
- Live display screen updates over Socket.IO
- SMS notification abstraction with mock, Dialog, Mobitel, and Twilio providers
- Admin branch/user management and audit logging
- Branch manager officer management and analytics
- Local SQLite fallback for development and MySQL support for production
- Docker Compose deployment for web, MySQL, Redis, and Celery worker

## Current development state

### Completed

- Queue registration flow with customer and token persistence
- Role-based login and dashboard redirects
- Admin UI and API for branches, users, QR generation, and audit logs
- Manager UI and API for officer management and branch analytics
- Officer dashboard with current queue counts and recent completed tokens
- Live screen route and Socket.IO event handlers for branch room updates
- SMS task abstraction with Celery async fallback via thread
- CLI commands: `seed-db`, `create-admin`, `reset-queue`, `generate-qr`
- Default branch QR generation into `static/qrcodes`
- Test coverage for manager flow and seed data

### Incomplete / optional

- `app/tasks/cleanup_tasks.py` is present but not implemented
- Some view-level stats still use static placeholder values
- No production `.env`; developers must populate `.env.example`
- Swagger/OpenAPI docs not included
- Monitoring, logging and DNS/HTTPS configuration are not part of this repo

## Architecture

### Entry points

- `wsgi.py` — starts the Flask + Socket.IO application
- `app/__init__.py` — app factory, blueprint registration, DB init, CLI commands
- `app/config.py` — development, production, testing configuration
- `Dockerfile` — builds the web container
- `docker-compose.yml` — orchestrates `web`, `db`, `redis`, and `celery`

### Key packages

- `app/api/` — JSON API endpoints
- `app/views/` — server-rendered HTML pages
- `app/models/` — SQLAlchemy models and schema
- `app/services/` — business logic and notifications
- `app/tasks/` — asynchronous Celery tasks
- `app/utils/` — decorators and QR generation helpers
- `app/templates/` — Jinja2 UI templates
- `static/` — CSS, JavaScript, QR assets

### Database models

- `Branch` — branch metadata and QR payload
- `User` — employee accounts, roles, and branch assignment
- `ServiceType` — queue service categories and prefixes
- `Customer` — customer identity and mobile details
- `QueueToken` — ticket state, priority, service timing, and status
- `Counter` — branch counter metadata and officer assignment
- `SmsLog` — SMS send records and provider status
- `SatisfactionRating` — customer survey ratings
- `AuditLog` — recorded admin/manager actions

### Roles and permissions

- `ADMIN` — full system administration
- `BRANCH_MANAGER` — branch-level dashboards, managers, and QR codes
- `LOBBY_OFFICER` — lobby service queue handling
- `LOAN_OFFICER` — loan service queue handling

## Deployment options

### Local development with SQLite

This project can run out of the box using the default SQLite database.

1. Create and activate a Python virtual environment:

```powershell
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Copy environment variables:

```powershell
copy .env.example .env
```

4. Run database migrations and seed data:

```powershell
flask db upgrade
flask seed-db
flask create-admin
```

5. Start the app:

```powershell
flask run
```

### Docker Compose deployment

Use Docker Compose for MySQL + Redis + Celery.

```powershell
copy .env.example .env
docker compose build
docker compose up -d
docker compose exec web flask db upgrade
docker compose exec web flask seed-db
docker compose exec web flask create-admin
```

### Production readiness

- Set `DATABASE_URL` to a MySQL URI
- Set `REDIS_URL` and `CELERY_BROKER_URL` for Redis
- Configure real SMS provider credentials
- Use secure `SECRET_KEY` and HTTPS in production

## Environment variables

Use `.env.example` as a template.

- `FLASK_APP` — `wsgi.py`
- `FLASK_ENV` — `development` or `production`
- `SECRET_KEY` — session security key
- `DATABASE_URL` — SQLAlchemy URI
- `REDIS_URL` — Redis connection
- `CELERY_BROKER_URL` — Celery broker URL
- `SMS_PROVIDER` — `mock`, `dialog`, `mobitel`, `twilio`
- `DIALOG_USER`, `DIALOG_PASS`, `DIALOG_SENDER_ID`
- `MOBITEL_TOKEN`, `MOBITEL_SENDER_ID`
- `TWILIO_SID`, `TWILIO_TOKEN`, `TWILIO_FROM`
- `BASE_URL` — used for QR code registration payloads

## CLI commands

The repository defines these Flask CLI commands:

- `flask seed-db` — build schema and insert service types
- `flask create-admin` — add first admin user interactively
- `flask reset-queue --branch CODE` — clear today’s queue tokens
- `flask generate-qr --branch CODE` — generate QR for a branch
- `flask generate-qr --all` — generate all active branch QR codes

## Key user flows

### Customer

1. Scan branch QR code
2. Open `/register/<branch_code>`
3. Submit customer and service details
4. Receive token confirmation and estimated wait
5. Poll `/register/token/<id>` for queue status
6. Receive call SMS and proceed to counter
7. Submit satisfaction rating after service

### Officer

1. Login
2. View dashboard with waiting and served counts
3. Call next waiting customer
4. Start service and complete tokens
5. See recent completed tokens and ratings

### Branch Manager

1. Login
2. View branch totals, service mix, and officer stats
3. Add or edit officers
4. View branch QR code page

### Admin

1. Login
2. Manage branches and users
3. View audit logs and branch performance
4. Generate QR codes for branch registration

## API summary

- `POST /api/auth/login`
- `POST /api/queue/register`
- `GET /api/queue/token/<id>/status`
- `POST /api/queue/call-next`
- `POST /api/queue/token/<id>/start`
- `POST /api/queue/token/<id>/complete`
- `POST /api/queue/token/<id>/rate`
- `GET /api/queue/display/<branch_code>`
- `GET /api/admin/branches`
- `GET /api/admin/users`
- `GET /api/admin/audit-logs`
- `GET /api/manager/dashboard`

## Real-time support

- Socket.IO endpoint runs on `/socket.io/`
- Display clients join branch rooms
- Queue updates are emitted from `app.services.notification_service`

## Testing

Existing tests cover:

- `tests/test_manager_flow.py` — manager login, officer creation, branch QR page
- `tests/test_seed_db.py` — CLI seeding and service type creation

## File structure

```
pbqms/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── extensions.py
│   ├── api/
│   ├── views/
│   ├── models/
│   ├── services/
│   ├── tasks/
│   ├── utils/
│   └── templates/
├── static/
│   ├── css/
│   ├── js/
│   └── qrcodes/
├── migrations/
├── nginx/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
└── wsgi.py
```

## Notes

- The code is structured for both browser-based pages and JSON APIs.
- `app/services/queue_service.py` contains core queue logic.
- SMS sending can use Celery if available, otherwise a thread fallback is used.
- `app/tasks/cleanup_tasks.py` is a placeholder and currently empty.
- `static/qrcodes/` stores generated branch QR images.
- Default development DB is `pbqms_dev.sqlite3`; test DB is `pbqms_test.sqlite3`.

## Summary

This project is ready for local development and Docker deployment. The main queue flows are implemented, and the repository contains a working Flask application with roles, queue management, notifications, and live display support.
