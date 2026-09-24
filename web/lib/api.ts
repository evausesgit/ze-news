// Appels relatifs : ils passent par le proxy Next (/api → FastAPI).
const API = "/api";

export type Lang = "en" | "fr";

export interface LinkItem {
  id: number;
  url: string;
  kind: "tweet" | "web";
  domain: string;
  title: string | null;
  author: string | null;
  published_at: string | null;
  summary_en: string | null;
  summary_fr: string | null;
  label: string | null;
  themes: string[];
  status: string;
  shared_at: string;
  shared_by: string;
  message_text: string;
  seen_at: string | null;
  opened_at: string | null;
}

export interface LinkPage {
  items: LinkItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface Facets {
  labels: { code: string; en: string; fr: string; count: number }[];
  themes: { theme: string; count: number }[];
  total: number;
  unread: number;
  pending: number;
  dormant: number;
}

export interface Me {
  email: string;
  name: string;
  lang: Lang;
  feeds: { id: number; name: string; role: string }[];
}

export interface LinkQuery {
  label?: string[];
  theme?: string[];
  q?: string;
  date_from?: string;
  date_to?: string;
  read?: "all" | "unread" | "seen" | "opened";
  include_dormant?: boolean;
  offset?: number;
  limit?: number;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, { cache: "no-store", ...init });
  if (r.status === 401) {
    if (window.location.pathname !== "/login") window.location.href = "/login";
    throw new Error("Session expirée");
  }
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail ?? `Erreur ${r.status}`);
  }
  return r.json() as Promise<T>;
}

export function getLinks(q: LinkQuery): Promise<LinkPage> {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) {
    if (v === undefined || v === "" || v === null) continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, x));
    else p.set(k, String(v));
  }
  return call<LinkPage>(`/links?${p}`);
}

export const getFacets = () => call<Facets>("/facets");
export const getMe = () => call<Me>("/me");
export const setLang = (lang: Lang) =>
  call<Me>("/me", {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ lang }),
  });
export const markSeen = (id: number) => call<LinkItem>(`/links/${id}/seen`, { method: "POST" });
export const markOpened = (id: number) =>
  call<LinkItem>(`/links/${id}/opened`, { method: "POST" });
export const markUnread = (id: number) =>
  call<LinkItem>(`/links/${id}/state`, { method: "DELETE" });
export const summarizeLink = (id: number) =>
  call<LinkItem>(`/links/${id}/summarize`, { method: "POST" });

// Prévient la barre de navigation qu'un compteur a bougé (lu, ouvert, résumé
// demandé) : la pastille se met à jour sans attendre son rafraîchissement.
export const CHANGED_EVENT = "zenews:changed";
export function notifyChanged() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(CHANGED_EVENT));
}

// Libellés affichés des labels (miroir de app/labels.py).
export const LABEL_NAMES: Record<string, { en: string; fr: string }> = {
  AI: { en: "AI", fr: "IA" },
  TECH: { en: "Tech", fr: "Tech" },
  POLITICS: { en: "Politics", fr: "Politique" },
  NEWS: { en: "News", fr: "Actu" },
  ECONOMY: { en: "Economy", fr: "Économie" },
  STATS: { en: "Stats", fr: "Stats" },
  SCIENCE: { en: "Science", fr: "Science" },
  HEALTH: { en: "Health", fr: "Santé" },
  CULTURE: { en: "Culture", fr: "Culture" },
  OTHER: { en: "Other", fr: "Autre" },
};

export function labelName(code: string | null, lang: Lang): string {
  if (!code) return lang === "fr" ? "En cours" : "Pending";
  return LABEL_NAMES[code]?.[lang] ?? code;
}

export function formatDate(iso: string | null, lang: Lang): string {
  if (!iso) return "";
  // Date et heure du partage, dans le fuseau de l'appareil.
  return new Date(iso).toLocaleString(lang === "fr" ? "fr-FR" : "en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
