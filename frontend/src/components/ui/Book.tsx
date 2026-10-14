import type { ReactNode } from "react";

import styles from "./Book.module.css";

export { Spread, useBook, type Chapter } from "@/components/book/Book";

/** Page heading block: small eyebrow in `label` caps plus a title. */
export function PageTitle({ eyebrow, title, children }: { eyebrow?: string; title: ReactNode; children?: ReactNode }) {
  return (
    <header className={styles.pageTitle}>
      {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
      <h1 className="t-title-xl">{title}</h1>
      {children ? <div className={styles.lede}>{children}</div> : null}
    </header>
  );
}
