"use client";

import { useState } from "react";

import type { Support } from "@/types/api";

import { Button } from "./Button";
import { Icon } from "./Icon";
import { StickyNote } from "./Paper";
import styles from "./SupportNote.module.css";

/**
 * Care and safety note. Gentle, dismissible, no alarm colors: `petal` paper with the
 * quokka's `blossom`. Shown at the top of the page, before any forecast.
 */
export function SupportNote({ support }: { support: Support }) {
  const [open, setOpen] = useState(true);
  if (!open) return null;
  return (
    <StickyNote tone="petal" tape as="section" aria-label="Support" className={styles.note}>
      <div className={styles.head}>
        <Icon name="heart" className={styles.heart} />
        <p className="t-title-md">{support.message.split(". ")[0]}.</p>
      </div>
      <p>{support.message.split(". ").slice(1).join(". ")}</p>
      <ul className={styles.list}>
        {support.resources.map((r) => (
          <li key={r.name} className={styles.item}>
            <span className={styles.name}>{r.name}</span>
            <span className={styles.ways}>
              {r.phone ? (
                <a href={`tel:${r.phone.replace(/\s/g, "")}`} className={styles.link}>
                  <Icon name="phone" size={18} />
                  {r.phone}
                </a>
              ) : null}
              {r.url ? (
                <a href={r.url} target="_blank" rel="noreferrer" className={styles.link}>
                  <Icon name="link" size={18} />
                  Website
                </a>
              ) : null}
              {r.hours ? <span className="soft">{r.hours}</span> : null}
            </span>
          </li>
        ))}
      </ul>
      <div className={styles.actions}>
        <Button variant="quiet" onClick={() => setOpen(false)}>
          Close this note
        </Button>
      </div>
    </StickyNote>
  );
}
