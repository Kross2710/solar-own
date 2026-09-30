// For Font, Metadata, Theme color

import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const viewport: Viewport = {
  themeColor: "#04060c",
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
    <html lang="en" data-view="overview" suppressHydrationWarning>
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
        {children}
      </body>
    </html>
  );
}