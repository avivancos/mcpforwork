"use client";

import { useEffect, useRef, useState } from "react";

export function CopyButton({ text, className, label = "Copy" }: { text: string; className?: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(timer.current), []);

  return (
    <button
      type="button"
      className={className}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          timer.current = setTimeout(() => setCopied(false), 1500);
        } catch {
          // Clipboard blocked (insecure context / denied permission) — leave
          // the label unchanged rather than throw; the text is visible to copy.
        }
      }}
    >
      {copied ? "Copied ✓" : label}
    </button>
  );
}
