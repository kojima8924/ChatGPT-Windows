"""
メインウィンドウモジュール

アプリケーションのメインUIを定義する。
- 上部: 入力テキストボックス（クリップボードから貼り付け）
- 中央: 送信ボタンと設定
- 下部: 出力テキストボックス（API応答）
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QLineEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QGroupBox, QSplitter, QMessageBox, QApplication,
    QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QClipboard

from app.config import AppConfig, load_config, save_config, is_api_key_pattern
from app.api.openai_client import ChatGPTClient, ChatResponse


class ApiWorker(QThread):
    """
    API呼び出しを別スレッドで実行するワーカー

    UIをブロックしないようにバックグラウンドでAPI通信を行う。
    """

    # 完了シグナル: レスポンスを返す
    finished = Signal(ChatResponse)

    def __init__(
        self,
        client: ChatGPTClient,
        message: str,
        system_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int
    ):
        super().__init__()
        self.client = client
        self.message = message
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def run(self):
        """スレッドで実行される処理"""
        response = self.client.send_message(
            user_message=self.message,
            system_prompt=self.system_prompt,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        self.finished.emit(response)


class MainWindow(QMainWindow):
    """
    メインウィンドウクラス

    アプリケーションの主要なUIと機能を提供する。
    """

    def __init__(self):
        super().__init__()

        # 設定を読み込み
        self.config = load_config()

        # APIクライアント（初期化は後で）
        self.client: ChatGPTClient = None
        self.worker: ApiWorker = None

        # UIを構築
        self._setup_ui()

        # 設定を適用
        self._apply_config()

        # クリップボード監視用
        self.clipboard = QApplication.clipboard()

        # 自動貼り付けが有効なら初回読み込み（APIキーはスキップ）
        if self.config.auto_paste:
            QTimer.singleShot(100, self._auto_paste_from_clipboard)

    def _setup_ui(self):
        """UIコンポーネントを構築"""

        # ウィンドウ設定
        self.setWindowTitle("ChatGPT Desktop")
        self.setMinimumSize(500, 600)
        self.resize(600, 700)

        # 中央ウィジェット
        central = QWidget()
        self.setCentralWidget(central)

        # メインレイアウト
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ============================================
        # 設定エリア（折りたたみ可能）
        # ============================================
        settings_group = QGroupBox("設定")
        settings_layout = QVBoxLayout(settings_group)

        # APIキー入力
        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(QLabel("APIキー:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-...")
        api_key_layout.addWidget(self.api_key_input)
        settings_layout.addLayout(api_key_layout)

        # モデル選択とパラメータ
        params_layout = QHBoxLayout()

        # モデル選択
        params_layout.addWidget(QLabel("モデル:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-3.5-turbo"
        ])
        self.model_combo.setEditable(True)  # カスタムモデル入力可能
        params_layout.addWidget(self.model_combo)

        params_layout.addSpacing(20)

        # Temperature
        params_layout.addWidget(QLabel("Temperature:"))
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(0.7)
        params_layout.addWidget(self.temp_spin)

        params_layout.addSpacing(20)

        # 最大トークン
        params_layout.addWidget(QLabel("最大トークン:"))
        self.tokens_spin = QSpinBox()
        self.tokens_spin.setRange(1, 4096)
        self.tokens_spin.setValue(1024)
        params_layout.addWidget(self.tokens_spin)

        params_layout.addStretch()
        settings_layout.addLayout(params_layout)

        # オプション
        options_layout = QHBoxLayout()
        self.always_on_top_check = QCheckBox("常に最前面")
        self.always_on_top_check.toggled.connect(self._toggle_always_on_top)
        options_layout.addWidget(self.always_on_top_check)

        self.auto_paste_check = QCheckBox("起動時に自動貼り付け")
        options_layout.addWidget(self.auto_paste_check)

        options_layout.addStretch()

        # 設定保存ボタン
        self.save_config_btn = QPushButton("設定を保存")
        self.save_config_btn.clicked.connect(self._save_config)
        options_layout.addWidget(self.save_config_btn)

        settings_layout.addLayout(options_layout)

        layout.addWidget(settings_group)

        # ============================================
        # システムプロンプト
        # ============================================
        prompt_group = QGroupBox("システムプロンプト（AIへの指示）")
        prompt_layout = QVBoxLayout(prompt_group)

        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setMaximumHeight(80)
        self.system_prompt_input.setPlaceholderText(
            "例: あなたは優秀な翻訳者です。入力された文章を日本語に翻訳してください。"
        )
        prompt_layout.addWidget(self.system_prompt_input)

        layout.addWidget(prompt_group)

        # ============================================
        # 入力/出力エリア（スプリッター）
        # ============================================
        splitter = QSplitter(Qt.Vertical)

        # 入力エリア
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)

        input_header = QHBoxLayout()
        input_header.addWidget(QLabel("入力テキスト"))
        input_header.addStretch()

        self.paste_btn = QPushButton("クリップボードから貼り付け")
        self.paste_btn.clicked.connect(self._paste_from_clipboard)
        input_header.addWidget(self.paste_btn)

        self.clear_input_btn = QPushButton("クリア")
        self.clear_input_btn.clicked.connect(lambda: self.input_text.clear())
        input_header.addWidget(self.clear_input_btn)

        input_layout.addLayout(input_header)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("ここにテキストを入力、またはクリップボードから貼り付け...")
        self.input_text.setFont(QFont("Consolas", 10))
        input_layout.addWidget(self.input_text)

        splitter.addWidget(input_widget)

        # 出力エリア
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)

        output_header = QHBoxLayout()
        output_header.addWidget(QLabel("出力テキスト"))
        output_header.addStretch()

        self.copy_btn = QPushButton("クリップボードにコピー")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        output_header.addWidget(self.copy_btn)

        self.clear_output_btn = QPushButton("クリア")
        self.clear_output_btn.clicked.connect(lambda: self.output_text.clear())
        output_header.addWidget(self.clear_output_btn)

        output_layout.addLayout(output_header)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("APIからの応答がここに表示されます...")
        self.output_text.setFont(QFont("Consolas", 10))
        output_layout.addWidget(self.output_text)

        splitter.addWidget(output_widget)

        # スプリッターの初期サイズ比率
        splitter.setSizes([300, 300])

        layout.addWidget(splitter, 1)  # stretch=1 で残りスペースを使用

        # ============================================
        # 送信ボタン
        # ============================================
        button_layout = QHBoxLayout()

        self.send_btn = QPushButton("送信 (Ctrl+Enter)")
        self.send_btn.setMinimumHeight(40)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
            QPushButton:disabled {
                background-color: #6b7280;
            }
        """)
        self.send_btn.clicked.connect(self._send_request)
        button_layout.addWidget(self.send_btn)

        layout.addLayout(button_layout)

        # ============================================
        # ステータスバー
        # ============================================
        self.status_label = QLabel("準備完了")
        self.status_label.setStyleSheet("color: #6b7280;")
        layout.addWidget(self.status_label)

        # ============================================
        # キーボードショートカット
        # ============================================
        # Ctrl+Enter で送信
        self.input_text.installEventFilter(self)

    def eventFilter(self, obj, event):
        """キーボードショートカットを処理"""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent

        if obj == self.input_text and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
                self._send_request()
                return True
        return super().eventFilter(obj, event)

    def _apply_config(self):
        """設定をUIに反映"""
        self.api_key_input.setText(self.config.api_key)
        self.model_combo.setCurrentText(self.config.model)
        self.system_prompt_input.setPlainText(self.config.system_prompt)
        self.temp_spin.setValue(self.config.temperature)
        self.tokens_spin.setValue(self.config.max_tokens)
        self.always_on_top_check.setChecked(self.config.always_on_top)
        self.auto_paste_check.setChecked(self.config.auto_paste)

        # 常に最前面を適用
        self._toggle_always_on_top(self.config.always_on_top)

    def _save_config(self):
        """現在のUI設定を保存"""
        self.config.api_key = self.api_key_input.text()
        self.config.model = self.model_combo.currentText()
        self.config.system_prompt = self.system_prompt_input.toPlainText()
        self.config.temperature = self.temp_spin.value()
        self.config.max_tokens = self.tokens_spin.value()
        self.config.always_on_top = self.always_on_top_check.isChecked()
        self.config.auto_paste = self.auto_paste_check.isChecked()

        if save_config(self.config):
            self._set_status("設定を保存しました", "green")
        else:
            self._set_status("設定の保存に失敗しました", "red")

    def _toggle_always_on_top(self, checked: bool):
        """常に最前面の切り替え"""
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()  # フラグ変更後に再表示が必要

    def _auto_paste_from_clipboard(self):
        """起動時の自動貼り付け（APIキーはスキップ）"""
        text = self.clipboard.text()
        if text:
            # APIキーのパターンの場合はスキップ
            if is_api_key_pattern(text):
                self._set_status("クリップボードにAPIキーが検出されたためスキップしました", "orange")
                return
            self.input_text.setPlainText(text)
            self._set_status("クリップボードから貼り付けました", "green")

    def _paste_from_clipboard(self):
        """クリップボードからテキストを貼り付け（手動）"""
        text = self.clipboard.text()
        if text:
            # APIキーのパターンの場合は警告
            if is_api_key_pattern(text):
                self._set_status("警告: APIキーのようなテキストです", "orange")
                return
            self.input_text.setPlainText(text)
            self._set_status("クリップボードから貼り付けました", "green")
        else:
            self._set_status("クリップボードにテキストがありません", "orange")

    def _copy_to_clipboard(self):
        """出力テキストをクリップボードにコピー"""
        text = self.output_text.toPlainText()
        if text:
            self.clipboard.setText(text)
            self._set_status("クリップボードにコピーしました", "green")
        else:
            self._set_status("コピーするテキストがありません", "orange")

    def _send_request(self):
        """APIリクエストを送信"""
        # APIキーチェック
        api_key = self.api_key_input.text().strip()
        if not api_key:
            self._set_status("APIキーを入力してください", "red")
            return

        # 入力テキストチェック
        input_text = self.input_text.toPlainText().strip()
        if not input_text:
            self._set_status("入力テキストがありません", "red")
            return

        # すでに処理中の場合は無視
        if self.worker and self.worker.isRunning():
            return

        # クライアント作成
        self.client = ChatGPTClient(api_key)

        # UIを処理中状態に
        self.send_btn.setEnabled(False)
        self.send_btn.setText("処理中...")
        self._set_status("APIリクエスト中...", "blue")

        # ワーカースレッドを作成・開始
        self.worker = ApiWorker(
            client=self.client,
            message=input_text,
            system_prompt=self.system_prompt_input.toPlainText(),
            model=self.model_combo.currentText(),
            temperature=self.temp_spin.value(),
            max_tokens=self.tokens_spin.value()
        )
        self.worker.finished.connect(self._on_response)
        self.worker.start()

    def _on_response(self, response: ChatResponse):
        """APIレスポンスを受信した時の処理"""
        # UIを通常状態に戻す
        self.send_btn.setEnabled(True)
        self.send_btn.setText("送信 (Ctrl+Enter)")

        if response.success:
            self.output_text.setPlainText(response.content)
            self._set_status("完了", "green")
        else:
            self.output_text.setPlainText(f"エラー: {response.error}")
            self._set_status(f"エラー: {response.error}", "red")

    def _set_status(self, message: str, color: str = "gray"):
        """ステータスメッセージを更新"""
        color_map = {
            "green": "#10b981",
            "red": "#ef4444",
            "blue": "#3b82f6",
            "orange": "#f59e0b",
            "gray": "#6b7280"
        }
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color_map.get(color, color)};")
