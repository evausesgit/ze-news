"use client";

// Le fil : une pile de cartes.
//   swipe gauche  (ou →) : carte suivante, la carte quittée est marquée « lue » ;
//   swipe droite  (ou ←) : carte précédente ;
//   double-clic / double-tap (ou Entrée) : ouvre la source, marquée « ouverte ».
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Card from "./Card";
import {
  getFacets,
  getLinks,
  markOpened,
  markSeen,
  markUnread,
  type Facets,
  type LinkItem,
} from "@/lib/api";
import { usePrefs } from "@/lib/prefs";
import { useDoubleTap } from "@/lib/useDoubleTap";

const PAGE = 30;
const SWIPE_PX = 90;

type Mode = "unread" | "all";

export default function FeedPage() {
  const { lang } = usePrefs();
  const router = useRouter();
  const fr = lang === "fr";
  const [mode, setMode] = useState<Mode>("unread");
  const [items, setItems] = useState<LinkItem[]>([]);
  const [total, setTotal] = useState(0);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [facets, setFacets] = useState<Facets | null>(null);
  const [drag, setDrag] = useState<{ dx: number; leaving: 0 | 1 | -1 }>({ dx: 0, leaving: 0 });
  const start = useRef<{ x: number; y: number; id: number } | null>(null);
  const loadingMore = useRef(false);

  const load = useCallback(async (m: Mode) => {
    setLoading(true);
    setError(null);
    try {
      const page = await getLinks({ read: m, limit: PAGE });
      setItems(page.items);
      setTotal(page.total);
      setIndex(0);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(mode);
  }, [mode, load]);

  const refreshFacets = useCallback(() => {
    getFacets().then(setFacets).catch(() => {});
  }, []);

  useEffect(refreshFacets, [mode, refreshFacets]);

  // Charge la page suivante quand on approche du bout de la pile. En mode
  // « non lus », les cartes qu'on vient de lire sortent du filtre côté serveur :
  // le décalage = cartes chargées ENCORE non lues (les doublons sont écartés).
  useEffect(() => {
    if (loadingMore.current || items.length >= total || index < items.length - 5) return;
    loadingMore.current = true;
    const offset =
      mode === "unread" ? items.filter((i) => !i.seen_at && !i.opened_at).length : items.length;
    getLinks({ read: mode, limit: PAGE, offset })
      .then((page) => {
        setItems((prev) => {
          const known = new Set(prev.map((i) => i.id));
          const fresh = page.items.filter((i) => !known.has(i.id));
          if (fresh.length === 0) setTotal(prev.length); // plus rien à charger
          return [...prev, ...fresh];
        });
      })
      .finally(() => {
        loadingMore.current = false;
      });
  }, [index, items, total, mode]);

  const replace = (updated: LinkItem) =>
    setItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));

  // Réponse du serveur : on garde sa version de la carte et on recompte.
  const saved = useCallback(
    (updated: LinkItem) => {
      replace(updated);
      refreshFacets();
    },
    [refreshFacets],
  );

  const current = items[index];

  const next = useCallback(() => {
    const cur = items[index];
    if (!cur) return;
    if (!cur.seen_at) {
      // Optimiste : la couleur change tout de suite, le serveur suit.
      replace({ ...cur, seen_at: new Date().toISOString() });
      markSeen(cur.id).then(saved).catch(() => {});
    }
    setIndex((i) => Math.min(i + 1, items.length));
  }, [items, index, saved]);

  const prev = useCallback(() => setIndex((i) => Math.max(i - 1, 0)), []);

  const open = useCallback(() => {
    const cur = items[index];
    if (!cur) return;
    window.open(cur.url, "_blank", "noopener,noreferrer");
    const now = new Date().toISOString();
    replace({ ...cur, opened_at: now, seen_at: cur.seen_at ?? now });
    markOpened(cur.id).then(saved).catch(() => {});
  }, [items, index, saved]);

  const toggleRead = (link: LinkItem) => {
    const read = link.seen_at || link.opened_at;
    replace({ ...link, seen_at: read ? null : new Date().toISOString(), opened_at: read ? null : link.opened_at });
    (read ? markUnread(link.id) : markSeen(link.id)).then(saved).catch(() => {});
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.closest("input, textarea, select")) return;
      if (e.key === "ArrowRight" || e.key === "j") next();
      else if (e.key === "ArrowLeft" || e.key === "k") prev();
      else if (e.key === "Enter" || e.key === "o") open();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev, open]);

  const doubleTap = useDoubleTap(open);

  function onPointerDown(e: React.PointerEvent) {
    if (e.button !== 0) return;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    start.current = { x: e.clientX, y: e.clientY, id: e.pointerId };
  }
  function onPointerMove(e: React.PointerEvent) {
    if (!start.current || start.current.id !== e.pointerId) return;
    setDrag({ dx: e.clientX - start.current.x, leaving: 0 });
  }
  function onPointerUp(e: React.PointerEvent) {
    if (!start.current) return;
    const dx = e.clientX - start.current.x;
    const dy = e.clientY - start.current.y;
    start.current = null;
    if (Math.abs(dx) > SWIPE_PX && Math.abs(dx) > Math.abs(dy)) {
      const dir = dx < 0 ? -1 : 1;
      if (dir === 1 && index === 0) {
        setDrag({ dx: 0, leaving: 0 });
        return;
      }
      setDrag({ dx, leaving: dir });
      window.setTimeout(() => {
        if (dir === -1) next();
        else prev();
        setDrag({ dx: 0, leaving: 0 });
      }, 180);
      return;
    }
    setDrag({ dx: 0, leaving: 0 });
    if (Math.abs(dx) < 8 && Math.abs(dy) < 8) doubleTap(e);
  }

  const dx = drag.leaving ? drag.leaving * 600 : drag.dx;
  const topStyle = {
    transform: `translateX(${dx}px) rotate(${dx / 24}deg)`,
    transition: start.current ? "none" : "transform 180ms ease-out",
  };

  return (
    <main className="page feed">
      <div className="feed-bar">
        <div className="segmented" role="group">
          <button type="button" aria-pressed={mode === "unread"} onClick={() => setMode("unread")}>
            {fr ? "Non lus" : "Unread"}
            {facets ? <span className="count">{facets.unread}</span> : null}
          </button>
          <button type="button" aria-pressed={mode === "all"} onClick={() => setMode("all")}>
            {fr ? "Tout" : "All"}
            {facets ? <span className="count">{facets.total}</span> : null}
          </button>
        </div>
        {items.length > 0 && index < items.length && (
          <span className="position">
            {index + 1} / {total}
          </span>
        )}
      </div>

      {facets && facets.pending > 0 && (
        <p className="pending-note">
          {fr
            ? `${facets.pending} lien(s) en cours de résumé par Codex…`
            : `${facets.pending} link(s) being summarised by Codex…`}
        </p>
      )}

      <div className="deck" aria-live="polite">
        {loading ? (
          <p className="empty">{fr ? "Chargement…" : "Loading…"}</p>
        ) : error ? (
          <p className="empty error">{error}</p>
        ) : !current ? (
          <div className="empty">
            <p className="empty-title">
              {mode === "unread"
                ? fr ? "Tout est lu." : "All caught up."
                : fr ? "Aucun lien pour l'instant." : "No links yet."}
            </p>
            <p>
              {fr
                ? "Les nouveaux liens de Telegram arrivent ici automatiquement."
                : "New links from Telegram land here automatically."}
            </p>
            {index > 0 && (
              <button type="button" className="ghost" onClick={prev}>
                {fr ? "← Revenir à la dernière carte" : "← Back to last card"}
              </button>
            )}
          </div>
        ) : (
          <>
            {items.slice(index + 1, index + 3).reverse().map((l, i, arr) => (
              <div
                key={l.id}
                className="deck-slot behind"
                style={{ transform: `translateY(${(arr.length - i) * 10}px) scale(${1 - (arr.length - i) * 0.04})` }}
                aria-hidden="true"
              >
                <Card link={l} defaultLang={lang} />
              </div>
            ))}
            <div
              key={current.id}
              className="deck-slot top"
              style={topStyle}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerCancel={() => {
                start.current = null;
                setDrag({ dx: 0, leaving: 0 });
              }}
              title={fr ? "Double-clic pour ouvrir la source" : "Double-click to open the source"}
            >
              <Card
                link={current}
                defaultLang={lang}
                onToggleRead={() => toggleRead(current)}
                onThemeClick={(t) => router.push(`/recherche?theme=${encodeURIComponent(t)}`)}
              />
            </div>
          </>
        )}
      </div>

      {current && (
        <div className="deck-actions">
          <button type="button" className="ghost" onClick={prev} disabled={index === 0}>
            ←
          </button>
          <button type="button" onClick={open}>
            {fr ? "Ouvrir la source" : "Open source"}
          </button>
          <button type="button" className="ghost" onClick={next}>
            →
          </button>
        </div>
      )}
      <p className="hint">
        {fr
          ? "Swipe à gauche : suivante · à droite : précédente · double-clic : ouvrir"
          : "Swipe left: next · right: previous · double-click: open"}
      </p>
    </main>
  );
}
