# Deployment

The root `Dockerfile` builds the complete frontend and FastAPI app, with the small four-van demo. A GPU is unnecessary for optimization and local summaries. `frontend/Dockerfile` builds only static assets; use the root image for a working application.

```sh
docker build -t chargewise .
docker run --rm -p 8080:8080 chargewise
# http://localhost:8080 ; health: /api/health
```

Keep one application worker/replica: simulations live in memory, isolated by browser cookie, with a four-hour idle expiry and at most 16 workspaces. A restart clears them. Serve HTTPS through the platform's ingress. Set the container port to **8080** and the readiness path to **/api/health**. No datasets, API keys or model weights need to be uploaded to run the CPU demo. The local application/build tests passed; the Docker engine was unavailable on the preparation laptop, so the container build still needs a Docker/cloud smoke test.

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

If the team later chooses server-side inference credentials, configure `NEBIUS_API_KEY`, `NEBIUS_MODEL` and `NEBIUS_BASE_URL` in the host's secret/environment settings. Keep the key out of Git, the browser and recordings. Nebius is preferred over HF when both are configured. The local self-hosted option takes precedence when explicitly configured. With no provider, the UI labels responses **Local computed summary — no AI model call**.

## Before the final submission

Confirm a real NVIDIA model response through the deployed app, inspect the tool trace, test one read-only question and one explicitly authorized replan, and record the provider/model plus Nebius workload evidence. Test the public application URL from a signed-out browser. Record the demo and credits/model usage honestly. Per the [official hackathon rules](https://nebiusglobalaihackathon.devpost.com/rules), a credential-free optimizer simulation alone does not satisfy the required NVIDIA model runtime on Nebius; a local summary must never be submitted as proof of inference.
