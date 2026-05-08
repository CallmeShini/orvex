import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Orvex",
  description: "AI-assisted photovoltaic inspection triage for solar operations teams."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
