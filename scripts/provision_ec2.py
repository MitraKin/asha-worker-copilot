#!/usr/bin/env python3
"""
One-shot AWS infrastructure provisioner for ASHA Worker Copilot EC2 deployment.
Creates: IAM role, instance profile, security group, key pair, EC2 instance, Elastic IP.

Run from project root:
    python scripts/provision_ec2.py
"""
import subprocess
import json
import sys
import time
import os
import base64

AWS = r"C:\Program Files\Amazon\AWSCLIV2\aws.exe"
REGION = "us-east-1"
GITHUB_REPO = "https://github.com/MitraKin/asha-worker-copilot.git"

ROLE_NAME = "asha-copilot-ec2-role"
INSTANCE_PROFILE_NAME = "asha-copilot-ec2-profile"
SG_NAME = "asha-copilot-sg"
KEY_NAME = "asha-copilot-key"
INSTANCE_TYPE = "t3.small"
AMI_PARAM = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"


def aws(*args):
    cmd = [AWS, "--region", REGION, "--output", "json"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {"_error": result.stderr.strip()}
    if result.stdout.strip():
        return json.loads(result.stdout)
    return {}


def step(msg):
    print(f"\n{'='*60}\n  {msg}\n{'='*60}")


def create_iam_role():
    step("1/7  Creating IAM Role for EC2")
    trust_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    })
    result = aws("iam", "create-role",
                 "--role-name", ROLE_NAME,
                 "--assume-role-policy-document", trust_policy,
                 "--description", "ASHA Worker Copilot EC2 role")
    if "_error" in result:
        if "EntityAlreadyExists" in result["_error"]:
            print(f"  Role '{ROLE_NAME}' already exists — reusing")
        else:
            print(f"  Warning: {result['_error']}")
    else:
        print(f"  Created role: {ROLE_NAME}")

    policies = [
        "arn:aws:iam::aws:policy/AmazonBedrockFullAccess",
        "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess",
        "arn:aws:iam::aws:policy/AmazonS3FullAccess",
        "arn:aws:iam::aws:policy/AmazonTranscribeFullAccess",
        "arn:aws:iam::aws:policy/TranslateFullAccess",
        "arn:aws:iam::aws:policy/AmazonPollyFullAccess",
        "arn:aws:iam::aws:policy/AmazonCognitoPowerUser",
    ]
    for arn in policies:
        r = aws("iam", "attach-role-policy", "--role-name", ROLE_NAME, "--policy-arn", arn)
        name = arn.split("/")[-1]
        if "_error" in r and "already exists" not in r.get("_error", "").lower():
            print(f"  Warning attaching {name}: {r['_error']}")
        else:
            print(f"  Attached: {name}")

    r = aws("iam", "create-instance-profile",
            "--instance-profile-name", INSTANCE_PROFILE_NAME)
    if "_error" in r:
        if "EntityAlreadyExists" in r["_error"]:
            print(f"  Instance profile already exists — reusing")
        else:
            print(f"  Warning: {r['_error']}")
    else:
        print(f"  Instance profile created")

    r = aws("iam", "add-role-to-instance-profile",
            "--instance-profile-name", INSTANCE_PROFILE_NAME,
            "--role-name", ROLE_NAME)
    if "_error" in r:
        if "LimitExceeded" in r["_error"] or "Cannot exceed" in r["_error"]:
            print(f"  Role already attached to instance profile")
        else:
            print(f"  Note: {r['_error']}")
    else:
        print(f"  Role added to instance profile")

    print("  Waiting 10s for IAM propagation...")
    time.sleep(10)


def create_security_group():
    step("2/7  Creating Security Group")
    vpcs = aws("ec2", "describe-vpcs", "--filters", "Name=isDefault,Values=true")
    vpc_id = None
    if "_error" not in vpcs and vpcs.get("Vpcs"):
        vpc_id = vpcs["Vpcs"][0]["VpcId"]
        print(f"  VPC: {vpc_id}")

    sg_args = ["ec2", "create-security-group",
               "--group-name", SG_NAME,
               "--description", "ASHA Worker Copilot - HTTP HTTPS SSH"]
    if vpc_id:
        sg_args += ["--vpc-id", vpc_id]

    r = aws(*sg_args)
    if "_error" in r:
        if "already exists" in r["_error"]:
            print(f"  Security group already exists — looking up ID")
            sgs = aws("ec2", "describe-security-groups",
                      "--filters", f"Name=group-name,Values={SG_NAME}")
            if "_error" in sgs or not sgs.get("SecurityGroups"):
                print(f"  Error finding SG: {sgs}")
                return None
            sg_id = sgs["SecurityGroups"][0]["GroupId"]
        else:
            print(f"  Error: {r['_error']}")
            return None
    else:
        sg_id = r["GroupId"]
        print(f"  Security group created: {sg_id}")

    for port, desc in [(22, "SSH"), (80, "HTTP"), (443, "HTTPS")]:
        r = aws("ec2", "authorize-security-group-ingress",
                "--group-id", sg_id, "--protocol", "tcp",
                "--port", str(port), "--cidr", "0.0.0.0/0")
        if "_error" in r and "already exists" in r.get("_error", ""):
            print(f"  Port {port} ({desc}) rule already exists")
        elif "_error" in r:
            print(f"  Warning port {port}: {r['_error']}")
        else:
            print(f"  Allowed inbound port {port} ({desc})")

    return sg_id


def create_key_pair():
    step("3/7  Creating EC2 Key Pair")
    key_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", f"{KEY_NAME}.pem"))

    r = aws("ec2", "create-key-pair", "--key-name", KEY_NAME, "--key-type", "rsa")
    if "_error" in r:
        if "already exists" in r["_error"]:
            print(f"  Key pair '{KEY_NAME}' already exists — reusing")
            return KEY_NAME
        else:
            print(f"  Error: {r['_error']}")
            return None

    pem = r.get("KeyMaterial", "")
    with open(key_file, "w") as f:
        f.write(pem)
    print(f"  Key saved to: {key_file}")
    print(f"  IMPORTANT: Keep this .pem file safe — it's the only copy!")
    return KEY_NAME


def get_latest_ami():
    step("4/7  Resolving latest Amazon Linux 2023 AMI")
    r = aws("ssm", "get-parameter", "--name", AMI_PARAM)
    if "_error" in r:
        print(f"  Could not resolve AMI via SSM — using known AL2023 AMI")
        return "ami-0c02fb55956c7d316"
    ami_id = r["Parameter"]["Value"]
    print(f"  AMI: {ami_id}")
    return ami_id


def build_user_data():
    """Build the EC2 User Data bootstrap script (runs on first boot as root)."""
    script = f"""#!/bin/bash
set -ex
exec > /var/log/asha-setup.log 2>&1

echo "=== ASHA Worker Copilot EC2 Bootstrap ==="
echo "Started: $(date)"

# 1. Install packages
dnf update -y
dnf install -y git nginx python3.11 python3.11-pip nodejs npm
alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 || true

# 2. Clone repository
APP_DIR="/opt/asha-copilot"
rm -rf "$APP_DIR"
git clone {GITHUB_REPO} "$APP_DIR"
chown -R ec2-user:ec2-user "$APP_DIR"

# 3. Production .env (IAM Instance Role handles AWS credentials — no keys needed)
SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
cat > "$APP_DIR/backend/.env" << ENVEOF
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=$SECRET
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=
BEDROCK_MODEL_ID=amazon.nova-pro-v1:0
BEDROCK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_API_KEY=
BEDROCK_KNOWLEDGE_BASE_ID=
BEDROCK_DATA_SOURCE_ID=
COGNITO_USER_POOL_ID=us-east-1_PfhijEVpM
COGNITO_CLIENT_ID=6pdhbp4n418ubbp61t9ln5ikpm
COGNITO_REGION=us-east-1
DYNAMO_PATIENTS_TABLE=asha-patients
DYNAMO_ASSESSMENTS_TABLE=asha-assessments
DYNAMO_VACCINATIONS_TABLE=asha-vaccinations
DYNAMO_SESSIONS_TABLE=asha-sessions
S3_GUIDELINES_BUCKET=asha-copilot-guidelines
S3_AUDIO_BUCKET=asha-copilot-audio
ENVEOF

# 4. Backend virtual environment + dependencies
cd "$APP_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. systemd service for FastAPI backend
cat > /etc/systemd/system/asha-backend.service << 'SVCEOF'
[Unit]
Description=ASHA Worker Copilot FastAPI Backend
After=network.target

[Service]
User=ec2-user
Group=ec2-user
WorkingDirectory=/opt/asha-copilot/backend
EnvironmentFile=/opt/asha-copilot/backend/.env
ExecStart=/opt/asha-copilot/backend/venv/bin/gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --timeout 120 --access-logfile /var/log/asha-backend-access.log --error-logfile /var/log/asha-backend-error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

# 6. Build React frontend
cd "$APP_DIR/frontend"
npm ci
npm run build

# 7. Nginx configuration
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/conf.d/asha-copilot.conf
rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true
nginx -t

# 8. Start services
systemctl daemon-reload
systemctl enable --now asha-backend
systemctl enable --now nginx

# 9. Deploy helper script for CI/CD pulls
cat > /opt/asha-copilot/deploy/pull-and-restart.sh << 'DEPLOYEOF'
#!/bin/bash
set -e
cd /opt/asha-copilot
git pull origin master
cd backend && source venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm ci && npm run build
sudo systemctl restart asha-backend
sudo systemctl restart nginx
echo "Deploy complete at $(date)"
DEPLOYEOF
chmod +x /opt/asha-copilot/deploy/pull-and-restart.sh

echo "=== Setup Complete ==="
echo "Finished: $(date)"
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "unknown")
echo "URL: http://$PUBLIC_IP"
"""
    return base64.b64encode(script.encode()).decode()


def launch_instance(ami_id, sg_id, key_name):
    step("5/7  Launching EC2 Instance")
    user_data = build_user_data()

    r = aws("ec2", "run-instances",
            "--image-id", ami_id,
            "--instance-type", INSTANCE_TYPE,
            "--key-name", key_name,
            "--security-group-ids", sg_id,
            "--iam-instance-profile", f"Name={INSTANCE_PROFILE_NAME}",
            "--user-data", user_data,
            "--tag-specifications",
            'ResourceType=instance,Tags=[{Key=Name,Value=asha-copilot},{Key=Project,Value=asha-copilot}]',
            "--block-device-mappings",
            '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":20,"VolumeType":"gp3"}}]',
            "--count", "1")

    if "_error" in r:
        print(f"  Launch failed: {r['_error']}")
        return None

    instance_id = r["Instances"][0]["InstanceId"]
    print(f"  Instance launched: {instance_id}")
    print(f"  Waiting for running state...")

    aws("ec2", "wait", "instance-running", "--instance-ids", instance_id)
    print(f"  Instance is running!")
    return instance_id


def allocate_elastic_ip(instance_id):
    step("6/7  Allocating Elastic IP")
    r = aws("ec2", "allocate-address", "--domain", "vpc",
            "--tag-specifications",
            'ResourceType=elastic-ip,Tags=[{Key=Name,Value=asha-copilot},{Key=Project,Value=asha-copilot}]')
    if "_error" in r:
        print(f"  Warning: {r['_error']}")
        return None

    alloc_id = r["AllocationId"]
    public_ip = r["PublicIp"]
    print(f"  Elastic IP: {public_ip}")

    r2 = aws("ec2", "associate-address",
             "--instance-id", instance_id,
             "--allocation-id", alloc_id)
    if "_error" in r2:
        print(f"  Association warning: {r2['_error']}")
    else:
        print(f"  Associated with {instance_id}")

    return public_ip


def main():
    print("\n  ASHA Worker Copilot — EC2 Deployment Provisioner\n")

    if not os.path.exists(AWS):
        print(f"  AWS CLI not found at: {AWS}")
        sys.exit(1)

    identity = aws("sts", "get-caller-identity")
    if "_error" in identity:
        print(f"  Not authenticated: {identity['_error']}")
        print("  Run 'aws sso login' or 'python scripts/refresh_credentials.py' first.")
        sys.exit(1)
    print(f"  AWS Account: {identity['Account']}")
    print(f"  Region: {REGION}")

    # Step 1: IAM
    create_iam_role()

    # Step 2: Security Group
    sg_id = create_security_group()
    if not sg_id:
        print("  FATAL: Could not create/find security group")
        sys.exit(1)

    # Step 3: Key Pair
    key_name = create_key_pair()
    if not key_name:
        print("  FATAL: Could not create/find key pair")
        sys.exit(1)

    # Step 4: AMI
    ami_id = get_latest_ami()

    # Step 5: Launch
    instance_id = launch_instance(ami_id, sg_id, key_name)
    if not instance_id:
        print("  FATAL: Instance launch failed")
        sys.exit(1)

    # Step 6: Elastic IP
    public_ip = allocate_elastic_ip(instance_id)
    if not public_ip:
        desc = aws("ec2", "describe-instances", "--instance-ids", instance_id)
        try:
            public_ip = desc["Reservations"][0]["Instances"][0].get(
                "PublicIpAddress", "UNKNOWN")
        except (KeyError, IndexError):
            public_ip = "UNKNOWN"

    # Step 7: Summary
    step("7/7  Deployment Summary")
    print(f"  Instance ID: {instance_id}")
    print(f"  Public IP:   {public_ip}")
    print(f"  App URL:     http://{public_ip}")
    print(f"  API Docs:    http://{public_ip}/api/docs")
    print(f"  Health:      http://{public_ip}/health")
    print(f"  SSH:         ssh -i {KEY_NAME}.pem ec2-user@{public_ip}")
    print(f"  Setup Logs:  ssh -i {KEY_NAME}.pem ec2-user@{public_ip} "
          f"'sudo tail -f /var/log/asha-setup.log'")
    print()
    print("  Instance is bootstrapping (3-5 min). Check logs for progress.")
    print()
    print("  Next steps for CI/CD:")
    print(f"    1. Add GitHub secret EC2_HOST = {public_ip}")
    print(f"    2. Add GitHub secret EC2_SSH_KEY = contents of {KEY_NAME}.pem")
    print("    3. Push to master to trigger auto-deploy")

    # Save deployment info
    info = {
        "instance_id": instance_id,
        "public_ip": public_ip,
        "region": REGION,
        "key_name": key_name,
        "security_group": sg_id,
        "role": ROLE_NAME,
        "github_repo": GITHUB_REPO,
    }
    info_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "deploy", "deployment-info.json"))
    with open(info_file, "w") as f:
        json.dump(info, f, indent=2)
    print(f"\n  Saved: {info_file}")


if __name__ == "__main__":
    main()
