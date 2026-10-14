# DigiBuddy: the presenter's guide

Everything you need to present DigiBuddy to a panel: the pitch, a demo script, how it works
in plain words, the results, and answers to the questions you are likely to get.
For the full engineering detail, see `technical.md`.

---

## 1. The 30-second pitch

> Most of us can't say why some days feel heavy and others feel easy. DigiBuddy is a
> personal "digital twin" for your wellbeing. You spend a minute a day logging how you
> feel and a few things about your day: sleep, activity, screen time, workload, time with
> people. After one week it starts forecasting how **tomorrow** is likely to feel, giving
> mood, energy and stress, each with an honest range and the reasons behind it. Every day
> it checks its guess against what really happened and learns from the gap. It's built
> on *your* data only, it is never worse than the simplest possible guess, and it shows
> you its accuracy.

**One line:** *A weather forecast for your mood, built only from your own days, that shows
how often it's right.*

---

## 2. The problem

- Mood, energy and stress follow patterns: sleep, workload, exercise, people, the day of
  the week. Those patterns are personal, and they are hard to see from inside one day at
  a time.
- Mood-tracking apps record the past, then leave you to stare at charts. They don't look
  forward.
- Generic advice ("sleep more") ignores that sleep might matter a lot for one person and
  hardly at all for another.
- People want to **plan around** a hard day (move a meeting, protect sleep, call a friend),
  not only reflect on it afterwards.

## 3. What DigiBuddy does: the core loop

```
   LOG  ──►  LEARN  ──►  PREDICT  ──►  COMPARE
    ▲                                    │
    └────────────────────────────────────┘
```

1. **Log.** Five quick feelings (mood, energy, stress, worry, focus, each 1 to 10). Everything
   else is optional: sleep hours and quality, exercise, time outdoors, screen time, caffeine,
   alcohol, meals, time with people, workload, tags (e.g. "exam", "gym", "family"), your own
   custom trackers, and private notes.
2. **Learn.** It builds a model of *you*, from your days only.
3. **Predict.** Tomorrow's mood, energy and stress, each with an 80% range ("likely between
   5 and 7") and the top three reasons ("you slept less than usual", "workload has been high").
4. **Compare.** When you log tomorrow, it shows "I guessed 6, it was 7", scores itself, and
   retrains overnight.

## 4. Demo script (about 6 minutes)

**Before you start:** run the app (section 14), open http://localhost:3000, and sign out so
you start on the cover. Demo login: **demo@digibuddy.app / demo1234**. It has 120 days of
realistic synthetic data, so every screen is full.

| # | Screen | Do | Say |
|---|---|---|---|
| 1 | **Sign in** | Point at the left page (quokka, "not a medical device"), then sign in. Watch the page turn. | "The whole app is a hand-painted journal. Every screen is a page, and moving through the app turns real pages, forwards or backwards." |
| 2 | **Today** | Show the three weather tiles for tomorrow, the ranges, the reasons, and the "N% in tune" note. | "This is tomorrow's forecast. Each feeling has a range, not a single number pretending to be certain, and the reasons come straight from the model." |
| 3 | **Check-in** | Click the Check-in tab. Set the five feelings; open "Sleep" and change hours; add a tag; save. | "Thirty seconds a day. Only five things are required, the rest is optional. Saving turns to a 'page saved' page that compares yesterday's guess with today." |
| 4 | **History** | Show the "Guessed vs. felt" chart; switch mood / energy / stress; scroll the day list. | "Every forecast is kept and scored. You can see where it got close and where it missed." |
| 5 | **Your twin** | Show the stage (chapter), the "in tune" meter, and the accuracy-over-time chart against "same as today". | "This is the twin itself. It grows in stages as you log more. The chart shows its error dropping over time, always compared with the simplest guess: tomorrow is the same as today." |
| 6 | **Insights** | Show "The day after…" notes, the weekday polaroids, the tag notes. | "Plain observations, never claims about causes, and each one shows how many days it's based on." |
| 7 | **Settings** | Show the theme switch (Daylight / Lamplight), custom trackers, export, delete account. | "Your data is yours: export everything as JSON or CSV, or delete the account and every trained model with it." |

**Optional extras:**
- Create a fresh account to show the first week: "3 of 7 pages written". There is no
  forecast until there is enough data.
- Show the support note: log a mood of 2 and the next screen leads with a gentle message
  and local helplines, before any forecast.

## 5. How the twin works (no jargon)

**It grows with you.** It counts the days you have actually logged, not days since sign-up:

| Days logged | What the twin uses |
|---|---|
| 0–6 | Nothing yet. It shows progress toward the first forecast. |
| 7–20 | Your recent trend (recent days count most) plus how each weekday usually goes for you. |
| 21–59 | Also a personal model of how your sleep, workload, activity, people and tags push your next day. |
| 60+ | Also a more flexible model that can pick up combinations (e.g. little sleep *and* a heavy workload). Each feeling uses whichever model has proven most accurate for you. |

**It has to earn every change.** Before a new model is used, the twin "replays" your recent
days. For each day it trains only on the days before, makes a guess, and records how far off
it was. A new model replaces the current one only if it is clearly better than both the
current model and the simplest guess ("tomorrow = today"), and for the advanced models
the win has to pass a statistical check so it isn't just luck. **If nothing beats "tomorrow
= today", that is what you get.** It never ships something worse.

**Its ranges are honest.** The 80% range comes from the twin's own recent misses. On test
data about 80% of real outcomes land inside, and the Twin page shows the live rate. Skip
days and the range widens; after more than three days without a check-in it falls back to
the simple trend model.

**It explains itself.** The reasons are calculated from the model, not written afterwards:
which of today's inputs pushed tomorrow up or down the most, in plain words.

**It keeps learning.** Every night at 3 a.m. your time, if you logged anything new, it
retrains, re-tests and refreshes tomorrow's forecast. Recent weeks count more than old ones,
so it follows you as your life changes.

**It can't cheat.** An automated test rebuilds every input with the future removed and checks
nothing changes, so no input can peek at tomorrow.

## 6. Does it work? (the numbers)

On the demo user (synthetic, 120 days, realistic patterns):

- Over the last 30 days the twin's forecasts were **34% (mood), 54% (energy) and 52%
  (stress) more accurate** than "tomorrow = today".
- Its average error fell from **about 4.5 points** (out of 10) at the first forecasts to
  **about 1.2 points**.
- The 80% ranges contain the real value about 80% of the time (automated test: between 70%
  and 90%).

The safety net is proven too. On a synthetic user whose days are **pure noise** (inputs have
no effect), the twin correctly refuses to promote the advanced models: across 10 random seeds
they won 1 of 30 decisions, about what you'd expect from chance at the 5% level. It doesn't
invent patterns that aren't there.

> **Be upfront:** these are results on synthetic data designed to behave like real people.
> Real-user results will come from a pilot.

## 7. Insights

Simple, checkable observations, never causes, each with its sample size:

- **"The day after…"**: links such as "on days after you sleep more, your mood tends to be
  higher". Shown only after 21+ days and only when the link is moderately strong.
- **Weekdays**: your best and worst days of the week, once each weekday has 3+ pages.
- **Tags**: tags that tend to come before better or worse days (5+ occurrences), including
  your own custom tags.

## 8. Safety and privacy

**Wellbeing safety:**
- DigiBuddy is a **self-reflection tool, not a medical or diagnostic product**. This is said
  at sign-up, during onboarding (where the user must tick to acknowledge it), and in Settings.
- If someone logs a very low mood (2 or less), a low mood three days running (3 or less), or
  the forecast is very low (3 or less), the app shows a gentle support note with local helplines
  **before** any forecast. Singapore: SOS 1767, IMH 6389 2222. India: Tele-MANAS 14416.
  Everywhere else: the Find A Helpline directory.
- No alarm colours and no scary language. The note can be dismissed.

**Privacy:**
- Each person's model is trained **only on their own data**. Nothing is pooled across users.
- **Private notes are never analysed.** They are stored for the user and excluded from every
  model (tested).
- Server logs contain IDs and timings, never feelings or notes.
- Export everything (JSON or CSV) at any time; deleting the account removes every row and
  every trained model file (tested).
- Passwords are hashed with argon2 (the current recommended standard). Sessions use
  short-lived tokens, and signing out revokes all of them.

## 9. The design

- The **DigiBuddy Storybook** design system: every screen is a page in a hand-painted journal
  on a wooden desk, with chapter tabs, a ribbon bookmark, and a **quokka** mascot (the
  "world's happiest animal").
- Forecasts are shown as weather (sunny, cloudy, rainy), which people read at a glance.
- Real page-turn animations: going forward flips the page forwards, going back flips it back,
  and the book never jumps or cuts.
- Two themes: Daylight and Lamplight (dark), or match the device. Works on phones (one page at a
  time) and desktops (two-page spread). Respects "reduce motion".
- Why it matters: wellbeing apps often feel clinical. A journal feels personal and calm, so
  people keep coming back, and the forecast only gets good if they do.

## 10. Tech in one breath

**Next.js + React** frontend → **FastAPI (Python)** backend → **PostgreSQL** database, all
running in **Docker** with one command. The ML uses **scikit-learn** (trend and ridge
regression) and **LightGBM** (gradient boosting), with conformal prediction for the ranges and
SHAP-style contributions for the reasons. It has automated tests, type checking and CI on
GitHub.

## 11. What makes it different

| Typical mood tracker | DigiBuddy |
|---|---|
| Looks backwards (charts of the past) | Looks **forward** (tomorrow's forecast) |
| One-size-fits-all tips | A model of **you**, trained only on your days |
| A single number, or no prediction at all | A **range** that's right about 80% of the time |
| "Trust us" | Shows its **accuracy** against a simple baseline every day |
| Black box | **Reasons** for every forecast |
| Complex models from day one | **Starts simple and only upgrades when it's proven better** |
| Often reads your journal | **Notes are never analysed** |

## 12. Likely panel questions and answers

**"How accurate is it?"**
On our demo user it's 34–54% more accurate than "tomorrow = today", with an average error of
about 1.2 points out of 10. More importantly, it measures itself every day and shows the user,
so accuracy isn't a claim, it's on screen.

**"What happens in the first week? (cold start)"**
No forecast until 7 logged days, which avoids guessing from nothing. Then it starts with the
simplest model (recent trend + weekday) and only moves up as data proves a better model works.

**"Why not just use ChatGPT / an LLM?"**
This is a numbers problem on a small personal dataset: a few months of daily values. Small,
proven statistical models are more accurate here, give honest ranges, explain themselves,
run cheaply, and keep data private. An LLM can't tell you how often it's right. We also
deliberately never analyse journal notes.

**"Isn't predicting someone's mood risky?"**
It's positioned as self-reflection, never diagnosis, and that's said up front. Very low moods
or low forecasts trigger a support note with helplines before any forecast is shown. We avoid
alarming language and colours.

**"What if the model is wrong?"**
It will be sometimes, and that's why it shows a range rather than a single number and shows its
track record. It also has a floor: if no model beats "tomorrow = today", that's what it uses.

**"Correlation isn't causation. Aren't the insights misleading?"**
Insights are worded as observations ("days after X tend to…"), never causes, and each shows how
many days it's based on. Weak or small-sample patterns aren't shown at all.

**"Where is the data stored? Who owns it?"**
In the app's own Postgres database. Each user's data and model are separate. Users can export
everything or delete everything, including trained models, at any time.

**"Why would people log every day?"**
It's quick (five sliders, the rest is optional), it's pleasant (the journal design), and it
pays back: the more you log, the better your forecast gets, and you can see that happen on the
Twin page.

**"How does it scale?"**
Per-user models are tiny (milliseconds to predict, seconds to train). It's containerised
already. To scale out, the rate limiter and nightly scheduler move to Redis and a job queue,
and it runs on a managed database with HTTPS.

**"Is the data real?"**
The demo uses a synthetic data generator that models realistic effects (sleep debt, workload,
weekends, exams, exercise). We also built "weak-signal" and "pure-noise" users to prove the
twin doesn't overfit. A real-user pilot is the next step.

**"What's the business / funding?"**
DigiBuddy is raising **₹5,00,000 pre-seed**. Use your fund-utilisation plan and pitch deck for
the breakdown.

## 13. Limitations (say them before they're asked)

- Results so far are on **synthetic data**; real-user validation comes next.
- It finds **associations, not causes**.
- Each new user starts cold (a week before the first forecast).
- No email verification or password reset yet (needs an email service).
- Helpline numbers must be verified before a public launch.
- Runs locally via Docker today; not yet hosted publicly.

**Roadmap:** reminders, multi-day forecasts, wearable integrations (sleep, steps), faster cold
starts using privacy-preserving shared priors, richer custom-tracker insights, and a hosted
version with HTTPS and a managed database.

## 14. Running the demo

1. Install and open **Docker Desktop**.
2. Windows: double-click `start.bat`. Mac: run `docker compose up --build -d`, then
   `docker compose exec api python -m scripts.seed` once. After that, start and stop it from
   the Docker Desktop app.
3. Open **http://localhost:3000** and sign in with **demo@digibuddy.app / demo1234**.
4. If port 3000 is busy: `WEB_PORT=3001 API_PORT=8001 docker compose up --build -d`
   (Mac) and open http://localhost:3001.

The first build takes 5–10 minutes, so do it **before** the presentation. The data persists
between restarts.

## 15. Cheat sheet

| | |
|---|---|
| What | Personal wellbeing forecast: tomorrow's mood, energy, stress |
| Daily effort | 5 required sliders, about 30 seconds |
| First forecast | After 7 logged days |
| Model stages | Trend (7+) → personal linear (21+) → adaptive / boosting (60+) |
| Safety floor | Never worse than "tomorrow = today" |
| Range | 80%, and it's right about 80% of the time |
| Demo accuracy | 34% / 54% / 52% better than "same as today"; error 4.5 → 1.2 |
| Retraining | Nightly at 3 a.m. local time, only if there's new data |
| Privacy | Per-user only, notes never analysed, full export and delete |
| Safety | Support note and SG/IN/international helplines on low moods |
| Stack | Next.js, FastAPI, PostgreSQL, scikit-learn, LightGBM, Docker |
| Demo login | demo@digibuddy.app / demo1234 |
| Raising | ₹5,00,000 pre-seed |
