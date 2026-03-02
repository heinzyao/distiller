"""
LINE Messaging API 通知模組

使用 LINE Messaging API 的 Push Message 端點發送通知。
透過 Channel ID + Secret 動態取得短期 Access Token（與 music-collector 共用相同憑證）。

需要設定環境變數：
  - LINE_CHANNEL_ID: LINE Channel ID
  - LINE_CHANNEL_SECRET: LINE Channel Secret
  - LINE_USER_ID: 接收通知的使用者 ID
"""

import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

LINE_TOKEN_URL = "https://api.line.me/v2/oauth/accessToken"
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


class LineNotifier:
    """透過 LINE Messaging API 發送推播通知。"""

    def __init__(
        self,
        channel_id: str | None = None,
        channel_secret: str | None = None,
        user_id: str | None = None,
    ):
        self.channel_id = channel_id if channel_id is not None else os.getenv("LINE_CHANNEL_ID", "")
        self.channel_secret = channel_secret if channel_secret is not None else os.getenv("LINE_CHANNEL_SECRET", "")
        self.user_id = user_id if user_id is not None else os.getenv("LINE_USER_ID", "")

    def is_configured(self) -> bool:
        """當 channel_id、channel_secret、user_id 皆已設定時回傳 True。"""
        return bool(self.channel_id and self.channel_secret and self.user_id)

    def _get_access_token(self) -> str | None:
        """用 Channel ID + Secret 產生短期 Access Token。"""
        try:
            resp = requests.post(
                LINE_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.channel_id,
                    "client_secret": self.channel_secret,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning("LINE Token 取得失敗：%s %s", resp.status_code, resp.text)
                return None
            return resp.json()["access_token"]
        except requests.RequestException as exc:
            logger.error("LINE Token 請求失敗：%s", exc)
            return None

    def send(self, text: str) -> bool:
        """發送文字推播訊息，成功回傳 True。"""
        if not self.is_configured():
            logger.warning("LINE 憑證未設定，跳過通知。")
            return False

        token = self._get_access_token()
        if not token:
            return False

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        body = {
            "to": self.user_id,
            "messages": [{"type": "text", "text": text}],
        }
        try:
            resp = requests.post(LINE_PUSH_URL, headers=headers, json=body, timeout=10)
            if resp.status_code == 200:
                logger.info("LINE 通知發送成功。")
                return True
            else:
                logger.warning("LINE 通知發送失敗：%s %s", resp.status_code, resp.text)
                return False
        except requests.RequestException as exc:
            logger.error("LINE 通知發送失敗：%s", exc)
            return False

    def notify_success(self, mode: str, stats: dict) -> bool:
        """格式化並發送爬取成功通知。"""
        total = stats.get("總記錄數", stats.get("total_records", "?"))
        failed = stats.get("失敗 URL 數", stats.get("failed_urls", "?"))
        categories = stats.get("類別分布", stats.get("category_distribution", {}))
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = [
            "✅ Distiller 爬蟲執行完成",
            "━" * 20,
            f"⏰ {now}",
            "",
            f"  模式　　{mode}",
            f"  總筆數　{total}",
            f"  失敗數　{failed}",
        ]
        if categories:
            cat_total = sum(categories.values()) if all(isinstance(v, (int, float)) for v in categories.values()) else 0
            lines.append("")
            lines.append("📋 類別分布")
            lines.append("─" * 20)
            for k, v in categories.items():
                if cat_total > 0 and isinstance(v, (int, float)):
                    bar_len = round(v / cat_total * 10)
                    bar = "█" * bar_len + "░" * (10 - bar_len)
                    lines.append(f"  {k}　{bar} {v}")
                else:
                    lines.append(f"  {k}　{v}")
        else:
            lines.append(f"  類別　　無")

        text = "\n".join(lines)
        return self.send(text)

    def notify_failure(self, mode: str, error: str = "") -> bool:
        """格式化並發送爬取失敗通知。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            "❌ Distiller 爬蟲執行失敗",
            "━" * 20,
            f"⏰ {now}",
            "",
            f"  模式　{mode}",
            f"  錯誤　{error or '未知錯誤，請查看日誌。'}",
        ]
        return self.send("\n".join(lines))
