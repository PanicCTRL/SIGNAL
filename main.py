"""
main.py — Главный модуль приложения SIGNAL.
Автоматически находит самый свежий файл тиков, вызывает Lua-парсер
и отображает свечи на холсте. Позволяет выбрать любой другой файл через меню.
"""

import sys
import os
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QStatusBar
)
from PyQt6.QtGui import QAction, QKeySequence
from chart_canvas import ChartCanvas
from tick_loader import TickLoader


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIGNAL — Visualizer & Indicator Lab")
        self.resize(1300, 850)

        # 1. Инициализация Lua-загрузчика тиков
        self.loader = TickLoader()

        # 2. Создание двухпанельного холста
        self.canvas = ChartCanvas()
        self.setCentralWidget(self.canvas)

        # 3. Строка состояния внизу окна
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 4. Меню приложения
        self._init_menu()

        # 5. Автоматическая загрузка самого свежего файла при старте
        self._auto_load_latest()

    def _init_menu(self):
        """Создание верхнего меню приложения."""
        menu = self.menuBar()

        # Меню "Файл"
        file_menu = menu.addMenu("&Файл")

        # Действие "Открыть тики..." (Ctrl+O)
        open_action = QAction("📂 Открыть тики (Finam)...", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.setStatusTip("Выбрать файл тиков Финам для анализа")
        open_action.triggered.connect(self.choose_file_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        # Действие "Выход"
        exit_action = QAction("Выход", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _auto_load_latest(self):
        """Поиск и автоматическая загрузка самого свежего файла тиков."""
        latest_file = TickLoader.find_latest_file(preferred_dir=".")
        if latest_file and os.path.exists(latest_file):
            self.load_file(latest_file)
        else:
            self.status_bar.showMessage("Тиковые файлы не найдены. Откройте файл через меню Файл (Ctrl+O).")

    def choose_file_dialog(self):
        """Диалоговое окно выбора файла пользователем."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл тиков Финам",
            os.path.abspath("."),
            "Текстовые файлы (*.txt);;Все файлы (*.*)"
        )
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path):
        """Парсинг тиков через Lua и отрисовка свечей на графике."""
        file_name = os.path.basename(file_path)
        self.status_bar.showMessage(f"Чтение и парсинг {file_name}...")

        start_time = time.time()
        try:
            # Вызываем Lua-скрипт прямо в оперативной памяти Python
            candles = self.loader.parse(file_path, output_dir="Y:/SIGNAL", period_sec=300)
            elapsed = time.time() - start_time

            if not candles:
                QMessageBox.warning(self, "Внимание", f"Файл {file_name} не содержит корректных тиковых данных!")
                self.status_bar.showMessage(f"Ошибка чтения {file_name}")
                return

            # Передаем свечи на холст
            self.canvas.set_candles(candles)

            # Обновляем заголовок окна и статус-бар
            count = len(candles)
            date_str = candles[0].get("date", "")
            first_time = candles[0].get("time", "")
            last_time = candles[-1].get("time", "")

            self.setWindowTitle(
                f"SIGNAL — [{file_name} | {count} свечей M5 | {first_time[:5]} - {last_time[:5]}]"
            )
            self.status_bar.showMessage(
                f"Загружено: {file_name} | Свечей: {count} | Дата: {date_str} | Время обработки Lua: {elapsed:.3f} сек."
            )

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось разобрать файл:\n{str(e)}")
            self.status_bar.showMessage("Ошибка обработки файла")


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
