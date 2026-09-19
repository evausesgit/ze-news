"use client";

// Préférences de l'utilisateur connecté (langue par défaut des cartes), lues
// depuis /api/me et enregistrées côté serveur : elles suivent l'utilisateur
// d'un appareil à l'autre.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { getMe, setLang as saveLang, type Lang, type Me } from "@/lib/api";

interface Prefs {
  me: Me | null;
  lang: Lang;
  setLang: (l: Lang) => void;
}

const PrefsContext = createContext<Prefs>({ me: null, lang: "en", setLang: () => {} });

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    if (window.location.pathname === "/login") return;
    getMe()
      .then((m) => {
        setMe(m);
        setLangState(m.lang);
      })
      .catch(() => {});
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    saveLang(l).then(setMe).catch(() => {});
  }, []);

  return <PrefsContext.Provider value={{ me, lang, setLang }}>{children}</PrefsContext.Provider>;
}

export const usePrefs = () => useContext(PrefsContext);
