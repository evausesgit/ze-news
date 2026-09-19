// Client Firebase (SDK web) — connexion Google uniquement.
// La config est publique par conception : la protection vient de la
// vérification du jeton côté serveur (proxy.ts).
import { getApps, initializeApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

// Initialisation paresseuse : uniquement côté navigateur.
export function getFirebaseAuth(): Auth {
  const app = getApps()[0] ?? initializeApp(config);
  return getAuth(app);
}

// Cookie lu par proxy.ts. 55 min < validité du jeton (60 min).
export const SESSION_COOKIE = "lefil_session";

export function setSessionCookie(token: string | null) {
  if (typeof document === "undefined") return;
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = token
    ? `${SESSION_COOKIE}=${token}; path=/; max-age=3300; SameSite=Lax${secure}`
    : `${SESSION_COOKIE}=; path=/; max-age=0; SameSite=Lax${secure}`;
}
