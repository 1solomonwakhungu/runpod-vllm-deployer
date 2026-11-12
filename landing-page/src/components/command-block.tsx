import { CopyButton } from "@/components/copy-button";
import { cn } from "@/lib/utils";

/** A copyable shell snippet. Each line gets a "$" prompt unless it continues the previous one. */
export function CommandBlock({
  command,
  label,
  className,
}: {
  command: string;
  label: string;
  className?: string;
}) {
  const lines = command.split("\n");
  return (
    <div
      className={cn(
        "group/cmd flex items-start gap-3 rounded-lg border border-white/10 bg-zinc-900/70 py-2.5 pr-2.5 pl-4 transition-colors duration-150 hover:border-white/20",
        className,
      )}
    >
      <pre
        tabIndex={0}
        aria-label={label}
        className="scrollbar-thin min-w-0 flex-1 overflow-x-auto py-1 font-mono text-[13px] leading-6 text-zinc-100"
      >
        <code>
          {lines.map((line, i) => {
            const continued = i > 0 && lines[i - 1].trimEnd().endsWith("\\");
            return (
              <span key={i} className="block whitespace-pre">
                <span aria-hidden className="text-lime-400/80 select-none">
                  {continued ? "  " : "$ "}
                </span>
                {line}
              </span>
            );
          })}
        </code>
      </pre>
      <CopyButton text={command} label={`Copy: ${label}`} />
    </div>
  );
}
