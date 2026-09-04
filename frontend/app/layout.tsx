import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter } from "next/font/google";

import InlineScript from "@/components/shared/InlineScript";
import { THEME_INIT_SCRIPT } from "@/lib/theme";

import "./globals.css";

// Spec §12.3: one sans face for UI, one mono face for every metric value.
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  weight: ["400", "500"],
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Textropy",
  description: "Linguistic analysis and comparison of text.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    /*
      `data-theme` is the server's guess — `:root`'s own palette — and the script below
      corrects it while the HTML is still parsing, before the first paint. That write is a
      DOM mutation React did not make, hence `suppressHydrationWarning`: without it React
      treats the attribute as a mismatch and discards the correction.
    */
    <html
      lang="en"
      data-theme="light"
      suppressHydrationWarning
      className={`${inter.variable} ${plexMono.variable} h-full antialiased`}
    >
      <head>
        <InlineScript html={THEME_INIT_SCRIPT} />
      </head>
      <body className="font-sans text-ink h-full overflow-hidden">{children}</body>
    </html>
  );
}
