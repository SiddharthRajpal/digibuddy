# DigiBuddy: Technical Reference

This document describes every technical part of DigiBuddy: architecture, data model, API,
security, the full prediction engine, insights, safety features, the frontend, the page-turn
animation system, testing, tooling and deployment. Every number below is taken from the code
in this repository.

---

## Contents

1. [What the system does](#1-what-the-system-does)
2. [Architecture](#2-architecture)
3. [Repository layout](#3-repository-layout)
4. [Technology stack](#4-technology-stack)
5. [Data model](#5-data-model)
6. [Backend application](#6-backend-application)
7. [Authentication and security](#7-authentication-and-security)
8. [API reference](#8-api-reference)
9. [Check-in rules](#9-check-in-rules)
10. [The prediction engine (ML)](#10-the-prediction-engine-ml)
11. [Insights engine](#11-insights-engine)
12. [Wellbeing safety](#12-wellbeing-safety)
13. [Privacy and the data lifecycle](#13-privacy-and-the-data-lifecycle)
14. [Synthetic data generator](#14-synthetic-data-generator)
15. [Seeding the demo account](#15-seeding-the-demo-account)
16. [Nightly retraining job](#16-nightly-retraining-job)
17. [Frontend](#17-frontend)
18. [Design system implementation](#18-design-system-implementation)
19. [Animation system (page turns)](#19-animation-system-page-turns)
20. [Testing](#20-testing)
21. [Tooling and CI](#21-tooling-and-ci)
22. [Running and deployment](#22-running-and-deployment)
23. [Configuration reference](#23-configuration-reference)
24. [Known limitations and future work](#24-known-limitations-and-future-work)

---

## 1. What the system does

DigiBuddy is a personal "digital twin" for emotional wellbeing.

1. **Log.** Each day the user records five core feelings (mood, energy, stress, worry/anxiety,
   focus, each 1–10) and, optionally, sleep, activity, lifestyle, social and workload details,
   tags, their own custom trackers, and private notes.
2. **Learn.** The system keeps a per-user model of how their days affect their next day.
3. **Predict.** After 7 logged days it forecasts tomorrow's **mood, energy and stress**, each
   with an 80% range and the top three reasons.
4. **Compare.** When the next day is logged, the forecast is scored against what actually
   happened. Accuracy is tracked over time, and models are retrained nightly and replaced only
   when a better one is proven on the user's own recent days.

It is a self-reflection tool, not a medical device. Free-text notes are never analysed.

---

## 2. Architecture

```
 Browser (React, Next.js client components)
    │  same origin: http://host:3000
    ▼
 Next.js server (frontend container)
    │  serves the app; rewrites /api/v1/*  ──►  http://api:8000/api/v1/*
    ▼
 FastAPI (api container, Python 3.12, uvicorn)
    ├── api/        routers (HTTP only: validate, call service, shape response)
    ├── services/   business logic, all queries scoped to the signed-in user
    ├── ml/         prediction engine (pure pandas/numpy/sklearn, no web or DB code)
    ├── jobs/       nightly retraining (APScheduler, in-process)
    └── db/         SQLAlchemy 2 async models
    │
    ├──► PostgreSQL 16 (db container, volume db-data)       all rows
    └──► model artifact files (volume artifacts)             trained models (joblib)
```

Design principles:

- **The ML package (`app/ml`) knows nothing about HTTP or the database.** It takes plain records
  or DataFrames and returns forecasts and training outcomes, so it can be unit-tested and run
  from scripts. `services/twin.py` is the only bridge between the database and the ML code.
- **Routers are thin.** Logic lives in services. Every service query filters by `user_id`, which
  is where authorization is enforced.
- **Same-origin frontend.** The browser only talks to the Next.js server, which proxies
  `/api/v1/*` to the API. The httpOnly refresh cookie therefore works without CORS.
- **The CPU-heavy ML work** (training, forecasting) runs in a worker thread
  (`asyncio.to_thread`) so it never blocks the async event loop.

---

## 3. Repository layout

```
digibuddy/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app factory, CORS, middleware, routers, scheduler lifespan
│   │   ├── api/                 auth.py, me.py, checkins.py, other.py (metrics, predictions,
│   │   │                        twin, insights, meta, health), deps.py (session, clock, current user)
│   │   ├── core/                config.py, security.py, rate_limit.py, clock.py, logging.py,
│   │   │                        support_resources.py
│   │   ├── db/                  base.py (naming conventions), session.py, models.py
│   │   ├── schemas/             Pydantic v2 request/response models
│   │   ├── services/            users.py, checkins.py, twin.py, accuracy.py, insights.py, support.py
│   │   ├── ml/                  schema.py, data.py, features.py, feature_labels.py, models.py,
│   │   │                        evaluation.py, training.py, predict.py
│   │   └── jobs/retrain.py      nightly job + APScheduler wiring
│   ├── alembic/                 migrations (0001_initial_schema.py)
│   ├── scripts/                 generate_synthetic.py, seed.py, export_openapi.py
│   ├── tests/                   conftest.py, test_api.py, test_ml.py, test_safety_privacy.py
│   ├── openapi.json             exported schema (source of the frontend's types)
│   ├── Dockerfile, requirements*.txt, pyproject.toml, alembic.ini, .env.example
├── frontend/
│   ├── src/app/                 routes: / (Today), /checkin/[date], /history, /twin, /insights,
│   │                            /settings, /login, /signup, /onboarding, not-found
│   ├── src/components/book/     Book.tsx (BookFrame + Spread), flip.ts (page-turn engine), routes.ts
│   ├── src/components/ui/       design-system components
│   ├── src/components/checkin/  check-in form hook and fields
│   ├── src/lib/                 api.ts, auth.tsx, hooks/, schemas.ts, feelings.ts, dates.ts, theme.ts
│   ├── src/types/               openapi.d.ts (generated) and api.ts (friendly aliases)
│   ├── src/styles/              tokens.css (generated from design/tokens.json), globals.css
│   ├── design/tokens.json       design system export
│   ├── public/mascot/           quokka cut-outs
│   └── Dockerfile, next.config.mjs, vitest.config.ts, eslint.config.mjs, tsconfig.json
├── docker-compose.yml           db + api + frontend
├── start.bat / stop.bat         Windows one-click start/stop
├── start.command / stop.command macOS equivalents
├── .github/workflows/ci.yml     lint, type-check, tests, build
├── README.md, DECISIONS.md, technical.md, wee.md
```

---

## 4. Technology stack

| Layer | Technology |
|---|---|
| API | Python 3.12, FastAPI, uvicorn, Pydantic v2, pydantic-settings |
| Database | PostgreSQL 16 via SQLAlchemy 2.x async (asyncpg); SQLite (aiosqlite) in tests |
| Migrations | Alembic (async env, batch mode) |
| ML | pandas, numpy, scipy, scikit-learn (Ridge, HistGradientBoosting, SimpleImputer, StandardScaler, TimeSeriesSplit), LightGBM (optional), joblib |
| Jobs | APScheduler 3 (AsyncIOScheduler) |
| Auth | argon2-cffi (Argon2id), PyJWT (HS256) |
| Timezones | Python `zoneinfo` + the `tzdata` package (slim Docker images have no system tz database) |
| Frontend | Next.js 15 (App Router), React 19, TypeScript (strict), TanStack React Query 5, react-hook-form 7, zod 3 |
| Styling | CSS Modules + generated CSS custom properties (design tokens); fonts via `next/font/google` |
| Testing | pytest + pytest-asyncio + httpx (ASGI transport); vitest + Testing Library + jsdom |
| Quality | ruff (lint + format), mypy (strict), ESLint (next/core-web-vitals + typescript), tsc |
| Packaging | Docker, Docker Compose; Next.js standalone output |

---

## 5. Data model

All tables use integer primary keys. Foreign keys to `users` cascade on delete. Constraint names
follow a fixed naming convention (`uq_…`, `fk_…`, `ix_…`). Timestamps are timezone-aware.

### `users`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `email` | varchar(320), unique, indexed | stored lowercased |
| `password_hash` | varchar(255) | Argon2id hash string (includes salt and parameters) |
| `display_name` | varchar(80) | |
| `timezone` | varchar(64) | IANA name (e.g. `Asia/Singapore`); defines every "day" for this user |
| `onboarding_completed` | bool | set by onboarding |
| `token_version` | int | incremented on logout to revoke every issued token |
| `created_at` | timestamptz | server default now() |

### `daily_checkins`: one row per user per *local* calendar date

Unique constraint `(user_id, date)`.

| Column | Type | Range / notes |
|---|---|---|
| `date` | date | user's local date |
| `mood`, `energy`, `stress`, `anxiety`, `focus` | int, required | 1–10 |
| `sleep_hours` | float, nullable | 0–24 |
| `sleep_quality` | int, nullable | 1–5 |
| `exercise_minutes`, `outdoor_minutes` | int, nullable | 0–1440 |
| `screen_time_hours` | float, nullable | 0–24 |
| `caffeine_servings` | int, nullable | 0–50 |
| `alcohol_units` | int, nullable | 0–100 |
| `meals_eaten` | int, nullable | 0–5 |
| `social_interaction`, `workload` | int, nullable | 1–5 |
| `tags` | JSON list of strings | ≤20 tags, each 1–32 chars, lowercased, trimmed, de-duplicated |
| `notes` | text, nullable | ≤2,000 chars; stored for the user only, never modelled |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | set in Python on insert/update (microsecond precision on every backend); drives "needs retrain" |

### `custom_metrics` and `custom_metric_values`

- `custom_metrics(id, user_id, name ≤60, min, max, unit ≤20)`, unique `(user_id, name)`.
- `custom_metric_values(id, checkin_id → daily_checkins, metric_id → custom_metrics, value)`,
  unique `(checkin_id, metric_id)`. Values must lie in `[min, max]` and the metric must belong to
  the same user.

### `model_versions`: one row per trained model *per target*

Stage 3 picks the best model separately for mood, energy and stress, so each row is one model
for one target.

| Column | Notes |
|---|---|
| `target` | `mood` / `energy` / `stress` |
| `model_type` | `naive` / `baseline` / `ridge` / `gbm` |
| `stage` | 0–3 at training time |
| `trained_at` | when training ran |
| `trained_through` | last local date included in the data |
| `data_updated_at` | newest `daily_checkins.updated_at` seen by this training (the retrain watermark) |
| `n_training_days` | number of training rows used for the final fit |
| `feature_list` | JSON list of feature names (ridge/gbm only) |
| `hyperparameters` | JSON, e.g. `{"alpha": 30.0, "selection": "promoted: …"}`; non-winning candidates have `{"selection": "candidate"}` |
| `backtest_mae`, `naive_mae` | MAE over the same backtest days |
| `backtest_coverage` | empirical 80%-interval coverage measured sequentially on the backtest |
| `interval_halfwidth` | conformal half-width used for this model's ranges |
| `is_active` | indexed; exactly one active row per (user, target) |
| `artifact_path` | path of the serialized model on disk (winners only), never stored in the row |

Every training run writes one row per evaluated candidate per target (including `naive`), so the
full selection history is auditable.

### `predictions`: one row per user per target date

Unique `(user_id, target_date)`.

| Column | Notes |
|---|---|
| `target_date` | the day being forecast |
| `stage`, `days_since_last_log` | context at forecast time |
| `created_at` | when the forecast was (re)made |
| `{mood,energy,stress}_model_version_id` | FK to the active `model_versions` row, `ON DELETE SET NULL` |
| `{t}_predicted`, `{t}_lower`, `{t}_upper` | point forecast and 80% interval, clipped to 1–10, one decimal |
| `{t}_naive` | "tomorrow = today" value at forecast time (for fair accuracy comparison) |
| `{t}_actual`, `{t}_abs_error` | filled when the target day is logged (abs error rounded to 2 dp) |
| `model_types` | JSON `{"mood": "gbm", …}`: model actually used (can differ from the active one after long gaps) |
| `top_factors` | JSON `{"mood": [{feature, label, note, direction, contribution}, …], …}` |

### Migrations

`alembic/versions/0001_initial_schema.py` was autogenerated against PostgreSQL and is applied
on container start (`alembic upgrade head`). `render_as_batch=True` keeps migrations
SQLite-compatible. Tests create tables directly from the metadata.

---

## 6. Backend application

### Startup (`app/main.py`)

- `create_app()` builds the FastAPI app (title "DigiBuddy API", version from settings) and adds:
  - CORS middleware (origins from `CORS_ORIGINS`, credentials allowed),
  - a request-timing middleware,
  - all routers under the `/api/v1` prefix.
- A lifespan hook configures logging and, if `ENABLE_SCHEDULER=true`, starts the APScheduler job
  (stopped on shutdown).
- Interactive OpenAPI docs are served at `/docs`; `scripts/export_openapi.py` writes
  `backend/openapi.json`.

### Dependencies (`app/api/deps.py`)

- `db_session`: one `AsyncSession` per request.
- `get_now`: current UTC time. Tests override it with a controllable clock, so timezone and
  "day" logic is fully testable.
- `current_user`: reads the bearer token, validates it, loads the user, checks the token
  version, and stores `user_id` on `request.state` for logging.

### Logging (`app/core/logging.py`)

One log line per request: method, **route template** (e.g. `/checkins/{day}`, not the filled
path), status, user id, duration in ms. **Check-in values and notes are never logged**; training
logs only user id, stage and duration.

### Time and timezones (`app/core/clock.py`)

- `local_date(tz, now)` converts UTC "now" into the user's local calendar date. Every "today",
  backfill window, forecast date and nightly-job hour uses it.
- `is_valid_timezone` validates IANA names via `zoneinfo`. `tzdata` is a dependency so this works
  in slim containers and on Windows.

---

## 7. Authentication and security

### Passwords

- Hashed with **Argon2id** via `argon2-cffi`'s `PasswordHasher` defaults (memory 64 MiB,
  3 iterations, parallelism 4, random salt per hash). The hash string embeds its own parameters.
- Verification failures of any kind (mismatch, malformed hash) return "not authenticated"
  without leaking which.
- Passwords: 8–128 characters. Emails are validated (`email-validator`) and lowercased.

### Tokens (`app/core/security.py`)

- JWT, HS256, signed with `JWT_SECRET` (min 16 chars; a long random value is required in
  production).
- Payload: `sub` (user id), `type` (`access` | `refresh`), `iat`, `exp`, `jti` (random), `ver`
  (the user's `token_version` at issue time).
- **Access token**: 15 minutes, returned in the JSON body, kept **in browser memory only**
  (never localStorage), sent as `Authorization: Bearer …`.
- **Refresh token**: 30 days, set as an **httpOnly** cookie `digibuddy_refresh` with
  `path=/api/v1/auth`, `SameSite=Lax`, `Secure` when `COOKIE_SECURE=true`. JavaScript cannot
  read it, and the browser sends it only to auth endpoints.
- A token is rejected if its `type` is wrong (a refresh token cannot be used as an access token),
  its signature or expiry is invalid, or its `ver` differs from the user's current
  `token_version`.
- **Logout** increments `token_version`, which revokes every access and refresh token ever
  issued to that user, on every device, and clears the cookie.

### Rate limiting (`app/core/rate_limit.py`)

- In-memory sliding window of 60 seconds, keyed by `(client IP, path)`.
- Signup and login: **10 requests/minute** (`AUTH_RATE_LIMIT_PER_MINUTE`).
- Refresh: **120/minute** (`REFRESH_RATE_LIMIT_PER_MINUTE`), because it runs on every page load.
- Exceeding a limit returns HTTP 429 "Too many attempts. Please wait a minute and try again."
- Behind the Next.js proxy every request comes from the proxy's IP, so the limiter uses the
  first `X-Forwarded-For` hop when `TRUST_FORWARDED_FOR=true` (default; only safe when the API is
  reachable solely through the proxy).
- In-memory means per-process. Running several API workers needs a shared store (e.g. Redis).

### Authorization

- Every endpoint except `signup`, `login`, `refresh`, `logout` and `health` requires a valid
  access token (`/meta` included).
- Every service query filters by the caller's `user_id`. Another user's resources return 404, as
  if they did not exist. Custom-metric ids in a check-in must belong to the caller.
  `test_user_cannot_touch_another_users_data` covers all of this.

---

## 8. API reference

All paths are under `/api/v1`. Every request and response body is a Pydantic model, so the
OpenAPI schema is exact. Validation errors return 422 with FastAPI's standard error list; the
frontend shows the first message.

### Auth

| Method & path | Auth | Behaviour |
|---|---|---|
| `POST /auth/signup` | none, 10/min | Body `{email, password(8–128), display_name(1–80), timezone(IANA)}`. 201 + `{access_token, token_type, expires_in, user}` + refresh cookie. 409 if the email exists. 422 on invalid timezone or short password. |
| `POST /auth/login` | none, 10/min | Body `{email, password}`. 200 + tokens, or 401 "Email or password is not right." |
| `POST /auth/refresh` | refresh cookie, 120/min | 200 + new access token and a rotated refresh cookie, or 401. |
| `POST /auth/logout` | refresh cookie | Revokes all tokens (token_version += 1) and clears the cookie. Always 200. |

### Me

| Method & path | Behaviour |
|---|---|
| `GET /me` | Current user. |
| `PATCH /me` | Any of `display_name`, `timezone` (validated), `onboarding_completed: true`. |
| `GET /me/export` | All data as JSON: `exported_at`, `user`, `checkins` (with custom metric values and notes), `custom_metrics`, `predictions`, `model_versions` (without artifact paths). |
| `GET /me/export?format=csv` | Check-ins as CSV (`date, mood, energy, stress, anxiety, focus, <optional fields>, tags (; separated), notes`), as a download. |
| `DELETE /me` | 204. Hard-deletes every row of the user in every table **and** their model-artifact folder; clears the cookie. |

### Check-ins

| Method & path | Behaviour |
|---|---|
| `POST /checkins` | Create or replace (upsert) the check-in for `date` (default: today in the user's timezone). 201 when created, 200 when replaced. Response: `{checkin, scored_prediction, forecast_tomorrow, support}`. See §9. |
| `GET /checkins?from=&to=` | The user's check-ins in a date range, ascending. |
| `GET /checkins/{date}` | One day, or 404. |
| `PATCH /checkins/{date}` | Partial update of an existing day (any date). Core feelings cannot be set to null; `tags: null` becomes `[]`. Re-scores that day's forecast; if the day is today, regenerates tomorrow's forecast. |
| `DELETE /checkins/{date}` | 204, or 404. Clears the actuals/errors on that day's forecast. |

### Custom metrics (trackers)

`GET /metrics`, `POST /metrics` (`{name, min, max, unit}`, max > min, 409 on duplicate name),
`PATCH /metrics/{id}`, `DELETE /metrics/{id}` (cascades its values). Another user's metric → 404.

### Predictions

| Method & path | Behaviour |
|---|---|
| `GET /predictions/tomorrow` | If fewer than 7 logged days (through today): `{status: "collecting", days_logged, days_needed: 7 − n, support}`. Otherwise `{status: "ready", days_logged, days_needed: 0, forecast, support}`. Uses the stored forecast for tomorrow if one exists, otherwise generates it. |
| `GET /predictions/history?from=&to=` | Past forecasts (newest first) with actuals and errors per target. |

A forecast object: `{target_date, stage, days_since_last_log, created_at, mood, energy, stress}`,
each target `{predicted, lower, upper, actual, abs_error, model_type, factors[]}`, each factor
`{feature, label, note, direction: "up"|"down", contribution}`.

### Twin, insights, meta

| Method & path | Behaviour |
|---|---|
| `GET /twin` | Stage and name, days logged, days to next stage, last training time, `in_tune_pct`, active model per target (type, trained_at, backtest MAE, naive MAE, backtest coverage), accuracy per target (§10.16) and an accuracy time series. |
| `GET /insights` | `{items, days_logged, message}`. If there are no insights: "Keep checking in. Patterns start to show after about N more days." (N = 22 − days logged), or "No clear patterns yet. That's okay: your days may simply be varied." |
| `GET /health` | `{"status": "ok"}`, public. |
| `GET /meta` | `{name, version, disclaimer, support_regions}`. The disclaimer states DigiBuddy is not a medical device. |

---

## 9. Check-in rules

- **Local dates.** "Today" is computed in the user's timezone. A check-in at 23:30 in Singapore
  lands on that local date; at 00:30 it lands on the next (tested).
- **No future dates** ("You can't check in for a future day.").
- **Backfill window:** creating a check-in is allowed for today and the **3 previous days**.
  Older days can still be *edited* via PATCH if they exist.
- **Upsert:** posting the same date again replaces the values (200 instead of 201).
- On every successful create, in this order:
  1. **Score**: if a forecast exists for that date, fill `actual` and `abs_error` for each target.
  2. **Forecast**: generate (or refresh) the forecast for *tomorrow* (local) using the
     **currently active models**. There is no retraining on the request path, except a one-off
     first training when a user has just reached 7 logged days and has no model yet.
  3. **Support**: evaluate the support rules (§12) over the last 3 days and tomorrow's forecast.
- Forecasts are never overwritten after they have been scored, and no forecast is created for a
  day that is already logged. This keeps the accuracy record honest: a forecast can't be made
  after the answer is known.

---

## 10. The prediction engine (ML)

Code: `backend/app/ml/` (pure computation) plus `backend/app/services/twin.py` (persistence and
orchestration).

### 10.1 Problem framing

- **Targets:** next-day `mood`, `energy` and `stress`, each on 1–10. Anxiety and focus are
  inputs only.
- **Origin day `t`:** a forecast for day `t + 1` may use only information available by the end of
  day `t`.
- **Output per target:** point forecast, 80% prediction interval, top 3 contributing factors.
- **One model per user per target.** No data is pooled across users; every twin learns only
  from its own person.

### 10.2 Data preparation (`ml/data.py`)

`records_to_daily(records, through)` turns check-ins into a **calendar-indexed daily DataFrame**:

- one row per calendar day from the first logged day to `through` (inclusive);
- `logged` is True on days with a check-in; skipped days are rows of NaN, so the calendar has no
  holes and rolling windows are true calendar windows;
- columns: the 5 core feelings, the 10 optional numeric fields, `tags` (list, lowercased), and
  one `cm_<metric_id>` column per custom tracker;
- **notes are dropped here** and never enter the ML pipeline.

`extend_to(daily, date)` adds unlogged rows up to a later date, used when forecasting from a day
the user hasn't logged.

### 10.3 Stages (`ml/schema.py`)

Stages count **distinct logged days**, not calendar days since signup:

| Stage | Logged days | Name | Candidate models |
|---|---|---|---|
| 0 | 0–6 | collecting | none: show progress toward 7 |
| 1 | 7–20 | baseline | baseline |
| 2 | 21–59 | personal_linear | baseline, ridge |
| 3 | 60+ | personal_adaptive | baseline, ridge, gbm |

`naive` (persistence) is always evaluated as the floor in every stage.

### 10.4 Feature engineering (`ml/features.py`)

Each row is indexed by origin day `t` and contains only what was known at the end of `t`.

**Total features = 92 + 2 × (top tags, ≤10) + 2 × (eligible custom trackers).** The demo user
has 6 frequent tags and no eligible tracker: 104 features.

| Group | Features | Count | Definition |
|---|---|---|---|
| Recency | `days_since_last_log` | 1 | days between `t` and the most recent logged day ≤ `t` |
| Lags | `{feeling}_lag0/1/2` for the 5 feelings | 15 | the last, second-last and third-last **logged** values as of `t` (computed over the sequence of logged days, then forward-filled across gaps) |
| Rolling stats | `{field}_mean_3d`, `_std_3d`, `_mean_7d`, `_std_7d` for the 5 feelings + `sleep_hours`, `exercise_minutes`, `screen_time_hours`, `workload` | 36 | trailing **calendar** windows ending at `t`; NaNs (unlogged/missing) are skipped; mean needs ≥1 value, std needs ≥2 |
| Deltas | `{feeling}_delta_7d` | 5 | `lag0 − mean_7d`: today versus the user's week |
| Sleep debt | `sleep_debt_3d` | 1 | Σ over the last 3 calendar days of (personal median sleep − sleep), where the personal median is an **expanding** median up to that day (causal); missing sleep contributes 0 |
| Calendar (of the *target* day) | `target_dow_sin`, `target_dow_cos`, `target_is_weekend` | 3 | cyclical encoding `sin/cos(2π·dow/7)` of day `t+1`; weekend = Sat/Sun. Uses only the date. |
| Tags | `tag_<x>` and `tag_<x>_3d` for each of the user's top-10 tags | 2 per tag | tag present on day `t`; tag present in any of the last 3 days |
| Streaks | `low_mood_streak`, `exercise_streak` | 2 | consecutive logged days with mood ≤ 4 ending at the last log; consecutive calendar days with exercise > 0 ending at `t` |
| Same-day optional values | the 10 optional fields | 10 | raw value on day `t` (NaN if missing) |
| Missingness indicators | `missing_<field>` | 10 | 1 if that field is missing on day `t` (including unlogged days) |
| Custom trackers | `cm_<id>`, `missing_cm_<id>` | 2 per tracker | only trackers with ≥14 non-null values |
| Baseline ingredients | `base_ewma_{t}`, `base_mean_{t}`, `base_dowoff_{t}` for mood, energy, stress | 9 | see §10.6.2; also available to ridge and gbm as features |

**The FeatureSpec.** The two data-dependent column choices (which tags, which trackers) are fixed
in a `FeatureSpec`, fitted on the training data (top 10 tags by number of days used, trackers
with ≥14 values). The spec is saved inside the model artifact, so forecasting builds exactly the
same columns the model was trained on.

**Missing values.** Ridge imputes missing values with the median of the training fold (in a
pipeline, so validation data never leaks into the medians) and also sees the explicit `missing_*`
indicators. Gradient boosting handles NaN natively. Columns that are entirely empty are dropped
for gradient boosting, because they break histogram binning and carry no signal.

### 10.5 No leakage, proven

Every operation is backward-looking: positive shifts, trailing windows, expanding statistics,
and calendar features computed from the date alone. Targets are built separately
(`make_targets` = value at `t+1`, NaN unless `t+1` was logged).

**Leakage test** (`test_no_feature_uses_future_data`): build features on the full 120-day
dataset, then rebuild them on data truncated at `t` (for `t` = day 20, 45, 59, 90). The feature
row for `t` must be identical in both cases (`assert_series_equal`). A companion test
(`test_leakage_check_would_catch_a_leaky_feature`) confirms the check would catch a feature
that looks one day ahead.

**Training rows:** an origin day `t` is used for training only if day `t+1` was logged (the
target is known) and `days_since_last_log ≤ 3` at `t` (the information isn't stale).

### 10.6 Models (`ml/models.py`)

All models share one interface: `fit(X, y, sample_weight)`, `predict(X)`, `explain(x_row)`.

#### 10.6.1 Naive persistence (`naive`)

Tomorrow equals the most recent logged value (`{target}_lag0`). It is the floor every model
must beat, and it becomes the active model when nothing beats it. "Never ship a model worse than
tomorrow = today" therefore always has something safe to ship.

#### 10.6.2 Baseline (`baseline`), stage 1

`prediction = EWMA level + day-of-week offset`

- **EWMA level** (`base_ewma`): exponentially weighted mean of the target over the logged days,
  with a **half-life of 3 days measured in calendar time** (pandas `ewm(halflife=3 days,
  times=dates)`), so a gap counts as elapsed time.
- **Day-of-week offset** (`base_dowoff`): for each weekday `d`, average the residuals
  `value − EWMA level before that day` over all logged days falling on `d`, using only days up to
  `t`. The offset for the target day's weekday is then **shrunk toward zero** as
  `mean_d × n_d / (n_d + 4)`, where `n_d` is the number of samples for that weekday. It is
  switched on only once **every weekday has ≥ 2 samples** (as the spec requires); before that the
  offset is 0.
  - *Why residuals and shrinkage:* the literal "weekday mean minus overall mean" is very noisy
    with 2 samples per weekday, and on a drifting level it is biased. In experiments it often
    made the baseline lose to naive persistence. Shrinkage fixes that while keeping the spec's
    behaviour.
- The baseline has no fitted parameters, so every one of its predictions is honestly
  out-of-sample.

#### 10.6.3 Ridge regression (`ridge`), stage 2+

Pipeline: `SimpleImputer(median, keep_empty_features=True)` → `StandardScaler` →
`Ridge(alpha)`, trained with **recency sample weights** (§10.8).

**Choosing alpha:** grid `{0.3, 1, 3, 10, 30, 100, 300, 1000}`, scored by **mean absolute error
under `TimeSeriesSplit`** with `n_splits = min(4, max(2, n // 8))`, using weighted fits.
With fewer than 12 rows, alpha = 100 (heavy shrinkage).

**During backtesting**, alpha is chosen **once**, using only the rows *before* the backtest
window, and reused in every fold. This prevents peeking and is about 5× faster than a nested
search per fold. The final model re-chooses alpha on all data.

#### 10.6.4 Gradient boosting (`gbm`), stage 3

- **LightGBM** when installed: `n_estimators=150, learning_rate=0.05, num_leaves=7,
  min_child_samples=max(5, n//12), subsample=0.8 (subsample_freq=1), colsample_bytree=0.7,
  reg_lambda=1.0, random_state=0, n_jobs=1`.
- **Fallback** (no LightGBM): scikit-learn `HistGradientBoostingRegressor(max_iter=150,
  learning_rate=0.05, max_leaf_nodes=7, min_samples_leaf=max(5, n//12),
  l2_regularization=1.0, random_state=0)`. The system works fully without LightGBM.
- Shallow trees, strong regularisation and row/column subsampling are deliberate: per-user
  datasets are small (60–200 rows).
- **Single-threaded** (`n_jobs=1`): on tiny datasets, thread start-up costs more than it saves.
  Measured: about 6 s per full training versus 30 s+ with all threads on 2 cores.

### 10.7 Staged candidates

Each training run evaluates, per target, the stage's candidates plus the currently active model
type (if any) plus naive.

### 10.8 Recency weighting

Training rows are weighted `w = 0.5 ^ (age_in_days / 60)`, where age is measured from the most
recent training row. A day two months old counts half as much as yesterday, so the twin adapts
as the user's life changes. The 60-day half-life is configurable (`RECENCY_HALF_LIFE_DAYS`).

### 10.9 Rolling-origin backtesting (`ml/evaluation.py`)

How the engine measures a model honestly on the user's own data:

- **Window size `N`:**
  - if any candidate must be fitted (ridge, gbm): `N = max(1, min(30, floor(0.25 × rows)))`, as
    the spec requires;
  - if all candidates are unfitted (naive and baseline only, e.g. stage 1):
    `N = min(30, rows)`. These models predict honestly on every row, so they can use the full
    window from day one.
- **Expanding window:** for each of the last `N` training rows `i` (origin `t_i`), fit the model
  on rows `0 … i−1` only (all target days ≤ `t_i`), with recency weights relative to that
  training set, then predict row `i`.
- If fewer than **10** rows precede a test row, the fitted model is not trained; the baseline's
  formula is used for that row instead.
- Predictions are clipped to 1–10. Naive persistence is evaluated on **exactly the same days**.
- Output: dates, predictions, actuals, naive predictions, residuals, MAE, naive MAE.

### 10.10 Prediction intervals: split conformal

- **Half-width** `q` = the `ceil((n + 1) × 0.8)`-th smallest absolute backtest residual
  (finite-sample split-conformal quantile for 80% coverage).
- At least **5 residuals** are required; otherwise `q = 1.5`. `q` is never below **0.5**.
- The interval is `[pred − q, pred + q]`, clipped to [1, 10] and rounded to 1 decimal.
- **Coverage tracking:** `sequential_coverage` checks each backtest residual against a `q`
  calibrated only on *earlier* residuals, reporting the realistic hit rate (stored as
  `backtest_coverage`). Live coverage is also tracked from scored forecasts (§10.16).
- **Gaps widen the interval:** `q × (1 + 0.25 × max(0, days_since_last_log − 1))`. A forecast
  made 3 days after the last check-in is 50% wider.
- Test: average empirical coverage on synthetic users (60-day backtests, 3 users × 3 targets)
  lies between 70% and 90%.

### 10.11 Model selection and the promotion rule (`ml/training.py`)

The spec's rule: a model is promoted only if its backtest MAE beats **both** naive persistence
**and** the currently active model, measured on the same days. The engine implements it as
follows.

**What "beats" means** (`_beats(a, b)`):

1. At least **5 paired backtest days** (`MIN_EVIDENCE_DAYS`).
2. `MAE(a) < MAE(b) × (1 − 0.02)`: at least a **2% improvement** (`PROMOTION_MIN_IMPROVEMENT`),
   so noise doesn't cause churn.
3. **For fitted models (ridge, gbm) only:** a **one-sided paired t-test** on the daily absolute
   errors (`scipy.stats.ttest_rel(…, alternative="less")`) must give **p < 0.05**. Ridge and
   gradient boosting can overfit or win by luck on 10–30 days; the baseline has nothing to fit,
   so a plain MAE win is enough.

**Step 1: pick the challenger by walking up a complexity ladder.** Start at naive. For each of
baseline → ridge → gbm that is a candidate in this stage: it qualifies only if it *beats the
lowest-MAE model among naive and every simpler model evaluated so far*. The last qualifier is the
challenger. Simpler models win ties.

**Step 2: compare against the active model (incumbent):**

| Situation | Result | Recorded reason |
|---|---|---|
| No active model yet | challenger becomes active (or naive if nothing qualified) | `promoted: first model, beats naive persistence` / `fallback: nothing beat naive persistence yet` |
| Challenger is the same type as the active model | refit the active model on the new data | `refreshed: active model retrained on new data` |
| Challenger beats the active model (same test) | promote the challenger | `promoted: beats naive persistence and the active model` |
| Active model still has lower MAE than naive | keep it | `kept: no challenger clearly beat the active model` |
| Active model has fallen behind naive | replace it with the challenger (possibly naive) | `replaced: active model fell behind naive persistence` |

**Why the extra statistics were needed (from experiments on synthetic users):**

- Without significance testing, weekly retraining on a **pure-noise** user promoted ridge in
  most runs, purely by luck.
- With a very strict test (p < 0.01), **strong-signal** users stayed on naive until day 70+; one
  never got ridge in 120 days.
- The final design (complexity ladder, significance only for fitted models, p < 0.05,
  baseline judged on plain MAE) gave:
  - strong-signal users promoted to ridge between **day ~35 and ~63**;
  - in a single training on 10 pure-noise users at 120 days, ridge or gbm won **1 of 30**
    target decisions, about the 5% false-positive rate a p < 0.05 test predicts.

### 10.12 Final fit and artifacts

- The winner is refit on **all** training rows with recency weights (ridge re-chooses alpha).
- A `ModelVersion` row is written for every evaluated candidate. Only the winner gets
  `is_active = true` and an artifact.
- The **artifact** is a joblib file `MODEL_ARTIFACT_DIR/user_<id>/mv_<version_id>.joblib`
  containing `{target, model_type, model (fitted object), spec (FeatureSpec), halfwidth,
  feature_list}`. Artifacts never go in the database.
- Training runs in a worker thread. A full stage-3 training (3 targets × up to 4 models ×
  30-fold backtests) takes about **6 s** on 2 CPU cores with 120 days of data.

### 10.13 Forecasting (`ml/predict.py`, `services/twin.py`)

`forecast_next_day(daily, origin, artifacts)`:

1. Extend the calendar to `origin` (adding unlogged days if needed) and build features with the
   artifact's `FeatureSpec`.
2. Take the feature row for `origin`; read `days_since_last_log`.
3. **Gap rule:** if `days_since_last_log > 3`, every target **reverts to the stage-1 baseline**
   for this forecast. This prevents a model trained on fresh data from extrapolating from stale
   inputs.
4. Predict; if a model returns a non-finite value, fall back to the baseline.
5. Interval = conformal half-width × gap widening; clip to [1, 10]; round to 1 decimal.
6. Store the naive value (`lag0`) alongside, for fair accuracy comparison later.
7. Explain (§10.14).

`generate_prediction(user, origin)` (service):

- does nothing in stage 0;
- never overwrites a forecast that has already been scored;
- never creates a forecast for a day that is already logged;
- if the user has no active model yet (just reached 7 days), runs one training first;
- upserts the `predictions` row with all three targets, the model version ids, model types and
  factors.

### 10.14 Explainability: "what's shaping tomorrow"

Each forecast lists the top 3 factors per target, ranked by absolute contribution, as
`{feature, label, note, direction, contribution}`.

| Model | How contributions are computed |
|---|---|
| ridge | `coefficient × standardized feature value` (after imputation and scaling): how far this input pushes the forecast from an average day |
| gbm (LightGBM) | **SHAP values** via LightGBM's built-in `predict(pred_contrib=True)` (exact tree SHAP; bias term dropped) |
| gbm (sklearn fallback) | perturbation: `prediction − prediction with this feature set to its training median`, for every feature |
| baseline | two factors: "recent trend" (`EWMA − long-run mean`) and "day of week" (the shrunk weekday offset) |
| naive | one factor: today's value versus the 7-day mean |

**Merging:** features that map to the same human label (e.g. `target_dow_sin` and
`target_dow_cos` → "Day of the week") are summed before ranking, so the top 3 are three
distinct reasons.

**Labels** (`ml/feature_labels.py`, the single place raw names are translated): each feature
gets a sentence-case `label` (e.g. `sleep_debt_3d` → "Short on sleep over the last 3 days") and
a short lowercase `note` used on the sticky notes (e.g. "short on sleep"). Pattern rules cover
lags ("Yesterday's mood"), rolling means and stds ("Hours of sleep over the last 3 days",
"How much your stress has varied over 7 days"), missing indicators ("No entry for your sleep
today"), tags ("'exam' in the last 3 days"), baseline parts and custom trackers (by their
names).

### 10.15 The learning loop

```
evening, day t:   user logs day t
                  ├─ score the stored forecast for day t (actual, abs error)
                  └─ forecast day t+1 with the ACTIVE models (no retraining)
03:00 local, t+1: nightly job (if any check-in changed since the last training)
                  ├─ retrain on data through day t: backtest, select, promote or keep
                  └─ refresh the forecast for day t+1 with the (possibly new) models
evening, t+1:     user logs day t+1 → scored against that forecast …
```

### 10.16 Accuracy tracking (`services/accuracy.py`, `GET /twin`)

Computed from scored forecasts, per target:

| Metric | Definition |
|---|---|
| `mae_7d`, `mae_30d` | mean absolute error over forecasts whose target date is within the last 7 / 30 days |
| `naive_mae_30d` | the same for the stored naive values |
| `within_1_rate` | share of the last 30 days' forecasts within 1 point of the actual |
| `improvement_vs_naive_pct` | `100 × (1 − mae_30d / naive_mae_30d)` |
| `interval_coverage` | share of the last 30 days' actuals inside the 80% range |
| `n_scored` | all scored forecasts |

- **`in_tune_pct`** ("78% in tune with you") = the average `within_1_rate` across the three
  targets × 100.
- **Series** for the chart: for each scored day, that day's three absolute errors plus a rolling
  7-forecast average of the twin's error and of the naive error (pooled across targets).

**Demo-account results** (synthetic strong-signal user, 120 days):

- over the last 30 days the twin beat "tomorrow = today" by **34%** (mood), **54%** (energy) and
  **52%** (stress);
- the rolling 7-day error fell from **~4.5 points** at the first forecasts to **~1.2**.

### 10.17 Validation summary (all automated)

| Property | Test |
|---|---|
| No feature uses future data | `test_no_feature_uses_future_data` |
| Correct stage at 0/6/7/20/21/59/60/120 days; stages count logged days, not calendar days | `test_stage_thresholds`, `test_stage_counts_distinct_logged_days_not_calendar_days` |
| A model worse than naive is never activated (on a random walk where persistence is optimal) | `test_model_worse_than_naive_is_never_activated` |
| A switch happens only with a clear win over both references | `test_active_model_kept_unless_challenger_clearly_wins` |
| Strong-signal user: stage 2 (ridge, day 66) and stage 3 (ridge/gbm, day 120) models beat naive MAE by ≥15% for **every** target, on 30-day backtests | `test_strong_signal_models_beat_naive_by_15_percent` |
| Pure-noise users (5 seeds): neither ridge nor gbm is promoted over baseline | `test_pure_noise_user_is_not_promoted_beyond_baseline` |
| Conformal quantile correctness | `test_conformal_halfwidth_basics` |
| Empirical 80% coverage between 70% and 90% | `test_interval_coverage_close_to_80_percent` |
| Valid forecasts with skipped days and 50% missing fields | `test_predictions_valid_with_skipped_days_and_nulls` |
| Gaps widen the interval; >3 days reverts to baseline | `test_gap_widens_interval_and_long_gap_reverts_to_baseline` |
| Notes never enter the ML frame | `test_notes_are_not_part_of_ml_frame` |

### 10.18 ML limitations (honest)

- Backtest windows are small (25% of history, max 30 days), so model choices carry uncertainty.
  The significance test reduces but cannot remove lucky promotions (~5% per decision on pure
  noise). Because the spec keeps an active model unless something beats it, a lucky promotion
  can persist for a while; on such users ridge then performs about as well as the baseline, so
  the cost is small.
- Per-user data only: no cold-start help from other users (a deliberate privacy choice).
- Factors are associations learned from the user's data, not causes, and ridge contributions
  can split credit between correlated features.
- Integer ratings (1–10) limit how precise any forecast can be.

---

## 11. Insights engine

Code: `services/insights.py`, computed on request from the user's structured fields only.
All insights compare **day `t`** with **mood on day `t + 1`**, using only pairs where both days
were logged.

1. **Factor correlations** (each optional field plus custom trackers):
   - Spearman rank correlation between the factor and next-day mood;
   - reported only if **n ≥ 21** pairs, the factor has ≥3 distinct values, and **|r| ≥ 0.3**;
   - phrased by splitting days at the user's median of that factor and comparing average
     next-day mood above versus at-or-below it (each side needs ≥3 days): *"On days after more
     sleep than your usual (above 7.1 hours), your next-day mood has averaged 2.9 points higher
     (n = 32 vs 38 days)."*
   - sorted by |r|.
2. **Weekdays:** once **every weekday has ≥3 check-ins**, the best and worst weekday by average
   mood versus the overall average: *"Sundays tend to be your brightest days: mood averages
   7.6 compared with 6.1 overall (n = 15 Sundays)."*
3. **Tags:** every distinct tag (suggested or custom) with **≥5** tagged days and ≥5 untagged
   days; next-day mood after tagged days versus after other days; shown if the difference is
   **≥0.3** points; sorted by size: *"The day after a day tagged 'exam', your mood has averaged
   3.7 points lower than after other days (n = 6 vs 75 days)."*

Rules: always phrased as observations, never causes; always with sample sizes; tags are matched
exactly (after lowercasing), so "exam" and "exams" are different tags; notes are never read.

---

## 12. Wellbeing safety

Code: `services/support.py`, `core/support_resources.py`.

**Triggers** (each produces a reason):

| Reason | Condition |
|---|---|
| `very_low_mood` | the check-in being evaluated has mood **≤ 2** |
| `low_mood_streak` | mood **≤ 3** on **3 consecutive calendar days** ending on that day (a skipped day breaks the streak) |
| `low_forecast` | the forecast for tomorrow predicts mood **≤ 3.0** |

When any reason applies, the API includes a `support` object with a gentle message ("Today
sounds really heavy. You don't have to carry it alone. …"), the reasons and region-specific
resources. It is returned on check-in creation and on `GET /predictions/tomorrow` (including
during the first 7 days). The Today page shows it **above** any forecast, so a forecast is never
the first thing seen after a very low check-in. The note is dismissible and uses no alarm
colours.

**Region** from the user's timezone: `Asia/Singapore` → SG, `Asia/Kolkata`/`Asia/Calcutta` →
IN, otherwise INTL.

| Region | Resources |
|---|---|
| SG | Samaritans of Singapore (SOS) 1767, 24h; IMH Mental Health Helpline 6389 2222, 24h |
| IN | Tele-MANAS 14416, 24h |
| INTL | Find A Helpline directory (findahelpline.com); local emergency services if in immediate danger |

Phone numbers are `tel:` links. The list is configurable in one file and must be verified by
the product team before launch.

**Not-a-medical-device statement:** shown in onboarding (with an explicit acknowledgement
checkbox), on the sign-in/sign-up pages, in Settings, and returned by `GET /meta`.

---

## 13. Privacy and the data lifecycle

- **Notes** are stored for the user only, never used for forecasts or insights (dropped in
  `records_to_daily`, tested).
- **Logs** contain ids, routes, status codes and timings, never values or notes.
- **Export:** full JSON of everything, or CSV of check-ins (`GET /me/export`).
- **Deletion:** `DELETE /me` removes the user's rows in all six tables and deletes their model
  artifact directory from disk. Tested: row counts go to zero for that user while another user's
  data is untouched, and the folder is gone.
- **Isolation:** no cross-user data use anywhere; every query is scoped to the user.
- **Sessions:** short-lived access token in memory; httpOnly refresh cookie; logout revokes
  everything.
- **Config by environment variables** (`.env.example` provided); no secrets in code.
- In the browser, only the theme choice is stored (localStorage). No check-in data is stored
  client-side.

---

## 14. Synthetic data generator

`backend/scripts/generate_synthetic.py` creates realistic users whose next-day feelings truly
depend on their inputs, so the models have something real to learn (and something to fail on
for the noise user).

**Daily inputs:**

| Field | Distribution |
|---|---|
| sleep_hours | 15% "short nights" N(5.0, 0.7), else N(7.3, 0.9); clipped 3–11 |
| sleep_quality | ≈ 1 + 0.7 × (sleep − 4) + noise, 1–5 |
| exercise | P(exercise) 45% weekdays / 35% weekends; minutes max(10, N(40, 15)) |
| outdoor_minutes | N(60 weekends / 25 weekdays, 20), ≥0 |
| screen_time_hours | N(5.5, 1.5), 0.5–14 |
| caffeine / alcohol | Poisson(1.6) / Poisson(1.5 weekends, 0.2 weekdays) |
| meals | N(3, 0.6), 0–5 |
| workload | N(3.6, 0.9) weekdays / N(2.0, 0.8) weekends, 1–5 |
| social | N(2.6, 1.0) weekdays / N(3.8, 0.9) weekends, 1–5 |
| tags | `gym` when exercising; `deadline` 12% of weekdays; `sick` 6%; `date` 25% of weekends; `travel` 5%; `exam` on weekdays during a 7-day window every 60 days |

**Next-day feelings** (driven by *yesterday's* inputs; `debt` = Σ over the previous 3 days of
(7 − sleep); `ex` = exercised yesterday; `b` = signal strength):

```
mood    = 6 + b·(0.6·(sleep−7) − 0.35·debt + 0.8·ex − 0.5·(workload−3) + 0.5·(social−3)
                 − 1.5·[sick] + 0.8·[date]) + weekly + e_mood
energy  = 6 + b·(0.7·(sleep−7) + 0.6·ex − 0.3·debt) + 0.5·weekly + e_energy
stress  = 5 + b·(0.9·(workload−3) − 0.3·(sleep−7) + 1.2·[exam or deadline]) − 0.5·weekly + e_stress
anxiety = 0.6·stress + 1.5 + N(0, 0.8)
focus   = 0.5·energy + 2.5 + N(0, 0.8)
weekly  = amp × (+0.6 on weekends, −0.5 on Mondays)
e_t     = φ·e_(t−1) + N(0, σ)        (AR(1) noise)
```

All feelings are rounded and clipped to 1–10.

| Profile | b (signal) | σ (noise) | φ (AR) | weekly amp |
|---|---|---|---|---|
| strong | 1.5 | 0.5 | 0.3 | 1.0 |
| weak | 0.5 | 1.0 | 0.4 | 0.5 |
| noise | 0 | 1.2 | n/a | 0 |

The **noise** profile is a *local-level* process: `level = 0.97·level + N(0, 0.3)`, observed as
`base + level + N(0, 1.2)`. Inputs have no effect at all. For this process exponential smoothing
is near-optimal, so a correct engine should *not* find anything better than the baseline. (With
plain i.i.d. noise, a heavily regularised ridge legitimately beats an EWMA by estimating the
long-run mean, which would make the "fail to beat the baseline" test wrong for the right
reasons.)

**Realism:** about 20% of each optional field is missing and about 10% of days are skipped (the
first 3 days are always logged).

---

## 15. Seeding the demo account

`python -m scripts.seed` (≈1 minute):

1. Deletes any existing `demo@digibuddy.app` (via the same hard-delete path as account
   deletion), then creates it (password `demo1234`, timezone `Asia/Singapore`, onboarding done)
   with a "Practice hours" tracker (0–8 h).
2. Generates 120 days for the **strong** profile (seed 7), ending **yesterday**, so the user can
   check in "today".
3. **Replays the app day by day, as it would have run live:**
   - each evening: insert the check-in (with a random 0–4 h practice value on 80% of days),
     score that day's forecast, forecast the next day with the active models (timestamped 21:00
     local);
   - on retraining nights: retrain at 03:00 local the next day and refresh the next-day
     forecast. Retraining runs **weekly and at every stage boundary** (7, 21, 60 logged days)
     instead of nightly, to keep seeding fast (`--retrain-every` changes the interval).
4. Result: a complete, honest prediction history (every forecast made before its day was
   logged), model-version history, accuracy that improves over time, and insights.

Options: `--all-profiles` also creates `weak@digibuddy.app` and `noise@digibuddy.app`;
`--create-tables` creates tables without Alembic (dev only); `--days N`.

---

## 16. Nightly retraining job

`app/jobs/retrain.py`:

- APScheduler `AsyncIOScheduler` (UTC) runs `run_nightly()` at **minute 0 of every hour**.
- It selects users whose **local hour is 3** (`NIGHTLY_HOUR_LOCAL`), so each user is processed
  once per local night, including half-hour timezones like India's (03:30 local).
- For each such user: retrain only if **any check-in changed since the newest
  `data_updated_at`** recorded on their model versions. This is a data watermark, not a clock
  comparison, so it is robust to clock skew.
- Retrain on data **through yesterday**, then refresh the forecast for **today** (origin
  yesterday), unless today is already logged or its forecast already scored.
- Per-user failures are logged and do not stop the run.
- `run_nightly` is a plain async function, so it can be moved to a real queue (Celery, RQ, a
  cron container) without changes. The scheduler runs in-process; with several API workers,
  enable it in exactly one.

---

## 17. Frontend

### 17.1 Stack and structure

Next.js 15 App Router with React 19 and TypeScript in strict mode (`noUncheckedIndexedAccess`).
All pages are client components: data comes from the API with an in-memory token, so server
rendering would add nothing. `next.config.mjs`: `output: "standalone"` (small Docker image) and a
rewrite `/api/v1/:path* → ${API_INTERNAL_URL}/api/v1/:path*` (baked in at build time;
`http://api:8000` in Docker, `http://localhost:8000` in dev).

### 17.2 API types (kept in sync with the backend)

`backend/scripts/export_openapi.py` → `backend/openapi.json` → `npm run gen:api`
(openapi-typescript) → `src/types/openapi.d.ts`. `src/types/api.ts` re-exports friendly names
(`CheckIn`, `Forecast`, `Twin`, …). No API shape is hand-written anywhere else.

### 17.3 API client (`lib/api.ts`)

- `apiFetch(path, {method, body, auth})`: JSON in and out, `credentials: "include"`, bearer token
  from memory.
- **On 401 it refreshes once** (`POST /auth/refresh`) and retries the request.
  `refreshSession()` de-duplicates concurrent refreshes.
- Errors become `ApiError(status, message)`, with the message taken from FastAPI's `detail`
  (string or first validation message).

### 17.4 Auth state (`lib/auth.tsx`)

`AuthProvider` tries a silent refresh on load (`status: loading → authenticated | anonymous`),
exposes `login`, `signup`, `logout`, `setUser`, and clears the React Query cache on sign-out.

- **`AppShell`** (signed-in pages) redirects anonymous visitors to
  `/login?next=<path>` and users who haven't finished onboarding to `/onboarding`.
- **`PublicShell`** (sign-in/sign-up) redirects visitors who *arrive* already signed in. Someone
  who signs in on the page is moved on by the form itself, to avoid two racing navigations.
- `next` redirects are checked (must start with `/`, not `//`).

### 17.5 Data layer (`lib/hooks/index.ts`)

All fetching goes through React Query hooks; pages never call `fetch`:

- **Reads:** `useTomorrow`, `usePredictionHistory(from, to)`, `useCheckins(from, to)`,
  `useCheckin(date)` (404 → `null`), `useTwin`, `useInsights`, `useMetrics`, `useMeta`.
  Queries are enabled only when authenticated.
- **Writes:** `useCreateCheckin`, `useUpdateCheckin`, `useDeleteCheckin`, `useUpdateMe`,
  `useCreateMetric`, `useUpdateMetric`, `useDeleteMetric`, `useExport` (downloads JSON/CSV as a
  file), `useDeleteAccount`.
- **Cache policy:** `staleTime` 30 s, no refetch on window focus, no retries on 4xx (up to 2 on
  other errors). Saving or deleting a check-in invalidates check-ins, predictions, twin and
  insights.

### 17.6 Forms and validation (`lib/schemas.ts`)

react-hook-form + zod, mirroring the API's limits so errors show before submitting:

- check-in: the five feelings are required integers 1–10 ("Pick a number from 1 to 10.");
  optional numbers accept empty input (→ `null`) and are range- and integer-checked with friendly
  messages; ≤20 tags; notes ≤2,000; tracker values numeric;
- login, signup (name, valid email, 8+ chars), tracker (`max > min`), profile.

The check-in form spans **both book pages**: feelings on page 1, optional details on page 2. It
is one form (submit buttons use `form="checkin-form"`). New days POST; existing days PATCH.

### 17.7 Pages

| Route | Left page | Right page |
|---|---|---|
| `/login`, `/signup` | the "endpaper": what DigiBuddy is, quokka, polaroid, disclaimer | the form (opened first on phones) |
| `/onboarding` | 3 steps, each a page turn: (1) how it works, (2) the promise (disclaimer from `/meta`, acknowledgement required), (3) timezone (prefilled from the browser) and optional trackers | ruled blank page |
| `/` Today | support note (if any) first; greeting; if not logged: quokka + quick check-in (5 feelings) + link to full details; if logged: summary tiles + "I guessed X, it was Y" | tomorrow's forecast (3 weather tiles with ranges + reasons) and "N% in tune" note, or progress slots toward the first forecast |
| `/checkin/[date]` | "How are you feeling?": the five feeling scales | optional details in collapsible sections (sleep, activity, lifestyle, people and load, tags, trackers, private notes); save / remove. Saving turns to a "Page saved" page with the comparison and any support note. Days outside the backfill window explain why they're closed. |
| `/history` | "Guessed vs. felt" chart for the last 30 days, switchable mood/energy/stress | day-by-day list (14 days, "show older" +30) with values, weather icons, the guess, tags, edit links |
| `/twin` | chapter (stage), "in tune" ring meter, pages written, days to next chapter, last training | accuracy-over-time chart (twin vs. "same as today"), per-target table (off by 7/30-day, within 1 point, better than same-as-today, inside the range), plain-language model descriptions |
| `/insights` | "The day after…" correlation notes | weekday polaroids, tag notes |
| `/settings` | profile, reading light (theme), trackers, sign out | export (JSON/CSV), delete account (type "delete" to confirm), about/disclaimer |

Every page has loading, empty and error states (with retry).

---

## 18. Design system implementation

The UI implements the **DigiBuddy Storybook** design system: each screen is a page of a
hand-painted journal on a wooden desk, with a painted quokka mascot.

- **Tokens:** `frontend/design/tokens.json` (the design system export) → `npm run tokens`
  (`scripts/build-tokens.mjs`) → `src/styles/tokens.css`: CSS custom properties for 30 colour
  tokens in two themes (Daylight, Lamplight), shadows (paper, book, stamp), spacing (4–48 px),
  radii (6/12/18/pill), durations (flip 700 ms, press 90 ms), font families and type styles
  (`.t-title-xl`, `.t-number-xl`, `.t-note`, …).
- **Fonts:** Grandstander (display), Literata (body), Gaegu (handwriting, the quokka's voice),
  loaded with `next/font/google`.
- **Colour semantics:** marigold is the single primary action per page; blossom/petal only for
  care and support; sky for anything predicted; sprout for learning and accuracy; brick only for
  form errors, never for low mood.
- **The feeling scale:** values map to five weather tokens (1–2 Rainy, 3–4 Drizzly, 5–6 Cloudy,
  7–8 Sunny, 9–10 Golden). Low values are a calm slate blue, never red. Stress and worry (higher
  is harder) use neutral sky so colour never implies good or bad.
- **Voice:** forecasts are weather, not verdicts ("Sunny, likely between 5.2 and 7.0"). The
  quokka speaks in first person ("I guessed 6.8, it was 7. Nearly spot on!"). The app praises
  the twin's learning, never the user's mood.
- **Components** (`components/ui/`): `Button`/`ButtonLink` (marigold rubber stamp that presses
  3 px), `TextField`/`TextArea` (ruled)/`SelectField`, `FeelingScale` (native radio group),
  `FactorSlot`, `TagChip`, `Toggle` (switch role), `Section` (`<details>`), `StickyNote`,
  `Polaroid`, `Tape`, `ReasonNote`, `SupportNote`, `Quokka`, `ForecastCard`, `CompareNote`,
  `PredictionChart`, `AccuracyChart`, `TwinMeter`, `Icon` (34 custom 24 px, 2 px-stroke icons),
  loading/empty/error notes, `PageTitle`.
- **Charts** are SVG with tokens: forecast line and range band in sky, actual values as
  weather-coloured dots, handwritten annotation of the latest comparison. Each chart also renders
  its data as a table (in a "Show as a table" disclosure) for screen readers and checking.
- **Themes:** Daylight (default), Lamplight, or "match my device"; stored per browser; applied
  before first paint by an inline script.
- **Accessibility:** semantic landmarks, labelled page sections, native radio groups for
  feelings, `role="switch"` toggles, `aria-current` tabs, `aria-live` counters and status
  messages, a 2 px focus ring with 2 px offset everywhere, decorative icons hidden from screen
  readers, all motion disabled under `prefers-reduced-motion`.
- **Layout:** wider than 720 px shows a two-page spread with chapter tabs and side arrow tabs;
  narrower shows one page at a time with a pager ("Page 1 of 2"). 16 px side gutters, no
  horizontal scroll.

---

## 19. Animation system (page turns)

Goal: no cuts anywhere. Every change of page is a page turn, and everything else glides.

### 19.1 Architecture (`components/book/`)

- **`BookFrame`** lives in the root layout (inside the providers). The desk, brand, chapter tabs,
  arrow tabs, book, page-turn layer, ribbon and phone pager **never unmount** across routes.
- **`Spread`** is what each page renders: its left and right content become the book's two pages.
  Wide screens always show two pages (a blank ruled page when a screen has only one), so the
  book never changes width.
- **`useBook().turn(direction, update)`** turns the page around an in-page state change
  (onboarding steps, "Page saved", phone page turns).

### 19.2 How a route-change turn works

1. When React is about to remove the old `Spread`, its layout-effect cleanup runs **before** the
   DOM is detached and **snapshots** the visible pages: deep clones (preserving typed input
   values, checked radios, open sections; ids removed; `inert` and `aria-hidden`), their
   positions, the book height and the scroll position.
2. The new `Spread`'s mount layout effect runs **before the browser paints**:
   1. It **pins the book** at the old height first, before reading any layout. If the document
      got shorter for even one layout, the browser would clamp the scroll position and the page
      would jump.
   2. It lays the static snapshot over the book (the **hold**), so the user still sees the old
      page.
3. **Hold:** wait (min 60 ms, max 1,000 ms) until:
   - the new page has its data (auth resolved and React Query has nothing fetching), and
   - the window has smoothly scrolled so the top of the book is in view (needed after using the
     phone pager at the bottom).
4. **Turn:** snapshot the live new pages, then animate:
   - **Wide, forward:** the right page lifts and turns over to the left around the spine. Front
     face = old right page, back face = new left page. The old left page lies underneath until
     covered.
   - **Wide, back:** mirror image (the left page turns over to the right).
   - **Phone, forward:** the page lifts off to the left, revealing the next page; its back is
     plain paper.
   - **Phone, back:** the previous page turns back in from the left over the current one.
   - **Same page re-rendered** (e.g. the loading state replaced by content): a 320 ms
     cross-fade.
5. **Settle:** a 160 ms fade from the last frame into the live page, which absorbs any final data
   change, then the overlay is removed.

### 19.3 Direction

`routes.ts` defines the reading order: sign-up → sign-in → onboarding → Today → Check-in →
History → Your twin → Insights → Settings (unknown pages at the end). Moving later turns
**forward**, earlier turns **back**; check-in pages for different days turn by date; the same
route cross-fades. Tested in `routes.test.ts`.

### 19.4 Height changes

- **Next page taller:** the book grows *during* the turn, in step with it, so new content is
  never clipped.
- **Next page shorter:** the book first **compresses** to the new height with the current page
  still in it (duration `300 + 0.4 × drop px`, max 720 ms), and only then turns at the new size.
- Old pages lying in the book are clipped to the book's height as it changes, so nothing hangs
  below the book.

### 19.5 Rendering details

- WAAPI (`element.animate`) only, so nothing re-renders in React during a turn and a form
  spanning both pages keeps its state.
- Perspective 2,400 px; leaf with `preserve-3d` and back faces hidden; easing
  `cubic-bezier(0.45, 0.05, 0.2, 1)`; duration from the design token `--flip-duration` (700 ms).
- Curl shading on each face (darkest at the spine, peaking at mid-turn) and a cast shadow on the
  page being revealed.
- The page-turn layer sits between the book and the ribbon bookmark, so the ribbon stays on top.
- Clones never run their own CSS animations or transitions (frozen picture).
- Starting a new transition cancels any running one cleanly.

### 19.6 Everything else that moves

| Element | Motion |
|---|---|
| First load | the book rises in (640 ms) |
| Content as it loads | "inks in": fade + 6 px rise, 380 ms, staggered 40 ms per item |
| Chapter tabs | slide up in (420 ms) when signed in, down out (320 ms) when signed out; the current tab lifts smoothly when you change chapter |
| Arrow tabs | scale in/out at the book's edges |
| Collapsible sections | animate height open/closed (`::details-content` + `interpolate-size`) and fade the content in |
| Support note | folds away (grid-row collapse + fade) when closed |
| Feeling slots, chips, buttons, inputs | smooth press, select and focus transitions |
| Theme switch | every colour fades over 420 ms instead of snapping |

**Reduced motion:** all of the above is disabled; pages change instantly.

### 19.7 How it was verified

Frame-by-frame screen recordings (Chrome DevTools screencast) of sign-up, onboarding forward
and back, sign-in, tab and arrow navigation, phone page turns, check-in save, sign-out and theme
switch, on desktop and phone. Consecutive-frame pixel differences were checked for single-frame
jumps. Contact sheets were reviewed visually. Issues found and fixed this way:

- a 160 px scroll jump at the start of phone page turns;
- old pages hanging below a shrinking book;
- the book shrinking mid-turn;
- a double turn after sign-up;
- the ribbon disappearing during turns.

---

## 20. Testing

**Backend: 53 tests (pytest), all passing.** `ruff` and strict `mypy` are clean. Tests run
against SQLite with an injectable clock; the ML tests use synthetic users.

- **API** (`test_api.py`): health is public; every protected route returns 401 without a token;
  signup/login/refresh/logout including token revocation; bad timezone and short password; rate
  limit (3 allowed then 429); PATCH /me and /meta; check-in CRUD, upsert, future and backfill
  rules, ranges, required fields, notes length; custom trackers (duplicates, ranges, ownership);
  the full collecting → first forecast → scoring flow and the twin endpoint; insights empty
  message; JSON and CSV export.
- **ML** (`test_ml.py`): leakage (2 tests), stage thresholds (8 cases), logged versus calendar
  days (6 cases), the promotion rule (2), strong-signal recovery ≥15% (2 stages), pure-noise
  non-promotion (5 seeds), the conformal quantile, interval coverage 70–90%, gaps and missing
  values, gap widening and reversion.
- **Safety and privacy** (`test_safety_privacy.py`): timezone date logic and the 23:30 Singapore
  check-in; cross-user authorization; tampered and wrong-type tokens; every support trigger
  (positive and negative cases); region mapping (SG, IN); support in the check-in response and
  during collecting; account deletion removes rows and artifacts but not other users' data; the
  nightly job runs only at 03:00 local and only with new data; insights are observations with
  sample sizes and need enough data; notes never enter the ML frame.

**Frontend: 24 tests (vitest + Testing Library), all passing.** ESLint and `tsc` are clean.

- API client: bearer header, refresh-and-retry on 401, error messages.
- Hooks: waits for the session, no fetching while signed out, 404 → null, saving invalidates
  predictions, twin and check-ins.
- Check-in form: an error per missing feeling and no submit; submits when complete; payload
  mapping (nulls, trackers).
- Schemas: required feelings, ranges, integer checks, conversions, signup, trackers.
- Utilities: timezone "today", date maths, weather mapping, stress never weather-coloured,
  forecast phrasing.
- Page-turn direction rules.

---

## 21. Tooling and CI

- **Backend:** `ruff check` and `ruff format --check` (line length 100; rules E, F, I, B, UP,
  SIM, RUF), `mypy --strict` with the Pydantic plugin, `pytest` (`-m "not slow"` skips the
  model-training tests).
- **Frontend:** `npm run lint` (ESLint flat config, `--max-warnings 0`), `npm run typecheck`,
  `npm test`, `npm run build`.
- **CI** (`.github/workflows/ci.yml`): on every push and PR, a backend job (Python 3.12: install,
  ruff, format check, mypy, pytest) and a frontend job (Node 22: npm ci, lint, typecheck, test,
  build).

---

## 22. Running and deployment

### Docker Compose (`docker-compose.yml`)

| Service | Image | Notes |
|---|---|---|
| `db` | postgres:16-alpine | volume `db-data`; health check `pg_isready` |
| `api` | `backend/Dockerfile` (python:3.12-slim + libgomp1 for LightGBM) | runs `alembic upgrade head` then uvicorn on 8000; volume `artifacts` at `/data/model_artifacts`; waits for a healthy db |
| `frontend` | `frontend/Dockerfile` (multi-stage node:22-alpine, Next standalone) | build arg `API_INTERNAL_URL=http://api:8000`; port 3000 |

- **Ports** are configurable: `WEB_PORT` (default 3000) and `API_PORT` (default 8000).
- **Data persists** in the volumes across restarts and rebuilds; `docker compose down -v`
  deletes it.
- **One-click scripts:** `start.bat` / `start.command` build and start everything, wait for the
  API health check, seed the demo account once (marker file `.seeded`) and open the browser.
  `stop.bat` / `stop.command` stop the containers and keep the data.
- **Manual:** `docker compose up --build -d`, then
  `docker compose exec api python -m scripts.seed`.
- **Updates:** `git pull`, then `docker compose up --build -d` (the Docker Desktop play button
  reuses old images).

### Local development

- **Backend:** venv, `pip install -r requirements-dev.txt`, `.env`, `alembic upgrade head`,
  `python -m scripts.seed`, `uvicorn app.main:app --reload`.
- **Frontend:** `npm install`, `npm run dev` (proxies `/api/v1` to `localhost:8000`).

### Production notes

Set a long random `JWT_SECRET`, `COOKIE_SECURE=true` (HTTPS), real `CORS_ORIGINS`, and keep
`TRUST_FORWARDED_FOR=true` only if the API is reachable solely through the frontend proxy. Use a
managed Postgres and persistent storage for artifacts. Run the scheduler in exactly one API
process. Verify the helpline list. Singapore and India hosting regions suit the target users and
data-residency expectations.

---

## 23. Configuration reference

All are environment variables (case-insensitive), read by `app/core/config.py`.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://digibuddy:digibuddy@localhost:5432/digibuddy` | database |
| `JWT_SECRET` | dev value | token signing key (≥16 chars) |
| `JWT_ALGORITHM` | HS256 | |
| `ACCESS_TOKEN_TTL_MINUTES` | 15 | |
| `REFRESH_TOKEN_TTL_DAYS` | 30 | |
| `COOKIE_SECURE` | false | true behind HTTPS |
| `COOKIE_SAMESITE` | lax | |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | |
| `AUTH_RATE_LIMIT_PER_MINUTE` | 10 | signup/login |
| `REFRESH_RATE_LIMIT_PER_MINUTE` | 120 | refresh |
| `TRUST_FORWARDED_FOR` | true | use X-Forwarded-For for rate limiting |
| `MODEL_ARTIFACT_DIR` | `./model_artifacts` | trained model files |
| `RECENCY_HALF_LIFE_DAYS` | 60 | training sample weights |
| `BASELINE_HALF_LIFE_DAYS` | 3 | EWMA |
| `BACKTEST_MAX_DAYS` | 30 | backtest window cap |
| `BACKTEST_FRACTION` | 0.25 | backtest share of history |
| `INTERVAL_COVERAGE` | 0.8 | prediction interval level |
| `PROMOTION_MIN_IMPROVEMENT` | 0.02 | required MAE improvement |
| `GAP_REVERT_DAYS` | 3 | stale-data cut-off for training rows and forecast reversion |
| `USE_LIGHTGBM` | true | prefer LightGBM when installed |
| `ENABLE_SCHEDULER` | true | nightly job in this process |
| `NIGHTLY_HOUR_LOCAL` | 3 | local hour for retraining |
| `DEFAULT_SUPPORT_REGION` | INTL | fallback region |
| `LOG_LEVEL` | INFO | |
| `APP_VERSION` | 0.1.0 | shown in /meta |
| Frontend `API_INTERNAL_URL` | `http://localhost:8000` (dev), `http://api:8000` (Docker) | proxy target, set at build time |
| Compose `WEB_PORT`, `API_PORT` | 3000, 8000 | host ports |

The significance level (p < 0.05), minimum evidence days (5), conformal minimums (5 residuals,
default 1.5, floor 0.5), gap widening (25% per extra day), top-tag count (10), tracker
eligibility (14 values) and weekday shrinkage (4) are constants in `app/ml`.

---

## 24. Known limitations and future work

- **No email verification or password reset:** both need an email service.
- **In-process rate limiter and scheduler:** fine for one API process; use Redis and a job
  queue to scale out.
- **Helpline numbers** must be verified by the product team before launch.
- **ML** (see §10.18): small backtest windows, occasional lucky promotions on noise users,
  association not causation, per-user cold start.
- **Seeding** retrains weekly (the live app retrains nightly).
- **Possible next steps:**
  - reminders and notifications;
  - pooled, privacy-preserving priors for faster cold starts;
  - multi-day forecasts;
  - richer custom-tracker insights;
  - wearable integrations (sleep, steps);
  - a hosted deployment with HTTPS and managed Postgres.
