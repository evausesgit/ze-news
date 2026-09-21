"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { usePrefs } from "@/lib/prefs";
import { CHANGED_EVENT, getFacets, type Lang } from "@/lib/api";

const REFRESH_MS = 60_000;

// Nombre de cartes non lues : pastille sur « Fil » et préfixe du titre de
// l'onglet (« (12) Ze News »). Rafraîchi chaque minute — le worker ajoute des
// liens toutes les 10 min —, au retour sur l'onglet, et dès qu'une action
// (lu, ouvert, résumé demandé) le signale.
function useUnreadCount(enabled: boolean): number | null {
  const [unread, setUnread] = useState<number | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    const refresh = () =>
      getFacets()
        .then((f) => alive && setUnread(f.unread))
        .catch(() => {});
    refresh();
    const timer = window.setInterval(refresh, REFRESH_MS);
    const onVisible = () => document.visibilityState === "visible" && refresh();
    window.addEventListener(CHANGED_EVENT, refresh);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      alive = false;
      window.clearInterval(timer);
      window.removeEventListener(CHANGED_EVENT, refresh);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [enabled]);

  useEffect(() => {
    if (unread === null) return;
    document.title = unread > 0 ? `(${unread}) Ze News` : "Ze News";
  }, [unread]);

  return unread;
}

export default function Nav() {
  const path = usePathname();
  const { lang, setLang, me } = usePrefs();
  const { signOutUser } = useAuth();
  const unread = useUnreadCount(path !== "/login");
  if (path === "/login") return null;
  const fr = lang === "fr";
  const badge = unread && unread > 0 ? (unread > 99 ? "99+" : String(unread)) : null;
  return (
    <nav className="nav">
      <Link href="/" className="brand">
        <span className="brand-dot" aria-hidden="true" />
        <span className="brand-text">Ze News</span>
      </Link>
      <div className="nav-links">
        <Link href="/" aria-current={path === "/" ? "page" : undefined}>
          {fr ? "Fil" : "Feed"}
          {badge && (
            <span
              className="badge"
              aria-label={fr ? `${unread} non lus` : `${unread} unread`}
            >
              {badge}
            </span>
          )}
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
