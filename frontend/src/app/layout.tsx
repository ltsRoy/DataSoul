import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DataSoul — Upload Any Messy Dataset. Leave With Decisions.",
  description:
    "DataSoul is an intelligent universal data readiness and business intelligence platform that transforms messy raw datasets into trusted, analytics-ready, AI-ready, and boardroom-ready assets.",
  keywords: [
    "data quality",
    "data cleaning",
    "business intelligence",
    "AI data platform",
    "data preprocessing",
    "threat detection",
    "data readiness",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased" suppressHydrationWarning>
        {/* Mesh gradient background */}
        <div className="mesh-gradient" />
        <div className="grid-pattern" />

        {/* Main content */}
        <div className="relative z-10">{children}</div>
      </body>
    </html>
  );
}
