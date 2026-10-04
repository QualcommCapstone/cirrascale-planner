import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "next-themes";
import { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Cirrascale Planner",
  description:
    "Turn any prompt into a structured, step-by-step plan — powered by the Qualcomm AI Inference Suite on Cirrascale.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
