"""
ChatGPT Desktop アプリケーション

クリップボードのテキストをChatGPT APIに送信し、
結果を表示するデスクトップアプリケーション。

使い方:
    python main.py

必要なパッケージ:
    pip install -r requirements.txt
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from app.window import MainWindow


def main():
    """アプリケーションのエントリーポイント"""

    # High DPI対応
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # アプリケーション作成
    app = QApplication(sys.argv)

    # アプリケーション情報
    app.setApplicationName("ChatGPT Desktop")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("ChatGPT-Windows")

    # デフォルトフォント設定（日本語対応）
    font = QFont("Yu Gothic UI", 9)
    app.setFont(font)

    # スタイルシート適用
    app.setStyleSheet("""
        /* 全体のベーススタイル */
        QWidget {
            background-color: #1f2937;
            color: #f3f4f6;
        }

        /* グループボックス */
        QGroupBox {
            font-weight: bold;
            border: 1px solid #374151;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 12px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px;
            color: #9ca3af;
        }

        /* テキスト入力 */
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #111827;
            border: 1px solid #374151;
            border-radius: 6px;
            padding: 8px;
            color: #f3f4f6;
            selection-background-color: #3b82f6;
        }
        QLineEdit:focus, QTextEdit:focus {
            border-color: #3b82f6;
        }

        /* コンボボックスのドロップダウン */
        QComboBox::drop-down {
            border: none;
            padding-right: 8px;
        }
        QComboBox QAbstractItemView {
            background-color: #1f2937;
            border: 1px solid #374151;
            selection-background-color: #3b82f6;
        }

        /* スピンボックスのボタン */
        QSpinBox::up-button, QSpinBox::down-button,
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
            background-color: #374151;
            border: none;
            width: 20px;
        }
        QSpinBox::up-button:hover, QSpinBox::down-button:hover,
        QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
            background-color: #4b5563;
        }

        /* 通常のボタン */
        QPushButton {
            background-color: #374151;
            border: 1px solid #4b5563;
            border-radius: 6px;
            padding: 8px 16px;
            color: #f3f4f6;
        }
        QPushButton:hover {
            background-color: #4b5563;
        }
        QPushButton:pressed {
            background-color: #1f2937;
        }

        /* チェックボックス */
        QCheckBox {
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 1px solid #4b5563;
            background-color: #111827;
        }
        QCheckBox::indicator:checked {
            background-color: #3b82f6;
            border-color: #3b82f6;
        }

        /* スプリッター */
        QSplitter::handle {
            background-color: #374151;
        }
        QSplitter::handle:vertical {
            height: 4px;
        }

        /* スクロールバー */
        QScrollBar:vertical {
            background-color: #111827;
            width: 12px;
            border-radius: 6px;
        }
        QScrollBar::handle:vertical {
            background-color: #4b5563;
            border-radius: 6px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #6b7280;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }

        /* ラベル */
        QLabel {
            color: #d1d5db;
        }
    """)

    # メインウィンドウ作成・表示
    window = MainWindow()
    window.show()

    # イベントループ開始
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
