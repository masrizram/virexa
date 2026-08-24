import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Virexa Control Center",
  description: "Autonomous Content Operating System — control plane",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
