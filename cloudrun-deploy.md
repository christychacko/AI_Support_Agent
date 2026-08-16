# Deploying to GCP Cloud Run (free tier) — step by step

Cloud Run's free tier gives you **2 million requests/month, 360k GB-seconds
of memory, and 180k vCPU-seconds** — enough to run this project for free
indefinitely at low traffic.

## One-time setup

1. Create a free GCP account (new accounts also get $300 in credits):
   https://console.cloud.google.com

2. Install the `gcloud` CLI: https://cloud.google.com/sdk/docs/install

3. Create a project and enable billing (required even for free tier, but
   you won't be charged unless you exceed the free quota):
   ```bash
   gcloud projects create my-support-agent --name="AI Support Agent"
   gcloud config set project my-support-agent
   ```

4. Enable the required APIs:
   ```bash
   gcloud services enable run.googleapis.com \
     artifactregistry.googleapis.com \
     cloudbuild.googleapis.com
   ```

5. Create an Artifact Registry repo (free, stores your Docker images):
   ```bash
   gcloud artifacts repositories create support-agent \
     --repository-format=docker \
     --location=us-central1
   ```

## Manual deploy (do this once to confirm it works)

```bash
gcloud builds submit --tag us-central1-docker.pkg.dev/my-support-agent/support-agent/api

gcloud run deploy support-agent \
  --image us-central1-docker.pkg.dev/my-support-agent/support-agent/api \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GROQ_API_KEY=your_groq_key_here \
  --memory 1Gi
```

You'll get a public URL like `https://support-agent-xxxx-uc.a.run.app`.

## Automated deploy via GitHub Actions

1. Create a service account with deploy permissions:
   ```bash
   gcloud iam service-accounts create gh-deployer \
     --display-name "GitHub Actions Deployer"

   gcloud projects add-iam-policy-binding my-support-agent \
     --member="serviceAccount:gh-deployer@my-support-agent.iam.gserviceaccount.com" \
     --role="roles/run.admin"

   gcloud projects add-iam-policy-binding my-support-agent \
     --member="serviceAccount:gh-deployer@my-support-agent.iam.gserviceaccount.com" \
     --role="roles/artifactregistry.writer"

   gcloud projects add-iam-policy-binding my-support-agent \
     --member="serviceAccount:gh-deployer@my-support-agent.iam.gserviceaccount.com" \
     --role="roles/iam.serviceAccountUser"

   gcloud iam service-accounts keys create key.json \
     --iam-account=gh-deployer@my-support-agent.iam.gserviceaccount.com
   ```

2. In your GitHub repo → Settings → Secrets and variables → Actions, add:
   - `GCP_SA_KEY` → paste the full contents of `key.json`
   - `GCP_PROJECT_ID` → `my-support-agent`
   - `GROQ_API_KEY` → your free Groq key

3. Delete `key.json` locally (never commit it!) and push to `main`.
   `.github/workflows/deploy.yml` will build, test, and deploy automatically.

## Notes for a beginner

- Cloud Run containers are stateless between deploys — the SQLite files
  (`support.db`, `checkpoints.sqlite`, Chroma index) will reset on every new
  revision unless you mount a persistent volume. For learning/demo purposes
  this is fine. For real production memory/DB, swap SQLite for a managed
  Postgres (e.g. free-tier Neon/Supabase) — only `app/config.py` and the
  checkpointer/order-tool connection strings need to change.
- Keep `--allow-unauthenticated` only while testing; add IAM/API-key auth
  before handling real customer data.
