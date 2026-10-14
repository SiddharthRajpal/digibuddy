/**
 * Page-turn engine. Plain DOM + Web Animations API, no React.
 *
 * A transition works from two snapshots: `from` (the pages just before the change) and
 * `to` (the pages just after it, already rendered underneath). Static clones of those
 * pages are laid over the book and animated, then removed once the live pages are
 * exactly what the last frame showed, so there is never a cut.
 *
 * Wide (two-page spread):
 *   forward  the right page turns over to the left. Front: old right page.
 *            Back: new left page. Old left page stays underneath until covered.
 *   back     the left page turns over to the right (mirror image).
 * Narrow (one page):
 *   forward  the page lifts off to the left, revealing the next page.
 *   back     the previous page turns back in from the left, over the current one.
 * fade       same page re-rendered (data loaded, view switched): cross-fade.
 */
import type { Transition } from "./routes";

export interface PageShot {
  node: HTMLElement;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Shot {
  pathname: string;
  wide: boolean;
  pages: PageShot[];
  bookH: number;
  scrollY: number;
  time: number;
}

const ROTATE_EASE = "cubic-bezier(0.45, 0.05, 0.2, 1)";
const SETTLE_MS = 160;

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function flipDuration(): number {
  const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--flip-duration"));
  return Number.isFinite(v) && v > 0 ? v : 700;
}

/** Deep clone that keeps what the user typed and picked, minus ids and focusability. */
function cloneWithState(src: HTMLElement): HTMLElement {
  const node = src.cloneNode(true) as HTMLElement;
  const srcFields = src.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(
    "input, textarea, select",
  );
  const dstFields = node.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(
    "input, textarea, select",
  );
  srcFields.forEach((f, i) => {
    const d = dstFields[i];
    if (!d) return;
    if (f instanceof HTMLInputElement && (f.type === "checkbox" || f.type === "radio")) {
      (d as HTMLInputElement).checked = f.checked;
    } else {
      d.value = f.value;
      if (d instanceof HTMLTextAreaElement) d.textContent = f.value;
    }
  });
  node.removeAttribute("hidden");
  node.removeAttribute("id");
  node.querySelectorAll("[id]").forEach((n) => n.removeAttribute("id"));
  node.setAttribute("aria-hidden", "true");
  node.setAttribute("inert", "");
  return node;
}

/** Snapshot the visible pages of the book. */
export function capture(
  book: HTMLElement,
  sections: (HTMLElement | null)[],
  pathname: string,
  wide: boolean,
): Shot {
  const b = book.getBoundingClientRect();
  const pages: PageShot[] = [];
  for (const s of sections) {
    // Pages hidden by CSS (the inactive page on a phone) have no boxes: skip them.
    if (!s || s.getClientRects().length === 0) continue;
    const r = s.getBoundingClientRect();
    pages.push({ node: cloneWithState(s), x: r.left - b.left, y: r.top - b.top, w: r.width, h: r.height });
  }
  return { pathname, wide, pages, bookH: b.height, scrollY: window.scrollY, time: performance.now() };
}

function place(node: HTMLElement, x: number, y: number, w: number, h: number): HTMLElement {
  Object.assign(node.style, {
    position: "absolute",
    left: `${x}px`,
    top: `${y}px`,
    width: `${w}px`,
    height: `${h}px`,
    margin: "0",
  });
  return node;
}

function div(className: string): HTMLDivElement {
  const d = document.createElement("div");
  d.className = className;
  return d;
}

let cancelActive: (() => void) | null = null;

/** Stop any running transition and remove its overlay immediately. */
export function cancelTransition(): void {
  cancelActive?.();
  cancelActive = null;
}

/**
 * Pin the book at its current height. Call before the new page is committed: if the
 * document got shorter even for one layout, the browser would clamp the scroll position
 * and the page would jump.
 */
export function pinBook(book: HTMLElement, height: number): void {
  book.style.height = `${height}px`;
  book.style.overflow = "clip";
  book.style.overflowClipMargin = "8px";
}

export function unpinBook(book: HTMLElement): void {
  book.style.height = "";
  book.style.overflow = "";
  book.style.overflowClipMargin = "";
}

const HOLD_MIN_MS = 60;
const HOLD_MAX_MS = 1000;

export interface TransitionArgs {
  book: HTMLElement;
  layer: HTMLElement;
  /** The pages as they looked just before the change. */
  from: Shot;
  kind: Transition;
  /** Snapshot of the pages as they are now (called once the new page is ready). */
  captureTo: () => Shot | null;
  /** True once the new page has what it needs (no data still loading). */
  isReady: () => boolean;
}

/**
 * Hold the old page still (a static picture over the book, book height pinned) while
 * the new page loads its data and the window scrolls to the top, then turn the page
 * onto the finished new page.
 */
export function beginTransition({ book, layer, from, kind, captureTo, isReady }: TransitionArgs): void {
  cancelTransition();
  if (prefersReducedMotion() || typeof book.animate !== "function") {
    unpinBook(book);
    return;
  }

  const animations: Animation[] = [];
  let done = false;
  let raf = 0;

  // Pin first, before anything reads layout of the new page (see pinBook).
  pinBook(book, from.bookH);
  Object.assign(layer.style, {
    left: `${book.offsetLeft}px`,
    top: `${book.offsetTop}px`,
    width: `${book.offsetWidth}px`,
    height: `${from.bookH}px`,
    opacity: "1",
  });
  for (const p of from.pages) layer.append(place(p.node, p.x, p.y, p.w, p.h));

  const cleanup = () => {
    if (done) return;
    done = true;
    cancelAnimationFrame(raf);
    animations.forEach((a) => a.cancel());
    layer.replaceChildren();
    layer.style.opacity = "";
    book.style.height = "";
    book.style.overflow = "";
    book.style.overflowClipMargin = "";
  };
  cancelActive = cleanup;

  // Bring the top of the book into view first, smoothly.
  const bookTop = book.getBoundingClientRect().top + window.scrollY;
  const targetY = Math.max(0, bookTop - 80);
  if (window.scrollY > targetY + 4) window.scrollTo({ top: targetY, behavior: "smooth" });

  const started = performance.now();
  let lastY = window.scrollY;
  let still = 0;
  const wait = () => {
    if (done) return;
    const y = window.scrollY;
    still = Math.abs(y - lastY) < 0.5 ? still + 1 : 0;
    lastY = y;
    const elapsed = performance.now() - started;
    const scrolled = still >= 2 && y <= targetY + 4;
    if (elapsed > HOLD_MAX_MS || (elapsed > HOLD_MIN_MS && scrolled && isReady())) {
      play();
      return;
    }
    raf = requestAnimationFrame(wait);
  };
  raf = requestAnimationFrame(wait);

  const play = () => {
    // Measure the new page at its natural height, then keep the book pinned while we
    // animate the height ourselves.
    book.style.height = "";
    const toH = book.getBoundingClientRect().height;
    const to = captureTo();
    book.style.height = `${from.bookH}px`;
    layer.replaceChildren();
    if (!to) {
      cleanup();
      return;
    }
    to.bookH = toH;
    layer.style.height = `${Math.max(from.bookH, toH)}px`;
    animate(book, layer, from, to, kind, animations, () => done, cleanup);
  };
}

function animate(
  book: HTMLElement,
  layer: HTMLElement,
  from: Shot,
  to: Shot,
  kind: Transition,
  animations: Animation[],
  isDone: () => boolean,
  cleanup: () => void,
): void {
  const duration = flipDuration();
  const isFade = kind === "fade";

  // Growing happens during the turn (so new content is never clipped). Shrinking waits
  // until the page has landed, then the book settles to its new size: a book doesn't
  // change size mid-turn.
  const grows = to.bookH >= from.bookH;
  const heightDelay = isFade || grows ? 0 : duration;
  const heightMs = isFade ? 320 : grows ? duration : 420;
  const height = book.animate([{ height: `${from.bookH}px` }, { height: `${to.bookH}px` }], {
    duration: heightMs,
    delay: heightDelay,
    easing: grows ? ROTATE_EASE : "cubic-bezier(0.3, 0, 0.2, 1)",
    fill: "both",
  });
  animations.push(height);

  // Old pages left lying in the book shrink with it, so nothing hangs below the book.
  const shrinkWithBook = (p: PageShot) => {
    const target = Math.min(p.h, to.bookH - p.y);
    if (target >= p.h - 1) return;
    p.node.style.overflow = "hidden";
    animations.push(
      p.node.animate([{ height: `${p.h}px` }, { height: `${Math.max(0, target)}px` }], {
        duration: heightMs,
        delay: heightDelay,
        easing: grows ? ROTATE_EASE : "cubic-bezier(0.3, 0, 0.2, 1)",
        fill: "both",
      }),
    );
  };

  const finish = () => {
    if (isDone()) return;
    // Settle: fade the last frame into the live pages.
    const settle = layer.animate([{ opacity: 1 }, { opacity: 0 }], {
      duration: SETTLE_MS,
      easing: "ease-out",
      fill: "forwards",
    });
    animations.push(settle);
    settle.onfinish = cleanup;
  };

  const twoUp = from.wide && to.wide && from.pages.length === 2 && to.pages.length === 2;
  const oneUp = !from.wide && !to.wide && from.pages.length === 1 && to.pages.length === 1;

  if (isFade || (!twoUp && !oneUp)) {
    for (const p of from.pages) {
      layer.append(place(p.node, p.x, p.y, p.w, p.h));
      shrinkWithBook(p);
    }
    const a = layer.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 320, easing: "ease-out", fill: "forwards" });
    animations.push(a);
    a.onfinish = cleanup;
    return;
  }
  const forward = kind === "forward";
  let under: PageShot | null;
  let front: HTMLElement;
  let back: HTMLElement;
  let rect: { x: number; y: number; w: number; frontH: number; backH: number };
  let origin: "left" | "right";
  let fromDeg: number;
  let toDeg: number;
  let fadeKeys: Keyframe[] | null = null;

  if (twoUp) {
    const [oL, oR] = from.pages as [PageShot, PageShot];
    const [nL, nR] = to.pages as [PageShot, PageShot];
    if (forward) {
      under = oL;
      front = oR.node;
      back = nL.node;
      rect = { x: oR.x, y: oR.y, w: oR.w, frontH: oR.h, backH: nL.h };
      origin = "left";
      fromDeg = 0;
      toDeg = -180;
    } else {
      under = oR;
      front = oL.node;
      back = nR.node;
      rect = { x: oL.x, y: oL.y, w: oL.w, frontH: oL.h, backH: nR.h };
      origin = "right";
      fromDeg = 0;
      toDeg = 180;
    }
  } else {
    const [o] = from.pages as [PageShot];
    const [n] = to.pages as [PageShot];
    origin = "left";
    back = div("book-flip-paper");
    if (forward) {
      under = null;
      front = o.node;
      rect = { x: o.x, y: o.y, w: o.w, frontH: o.h, backH: o.h };
      fromDeg = 0;
      toDeg = -180;
      fadeKeys = [{ opacity: 1 }, { opacity: 1, offset: 0.72 }, { opacity: 0 }];
    } else {
      under = o;
      front = n.node;
      rect = { x: n.x, y: n.y, w: n.w, frontH: n.h, backH: n.h };
      fromDeg = -180;
      toDeg = 0;
      fadeKeys = [{ opacity: 0 }, { opacity: 1, offset: 0.28 }, { opacity: 1 }];
    }
  }

  // The page underneath that the turning leaf will cover at the end.
  if (under) {
    layer.append(place(under.node, under.x, under.y, under.w, under.h));
    shrinkWithBook(under);
  }

  // A soft shadow cast on the page being revealed.
  const cast = div(`book-flip-cast book-flip-cast-${origin}`);
  // The revealed page is the live new page, so the shadow is as tall as the new book.
  place(cast, rect.x, rect.y, rect.w, Math.max(0, to.bookH - rect.y));
  layer.append(cast);
  animations.push(
    cast.animate([{ opacity: 0 }, { opacity: 1, offset: 0.45 }, { opacity: 0 }], {
      duration,
      easing: "ease-in-out",
      fill: "forwards",
    }),
  );

  // The turning leaf with its two faces.
  const leaf = div("book-flip-leaf");
  place(leaf, rect.x, rect.y, rect.w, Math.max(rect.frontH, rect.backH));
  leaf.style.transformOrigin = `${origin} center`;
  place(front, 0, 0, rect.w, rect.frontH);
  front.classList.add("book-flip-face");
  place(back, 0, 0, rect.w, rect.backH);
  back.classList.add("book-flip-face", "book-flip-back");
  const frontShade = div(`book-flip-shade book-flip-shade-${origin}`);
  const backShade = div(`book-flip-shade book-flip-shade-${origin === "left" ? "right" : "left"}`);
  front.append(frontShade);
  back.append(backShade);
  leaf.append(front, back);
  layer.append(leaf);

  const turn = leaf.animate(
    [{ transform: `rotateY(${fromDeg}deg)` }, { transform: `rotateY(${toDeg}deg)` }],
    { duration, easing: ROTATE_EASE, fill: "forwards" },
  );
  animations.push(turn);
  const lifting = fromDeg === 0;
  animations.push(
    frontShade.animate(
      lifting
        ? [{ opacity: 0 }, { opacity: 1, offset: 0.5 }, { opacity: 1 }]
        : [{ opacity: 1 }, { opacity: 1, offset: 0.5 }, { opacity: 0 }],
      { duration, easing: "linear", fill: "forwards" },
    ),
    backShade.animate(
      lifting
        ? [{ opacity: 1 }, { opacity: 1, offset: 0.5 }, { opacity: 0 }]
        : [{ opacity: 0 }, { opacity: 1, offset: 0.5 }, { opacity: 1 }],
      { duration, easing: "linear", fill: "forwards" },
    ),
  );
  if (fadeKeys) {
    animations.push(leaf.animate(fadeKeys, { duration, easing: "linear", fill: "forwards" }));
  }
  // Settle once the page has landed and the book has reached its new size.
  turn.onfinish = () => {
    height.finished.then(finish, () => undefined);
  };
}

/** Turn immediately with both snapshots in hand (no waiting). */
export function runTransition(args: {
  book: HTMLElement;
  layer: HTMLElement;
  from: Shot;
  to: Shot;
  kind: Transition;
}): void {
  beginTransition({ ...args, captureTo: () => args.to, isReady: () => true });
}
