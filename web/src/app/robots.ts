import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // Personal dashboard/auth routes aren't for indexing. Bare prefixes
      // (no trailing slash) so each covers both the index and its children.
      disallow: ["/pipeline", "/matches", "/profile", "/account", "/connect", "/onboarding", "/login"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
