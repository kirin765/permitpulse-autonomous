import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PermitPulse",
  description: "Zero-human-ops STR compliance intelligence platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
