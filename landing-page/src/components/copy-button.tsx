import { useEffect, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";

import { cn } from "@/lib/utils";

export function CopyButton({ text, label, className }: { text: string; label: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Clipboard API can be blocked; fall back to a hidden textarea.
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      const ok = document.execCommand("copy");
      area.remove();
      if (!ok) return;
    }
    setCopied(true);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(false), 1800);
  }

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={copied ? "Copied" : label}
      className={cn(
        "group/copy relative inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.04] px-2 text-xs font-medium text-zinc-400 transition-[color,background-color,border-color] duration-150 hover:border-white/20 hover:bg-white/[0.08] hover:text-zinc-100 active:translate-y-px",
        copied && "border-lime-400/40 bg-lime-400/10 text-lime-300 hover:border-lime-400/40 hover:bg-lime-400/10 hover:text-lime-300",
        className,
      )}
    >
      <span className="relative grid size-3.5 place-items-center">
        <Copy
          aria-hidden
          className={cn(
            "col-start-1 row-start-1 size-3.5 transition-[opacity,transform] duration-200",
            copied ? "scale-50 opacity-0" : "scale-100 opacity-100",
          )}
        />
        <Check
          aria-hidden
          className={cn(
            "col-start-1 row-start-1 size-3.5 transition-[opacity,transform] duration-200",
            copied ? "scale-100 opacity-100" : "scale-50 opacity-0",
          )}
        />
      </span>
      <span aria-hidden className="max-sm:hidden">{copied ? "Copied" : "Copy"}</span>
      <span role="status" aria-live="polite" className="sr-only">
        {copied ? "Copied to clipboard" : ""}
      </span>
    </button>
  );
}
