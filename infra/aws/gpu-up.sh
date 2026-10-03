#!/usr/bin/env bash
#
# Launch a single-GPU EC2 box to serve a model with vLLM -- entirely via the AWS
# API, so you can read exactly what each step does. This is the "learn how NVIDIA
# + vLLM serving works" session.
#
#   💸 It starts billing (~$0.80/hr on-demand, ~$0.68/hr spot) the moment the
#      instance boots. Run ./gpu-down.sh when you're done.
#
# Usage:  ./gpu-up.sh
# Vars:   REGION, INSTANCE_TYPE, USE_SPOT=1 to override defaults.
set -euo pipefail

REGION="${REGION:-us-east-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-g6.xlarge}"   # 1x L4 24GB, 4 vCPU (fits your 8-vCPU quota)
PROJECT="tandem-vllm"
KEY_NAME="$PROJECT-key"
SG_NAME="$PROJECT-sg"
PEM="$KEY_NAME.pem"

echo "[1/5] Resolving Deep Learning AMI (NVIDIA drivers + CUDA + Docker preinstalled)..."
AMI_ID=$(aws ssm get-parameter --region "$REGION" \
  --name /aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-22.04/latest/ami-id \
  --query 'Parameter.Value' --output text)
echo "      AMI = $AMI_ID"

echo "[2/5] Ensuring SSH key pair ($PEM)..."
if [ ! -f "$PEM" ]; then
  aws ec2 create-key-pair --region "$REGION" --key-name "$KEY_NAME" \
    --query 'KeyMaterial' --output text > "$PEM"
  chmod 600 "$PEM"
  echo "      created $PEM"
else
  echo "      reusing existing $PEM"
fi

echo "[3/5] Ensuring security group (SSH + vLLM open to YOUR IP only)..."
MYIP=$(curl -s https://checkip.amazonaws.com)
SG_ID=$(aws ec2 describe-security-groups --region "$REGION" \
  --filters "Name=group-name,Values=$SG_NAME" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)
if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  SG_ID=$(aws ec2 create-security-group --region "$REGION" \
    --group-name "$SG_NAME" --description "tandem vLLM learning box" \
    --query 'GroupId' --output text)
fi
# Open SSH (22) + vLLM (8000) to just your current IP. Rerun-safe (ignore dupes).
aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID" \
  --protocol tcp --port 22 --cidr "$MYIP/32" 2>/dev/null || true
aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID" \
  --protocol tcp --port 8000 --cidr "$MYIP/32" 2>/dev/null || true
echo "      SG = $SG_ID (locked to $MYIP)"

echo "[4/5] Launching $INSTANCE_TYPE (100GB gp3 root for model weights)..."
MARKET_OPTS=()
if [ "${USE_SPOT:-0}" = "1" ]; then
  MARKET_OPTS=(--instance-market-options '{"MarketType":"spot"}')
  echo "      (spot pricing)"
fi
INSTANCE_ID=$(aws ec2 run-instances --region "$REGION" \
  --image-id "$AMI_ID" --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" --security-group-ids "$SG_ID" \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":100,"VolumeType":"gp3"}}]' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Project,Value=$PROJECT}]" \
  "${MARKET_OPTS[@]}" \
  --query 'Instances[0].InstanceId' --output text)
echo "      instance = $INSTANCE_ID"

echo "[5/5] Waiting for it to boot..."
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"
IP=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

cat <<EOF

============================================================
✅ GPU box is UP (billing now — run ./gpu-down.sh when done)
   instance : $INSTANCE_ID
   SSH      : ssh -i $PEM ubuntu@$IP
------------------------------------------------------------
Next: copy the serve script over and run it, then watch vLLM boot:
   scp -i $PEM vllm-serve.sh ubuntu@$IP:~
   ssh -i $PEM ubuntu@$IP 'bash vllm-serve.sh'

Then point the app at it (edit ../../.env):
   LLM_BASE_URL=http://$IP:8000/v1
   LLM_MODEL=nvidia/Nemotron-Mini-4B-Instruct
   LLM_API_KEY=dummy
============================================================
EOF
