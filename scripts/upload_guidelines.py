#!/usr/bin/env python3
"""
Upload medical guidelines to S3 for the Bedrock Knowledge Base (RAG).
Run after setup_aws_resources.py.

Usage:
    python scripts/upload_guidelines.py
"""
import boto3
import json
import os
import glob

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
BUCKET = "asha-copilot-guidelines"
GUIDELINES_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "knowledge_base", "guidelines")

s3 = boto3.client("s3", region_name=REGION)


def upload_guidelines():
    print(f"\n📚 Uploading medical guidelines to s3://{BUCKET}/\n")
    json_files = glob.glob(os.path.join(GUIDELINES_DIR, "*.json"))

    if not json_files:
        print("⚠️  No guideline files found in backend/knowledge_base/guidelines/")
        return

    for filepath in json_files:
        filename = os.path.basename(filepath)
        s3_key = f"guidelines/{filename}"
        try:
            s3.upload_file(
                filepath, BUCKET, s3_key,
                ExtraArgs={"ContentType": "application/json"},
            )
            print(f"  ✅ Uploaded: {filename} → s3://{BUCKET}/{s3_key}")
        except Exception as e:
            print(f"  ❌ Failed to upload {filename}: {e}")

    print("\n✅ Guidelines uploaded!")
    print("\n📝 Next: Create Bedrock Knowledge Base in AWS Console:")
    print("   1. Go to Amazon Bedrock → Knowledge Bases → Create knowledge base")
    print("   2. Name: asha-medical-guidelines")
    print("   3. Data source: S3 → asha-copilot-guidelines/guidelines/")
    print("   4. Embeddings model: Titan Embeddings V2")
    print("   5. Vector store: OpenSearch Serverless (managed)")
    print("   6. After creation, copy Knowledge Base ID → set BEDROCK_KNOWLEDGE_BASE_ID in .env\n")


if __name__ == "__main__":
    upload_guidelines()
