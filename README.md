# People's Bank Sri Lanka — Queue Management System

A production-ready, full-stack queue management system built with Flask, MySQL, Redis, and Bootstrap 5.

## Brand colours
| Colour  | Hex       | Usage                          |
|---------|-----------|--------------------------------|
| Red     | `#c80000` | Primary brand, nav, buttons    |
| Green   | `#99c630` | Success, priority toggle, bars |
| Yellow  | `#FFCB47` | Priority customers, warnings   |
| Dark    | `#4c4e54` | Text, sidebar, neutral         |
| White   | `#ffffff`  | Backgrounds, cards             |

## Quick start

```bash
git clone https://github.com/peoplesbank/pbqms.git
cd pbqms
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in values
flask db upgrade
flask seed-db                 # seeds service types
flask create-admin            # creates first admin user
flask run --debug
```

## Production (Docker)

```bash
cp .env.example .env
docker compose build
docker compose up -d
docker compose exec web flask db upgrade
docker compose exec web flask seed-db
docker compose exec web flask create-admin
```

## Generate branch QR codes

```bash
flask generate-qr --branch CLF   # single branch
flask generate-qr --all           # all active branches
```

## Customer flow

```
Customer scans QR → /register/{branch_code}
    ↓
Fills form (name, mobile, service, optional priority flag)
    ↓
POST /api/queue/register → token issued + SMS sent
    ↓
Lands on /register/token/{id} — live status polling
    ↓
Officer clicks "Call next" → POST /api/queue/call-next
    ↓
Second SMS to customer with counter number
    ↓
Display screen (WebSocket) updates in real-time
    ↓
Service complete → customer rates experience (1–5 stars)
```

## Role access

| Role           | Can serve                  | Dashboard          |
|----------------|----------------------------|--------------------|
| Admin          | All services               | System-wide admin  |
| Branch Manager | Other                      | Branch overview    |
| Lobby Officer  | Account Open/Close, FD     | Officer console    |
| Loan Officer   | Loans                      | Officer console    |

## Key API endpoints

| Method | Endpoint                        | Auth     | Description             |
|--------|---------------------------------|----------|-------------------------|
| POST   | `/api/auth/login`               | Public   | Login                   |
| POST   | `/api/queue/register`           | Public   | Customer registration   |
| GET    | `/api/queue/token/{id}/status`  | Public   | Token status polling    |
| POST   | `/api/queue/call-next`          | Officer  | Call next customer      |
| POST   | `/api/queue/token/{id}/complete`| Officer  | Mark service complete   |
| POST   | `/api/queue/token/{id}/rate`    | Public   | Submit satisfaction     |
| GET    | `/api/manager/dashboard`        | Manager  | Branch dashboard data   |
| GET    | `/api/admin/branches`           | Admin    | List all branches       |
| GET    | `/api/admin/audit-logs`         | Admin    | Audit trail             |
| GET    | `/api/queue/display/{code}`     | Public   | Display screen state    |
| WS     | `/socket.io/`                   | —        | Real-time updates       |

## SMS providers

Set `SMS_PROVIDER` in `.env` to one of:
- `mock` — logs to console (development)
- `dialog` — Dialog Sri Lanka SMS API
- `mobitel` — Mobitel SMS API
- `twilio` — Twilio (international)

## Tech stack

- **Backend**: Python 3.12, Flask 3.0, SQLAlchemy 2.0
- **Database**: MySQL 8.0
- **Cache/Queue**: Redis 7
- **Async tasks**: Celery 5.4
- **Real-time**: Flask-SocketIO (gevent-websocket)
- **Frontend**: Bootstrap 5.3, Chart.js 4, Tabler Icons
- **Infrastructure**: Docker Compose, Nginx, Gunicorn

## File structure

```
pbqms/
├── app/
│   ├── __init__.py         # App factory
│   ├── extensions.py       # db, socketio, celery
│   ├── config.py           # Dev / Prod / Test configs
│   ├── models/             # 9 SQLAlchemy models
│   ├── api/                # REST blueprints (auth, queue, admin, manager)
│   ├── views/              # Page route blueprints
│   ├── services/           # Queue logic, SMS, WebSocket, audit
│   ├── tasks/              # Celery async tasks
│   ├── utils/              # RBAC decorators, QR generator
│   └── templates/          # Jinja2 HTML (base + 7 screens)
├── migrations/             # Alembic scripts
├── static/
│   ├── css/pbqms.css       # 589-line brand design system
│   ├── js/
│   │   ├── officer-console.js
│   │   └── queue-display.js
│   └── qrcodes/            # Generated branch QR PNGs
├── nginx/pbqms.conf
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── wsgi.py
```
