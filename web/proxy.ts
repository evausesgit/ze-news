// Garde d'authentification globale (convention Next 16 : proxy.ts, ex-middleware).
// Même mécanique que x-med : toute requête — pages ET relais /api/* vers
// FastAPI — doit porter un ID token Firebase valide dans le cookie de session,
// vérifié contre les clés publiques de Google. Seule /login reste publique.
import { NextResponse, type NextRequest } from "next/server";
import { createRemoteJWKSet, jwtVerify } from "jose";
import { SESSION_COOKIE } from "@/lib/firebase";

const PROJECT_ID = process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? "";
const INTERNAL_TOKEN = process.env.INTERNAL_API_TOKEN ?? "";

// Dev local uniquement : identité simulée, jamais active en production.
const DEV_USER_EMAIL =
  process.env.NODE_ENV !== "production" ? (process.env.LEFIL_DEV_USER_EMAIL ?? "") : "";

const JWKS = createRemoteJWKSet(
  new URL(
    "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com",
  ),
);

// Liste blanche optionnelle d'emails Google (séparés par des virgules).
const ALLOWED_EMAILS = (process.env.LEFIL_ALLOWED_EMAILS ?? "")
  .split(",")
  .map((e) => e.trim().toLowerCase())
  .filter(Boolean);

type Session =
  | { verdict: "ok"; email: string; uid: string; name: string }
  | { verdict: "anonymous" | "forbidden" };

async function checkSession(req: NextRequest): Promise<Session> {
  if (DEV_USER_EMAIL) {
    return { verdict: "ok", email: DEV_USER_EMAIL, uid: `dev-${DEV_USER_EMAIL}`, name: "Dev" };
  }
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (!token || !PROJECT_ID) return { verdict: "anonymous" };
  try {
    const { payload } = await jwtVerify(token, JWKS, {
      issuer: `https://securetoken.google.com/${PROJECT_ID}`,
      audience: PROJECT_ID,
      algorithms: ["RS256"],
    });
    if (!payload.sub) return { verdict: "anonymous" };
    const email = String(payload.email ?? "").toLowerCase();
    if (!email || payload.email_verified === false) return { verdict: "anonymous" };
    if (ALLOWED_EMAILS.length > 0 && !ALLOWED_EMAILS.includes(email)) {
      return { verdict: "forbidden" };
    }
    return { verdict: "ok", email, uid: payload.sub, name: String(payload.name ?? "") };
  } catch {
    return { verdict: "anonymous" };
  }
}

export async function proxy(req: NextRequest) {
  const session = await checkSession(req);
  const { pathname, search } = req.nextUrl;

  if (session.verdict === "ok") {
    if (pathname === "/login") return NextResponse.redirect(new URL("/", req.url));
    // On ÉCRASE toujours ces en-têtes : une valeur venue du navigateur serait
    // de l'usurpation, jamais relayée.
    const headers = new Headers(req.headers);
    headers.set("x-user-email", session.email);
    headers.set("x-user-uid", session.uid);
    headers.set("x-user-name", encodeURIComponent(session.name));
    headers.set("x-internal-token", INTERNAL_TOKEN);
    return NextResponse.next({ request: { headers } });
  }

  if (pathname === "/login") return NextResponse.next();

  if (pathname.startsWith("/api/")) {
    return NextResponse.json(
      { detail: "Authentification requise." },
      { status: session.verdict === "forbidden" ? 403 : 401 },
    );
  }

  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  if (session.verdict === "forbidden") url.searchParams.set("denied", "1");
  else if (pathname + search !== "/") url.searchParams.set("next", pathname + search);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/|favicon\\.ico|icon\\.svg).*)"],
};
