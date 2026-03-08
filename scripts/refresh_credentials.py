#!/usr/bin/env python3
"""
Refresh AWS credentials in backend/.env using the current AWS CLI session.

Run this whenever credentials expire (typically every few hours when using
IAM Identity Center / Kiro login sessions):

    python scripts/refresh_credentials.py

Requires AWS CLI v2 to be installed and you must be logged in
(run your Kiro login flow or `aws sso login` first if not).
"""
import subprocess
import os
import re
import sys

AWS_CLI = r"C:\Program Files\Amazon\AWSCLIV2\aws.exe"
ENV_FILE = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")


def get_credentials():
    """Export current AWS CLI credentials as env vars."""
    result = subprocess.run(
        [AWS_CLI, "configure", "export-credentials", "--format", "env-no-export"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"❌ Failed to export credentials: {result.stderr}")
        print("   Make sure you are logged in. Run your Kiro/SSO login flow first.")
        sys.exit(1)

    creds = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            creds[key.strip()] = value.strip()
    return creds


def update_env_file(creds):
    """Write credentials into backend/.env, replacing existing values."""
    env_path = os.path.abspath(ENV_FILE)
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()

    def set_value(text, key, value):
        pattern = rf"^({re.escape(key)}=).*$"
        replacement = rf"\g<1>{value}"
        new_text, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
        if count == 0:
            # Key not found — append it
            new_text = text.rstrip() + f"\n{key}={value}\n"
        return new_text

    content = set_value(content, "AWS_ACCESS_KEY_ID", creds.get("AWS_ACCESS_KEY_ID", ""))
    content = set_value(content, "AWS_SECRET_ACCESS_KEY", creds.get("AWS_SECRET_ACCESS_KEY", ""))
    content = set_value(content, "AWS_SESSION_TOKEN", creds.get("AWS_SESSION_TOKEN", ""))

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)

    expiry = creds.get("AWS_CREDENTIAL_EXPIRATION", "unknown")
    print(f"✅ Credentials written to backend/.env")
    print(f"   Access Key: {creds.get('AWS_ACCESS_KEY_ID', '')[:12]}...")
    print(f"   Expires:    {expiry}")
    print(f"\n⚠️  Restart the backend server to pick up new credentials.")


def main():
    print("🔑 Refreshing AWS credentials in backend/.env ...\n")
    if not os.path.exists(AWS_CLI):
        print(f"❌ AWS CLI not found at: {AWS_CLI}")
        sys.exit(1)
    creds = get_credentials()
    update_env_file(creds)


if __name__ == "__main__":
    main()
