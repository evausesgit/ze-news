"use client";

import { useEffect, useState } from "react";
import { formatDate, labelName, type Lang, type LinkItem } from "@/lib/api";

// Contenu d'une carte. Les gestes (swipe, double-tap) sont gérés par le parent :
// le deck et la grille de recherche n'ont pas les mêmes besoins.
export default function Card({
  link,
  defaultLang,
  onToggleRead,
  onThemeClick,
}: {
  link: LinkItem;
  defaultLang: Lang;
  onToggleRead?: () => void;
  onThemeClick?: (theme: string) => void;
}) {
  // Langue propre à la carte, qui suit la préférence globale tant qu'on n'y touche pas.
  const [lang, setLang] = useState<Lang>(defaultLang);
  useEffect(() => setLang(defaultLang), [defaultLang]);

  const summary =
    (lang === "fr" ? link.summary_fr : link.summary_en) ??
    link.summary_en ??
    link.summary_fr ??
    (lang === "fr" ? "Résumé en cours de préparation…" : "Summary on its way…");
  const read = Boolean(link.seen_at || link.opened_at);
  const label = link.label ?? "PENDING";

  return (
    <article
      className={`card label-${label.toLowerCase()} ${read ? "is-read" : ""}`}
      data-read={read}
    >
      <header className="card-head">
        <span className="chip">{labelName(link.label, lang)}</span>
        {link.opened_at ? (
          <span className="state state-opened">{lang === "fr" ? "ouvert" : "opened"}</span>
        ) : read ? (
          <span className="state">{lang === "fr" ? "lu" : "read"}</span>
        ) : (
          <span className="state state-new">{lang === "fr" ? "nouveau" : "new"}</span>
        )}
        <div
          className="lang-toggle"
          role="group"
          aria-label="Langue"
          onPointerUp={(e) => e.stopPropagation()}
          onPointerDown={(e) => e.stopPropagation()}
        >
          {(["en", "fr"] as Lang[]).map((l) => (
            <button
              key={l}
              type="button"
              aria-pressed={lang === l}
              onClick={() => setLang(l)}
            >
              {l.toUpperCase()}
            </button>
          ))}
        </div>
      </header>

      <p className="summary">{summary}</p>

      {link.title && <p className="title">{link.title}</p>}

      {link.themes.length > 0 && (
        <ul className="themes">
          {link.themes.map((t) => (
            <li key={t}>
              {onThemeClick ? (
                <button
                  type="button"
                  onPointerDown={(e) => e.stopPropagation()}
                  onPointerUp={(e) => e.stopPropagation()}
                  onClick={() => onThemeClick(t)}
                >
                  #{t}
                </button>
              ) : (
                <span>#{t}</span>
              )}
            </li>
          ))}
        </ul>
      )}

      <footer className="card-foot">
        <span className="source">
          {link.kind === "tweet" ? "𝕏 " : ""}
          {link.author ?? link.domain}
        </span>
        <span className="meta">
          {link.shared_by && (lang === "fr" ? `via ${link.shared_by} · ` : `via ${link.shared_by} · `)}
          {formatDate(link.shared_at, lang)}
        </span>
        {onToggleRead && (
          <button
            type="button"
            className="mark"
            onPointerDown={(e) => e.stopPropagation()}
            onPointerUp={(e) => e.stopPropagation()}
            onClick={onToggleRead}
          >
            {read
              ? lang === "fr" ? "Marquer non lu" : "Mark unread"
              : lang === "fr" ? "Marquer lu" : "Mark read"}
          </button>
        )}
      </footer>
    </article>
  );
}
