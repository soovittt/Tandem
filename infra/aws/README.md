# AWS vLLM learning session

Spin up a single-GPU EC2 box, serve an NVIDIA model with **vLLM**, point the app
at it, and watch how real model serving works — all driven through the AWS API so
you can read every step. Then tear it down.

**Your account is ready:** G-instance quota = 8 vCPUs (no approval wait), region
`us-east-1`, g6.xlarge spot ≈ $0.68/hr. A 2-hour session ≈ **$1.40–1.60**.

## The flow

```
./gpu-up.sh                     # launch g6.xlarge (L4 24GB), locked to your IP
# it prints the SSH command + the .env values to use

scp -i tandem-vllm-key.pem vllm-serve.sh ubuntu@<IP>:~
ssh -i tandem-vllm-key.pem ubuntu@<IP> 'bash vllm-serve.sh'   # serve Nemotron w/ vLLM

# edit ../../.env:
#   LLM_BASE_URL=http://<IP>:8000/v1
#   LLM_MODEL=nvidia/Nemotron-Mini-4B-Instruct
#   LLM_API_KEY=dummy
# restart the backend -> the app now runs on YOUR vLLM server

./gpu-down.sh                   # ⛔ terminate + stop billing when done
```

## What each script teaches

- **gpu-up.sh** — the cloud-ops half: resolving a driver-ready AMI (SSM), key pairs,
  a security group locked to your IP, `run-instances`, waiting for boot. This is
  "how you get a GPU in the cloud", the part Nebius/Token Factory hides from you.
- **vllm-serve.sh** — the serving half: `vllm serve` via Docker. In its logs you'll
  literally see `# GPU blocks: N` (the KV cache it carved out of VRAM) and requests
  being **continuously batched** — the two mechanisms we discussed, live.
- **gpu-down.sh** — the discipline half: always tear GPUs down; a forgotten one bills 24/7.

## Notes / gotchas
- **Same app, zero code change.** vLLM speaks the OpenAI-compatible API, so switching
  Ollama → your vLLM → Nebius is only `.env`. That's the whole point.
- **First serve is slow** (image pull + weight download) and you pay GPU time for it.
- **Bigger models** need more GPU: 70B wants 2× H100 and gets pricey — stick to a
  small Nemotron (~4–8B) on the L4 for learning.
- If `run-instances` returns AccessDenied, your IAM user lacks EC2 create perms —
  add them in IAM, then retry.
- **Always run `./gpu-down.sh`.** Set a phone alarm as backup.
