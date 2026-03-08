# ASHA Worker Copilot — AI Health Assistant

[![Built with](https://img.shields.io/badge/Built%20with-Amazon%20Bedrock-orange)](https://aws.amazon.com/bedrock/)
[![Language](https://img.shields.io/badge/Language-Python%20FastAPI-blue)](https://fastapi.tiangolo.com/)
[![Frontend](https://img.shields.io/badge/Frontend-React%20Vite-61dafb)](https://vitejs.dev/)

> Multilingual voice-first AI health assistant for ASHA workers in rural India — **AI for Bharat Hackathon 2024**

---

## 🎯 Problem Statement

ASHA (Accredited Social Health Activists) workers are India's frontline health workforce serving over 1.3 billion people in rural areas. They struggle with:
- Conducting structured assessments without formal medical training
- Tracking maternal health and vaccination schedules across hundreds of patients
- Communicating in regional languages
- Identifying high-risk cases needing urgent referral

## 💡 Solution

ASHA Copilot is an always-on web app that guides ASHA workers through **AI-powered voice health assessments in Hindi and regional languages**, powered entirely by AWS AI services.

---

## 🏗️ Architecture

```
Browser (React) ──HTTPS──▶ Nginx ──▶ FastAPI Backend
                                        │
                              ┌─────────┼──────────────┐
                           Bedrock  Transcribe      DynamoDB
                           Claude   Translate       S3
                           RAG/KB   Polly           Cognito
```

**Deployment**: EC2 `t3.small` · Nginx reverse proxy · systemd (always running) · Elastic IP

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, Gunicorn + Uvicorn |
| Frontend | React 18, Vite, React Router |
| LLM | Amazon Bedrock — Claude 3 Sonnet |
| Voice I/O | Amazon Transcribe + Polly |
| Translation | Amazon Translate |
| RAG | Bedrock Knowledge Base + S3 |
| Database | Amazon DynamoDB |
| Auth | Amazon Cognito |
| Deployment | EC2, Nginx, systemd |

---

## 📋 Key Features

| Feature | AWS Services |
|---------|-------------|
| Voice assessment (Hindi/regional) | Transcribe, Translate, Polly |
| AI-guided question flow | Bedrock Claude 3 |
| Medical guideline RAG | Bedrock Knowledge Base, S3 |
| Maternal risk scoring | Bedrock + ICMR guidelines |
| Emergency detection & alert | Bedrock + keyword detection |
| Vaccination schedule (Govt. UIP) | DynamoDB |
| Patient management | DynamoDB |
| Secure authentication | Amazon Cognito |

---

## 🚀 Getting Started

### Prerequisites

1. AWS Account with IAM credentials
2. **Bedrock model access** enabled for:
   - `anthropic.claude-3-sonnet-20240229-v1:0`
   - `amazon.titan-embed-text-v2:0`
3. AWS CLI configured (`aws configure`)
4. Python 3.11+, Node.js 18+

### Step 1: Setup AWS Resources

```bash
pip install boto3
python scripts/setup_aws_resources.py
```

This creates DynamoDB tables, S3 buckets, and Cognito User Pool.

### Step 2: Configure Environment

```bash
cp backend/.env.example backend/.env
# Fill in Cognito IDs printed by the setup script above
```

### Step 3: Bedrock Knowledge Base (RAG)

1. Open **AWS Console → Amazon Bedrock → Knowledge Bases → Create**
2. Name: `asha-medical-guidelines`
3. Data source: S3 → `asha-copilot-guidelines/guidelines/`
4. Embeddings: Titan Embeddings V2 · Vector store: OpenSearch Serverless
5. Run: `python scripts/upload_guidelines.py` then sync the data source
6. Paste Knowledge Base ID → `BEDROCK_KNOWLEDGE_BASE_ID` in `.env`

### Step 4: Run Locally

```bash
# Terminal 1 — Backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && npm install && npm run dev
# Open http://localhost:3000
```

### Step 5: Deploy to EC2

```bash
# On EC2 instance (Amazon Linux 2023, t3.small):
sudo bash deploy/setup_ec2.sh
```

---

## 📁 Project Structure

```
Asha_Worker_copilot/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings from env vars
│   ├── routers/                 # API routes (auth, patients, assessment, vaccination)
│   ├── services/                # AWS service wrappers (Bedrock, Transcribe, Polly...)
│   ├── models/                  # Pydantic models
│   ├── prompts/                 # Bedrock medical system prompts
│   └── knowledge_base/
│       └── guidelines/          # Medical guidelines JSONs (RAG source)
├── frontend/
│   └── src/
│       ├── pages/               # Login, Dashboard, Assessment, Patients, Vaccination
│       └── components/          # Layout, shared UI components
├── deploy/
│   ├── setup_ec2.sh             # EC2 provisioning script
│   └── nginx.conf               # Nginx reverse proxy config
└── scripts/
    ├── setup_aws_resources.py   # One-time AWS resource creation
    └── upload_guidelines.py     # Upload RAG knowledge base to S3
```

---

## 🔐 Security

- All API endpoints protected by Cognito JWT token validation
- S3 public access blocked + SSE-S3 encryption at rest
- DynamoDB encrypted at rest by default
- ASHA workers can only access their own patient records
- HTTPS via Let's Encrypt / ACM

---

## 🧪 Testing the App

1. Register as ASHA worker → verify email OTP
2. Add a patient (pregnant woman, child)
3. Start assessment → choose Hindi → press 🎤 → speak symptoms
4. AI asks follow-up questions → generates risk score with ICMR guideline references
5. Generate vaccination schedule (Govt. of India UIP)
6. Emergency test: say "bahut khoon" → emergency alert triggers with 108 call prompt

---

*Built for the AI for Bharat Hackathon — healthcare for rural India using AWS AI.*
