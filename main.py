"""
main.py — Главный модуль приложения SIGNAL с пошаговым плеером рынка (Replayer).
Поддерживает воспроизведение тиков, живое дыхание формирующейся свечи,
скруббинг по шкале времени, переключение скоростей (1x..MAX) и управление с клавиатуры.
"""

import sys
import os
import time
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QSlider, QLabel, QButtonGroup,
    QFileDialog, QMessageBox, QStatusBar, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence

from chart_canvas import ChartCanvas
from tick_loader import TickLoader
from zigzag_calculator import ZigzagCalculator
from regression_calculator import RegressionCalculator
from theme import GLOBAL_STYLESHEET


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIGNAL — Visualizer & Indicator Lab")
        self.resize(1350, 880)

        # 1. Инициализация движков
        self.loader = TickLoader()
        self.zigzag_calc = ZigzagCalculator()
        self.reg_calc = RegressionCalculator(price_step=25.0)

        # 2. Состояние воспроизведения
        self.is_playing = False
        self.current_tick_idx = 0
        self.speed_multiplier = 25
        self.replay_timer = QTimer(self)
        self.replay_timer.setInterval(35)  # ~30 FPS
        self.replay_timer.timeout.connect(self._on_replay_timer_tick)

        # 3. Компоновка интерфейса
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(4)

        # Холст графика (верхние свечи + нижний осциллятор)
        self.canvas = ChartCanvas()
        root_layout.addWidget(self.canvas, stretch=1)

        # Панель управления воспроизведением под графиком
        self.replayer_panel = self._create_replayer_panel()
        root_layout.addWidget(self.replayer_panel)

        # Строка состояния внизу окна
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Меню приложения
        self._init_menu()

        # Автоматическая загрузка самого свежего файла
        self._auto_load_latest()

    def _create_replayer_panel(self):
        """Панель управления воспроизведением рынка под графиком (в стиле STRG)."""
        panel = QFrame()
        panel.setObjectName("ReplayerPanel")
        panel.setFixedHeight(62)

        main_layout = QHBoxLayout(panel)
        main_layout.setContentsMargins(6, 4, 6, 4)
        main_layout.setSpacing(6)

        # 1. Сетка кнопок воспроизведения (2 ряда)
        btn_grid = QGridLayout()
        btn_grid.setContentsMargins(0, 0, 0, 0)
        btn_grid.setSpacing(3)

        # [ ⏹ В начало ] — занимает 2 ряда
        self.btn_reset = QPushButton("⏹ В начало")
        self.btn_reset.setProperty("class", "ReplayBtn")
        self.btn_reset.setFixedWidth(86)
        self.btn_reset.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.btn_reset.setToolTip("Перемотать в самое начало дня (на первый тик)")
        self.btn_reset.clicked.connect(self.reset_replay)
        btn_grid.addWidget(self.btn_reset, 0, 0, 2, 1)

        # Ряд 0: Шаг назад (тики с изменением цены)
        self.btn_step_back = QPushButton("⏮ Шаг")
        self.btn_step_back.setProperty("class", "ReplayBtn")
        self.btn_step_back.setToolTip("Шаг назад (к предыдущему изменению цены) [Стрелка Вниз]")
        self.btn_step_back.setFixedWidth(80)
        self.btn_step_back.clicked.connect(self.step_tick_backward)
        btn_grid.addWidget(self.btn_step_back, 0, 1)

        # Ряд 1: Свеча назад
        self.btn_candle_back = QPushButton("⏮ Свеча")
        self.btn_candle_back.setProperty("class", "ReplayBtn")
        self.btn_candle_back.setToolTip("Свеча назад (на 1 свечу М5) [Стрелка Влево]")
        self.btn_candle_back.setFixedWidth(80)
        self.btn_candle_back.clicked.connect(self.step_candle_backward)
        btn_grid.addWidget(self.btn_candle_back, 1, 1)

        # [ ▶ Старт ] — занимает 2 ряда
        self.btn_play = QPushButton("▶ Старт")
        self.btn_play.setProperty("class", "ReplayBtn")
        self.btn_play.setFixedWidth(80)
        self.btn_play.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.btn_play.setToolTip("Запуск / Пауза воспроизведения [Пробел]")
        self.btn_play.clicked.connect(self.toggle_play)
        btn_grid.addWidget(self.btn_play, 0, 2, 2, 1)

        # Ряд 0: Шаг вперед (тики с изменением цены)
        self.btn_step_fwd = QPushButton("⏭ Шаг")
        self.btn_step_fwd.setProperty("class", "ReplayBtn")
        self.btn_step_fwd.setToolTip("Шаг вперед (к следующему изменению цены) [Стрелка Вверх]")
        self.btn_step_fwd.setFixedWidth(80)
        self.btn_step_fwd.clicked.connect(self.step_tick_forward)
        btn_grid.addWidget(self.btn_step_fwd, 0, 3)

        # Ряд 1: Свеча вперед
        self.btn_candle_fwd = QPushButton("⏭ Свеча")
        self.btn_candle_fwd.setProperty("class", "ReplayBtn")
        self.btn_candle_fwd.setToolTip("Свеча вперед (на 1 свечу М5) [Стрелка Вправо]")
        self.btn_candle_fwd.setFixedWidth(80)
        self.btn_candle_fwd.clicked.connect(self.step_candle_forward)
        btn_grid.addWidget(self.btn_candle_fwd, 1, 3)

        # [ ⇥ Весь день ] — занимает 2 ряда
        self.btn_show_all = QPushButton("⇥ Весь день")
        self.btn_show_all.setProperty("class", "ReplayBtn")
        self.btn_show_all.setFixedWidth(86)
        self.btn_show_all.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.btn_show_all.setToolTip("Показать весь торговый день до конца со всеми свечами")
        self.btn_show_all.clicked.connect(self.show_all)
        btn_grid.addWidget(self.btn_show_all, 0, 4, 2, 1)

        main_layout.addLayout(btn_grid)

        # 2. Правая часть: Сверху слайдер-скруббер, снизу табло и скорости
        right_box = QVBoxLayout()
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(2)

        # Слайдер перемотки времени
        self.slider_time = QSlider(Qt.Orientation.Horizontal)
        self.slider_time.setMinimum(0)
        self.slider_time.setMaximum(100)
        self.slider_time.sliderMoved.connect(self.on_slider_moved)
        right_box.addWidget(self.slider_time)

        # Нижний ряд: цифровое табло + кнопки скоростей
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(6)

        # Табло времени
        self.lbl_replay_time = QLabel("00:00:00")
        self.lbl_replay_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_replay_time.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #d4b106; background: #1a1708; "
            "border: 1px solid #4a3e0f; padding: 2px 6px; min-width: 65px;"
        )
        bottom_row.addWidget(self.lbl_replay_time)

        # Табло цены
        self.lbl_replay_price = QLabel("0")
        self.lbl_replay_price.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_replay_price.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #e0e0e0; background: #202020; "
            "border: 1px solid #353535; padding: 2px 6px; min-width: 65px;"
        )
        bottom_row.addWidget(self.lbl_replay_price)

        bottom_row.addStretch()

        # Кнопки скоростей воспроизведения
        self.speed_group = QButtonGroup(self)
        self.speed_buttons = {}

        for spd_val, spd_label in [(1, "1x"), (5, "5x"), (25, "25x"), (100, "100x"), (1000, "MAX")]:
            btn = QPushButton(spd_label)
            btn.setCheckable(True)
            btn.setProperty("class", "ReplayBtn")
            btn.setFixedWidth(42)
            btn.clicked.connect(lambda checked, s=spd_val: self.set_speed(s))
            self.speed_group.addButton(btn)
            bottom_row.addWidget(btn)
            self.speed_buttons[spd_val] = btn

        self.speed_buttons[25].setChecked(True)
        right_box.addLayout(bottom_row)

        main_layout.addLayout(right_box, stretch=1)
        return panel

    def _init_menu(self):
        """Создание верхнего меню приложения."""
        menu = self.menuBar()

        file_menu = menu.addMenu("&Файл")

        open_action = QAction("📂 Открыть тики (Finam)...", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.setStatusTip("Выбрать файл тиков Финам для анализа")
        open_action.triggered.connect(self.choose_file_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

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
        """Загрузка файла, настройка шкалы времени и старт воспроизведения с начала дня."""
        file_name = os.path.basename(file_path)
        self.status_bar.showMessage(f"Чтение и парсинг {file_name}...")
        self.pause_replay()

        start_time = time.time()
        try:
            candles = self.loader.load_file(file_path, output_dir="Y:/SIGNAL", period_sec=300)
            elapsed = time.time() - start_time

            if not candles or self.loader.get_num_ticks() == 0:
                QMessageBox.warning(self, "Внимание", f"Файл {file_name} не содержит корректных тиковых данных!")
                self.status_bar.showMessage(f"Ошибка чтения {file_name}")
                return

            n_ticks = self.loader.get_num_ticks()
            self.slider_time.blockSignals(True)
            self.slider_time.setMaximum(n_ticks - 1)
            self.slider_time.setValue(0)
            self.slider_time.blockSignals(False)

            self.current_tick_idx = 0

            # Устанавливаем стабильную шкалу времени на весь день
            self.canvas.set_full_timeline(candles)

            # Отрисовываем начальный кадр (первый тик дня) с автомасштабированием
            self.render_current_frame(auto_range=True)

            count = len(candles)
            date_str = candles[0].get("date", "")
            first_time = candles[0].get("time", "")
            last_time = candles[-1].get("time", "")

            self.setWindowTitle(
                f"SIGNAL — [{file_name} | {count} свечей M5 ({first_time[:5]} - {last_time[:5]}) | {n_ticks:,} тиков]"
            )
            self.status_bar.showMessage(
                f"Загружено: {file_name} | Свечей: {count} | Тиков: {n_ticks:,} | {date_str} | Загрузка: {elapsed:.3f}с"
            )

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось разобрать файл:\n{str(e)}")
            self.status_bar.showMessage("Ошибка обработки файла")

    def render_current_frame(self, auto_range=False):
        """Отрисовывает состояние рынка в момент self.current_tick_idx с дышащей свечой."""
        if self.loader.get_num_ticks() == 0:
            return

        curr_time, curr_price, visible_candles, candle_idx = self.loader.get_visible_frame(self.current_tick_idx)
        if curr_time is None or not visible_candles:
            return

        # Обновление цифрового табло
        self.lbl_replay_time.setText(curr_time.strftime("%H:%M:%S"))
        self.lbl_replay_price.setText(f"{int(curr_price):,} ".replace(",", " "))

        # Отрисовка свечей и бегающей линии цены
        self.canvas.render_frame(visible_candles, current_price=curr_price, auto_range=auto_range)

        # Динамический пересчет ЗигЗага и Регрессии
        if len(visible_candles) >= 2:
            pivots = self.zigzag_calc.calculate_zigzag(visible_candles, dev_percent=0.9)
            self.canvas.render_zigzag(pivots)

            # Канал линейной регрессии строится строго по закрытым свечам, исключая текущую формирующуюся (дышащую)
            last_wave = self.zigzag_calc.last_line
            channel = None
            if last_wave and "start_bar" in last_wave and "end_bar" in last_wave and len(visible_candles) >= 3:
                closed_candles = visible_candles[:-1] if len(visible_candles) > 1 else visible_candles
                closed_end_bar = min(int(last_wave["end_bar"]), len(closed_candles))
                start_bar = int(last_wave["start_bar"])

                if closed_end_bar - start_bar + 1 >= 3:
                    channel = self.reg_calc.calculate_channel(
                        closed_candles,
                        start_bar=start_bar,
                        end_bar=closed_end_bar,
                        k=2.0
                    )
            self.canvas.render_regression_channel(channel)
        else:
            self.canvas.render_zigzag([])
            self.canvas.render_regression_channel(None)

    # ============================================================
    # Управление плеером
    # ============================================================
    def toggle_play(self):
        if self.is_playing:
            self.pause_replay()
        else:
            self.start_replay()

    def start_replay(self):
        n_ticks = self.loader.get_num_ticks()
        if n_ticks == 0:
            return
        if self.current_tick_idx >= n_ticks - 1:
            self.current_tick_idx = 0
        self.is_playing = True
        self.btn_play.setText("⏸ Пауза")
        self.btn_play.setStyleSheet("background-color: #332014; color: #e67e22; border: 1px solid #7d4414;")
        self.replay_timer.start()

    def pause_replay(self):
        self.is_playing = False
        self.btn_play.setText("▶ Старт")
        self.btn_play.setStyleSheet("")
        self.replay_timer.stop()

    def step_tick_forward(self):
        """Шаг вперед к следующему тику с изменением цены."""
        self.pause_replay()
        self.current_tick_idx = self.loader.get_next_price_change_tick(self.current_tick_idx)
        self.slider_time.blockSignals(True)
        self.slider_time.setValue(self.current_tick_idx)
        self.slider_time.blockSignals(False)
        self.render_current_frame(auto_range=False)

    def step_tick_backward(self):
        """Шаг назад к предыдущему тику с изменением цены."""
        self.pause_replay()
        self.current_tick_idx = self.loader.get_prev_price_change_tick(self.current_tick_idx)
        self.slider_time.blockSignals(True)
        self.slider_time.setValue(self.current_tick_idx)
        self.slider_time.blockSignals(False)
        self.render_current_frame(auto_range=False)

    def step_candle_forward(self):
        """Шаг вперед на 1 свечу М5."""
        self.pause_replay()
        self.current_tick_idx = self.loader.get_next_candle_tick(self.current_tick_idx)
        self.slider_time.blockSignals(True)
        self.slider_time.setValue(self.current_tick_idx)
        self.slider_time.blockSignals(False)
        self.render_current_frame(auto_range=False)

    def step_candle_backward(self):
        """Шаг назад на 1 свечу М5."""
        self.pause_replay()
        self.current_tick_idx = self.loader.get_prev_candle_tick(self.current_tick_idx)
        self.slider_time.blockSignals(True)
        self.slider_time.setValue(self.current_tick_idx)
        self.slider_time.blockSignals(False)
        self.render_current_frame(auto_range=False)

    def reset_replay(self):
        """Сброс в самое начало дня."""
        self.pause_replay()
        self.current_tick_idx = 0
        self.slider_time.blockSignals(True)
        self.slider_time.setValue(0)
        self.slider_time.blockSignals(False)
        self.render_current_frame(auto_range=False)

    def show_all(self):
        """Перемотка в конец дня со всеми свечами и сбросом масштаба."""
        self.pause_replay()
        n_ticks = self.loader.get_num_ticks()
        if n_ticks == 0:
            return
        self.current_tick_idx = n_ticks - 1
        self.slider_time.blockSignals(True)
        self.slider_time.setValue(self.current_tick_idx)
        self.slider_time.blockSignals(False)
        self.render_current_frame(auto_range=True)
        self.status_bar.showMessage("Показан весь торговый день (финишное состояние)")

    def set_speed(self, speed_val):
        self.speed_multiplier = speed_val

    def on_slider_moved(self, val):
        self.current_tick_idx = val
        self.render_current_frame(auto_range=False)

    def _on_replay_timer_tick(self):
        # Шаг тиков за кадр в зависимости от выбранной скорости
        if self.speed_multiplier == 1:
            step = 1
        elif self.speed_multiplier == 5:
            step = 6
        elif self.speed_multiplier == 25:
            step = 35
        elif self.speed_multiplier == 100:
            step = 160
        else:  # MAX
            step = 700

        n_ticks = self.loader.get_num_ticks()
        self.current_tick_idx += step

        if self.current_tick_idx >= n_ticks - 1:
            self.current_tick_idx = n_ticks - 1
            self.pause_replay()

        self.slider_time.blockSignals(True)
        self.slider_time.setValue(self.current_tick_idx)
        self.slider_time.blockSignals(False)

        self.render_current_frame(auto_range=False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.toggle_play()
        elif event.key() == Qt.Key.Key_Left:
            self.step_candle_backward()
        elif event.key() == Qt.Key.Key_Right:
            self.step_candle_forward()
        elif event.key() == Qt.Key.Key_Down:
            self.step_tick_backward()
        elif event.key() == Qt.Key.Key_Up:
            self.step_tick_forward()
        else:
            super().keyPressEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(GLOBAL_STYLESHEET)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
