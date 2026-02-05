# ChatGPT Desktop

Windows向けのChatGPTデスクトップクライアント。クリップボードのテキストをワンクリックでChatGPT APIに送信し、ストリーミングで結果を表示します。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/GUI-PySide6%20(Qt6)-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 特徴

- **ストリーミング応答** - GPTの応答をリアルタイムに表示
- **システムプロンプトプリセット** - 翻訳・補完・要約・校正・説明の5つのプリセットを搭載。カスタムプリセットも追加可能
- **クリップボード連携** - 起動時に自動ペースト、ワンクリックで入出力のコピー＆ペースト
- **システムトレイ常駐** - 閉じてもトレイに常駐し、すぐに再表示可能
- **グローバルホットキー** - `Ctrl+Alt+V` でどこからでもウィンドウを呼び出し
- **1インスタンス制御** - 二重起動を防止し、既存ウィンドウを前面に表示
- **APIキーの安全な管理** - Windows資格情報マネージャーに保存（平文ファイルに保存しない）
- **ダークテーマ** - 目に優しいダークモードUI
- **モデル自動取得** - 利用可能なGPTモデルをAPIから自動取得
- **パラメータ調整** - Temperature、最大トークン数を自由に設定

## スクリーンショット

<!-- スクリーンショットを追加する場合: -->
<!-- ![メイン画面](docs/screenshot.png) -->

## 必要環境

- Windows 10/11
- Python 3.10 以上
- OpenAI APIキー

## インストール

```bash
git clone https://github.com/kojima8924/ChatGPT-Windows.git
cd ChatGPT-Windows
pip install -r requirements.txt
```

## 使い方

### 起動

```bash
python main.py
```

バックグラウンド起動（トレイに常駐した状態で起動）:

```bash
python main.py --hidden
```

### 初回設定

1. アプリを起動し、「APIキー」欄にOpenAI APIキーを入力
2. 「設定を保存」をクリック（キーはWindows資格情報マネージャーに安全に保存されます）
3. 使いたいモデルを選択（デフォルト: gpt-5）

環境変数 `OPENAI_API_KEY` を設定している場合は、入力を省略できます。

### 基本操作

1. 入力欄にテキストを入力（または「クリップボードから貼り付け」をクリック）
2. 必要に応じてシステムプロンプトのプリセットを選択
3. 「送信 (Ctrl+Enter)」をクリック、またはCtrl+Enterを押す
4. 出力欄にストリーミングで結果が表示される
5. 「クリップボードにコピー」で結果をコピー

## キーボードショートカット

| ショートカット | 動作 |
|---|---|
| `Ctrl+Enter` | 送信 |
| `Ctrl+Alt+V` | ウィンドウの表示/非表示切り替え（グローバル） |

## 設定

設定は `~/.chatgpt-windows/config.json` に保存されます（APIキーを除く）。

| 項目 | 説明 | デフォルト |
|---|---|---|
| モデル | 使用するGPTモデル | gpt-5 |
| Temperature | 応答のランダム性 (0.0-2.0) | 0.7 |
| 最大トークン数 | 応答の最大長 (1-16384) | 1024 |
| 常に最前面 | ウィンドウを最前面に固定 | OFF |
| 起動時自動ペースト | 起動時にクリップボードを自動入力 | OFF |

## プロジェクト構成

```
ChatGPT-Windows/
├── main.py              # エントリーポイント（1インスタンス制御、DPI対応、テーマ設定）
├── app/
│   ├── __init__.py
│   ├── config.py        # 設定管理（keyring連携）
│   ├── window.py        # メインUI（プリセット管理、トレイ、ホットキー）
│   └── api/
│       ├── __init__.py
│       └── openai_client.py  # OpenAI API クライアント（ストリーミング対応）
├── requirements.txt     # 依存パッケージ
└── README.md
```

## 依存パッケージ

| パッケージ | バージョン | 用途 |
|---|---|---|
| PySide6 | >= 6.6.0 | Qt6 GUIフレームワーク |
| openai | >= 1.0.0 | OpenAI APIクライアント |
| keyring | >= 24.0.0 | Windows資格情報マネージャー連携 |

## ライセンス

[MIT License](LICENSE)
