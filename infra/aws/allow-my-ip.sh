#!/usr/bin/env bash
#
# Authorize YOUR current public IP on the GPU box's security group (SSH + :8000).
#
# Run this whenever SSH and/or the vLLM endpoint (:8000) start timing out — that's
# almost always your home IP changing, NOT the box hanging. The SG is IP-locked to a
# single /32 for safety, so a new IP gets blocked on both ports.
set -euo pipefail

REGION="${REGION:-us-east-1}"
SG="${SG:-sg-04a5cedf239a98553}"

MYIP=$(curl -s -m 10 https://checkip.amazonaws.com | tr -d '[:space:]')
if [ -z "$MYIP" ]; then echo "Could not determine your public IP."; exit 1; fi
echo "Your public IP: $MYIP"

for PORT in 22 8000; do
  if aws ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp \
       --port "$PORT" --cidr "$MYIP/32" --region "$REGION" >/dev/null 2>&1; then
    echo "  allowed $MYIP on port $PORT"
  else
    echo "  port $PORT already allows $MYIP (or add failed)"
  fi
done
echo "Done. SSH + :8000 should work from this network now."
