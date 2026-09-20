"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { usePrefs } from "@/lib/prefs";
import type { Lang } from "@/lib/api";

export default function Nav() {
  const path = usePathname();
  const { lang, setLang, me } = usePrefs();
  const { signOutUser } = useAuth();
  if (path === "/login") return null;
  const fr = lang === "fr";
  return (
    <nav className="nav">
      <Link href="/" className="brand">
        <span className="brand-dot" aria-hidden="true" />
        <span className="brand-text">Ze News</span>
      </Link>
      <div className="nav-links">
        <Link href="/" aria-current={path === "/" ? "page" : undefined}>
          {fr ? "Fil" : "Feed"}
        </Link>
        <Link href="/recherche" aria-current={path.startsWith("/recherche") ? "page" : undefined}>
          {fr ? "Recherche" : "Search"}
        </Link>
      </div>
      <div className="nav-right">
        <div className="lang-toggle" role="group" aria-label={fr ? "Langue par défaut" : "Default language"}>
          {(["en", "fr"] as Lang[]).map((l) => (
            <button key={l} type="button" aria-pressed={lang === l} onClick={() => setLang(l)}>
              {l.toUpperCase()}
            </button>
          ))}
        </div>
        <button type="button" className="ghost" onClick={signOutUser} title={me?.email}>
          {fr ? "Déconnexion" : "Sign out"}
        </button>
      </div>
    </nav>
  );
}
