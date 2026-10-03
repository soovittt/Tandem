#!/usr/bin/env bash
#
# STOP BILLING: terminate the GPU box (and leave the SG + key pair for reuse).
# Safe to run anytime -- it only touches instances tagged Project=tandem-vllm.
#
# Usage:  ./gpu-down.sh
set -euo pipefail

REGION="${REGION:-us-east-1}"
PROJECT="tandem-vllm"

IDS=$(aws ec2 describe-instances --region "$REGION" \
  --filters "Name=tag:Project,Values=$PROJECT" \
            "Name=instance-state-name,Values=running,pending,stopped,stopping" \
  --query 'Reservations[].Instances[].InstanceId' --output text)

if [ -z "$IDS" ]; then
  echo "No instances tagged Project=$PROJECT. Nothing to terminate."
  exit 0
fi

echo "Terminating: $IDS"
aws ec2 terminate-instances --region "$REGION" --instance-ids $IDS >/dev/null
aws ec2 wait instance-terminated --region "$REGION" --instance-ids $IDS
echo "✅ Terminated. Billing stopped."
echo "(Kept the security group + key pair for next time. Delete manually if you want them gone.)"
