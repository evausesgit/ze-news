"use client";

import { useEffect, useRef, useState } from "react";
import { formatDate, labelName, type Lang, type LinkItem } from "@/lib/api";

// Contenu d'une carte. Les gestes (swipe, double-tap) sont gérés par le parent :
// le deck et la grille de recherche n'ont pas les mêmes besoins.
export default function Card({
  link,
  defaultLang,
  onToggleRead,
  onThemeClick,
  onSummarize,
}: {
  link: LinkItem;
  defaultLang: Lang;
  onToggleRead?: () => void;
  onThemeClick?: (theme: string) => void;
  // Lien ancien « en sommeil » : demande son résumé au worker.
  onSummarize?: () => void;
}) {
  // Langue propre à la carte, qui suit la préférence globale tant qu'on n'y touche pas.
  const [lang, setLang] = useState<Lang>(defaultLang);
  useEffect(() => setLang(defaultLang), [defaultLang]);

  const fr = lang === "fr";
  const placeholder =
    link.status === "dormant"
      ? fr
        ? "Lien ancien, pas encore résumé."
        : "Older link, not summarised yet."
      : fr
        ? "Résumé en cours de préparation…"
        : "Summary on its way…";
  const summary =
    (fr ? link.summary_fr : link.summary_en) ?? link.summary_en ?? link.summary_fr ?? placeholder;
  // Résumé = phrase factuelle, puis (après une ligne vide) l'interprétation.
  const [fact, ...rest] = summary.split(/\n\s*\n/);
  const interpretation = rest.join("\n\n").trim();
  // Texte qui dépasse de la carte : fondu en bas tant qu'il reste à lire.
  const bodyRef = useRef<HTMLDivElement>(null);
  const [more, setMore] = useState(false);
  const checkMore = () => {
    const el = bodyRef.current;
    if (el) setMore(el.scrollHeight - el.scrollTop - el.clientHeight > 4);
  };
  useEffect(() => {
    const el = bodyRef.current;
    if (!el) return;
    checkMore();
    const ro = new ResizeObserver(checkMore);
    ro.observe(el);
    return () => ro.disconnect();
  }, [summary]);
  const read = Boolean(link.seen_at || link.opened_at);
  const label = link.label ?? "PENDING";

  return (
    <article
      className={`card label-${label.toLowerCase()} ${read ? "is-read" : ""}`}
      data-read={read}
    >
      <header className="card-head">
        <span className="chip">
          {link.status === "dormant" ? (fr ? "Ancien" : "Older") : labelName(link.label, lang)}
        </span>
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

      <div ref={bodyRef} className={`card-body ${more ? "has-more" : ""}`} onScroll={checkMore}>
        <p className="summary">{fact}</p>
        {interpretation && <p className="interpretation">{interpretation}</p>}
        {link.title && <p className="title">{link.title}</p>}
      </div>

      {link.status === "dormant" && onSummarize && (
        <button
          type="button"
          className="summarize"
          onPointerDown={(e) => e.stopPropagation()}
          onPointerUp={(e) => e.stopPropagation()}
          onClick={onSummarize}
        >
          {fr ? "Résumer ce lien" : "Summarise this link"}
        </button>
      )}
      {link.status === "pending" && !link.summary_en && (
        <p className="title">
          {fr
            ? "Demandé : résumé au prochain passage du worker (10 min au plus)."
            : "Requested: summarised on the worker's next pass (within 10 min)."}
        </p>
      )}

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
