# Perde

A minimalist collaborative story-writing app for pen-pal style co-authoring.

## Local Development

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
# 1. Clone and enter the project
cd perde

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies (use the venv pip, not system pip)
.venv/bin/pip install -r backend/requirements.txt

# 4. (Optional) set environment variables
export RESEND_API_KEY=your_resend_api_key_here
export APP_URL=http://localhost:8000
export FROM_EMAIL="Perde <you@yourdomain.com>"
# JWT_SECRET will default to a dev placeholder if not set

# 5. Run the dev server
.venv/bin/uvicorn backend.main:app --reload --port 8000
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

> **Note:** If `RESEND_API_KEY` is not set, email notifications are logged to the console instead of sent.

### Project structure

```
perde/
├── backend/
│   ├── main.py            # FastAPI app + all routes
│   ├── models.py          # SQLite query functions
│   ├── auth.py            # JWT + bcrypt
│   ├── email_service.py   # Resend API integration
│   ├── database.py        # DB connection + schema
│   └── requirements.txt
├── frontend/
│   ├── index.html         # Login / register
│   ├── home.html          # Story list
│   ├── editor.html        # Story editor
│   ├── style.css          # Shared styles (dark mode)
│   └── app.js             # All page logic
├── render.yaml            # Render.com deploy config
└── README.md
```

## Deploying to Render.com

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → New → Blueprint.
3. Select your repo — Render will detect `render.yaml` automatically.
4. In the service's **Environment** tab, set:
   - `RESEND_API_KEY` — your Resend API key
   - `APP_URL` — your Render public URL (e.g. `https://perde.onrender.com`)
   - `FROM_EMAIL` — the from address (must be a verified sender in Resend)
5. Deploy. SQLite data persists on the attached 1 GB disk at `/data/perde.db`.

## Email setup (Resend)

1. Sign up at [resend.com](https://resend.com) — free tier: 3,000 emails/month.
2. Add and verify your sending domain (or use the sandbox for testing).
3. Create an API key and set it as `RESEND_API_KEY`.
4. Set `FROM_EMAIL` to match your verified domain, e.g. `Perde <notifications@yourdomain.com>`.

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | No | `./perde.db` | Path to SQLite file |
| `JWT_SECRET` | Yes (prod) | dev placeholder | Secret for signing JWTs |
| `RESEND_API_KEY` | No | — | Resend API key (emails logged if unset) |
| `APP_URL` | No | `http://localhost:8000` | Base URL for email links |
| `FROM_EMAIL` | No | `Perde <notifications@perde.app>` | Email sender address |
