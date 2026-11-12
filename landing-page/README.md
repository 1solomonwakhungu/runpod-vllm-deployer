# Landing page

Static site for RunPod vLLM Deployer, published at <https://runpod-vllm-deployer.vercel.app>.

Vite, React, Tailwind CSS v4 and shadcn/ui components. Dark theme only. The build output in `dist/` is plain static files.

```bash
cd landing-page
npm install
npm run dev      # local preview
npm run build    # type check and build into dist/
```

## Content rules

All copy lives in `src/content.ts` and `src/App.tsx`. Everything on the page must be true and traceable to this repository: the README, `docs/`, the CLI source and the agent skill. The `plan` output in the walkthrough is real output from the CLI. Output for commands that need a live Pod shows the format from the CLI source with placeholders, and says so.

When a release changes the version, update `VERSION` in `src/content.ts`.

## Deployment

The Vercel project `runpod-vllm-deployer` builds this folder (root directory `landing-page`) on every push to `main` that touches it. Nothing here is part of the Python package: the folder is excluded from the sdist and the wheel only ships `src/runpod_vllm`.
