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
    QSizePolicy, QDialog, QListWidget, QListWidgetItem,
    QDialogButtonBox, QFormLayout, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QClipboard, QTextCursor

from app.config import (
    AppConfig, load_config, save_config, is_api_key_pattern, get_api_key,
    AVAILABLE_MODELS, MAX_TOKENS_LIMIT, PromptPreset, DEFAULT_PRESETS
)
from app.api.openai_client import ChatGPTClient, ChatResponse, fetch_available_models


class PresetEditorDialog(QDialog):
    """
    プリセット編集ダイアログ

    プリセットの追加、編集、削除、並べ替えを行う。
    """

    def __init__(self, presets: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("プリセット編集")
        self.setMinimumSize(500, 400)
        self.resize(600, 500)

        # プリセットのコピーを作成
        self.presets = [dict(p) for p in presets]
        self.selected_index = -1

        self._setup_ui()
        self._update_list()

    def _setup_ui(self):
        """UIを構築"""
        # トップレベルレイアウトを1本に統一
        main_layout = QVBoxLayout(self)

        # 左右分割用の水平レイアウト
        h_layout = QHBoxLayout()

        # 左側: プリセットリスト
        left_layout = QVBoxLayout()

        self.preset_list = QListWidget()
        self.preset_list.currentRowChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.preset_list)

        # リスト操作ボタン
        list_btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("追加")
        self.add_btn.clicked.connect(self._add_preset)
        list_btn_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("削除")
        self.remove_btn.clicked.connect(self._remove_preset)
        list_btn_layout.addWidget(self.remove_btn)

        self.up_btn = QPushButton("↑")
        self.up_btn.setMaximumWidth(40)
        self.up_btn.clicked.connect(self._move_up)
        list_btn_layout.addWidget(self.up_btn)

        self.down_btn = QPushButton("↓")
        self.down_btn.setMaximumWidth(40)
        self.down_btn.clicked.connect(self._move_down)
        list_btn_layout.addWidget(self.down_btn)

        left_layout.addLayout(list_btn_layout)
        h_layout.addLayout(left_layout, 1)

        # 右側: 編集フォーム
        right_layout = QVBoxLayout()

        form_group = QGroupBox("プリセット編集")
        form_layout = QFormLayout(form_group)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("ボタンに表示する名前")
        self.name_input.textChanged.connect(self._on_name_changed)
        form_layout.addRow("名前:", self.name_input)

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("システムプロンプトの内容")
        self.prompt_input.textChanged.connect(self._on_prompt_changed)
        form_layout.addRow("プロンプト:", self.prompt_input)

        right_layout.addWidget(form_group)

        # デフォルトに戻すボタン
        self.reset_btn = QPushButton("デフォルトに戻す")
        self.reset_btn.clicked.connect(self._reset_to_default)
        right_layout.addWidget(self.reset_btn)

        h_layout.addLayout(right_layout, 2)

        # 水平レイアウトをメインに追加
        main_layout.addLayout(h_layout)

        # ダイアログボタン
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        main_layout.addWidget(button_box)

    def _update_list(self):
        """リストを更新"""
        self.preset_list.clear()
        for preset in self.presets:
            self.preset_list.addItem(preset["name"])

        # 選択状態を復元
        if 0 <= self.selected_index < len(self.presets):
            self.preset_list.setCurrentRow(self.selected_index)
        elif self.presets:
            self.preset_list.setCurrentRow(0)

        self._update_buttons()

    def _update_buttons(self):
        """ボタンの有効/無効を更新"""
        has_selection = self.selected_index >= 0
        can_remove = len(self.presets) > 1

        self.remove_btn.setEnabled(has_selection and can_remove)
        self.up_btn.setEnabled(has_selection and self.selected_index > 0)
        self.down_btn.setEnabled(
            has_selection and self.selected_index < len(self.presets) - 1
        )
        self.name_input.setEnabled(has_selection)
        self.prompt_input.setEnabled(has_selection)

    def _on_selection_changed(self, index: int):
        """選択変更時の処理"""
        self.selected_index = index

        if 0 <= index < len(self.presets):
            preset = self.presets[index]
            # シグナルを一時的にブロック
            self.name_input.blockSignals(True)
            self.prompt_input.blockSignals(True)

            self.name_input.setText(preset["name"])
            self.prompt_input.setPlainText(preset["prompt"])

            self.name_input.blockSignals(False)
            self.prompt_input.blockSignals(False)
        else:
            self.name_input.clear()
            self.prompt_input.clear()

        self._update_buttons()

    def _on_name_changed(self, text: str):
        """名前変更時の処理"""
        if 0 <= self.selected_index < len(self.presets):
            self.presets[self.selected_index]["name"] = text
            # リストアイテムのテキストを更新
            item = self.preset_list.item(self.selected_index)
            if item:
                item.setText(text)

    def _on_prompt_changed(self):
        """プロンプト変更時の処理"""
        if 0 <= self.selected_index < len(self.presets):
            self.presets[self.selected_index]["prompt"] = \
                self.prompt_input.toPlainText()

    def _add_preset(self):
        """プリセットを追加"""
        new_preset = {
            "name": f"プリセット{len(self.presets) + 1}",
            "prompt": ""
        }
        self.presets.append(new_preset)
        self.selected_index = len(self.presets) - 1
        self._update_list()

    def _remove_preset(self):
        """プリセットを削除"""
        if 0 <= self.selected_index < len(self.presets) and len(self.presets) > 1:
            del self.presets[self.selected_index]
            if self.selected_index >= len(self.presets):
                self.selected_index = len(self.presets) - 1
            self._update_list()

    def _move_up(self):
        """プリセットを上に移動"""
        if self.selected_index > 0:
            idx = self.selected_index
            self.presets[idx], self.presets[idx - 1] = \
                self.presets[idx - 1], self.presets[idx]
            self.selected_index -= 1
            self._update_list()

    def _move_down(self):
        """プリセットを下に移動"""
        if self.selected_index < len(self.presets) - 1:
            idx = self.selected_index
            self.presets[idx], self.presets[idx + 1] = \
                self.presets[idx + 1], self.presets[idx]
            self.selected_index += 1
            self._update_list()

    def _reset_to_default(self):
        """デフォルトプリセットに戻す"""
        reply = QMessageBox.question(
            self,
            "確認",
            "プリセットをデフォルトに戻しますか？\n現在の変更は失われます。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.presets = [dict(p) for p in DEFAULT_PRESETS]
            self.selected_index = 0
            self._update_list()

    def get_presets(self) -> list:
        """編集後のプリセットリストを取得"""
        return self.presets


class ModelFetchWorker(QThread):
    """
    モデルリストを取得するワーカー

    起動時にOpenAI APIから利用可能なモデルを取得する。
    """

    # 完了シグナル: モデルリスト（Noneの場合は取得失敗）
    finished = Signal(object)

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    def run(self):
        """モデルリストを取得"""
        models = fetch_available_models(self.api_key)
        self.finished.emit(models)


class ApiWorker(QThread):
    """
    API呼び出しを別スレッドで実行するワーカー

    UIをブロックしないようにバックグラウンドでAPI通信を行う。
    ストリーミングレスポンスに対応。
    """

    # 完了シグナル: レスポンスを返す
    finished = Signal(ChatResponse)
    # ストリーミングチャンクシグナル: テキストの断片を返す
    chunk_received = Signal(str)

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
        """スレッドで実行される処理（ストリーミング対応）"""
        response = self.client.send_message(
            user_message=self.message,
            system_prompt=self.system_prompt,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
            on_chunk=self._on_chunk
        )
        self.finished.emit(response)

    def _on_chunk(self, chunk_text: str):
        """ストリーミングチャンクを受信した時のコールバック"""
        self.chunk_received.emit(chunk_text)


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
        self.model_fetch_worker: ModelFetchWorker = None

        # プリセットボタンのリスト
        self.preset_buttons: list = []

        # UIを構築
        self._setup_ui()

        # 設定を適用
        self._apply_config()

        # クリップボード監視用
        self.clipboard = QApplication.clipboard()

        # 自動貼り付けが有効なら初回読み込み（APIキーはスキップ）
        if self.config.auto_paste:
            QTimer.singleShot(100, self._auto_paste_from_clipboard)

        # モデルリストを動的に取得（非同期）
        QTimer.singleShot(200, self._fetch_models)

    def _setup_ui(self):
        """UIコンポーネントを構築"""

        # ウィンドウ設定
        self.setWindowTitle("ChatGPT Desktop")
        self.setMinimumSize(500, 650)
        self.resize(650, 750)

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

        # モデル選択（ドロップダウンリストから選択のみ）
        params_layout.addWidget(QLabel("モデル:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(AVAILABLE_MODELS)
        self.model_combo.setEditable(False)  # ドロップダウン選択式
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

        # 最大トークン（上限を拡大）
        params_layout.addWidget(QLabel("最大トークン:"))
        self.tokens_spin = QSpinBox()
        self.tokens_spin.setRange(1, MAX_TOKENS_LIMIT)
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
        # システムプロンプト（プリセット付き）
        # ============================================
        prompt_group = QGroupBox("システムプロンプト（AIへの指示）")
        prompt_layout = QVBoxLayout(prompt_group)

        # プリセットボタン行
        preset_header = QHBoxLayout()

        # スクロール可能なプリセットボタンエリア
        self.preset_scroll = QScrollArea()
        self.preset_scroll.setWidgetResizable(True)
        self.preset_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.preset_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.preset_scroll.setMaximumHeight(50)
        self.preset_scroll.setFrameShape(QFrame.NoFrame)

        self.preset_container = QWidget()
        self.preset_btn_layout = QHBoxLayout(self.preset_container)
        self.preset_btn_layout.setContentsMargins(0, 0, 0, 0)
        self.preset_btn_layout.setSpacing(4)

        self.preset_scroll.setWidget(self.preset_container)
        preset_header.addWidget(self.preset_scroll, 1)

        # 編集ボタン
        self.edit_preset_btn = QPushButton("編集")
        self.edit_preset_btn.setMaximumWidth(60)
        self.edit_preset_btn.clicked.connect(self._open_preset_editor)
        preset_header.addWidget(self.edit_preset_btn)

        prompt_layout.addLayout(preset_header)

        # システムプロンプト入力
        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setMaximumHeight(80)
        self.system_prompt_input.setPlaceholderText(
            "例: あなたは優秀な翻訳者です。入力された文章を日本語に翻訳してください。"
        )
        self.system_prompt_input.textChanged.connect(self._on_prompt_manually_changed)
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
        # 日本語混在に対応したフォント設定（フォールバック付き）
        input_font = QFont()
        input_font.setFamilies(["Consolas", "Yu Gothic UI", "MS Gothic"])
        input_font.setPointSize(10)
        self.input_text.setFont(input_font)
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
        # 日本語混在に対応したフォント設定（フォールバック付き）
        output_font = QFont()
        output_font.setFamilies(["Consolas", "Yu Gothic UI", "MS Gothic"])
        output_font.setPointSize(10)
        self.output_text.setFont(output_font)
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

    def _create_preset_buttons(self):
        """プリセットボタンを作成"""
        # 既存のボタンをクリア
        for btn in self.preset_buttons:
            btn.deleteLater()
        self.preset_buttons.clear()

        # 新しいボタンを作成
        for i, preset in enumerate(self.config.presets):
            btn = QPushButton(preset["name"])
            btn.setCheckable(True)
            btn.setMinimumWidth(60)
            btn.clicked.connect(lambda checked, idx=i: self._on_preset_clicked(idx))

            # スタイル設定
            btn.setStyleSheet("""
                QPushButton {
                    padding: 6px 12px;
                    border-radius: 4px;
                }
                QPushButton:checked {
                    background-color: #3b82f6;
                    color: white;
                }
            """)

            self.preset_btn_layout.addWidget(btn)
            self.preset_buttons.append(btn)

        # ストレッチを追加
        self.preset_btn_layout.addStretch()

        # アクティブなプリセットを選択
        self._update_preset_button_states()

    def _update_preset_button_states(self):
        """プリセットボタンの選択状態を更新"""
        for i, btn in enumerate(self.preset_buttons):
            btn.setChecked(i == self.config.active_preset_index)

    def _on_preset_clicked(self, index: int):
        """プリセットボタンがクリックされた時の処理"""
        if 0 <= index < len(self.config.presets):
            self.config.active_preset_index = index
            preset = self.config.presets[index]

            # システムプロンプトを更新（シグナルをブロック）
            self.system_prompt_input.blockSignals(True)
            self.system_prompt_input.setPlainText(preset["prompt"])
            self.system_prompt_input.blockSignals(False)

            self.config.system_prompt = preset["prompt"]
            self._update_preset_button_states()
            self._set_status(f"プリセット「{preset['name']}」を選択", "green")

    def _on_prompt_manually_changed(self):
        """システムプロンプトが手動で変更された時の処理"""
        current_text = self.system_prompt_input.toPlainText()

        # 現在のプリセットと一致するかチェック
        if 0 <= self.config.active_preset_index < len(self.config.presets):
            preset_prompt = self.config.presets[self.config.active_preset_index]["prompt"]
            if current_text != preset_prompt:
                # カスタム状態に変更
                self.config.active_preset_index = -1
                self._update_preset_button_states()

        self.config.system_prompt = current_text

    def _open_preset_editor(self):
        """プリセット編集ダイアログを開く"""
        dialog = PresetEditorDialog(self.config.presets, self)
        if dialog.exec() == QDialog.Accepted:
            self.config.presets = dialog.get_presets()

            # アクティブインデックスを調整
            if self.config.active_preset_index >= len(self.config.presets):
                self.config.active_preset_index = 0

            # ボタンを再作成
            self._create_preset_buttons()

            # 設定を保存
            self._save_config()
            self._set_status("プリセットを更新しました", "green")

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
        # APIキーは自動表示しない（ユーザーが入力した場合のみ表示）
        # 環境変数やkeyringから取得したキーは送信時に使用
        # self.api_key_input.setText(self.config.api_key)
        self.model_combo.setCurrentText(self.config.model)
        self.system_prompt_input.setPlainText(self.config.system_prompt)
        self.temp_spin.setValue(self.config.temperature)
        self.tokens_spin.setValue(self.config.max_tokens)
        self.always_on_top_check.setChecked(self.config.always_on_top)
        self.auto_paste_check.setChecked(self.config.auto_paste)

        # プリセットボタンを作成
        self._create_preset_buttons()

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

    def _get_clipboard_text(self) -> str:
        """
        クリップボードからテキストを安全に取得

        Returns:
            str: クリップボードのテキスト（取得失敗時は空文字列）
        """
        try:
            return self.clipboard.text() or ""
        except Exception:
            return ""

    def _set_clipboard_text(self, text: str) -> bool:
        """
        クリップボードにテキストを安全に設定

        Args:
            text: 設定するテキスト

        Returns:
            bool: 設定に成功した場合True
        """
        try:
            self.clipboard.setText(text)
            return True
        except Exception:
            return False

    def _auto_paste_from_clipboard(self):
        """起動時の自動貼り付け（APIキーはスキップ）"""
        text = self._get_clipboard_text()
        if text:
            # APIキーのパターンの場合はスキップ
            if is_api_key_pattern(text):
                self._set_status("クリップボードにAPIキーが検出されたためスキップしました", "orange")
                return
            self.input_text.setPlainText(text)
            self._set_status("クリップボードから貼り付けました", "green")

    def _paste_from_clipboard(self):
        """クリップボードからテキストを貼り付け（手動）"""
        text = self._get_clipboard_text()
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
            if self._set_clipboard_text(text):
                self._set_status("クリップボードにコピーしました", "green")
            else:
                self._set_status("クリップボードへのコピーに失敗しました", "red")
        else:
            self._set_status("コピーするテキストがありません", "orange")

    def _cleanup_worker(self):
        """古いワーカースレッドをクリーンアップ"""
        if self.worker is not None:
            # シグナル接続を解除
            try:
                self.worker.finished.disconnect()
            except RuntimeError:
                pass  # すでに接続解除されている場合
            try:
                self.worker.chunk_received.disconnect()
            except RuntimeError:
                pass  # すでに接続解除されている場合
            # スレッドが終了するまで待機（タイムアウト付き）
            if self.worker.isRunning():
                self.worker.wait(1000)  # 最大1秒待機
            self.worker = None

    def _send_request(self):
        """APIリクエストを送信"""
        # APIキーチェック（UI入力→環境変数/keyringの順でフォールバック）
        api_key = self.api_key_input.text().strip()
        if not api_key:
            # UI入力が空の場合、環境変数またはkeyringから取得
            from app.config import get_api_key
            api_key = get_api_key()
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

        # 古いワーカーをクリーンアップ
        self._cleanup_worker()

        # クライアント作成
        self.client = ChatGPTClient(api_key)

        # UIを処理中状態に（誤操作防止のため各種UI要素を無効化）
        self.send_btn.setEnabled(False)
        self.send_btn.setText("処理中...")
        self.api_key_input.setEnabled(False)
        self.model_combo.setEnabled(False)
        self.temp_spin.setEnabled(False)
        self.tokens_spin.setEnabled(False)
        self.edit_preset_btn.setEnabled(False)
        self.save_config_btn.setEnabled(False)
        self._set_status("APIリクエスト中...", "blue")

        # 出力テキストをクリア（ストリーミング準備）
        self.output_text.clear()

        # ワーカースレッドを作成・開始
        self.worker = ApiWorker(
            client=self.client,
            message=input_text,
            system_prompt=self.system_prompt_input.toPlainText(),
            model=self.model_combo.currentText(),
            temperature=self.temp_spin.value(),
            max_tokens=self.tokens_spin.value()
        )
        # UniqueConnectionで重複接続を防止
        self.worker.finished.connect(self._on_response, Qt.UniqueConnection)
        self.worker.chunk_received.connect(self._on_chunk, Qt.UniqueConnection)
        self.worker.start()

    def _on_chunk(self, chunk_text: str):
        """ストリーミングチャンクを受信した時の処理"""
        # 現在のカーソル位置を保持
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk_text)
        self.output_text.setTextCursor(cursor)
        # 自動スクロール
        self.output_text.ensureCursorVisible()

    def _on_response(self, response: ChatResponse):
        """APIレスポンスを受信した時の処理（ストリーミング完了時）"""
        # UIを通常状態に戻す（全要素を有効化）
        self.send_btn.setEnabled(True)
        self.send_btn.setText("送信 (Ctrl+Enter)")
        self.api_key_input.setEnabled(True)
        self.model_combo.setEnabled(True)
        self.temp_spin.setEnabled(True)
        self.tokens_spin.setEnabled(True)
        self.edit_preset_btn.setEnabled(True)
        self.save_config_btn.setEnabled(True)

        if response.success:
            # ストリーミングで既にテキストは表示されているので、ステータスのみ更新
            self._set_status("完了", "green")
        else:
            # エラーの場合は出力エリアにエラーメッセージを表示
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

    def _fetch_models(self):
        """利用可能なモデルリストを動的に取得"""
        # APIキーを取得（UI入力→環境変数/keyringの順）
        api_key = self.api_key_input.text().strip()
        if not api_key:
            api_key = get_api_key()

        if not api_key:
            # APIキーがない場合はデフォルトリストを使用
            return

        # 既にワーカーが実行中の場合はスキップ
        if self.model_fetch_worker and self.model_fetch_worker.isRunning():
            return

        # ワーカースレッドでモデルリストを取得
        self.model_fetch_worker = ModelFetchWorker(api_key)
        self.model_fetch_worker.finished.connect(self._on_models_fetched, Qt.UniqueConnection)
        self.model_fetch_worker.start()

    def _on_models_fetched(self, models):
        """モデルリスト取得完了時の処理"""
        if models and len(models) > 0:
            # 現在選択されているモデルを保持
            current_model = self.model_combo.currentText()

            # コンボボックスを更新
            self.model_combo.clear()
            self.model_combo.addItems(models)

            # 以前のモデルが新しいリストにあれば選択を維持
            index = self.model_combo.findText(current_model)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
            else:
                # なければ最初のモデルを選択
                self.model_combo.setCurrentIndex(0)

            self._set_status(f"モデルリストを更新しました（{len(models)}件）", "green")
        else:
            # 取得失敗時はデフォルトリストを維持（何もしない）
            self._set_status("モデルリスト取得失敗、デフォルトを使用", "orange")

    def closeEvent(self, event):
        """ウィンドウ終了時のクリーンアップ"""
        self._cleanup_worker()

        # モデル取得ワーカーもクリーンアップ
        if self.model_fetch_worker and self.model_fetch_worker.isRunning():
            self.model_fetch_worker.wait(1000)

        super().closeEvent(event)
