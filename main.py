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


# ============================================
# 1インスタンス化 (Windows専用)
# ============================================
MUTEX_NAME = "Global\\ChatGPT-Windows-SingleInstance"
WINDOW_TITLE = "ChatGPT Desktop"


def _acquire_single_instance_mutex():
    """
    Named Mutex を取得して1インスタンス化を実現する (Windows専用)

    Returns:
        mutex ハンドル（成功時）、None（既に起動中 or 非Windows）
    """
    if sys.platform != "win32":
        return "non-windows"  # 非Windowsは常に成功扱い

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32

    # CreateMutexW(lpMutexAttributes, bInitialOwner, lpName)
    mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    if not mutex:
        return None  # 失敗時は従来通り起動

    # ERROR_ALREADY_EXISTS = 183
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(mutex)
        return None  # 既に起動中

    return mutex


def _activate_existing_window():
    """
    既存のウィンドウを探して前面に出す (Windows専用)
    hidden ウィンドウは前面化しない（visible の場合のみ）
    """
    if sys.platform != "win32":
        return

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    # コールバック用の型定義
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    found_hwnd = None

    def enum_callback(hwnd, lparam):
        nonlocal found_hwnd
        # ウィンドウタイトルを取得
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            if buffer.value == WINDOW_TITLE:
                found_hwnd = hwnd
                return False  # 列挙を停止
        return True  # 列挙を続行

    try:
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

        if found_hwnd:
            # visible の場合のみ前面化（hidden は無視）
            if user32.IsWindowVisible(found_hwnd):
                user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(found_hwnd)
    except Exception:
        pass  # 失敗しても黙って終了


def main():
    """アプリケーションのエントリーポイント"""

    # 1インスタンス化: Mutex取得を試みる
    mutex = _acquire_single_instance_mutex()
    if mutex is None:
        # 既に起動中: 既存ウィンドウを前面に出して終了
        _activate_existing_window()
        sys.exit(0)

    # コマンドライン引数解析
    hidden = '--hidden' in sys.argv

    # High DPI対応
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # アプリケーション作成（--hiddenを除外して渡す）
    qt_args = [arg for arg in sys.argv if arg != '--hidden']
    app = QApplication(qt_args)

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

    # メインウィンドウ作成
    window = MainWindow()

    # --hidden オプションがなければウィンドウを表示
    if not hidden:
        window.show()

    # イベントループ開始
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
