"use client";

import { useState } from "react";

import styles from "./Quokka.module.css";

export interface QuokkaProps {
  /** What the quokka says, in first person, short ("I'm learning!"). */
  says?: string;
  size?: number;
  /** Use the full-size cut-out for big moments (sign in, onboarding). */
  large?: boolean;
}

/**
 * The painted quokka, the only character. It uses the design system's cut-out image,
 * never redrawn or recolored, at most once per page. Put the files from the design
 * system's `Mascot/` folder in `public/mascot/`. If they are missing, the speech
 * still shows and the picture is skipped.
 */
export function Quokka({ says, size = 112, large = false }: QuokkaProps) {
  const [missing, setMissing] = useState(false);
  const src = large ? "/mascot/quokka-cutout.png" : "/mascot/quokka-cutout-small.png";
  return (
    <div className={styles.quokka}>
      {!missing ? (
        // eslint-disable-next-line @next/next/no-img-element -- static asset, no optimisation needed
        <img
          src={src}
          alt="DigiBuddy's quokka"
          width={size}
          height={size}
          className={styles.img}
          onError={() => setMissing(true)}
        />
      ) : null}
      {says ? (
        <p className={styles.bubble}>
          <span className="t-note">{says}</span>
        </p>
      ) : null}
    </div>
  );
}
