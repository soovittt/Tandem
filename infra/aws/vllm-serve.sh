#!/usr/bin/env bash
#
# Run this ON the GPU box (after you SSH in). It serves a model with vLLM using
# vLLM's official Docker image -- the AMI already has Docker + the NVIDIA runtime.
#
# The first run pulls the image and downloads the model weights (a few minutes;
# you pay GPU time during this too). After that, requests are served fast.
#
# Usage (on the box):  bash vllm-serve.sh [model-id]
set -euo pipefail

# 8B dense Nemotron (reasoning + native tool calling); BF16 ~16GB fits a 24GB L4
# with ~32K context under fp8 KV cache. A real step up from Nemotron-Mini-4B.
MODEL="${1:-nvidia/Llama-3.1-Nemotron-Nano-8B-v1}"
echo "Serving $MODEL with vLLM on :8000  (Ctrl-C to stop)"
echo "Watch for two things in the logs:"
echo "  * '# GPU blocks: N'  -> the KV cache vLLM carved out of GPU memory"
echo "  * requests being batched together -> continuous batching in action"
echo

sudo docker run --rm --gpus all -p 8000:8000 \
  -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
  ${HF_TOKEN:+-e HF_TOKEN=$HF_TOKEN} \
  vllm/vllm-openai:latest \
  --model "$MODEL" \
  --max-model-len 32768 \
  --enable-prefix-caching \
  --enable-chunked-prefill \
  --max-num-batched-tokens 2048 \
  --max-num-seqs 4 \
  --kv-cache-dtype fp8 \
  --gpu-memory-utilization 0.92 \
  --enable-auto-tool-choice \
  --tool-call-parser llama3_json
# Efficiency flags (per docs/harness-plan.md): prefix-caching reuses the KV cache
# across ReAct steps (the big win for a tool loop); chunked prefill keeps the
# single live agent latency-biased; fp8 KV cache fits a longer context on the L4.
#
# Native tool calling (TOOL_MODE=native): --enable-auto-tool-choice lets vLLM emit
# OpenAI tool_calls; --tool-call-parser decodes this model's format.
# MUST-VERIFY the parser token on this vLLM build:
#   sudo docker run --rm vllm/vllm-openai:latest --help | grep -A3 tool-call-parser
# For the Llama-3.1-Nemotron-Nano models it's the Llama-3 JSON parser (llama3_json);
# some NVIDIA docs reference `hermes` for certain tool formats -- confirm if routing
# misbehaves. If vLLM complains about a missing tool chat template, pass the
# tool-enabled --chat-template the model card ships.
