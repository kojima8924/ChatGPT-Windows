"""
OpenAI API クライアントモジュール

ChatGPT APIとの通信を担当する。
ストリーミングレスポンスに対応し、UIをブロックしないようにする。
"""

from openai import OpenAI
from typing import Optional, Callable, Iterator, List
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

    OpenAI Responses APIを使用してテキスト生成を行う。
    ストリーミングとノンストリーミングの両方に対応。
    """

    def __init__(self, api_key: str):
        """
        クライアントを初期化

        Args:
            api_key: OpenAI APIキー
        """
        self.client = OpenAI(api_key=api_key)
        self.api_key = api_key

    def _get_max_tokens_param(self, model: str) -> str:
        """
        モデルに応じて適切なmax_tokensパラメータ名を返す

        Args:
            model: モデル名

        Returns:
            str: 'max_tokens' または 'max_completion_tokens'
        """
        # 新しいモデル（gpt-4o, gpt-5, o1シリーズなど）はmax_completion_tokensを使用
        new_models = ['gpt-4o', 'gpt-5', 'o1-', 'o3-']
        for prefix in new_models:
            if model.startswith(prefix):
                return 'max_completion_tokens'
        return 'max_tokens'

    def send_message(
        self,
        user_message: str,
        system_prompt: str = "",
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = True,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> ChatResponse:
        """
        メッセージを送信してレスポンスを取得

        Args:
            user_message: ユーザーからのメッセージ
            system_prompt: システムプロンプト（AIへの指示）
            model: 使用するモデル名
            temperature: 創造性パラメータ
            max_tokens: 最大出力トークン数
            stream: ストリーミングレスポンスを使用するか
            on_chunk: ストリーミング時のチャンクコールバック

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

            # モデルに応じて適切なmax_tokensパラメータを使用
            max_tokens_param = self._get_max_tokens_param(model)

            if stream:
                # ストリーミングレスポンス
                return self._stream_response(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    max_tokens_param=max_tokens_param,
                    on_chunk=on_chunk
                )
            else:
                # 通常のレスポンス
                api_params = {
                    'model': model,
                    'messages': messages,
                    'temperature': temperature,
                    max_tokens_param: max_tokens,
                }
                response = self.client.chat.completions.create(**api_params)

                # getattr で安全にレスポンスからテキストを抽出
                choices = getattr(response, 'choices', None)
                if choices and len(choices) > 0:
                    message = getattr(choices[0], 'message', None)
                    content = getattr(message, 'content', None) if message else None
                else:
                    content = None

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

    def _stream_response(
        self,
        model: str,
        messages: list,
        temperature: float,
        max_tokens: int,
        max_tokens_param: str,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> ChatResponse:
        """
        ストリーミングレスポンスを処理

        Args:
            model: モデル名
            messages: メッセージリスト
            temperature: 温度パラメータ
            max_tokens: 最大トークン数
            max_tokens_param: max_tokensパラメータ名（'max_tokens' または 'max_completion_tokens'）
            on_chunk: チャンク受信時のコールバック

        Returns:
            ChatResponse: 完全なレスポンス
        """
        try:
            # モデルに応じたパラメータで API を呼び出す
            api_params = {
                'model': model,
                'messages': messages,
                'temperature': temperature,
                max_tokens_param: max_tokens,
                'stream': True,
            }
            stream = self.client.chat.completions.create(**api_params)

            full_content = ""
            for chunk in stream:
                # getattr で安全にチャンクデータを取得
                choices = getattr(chunk, 'choices', None)
                if not choices or len(choices) == 0:
                    continue

                delta = getattr(choices[0], 'delta', None)
                if not delta:
                    continue

                chunk_text = getattr(delta, 'content', None)
                if chunk_text:
                    full_content += chunk_text

                    # コールバックがあれば呼び出す
                    if on_chunk:
                        try:
                            on_chunk(chunk_text)
                        except Exception:
                            # コールバックのエラーはストリーミングを中断しない
                            pass

            return ChatResponse(
                success=True,
                content=full_content
            )

        except Exception as e:
            error_message = str(e)

            # エラーを日本語化
            if "invalid_api_key" in error_message.lower():
                error_message = "APIキーが無効です"
            elif "rate_limit" in error_message.lower():
                error_message = "レート制限に達しました"
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


def fetch_available_models(api_key: str) -> Optional[List[str]]:
    """
    OpenAI APIから利用可能なモデルのリストを取得

    Args:
        api_key: OpenAI APIキー

    Returns:
        Optional[List[str]]: モデルのリスト（取得失敗時はNone）
    """
    if not api_key:
        return None

    try:
        client = OpenAI(api_key=api_key)
        models_response = client.models.list()

        # gpt-* モデルのみを抽出してソート
        models = []
        for model in models_response.data:
            model_id = getattr(model, 'id', None)
            if model_id and model_id.startswith('gpt-'):
                models.append(model_id)

        # モデルを優先度順にソート（新しいモデルを優先）
        priority_order = ['gpt-4o', 'gpt-4', 'gpt-3.5']

        def sort_key(model_name: str) -> tuple:
            # 優先度を数値化（小さいほど優先）
            for i, prefix in enumerate(priority_order):
                if model_name.startswith(prefix):
                    return (i, model_name)
            return (len(priority_order), model_name)

        models.sort(key=sort_key)
        return models if models else None

    except Exception:
        return None
