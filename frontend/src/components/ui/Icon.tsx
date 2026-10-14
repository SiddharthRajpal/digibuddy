/**
 * Icon set for the DigiBuddy storybook: 24px, 2px round strokes, drawn in
 * `currentColor` (set the color to `stroke` or `ink` on the parent).
 */
import type { SVGProps } from "react";

const PATHS = {
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6" />
    </>
  ),
  golden: (
    <>
      <circle cx="12" cy="13" r="4.5" />
      <path d="M12 3v2.5M4.2 6.5l1.8 1.6M19.8 6.5 18 8.1M2.5 13H5M19 13h2.5M7 20.5h10" />
    </>
  ),
  cloud: <path d="M7 18.5h10.2a3.8 3.8 0 0 0 .4-7.6 5.5 5.5 0 0 0-10.6 1.4A3.1 3.1 0 0 0 7 18.5Z" />,
  drizzle: (
    <>
      <path d="M7 15h10.2a3.6 3.6 0 0 0 .4-7.2 5.3 5.3 0 0 0-10.2 1.3A3 3 0 0 0 7 15Z" />
      <path d="M9 18.5v1.5M13 18.5v1.5" />
    </>
  ),
  rain: (
    <>
      <path d="M7 14h10.2a3.6 3.6 0 0 0 .4-7.2 5.3 5.3 0 0 0-10.2 1.3A3 3 0 0 0 7 14Z" />
      <path d="M8.5 17l-1 3M12.5 17l-1 3M16.5 17l-1 3" />
    </>
  ),
  moon: <path d="M19.5 14.5A7.5 7.5 0 0 1 9.5 4.5a7.5 7.5 0 1 0 10 10Z" />,
  "arrow-left": <path d="M15 5l-7 7 7 7" />,
  "arrow-right": <path d="M9 5l7 7-7 7" />,
  "arrow-up": <path d="M12 19V5M6 11l6-6 6 6" />,
  "arrow-down": <path d="M12 5v14M6 13l6 6 6-6" />,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  plus: <path d="M12 5v14M5 12h14" />,
  pencil: <path d="M4 20l1-4.5L15.5 5a2.1 2.1 0 0 1 3 3L8 18.5 4 20ZM13.5 7l3 3" />,
  trash: <path d="M5 7h14M9.5 7V5h5v2M7 7l1 12.5h8L17 7M10.5 10.5v6M13.5 10.5v6" />,
  download: <path d="M12 4v11M7 10.5l5 5 5-5M5 19.5h14" />,
  heart: <path d="M12 19.5s-7.5-4.4-7.5-9.7A4.1 4.1 0 0 1 12 7.6a4.1 4.1 0 0 1 7.5 2.2c0 5.3-7.5 9.7-7.5 9.7Z" />,
  phone: <path d="M8 3.5H5.5a1.5 1.5 0 0 0-1.5 1.7A15.5 15.5 0 0 0 18.8 20a1.5 1.5 0 0 0 1.7-1.5V16l-4-1.5-2 2a11 11 0 0 1-5.5-5.5l2-2L9.5 5Z" />,
  link: <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" />,
  book: <path d="M12 6.5c-2-1.5-5-2-8-1.5v13c3-.5 6 0 8 1.5 2-1.5 5-2 8-1.5V5c-3-.5-6 0-8 1.5ZM12 6.5v13" />,
  chart: <path d="M4 4v16h16M7.5 15l3.5-4 3 2.5 4.5-6" />,
  sparkle: <path d="M12 3.5l1.8 5.2 5.2 1.8-5.2 1.8L12 17.5l-1.8-5.2L5 10.5l5.2-1.8L12 3.5ZM18.5 16l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7.7-1.8Z" />,
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M5.6 18.4l1.8-1.8M16.6 7.4l1.8-1.8" />
    </>
  ),
  sleep: <path d="M18.5 14.5a7 7 0 0 1-9-9 7 7 0 1 0 9 9ZM15 4h4l-4 4.5h4" />,
  shoe: <path d="M3.5 16.5V9l4 1.5 2.5-3 9 6.5c1 .7 1.5 1.6 1.5 2.5v.5h-17ZM3.5 19.5h17" />,
  tree: <path d="M12 21v-5.5M12 3.5 6 12h3l-3.5 4.5h13L15 12h3L12 3.5Z" />,
  screen: <path d="M4 5.5h16v10H4ZM9 19.5h6M12 15.5v4" />,
  cup: <path d="M5 8h11v5.5A4.5 4.5 0 0 1 11.5 18h-2A4.5 4.5 0 0 1 5 13.5ZM16 9.5h1.5a2.5 2.5 0 0 1 0 5H16M8 3.5v2M11 3.5v2" />,
  glass: <path d="M7 3.5h10l-1.5 8a3.5 3.5 0 0 1-7 0ZM12 15v5.5M8.5 20.5h7" />,
  bowl: <path d="M3.5 11h17a8.5 8.5 0 0 1-17 0ZM9 19.5h6M14 4l-3 7M17.5 5l-4.5 6" />,
  people: (
    <>
      <circle cx="9" cy="8.5" r="3" />
      <circle cx="16.5" cy="9.5" r="2.5" />
      <path d="M3.5 19.5a5.5 5.5 0 0 1 11 0M14.5 14.6a4.5 4.5 0 0 1 6 4.9" />
    </>
  ),
  briefcase: <path d="M4 8h16v11H4ZM9 8V5.5h6V8M4 13h16" />,
  tag: <path d="M3.5 12.5V4h8.5l8.5 8.5-8.5 8.5ZM8 8.5h.01" />,
  note: <path d="M5 4h14v11l-5 5H5ZM14 20v-5h5M8.5 9h7M8.5 12.5h4" />,
  ruler: <path d="M3.5 15.5 15.5 3.5l5 5-12 12ZM7 12l2 2M10 9l2 2M13 6l2 2" />,
  lock: <path d="M6 11h12v9.5H6ZM8.5 11V8a3.5 3.5 0 0 1 7 0v3" />,
} as const;

export type IconName = keyof typeof PATHS;

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: IconName;
  size?: number;
  /** Accessible label. Omit for decorative icons (they are hidden from screen readers). */
  label?: string;
}

export function Icon({ name, size = 24, label, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
      {...rest}
    >
      {PATHS[name]}
    </svg>
  );
}
