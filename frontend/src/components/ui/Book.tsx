"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Icon } from "./Icon";
import styles from "./Book.module.css";

export interface Chapter {
  href: string;
  label: string;
  /** Path prefix that marks this chapter as current. */
  match: string;
}

export interface BookProps {
  /** Left page (or the only page on narrow screens: page 1). */
  left: ReactNode;
  /** Right page (page 2 on narrow screens). */
  right?: ReactNode;
  chapters?: Chapter[];
  /** Accessible name of the spread, e.g. "Today". */
  label: string;
  /** Which page narrow screens open on (0 = left, 1 = right). */
  startPage?: 0 | 1;
}

function useIsWide(): boolean {
  const [wide, setWide] = useState(true);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 721px)");
    const update = () => setWide(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return wide;
}

/**
 * The storybook. Wider than 720px it shows a two-page spread with arrow tabs on the
 * sides; narrower, one page with arrows and a page counter underneath. Chapter tabs
 * stick up from the top edge. Turning a page rotates it around the spine for
 * `flip-duration`; with reduced motion the page changes instantly.
 *
 * Both pages stay mounted (the hidden one uses `hidden`), so a form can span them.
 */
export function Book({ left, right, chapters, label, startPage = 0 }: BookProps) {
  const pathname = usePathname() ?? "/";
  const wide = useIsWide();
  const [page, setPage] = useState<number>(startPage);
  const [turn, setTurn] = useState<"forward" | "back">("forward");
  const leftRef = useRef<HTMLElement>(null);
  const rightRef = useRef<HTMLElement>(null);
  const pages = right ? 2 : 1;

  const currentIdx = chapters?.findIndex((c) =>
    c.match === "/" ? pathname === "/" : pathname.startsWith(c.match),
  );
  const prev = chapters && currentIdx !== undefined && currentIdx > 0 ? chapters[currentIdx - 1] : undefined;
  const next =
    chapters && currentIdx !== undefined && currentIdx >= 0 && currentIdx < chapters.length - 1
      ? chapters[currentIdx + 1]
      : undefined;

  useEffect(() => {
    setPage(startPage);
    setTurn("forward");
  }, [pathname, startPage]);

  // Turn the page around the spine. Uses the Web Animations API so pages are never
  // remounted (a form spanning both pages keeps its state).
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const el = wide ? rightRef.current ?? leftRef.current : page === 0 ? leftRef.current : rightRef.current;
    if (!el || typeof el.animate !== "function") return;
    const duration =
      parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--flip-duration")) || 700;
    const angle = turn === "forward" ? -75 : 75;
    el.style.transformOrigin = turn === "forward" ? "left center" : "right center";
    el.animate(
      [
        { transform: `rotateY(${angle}deg)`, opacity: 0.4 },
        { transform: "rotateY(0deg)", opacity: 1 },
      ],
      { duration, easing: "ease-in-out" },
    );
  }, [page, pathname, wide, turn]);

  const go = (delta: number) => {
    setTurn(delta > 0 ? "forward" : "back");
    setPage((p) => Math.min(pages - 1, Math.max(0, p + delta)));
    window.scrollTo({ top: 0 });
  };

  const showLeft = wide || page === 0;
  const showRight = Boolean(right) && (wide || page === 1);

  return (
    <div className={styles.desk}>
      <header className={styles.top}>
        <Link href="/" className={styles.brand}>
          DigiBuddy
        </Link>
      </header>

      {chapters ? (
        <nav aria-label="Chapters" className={styles.tabs}>
          <ul className={styles.tabList}>
            {chapters.map((c, i) => (
              <li key={c.href}>
                <Link
                  href={c.href}
                  className={[styles.tab, i === currentIdx ? styles.tabOn : ""].join(" ")}
                  aria-current={i === currentIdx ? "page" : undefined}
                >
                  {c.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}

      <div className={styles.bookRow}>
        {wide && prev ? (
          <Link href={prev.href} className={[styles.arrow, styles.arrowLeft].join(" ")} aria-label={`Previous chapter: ${prev.label}`}>
            <Icon name="arrow-left" />
          </Link>
        ) : (
          <span className={styles.arrowSpacer} aria-hidden="true" />
        )}

        <main className={[styles.book, right ? styles.spread : styles.single].join(" ")} aria-label={label} id="main">
          <span className={styles.ribbon} aria-hidden="true" />
          <section
            ref={leftRef}
            className={[styles.page, styles.pageLeft].join(" ")}
            hidden={!showLeft}
            aria-label={right ? `${label}, page 1` : undefined}
          >
            {left}
          </section>
          {right ? (
            <section
              ref={rightRef}
              className={[styles.page, styles.pageRight].join(" ")}
              hidden={!showRight}
              aria-label={`${label}, page 2`}
            >
              {right}
            </section>
          ) : null}
        </main>

        {wide && next ? (
          <Link href={next.href} className={[styles.arrow, styles.arrowRight].join(" ")} aria-label={`Next chapter: ${next.label}`}>
            <Icon name="arrow-right" />
          </Link>
        ) : (
          <span className={styles.arrowSpacer} aria-hidden="true" />
        )}
      </div>

      {!wide ? (
        <div className={styles.pager}>
          {page > 0 ? (
            <button type="button" className={styles.pagerBtn} onClick={() => go(-1)} aria-label="Previous page">
              <Icon name="arrow-left" />
            </button>
          ) : prev ? (
            <Link href={prev.href} className={styles.pagerBtn} aria-label={`Previous chapter: ${prev.label}`}>
              <Icon name="arrow-left" />
            </Link>
          ) : (
            <span className={styles.pagerSpacer} />
          )}
          <span className={styles.counter} aria-live="polite">
            Page {page + 1} of {pages}
          </span>
          {page < pages - 1 ? (
            <button type="button" className={styles.pagerBtn} onClick={() => go(1)} aria-label="Next page">
              <Icon name="arrow-right" />
            </button>
          ) : next ? (
            <Link href={next.href} className={styles.pagerBtn} aria-label={`Next chapter: ${next.label}`}>
              <Icon name="arrow-right" />
            </Link>
          ) : (
            <span className={styles.pagerSpacer} />
          )}
        </div>
      ) : null}
    </div>
  );
}

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
