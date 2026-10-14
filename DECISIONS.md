# Decisions

Choices made where the spec was ambiguous or where building it showed something the spec
didn't anticipate. Each entry: what we chose, and why.

## Scope

- **The frontend is styled with the DigiBuddy Storybook design system.** The spec asked
  for unstyled placeholders, but the design system was available at build time, so the
  `components/ui/` wrappers are real design-system components (tokens, type, spacing,
  shapes and copy from its README and `tokens.json`). Data flow lives in hooks, so
  presentation can still change without touching it.
- **Component code was written from the design system's README**, because no component
  bundle was published with it. Tokens are generated from `frontend/design/tokens.json`
  (`npm run tokens`).
- **The quokka cut-outs** come from the design system's assets, copied unchanged into
  `frontend/public/mascot/`. The quokka is never redrawn or recolored.

## Data model

- **`ModelVersion` is per target.** Stage 3 picks the best model *per target*, so each
  row is one model for one of mood, energy or stress (`target` column). A `Prediction`
  links to all three (`mood_model_version_id`, ...) and stores `model_types`.
- **`top_factors` is a dict per target** (`{"mood": [...], ...}`), each factor with a
  human `label` and a short lowercase `note` for the UI.
- **Predictions store the naive forecast** (`*_naive`) so accuracy can be compared with
  "tomorrow = today" on exactly the same days.
- **`User.token_version`** was added so logout revokes all access and refresh tokens.
- **`ModelVersion.data_updated_at`** records the newest check-in change a training saw;
  the nightly job retrains only when something newer exists. Comparing clocks proved
  fragile, so this is a watermark instead.
- **Integer primary keys**, JSON for tags (works in Postgres and SQLite).
- **Support region comes from the timezone** (`Asia/Singapore` -> SG, `Asia/Kolkata` -> IN,
  anything else -> international). The User table has no region field in the spec.

## API

- `PATCH /me` also accepts `onboarding_completed: true` (needed by onboarding).
- `GET /me/export` returns JSON; `GET /me/export?format=csv` returns check-ins as CSV.
- `POST /checkins` returns 201 when a day is created and 200 when it is replaced.
- `PATCH /checkins/{date}` works on any existing day; creating a day (`POST`) is limited
  to today and the 3 days before.
- `/meta` requires auth, as the spec says (only signup, login and health are public). The
  sign-up page shows a static "not a medical device" line instead.
- `GET /predictions/tomorrow` includes the `support` object too, even while still
  collecting the first week, so the Today page can show it first after a reload.
- Refresh tokens live in an httpOnly cookie scoped to `/api/v1/auth`. The browser talks to
  the API through the Next.js server (`/api/v1/*` rewrite), so it is same-origin and no
  CORS is needed for cookies.
- Rate limits: 10/min per IP for signup and login, 120/min for refresh (it runs on every
  page load). Behind the proxy the limiter uses `X-Forwarded-For` (`TRUST_FORWARDED_FOR`).
  The limiter is in-memory: fine for one API process, swap for Redis when scaling out.

## Prediction engine

- **Naive persistence is a real model type (`naive`).** "Never ship a model worse than
  tomorrow = today" needs something to ship when nothing beats it.
- **Baseline day-of-week offset** is the average residual against the EWMA level on that
  weekday, shrunk toward 0 by `n / (n + 4)`. The literal version (weekday mean minus
  overall mean, used as soon as each weekday has 2 samples) was so noisy that it often
  lost to naive persistence.
- **What "beats" means in the promotion rule.** Lower backtest MAE by at least 2%
  (`PROMOTION_MIN_IMPROVEMENT`) on at least 5 backtest days. For fitted models (ridge,
  gbm) we also require a one-sided paired t-test on daily absolute errors, p < 0.05.
  Without it, weekly retraining on a pure-noise user promoted ridge by luck most of the
  time. The baseline has nothing to fit, so it only needs the plain MAE win.
- **Complexity ladder.** Candidates are tried in order baseline -> ridge -> gbm; each must
  beat the best simpler option (including naive). Stage 2 includes the baseline as a
  candidate so it can keep winning if ridge doesn't help.
- **Observed behaviour on synthetic users** (seeded generator, 120 days):
  - Strong-signal users usually get ridge between day 35 and day 63, and the active models
    beat naive persistence by 35-55% on the last 30 days.
  - Pure-noise users: in a single training at 120 days, ridge or gbm won 1 of 30 target
    decisions across 10 seeds (about what p < 0.05 predicts). With weekly retraining,
    such a lucky promotion can stick for a while because the spec keeps the active model
    unless something beats it. Harmless here (ridge then performs about as well as the
    baseline), but worth knowing.
- **Ridge alpha** is chosen once per backtest, by time-series CV on the data *before*
  the backtest window, then reused for every fold. A nested search per fold was 5x slower
  for no measurable gain. The final model re-chooses alpha on all data.
- **The feature spec** (top 10 tags, custom metrics with 14+ values) is fitted on the
  whole training set before backtesting. Column choice only, never values; imputation
  medians are fitted per fold.
- **Synthetic "noise" user** is a local-level process (noise around a slowly drifting
  level), for which exponential smoothing is near-optimal. With i.i.d. noise, a heavily
  regularised ridge legitimately beats an EWMA (it estimates the long-run mean better),
  which would make "no model beats the baseline" false for the right reasons.
- **Gaps.** A day counts toward training only if its last check-in is at most 3 days old.
  Forecasts made with a stale last check-in get an interval widened by 25% per extra day,
  and fall back to the baseline after 3 days.
- **LightGBM runs single-threaded** (`n_jobs=1`). On tiny per-user datasets threads only
  add overhead (6s vs 30s+ per training on 2 cores).
- **Seeding retrains weekly** (and at each stage boundary) instead of nightly, to keep
  `scripts/seed.py` under a minute. The live app retrains nightly.

## Frontend

- Next.js 15 (App Router) with React 19, React Query 5, react-hook-form + zod.
- API types are generated from the backend's OpenAPI schema (`npm run gen:api`) and
  re-exported with friendly names from `src/types/api.ts`.
- Pages are client components: data comes from the API with a token held in memory, so
  server rendering would add nothing.
- **Page turns.** The book (desk, tabs, arrows, book) lives in the root layout and never
  remounts; each page renders a `<Spread>` into it (`components/book/`). On a route
  change the old spread snapshots its pages just before React removes them, and the new
  spread turns the page from that snapshot, forward or back by reading order
  (`routes.ts`). The turn holds the old page still until the new page's data has loaded
  (max 1s) and the window has scrolled to the top, so it always lands on a finished page.
  The book keeps its size during a turn; it grows with the turn when the next page is
  taller and settles afterwards when it is shorter. In-page changes (onboarding steps,
  "page saved", phone page turns) use `useBook().turn()`. Same-page swaps cross-fade.
  Reduced motion turns all of this off. Frame-by-frame screen recordings were used to
  check there are no single-frame jumps.
- Wide screens always show a two-page spread (a blank ruled page when a screen has only
  one), so the book never changes width between pages.
- On phones the book shows one page at a time. Sign-in and sign-up open on the form page;
  other chapters open on page 1.
- Insights is a sixth chapter tab (the design README lists five tabs, but also lists
  Insights as a chapter).
- Theme: Daylight by default, Lamplight, or "match my device"; the choice is stored in
  `localStorage` (a per-device preference).
