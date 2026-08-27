import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Financial AI Operator | Autonomous FinOps Platform",
  description: "Enterprise AI-powered financial operations, reconciliation, and anomaly detection platform.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased selection:bg-emerald-500 selection:text-black">
        {children}
      </body>
    </html>
  );
}
