"""
設定管理モジュール

アプリケーションの設定を管理する。
設定はJSONファイルに保存され、起動時に読み込まれる。
APIキーはWindows資格情報マネージャーに安全に保存される。
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict, fields, field
from typing import Optional, List, Dict
import keyring


# ============================================
# 設定ファイルのパス
# ユーザーのホームディレクトリに保存
# ============================================
CONFIG_DIR = Path.home() / ".chatgpt-windows"
CONFIG_FILE = CONFIG_DIR / "config.json"
LOCK_FILE = CONFIG_DIR / "config.lock"

# ============================================
# キーリング設定（Windows資格情報マネージャー用）
# ============================================
KEYRING_SERVICE = "ChatGPT-Windows"
KEYRING_USERNAME = "openai_api_key"

# ============================================
# 利用可能なモデルリスト
# ============================================
AVAILABLE_MODELS: List[str] = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-3.5-turbo",
]

# ============================================
# トークン数の上限設定
# ============================================
MAX_TOKENS_LIMIT = 16384

# ============================================
# デフォルトのシステムプロンプトプリセット
# ============================================
DEFAULT_PRESETS: List[Dict[str, str]] = [
    {
        "name": "翻訳",
        "prompt": "ユーザーの入力に対して、英日あるいは日英の翻訳をしてください。原文の意味を正確に伝えつつ、自然な表現にしてください。"
    },
    {
        "name": "補完",
        "prompt": "ユーザーの入力テキストの続きを自然に補完してください。文脈を理解し、一貫性のある内容を生成してください。"
    },
    {
        "name": "要約",
        "prompt": "ユーザーの入力テキストを簡潔に要約してください。重要なポイントを漏らさず、分かりやすくまとめてください。"
    },
    {
        "name": "校正",
        "prompt": "ユーザーの入力テキストの文法・スペル・表現を校正してください。修正箇所があれば修正後のテキストを出力してください。"
    },
    {
        "name": "説明",
        "prompt": "ユーザーの入力内容について、分かりやすく詳しく説明してください。専門用語は噛み砕いて解説してください。"
    },
]


@dataclass
class PromptPreset:
    """
    システムプロンプトのプリセット

    Attributes:
        name: プリセット名（ボタンに表示）
        prompt: システムプロンプトの内容
    """
    name: str
    prompt: str


@dataclass
class AppConfig:
    """
    アプリケーション設定を保持するデータクラス

    Attributes:
        api_key: OpenAI APIキー（メモリ上のみ、保存時はkeyringを使用）
        model: 使用するモデル名
        system_prompt: 現在のシステムプロンプト（AIへの指示）
        temperature: 創造性パラメータ (0.0-2.0)
        max_tokens: 最大出力トークン数
        always_on_top: 常に最前面に表示するか
        auto_paste: 起動時に自動でクリップボードを読み込むか
        presets: システムプロンプトのプリセットリスト
        active_preset_index: 現在選択中のプリセットインデックス（-1はカスタム）
    """
    api_key: str = ""
    model: str = "gpt-4o-mini"
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 1024
    always_on_top: bool = True
    auto_paste: bool = True
    presets: List[Dict[str, str]] = field(default_factory=list)
    active_preset_index: int = 0

    def __post_init__(self):
        """初期化後の処理"""
        # プリセットが空の場合はデフォルトを設定
        if not self.presets:
            self.presets = [dict(p) for p in DEFAULT_PRESETS]
        # system_promptが空で、プリセットがある場合は最初のプリセットを適用
        if not self.system_prompt and self.presets:
            if 0 <= self.active_preset_index < len(self.presets):
                self.system_prompt = self.presets[self.active_preset_index]["prompt"]
            else:
                self.system_prompt = self.presets[0]["prompt"]
                self.active_preset_index = 0

    def get_preset_list(self) -> List[PromptPreset]:
        """プリセットリストをPromptPresetオブジェクトとして取得"""
        return [PromptPreset(**p) for p in self.presets]

    def set_preset_list(self, presets: List[PromptPreset]):
        """プリセットリストを設定"""
        self.presets = [asdict(p) for p in presets]

    def add_preset(self, name: str, prompt: str) -> int:
        """プリセットを追加し、インデックスを返す"""
        self.presets.append({"name": name, "prompt": prompt})
        return len(self.presets) - 1

    def remove_preset(self, index: int) -> bool:
        """プリセットを削除"""
        if 0 <= index < len(self.presets) and len(self.presets) > 1:
            del self.presets[index]
            # アクティブなインデックスを調整
            if self.active_preset_index >= len(self.presets):
                self.active_preset_index = len(self.presets) - 1
            return True
        return False

    def update_preset(self, index: int, name: str, prompt: str) -> bool:
        """プリセットを更新"""
        if 0 <= index < len(self.presets):
            self.presets[index] = {"name": name, "prompt": prompt}
            return True
        return False


def _get_valid_field_names() -> set:
    """AppConfigの有効なフィールド名を取得"""
    return {f.name for f in fields(AppConfig)}


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
    未知のキーは無視される。

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

                # 有効なフィールドのみをフィルタリング（未知のキーを無視）
                valid_keys = _get_valid_field_names()
                filtered_data = {k: v for k, v in data.items() if k in valid_keys}

                config = AppConfig(**filtered_data)
        except (json.JSONDecodeError, TypeError, ValueError):
            # パースエラーや不正な値の場合はデフォルト値を使用
            pass

    # APIキーは資格情報マネージャーから読み込む
    config.api_key = load_api_key_secure()

    return config


def save_config(config: AppConfig) -> bool:
    """
    設定をファイルに保存する

    APIキーはWindows資格情報マネージャーに安全に保存される。
    その他の設定はJSONファイルに保存される。
    ファイルロックを使用して競合を防ぐ。

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

        # ファイルロックを使用して書き込み（Windows互換）
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            try:
                # Windows環境ではmsvcrtを使用
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                json.dump(data, f, ensure_ascii=False, indent=2)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except (ImportError, OSError):
                # ロックが取得できない場合はそのまま書き込み
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
