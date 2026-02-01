"""
設定管理モジュール

アプリケーションの設定を管理する。
設定はJSONファイルに保存され、起動時に読み込まれる。
APIキーはWindows資格情報マネージャーに安全に保存される。
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
import keyring


# ============================================
# 設定ファイルのパス
# ユーザーのホームディレクトリに保存
# ============================================
CONFIG_DIR = Path.home() / ".chatgpt-windows"
CONFIG_FILE = CONFIG_DIR / "config.json"

# ============================================
# キーリング設定（Windows資格情報マネージャー用）
# ============================================
KEYRING_SERVICE = "ChatGPT-Windows"
KEYRING_USERNAME = "openai_api_key"


@dataclass
class AppConfig:
    """
    アプリケーション設定を保持するデータクラス

    Attributes:
        api_key: OpenAI APIキー（メモリ上のみ、保存時はkeyringを使用）
        model: 使用するモデル名
        system_prompt: システムプロンプト（AIへの指示）
        temperature: 創造性パラメータ (0.0-2.0)
        max_tokens: 最大出力トークン数
        always_on_top: 常に最前面に表示するか
        auto_paste: 起動時に自動でクリップボードを読み込むか
    """
    api_key: str = ""
    model: str = "gpt-4o-mini"
    system_prompt: str = "ユーザーの入力に対して、英日あるいは日英の翻訳をしてください。"
    temperature: float = 0.7
    max_tokens: int = 1024
    always_on_top: bool = True
    auto_paste: bool = True


def load_api_key_secure() -> str:
    """
    Windows資格情報マネージャーからAPIキーを安全に読み込む

    Returns:
        str: APIキー（保存されていない場合は空文字列）
    """
    try:
        key = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        return key if key else ""
    except Exception:
        return ""


def save_api_key_secure(api_key: str) -> bool:
    """
    Windows資格情報マネージャーにAPIキーを安全に保存する

    Args:
        api_key: 保存するAPIキー

    Returns:
        bool: 保存に成功した場合True
    """
    try:
        if api_key:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)
        else:
            # 空の場合は削除を試みる
            try:
                keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
            except keyring.errors.PasswordDeleteError:
                pass
        return True
    except Exception:
        return False


def is_api_key_pattern(text: str) -> bool:
    """
    テキストがOpenAI APIキーのパターンかどうかを判定する

    Args:
        text: 判定するテキスト

    Returns:
        bool: APIキーのパターンに一致する場合True
    """
    if not text:
        return False
    text = text.strip()
    # OpenAI APIキーは "sk-" で始まり、一定の長さがある
    # 新形式: sk-proj-... や sk-... など
    return text.startswith("sk-") and len(text) >= 20


def load_config() -> AppConfig:
    """
    設定ファイルから設定を読み込む

    ファイルが存在しない場合はデフォルト設定を返す。
    パースエラーの場合もデフォルト設定を返す。
    APIキーはWindows資格情報マネージャーから読み込む。

    Returns:
        AppConfig: 読み込んだ設定（またはデフォルト設定）
    """
    config = AppConfig()

    # JSONファイルから設定を読み込む
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # api_keyはJSONには保存しないので除外
                data.pop("api_key", None)
                config = AppConfig(**data)
        except (json.JSONDecodeError, TypeError, KeyError):
            # パースエラーや不正なキーの場合はデフォルト値を使用
            pass

    # APIキーは資格情報マネージャーから読み込む
    config.api_key = load_api_key_secure()

    return config


def save_config(config: AppConfig) -> bool:
    """
    設定をファイルに保存する

    APIキーはWindows資格情報マネージャーに安全に保存される。
    その他の設定はJSONファイルに保存される。

    Args:
        config: 保存する設定

    Returns:
        bool: 保存に成功した場合True
    """
    try:
        # APIキーを資格情報マネージャーに保存
        if not save_api_key_secure(config.api_key):
            return False

        # ディレクトリが存在しない場合は作成
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # JSONに保存するデータからapi_keyを除外
        data = asdict(config)
        data.pop("api_key", None)

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except (IOError, OSError):
        return False


def get_api_key() -> Optional[str]:
    """
    APIキーを取得する

    環境変数、資格情報マネージャーの順で取得する。
    環境変数が優先される。

    Returns:
        Optional[str]: APIキー（設定されていない場合はNone）
    """
    # 環境変数を優先
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        return env_key

    # 資格情報マネージャーから取得
    key = load_api_key_secure()
    return key if key else None
