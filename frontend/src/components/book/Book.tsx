"use client";

/**
 * The storybook, split in two so it never has to be rebuilt:
 *
 * - <BookFrame> lives in the root layout: the desk, brand, chapter tabs, arrow tabs and
 *   the book itself persist across every route, so navigation never flashes.
 * - <Spread> is what each page renders: its left and right pages go into the book.
 *
 * When a Spread is replaced (a route change), it snapshots its pages just before React
 * removes them; the new Spread then turns the page from that snapshot to itself, in the
 * direction of travel through the book (see routes.ts and flip.ts). In-page changes
 * (onboarding steps, "page saved", turning pages on a phone) use `useBook().turn()`.
 */
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
  type ReactNode,
  type RefObject,
} from "react";
import { createPortal, flushSync } from "react-dom";

import { Icon } from "@/components/ui/Icon";
import styles from "@/components/ui/Book.module.css";
import { useAuth } from "@/lib/auth";
import { todayIn } from "@/lib/dates";

import { beginTransition, cancelTransition, capture, pinBook, prefersReducedMotion, type Shot } from "./flip";
import { PUBLIC_ROUTES, transitionBetween, type TurnDirection } from "./routes";

export interface Chapter {
  href: string;
  label: string;
  /** Path prefix that marks this chapter as current. */
  match: string;
}

interface SpreadApi {
  capture: () => Shot | null;
}

interface BookContextValue {
  bookRef: RefObject<HTMLElement | null>;
  layerRef: RefObject<HTMLDivElement | null>;
  pendingShot: MutableRefObject<Shot | null>;
  spread: MutableRefObject<SpreadApi | null>;
  pagerSlot: HTMLElement | null;
  prev?: Chapter;
  next?: Chapter;
  /** Turn the page while applying a state change (e.g. the next onboarding step). */
  turn: (direction: TurnDirection, update: () => void) => void;
  /** True when nothing is still loading, so the next page is ready to be shown. */
  isReady: () => boolean;
}

const BookContext = createContext<BookContextValue | null>(null);

export function useBook(): BookContextValue {
  const ctx = useContext(BookContext);
  if (!ctx) throw new Error("useBook must be used inside <BookFrame>");
  return ctx;
}

function isWide(): boolean {
  return window.matchMedia("(min-width: 721px)").matches;
}

function chaptersFor(timeZone: string): Chapter[] {
  return [
    { href: "/", label: "Today", match: "/" },
    { href: `/checkin/${todayIn(timeZone)}`, label: "Check-in", match: "/checkin" },
    { href: "/history", label: "History", match: "/history" },
    { href: "/twin", label: "Your twin", match: "/twin" },
    { href: "/insights", label: "Insights", match: "/insights" },
    { href: "/settings", label: "Settings", match: "/settings" },
  ];
}

/** Keeps the last non-null value around for `ms` after it becomes null, for exit animations. */
function useLingering<T>(value: T | null | undefined, ms: number): { value: T | null; leaving: boolean } {
  const [kept, setKept] = useState<T | null>(value ?? null);
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    if (value != null) {
      setKept(value);
      setLeaving(false);
      return;
    }
    setLeaving(true);
    const t = window.setTimeout(() => {
      setKept(null);
      setLeaving(false);
    }, ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return { value: value ?? kept, leaving: value == null && kept != null && leaving };
}

export function BookFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const { status, user } = useAuth();
  const bookRef = useRef<HTMLElement | null>(null);
  const layerRef = useRef<HTMLDivElement | null>(null);
  const pendingShot = useRef<Shot | null>(null);
  const spread = useRef<SpreadApi | null>(null);
  const [pagerSlot, setPagerSlot] = useState<HTMLElement | null>(null);
  const queryClient = useQueryClient();
  const authStatus = useRef(status);
  authStatus.current = status;
  const isReady = useCallback(
    () => authStatus.current !== "loading" && queryClient.isFetching() === 0,
    [queryClient],
  );

  const showTabs =
    status === "authenticated" && Boolean(user?.onboarding_completed) && !PUBLIC_ROUTES.includes(pathname);
  const chapters = useMemo(
    () => (showTabs && user ? chaptersFor(user.timezone) : null),
    [showTabs, user],
  );
  const tabs = useLingering(chapters, 320);
  const list = chapters ?? [];
  const idx = list.findIndex((c) => (c.match === "/" ? pathname === "/" : pathname.startsWith(c.match)));
  const prev = idx > 0 ? list[idx - 1] : undefined;
  const next = idx >= 0 && idx < list.length - 1 ? list[idx + 1] : undefined;
  const prevArrow = useLingering(prev, 320);
  const nextArrow = useLingering(next, 320);

  const turn = useCallback(
    (direction: TurnDirection, update: () => void) => {
      const api = spread.current;
      const from = api?.capture() ?? null;
      if (from && bookRef.current && !prefersReducedMotion()) pinBook(bookRef.current, from.bookH);
      flushSync(update);
      if (from && api && bookRef.current && layerRef.current) {
        beginTransition({
          book: bookRef.current,
          layer: layerRef.current,
          from,
          kind: direction,
          captureTo: api.capture,
          isReady,
        });
      }
    },
    [isReady],
  );

  const value = useMemo<BookContextValue>(
    () => ({ bookRef, layerRef, pendingShot, spread, pagerSlot, prev, next, turn, isReady }),
    [pagerSlot, prev, next, turn, isReady],
  );

  const arrow = (side: "left" | "right", c: Chapter | null, leaving: boolean) =>
    c ? (
      <Link
        href={c.href}
        scroll={false}
        className={[styles.arrow, side === "left" ? styles.arrowLeft : styles.arrowRight, leaving ? styles.leaving : ""].join(" ")}
        aria-label={`${side === "left" ? "Previous" : "Next"} chapter: ${c.label}`}
        tabIndex={leaving ? -1 : undefined}
      >
        <Icon name={side === "left" ? "arrow-left" : "arrow-right"} />
      </Link>
    ) : (
      <span className={styles.arrowSpacer} aria-hidden="true" />
    );

  return (
    <BookContext.Provider value={value}>
      <div className={styles.desk}>
        <header className={styles.top}>
          <Link href="/" scroll={false} className={styles.brand}>
            DigiBuddy
          </Link>
        </header>

        <div className={styles.tabsSlot}>
          {tabs.value ? (
            <nav aria-label="Chapters" className={[styles.tabs, tabs.leaving ? styles.tabsLeaving : ""].join(" ")}>
              <ul className={styles.tabList}>
                {tabs.value.map((c) => {
                  const on = c.match === "/" ? pathname === "/" : pathname.startsWith(c.match);
                  return (
                    <li key={c.label}>
                      <Link
                        href={c.href}
                        scroll={false}
                        className={[styles.tab, on ? styles.tabOn : ""].join(" ")}
                        aria-current={on ? "page" : undefined}
                      >
                        {c.label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </nav>
          ) : null}
        </div>

        <div className={styles.bookRow}>
          {arrow("left", prevArrow.value, prevArrow.leaving)}
          <div className={styles.bookWrap}>
            <main ref={bookRef} className={styles.book} id="main">
              {children}
            </main>
            <div ref={layerRef} className="book-flip-layer" aria-hidden="true" />
            <span className={styles.ribbon} aria-hidden="true" />
          </div>
          {arrow("right", nextArrow.value, nextArrow.leaving)}
        </div>

        <div ref={setPagerSlot} className={styles.pagerSlot} />
      </div>
    </BookContext.Provider>
  );
}

export interface SpreadProps {
  /** Accessible name, e.g. "Today". */
  label: string;
  /** Left page (page 1 on phones). */
  left: ReactNode;
  /** Right page (page 2 on phones). Without one, wide screens show a blank ruled page. */
  right?: ReactNode;
  /** Which page phones open on (0 = left, 1 = right). */
  startPage?: 0 | 1;
}

export function Spread({ label, left, right, startPage = 0 }: SpreadProps) {
  const ctx = useBook();
  const pathname = usePathname() ?? "/";
  const hasRight = right != null;
  const pages = hasRight ? 2 : 1;
  const [page, setPage] = useState<number>(hasRight ? startPage : 0);
  const leftRef = useRef<HTMLElement>(null);
  const rightRef = useRef<HTMLElement>(null);
  const pathRef = useRef(pathname);
  pathRef.current = pathname;

  if (page > pages - 1) setPage(pages - 1);

  const snap = useCallback((): Shot | null => {
    const book = ctx.bookRef.current;
    if (!book) return null;
    return capture(book, [leftRef.current, rightRef.current], pathRef.current, isWide());
  }, [ctx.bookRef]);

  useLayoutEffect(() => {
    const api: SpreadApi = { capture: snap };
    ctx.spread.current = api;

    const from = ctx.pendingShot.current;
    ctx.pendingShot.current = null;
    if (from && performance.now() - from.time < 2000 && ctx.bookRef.current && ctx.layerRef.current) {
      // Hold the old page over the book (before the new one is ever painted), wait for
      // the new page's data, then turn.
      beginTransition({
        book: ctx.bookRef.current,
        layer: ctx.layerRef.current,
        from,
        kind: transitionBetween(from.pathname, pathRef.current),
        captureTo: snap,
        isReady: ctx.isReady,
      });
    }

    return () => {
      // Runs before React removes this spread's DOM: remember how it looked.
      cancelTransition();
      ctx.pendingShot.current = snap();
      if (ctx.spread.current === api) ctx.spread.current = null;
    };
    // Mount/unmount only: the snapshot must cover the whole life of this spread.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const go = (delta: number) =>
    ctx.turn(delta > 0 ? "forward" : "back", () => setPage((p) => Math.min(pages - 1, Math.max(0, p + delta))));

  const pager = (
    <div className={styles.pager}>
      {page > 0 ? (
        <button type="button" className={styles.pagerBtn} onClick={() => go(-1)} aria-label="Previous page">
          <Icon name="arrow-left" />
        </button>
      ) : ctx.prev ? (
        <Link href={ctx.prev.href} scroll={false} className={styles.pagerBtn} aria-label={`Previous chapter: ${ctx.prev.label}`}>
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
      ) : ctx.next ? (
        <Link href={ctx.next.href} scroll={false} className={styles.pagerBtn} aria-label={`Next chapter: ${ctx.next.label}`}>
          <Icon name="arrow-right" />
        </Link>
      ) : (
        <span className={styles.pagerSpacer} />
      )}
    </div>
  );

  return (
    <>
      <section
        ref={leftRef}
        className={[styles.page, styles.pageLeft].join(" ")}
        data-active={page === 0}
        aria-label={hasRight ? `${label}, page 1` : label}
      >
        {left}
      </section>
      <section
        ref={rightRef}
        className={[styles.page, styles.pageRight, hasRight ? "" : styles.blankPage].join(" ")}
        data-active={page === 1}
        aria-label={hasRight ? `${label}, page 2` : undefined}
        aria-hidden={hasRight ? undefined : true}
      >
        {right}
      </section>
      {ctx.pagerSlot ? createPortal(pager, ctx.pagerSlot) : null}
    </>
  );
}
