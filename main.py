from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.messaging.models import (
    ReplyMessageRequest, TextMessage, FlexMessage, FlexContainer
)
from linebot.v3.webhooks.models import MessageEvent, TextMessageContent
import cloudscraper
import requests
from bs4 import BeautifulSoup
import time
import logging
import os

# 設置日誌記錄
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 用於追蹤已處理的訊息ID，避免重複處理
processed_messages = set()

app = Flask(__name__)

class PTTQueryBot:
    def __init__(self, channel_access_token, channel_secret):
        configuration = Configuration(access_token=channel_access_token)
        self.api_client = ApiClient(configuration)
        self.line_bot_api = MessagingApi(self.api_client)
        self.handler = WebhookHandler(channel_secret)
        self.setup_handlers()
    
    def setup_handlers(self):
        @self.handler.add(MessageEvent, message=TextMessageContent)
        def handle_message(event):
            user_id = event.source.user_id if hasattr(event.source, 'user_id') else 'unknown'
            message_id = event.message.id if hasattr(event.message, 'id') else 'unknown'
            user_message = event.message.text.strip()
            
            logger.info(f"收到用戶 {user_id} 的訊息 (ID: {message_id}): '{user_message}'")
            logger.info(f"事件時間戳: {event.timestamp}")
            logger.info(f"Webhook事件ID: {event.webhook_event_id}")
            
            # 檢查是否已經處理過這個訊息
            if message_id in processed_messages:
                logger.warning(f"⚠️ 訊息 {message_id} 已經處理過，跳過")
                return
            
            # 標記為已處理
            processed_messages.add(message_id)
            
            # 清理舊的訊息ID（保留最近100個）
            if len(processed_messages) > 100:
                processed_messages.clear()
                processed_messages.add(message_id)
                logger.info("清理舊的訊息ID記錄")
            
            # 檢查是否為查詢指令格式：看板 關鍵字  
            if ' ' in user_message and len(user_message.split(' ', 1)) == 2:
                logger.info(f"識別為PTT查詢指令: {user_message}")
                self.handle_ptt_query(event, user_message)
            else:
                # 幫助訊息
                help_message = """
🔍 PTT查詢機器人使用說明：

📝 指令格式：看板名稱 關鍵字

💡 範例：
• Soft_Job python
• Tech_Job 後端工程師
• Stock 台積電
• CPBL_ticket 7/30

⚡ 我會立即為您搜尋該版面最新20篇文章中包含關鍵字的貼文！
                """
                self.line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=help_message)]
                    )
                )
    
    def handle_ptt_query(self, event, query):
        """處理PTT查詢"""
        user_id = event.source.user_id if hasattr(event.source, 'user_id') else 'unknown'
        logger.info(f"開始處理用戶 {user_id} 的PTT查詢: {query}")
        
        try:
            # 解析指令 - 改用空格分隔看板和關鍵字
            parts = query.split(' ', 1)
            if len(parts) != 2:
                self.line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ 格式錯誤！請使用：看板名稱 關鍵字")]
                    )
                )
                return
            
            board_name, keyword = parts
            board_name = board_name.strip()
            keyword = keyword.strip()
            
            if not board_name or not keyword:
                self.line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ 看板名稱和關鍵字都不能為空！")]
                    )
                )
                return
            
            # 執行搜尋
            logger.info(f"開始搜尋看板 {board_name}，關鍵字: {keyword}")
            results = self.search_ptt_posts(board_name, keyword)
            logger.info(f"搜尋完成，找到 {len(results)} 篇文章")
            
            # 發送結果
            if results:
                # 建立一個 Flex Message 泡泡列表
                bubbles = [self.create_result_bubble(result, board_name, keyword) for result in results[:5]]
                
                carousel_container = FlexContainer.from_dict({
                    "type": "carousel",
                    "contents": bubbles
                })
                
                flex_message = FlexMessage(
                    alt_text=f"✅ 在 {board_name} 版找到關於「{keyword}」的文章",
                    contents=carousel_container
                )
                
                self.line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[flex_message]
                    )
                )
            else:
                no_result_msg = f"😅 在 {board_name} 版沒有找到包含「{keyword}」的文章"
                self.line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=no_result_msg)]
                    )
                )
                
        except Exception as e:
            error_msg = f"❌ 搜尋過程發生錯誤：{str(e)}"
            logger.error(f"處理查詢時發生錯誤: {e}")
            try:
                self.line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=error_msg)]
                    )
                )
            except: 
                pass
    
    def search_ptt_posts(self, board_name, keyword):
        """搜尋PTT文章 (使用 cloudscraper 繞過反爬蟲)"""
        # 使用 cloudscraper 取代 requests.Session()
        session = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        
        # 設定額外的 headers (移除Accept-Encoding讓cloudscraper自動處理壓縮)
        session.headers.update({
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
        url = f"https://www.ptt.cc/bbs/{board_name}/index.html"
    
        try:
            # 4. 在請求前加入延遲，成為有禮貌的爬蟲
            time.sleep(1)
            # 第一步：先 get 一次頁面
            logging.info(f"正在嘗試存取看板: {board_name}")
            # 第一次請求，用來獲取頁面內容或18歲確認頁
            response = session.get(url, timeout=10)
            
            # 檢查回應狀態
            if response.status_code != 200:
                raise requests.exceptions.HTTPError(f"HTTP {response.status_code}", response=response)

            # 檢查是否需要進行18歲確認
            if "我是否已年滿十八歲" in response.text:
                logger.info(f"觸發 PTT 18歲確認，為看板 {board_name} 進行模擬點擊...")
                
                # 從確認頁面中解析出POST請求需要的資料
                soup = BeautifulSoup(response.text, 'html.parser')
                form = soup.find('form', action='/ask/over18')
                if not form:
                    logger.error("在18歲確認頁上找不到POST表單")
                    return []

                # 準備POST的資料
                payload = {
                    'from': form.find('input', {'name': 'from'})['value'],
                    'yes': 'yes'
                }
            
                # 發送POST請求來模擬點擊「是」
                post_url = "https://www.ptt.cc/ask/over18"
                session.post(post_url, data=payload, headers={'Referer': url})
            
                # 再次請求原始的看板頁面，此時 session 中應該已經有有效的 cookie
                logger.info("完成18歲確認，重新載入看板頁面...")
                time.sleep(1) # 同意後再等一下
                response = session.get(url, timeout=10)
        
            # 確認最終請求是否成功
            if response.status_code != 200:
                raise requests.exceptions.HTTPError(f"HTTP {response.status_code}", response=response)
        
            # --- 後續的頁面解析程式碼保持不變 ---
            # 確保正確的編碼
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            logging.info(f"成功解析看板: {board_name}")
            results = []
        
            # 取得最新一頁的文章
            for post_div in soup.find_all('div', class_='r-ent'):
                title_tag = post_div.find('div', class_='title')
                # 排除已被刪除的文章 (標題為空) 或置底公告
                if title_tag and title_tag.find('a'):
                    link_tag = title_tag.find('a')
                    title = link_tag.text.strip()
                    
                    # 檢查標題是否包含關鍵字
                    if keyword.lower() in title.lower():
                        link = f"https://www.ptt.cc{link_tag['href']}"
                        author_tag = post_div.find('div', class_='author')
                        date_tag = post_div.find('div', class_='date')
                        
                        author = author_tag.text.strip() if author_tag else "N/A"
                        date = date_tag.text.strip() if date_tag else "N/A"
                        
                        results.append({
                            'title': title,
                            'author': author,
                            'date': date,
                            'link': link
                        })
        
            # 反轉結果，讓最新的文章排在後面 (PTT首頁文章是新的在上面)
            return results[::-1] # 反轉列表
            
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP 錯誤，無法存取看板 {board_name}。狀態碼: {http_err.response.status_code}")
            # 將 PTT 的錯誤訊息回傳給使用者，讓他們知道問題所在
            raise Exception(f"PTT伺服器錯誤 (狀態碼: {http_err.response.status_code})，可能看板不存在或暫時關閉。")
        except Exception as e:
            logger.error(f"搜尋PTT文章時發生未知錯誤: {e}")
            raise e
    
    def create_result_bubble(self, post, board_name, keyword):
        """建立搜尋結果的 Flex Message"""
        # 高亮關鍵字
        highlighted_title = post['title'].replace(
            keyword, f"🔥{keyword}🔥"
        )
        
        flex_content = {
            "type": "bubble",
            "hero": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"🎯 {board_name} 搜尋結果",
                        "weight": "bold",
                        "color": "#1DB446",
                        "size": "sm"
                    }
                ],
                "backgroundColor": "#F0F0F0",
                "paddingAll": "10px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": highlighted_title,
                        "weight": "bold",
                        "size": "md",
                        "wrap": True,
                        "color": "#333333"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "baseline",
                                "spacing": "sm",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "👤 作者",
                                        "color": "#aaaaaa",
                                        "size": "sm",
                                        "flex": 2
                                    },
                                    {
                                        "type": "text",
                                        "text": post['author'],
                                        "wrap": True,
                                        "color": "#666666",
                                        "size": "sm",
                                        "flex": 5
                                    }
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "baseline",
                                "spacing": "sm",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "📅 日期",
                                        "color": "#aaaaaa",
                                        "size": "sm",
                                        "flex": 2
                                    },
                                    {
                                        "type": "text",
                                        "text": post['date'],
                                        "wrap": True,
                                        "color": "#666666",
                                        "size": "sm",
                                        "flex": 5
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        "action": {
                            "type": "uri",
                            "uri": post['link'],
                            "label": "查看完整文章"
                        },
                        "text": "📖 查看完整文章",
                        "color": "#1DB446"
                    }
                ]
            }
        }
        
        return flex_content

# 添加根路由用於測試
@app.route("/")
def home():
    return "PTT Query Bot is running!"

# Flask Webhook 端點
@app.route("/webhook", methods=['POST'])
def webhook():
    # 記錄收到的請求
    logger.info(f"收到 webhook 請求，方法: {request.method}")
    logger.info(f"請求標頭: {dict(request.headers)}")
    logger.info(f"請求來源IP: {request.remote_addr}")

    # 檢查必要的標頭
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        logger.error("缺少 X-Line-Signature 標頭")
        abort(400)

    body = request.get_data(as_text=True)
    logger.info(f"請求內容長度: {len(body)}")
    logger.info(f"請求內容: {body}")
    
    # 檢查是否為重複請求
    import json
    try:
        webhook_data = json.loads(body)
        if 'events' in webhook_data:
            for event in webhook_data['events']:
                if 'webhookEventId' in event:
                    logger.info(f"Webhook事件ID: {event['webhookEventId']}")
                if 'deliveryContext' in event:
                    is_redelivery = event['deliveryContext'].get('isRedelivery', False)
                    logger.info(f"是否為重新發送: {is_redelivery}")
                    if is_redelivery:
                        logger.warning("⚠️ 這是一個重新發送的請求")
    except json.JSONDecodeError:
        logger.error("無法解析webhook內容為JSON")

    try:
        bot.handler.handle(body, signature)
        logger.info("成功處理 webhook 請求")
    except InvalidSignatureError:
        logger.error("無效的簽名")
        abort(400)
    except Exception as e:
        logger.error(f"處理 webhook 時發生錯誤: {e}")
        import traceback
        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        abort(500)
    
    return 'OK'

# 添加錯誤處理路由
@app.errorhandler(403)
def forbidden(error):
    logger.error(f"403 Forbidden: {error}")
    return "Forbidden", 403

@app.errorhandler(404)
def not_found(error):
    logger.error(f"404 Not Found: {error}")
    return "Not Found", 404

# 初始化Bot - 從環境變數讀取憑證
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("請務必設定 LINE_CHANNEL_ACCESS_TOKEN 和 LINE_CHANNEL_SECRET 環境變數")

bot = PTTQueryBot(
    channel_access_token=LINE_CHANNEL_ACCESS_TOKEN,
    channel_secret=LINE_CHANNEL_SECRET
)

if __name__ == "__main__":
    logger.info("啟動 PTT Query Bot...")
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)