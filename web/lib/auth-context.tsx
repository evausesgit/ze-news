"use client";

// Maintient le cookie de session à jour (renouvellement du jeton Firebase) et
// expose la déconnexion. En dev avec LEFIL_DEV_USER_EMAIL, Firebase n'est pas
// configuré : on ne l'initialise pas.
import { createContext, useCallback, useContext, useEffect, type ReactNode } from "react";
import { onIdTokenChanged, signOut } from "firebase/auth";
import { getFirebaseAuth, setSessionCookie } from "@/lib/firebase";

const FIREBASE_ON = Boolean(process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID);

const AuthContext = createContext<{ signOutUser: () => Promise<void> }>({
  signOutUser: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    if (!FIREBASE_ON) return;
    const auth = getFirebaseAuth();
    const unsub = onIdTokenChanged(auth, async (u) => {
      setSessionCookie(u ? await u.getIdToken() : null);
    });
    const timer = setInterval(
      () => auth.currentUser?.getIdToken().then(setSessionCookie),
      45 * 60 * 1000,
    );
    return () => {
      unsub();
      clearInterval(timer);
    };
  }, []);

  const signOutUser = useCallback(async () => {
    if (FIREBASE_ON) await signOut(getFirebaseAuth());
    setSessionCookie(null);
    window.location.href = "/login";
  }, []);

  return <AuthContext.Provider value={{ signOutUser }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
