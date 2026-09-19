"use client";

// Recherche dans la base : texte libre, labels (plusieurs = OU), thèmes
// (plusieurs = ET), période de partage, état de lecture. Les filtres sont
// reflétés dans l'URL : une recherche se partage et se met en favori.
import { Suspense, useCallback, useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Card from "../Card";
import {
  getFacets,
  getLinks,
  labelName,
  markOpened,
  markSeen,
  markUnread,
  type Facets,
  type LinkItem,
  type LinkQuery,
} from "@/lib/api";
import { usePrefs } from "@/lib/prefs";
import { useDoubleTap } from "@/lib/useDoubleTap";

const PAGE = 30;
type Read = NonNullable<LinkQuery["read"]>;

function ResultCard({
  link,
  onChange,
  onTheme,
}: {
  link: LinkItem;
  onChange: (l: LinkItem) => void;
  onTheme: (t: string) => void;
}) {
  const { lang } = usePrefs();
  const open = () => {
    window.open(link.url, "_blank", "noopener,noreferrer");
    const now = new Date().toISOString();
    onChange({ ...link, opened_at: now, seen_at: link.seen_at ?? now });
    markOpened(link.id).then(onChange).catch(() => {});
  };
  const doubleTap = useDoubleTap(open);
  const toggle = () => {
    const read = link.seen_at || link.opened_at;
    onChange({ ...link, seen_at: read ? null : new Date().toISOString(), opened_at: read ? null : link.opened_at });
    (read ? markUnread(link.id) : markSeen(link.id)).then(onChange).catch(() => {});
  };
  return (
    <div className="result" onPointerUp={(e) => doubleTap(e)}>
      <Card link={link} defaultLang={lang} onToggleRead={toggle} onThemeClick={onTheme} />
    </div>
  );
}

function SearchInner() {
  const { lang } = usePrefs();
  const fr = lang === "fr";
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const labels = params.getAll("label");
  const themes = params.getAll("theme");
  const q = params.get("q") ?? "";
  const dateFrom = params.get("date_from") ?? "";
  const dateTo = params.get("date_to") ?? "";
  const read = (params.get("read") as Read) ?? "all";

  const [text, setText] = useState(q);
  const [items, setItems] = useState<LinkItem[]>([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState<Facets | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const key = params.toString();

  const update = useCallback(
    (patch: Record<string, string | string[] | null>) => {
      const p = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(patch)) {
        p.delete(k);
        if (Array.isArray(v)) v.forEach((x) => p.append(k, x));
        else if (v) p.set(k, v);
      }
      router.replace(`${pathname}?${p}`, { scroll: false });
    },
    [params, pathname, router],
  );

  useEffect(() => setText(q), [q]);

  // Recherche au fil de la frappe, avec un petit délai.
  useEffect(() => {
    if (text === q) return;
    const t = window.setTimeout(() => update({ q: text || null }), 350);
    return () => window.clearTimeout(t);
  }, [text, q, update]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getLinks({ label: labels, theme: themes, q, date_from: dateFrom, date_to: dateTo, read, limit: PAGE })
      .then((page) => {
        setItems(page.items);
        setTotal(page.total);
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    getFacets().then(setFacets).catch(() => {});
  }, []);

  const more = () =>
    getLinks({
      label: labels, theme: themes, q, date_from: dateFrom, date_to: dateTo, read,
      limit: PAGE, offset: items.length,
    }).then((page) => {
      const known = new Set(items.map((i) => i.id));
      setItems([...items, ...page.items.filter((i) => !known.has(i.id))]);
      setTotal(page.total);
    });

  const toggleIn = (list: string[], v: string) =>
    list.includes(v) ? list.filter((x) => x !== v) : [...list, v];

  const replace = (l: LinkItem) => setItems((prev) => prev.map((i) => (i.id === l.id ? l : i)));
  const addTheme = (t: string) => {
    if (!themes.includes(t)) update({ theme: [...themes, t] });
  };

  const hasFilters = labels.length || themes.length || q || dateFrom || dateTo || read !== "all";

  return (
    <main className="page search">
      <section className="filters" aria-label={fr ? "Filtres" : "Filters"}>
        <input
          type="search"
          className="search-input"
          placeholder={fr ? "Rechercher (mots, auteur, site, thème)…" : "Search (words, author, site, theme)…"}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />

        <div className="chips" role="group" aria-label="Labels">
          {(facets?.labels ?? []).map((l) => (
            <button
              key={l.code}
              type="button"
              className={`chip-filter label-${l.code.toLowerCase()}`}
              aria-pressed={labels.includes(l.code)}
              onClick={() => update({ label: toggleIn(labels, l.code) })}
              disabled={l.count === 0 && !labels.includes(l.code)}
            >
              {labelName(l.code, lang)} <span className="count">{l.count}</span>
            </button>
          ))}
        </div>

        <div className="row">
          <label>
            {fr ? "Du" : "From"}
            <input type="date" value={dateFrom} onChange={(e) => update({ date_from: e.target.value || null })} />
          </label>
          <label>
            {fr ? "au" : "to"}
            <input type="date" value={dateTo} onChange={(e) => update({ date_to: e.target.value || null })} />
          </label>
          <label>
            {fr ? "Lecture" : "Status"}
            <select value={read} onChange={(e) => update({ read: e.target.value === "all" ? null : e.target.value })}>
              <option value="all">{fr ? "Tout" : "All"}</option>
              <option value="unread">{fr ? "Non lus" : "Unread"}</option>
              <option value="seen">{fr ? "Lus" : "Read"}</option>
              <option value="opened">{fr ? "Ouverts" : "Opened"}</option>
            </select>
          </label>
          {hasFilters ? (
            <button type="button" className="ghost" onClick={() => router.replace(pathname)}>
              {fr ? "Effacer les filtres" : "Clear filters"}
            </button>
          ) : null}
        </div>

        {themes.length > 0 && (
          <div className="chips" aria-label={fr ? "Thèmes sélectionnés" : "Selected themes"}>
            {themes.map((t) => (
              <button key={t} type="button" className="chip-filter" aria-pressed="true"
                onClick={() => update({ theme: themes.filter((x) => x !== t) })}>
                #{t} ×
              </button>
            ))}
          </div>
        )}

        {facets && facets.themes.length > 0 && (
          <details className="theme-cloud">
            <summary>{fr ? "Thématiques" : "Themes"}</summary>
            <div className="chips">
              {facets.themes.map((t) => (
                <button key={t.theme} type="button" className="chip-filter"
                  aria-pressed={themes.includes(t.theme)}
                  onClick={() => update({ theme: toggleIn(themes, t.theme) })}>
                  #{t.theme} <span className="count">{t.count}</span>
                </button>
              ))}
            </div>
          </details>
        )}
      </section>

      <p className="result-count">
        {loading ? (fr ? "Recherche…" : "Searching…") : error ? error : fr
          ? `${total} lien${total > 1 ? "s" : ""}`
          : `${total} link${total > 1 ? "s" : ""}`}
      </p>

      <section className="grid">
        {items.map((l) => (
          <ResultCard key={l.id} link={l} onChange={replace} onTheme={addTheme} />
        ))}
      </section>

      {!loading && items.length < total && (
        <div className="more">
          <button type="button" className="ghost" onClick={more}>
            {fr ? "Charger plus" : "Load more"}
          </button>
        </div>
      )}
    </main>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<main className="page search" />}>
      <SearchInner />
    </Suspense>
  );
}
