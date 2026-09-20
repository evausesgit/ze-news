import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Nav from "./Nav";
import { AuthProvider } from "@/lib/auth-context";
import { PrefsProvider } from "@/lib/prefs";

const inter = Inter({ subsets: ["latin"], variable: "--ff-sans", display: "swap" });

export const metadata: Metadata = {
  title: "Ze News",
  description: "Les liens partagés sur Telegram, résumés et rangés.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f5f2" },
    { media: "(prefers-color-scheme: dark)", color: "#141414" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr" className={inter.variable}>
      <body>
        <AuthProvider>
          <PrefsProvider>
            <Nav />
            {children}
          </PrefsProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
