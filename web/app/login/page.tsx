"use client";

// Seule page publique : connexion Google (Firebase Auth), comme x-med.
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  GoogleAuthProvider,
  getRedirectResult,
  onIdTokenChanged,
  signInWithPopup,
  signInWithRedirect,
  signOut,
} from "firebase/auth";
import { getFirebaseAuth, setSessionCookie } from "@/lib/firebase";

function safeNext(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/";
  return raw;
}

function LoginInner() {
  const params = useSearchParams();
  const nextUrl = safeNext(params.get("next"));
  const denied = params.get("denied") === "1";
  const [checking, setChecking] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deniedEmail, setDeniedEmail] = useState<string | null>(null);

  useEffect(() => {
    if (!process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID) {
      setError("Firebase n'est pas configuré (NEXT_PUBLIC_FIREBASE_*).");
      setChecking(false);
      return;
    }
    const auth = getFirebaseAuth();
    getRedirectResult(auth).catch(() => setError("La connexion a échoué, réessaie."));
    return onIdTokenChanged(auth, async (u) => {
      if (u && !denied) {
        setSessionCookie(await u.getIdToken());
        window.location.replace(nextUrl);
        return;
      }
      if (u && denied) setDeniedEmail(u.email);
      setChecking(false);
    });
  }, [nextUrl, denied]);

  async function signIn() {
    setBusy(true);
    setError(null);
    const auth = getFirebaseAuth();
    const provider = new GoogleAuthProvider();
    provider.setCustomParameters({ prompt: "select_account" });
    try {
      const cred = await signInWithPopup(auth, provider);
      setSessionCookie(await cred.user.getIdToken());
      window.location.replace(nextUrl);
    } catch (e) {
      const code = (e as { code?: string })?.code ?? "";
      if (code === "auth/popup-blocked") {
        await signInWithRedirect(auth, provider);
        return;
      }
      if (code !== "auth/popup-closed-by-user" && code !== "auth/cancelled-popup-request") {
        setError("La connexion a échoué, réessaie.");
      }
      setBusy(false);
    }
  }

  async function switchAccount() {
    await signOut(getFirebaseAuth());
    setSessionCookie(null);
    window.location.replace("/login");
  }

  return (
    <>
      {checking ? (
        <p className="login-sub">Vérification de la session…</p>
      ) : denied && deniedEmail ? (
        <>
          <p className="login-sub">
            Le compte <strong>{deniedEmail}</strong> n&apos;a pas accès au Fil.
          </p>
          <button type="button" onClick={switchAccount}>Changer de compte</button>
        </>
      ) : (
        <>
          <p className="login-sub">Les liens partagés sur Telegram, résumés et rangés.</p>
          <button type="button" onClick={signIn} disabled={busy}>
            {busy ? "Connexion…" : "Continuer avec Google"}
          </button>
        </>
      )}
      {error && <p className="login-err">{error}</p>}
    </>
  );
}

export default function LoginPage() {
  return (
    <main className="login">
      <div className="login-card">
        <div className="brand big">
          <span className="brand-dot" aria-hidden="true" />
          Ze News
        </div>
        <Suspense fallback={<p className="login-sub">Vérification de la session…</p>}>
          <LoginInner />
        </Suspense>
      </div>
    </main>
  );
}
