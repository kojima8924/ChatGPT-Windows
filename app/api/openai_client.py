"""
OpenAI API クライアントモジュール

OpenAI Responses APIを使用してテキスト生成を行う。
ストリーミングレスポンスに対応し、UIをブロックしないようにする。
"""

from openai import OpenAI
from typing import Optional, Callable, List, Any
from dataclasses import dataclass
import threading


@dataclass
class ChatResponse:
    """
    APIレスポンスを保持するデータクラス

    Attributes:
        success: リクエストが成功したか
        content: レスポンスの本文（成功時）
        error: エラーメッセージ（失敗時）
        cancelled: ユーザーによってキャンセルされたか
    """
    success: bool
    content: str = ""
    error: str = ""
    cancelled: bool = False


class ChatGPTClient:
    """
    OpenAI APIクライアント

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

    def _localize_error(self, error_message: str) -> str:
        """
        エラーメッセージを日本語化

        Args:
            error_message: 元のエラーメッセージ

        Returns:
            str: 日本語化されたエラーメッセージ
        """
        error_lower = error_message.lower()

        if "invalid_api_key" in error_lower or "invalid api key" in error_lower:
            return "APIキーが無効です"
        elif "rate_limit" in error_lower or "rate limit" in error_lower:
            return "レート制限に達しました。しばらく待ってから再試行してください"
        elif "insufficient_quota" in error_lower or "insufficient quota" in error_lower:
            return "API利用枠が不足しています"
        elif "connection" in error_lower:
            return "接続エラー: インターネット接続を確認してください"
        elif "model_not_found" in error_lower or "model not found" in error_lower:
            return "指定されたモデルが見つかりません"
        elif "context_length" in error_lower or "maximum context" in error_lower:
            return "入力が長すぎます。テキストを短くするか、最大トークン数を下げてください"
        elif "max_tokens" in error_lower or "max_output_tokens" in error_lower:
            return "出力トークン数の設定を確認してください"

        return error_message

    def _is_temperature_error(self, error_message: str) -> bool:
        """
        エラーがtemperature非対応によるものか判定

        Args:
            error_message: エラーメッセージ

        Returns:
            bool: temperature非対応エラーの場合True
        """
        error_lower = error_message.lower()
        if "temperature" not in error_lower:
            return False
        # エラーメッセージ文言の揺れに対応
        error_keywords = ["unsupported", "not supported", "unknown", "invalid", "unrecognized"]
        return any(kw in error_lower for kw in error_keywords)

    def _extract_delta_text(self, event: Any) -> str:
        """
        ストリーミングイベントからdelta文字列を安全に抽出

        Args:
            event: ストリーミングイベント

        Returns:
            str: 抽出されたテキスト（抽出できない場合は空文字列）
        """
        delta = getattr(event, 'delta', None)

        if delta is None:
            return ""

        # delta が文字列の場合はそのまま返す
        if isinstance(delta, str):
            return delta

        # delta が dict の場合は代表キーを探す
        if isinstance(delta, dict):
            # "text" キーを優先
            if 'text' in delta:
                text = delta['text']
                return text if isinstance(text, str) else ""
            # "content" キーを試す
            if 'content' in delta:
                content = delta['content']
                return content if isinstance(content, str) else ""
            return ""

        # その他の型は空文字列
        return ""

    def _extract_output_text(self, response: Any) -> str:
        """
        Responses APIレスポンスからテキストを安全に抽出

        Args:
            response: APIレスポンス

        Returns:
            str: 抽出されたテキスト
        """
        # output_text を最優先で取得
        output_text = getattr(response, 'output_text', None)
        if output_text and isinstance(output_text, str):
            return output_text

        # fallback: output 配列から取得を試みる
        output = getattr(response, 'output', None)
        if not output or not isinstance(output, list):
            return ""

        # output の各要素を走査
        for item in output:
            # 直接 text を試す
            text = getattr(item, 'text', None)
            if text and isinstance(text, str):
                return text

            # content を試す（content が list の可能性がある）
            content = getattr(item, 'content', None)
            if content:
                # content が文字列の場合
                if isinstance(content, str):
                    return content
                # content が list の場合
                if isinstance(content, list):
                    for content_item in content:
                        # 各要素の text を試す
                        item_text = getattr(content_item, 'text', None)
                        if item_text and isinstance(item_text, str):
                            return item_text
                        # dict の場合
                        if isinstance(content_item, dict) and 'text' in content_item:
                            t = content_item['text']
                            if isinstance(t, str):
                                return t

        return ""

    def send_message(
        self,
        user_message: str,
        system_prompt: str = "",
        model: str = "gpt-5",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = True,
        on_chunk: Optional[Callable[[str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> ChatResponse:
        """
        メッセージを送信してレスポンスを取得（Responses API使用）

        Args:
            user_message: ユーザーからのメッセージ
            system_prompt: システムプロンプト（AIへの指示）→ instructions へ
            model: 使用するモデル名
            temperature: 創造性パラメータ
            max_tokens: 最大出力トークン数 → max_output_tokens へ
            stream: ストリーミングレスポンスを使用するか
            on_chunk: ストリーミング時のチャンクコールバック
            cancel_event: キャンセル用のイベント

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
            if stream:
                return self._stream_response(
                    model=model,
                    user_message=user_message,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    on_chunk=on_chunk,
                    cancel_event=cancel_event
                )
            else:
                return self._non_stream_response(
                    model=model,
                    user_message=user_message,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

        except Exception as e:
            error_message = self._localize_error(str(e))
            return ChatResponse(
                success=False,
                error=error_message
            )

    def _build_api_params(
        self,
        model: str,
        user_message: str,
        system_prompt: str,
        max_tokens: int,
        temperature: Optional[float] = None,
        stream: bool = False,
    ) -> dict:
        """
        APIパラメータを構築

        Args:
            model: モデル名
            user_message: ユーザーメッセージ
            system_prompt: システムプロンプト
            max_tokens: 最大出力トークン数
            temperature: 温度パラメータ（Noneなら含めない）
            stream: ストリーミングモード

        Returns:
            dict: APIパラメータ
        """
        api_params = {
            'model': model,
            'input': [{"role": "user", "content": user_message}],
            'max_output_tokens': max_tokens,
            'store': False,
        }

        if stream:
            api_params['stream'] = True

        if temperature is not None:
            api_params['temperature'] = temperature

        if system_prompt and system_prompt.strip():
            api_params['instructions'] = system_prompt

        return api_params

    def _non_stream_response(
        self,
        model: str,
        user_message: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> ChatResponse:
        """
        非ストリーミングでResponses APIを呼び出す

        Args:
            model: モデル名
            user_message: ユーザーメッセージ
            system_prompt: システムプロンプト（instructions）
            temperature: 温度パラメータ
            max_tokens: 最大出力トークン数

        Returns:
            ChatResponse: 完全なレスポンス
        """
        try:
            # まずtemperature付きで試行
            api_params = self._build_api_params(
                model=model,
                user_message=user_message,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False
            )

            try:
                response = self.client.responses.create(**api_params)
            except Exception as e:
                # temperature非対応エラーなら再試行
                if self._is_temperature_error(str(e)):
                    api_params_no_temp = self._build_api_params(
                        model=model,
                        user_message=user_message,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens,
                        temperature=None,
                        stream=False
                    )
                    response = self.client.responses.create(**api_params_no_temp)
                else:
                    raise

            # 堅牢なテキスト抽出
            content = self._extract_output_text(response)

            return ChatResponse(
                success=True,
                content=content
            )

        except Exception as e:
            error_message = self._localize_error(str(e))
            return ChatResponse(
                success=False,
                error=error_message
            )

    def _stream_response(
        self,
        model: str,
        user_message: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        on_chunk: Optional[Callable[[str], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> ChatResponse:
        """
        ストリーミングでResponses APIを呼び出す

        Args:
            model: モデル名
            user_message: ユーザーメッセージ
            system_prompt: システムプロンプト（instructions）
            temperature: 温度パラメータ
            max_tokens: 最大出力トークン数
            on_chunk: チャンク受信時のコールバック
            cancel_event: キャンセル用のイベント

        Returns:
            ChatResponse: 完全なレスポンス
        """
        try:
            # まずtemperature付きで試行
            api_params = self._build_api_params(
                model=model,
                user_message=user_message,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )

            try:
                stream = self.client.responses.create(**api_params)
            except Exception as e:
                # temperature非対応エラーなら再試行
                if self._is_temperature_error(str(e)):
                    api_params_no_temp = self._build_api_params(
                        model=model,
                        user_message=user_message,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens,
                        temperature=None,
                        stream=True
                    )
                    stream = self.client.responses.create(**api_params_no_temp)
                else:
                    raise

            full_content = ""

            for event in stream:
                # キャンセルチェック
                if cancel_event and cancel_event.is_set():
                    # ストリームを明示的にクローズ
                    try:
                        close_fn = getattr(stream, "close", None)
                        if callable(close_fn):
                            close_fn()
                    except Exception:
                        pass
                    return ChatResponse(
                        success=True,
                        content=full_content,
                        cancelled=True
                    )

                # イベントタイプを安全に取得
                event_type = getattr(event, 'type', None)

                if event_type == "response.output_text.delta":
                    # 堅牢なdelta抽出
                    delta = self._extract_delta_text(event)
                    if delta:
                        full_content += delta

                        # コールバックがあれば呼び出す
                        if on_chunk:
                            try:
                                on_chunk(delta)
                            except Exception:
                                # コールバックのエラーはストリーミングを中断しない
                                pass

                elif event_type == "error":
                    # エラーイベントを処理
                    error_msg = getattr(event, 'message', None)
                    error_code = getattr(event, 'code', None)
                    if error_msg:
                        raise RuntimeError(f"{error_code}: {error_msg}" if error_code else error_msg)
                    else:
                        raise RuntimeError(str(event))

            return ChatResponse(
                success=True,
                content=full_content
            )

        except Exception as e:
            error_message = self._localize_error(str(e))
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

        # gpt-* および o1-*, o3-* モデルを抽出
        models = []
        for model in models_response.data:
            model_id = getattr(model, 'id', None)
            if model_id:
                # gpt-*, o1-*, o3-* モデルを含める
                if (model_id.startswith('gpt-') or
                    model_id.startswith('o1-') or
                    model_id.startswith('o3-')):
                    models.append(model_id)

        # モデルを優先度順にソート（新しいモデルを優先）
        priority_order = ['gpt-5', 'gpt-4o', 'gpt-4', 'o1-', 'o3-', 'gpt-3.5']

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
