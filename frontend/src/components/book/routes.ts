/** Reading order of the book. Decides which way a page turns between two routes. */

export type TurnDirection = "forward" | "back";
export type Transition = TurnDirection | "fade";

const ORDER = [
  "/signup",
  "/login",
  "/onboarding",
  "/",
  "/checkin",
  "/history",
  "/twin",
  "/insights",
  "/settings",
] as const;

/** Routes without chapter tabs (signed out or still onboarding). */
export const PUBLIC_ROUTES = ["/login", "/signup", "/onboarding"];

export function routeRank(pathname: string): number {
  if (pathname === "/") return ORDER.indexOf("/");
  for (let i = ORDER.length - 1; i >= 0; i--) {
    const r = ORDER[i]!;
    if (r !== "/" && (pathname === r || pathname.startsWith(`${r}/`))) return i;
  }
  return ORDER.length; // unknown pages sit at the end of the book
}

/**
 * Which way to turn when going from `from` to `to`. Going further into the book turns
 * forward (the right page turns over to the left), going back turns back. The same
 * route re-rendering cross-fades instead. Check-in pages for different days turn by date.
 */
export function transitionBetween(from: string, to: string): Transition {
  if (from === to) return "fade";
  const a = routeRank(from);
  const b = routeRank(to);
  if (a !== b) return b > a ? "forward" : "back";
  return to > from ? "forward" : "back";
}
