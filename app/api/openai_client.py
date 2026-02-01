"""
OpenAI API クライアントモジュール

ChatGPT APIとの通信を担当する。
非同期処理でUIをブロックしないようにする。
"""

from openai import OpenAI
from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class ChatResponse:
    """
    APIレスポンスを保持するデータクラス

    Attributes:
        success: リクエストが成功したか
        content: レスポンスの本文（成功時）
        error: エラーメッセージ（失敗時）
    """
    success: bool
    content: str = ""
    error: str = ""


class ChatGPTClient:
    """
    ChatGPT APIクライアント

    OpenAI APIを使用してテキスト生成を行う。
    """

    def __init__(self, api_key: str):
        """
        クライアントを初期化

        Args:
            api_key: OpenAI APIキー
        """
        self.client = OpenAI(api_key=api_key)
        self.api_key = api_key

    def send_message(
        self,
        user_message: str,
        system_prompt: str = "",
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ChatResponse:
        """
        メッセージを送信してレスポンスを取得

        Args:
            user_message: ユーザーからのメッセージ
            system_prompt: システムプロンプト（AIへの指示）
            model: 使用するモデル名
            temperature: 創造性パラメータ
            max_tokens: 最大出力トークン数

        Returns:
            ChatResponse: APIからのレスポンス
        """
        # 入力チェック
        if not user_message.strip():
            return ChatResponse(
                success=False,
                error="入力テキストが空です"
            )

        if not self.api_key:
            return ChatResponse(
                success=False,
                error="APIキーが設定されていません"
            )

        try:
            # メッセージリストを構築
            messages = []

            # システムプロンプトがある場合は追加
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })

            # ユーザーメッセージを追加
            messages.append({
                "role": "user",
                "content": user_message
            })

            # API呼び出し
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # レスポンスからテキストを抽出
            content = response.choices[0].message.content

            return ChatResponse(
                success=True,
                content=content or ""
            )

        except Exception as e:
            # エラーハンドリング
            error_message = str(e)

            # よくあるエラーを日本語化
            if "invalid_api_key" in error_message.lower():
                error_message = "APIキーが無効です"
            elif "rate_limit" in error_message.lower():
                error_message = "レート制限に達しました。しばらく待ってから再試行してください"
            elif "insufficient_quota" in error_message.lower():
                error_message = "API利用枠が不足しています"
            elif "connection" in error_message.lower():
                error_message = "接続エラー: インターネット接続を確認してください"

            return ChatResponse(
                success=False,
                error=error_message
            )


def create_client(api_key: str) -> Optional[ChatGPTClient]:
    """
    ChatGPTクライアントを作成

    Args:
        api_key: OpenAI APIキー

    Returns:
        Optional[ChatGPTClient]: クライアント（APIキーが空の場合はNone）
    """
    if not api_key:
        return None
    return ChatGPTClient(api_key)
