# Deployment

The root `Dockerfile` builds the complete frontend and FastAPI app, with the small four-van demo. A GPU is unnecessary for optimization and local summaries. `frontend/Dockerfile` builds only static assets; use the root image for a working application.

```sh
docker build -t chargewise .
docker run --rm -p 8080:8080 chargewise
# http://localhost:8080 ; health: /api/health
```

Keep one application worker/replica: simulations live in memory, isolated by browser cookie, with a four-hour idle expiry and at most 16 workspaces. A restart clears them. Serve HTTPS through the platform's ingress. Set the container port to **8080** and the readiness path to **/api/health**. No datasets, API keys or model weights need to be uploaded to run the CPU demo. Native tests and the extracted build are verified; a Docker engine was unavailable for a container smoke test.

## Public presentation and test build

[GitHub Pages](https://j-stoerk.github.io/nebiusxnvidia_hackathon/) serves the original animation, recorded app workflow and download instructions, without credentials or a backend. The complete React/FastAPI/OR-Tools app is a [downloadable test build](https://github.com/j-stoerk/nebiusxnvidia_hackathon/releases/tag/submission-review-2026-10-25), with prebuilt frontend assets. It runs locally without Node.js or an API token. Pages is static hosting and does not run the optimizer.

`presentation/` contains editable HTML/Canvas source and the narration timeline. GitHub Pages publishes the separate `gh-pages` branch, which includes the small reviewed media files; source history on `main` contains no video/model binaries. To preview, extract `ChargeWise_Animation_Assets.zip` into `presentation/media`, then serve `presentation/` with a local HTTP server. The synthetic voice is replaceable with the team's recordings; it does not impersonate team members. Publishing source edits to `main` does not update the site automatically: synchronize the reviewed presentation and media to `gh-pages` after checking them.

## NVIDIA Nemotron without an API token

Run the public NVIDIA model and ChargeWise on the **same Nebius GPU DevPod**. The application talks to a loopback vLLM server without an Authorization header; no HF/Nebius inference API token is required. Cloud console sign-in, GPU capacity and credits/billing are still needed. Model weights are downloaded **on the cloud host**, not the laptop.

Choose a compatible GPU/runtime using [NVIDIA's model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16#use-it-with-vllm). The documented vLLM integration requires version 0.12 or later, the Nano reasoning parser and the Qwen3 tool parser; follow the current NVIDIA cookbook for hardware sizing. The prepared launcher uses a shorter context and fewer sequences for the demo:

```sh
# Inside an already provisioned GPU DevPod with vLLM >=0.12, uv and curl:
# Install Node.js 22.12+ for the frontend, or copy frontend/dist from a local build.
bash deployment/run-nebius-gpu.sh
```

Expose only application port 8080 through the DevPod's supported ingress/port forwarding. The model stays on `127.0.0.1:8001`; do not publish it as an unauthenticated model endpoint. The launcher is prepared but **has not been run on cloud GPUs**. Neither the launcher nor its presence in Git proves a live Nebius deployment.

## Token Factory alternative

For a private live demo, run `uv run --locked python scripts/run_live_demo.py --budget 0.05 --requests 12`. Enter the key at the hidden prompt, open `http://127.0.0.1:8017`, and stop with Ctrl+C. The launcher builds before requesting the key; no credential is written to disk or passed to build subprocesses.

For an already configured server, use its secret settings for `NEBIUS_API_KEY`, `NEBIUS_MODEL` and `NEBIUS_BASE_URL`, plus the explicit `CLOUD_INFERENCE_ENABLED=true` opt-in. Only `nvidia/Nemotron-3_5-Lightning` has a verified local allowance. Limits default to $0.05 cumulative reservations, 12 requests and 1,024 output tokens/request. Errors/timeouts retain reservations. Persist `/app/.cache` on a durable volume: restarting on ephemeral storage must not reset a credit ledger. This guard covers only this installation, not other key users or account-wide billing. Never expose an enabled, unauthenticated paid assistant to public traffic. No key is included in the public site or ZIP.

With no provider, the UI labels responses **Local computed summary — no AI model call**. Explicitly configured loopback self-hosted inference takes precedence over cloud routing.

## Before the final submission

The [runtime evidence](../docs/runtime-evidence.json) records the actual model, read tool, authorized mutation, checked post-outage results and estimated usage. The [organizers' FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs) confirms that runtime inference through Token Factory satisfies the Nebius platform requirement; the rest of the app can run elsewhere. The rules accept a test-build URL. Full Nebius AI Cloud hosting has not been provisioned and is not implied by this evidence. The generic no-key optimizer summary is never proof of model inference.
