# Google Cloud Functions 部署指南

## 部署準備

### 1. 安裝 Google Cloud SDK
```bash
# macOS
brew install google-cloud-sdk

# 或下載安裝包
curl https://sdk.cloud.google.com | bash
```

### 2. 設定 Google Cloud 專案
```bash
# 登入 Google Cloud
gcloud auth login

# 設定專案 ID (替換為您的專案 ID)
gcloud config set project YOUR_PROJECT_ID

# 啟用 Cloud Functions API
gcloud services enable cloudfunctions.googleapis.com
```

## 部署 Cloud Function

### 1. 部署指令
```bash
gcloud functions deploy ptt-webhook \
  --runtime python311 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point webhook \
  --set-env-vars LINE_CHANNEL_ACCESS_TOKEN=你的_Channel_Access_Token,LINE_CHANNEL_SECRET=你的_Channel_Secret \
  --memory 512MB \
  --timeout 540s \
  --project=YOUR_PROJECT_ID \
  --region=us-central1 \
  --gen2
```

### 2. 使用環境變數檔案部署
創建 `.env.yaml` 檔案：
```yaml
LINE_CHANNEL_ACCESS_TOKEN: 你的_Channel_Access_Token
LINE_CHANNEL_SECRET: 你的_Channel_Secret
```

然後部署：
```bash
gcloud functions deploy ptt-webhook \
  --runtime python311 \
  --trigger-http \
  --allow-unauthenticated \
  --entry-point webhook \
  --env-vars-file .env.yaml \
  --memory 512MB \
  --timeout 540s \
  --project=YOUR_PROJECT_ID \
  --region=us-central1 \
  --gen2
```

### 3. 取得 Function URL
部署完成後，會顯示 Function 的觸發 URL，例如：
```
https://REGION-PROJECT_ID.cloudfunctions.net/ptt-webhook
```

## LINE Bot 設定

1. 登入 [LINE Developers Console](https://developers.line.biz)
2. 選擇您的 Bot
3. 在 Messaging API 設定中：
   - 設定 Webhook URL 為上方取得的 Function URL
   - 啟用 "Use webhook"
   - 停用 "Auto-reply messages" 和 "Greeting messages"（可選）

## 監控和除錯

### 查看日誌
```bash
gcloud functions logs read ptt-webhook --limit 50
```

### 測試 Function
```bash
curl -X POST https://REGION-PROJECT_ID.cloudfunctions.net/ptt-webhook \
  -H "Content-Type: application/json" \
  -d '{"test": "message"}'
```

## 成本優化

- **記憶體**：512MB 適合大部分使用情況
- **逾時**：540s 是最大值，足夠處理 PTT 爬蟲請求
- **並行數**：預設即可，按需自動調整

## 優勢對比

| 項目 | Cloud Functions | Railway/Render |
|------|----------------|----------------|
| 成本 | 按需付費，閒置免費 | 月費制 |
| 冷啟動 | ~1-3秒 | 無 |
| 維護 | 無需維護 | 需監控 |
| 擴展 | 自動 | 手動 |
| 設定複雜度 | 中等 | 簡單 |

## 故障排除

### 常見問題

1. **部署失敗 - 403 錯誤**：
   ```
   ResponseError: status=[403], code=[Ok], message=[Location REGION is not found or access is unauthorized.]
   ```
   - **原因**：使用了 `REGION` 占位符而非實際區域名稱
   - **解決**：使用具體區域如 `--region=us-central1`

2. **Cloud Run 服務未找到**：
   ```
   Cloud Run service for the function was not found
   ```
   - **原因**：初始部署不完整，缺少必要參數
   - **解決**：使用完整參數重新部署，包含 `--project`, `--region`, `--gen2`

3. **Function 狀態 FAILED**：
   - **檢查狀態**：`gcloud functions describe ptt-webhook --project=YOUR_PROJECT_ID --region=us-central1`
   - **解決**：重新部署並確保所有參數正確

### 必要參數說明

- `--project=YOUR_PROJECT_ID`：明確指定 GCP 專案 ID
- `--region=us-central1`：指定部署區域（推薦使用 us-central1）
- `--gen2`：使用 Gen 2 Cloud Functions（更穩定，功能更完整）

1. **部署失敗**：檢查專案權限和 API 啟用狀態
2. **Function 逾時**：增加 timeout 或優化程式碼
3. **記憶體不足**：增加 memory 設定
4. **LINE Bot 無回應**：檢查環境變數和 Webhook URL