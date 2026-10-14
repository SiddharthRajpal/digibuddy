import { formatDay } from "@/lib/dates";
import { FEELING_COPY, fillFor, forecastPhrase, usesWeather, weatherFor } from "@/lib/feelings";
import type { Forecast, Target, TargetForecast } from "@/types/api";

import { Icon } from "./Icon";
import { ReasonNote, tiltFor } from "./Paper";
import styles from "./ForecastCard.module.css";

const ROWS: Target[] = ["mood", "energy", "stress"];

function Tile({ target, tf }: { target: Target; tf: TargetForecast }) {
  const weather = usesWeather(target) ? weatherFor(tf.predicted) : null;
  return (
    <div
      className={styles.tile}
      style={{
        background: fillFor(target, tf.predicted),
        color: weather ? "var(--on-weather)" : "var(--ink)",
      }}
    >
      {weather ? <Icon name={weather.icon} size={22} className={styles.tileIcon} /> : null}
      <span className="t-number-xl">{tf.predicted.toFixed(1)}</span>
    </div>
  );
}

export interface ForecastCardProps {
  forecast: Forecast;
  /** Show the top reasons for the mood forecast. */
  showReasons?: boolean;
  heading?: string;
}

/**
 * Tomorrow's forecast. Forecasts are weather, not verdicts: always the range, never a
 * promise. Mood and energy use the weather scale; stress uses the plain sky tone.
 */
export function ForecastCard({ forecast, showReasons = true, heading }: ForecastCardProps) {
  const reasons = forecast.mood.factors ?? [];
  return (
    <section className={styles.card} aria-labelledby="forecast-heading">
      <header className={styles.head}>
        <p className="eyebrow">Forecast · {formatDay(forecast.target_date)}</p>
        <h2 id="forecast-heading" className="t-title-lg">
          {heading ?? "How tomorrow might feel"}
        </h2>
        {forecast.days_since_last_log > 1 ? (
          <p className={styles.stale}>
            Based on your last check-in {forecast.days_since_last_log} days ago, so the range is wider.
          </p>
        ) : null}
      </header>

      <ul className={styles.rows}>
        {ROWS.map((t) => {
          const tf = forecast[t];
          return (
            <li key={t} className={styles.row}>
              <Tile target={t} tf={tf} />
              <div className={styles.rowText}>
                <span className="t-title-md">{FEELING_COPY[t].label}</span>
                <span className="t-body-sm">{forecastPhrase(t, tf.predicted, tf.lower, tf.upper)}</span>
                <span className={styles.band} aria-hidden="true">
                  <span
                    className={styles.bandFill}
                    style={{
                      left: `${((tf.lower - 1) / 9) * 100}%`,
                      width: `${((tf.upper - tf.lower) / 9) * 100}%`,
                    }}
                  />
                  <span className={styles.bandDot} style={{ left: `${((tf.predicted - 1) / 9) * 100}%` }} />
                </span>
              </div>
            </li>
          );
        })}
      </ul>

      {showReasons && reasons.length > 0 ? (
        <div className={styles.reasons}>
          <h3 className="t-title-md">What’s shaping tomorrow’s mood</h3>
          <ul className={styles.reasonList}>
            {reasons.map((f, i) => (
              <ReasonNote
                key={f.feature}
                note={f.note}
                direction={f.direction}
                detail={f.label}
                tilt={tiltFor(f.feature + i)}
              />
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

/** "you guessed 6, it was 7!" — celebrates the twin's learning, never the mood value. */
export function CompareNote({ predicted, actual }: { predicted: number; actual: number }) {
  const close = Math.abs(predicted - actual) <= 1;
  return (
    <p className={styles.compare}>
      <Icon name={close ? "check" : "sparkle"} size={20} className={close ? styles.good : styles.learn} />
      <span className="t-note-sm">
        I guessed {predicted.toFixed(1)}, it was {actual}
        {close ? ". Nearly spot on!" : ". Noted, I'm learning!"}
      </span>
    </p>
  );
}
