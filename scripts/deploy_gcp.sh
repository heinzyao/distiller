#!/usr/bin/env bash
# =============================================================================
# Distiller GCP 初次部署腳本
#
# 用法：
#   export GCP_PROJECT_ID=your-project-id
#   bash scripts/deploy_gcp.sh
#
# 前置需求：
#   - gcloud CLI 已安裝並登入 (gcloud auth login)
#   - 專案目錄下存在 .env（含 LINE_CHANNEL_ID / LINE_CHANNEL_SECRET / LINE_USER_ID）
#   - Docker 已安裝（用於本機建置測試）
#
# 安全注意事項：
#   - 機敏值透過 stdin pipe 傳入 gcloud，不會出現在 ps / shell history
#   - 本腳本不含任何明文憑證
# =============================================================================

set -euo pipefail

# ── 參數確認 ──────────────────────────────────────────────────────────────────

PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${CLOUD_RUN_REGION:-asia-east1}"
BUCKET_NAME="${GCS_BUCKET:-distiller-data}"
ENV_FILE="${ENV_FILE:-.env}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "❌ 請先設定環境變數：export GCP_PROJECT_ID=your-project-id"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ 找不到 $ENV_FILE，請先建立並填入 LINE 憑證"
  exit 1
fi

# 從 .env 讀取機敏值（不 export，不進入子 shell，不出現在 ps）
_read_env_value() {
  local key="$1"
  local value
  value=$(grep -E "^${key}=" "$ENV_FILE" | head -1 | cut -d= -f2-)
  if [[ -z "$value" ]]; then
    echo "❌ $ENV_FILE 中找不到 $key"
    exit 1
  fi
  printf '%s' "$value"
}

LINE_CHANNEL_ID=$(_read_env_value "LINE_CHANNEL_ID")
LINE_CHANNEL_SECRET=$(_read_env_value "LINE_CHANNEL_SECRET")
LINE_USER_ID=$(_read_env_value "LINE_USER_ID")

echo "✅ 讀取 .env 完成（值不會顯示於終端）"
echo ""
echo "📋 部署參數"
echo "  Project  : $PROJECT_ID"
echo "  Region   : $REGION"
echo "  Bucket   : $BUCKET_NAME"
echo ""

# ── Step 1: 啟用必要 API ───────────────────────────────────────────────────────

echo "▶ Step 1: 啟用 GCP APIs…"
gcloud services enable \
  run.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  --project="$PROJECT_ID"
echo "  ✅ APIs 已啟用"

# ── Step 2: 建立 GCS Bucket ───────────────────────────────────────────────────

echo ""
echo "▶ Step 2: 建立 GCS Bucket ($BUCKET_NAME)…"
if gcloud storage buckets describe "gs://${BUCKET_NAME}" \
     --project="$PROJECT_ID" &>/dev/null; then
  echo "  ℹ️  Bucket 已存在，跳過建立"
else
  gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --location="$REGION" \
    --project="$PROJECT_ID"
  echo "  ✅ Bucket 已建立"
fi

# 若本機有 distiller.db，上傳初始資料
if [[ -f "distiller.db" ]]; then
  echo "  📤 上傳本機 distiller.db 至 GCS…"
  gcloud storage cp distiller.db "gs://${BUCKET_NAME}/distiller.db" \
    --project="$PROJECT_ID"
  echo "  ✅ 初始資料已上傳"
fi

# ── Step 3: 建立 Secret Manager Secrets ──────────────────────────────────────

echo ""
echo "▶ Step 3: 建立 Secret Manager Secrets…"
echo "  （機敏值透過 stdin 傳入，不顯示於終端）"

_create_or_update_secret() {
  local name="$1"
  local value="$2"
  if gcloud secrets describe "$name" --project="$PROJECT_ID" &>/dev/null; then
    printf '%s' "$value" | \
      gcloud secrets versions add "$name" \
        --data-file=- \
        --project="$PROJECT_ID"
    echo "  🔄 $name — 已更新版本"
  else
    printf '%s' "$value" | \
      gcloud secrets create "$name" \
        --data-file=- \
        --replication-policy=automatic \
        --project="$PROJECT_ID"
    echo "  ✅ $name — 已建立"
  fi
}

_create_or_update_secret "LINE_CHANNEL_ID"     "$LINE_CHANNEL_ID"
_create_or_update_secret "LINE_CHANNEL_SECRET" "$LINE_CHANNEL_SECRET"
_create_or_update_secret "LINE_USER_ID"        "$LINE_USER_ID"

# 清除記憶體中的機敏值（bash 變數無法真正 shred，但減少暴露時間）
unset LINE_CHANNEL_ID LINE_CHANNEL_SECRET LINE_USER_ID

# ── Step 4: 授予 Service Account 存取權限 ─────────────────────────────────────

echo ""
echo "▶ Step 4: 設定 IAM 權限…"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" \
  --format="value(projectNumber)")
SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "  Service Account: $SA_EMAIL"

# GCS 讀寫
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectAdmin" \
  --project="$PROJECT_ID"

# Secret Manager 讀取
for secret in LINE_CHANNEL_ID LINE_CHANNEL_SECRET LINE_USER_ID; do
  gcloud secrets add-iam-policy-binding "$secret" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$PROJECT_ID"
done

# Cloud Run Jobs 呼叫（bot 需要觸發爬蟲）
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker"

echo "  ✅ IAM 權限已設定"

# ── Step 5: 建置並推送 Docker 映像 ────────────────────────────────────────────

echo ""
echo "▶ Step 5: 建置 Docker 映像…"

gcloud auth configure-docker gcr.io --quiet

echo "  🔨 建置爬蟲容器（含 Chrome，約 5-10 分鐘）…"
docker build \
  -f Dockerfile.scraper \
  -t "gcr.io/${PROJECT_ID}/distiller-scraper:latest" \
  .
docker push "gcr.io/${PROJECT_ID}/distiller-scraper:latest"
echo "  ✅ distiller-scraper 已推送"

echo "  🔨 建置 Bot 容器…"
docker build \
  -f Dockerfile.bot \
  -t "gcr.io/${PROJECT_ID}/distiller-bot:latest" \
  .
docker push "gcr.io/${PROJECT_ID}/distiller-bot:latest"
echo "  ✅ distiller-bot 已推送"

# ── Step 6: 部署 Cloud Run Job（爬蟲）────────────────────────────────────────

echo ""
echo "▶ Step 6: 部署 Cloud Run Job (distiller-scraper)…"

_secret_flags="LINE_CHANNEL_ID=DISTILLER_LINE_CHANNEL_ID:latest,LINE_CHANNEL_SECRET=DISTILLER_LINE_CHANNEL_SECRET:latest,LINE_USER_ID=DISTILLER_LINE_USER_ID:latest"

if gcloud run jobs describe distiller-scraper \
     --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
  gcloud run jobs update distiller-scraper \
    --image "gcr.io/${PROJECT_ID}/distiller-scraper:latest" \
    --region="$REGION" \
    --project="$PROJECT_ID"
  echo "  ✅ Cloud Run Job 已更新"
else
  gcloud run jobs create distiller-scraper \
    --image "gcr.io/${PROJECT_ID}/distiller-scraper:latest" \
    --region="$REGION" \
    --memory 2Gi \
    --cpu 2 \
    --task-timeout 3600 \
    --set-env-vars "GCS_BUCKET=${BUCKET_NAME}" \
    --set-secrets "$_secret_flags" \
    --project="$PROJECT_ID"
  echo "  ✅ Cloud Run Job 已建立"
fi

# ── Step 7: 部署 Cloud Run Service（Bot）────────────────────────────────────

echo ""
echo "▶ Step 7: 部署 Cloud Run Service (distiller-bot)…"

BOT_URL=$(gcloud run deploy distiller-bot \
  --image "gcr.io/${PROJECT_ID}/distiller-bot:latest" \
  --region="$REGION" \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 2 \
  --allow-unauthenticated \
  --set-env-vars "GCS_BUCKET=${BUCKET_NAME},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},CLOUD_RUN_REGION=${REGION}" \
  --set-secrets "$_secret_flags" \
  --project="$PROJECT_ID" \
  --format="value(status.url)" 2>/dev/null || true)

if [[ -z "$BOT_URL" ]]; then
  BOT_URL=$(gcloud run services describe distiller-bot \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --format="value(status.url)")
fi
echo "  ✅ Bot 已部署：$BOT_URL"

# ── Step 8: 設定 Cloud Scheduler（每日 10:00 台北時間）────────────────────────

echo ""
echo "▶ Step 8: 設定 Cloud Scheduler…"

JOBS_API_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/distiller-scraper:run"

if gcloud scheduler jobs describe distiller-daily-scrape \
     --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
  echo "  ℹ️  Scheduler 已存在，跳過建立"
else
  gcloud scheduler jobs create http distiller-daily-scrape \
    --schedule "0 2 * * *" \
    --time-zone "Asia/Taipei" \
    --uri "$JOBS_API_URI" \
    --http-method POST \
    --oauth-service-account-email "${SA_EMAIL}" \
    --location="$REGION" \
    --project="$PROJECT_ID"
  echo "  ✅ Scheduler 已建立（每日 UTC 02:00 = 台北 10:00）"
fi

# ── 完成摘要 ──────────────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════"
echo "✅ 部署完成！"
echo ""
echo "Bot Webhook URL："
echo "  ${BOT_URL}/webhook"
echo ""
echo "後續步驟："
echo "  1. 前往 LINE Developers Console"
echo "     → Messaging API → Webhook URL"
echo "     → 貼上：${BOT_URL}/webhook"
echo "     → 開啟「Use webhook」"
echo ""
echo "  2. 測試 Bot 健康狀態："
echo "     curl ${BOT_URL}/health"
echo ""
echo "  3. 手動觸發爬蟲（驗證）："
echo "     gcloud run jobs execute distiller-scraper \\"
echo "       --region $REGION --project $PROJECT_ID"
echo ""
echo "  4. 設定 GitHub Actions Secrets（CI/CD 用）："
echo "     GCP_PROJECT_ID    = $PROJECT_ID"
echo "     WIF_PROVIDER      = projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/..."
echo "     WIF_SERVICE_ACCOUNT = ...@...iam.gserviceaccount.com"
echo "════════════════════════════════════════"
