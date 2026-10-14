import { useId } from "react";

import { FEELING_COPY, fillFor, usesWeather, weatherFor } from "@/lib/feelings";
import type { Feeling } from "@/types/api";

import { Icon } from "./Icon";
import styles from "./FeelingScale.module.css";

export interface FeelingScaleProps {
  feeling: Feeling;
  value: number | null | undefined;
  onChange: (value: number) => void;
  error?: string;
  name?: string;
}

const VALUES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

/**
 * A 1–10 feeling picker. Mood, energy and focus use the weather scale; stress and
 * worry (higher is harder) use the plain sky tone so color never implies good or bad.
 * Built on native radio inputs for keyboard and screen-reader support.
 */
export function FeelingScale({ feeling, value, onChange, error, name }: FeelingScaleProps) {
  const id = useId();
  const copy = FEELING_COPY[feeling];
  const weather = value ? weatherFor(value) : null;
  return (
    <fieldset
      className={[styles.scale, usesWeather(feeling) ? styles.weather : styles.plain].join(" ")}
      aria-describedby={error ? `${id}-err` : undefined}>
      <legend className={styles.legend}>
        <span className="t-title-md">{copy.label}</span>
        {value ? (
          <span className={styles.reading}>
            {usesWeather(feeling) && weather ? (
              <>
                <Icon name={weather.icon} size={20} />
                {weather.name.toLowerCase()}, {value}
              </>
            ) : (
              <>{value} of 10</>
            )}
          </span>
        ) : null}
      </legend>
      <div className={styles.slots}>
        {VALUES.map((v) => (
          <label
            key={v}
            className={[styles.slot, value === v ? styles.selected : ""].join(" ")}
            style={{ ["--slot-fill" as string]: fillFor(feeling, v) }}
          >
            <input
              type="radio"
              className="visually-hidden"
              name={name ?? `${id}-${feeling}`}
              value={v}
              checked={value === v}
              onChange={() => onChange(v)}
            />
            <span className={styles.number}>{v}</span>
          </label>
        ))}
      </div>
      <div className={styles.ends} aria-hidden="true">
        <span>{copy.low}</span>
        <span>{copy.high}</span>
      </div>
      {error ? (
        <p id={`${id}-err`} className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}
