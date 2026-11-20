// For Font, Metadata, Theme color

import type { Metadata, Viewport } from "next";
import { Be_Vietnam_Pro } from "next/font/google";
import { COLORS } from "@/lib/colors";
import "./globals.css";
import DashboardShell from "@/components/DashboardShell";

const beVietnamPro = Be_Vietnam_Pro({
  variable: "--font-be-vietnam",
  subsets: ["latin", "vietnamese"],
  weight: ["200", "300", "400", "500", "600", "700"],
  display: "swap",
});

export const viewport: Viewport = {
  themeColor: COLORS.ink,
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  title: "Home Solar",
  description: "Solar Monitoring Dashboard",
  manifest: "./manifest.json",
  appleWebApp: {
    capable: true,
    title: "Home Solar",
    statusBarStyle: "black-translucent",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={beVietnamPro.variable} suppressHydrationWarning>
      <head>
        {/* Load Font Awesome hoặc link CSS vendor nếu vẫn dùng file tĩnh */}
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
        {/* Apply the saved text size before first paint, so the page doesn't jump. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var s=localStorage.getItem("fontscale");if(s==="lg"||s==="xl")document.documentElement.setAttribute("data-fontscale",s)}catch(e){}`,
          }}
        />
      </head>
      <body suppressHydrationWarning>
        <DashboardShell>{children}</DashboardShell>
      </body>
    </html>
  );
}