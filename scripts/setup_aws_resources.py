#!/usr/bin/env python3
"""
Setup AWS resources for ASHA Worker Copilot.
Run this ONCE before deploying the application.

Usage:
    python setup_aws_resources.py

Required env vars (or AWS CLI profile):
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
"""
import boto3
import json
import os
import sys

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
ACCOUNT_ID = None  # Will be resolved from STS

boto_kwargs = {
    "region_name": REGION,
}

dynamodb = boto3.client("dynamodb", **boto_kwargs)
s3 = boto3.client("s3", **boto_kwargs)
cognito = boto3.client("cognito-idp", **boto_kwargs)
sts = boto3.client("sts", **boto_kwargs)


def get_account_id():
    global ACCOUNT_ID
    ACCOUNT_ID = sts.get_caller_identity()["Account"]
    print(f"✅ AWS Account: {ACCOUNT_ID} | Region: {REGION}")


def create_dynamodb_table(name, pk, sk=None, gsi=None):
    """Create a DynamoDB table with optional GSI."""
    key_schema = [{"AttributeName": pk, "KeyType": "HASH"}]
    attr_defs = [{"AttributeName": pk, "AttributeType": "S"}]

    if sk:
        key_schema.append({"AttributeName": sk, "KeyType": "RANGE"})
        attr_defs.append({"AttributeName": sk, "AttributeType": "S"})

    kwargs = {
        "TableName": name,
        "KeySchema": key_schema,
        "AttributeDefinitions": attr_defs,
        "BillingMode": "PAY_PER_REQUEST",
        "Tags": [
            {"Key": "Project", "Value": "asha-copilot"},
            {"Key": "Environment", "Value": "production"},
        ],
    }

    if gsi:
        for g in gsi:
            attr_defs.append(g["attr_def"])
        kwargs["AttributeDefinitions"] = attr_defs
        kwargs["GlobalSecondaryIndexes"] = [g["index"] for g in gsi]

    try:
        dynamodb.create_table(**kwargs)
        print(f"  ✅ DynamoDB table '{name}' created")
    except dynamodb.exceptions.ResourceInUseException:
        print(f"  ℹ️  DynamoDB table '{name}' already exists — skipping")


def create_s3_bucket(bucket_name):
    """Create S3 bucket with versioning and server-side encryption."""
    try:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        # Enable versioning
        s3.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={"Status": "Enabled"},
        )
        # Enable SSE-S3 encryption (best practice)
        s3.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
            },
        )
        # Block public access
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        print(f"  ✅ S3 bucket '{bucket_name}' created with encryption + versioning")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"  ℹ️  S3 bucket '{bucket_name}' already exists — skipping")
    except Exception as e:
        print(f"  ⚠️  S3 bucket '{bucket_name}' error: {e}")


def create_cognito_user_pool():
    """Create Cognito User Pool for ASHA workers."""
    try:
        resp = cognito.create_user_pool(
            PoolName="asha-copilot-workers",
            Policies={
                "PasswordPolicy": {
                    "MinimumLength": 8,
                    "RequireUppercase": True,
                    "RequireLowercase": True,
                    "RequireNumbers": True,
                    "RequireSymbols": False,
                }
            },
            AutoVerifiedAttributes=["email"],
            UsernameAttributes=["email"],
            Schema=[
                {"Name": "email", "AttributeDataType": "String", "Required": True, "Mutable": True},
                {"Name": "name", "AttributeDataType": "String", "Required": True, "Mutable": True},
                {"Name": "area", "AttributeDataType": "String", "Required": False, "Mutable": True},
                {"Name": "role", "AttributeDataType": "String", "Required": False, "Mutable": True},
            ],
            UserPoolTags={"Project": "asha-copilot"},
        )
        pool_id = resp["UserPool"]["Id"]
        print(f"  ✅ Cognito User Pool created: {pool_id}")

        # Create app client
        client_resp = cognito.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName="asha-copilot-app",
            GenerateSecret=False,
            ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
            AccessTokenValidity=1,
            IdTokenValidity=1,
            RefreshTokenValidity=30,
            TokenValidityUnits={"AccessToken": "hours", "IdToken": "hours", "RefreshToken": "days"},
        )
        client_id = client_resp["UserPoolClient"]["ClientId"]
        print(f"  ✅ Cognito App Client created: {client_id}")
        print(f"\n  ⚠️  UPDATE these in your .env file:")
        print(f"      COGNITO_USER_POOL_ID={pool_id}")
        print(f"      COGNITO_CLIENT_ID={client_id}")
        return pool_id, client_id

    except Exception as e:
        print(f"  ⚠️  Cognito error: {e}")
        return None, None


def main():
    print("\n🚀 Setting up AWS resources for ASHA Worker Copilot\n")
    get_account_id()

    print("\n📦 Creating DynamoDB tables...")

    create_dynamodb_table("asha-patients", "patient_id", gsi=[{
        "attr_def": {"AttributeName": "asha_worker_id", "AttributeType": "S"},
        "index": {
            "IndexName": "asha_worker_index",
            "KeySchema": [{"AttributeName": "asha_worker_id", "KeyType": "HASH"}],
            "Projection": {"ProjectionType": "ALL"},
        },
    }])

    create_dynamodb_table("asha-assessments", "patient_id", sk="assessment_id")

    create_dynamodb_table("asha-vaccinations", "patient_id", sk="vaccine_name", gsi=[{
        "attr_def": {"AttributeName": "asha_worker_id", "AttributeType": "S"},
        "index": {
            "IndexName": "asha_due_index",
            "KeySchema": [{"AttributeName": "asha_worker_id", "KeyType": "HASH"}],
            "Projection": {"ProjectionType": "ALL"},
        },
    }])

    create_dynamodb_table("asha-sessions", "session_id")

    print("\n🪣 Creating S3 buckets...")
    create_s3_bucket("asha-copilot-guidelines")
    create_s3_bucket("asha-copilot-audio")

    print("\n🔐 Creating Cognito User Pool...")
    create_cognito_user_pool()

    print("\n✅ AWS resource setup complete!")
    print("\n📝 Next steps:")
    print("   1. Update backend/.env with Cognito pool ID and client ID printed above")
    print("   2. Run: python scripts/upload_guidelines.py (upload medical knowledge base)")
    print("   3. Enable Bedrock model access in AWS Console → Bedrock → Model Access")
    print("      → Request access for: Claude 3 Sonnet, Titan Embeddings V2")
    print("   4. Create Bedrock Knowledge Base in console and update .env with KB ID")
    print("   5. Deploy the application to EC2\n")


if __name__ == "__main__":
    main()
