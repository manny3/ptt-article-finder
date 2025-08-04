# PTT Article Finder Bot 部署指南

## 推荐部署平台

### 1. Railway (最推荐) ⭐⭐⭐⭐⭐

**优点：**
- 每月 $5 免费额度（约500小时运行时间）
- 部署简单，GitHub 自动部署
- 不会休眠，响应速度快
- 支持环境变量管理

**部署步骤：**

1. **准备 GitHub 仓库**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/你的用户名/ptt-article-finder.git
   git push -u origin main
   ```

2. **在 Railway 部署**
   - 访问 [railway.app](https://railway.app)
   - 使用 GitHub 账号登录
   - 点击 "New Project" → "Deploy from GitHub repo"
   - 选择你的仓库
   - Railway 会自动检测 Python 项目并部署

3. **设置环境变量**
   在 Railway 项目设置中添加：
   ```
   LINE_CHANNEL_ACCESS_TOKEN=你的_LINE_Channel_Access_Token
   LINE_CHANNEL_SECRET=你的_LINE_Channel_Secret
   ```

4. **获取部署 URL**
   - 部署完成后，Railway 会提供一个 URL，如：`https://your-app-name.railway.app`
   - 将这个 URL 加上 `/webhook` 设置到 LINE Bot 的 Webhook URL

### 2. Render (备选方案) ⭐⭐⭐⭐

**优点：**
- 免费 750 小时/月
- 简单易用

**缺点：**
- 15分钟无活动后会休眠，首次响应较慢

**部署步骤：**
1. 访问 [render.com](https://render.com)
2. 连接 GitHub 仓库
3. 选择 "Web Service"
4. 设置构建命令：`pip install -r requirements.txt`
5. 设置启动命令：`gunicorn main:app`
6. 添加环境变量

### 3. Fly.io (进阶用户) ⭐⭐⭐⭐

**优点：**
- 性能好，不休眠
- 每月 160 小时免费

**缺点：**
- 需要使用命令行工具部署

## 环境变量设置

无论使用哪个平台，都需要设置以下环境变量：

```
LINE_CHANNEL_ACCESS_TOKEN=你的Channel Access Token
LINE_CHANNEL_SECRET=你的Channel Secret
```

## LINE Bot 设置

1. **登录 LINE Developers Console**
   - 访问 [developers.line.biz](https://developers.line.biz)

2. **设置 Webhook URL**
   - 在你的 LINE Bot 设置中
   - 将 Webhook URL 设置为：`https://你的域名.railway.app/webhook`
   - 启用 "Use webhook"

3. **设置权限**
   - 确保已启用 Messaging API
   - 可以关闭 "Auto-reply messages" 和 "Greeting messages"

## 测试部署

部署完成后，可以：
1. 访问 `https://你的域名/` 查看是否正常运行
2. 在 LINE 中添加你的 Bot 好友
3. 发送测试消息，如：`Soft_Job python`

## 故障排除

1. **部署失败**
   - 检查 requirements.txt 是否正确
   - 查看部署日志

2. **Webhook 错误**
   - 确认 URL 设置正确
   - 检查环境变量是否设置

3. **Bot 无响应**
   - 查看服务器日志
   - 确认 Channel Access Token 和 Secret 正确

## 监控和维护

- Railway: 在控制台查看日志和使用量
- 建议定期检查免费额度使用情况
- 可以设置 GitHub Actions 自动部署更新