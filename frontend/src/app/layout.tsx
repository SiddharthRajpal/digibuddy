import type { Metadata, Viewport } from "next";
import { Gaegu, Grandstander, Literata } from "next/font/google";
import type { ReactNode } from "react";

import { Providers } from "@/components/Providers";
import { THEME_BOOT_SCRIPT } from "@/lib/theme";
import "@/styles/globals.css";

const grandstander = Grandstander({
  subsets: ["latin"],
  weight: ["600", "700", "800"],
  variable: "--font-grandstander",
  display: "swap",
});
const literata = Literata({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-literata",
  display: "swap",
});
const gaegu = Gaegu({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-gaegu",
  display: "swap",
});

export const metadata: Metadata = {
  title: "DigiBuddy",
  description: "A storybook about how you feel. One check-in is one page.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      data-theme="daylight"
      className={`${grandstander.variable} ${literata.variable} ${gaegu.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
