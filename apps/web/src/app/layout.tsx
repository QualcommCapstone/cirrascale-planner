import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { ThemeProvider } from "next-themes";
import { ReactNode } from "react";

// Self-hosted (next/font/local) so builds are deterministic and never depend on
// fetching Google Fonts at build time. Variable fonts cover the full weight range.
const sans = localFont({
  src: "./fonts/inter-latin.woff2",
  variable: "--font-sans",
  weight: "100 900",
  display: "swap",
});

// Bold, tight display face for headlines (see font-display in tailwind.config.ts).
const display = localFont({
  src: "./fonts/inter-tight-latin.woff2",
  variable: "--font-display",
  weight: "100 900",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Cirrascale Planner",
  description:
    "Describe a trip in a sentence and see it as real places, photos and a route on a globe. Powered by the Qualcomm AI Inference Suite on Cirrascale.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable}`} suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false} disableTransitionOnChange>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
