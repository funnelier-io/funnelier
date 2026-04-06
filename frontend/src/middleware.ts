import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  // Skip locale rewriting for API routes, WebSocket, Next internals, and static files
  matcher: [
    "/((?!api/v1|ws|_next|favicon\\.ico|icon\\.svg|apple-icon\\.png|opengraph-image\\.png|manifest\\.json|.*\\..*).*)",
  ],
};

