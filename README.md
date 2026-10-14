# DigiBuddy

A personal digital twin for your emotional wellbeing. Each day you log how you feel and
a few things about your day. After a week, DigiBuddy forecasts how tomorrow might feel,
with a range and the reasons behind it. Each evening it compares its guess with what you
logged and learns from the gap.

DigiBuddy is a self-reflection tool, not a medical or diagnostic product.

## Quick start (Docker)

Install Docker Desktop and open it, then double-click:

- **Windows:** `start.bat` (and `stop.bat`)
- **Mac:** `start.command` (and `stop.command`). The first time, macOS may block it: right-click it,
  choose **Open**, then **Open** again. If it says it can't be run, open Terminal in this folder and
  run `chmod +x *.command` once.

The script builds and starts everything (5-10 minutes the first time), creates the demo account
once, and opens the app. Or run it by hand:

```bash
docker compose up --build -d
docker compose exec api python -m scripts.seed      # demo data, about a minute
```

Open http://localhost:3000 and sign in as **demo@digibuddy.app / demo1234**. The demo has
120 days of synthetic pages, a full prediction history, accuracy that improves over time,
and insights. API docs: http://localhost:8000/docs.

Optional: `python -m scripts.seed --all-profiles` also creates `weak@digibuddy.app` and
`noise@digibuddy.app` (same password) to compare how the twin behaves.

## Local development

**Backend** (Python 3.12, Postgres 16):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                    # point DATABASE_URL at your Postgres
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```

Checks: `ruff check . && ruff format --check . && mypy app scripts && pytest`
(`pytest -m "not slow"` skips the model-training tests, which take a couple of minutes).
Tests use SQLite, so they need no database.

**Frontend** (Node 22):

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000, forwards /api/v1 to localhost:8000
```

Checks: `npm run lint && npm run typecheck && npm test && npm run build`.

After changing API schemas: `python -m scripts.export_openapi` (in `backend/`), then
`npm run gen:api` (in `frontend/`).

## Architecture

```
backend/
  app/api/        FastAPI routers (thin: validate, call a service, shape the response)
  app/services/   business logic; every query is scoped to the calling user
  app/ml/         the prediction engine, independent of FastAPI and the database
  app/jobs/       nightly retraining (APScheduler; run_nightly() is plain async code)
  app/core/       config, security, rate limiting, logging, support resources
  app/db/         SQLAlchemy models and session
  alembic/        migrations
  scripts/        synthetic data generator, seed, OpenAPI export
frontend/
  src/app/        routes (Today, Check-in, History, Twin, Insights, Settings, auth, onboarding)
  src/components/ui/   design-system components (Book, FeelingScale, ForecastCard, ...)
  src/lib/hooks/  all data fetching (React Query); pages never call fetch
  src/types/      API types generated from OpenAPI
```

Auth: email and password (argon2). A short-lived access token is kept in memory; a
refresh token sits in an httpOnly cookie. The browser only talks to the Next.js server,
which forwards `/api/v1/*` to the API, so everything is same-origin.

Privacy: notes are stored only for you and never used for forecasts or insights. Logs
contain IDs and timings, never check-in values or notes. `GET /me/export` downloads
everything; `DELETE /me` removes every row and every trained model file.

## How the prediction engine works

**What it predicts.** Tomorrow's mood, energy and stress (1 to 10), each with an 80%
range and the top three reasons.

**What it looks at.** Only what was known by the end of today: your last three days of
feelings, 3- and 7-day averages and how much things varied, sleep debt against your own
usual, exercise and outdoor time, screen time, workload, time with people, your most
common tags, streaks, which day tomorrow is, and how long since your last check-in. A
test rebuilds the features with the future removed and checks nothing changes, so no
feature can peek at tomorrow.

**It grows with you.** It counts the days you've actually logged:

| Logged days | What it uses |
|---|---|
| 0 to 6 | Nothing yet: it shows how many pages until the first forecast. |
| 7 to 20 | Your recent trend (a weighted average favouring the last few days) plus how each weekday tends to go. |
| 21 to 59 | Also a personal linear model (ridge regression) on all the features above. |
| 60+ | Also gradient boosting. Each feeling uses whichever model has been most accurate. |

**It has to earn every change.** To test a model, the engine replays your recent days.
For each day it trains only on the days before, makes a guess, and records how far off it
was. A new model replaces the current one only if it beats both the current model and
the simplest guess, "tomorrow = today". Ridge and gradient boosting must also show the
win isn't luck (a paired statistical test). If nothing beats "tomorrow = today", that is
what you get: the twin never ships something worse.

**Ranges are honest.** The 80% range comes from the model's own recent misses (split
conformal intervals). On synthetic data about 80% of real outcomes land inside, and the
Twin page shows the live rate. If you skip days, the range widens; after more than three
days without a page it falls back to the simple trend model.

**It keeps up with you.** Training gives recent days more weight (half-life 60 days).
Every night at 03:00 your time, if you logged anything new, it retrains, re-tests and
updates tomorrow's forecast. When you check in, it scores yesterday's guess and makes a
fresh forecast straight away with the current model.

**Reasons.** Ridge reasons come from each feature's weight times how unusual today's value
is. Gradient-boosting reasons use LightGBM's per-feature contributions (SHAP values), or a
"what if this were typical" comparison when LightGBM isn't installed. The trend model's
reasons are "your recent days" and "the day of the week". All feature names are turned
into plain words in `app/ml/feature_labels.py`.

**Insights** are simple, checkable observations, never causes: correlations shown only
with 21+ days and |r| >= 0.3, best and worst weekdays once each has 3+ pages, and tags
that come before better or worse days (5+ occurrences). Each shows its sample size.

**Wellbeing safety.** If you log mood 2 or lower, mood 3 or lower three days running, or
the forecast is 3 or lower, the API returns a gentle support note with local helplines
(Singapore, India, or an international directory). The Today page shows it before any
forecast. Edit the list in `backend/app/core/support_resources.py`; the product team
must verify the numbers before launch.

## The design system

The UI uses the **DigiBuddy Storybook** design system: every screen is a page in a
hand-painted journal on a wooden desk.

- Tokens (colors for the Daylight and Lamplight themes, type, spacing, radii, shadows,
  motion) are generated from `frontend/design/tokens.json` into
  `src/styles/tokens.css` with `npm run tokens`. To update the look, replace
  `tokens.json` with a new export from the design system and run that command.
- Components live in `frontend/src/components/ui/` and only use tokens. Pages compose
  them and get data from hooks, so a redesign touches presentation only.
- Fonts (Grandstander, Literata, Gaegu) load through `next/font`.

See `DECISIONS.md` for every judgement call made while building this.
