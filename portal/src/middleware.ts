import { NextResponse, type NextRequest } from "next/server";

// Protected areas of the portal. Anything here requires a session.
const PROTECTED = [
  "/dashboard", "/devices", "/assets", "/users", "/telemetry", "/knowledge",
  "/self-healing", "/reports", "/notifications", "/audit", "/settings",
  "/billing", "/platform",
];

/**
 * Server-side auth gate. The real credential is the Bearer token the API validates —
 * this cookie is only a *presence hint* so the edge can bounce signed-out visitors
 * BEFORE any HTML is sent. Without it, a deep link to /dashboard would render the
 * shell and only redirect once client JS ran, which is the flicker users see.
 */
export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const isProtected = PROTECTED.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (!isProtected) return NextResponse.next();

  if (req.cookies.get("astra_auth")) return NextResponse.next();

  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  return NextResponse.redirect(url);
}

export const config = {
  // Skip static assets and the API proxy.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
