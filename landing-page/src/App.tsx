import type { ReactNode } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Bot,
  CircleAlert,
  EyeOff,
  FileCheck2,
  FileLock2,
  RefreshCw,
  ShieldCheck,
  SquareTerminal,
  Trash2,
} from "lucide-react";

import { CommandBlock } from "@/components/command-block";
import { GithubMark } from "@/components/github-mark";
import { Lifecycle } from "@/components/lifecycle";
import { Reveal } from "@/components/reveal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  commands,
  exitCodes,
  gpus,
  installSkill,
  installSource,
  installWheel,
  links,
  safeguards,
  skillRules,
  VERSION,
} from "@/content";

const safeguardIcons = {
  plan: FileCheck2,
  gate: ShieldCheck,
  state: FileLock2,
  verify: Trash2,
  redact: EyeOff,
  retry: RefreshCw,
} as const;

function Code({ children }: { children: ReactNode }) {
  return (
    <code className="rounded-[5px] border border-white/10 bg-white/[0.06] px-1.5 py-0.5 font-mono text-[0.85em] text-zinc-200">
      {children}
    </code>
  );
}

function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="group/link inline-flex items-center gap-0.5 rounded-sm font-medium text-lime-300 underline decoration-lime-400/30 underline-offset-4 transition-colors duration-150 hover:text-lime-200 hover:decoration-lime-300"
    >
      {children}
      <ArrowUpRight
        aria-hidden
        className="size-3.5 transition-transform duration-150 group-hover/link:translate-x-0.5 group-hover/link:-translate-y-0.5"
      />
    </a>
  );
}

function SectionHeading({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="max-w-2xl">
      <p className="font-mono text-xs tracking-wider text-lime-400 uppercase">{eyebrow}</p>
      <h2 className="mt-3 text-2xl font-semibold tracking-tight text-balance text-zinc-50 sm:text-3xl">{title}</h2>
      {children && <p className="mt-3 text-base leading-relaxed text-pretty text-zinc-400">{children}</p>}
    </div>
  );
}

function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.08] bg-zinc-950/75 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <a href="#top" className="flex items-center gap-2.5 rounded-md font-mono text-sm font-medium text-zinc-50">
          <span
            aria-hidden
            className="grid size-7 place-items-center rounded-md border border-white/15 bg-zinc-900 text-lime-400"
          >
            <SquareTerminal className="size-4" />
          </span>
          runpod-vllm
        </a>
        <nav aria-label="Sections" className="ml-auto hidden items-center gap-1 text-sm md:flex">
          {[
            ["#lifecycle", "Lifecycle"],
            ["#safety", "Safety"],
            ["#agents", "Agent skill"],
            ["#install", "Install"],
          ].map(([href, label]) => (
            <a
              key={href}
              href={href}
              className="rounded-md px-3 py-1.5 text-zinc-400 transition-colors duration-150 hover:bg-white/[0.06] hover:text-zinc-50"
            >
              {label}
            </a>
          ))}
        </nav>
        <Button asChild variant="outline" size="sm" className="ml-auto md:ml-2">
          <a href={links.repo} target="_blank" rel="noreferrer">
            <GithubMark className="size-4" />
            GitHub
          </a>
        </Button>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section id="top" className="relative isolate overflow-hidden">
      <div aria-hidden className="hero-grid absolute inset-0 -z-10" />
      <div aria-hidden className="hero-glow absolute inset-x-0 top-0 -z-10 h-[32rem]" />

      <div className="mx-auto max-w-6xl px-4 pt-16 pb-12 sm:px-6 sm:pt-24 sm:pb-16">
        <div className="mx-auto flex max-w-3xl flex-col items-center text-center">
          <a
            href={links.releases}
            target="_blank"
            rel="noreferrer"
            className="group/pill inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] py-1 pr-3 pl-1 text-xs text-zinc-300 transition-colors duration-150 hover:border-white/20 hover:bg-white/[0.07]"
          >
            <Badge variant="safe" className="rounded-full font-mono">
              v{VERSION}
            </Badge>
            Python 3.11+ · Apache-2.0
            <ArrowRight aria-hidden className="size-3 transition-transform duration-150 group-hover/pill:translate-x-0.5" />
          </a>

          <h1 className="mt-6 text-4xl leading-[1.08] font-semibold tracking-tight text-balance text-zinc-50 sm:text-5xl md:text-6xl">
            vLLM on RunPod GPUs, with a teardown you can <span className="text-lime-400">verify</span>
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-pretty text-zinc-400 sm:text-lg">
            <span className="text-zinc-200">runpod-vllm</span> is a Python CLI and agent skill for OpenAI-compatible
            vLLM servers on RunPod GPU Pods. It plans offline, asks before anything billable, checks readiness, runs a
            smoke test, and confirms the Pod is gone when you destroy it.
          </p>

          <div className="mt-8 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
            <Button asChild size="lg" className="group/cta">
              <a href="#install">
                Install the CLI
                <ArrowRight aria-hidden className="transition-transform duration-150 group-hover/cta:translate-x-0.5" />
              </a>
            </Button>
            <Button asChild size="lg" variant="outline">
              <a href={links.repo} target="_blank" rel="noreferrer">
                <GithubMark className="size-4" />
                View on GitHub
              </a>
            </Button>
          </div>
        </div>

        <div id="lifecycle" className="mt-14 sm:mt-20">
          <Lifecycle />
          <p className="mt-4 flex items-start justify-center gap-2 text-center text-[13px] leading-relaxed text-zinc-400">
            <CircleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0 text-amber-400" />
            <span>
              GPU Pods are billable, and prices change often. Check{" "}
              <ExternalLink href={links.pricing}>RunPod's live pricing</ExternalLink> before you deploy.
            </span>
          </p>
        </div>
      </div>
    </section>
  );
}

function CommandsTable() {
  return (
    <section className="border-t border-white/[0.08]">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
        <Reveal>
          <SectionHeading eyebrow="Commands" title="Seven commands. Two of them change anything.">
            Only <Code>deploy</Code> creates a resource and only <Code>destroy</Code> removes one. Everything else
            reads.
          </SectionHeading>
        </Reveal>

        <Reveal className="mt-10">
          {/* Table from sm up, stacked rows on phones. */}
          <div className="hidden overflow-hidden rounded-xl border border-white/10 sm:block">
            <table className="w-full text-left text-sm">
              <thead className="bg-white/[0.03] text-xs text-zinc-400">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Command</th>
                  <th scope="col" className="px-4 py-3 font-medium">Network</th>
                  <th scope="col" className="px-4 py-3 font-medium">Mutates RunPod</th>
                  <th scope="col" className="px-4 py-3 font-medium">Purpose</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.07]">
                {commands.map((command) => (
                  <tr key={command.name} className="transition-colors duration-150 hover:bg-white/[0.03]">
                    <th scope="row" className="px-4 py-3 font-mono text-[13px] font-medium whitespace-nowrap text-zinc-50">
                      {command.name}
                    </th>
                    <td className="px-4 py-3">
                      <Badge variant={command.network ? "outline" : "safe"}>{command.network ? "Yes" : "No"}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <MutatesBadge value={command.mutates} />
                    </td>
                    <td className="px-4 py-3 text-zinc-400">{command.purpose}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="space-y-2 sm:hidden">
            {commands.map((command) => (
              <li key={command.name} className="rounded-lg border border-white/10 bg-zinc-900/50 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="mr-auto font-mono text-sm font-medium text-zinc-50">{command.name}</span>
                  <Badge variant={command.network ? "outline" : "safe"}>
                    {command.network ? "Network" : "Offline"}
                  </Badge>
                  {command.mutates !== "No" && (
                    <Badge variant={command.mutates.includes("billable") ? "warning" : "destructive"}>
                      {command.mutates.includes("billable") ? "Billable" : "Destructive"}
                    </Badge>
                  )}
                </div>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">{command.purpose}</p>
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal className="mt-6">
          <p className="max-w-3xl text-sm leading-relaxed text-zinc-400">
            State lives in <Code>.runpod-vllm-state.json</Code>. Pass the global <Code>--state-path PATH</Code> option
            before the command to run more than one deployment from a directory. Full option reference:{" "}
            <ExternalLink href={links.configuration}>Configuration</ExternalLink>
          </p>
        </Reveal>
      </div>
    </section>
  );
}

function MutatesBadge({ value }: { value: string }) {
  if (value === "No") return <span className="text-zinc-400">No</span>;
  return <Badge variant={value.includes("billable") ? "warning" : "destructive"}>{value}</Badge>;
}

function Safety() {
  return (
    <section id="safety" className="border-t border-white/[0.08]">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
        <Reveal>
          <SectionHeading eyebrow="Safety" title="Built around the two ways a GPU Pod goes wrong">
            You create one you did not mean to, or you lose track of one that is still billing. Each safeguard below
            closes off one of those.
          </SectionHeading>
        </Reveal>

        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {safeguards.map((item, index) => {
            const Icon = safeguardIcons[item.icon];
            return (
              <Reveal key={item.title} delay={(index % 3) * 70}>
                <Card className="group/card h-full transition-[border-color,background-color,transform] duration-200 hover:-translate-y-0.5 hover:border-white/20 hover:bg-zinc-900/90">
                  <span
                    aria-hidden
                    className="grid size-9 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-zinc-300 transition-colors duration-200 group-hover/card:border-lime-400/30 group-hover/card:text-lime-300"
                  >
                    <Icon className="size-4.5" />
                  </span>
                  <CardHeader>
                    <CardTitle>{item.title}</CardTitle>
                    <CardDescription>{item.body}</CardDescription>
                  </CardHeader>
                </Card>
              </Reveal>
            );
          })}
        </div>

        <Reveal className="mt-6">
          <p className="text-sm leading-relaxed text-zinc-400">
            Read the <ExternalLink href={links.security}>security model</ExternalLink> and{" "}
            <ExternalLink href={links.lifecycle}>lifecycle notes</ExternalLink> before operating the CLI.
          </p>
        </Reveal>
      </div>
    </section>
  );
}

function Configuration() {
  return (
    <section className="border-t border-white/[0.08]">
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-10 px-4 py-16 sm:px-6 sm:py-24 lg:grid-cols-2 lg:gap-16">
        <Reveal>
          <SectionHeading eyebrow="Configuration" title="Six GPU profiles and a pinned image">
            Profiles map to RunPod GPU type IDs. Sizing is approximate and model-specific: a profile name does not
            promise that a model will fit.
          </SectionHeading>
          <ul className="mt-8 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {gpus.map((gpu) => (
              <li
                key={gpu.profile}
                className="rounded-lg border border-white/10 bg-zinc-900/50 px-3 py-2.5 transition-colors duration-150 hover:border-white/20"
              >
                <span className="block font-mono text-sm font-medium text-zinc-50">{gpu.profile}</span>
                <span className="mt-0.5 block text-xs leading-snug text-zinc-400">{gpu.id}</span>
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal delay={80}>
          <dl className="divide-y divide-white/[0.08] rounded-xl border border-white/10 bg-zinc-900/40 text-sm">
            {[
              [
                "Default image",
                <>
                  <Code>vllm/vllm-openai:v0.19.1</Code>, pinned. Override with <Code>--image REPOSITORY:TAG</Code>.{" "}
                  <Code>latest</Code> is rejected.
                </>,
              ],
              [
                "Model",
                <>
                  Model and revision, context length, dtype, quantization, KV cache dtype, reasoning parsers, and
                  trusted model code.
                </>,
              ],
              [
                "Hardware",
                <>
                  GPU profile and count, tensor parallel size, GPU memory utilization, container and Pod volume sizes,
                  host CPU and RAM minimums.
                </>,
              ],
              [
                "Placement",
                <>Cloud type, data center restrictions, port, and repeatable container environment variables.</>,
              ],
              [
                "RunPod API",
                <>
                  REST v1 and v2 payloads. v1 is the default until RunPod retires it on 2026-11-15, then v2, with no
                  upgrade needed. Opt in earlier with <Code>--api-version v2</Code>.
                </>,
              ],
              [
                "Exit codes",
                <span className="flex flex-wrap gap-1.5">
                  {exitCodes.map((exit) => (
                    <span
                      key={exit.code}
                      className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-xs text-zinc-300"
                    >
                      <span className="font-mono text-lime-300">{exit.code}</span>
                      {exit.meaning}
                    </span>
                  ))}
                </span>,
              ],
            ].map(([term, description]) => (
              <div key={term as string} className="grid gap-1.5 px-4 py-3.5 sm:grid-cols-[8.5rem_minmax(0,1fr)] sm:gap-4">
                <dt className="font-medium text-zinc-200">{term}</dt>
                <dd className="leading-relaxed text-zinc-400">{description}</dd>
              </div>
            ))}
          </dl>
        </Reveal>
      </div>
    </section>
  );
}

function Agents() {
  return (
    <section id="agents" className="border-t border-white/[0.08]">
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-10 px-4 py-16 sm:px-6 sm:py-24 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-16">
        <Reveal>
          <SectionHeading eyebrow="Agent skill" title="Hand the workflow to an agent, keep the approval">
            The repository ships a portable Agent Skill, <Code>runpod-vllm-gpu-deploy</Code>, for agents that support
            the Agent Skills convention. It teaches the same plan-first flow and the same boundaries.
          </SectionHeading>
          <div className="mt-8 space-y-3">
            <CommandBlock command={installSkill} label="Install the agent skill" />
            <p className="text-sm leading-relaxed text-zinc-400">
              This installs the agent instructions, not the Python package. Install the CLI as well. See the skill on{" "}
              <ExternalLink href={links.skillsSh}>skills.sh</ExternalLink> or read{" "}
              <ExternalLink href={links.skill}>SKILL.md</ExternalLink>
            </p>
          </div>
        </Reveal>

        <Reveal delay={80}>
          <div className="rounded-xl border border-white/10 bg-zinc-900/40 p-5 sm:p-6">
            <p className="flex items-center gap-2 text-sm font-medium text-zinc-200">
              <Bot aria-hidden className="size-4 text-lime-400" />
              What the skill tells the agent
            </p>
            <ul className="mt-4 space-y-3">
              {skillRules.map((rule) => (
                <li key={rule} className="flex gap-3 text-sm leading-relaxed text-zinc-400">
                  <ShieldCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-lime-400/80" />
                  {rule}
                </li>
              ))}
            </ul>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function Install() {
  return (
    <section id="install" className="border-t border-white/[0.08]">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
        <div className="mx-auto max-w-3xl">
          <Reveal>
            <SectionHeading eyebrow="Install" title="Install, then plan before you spend">
              Python 3.11 or newer. Each release has a wheel and a source distribution attached on GitHub.
            </SectionHeading>
          </Reveal>

          <Reveal className="mt-8">
            <Tabs defaultValue="wheel">
              <TabsList>
                <TabsTrigger value="wheel">Release wheel</TabsTrigger>
                <TabsTrigger value="source">From source</TabsTrigger>
              </TabsList>
              <TabsContent value="wheel" className="panel-in">
                <CommandBlock command={installWheel} label={`Install the v${VERSION} wheel with pip`} />
              </TabsContent>
              <TabsContent value="source" className="panel-in">
                <CommandBlock command={installSource} label="Install from source" />
              </TabsContent>
            </Tabs>
          </Reveal>

          <Reveal className="mt-10">
            <ol className="space-y-6">
              {[
                {
                  title: "Plan offline",
                  note: "No API key, no network request.",
                  command: "runpod-vllm plan \\\n  --model ORG/MODEL \\\n  --gpu A40 \\\n  --max-model-len 8192",
                },
                {
                  title: "Deploy",
                  note: "Billable. Put RUNPOD_API_KEY in a local .env file first. The CLI prompts for confirmation.",
                  command:
                    "runpod-vllm --env-file .env deploy \\\n  --model ORG/MODEL \\\n  --gpu A40 \\\n  --max-model-len 8192",
                },
                {
                  title: "Wait, then smoke test",
                  note: "Polls until vLLM is ready, then sends one deterministic request.",
                  command: "runpod-vllm wait --timeout 900\nrunpod-vllm smoke-test",
                },
                {
                  title: "Destroy",
                  note: "Terminates the Pod and verifies it is absent.",
                  command: "runpod-vllm --env-file .env destroy",
                },
              ].map((step, index) => (
                <li key={step.title} className="grid gap-3 sm:grid-cols-[2rem_minmax(0,1fr)]">
                  <span
                    aria-hidden
                    className="hidden size-7 place-items-center rounded-full border border-white/15 font-mono text-xs text-zinc-400 sm:grid"
                  >
                    {index + 1}
                  </span>
                  <div className="min-w-0 space-y-2.5">
                    <p className="text-sm leading-relaxed">
                      <span className="font-medium text-zinc-100">{step.title}.</span>{" "}
                      <span className="text-zinc-400">{step.note}</span>
                    </p>
                    <CommandBlock command={step.command} label={step.title} />
                  </div>
                </li>
              ))}
            </ol>
            <p className="mt-8 text-sm leading-relaxed text-zinc-400">
              The <ExternalLink href={links.quickstart}>quickstart</ExternalLink> covers each step, and{" "}
              <ExternalLink href={links.troubleshooting}>troubleshooting</ExternalLink> covers unavailable GPU
              inventory, models that exceed memory, and gated checkpoints.
            </p>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  const columns = [
    {
      title: "Docs",
      items: [
        ["Quickstart", links.quickstart],
        ["Configuration", links.configuration],
        ["Lifecycle", links.lifecycle],
        ["Architecture", links.architecture],
      ],
    },
    {
      title: "Project",
      items: [
        ["GitHub", links.repo],
        ["Releases", links.releases],
        ["Changelog", links.changelog],
        ["Issues", links.issues],
      ],
    },
    {
      title: "Trust",
      items: [
        ["Security model", links.security],
        ["Troubleshooting", links.troubleshooting],
        ["Agent skill", links.skill],
        ["License", links.license],
      ],
    },
  ];
  return (
    <footer className="border-t border-white/[0.08]">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[minmax(0,1fr)_auto]">
        <div className="max-w-sm">
          <p className="flex items-center gap-2.5 font-mono text-sm font-medium text-zinc-50">
            <span
              aria-hidden
              className="grid size-7 place-items-center rounded-md border border-white/15 bg-zinc-900 text-lime-400"
            >
              <SquareTerminal className="size-4" />
            </span>
            runpod-vllm
          </p>
          <p className="mt-4 text-sm leading-relaxed text-zinc-400">
            A safe, tested Python CLI for deploying and tearing down OpenAI-compatible vLLM servers on RunPod GPUs.
          </p>
          <p className="mt-4 text-xs leading-relaxed text-zinc-400">
            Apache-2.0. Copyright 2026 Solomon Wakhungu.
          </p>
        </div>
        <nav aria-label="Footer" className="grid grid-cols-2 gap-x-10 gap-y-8 sm:grid-cols-3">
          {columns.map((column) => (
            <div key={column.title}>
              <p className="text-xs font-medium text-zinc-200">{column.title}</p>
              <ul className="mt-3 space-y-2">
                {column.items.map(([label, href]) => (
                  <li key={label}>
                    <a
                      href={href}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-sm text-sm text-zinc-400 transition-colors duration-150 hover:text-zinc-50"
                    >
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </div>
    </footer>
  );
}

export default function App() {
  return (
    <>
      <a
        href="#main"
        className="sr-only rounded-md bg-lime-400 px-3 py-2 text-sm font-medium text-lime-950 focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50"
      >
        Skip to content
      </a>
      <Header />
      <main id="main">
        <Hero />
        <CommandsTable />
        <Safety />
        <Configuration />
        <Agents />
        <Install />
      </main>
      <Footer />
    </>
  );
}
