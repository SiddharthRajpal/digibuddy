/** Paper details: tape, sticky notes, polaroids and reason notes. Paper on paper, never floating UI. */
import type { CSSProperties, ReactNode } from "react";

import { Icon, type IconName } from "./Icon";
import styles from "./Paper.module.css";

/** Deterministic small tilt between -3° and +3° so notes don't jump between renders. */
export function tiltFor(seed: string | number): number {
  const s = String(seed);
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return ((Math.abs(h) % 7) - 3) * 0.8;
}

export function Tape({ side = "top", style }: { side?: "top" | "left" | "right"; style?: CSSProperties }) {
  return <span aria-hidden="true" className={[styles.tape, styles[`tape-${side}`]].join(" ")} style={style} />;
}

export interface StickyNoteProps {
  children: ReactNode;
  tone?: "paper" | "sprout" | "sky" | "petal";
  tilt?: number;
  tape?: boolean;
  className?: string;
  as?: "div" | "li" | "section" | "article";
  "aria-label"?: string;
}

export function StickyNote({ children, tone = "paper", tilt = 0, tape = false, className, as: Tag = "div", ...rest }: StickyNoteProps) {
  return (
    <Tag
      className={[styles.note, styles[tone], className ?? ""].join(" ")}
      style={{ ["--tilt" as string]: `${tilt}deg` }}
      {...rest}
    >
      {tape ? <Tape /> : null}
      {children}
    </Tag>
  );
}

export interface PolaroidProps {
  children: ReactNode;
  caption: ReactNode;
  tilt?: number;
  sky?: boolean;
  className?: string;
}

export function Polaroid({ children, caption, tilt = 0, sky = true, className }: PolaroidProps) {
  return (
    <figure className={[styles.polaroid, className ?? ""].join(" ")} style={{ ["--tilt" as string]: `${tilt}deg` }}>
      <Tape />
      <div className={[styles.photo, sky ? styles.photoSky : ""].join(" ")}>{children}</div>
      <figcaption className={styles.caption}>{caption}</figcaption>
    </figure>
  );
}

export interface ReasonNoteProps {
  /** Short, lowercase, two to four words: "short on sleep". */
  note: string;
  direction?: "up" | "down" | "higher" | "lower";
  detail?: ReactNode;
  tilt?: number;
  icon?: IconName;
}

/** A gentle reason in the quokka's hand. */
export function ReasonNote({ note, direction, detail, tilt = 0, icon }: ReasonNoteProps) {
  const up = direction === "up" || direction === "higher";
  const arrow: IconName | undefined = direction ? (up ? "arrow-up" : "arrow-down") : icon;
  return (
    <StickyNote tone="sprout" tilt={tilt} className={styles.reason} as="li">
      <span className={styles.reasonHead}>
        {arrow ? <Icon name={arrow} size={20} label={direction ? (up ? "pushes up" : "pushes down") : undefined} /> : null}
        <span className="t-note">{note}</span>
      </span>
      {detail ? <span className={styles.reasonDetail}>{detail}</span> : null}
    </StickyNote>
  );
}
