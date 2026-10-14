/**
 * Charts drawn as SVG with design tokens. Every chart takes typed data props and also
 * renders the same data as a table (in a disclosure) for screen readers and checking.
 */
import { formatDay } from "@/lib/dates";
import { weatherFor } from "@/lib/feelings";

import styles from "./Charts.module.css";

const W = 640;
const H = 240;
const PAD = { top: 16, right: 16, bottom: 32, left: 32 };

function scaleX(i: number, n: number): number {
  if (n <= 1) return PAD.left + (W - PAD.left - PAD.right) / 2;
  return PAD.left + (i / (n - 1)) * (W - PAD.left - PAD.right);
}

function scaleY(v: number, min: number, max: number): number {
  return PAD.top + (1 - (v - min) / (max - min)) * (H - PAD.top - PAD.bottom);
}

function tickDates<T extends { date: string }>(points: T[], count = 5): { i: number; label: string }[] {
  if (points.length === 0) return [];
  const step = Math.max(1, Math.round((points.length - 1) / (count - 1)));
  const out: { i: number; label: string }[] = [];
  for (let i = 0; i < points.length; i += step) {
    out.push({ i, label: formatDay(points[i]!.date, { weekday: undefined }) });
  }
  return out;
}

export interface PredictionPoint {
  date: string;
  predicted: number;
  lower: number;
  upper: number;
  actual: number | null;
}

export interface PredictionChartProps {
  points: PredictionPoint[];
  title: string;
  /** Use weather colors for actual dots (mood/energy); otherwise plain ink. */
  weather?: boolean;
}

/** "Guessed vs. felt": the forecast range band and line in `sky`, what you felt as dots. */
export function PredictionChart({ points, title, weather = true }: PredictionChartProps) {
  const n = points.length;
  const band =
    n > 0
      ? [
          ...points.map((p, i) => `${scaleX(i, n)},${scaleY(p.upper, 1, 10)}`),
          ...points
            .map((p, i) => `${scaleX(i, n)},${scaleY(p.lower, 1, 10)}`)
            .reverse(),
        ].join(" ")
      : "";
  const line = points.map((p, i) => `${scaleX(i, n)},${scaleY(p.predicted, 1, 10)}`).join(" ");
  const last = [...points].reverse().find((p) => p.actual !== null);
  const lastIdx = last ? points.lastIndexOf(last) : -1;

  return (
    <figure className={styles.figure}>
      <svg viewBox={`0 0 ${W} ${H}`} className={styles.svg} role="img" aria-label={title}>
        {[2, 4, 6, 8, 10].map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={scaleY(v, 1, 10)} y2={scaleY(v, 1, 10)} className={styles.grid} />
            <text x={PAD.left - 8} y={scaleY(v, 1, 10) + 4} className={styles.axis} textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        {tickDates(points).map(({ i, label }) => (
          <text key={i} x={scaleX(i, n)} y={H - 8} className={styles.axis} textAnchor="middle">
            {label}
          </text>
        ))}
        {n > 1 ? <polygon points={band} className={styles.band} /> : null}
        {n > 1 ? <polyline points={line} className={styles.predLine} /> : null}
        {points.map((p, i) =>
          p.actual !== null ? (
            <circle
              key={p.date}
              cx={scaleX(i, n)}
              cy={scaleY(p.actual, 1, 10)}
              r={5}
              className={styles.dot}
              style={{ fill: weather ? weatherFor(p.actual).token : "var(--paper)" }}
            />
          ) : (
            <circle key={p.date} cx={scaleX(i, n)} cy={scaleY(p.predicted, 1, 10)} r={4} className={styles.predDot} />
          ),
        )}
        {last && lastIdx >= 0 ? (
          <text
            x={Math.min(scaleX(lastIdx, n), W - 150)}
            y={Math.max(scaleY(Math.max(last.actual ?? 0, last.upper), 1, 10) - 12, 18)}
            className={styles.annotation}
          >
            I guessed {last.predicted.toFixed(1)}, it was {last.actual}
          </text>
        ) : null}
      </svg>
      <figcaption className={styles.legend}>
        <span className={styles.key}>
          <span className={styles.keyBand} /> my guess and its range
        </span>
        <span className={styles.key}>
          <span className={styles.keyDot} /> how you felt
        </span>
      </figcaption>
      <details className={styles.tableWrap}>
        <summary>Show as a table</summary>
        <table className={styles.table}>
          <caption className="visually-hidden">{title}</caption>
          <thead>
            <tr>
              <th scope="col">Day</th>
              <th scope="col">Guess</th>
              <th scope="col">Range</th>
              <th scope="col">Felt</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.date}>
                <th scope="row">{formatDay(p.date)}</th>
                <td>{p.predicted.toFixed(1)}</td>
                <td>
                  {p.lower.toFixed(1)}–{p.upper.toFixed(1)}
                </td>
                <td>{p.actual ?? "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

export interface AccuracyPointView {
  date: string;
  twin: number | null;
  naive: number | null;
}

/** How far off the twin has been (7-day average) compared with "tomorrow = today". */
export function AccuracyChart({ points, title }: { points: AccuracyPointView[]; title: string }) {
  const n = points.length;
  const values = points.flatMap((p) => [p.twin ?? 0, p.naive ?? 0]);
  const max = Math.max(3, Math.ceil(Math.max(...values, 0)));
  const path = (key: "twin" | "naive") =>
    points
      .map((p, i) => (p[key] === null ? null : `${scaleX(i, n)},${scaleY(p[key] as number, 0, max)}`))
      .filter(Boolean)
      .join(" ");
  const ticks = Array.from({ length: max + 1 }, (_, i) => i);
  return (
    <figure className={styles.figure}>
      <svg viewBox={`0 0 ${W} ${H}`} className={styles.svg} role="img" aria-label={title}>
        {ticks.map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={scaleY(v, 0, max)} y2={scaleY(v, 0, max)} className={styles.grid} />
            <text x={PAD.left - 8} y={scaleY(v, 0, max) + 4} className={styles.axis} textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        {tickDates(points).map(({ i, label }) => (
          <text key={i} x={scaleX(i, n)} y={H - 8} className={styles.axis} textAnchor="middle">
            {label}
          </text>
        ))}
        {n > 1 ? <polyline points={path("naive")} className={styles.naiveLine} /> : null}
        {n > 1 ? <polyline points={path("twin")} className={styles.twinLine} /> : null}
      </svg>
      <figcaption className={styles.legend}>
        <span className={styles.key}>
          <span className={styles.keyTwin} /> your twin, points off on average
        </span>
        <span className={styles.key}>
          <span className={styles.keyNaive} /> guessing &ldquo;same as today&rdquo;
        </span>
      </figcaption>
      <details className={styles.tableWrap}>
        <summary>Show as a table</summary>
        <table className={styles.table}>
          <caption className="visually-hidden">{title}</caption>
          <thead>
            <tr>
              <th scope="col">Day</th>
              <th scope="col">Twin (7-day avg off)</th>
              <th scope="col">Same as today</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.date}>
                <th scope="row">{formatDay(p.date)}</th>
                <td>{p.twin?.toFixed(2) ?? "–"}</td>
                <td>{p.naive?.toFixed(2) ?? "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

/** A ring that fills in `sprout` as the twin gets more in tune. */
export function TwinMeter({ percent, label }: { percent: number | null; label: string }) {
  const r = 94;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, percent ?? 0));
  return (
    <div className={styles.meter}>
      <svg viewBox="0 0 220 220" width={220} height={220} role="img" aria-label={label}>
        <circle cx="110" cy="110" r={r} className={styles.meterTrack} />
        <circle
          cx="110"
          cy="110"
          r={r}
          className={styles.meterFill}
          strokeDasharray={`${(pct / 100) * c} ${c}`}
          transform="rotate(-90 110 110)"
        />
      </svg>
      <div className={styles.meterText}>
        <span className="t-number-xl">{percent === null ? "–" : `${Math.round(pct)}%`}</span>
        <span className="t-caption">in tune with you</span>
      </div>
    </div>
  );
}
