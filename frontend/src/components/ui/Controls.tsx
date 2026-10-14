/** Small controls: tag chips, toggles, factor slots, collapsible sections, status notes. */
"use client";

import { useId, type InputHTMLAttributes, type ReactNode } from "react";

import { Icon, type IconName } from "./Icon";
import styles from "./Controls.module.css";

export interface TagChipProps {
  label: string;
  selected?: boolean;
  onToggle?: () => void;
  onRemove?: () => void;
}

export function TagChip({ label, selected = false, onToggle, onRemove }: TagChipProps) {
  if (onRemove) {
    return (
      <span className={[styles.chip, styles.chipOn].join(" ")}>
        {label}
        <button type="button" className={styles.chipX} onClick={onRemove} aria-label={`Remove ${label}`}>
          <Icon name="close" size={16} />
        </button>
      </span>
    );
  }
  return (
    <button
      type="button"
      className={[styles.chip, selected ? styles.chipOn : ""].join(" ")}
      aria-pressed={selected}
      onClick={onToggle}
    >
      {selected ? <Icon name="check" size={16} /> : null}
      {label}
    </button>
  );
}

export interface ToggleProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: ReactNode;
  hint?: ReactNode;
}

/** A switch on a pill track. Native checkbox underneath. */
export function Toggle({ label, hint, id: idProp, ...rest }: ToggleProps) {
  const auto = useId();
  const id = idProp ?? auto;
  return (
    <div className={styles.toggleRow}>
      <label htmlFor={id} className={styles.toggleLabel}>
        <span className="t-label">{label}</span>
        {hint ? <span className={styles.hint}>{hint}</span> : null}
      </label>
      <span className={styles.toggle}>
        <input id={id} type="checkbox" role="switch" className={styles.toggleInput} {...rest} />
        <span className={styles.track} aria-hidden="true">
          <span className={styles.thumb} />
        </span>
      </span>
    </div>
  );
}

export interface FactorSlotProps {
  icon: IconName;
  title: string;
  filled?: boolean;
  children: ReactNode;
}

/** An item slot for an optional detail: an inset well when empty, raised paper when filled. */
export function FactorSlot({ icon, title, filled = false, children }: FactorSlotProps) {
  return (
    <div className={[styles.slot, filled ? styles.slotFilled : ""].join(" ")}>
      <div className={styles.slotHead}>
        <Icon name={icon} />
        <span className="t-label">{title}</span>
      </div>
      <div className={styles.slotBody}>{children}</div>
    </div>
  );
}

export interface SectionProps {
  title: string;
  icon?: IconName;
  defaultOpen?: boolean;
  summary?: string;
  children: ReactNode;
}

/** A collapsible section (native <details>). */
export function Section({ title, icon, defaultOpen = false, summary, children }: SectionProps) {
  return (
    <details className={styles.section} open={defaultOpen}>
      <summary className={styles.summary}>
        {icon ? <Icon name={icon} /> : null}
        <span className="t-title-md">{title}</span>
        {summary ? <span className={styles.summaryNote}>{summary}</span> : null}
        <Icon name="arrow-down" size={20} className={styles.chev} />
      </summary>
      <div className={styles.sectionBody}>{children}</div>
    </details>
  );
}

export function LoadingNote({ label = "Turning the page…" }: { label?: string }) {
  return (
    <p className={styles.status} role="status" aria-live="polite">
      <span className={styles.dots} aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span className="t-note-sm">{label}</span>
    </p>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className={styles.errorNote} role="alert">
      <p>{message}</p>
      {onRetry ? (
        <button type="button" className={styles.retry} onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function EmptyNote({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className={styles.empty}>
      <p className="t-title-md">{title}</p>
      {children ? <div className="soft">{children}</div> : null}
    </div>
  );
}
