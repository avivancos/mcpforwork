"use client";

import { useTransition } from "react";
import { revokeSession } from "@/lib/actions";

export function RevokeButton({ id }: { id: string }) {
  const [pending, start] = useTransition();
  return (
    <button
      type="button"
      className="btn btn--secondary"
      disabled={pending}
      onClick={() => start(() => revokeSession(id))}
    >
      Revoke
    </button>
  );
}
