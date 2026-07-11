import type { MetadataRoute } from "next";
import { DOCS_ORDER } from "@/app/docs/_nav";
import { SITE_URL } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const staticPaths = ["/", "/faq", "/privacy", "/terms", "/security"];
  const docPaths = DOCS_ORDER.map((d) => d.slug); // includes "/docs" (Quickstart)

  return [...staticPaths, ...docPaths].map((path) => ({
    url: `${SITE_URL}${path}`,
    changeFrequency: "monthly" as const,
    priority: path === "/" ? 1 : 0.7,
  }));
}
