// Every string on the page comes from the repository: README.md, docs/,
// src/runpod_vllm/ and skills/. Keep it that way when editing.

export const REPO = "1solomonwakhungu/runpod-vllm-deployer";
export const REPO_URL = `https://github.com/${REPO}`;
export const VERSION = "0.1.0";

export const links = {
  repo: REPO_URL,
  releases: `${REPO_URL}/releases`,
  changelog: `${REPO_URL}/blob/main/CHANGELOG.md`,
  quickstart: `${REPO_URL}/blob/main/docs/quickstart.md`,
  configuration: `${REPO_URL}/blob/main/docs/configuration.md`,
  lifecycle: `${REPO_URL}/blob/main/docs/lifecycle.md`,
  security: `${REPO_URL}/blob/main/docs/security.md`,
  troubleshooting: `${REPO_URL}/blob/main/docs/troubleshooting.md`,
  architecture: `${REPO_URL}/blob/main/docs/architecture.md`,
  skill: `${REPO_URL}/blob/main/skills/runpod-vllm-gpu-deploy/SKILL.md`,
  skillsSh: `https://skills.sh/${REPO}`,
  license: `${REPO_URL}/blob/main/LICENSE`,
  issues: `${REPO_URL}/issues`,
  pricing: "https://www.runpod.io/pricing",
};

export const installWheel = `python -m pip install ${REPO_URL}/releases/download/v${VERSION}/runpod_vllm_deployer-${VERSION}-py3-none-any.whl`;

export const installSource = `git clone ${REPO_URL}.git
cd runpod-vllm-deployer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
runpod-vllm --help`;

export const installSkill = `npx skills add ${REPO} --skill runpod-vllm-gpu-deploy`;

// Captured from `runpod-vllm plan` at v0.1.0 with no API key set.
const planOutput = `Deployment plan for RunPod REST v1 (offline; no API call)
{
  "cloudType": "SECURE",
  "computeType": "GPU",
  "containerDiskInGb": 50,
  "dataCenterPriority": "availability",
  "dockerEntrypoint": [],
  "dockerStartCmd": [
    "vllm",
    "serve",
    "Qwen/Qwen3-8B",
    "--host",
    "0.0.0.0",
    "--port",
    "8000",
    "--tensor-parallel-size",
    "1",
    "--max-model-len",
    "8192",
    "--gpu-memory-utilization",
    "0.9",
    "--dtype",
    "auto",
    "--kv-cache-dtype",
    "auto"
  ],
  "env": {},
  "gpuCount": 1,
  "gpuTypeIds": [
    "NVIDIA A40"
  ],
  "gpuTypePriority": "availability",
  "imageName": "vllm/vllm-openai:v0.19.1",
  "interruptible": false,
  "minRAMPerGPU": 16,
  "minVCPUPerGPU": 4,
  "name": "vllm-server",
  "ports": [
    "8000/http"
  ],
  "supportPublicIp": true,
  "volumeInGb": 40,
  "volumeMountPath": "/workspace"
}`;

export type Tone = "safe" | "warning" | "destructive" | "outline";

export type Step = {
  id: string;
  name: string;
  tag: string;
  tone: Tone;
  summary: string;
  detail: string;
  command: string;
  output: string;
  provenance: string;
};

export const steps: Step[] = [
  {
    id: "plan",
    name: "plan",
    tag: "Offline",
    tone: "safe",
    summary: "Validate inputs and print a redacted plan without network access.",
    detail:
      "plan never loads RUNPOD_API_KEY and never constructs an HTTP client. Review the payload here before anything can cost money.",
    command: `runpod-vllm plan \\
  --model Qwen/Qwen3-8B \\
  --gpu A40 \\
  --max-model-len 8192`,
    output: planOutput,
    provenance:
      "Real output, captured from v0.1.0 with no API key set. The CLI targets REST v1 until 2026-11-15 and v2 after.",
  },
  {
    id: "deploy",
    name: "deploy",
    tag: "Billable",
    tone: "warning",
    summary: "Create a billable RunPod GPU Pod and save teardown state.",
    detail:
      "deploy is the only command that creates a resource. It prompts for confirmation, then writes the Pod ID to local state straight after the create response.",
    command: `runpod-vllm --env-file .env deploy \\
  --model Qwen/Qwen3-8B \\
  --gpu A40 \\
  --max-model-len 8192`,
    output: `Create a billable RunPod GPU Pod? [y/N]: y
Pod created: <POD_ID>
Teardown state: .runpod-vllm-state.json
Next: runpod-vllm --state-path .runpod-vllm-state.json wait`,
    provenance: "Output format from the CLI source. No Pod was created to produce it.",
  },
  {
    id: "wait",
    name: "wait",
    tag: "Read only",
    tone: "outline",
    summary: "Wait for /health and /v1/models readiness.",
    detail:
      "Polls both endpoints through the recorded proxy URL every 5 seconds by default, and exits with code 7 if the timeout passes first.",
    command: "runpod-vllm wait --timeout 900",
    output: "Ready after <SECONDS>s and <N> attempts: Qwen/Qwen3-8B",
    provenance: "Output format from the CLI source. No Pod was created to produce it.",
  },
  {
    id: "smoke-test",
    name: "smoke-test",
    tag: "Read only",
    tone: "outline",
    summary: "Send a small deterministic OpenAI-compatible chat request.",
    detail:
      "One chat completion with max_tokens 4, temperature 0 and seed 0. An optional bearer token is read from VLLM_API_KEY.",
    command: "runpod-vllm smoke-test",
    output: "Smoke test passed. Usage: {<token usage reported by vLLM>}",
    provenance: "Output format from the CLI source. No Pod was created to produce it.",
  },
  {
    id: "destroy",
    name: "destroy",
    tag: "Destructive",
    tone: "destructive",
    summary: "Terminate a Pod, verify absence, and remove matching local state.",
    detail:
      "Sends the delete, then reads the Pod until it is absent. Local state is removed only after that. If verification times out, state stays so you can retry.",
    command: "runpod-vllm --env-file .env destroy",
    output: `Permanently terminate Pod <POD_ID>? [y/N]: y
Termination requested; verified absent: <POD_ID>
Removed local state: .runpod-vllm-state.json`,
    provenance: "Output format from the CLI source. No Pod was created to produce it.",
  },
];

export const commands = [
  { name: "plan", network: false, mutates: "No", purpose: "Validate configuration and print a redacted payload" },
  { name: "deploy", network: true, mutates: "Yes, billable", purpose: "Create a GPU Pod and immediately save teardown state" },
  { name: "status", network: true, mutates: "No", purpose: "Inspect the recorded Pod and display access URLs" },
  { name: "wait", network: true, mutates: "No", purpose: "Poll /health and /v1/models until ready" },
  { name: "smoke-test", network: true, mutates: "No", purpose: "Send a four-token deterministic chat request" },
  { name: "list", network: true, mutates: "No", purpose: "List active GPU Pods" },
  { name: "destroy", network: true, mutates: "Yes", purpose: "Delete, verify absence, then remove matching state" },
];

export const safeguards = [
  {
    icon: "plan",
    title: "Plans stay offline",
    body: "plan validates the configuration and prints the exact payload. It needs no API key and makes no network request.",
  },
  {
    icon: "gate",
    title: "Confirmation before cost",
    body: "deploy and destroy both prompt first. --yes skips the prompt for unattended runs, after you have reviewed the plan.",
  },
  {
    icon: "state",
    title: "Teardown state first",
    body: "The Pod ID is saved with an atomic replace and mode 0600 where supported. If that write fails, the CLI prints the destroy command with the Pod ID.",
  },
  {
    icon: "verify",
    title: "Deletion is verified",
    body: "destroy waits until RunPod reports the Pod absent before it removes local state. A 404 counts as success, so running it twice is safe.",
  },
  {
    icon: "redact",
    title: "Secrets stay out of files",
    body: "Credentials come from the environment or an env file you name. They are never written to state, and plans and error text are redacted on a best-effort basis.",
  },
  {
    icon: "retry",
    title: "Rate limits are retried",
    body: "HTTP 429 responses from RunPod are retried automatically with exponential backoff and jitter.",
  },
] as const;

export const gpus = [
  { profile: "A40", id: "NVIDIA A40" },
  { profile: "L40S", id: "NVIDIA L40S" },
  { profile: "A100", id: "NVIDIA A100-SXM4-80GB" },
  { profile: "H100", id: "NVIDIA H100 80GB HBM3" },
  { profile: "H200", id: "NVIDIA H200" },
  { profile: "B200", id: "NVIDIA B200" },
];

export const exitCodes = [
  { code: 0, meaning: "OK" },
  { code: 2, meaning: "Usage" },
  { code: 3, meaning: "Config" },
  { code: 4, meaning: "Auth" },
  { code: 5, meaning: "Network" },
  { code: 6, meaning: "API" },
  { code: 7, meaning: "Timeout" },
  { code: 8, meaning: "State" },
];

export const skillRules = [
  "Treats deploy as billable and will not run it unless your current request clearly authorizes the reviewed configuration.",
  "Treats destroy as destructive and needs authorization for the exact verified Pod.",
  "Does not use --yes to infer consent. The flag only skips the prompt once approval exists.",
  "Keeps validation offline until you authorize a live operation.",
];
