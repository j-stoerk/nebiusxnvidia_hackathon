#!/usr/bin/env bash
# Optional cloud-only launcher. Does not provision or charge for resources itself.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v vllm >/dev/null || { echo 'Use a compatible GPU DevPod with vLLM >=0.12 installed; see the NVIDIA model card.' >&2; exit 1; }
command -v uv >/dev/null || { echo 'Install uv in the DevPod first.' >&2; exit 1; }
command -v curl >/dev/null || { echo 'Install curl in the DevPod first.' >&2; exit 1; }
if [[ ! -f frontend/dist/index.html ]]; then
  command -v npm >/dev/null || { echo 'Install Node.js 22.12+ or provide the prebuilt frontend before loading model weights.' >&2; exit 1; }
  (cd frontend && npm ci --no-audit --no-fund && npm run build)
fi
export NEMOTRON_MODEL="${NEMOTRON_MODEL:-nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16}"
export NEMOTRON_BASE_URL=http://127.0.0.1:8001/v1
runtime_dir=$(mktemp -d)
# NVIDIA's documented custom parser; downloaded on the GPU host only.
curl --fail --location --silent --show-error \
  https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16/resolve/main/nano_v3_reasoning_parser.py \
  --output "$runtime_dir/nano_v3_reasoning_parser.py"
vllm serve "$NEMOTRON_MODEL" --served-model-name "$NEMOTRON_MODEL" \
  --host 127.0.0.1 --port 8001 --max-model-len 8192 --max-num-seqs 4 \
  --tensor-parallel-size 1 --trust-remote-code --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder --reasoning-parser-plugin "$runtime_dir/nano_v3_reasoning_parser.py" \
  --reasoning-parser nano_v3 > "$runtime_dir/model.log" 2>&1 &
model_pid=$!
trap 'kill "$model_pid" 2>/dev/null || true' EXIT
echo "Model log: $runtime_dir/model.log"
ready=false
for _ in $(seq 1 300); do
  kill -0 "$model_pid" 2>/dev/null || { tail -30 "$runtime_dir/model.log"; exit 1; }
  if curl --fail --silent http://127.0.0.1:8001/health >/dev/null; then ready=true; break; fi
  sleep 2
done
[[ "$ready" == true ]] || { echo 'Model startup timed out; inspect the log.' >&2; exit 1; }
uv sync --locked --no-dev
uv run --locked python scripts/run_demo.py --no-browser --host 0.0.0.0 --port 8080
