import { useEffect, useState } from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";

import { CopyButton } from "@/components/copy-button";
import { Badge } from "@/components/ui/badge";
import { steps, type Step } from "@/content";
import { cn } from "@/lib/utils";

function useIsDesktop() {
  const [desktop, setDesktop] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(min-width: 1024px)").matches,
  );
  useEffect(() => {
    const query = window.matchMedia("(min-width: 1024px)");
    const update = () => setDesktop(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return desktop;
}

function Output({ step }: { step: Step }) {
  const [first, ...rest] = step.output.split("\n");
  return (
    <>
      <span className="block whitespace-pre text-zinc-300">{first}</span>
      {rest.map((line, i) => (
        <span key={i} className="block whitespace-pre text-zinc-400">
          {line || " "}
        </span>
      ))}
    </>
  );
}

export function Lifecycle() {
  const [active, setActive] = useState(steps[0].id);
  const desktop = useIsDesktop();

  return (
    <TabsPrimitive.Root
      value={active}
      onValueChange={setActive}
      orientation={desktop ? "vertical" : "horizontal"}
      className="grid overflow-hidden rounded-xl border border-white/10 bg-zinc-900/50 shadow-2xl shadow-black/40 lg:grid-cols-[19rem_minmax(0,1fr)]"
    >
      <TabsPrimitive.List
        aria-label="Deployment lifecycle"
        className="scrollbar-thin flex gap-1 overflow-x-auto border-b border-white/10 p-2 lg:flex-col lg:gap-0.5 lg:overflow-visible lg:border-r lg:border-b-0 lg:p-3"
      >
        {steps.map((step, index) => (
          <TabsPrimitive.Trigger
            key={step.id}
            value={step.id}
            className="group/step relative flex shrink-0 items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors duration-150 hover:bg-white/[0.04] data-[state=active]:bg-white/[0.07] lg:items-start lg:py-3"
          >
            <span
              aria-hidden
              className="grid size-6 shrink-0 place-items-center rounded-full border border-white/15 font-mono text-[11px] text-zinc-400 transition-colors duration-150 group-data-[state=active]/step:border-lime-400/60 group-data-[state=active]/step:bg-lime-400/10 group-data-[state=active]/step:text-lime-300"
            >
              {index + 1}
            </span>
            <span className="flex min-w-0 flex-col gap-1">
              <span className="flex items-center gap-2">
                <span className="font-mono text-sm font-medium text-zinc-300 transition-colors group-hover/step:text-zinc-50 group-data-[state=active]/step:text-zinc-50">
                  {step.name}
                </span>
                <Badge variant={step.tone} className="hidden px-1.5 py-0 text-[10.5px] lg:inline-flex">
                  {step.tag}
                </Badge>
              </span>
              <span className="hidden text-[13px] leading-snug text-zinc-400 lg:block">{step.summary}</span>
            </span>
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>

      {steps.map((step) => (
        <TabsPrimitive.Content
          key={step.id}
          value={step.id}
          className="panel-in flex min-w-0 flex-col outline-none focus-visible:ring-2 focus-visible:ring-lime-400/60 focus-visible:ring-inset"
        >
          <div className="flex items-center gap-2 border-b border-white/10 px-4 py-2.5">
            <span aria-hidden className="flex gap-1.5">
              <span className="size-2.5 rounded-full bg-zinc-700" />
              <span className="size-2.5 rounded-full bg-zinc-700" />
              <span className="size-2.5 rounded-full bg-zinc-700" />
            </span>
            <span className="ml-2 truncate font-mono text-xs text-zinc-400">runpod-vllm {step.name}</span>
            <Badge variant={step.tone} className="ml-auto lg:hidden">
              {step.tag}
            </Badge>
            <CopyButton text={step.command} label={`Copy the ${step.name} command`} className="ml-2 lg:ml-auto" />
          </div>

          <pre
            tabIndex={0}
            aria-label={`${step.name} command and output`}
            className="scrollbar-thin h-[21rem] overflow-auto px-4 py-4 font-mono text-[12.5px] leading-[1.7] sm:text-[13px] lg:h-[24rem]"
          >
            <code>
              {step.command.split("\n").map((line, i) => (
                <span key={i} className="block whitespace-pre text-zinc-50">
                  <span aria-hidden className="text-lime-400 select-none">
                    {i === 0 ? "$ " : "  "}
                  </span>
                  {line}
                </span>
              ))}
              <span className="block h-3" />
              <Output step={step} />
              <span className="mt-3 block">
                <span aria-hidden className="text-lime-400 select-none">
                  ${" "}
                </span>
                <span aria-hidden className={cn("cursor-blink inline-block h-[1.05em] w-[0.55em] translate-y-[0.18em] bg-zinc-500")} />
              </span>
            </code>
          </pre>

          <div className="mt-auto space-y-1.5 border-t border-white/10 bg-zinc-950/40 px-4 py-3.5">
            <p className="text-sm leading-relaxed text-zinc-300 lg:hidden">{step.summary}</p>
            <p className="text-sm leading-relaxed text-zinc-300">{step.detail}</p>
            <p className="text-xs leading-relaxed text-zinc-400">{step.provenance}</p>
          </div>
        </TabsPrimitive.Content>
      ))}
    </TabsPrimitive.Root>
  );
}
