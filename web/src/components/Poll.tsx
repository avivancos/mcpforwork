"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Light polling — refreshes server data every `seconds`. No SSE (brief §6). */
export function Poll({ seconds = 30 }: { seconds?: number }) {
  const router = useRouter();
  useEffect(() => {
    const id = setInterval(() => router.refresh(), seconds * 1000);
    return () => clearInterval(id);
  }, [router, seconds]);
  return null;
}
