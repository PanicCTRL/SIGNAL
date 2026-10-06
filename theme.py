"""
theme.py — Визуальная тема проекта SIGNAL в строгом стиле QUIK / STRG.
Прямоугольные кнопки (border-radius: 0px), тонкие рамки 1px, системный шрифт Tahoma (11px).
"""

# ============================================================
# 1. ЦВЕТОВАЯ ПАЛИТРА
# ============================================================
CHART_BG          = "#111111"  # Фон графика (строгий темный графит)
CHART_GRID        = "#202020"  # Сетка
CHART_AXIS_TEXT   = "#777777"  # Текст на осях

# Свечи (монохромная палитра QUIK / STRG)
CANDLE_UP_BODY    = "#c0c0c0"  # Растущая свеча
CANDLE_DOWN_BODY  = "#111111"  # Падающая свеча (полое темное тело)
CANDLE_WICK_UP    = "#888888"  # Фитиль растущей свечи
CANDLE_WICK_DOWN  = "#666666"  # Фитиль падающей свечи

# Индикаторы
CURRENT_PRICE     = "#c9b037"  # Золотистая линия текущей цены
# Регрессионный тренд и канал (TradingView Style как в STRG)
REGRESSION_TW_BLUE       = "#2962ff"  # Ярко-синяя верхняя граница (TradingView blue)
REGRESSION_TW_RED        = "#ef5350"  # Насыщенно-красная нижняя граница (TradingView red)
REGRESSION_TW_MID        = "#ef5350"  # Пунктирная центральная линия регрессии (МНК)
REGRESSION_TW_BLUE_FILL  = (41, 98, 255, 45)  # Полупрозрачная синяя заливка верхней половины (TW)
REGRESSION_TW_RED_FILL   = (239, 83, 80, 45)  # Полупрозрачная красная заливка нижней половины (TW)

# ============================================================
# 2. ТАБЛИЦА СТИЛЕЙ QT (QSS)
# ============================================================
GLOBAL_STYLESHEET = """
/* Главное окно и базовые шрифты */
QMainWindow {
    background-color: #111111;
}
QWidget {
    color: #b5b5b5;
    font-family: 'Tahoma', 'Segoe UI', Arial, sans-serif;
    font-size: 11px;
}

/* Меню */
QMenuBar {
    background-color: #181818;
    color: #cccccc;
    border-bottom: 1px solid #282828;
    padding: 1px;
    font-size: 11px;
}
QMenuBar::item {
    background: transparent;
    padding: 3px 8px;
    border-radius: 0px;
}
QMenuBar::item:selected {
    background-color: #242424;
    color: #ffffff;
}
QMenu {
    background-color: #181818;
    color: #cccccc;
    border: 1px solid #333333;
    padding: 2px 0px;
}
QMenu::item {
    padding: 4px 20px 4px 15px;
}
QMenu::item:selected {
    background-color: #173650;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #2a2a2a;
    margin: 3px 5px;
}

/* Строка состояния */
QStatusBar {
    background-color: #161616;
    color: #888888;
    border-top: 1px solid #252525;
    font-size: 10.5px;
    min-height: 20px;
}

/* Панель плеера */
QFrame#ReplayerPanel {
    background-color: #161616;
    border: 1px solid #282828;
    border-radius: 0px;
}

/* Общий стиль кнопок — строго 0px */
QPushButton {
    border-radius: 0px;
    font-family: 'Tahoma', 'Segoe UI', Arial, sans-serif;
    font-size: 11px;
}

/* Кнопки плеера */
QPushButton.ReplayBtn {
    background-color: #1e1e1e;
    color: #cccccc;
    border: 1px solid #333333;
    border-radius: 0px;
    padding: 2px 5px;
    font-size: 11px;
    font-weight: bold;
    min-height: 20px;
}
QPushButton.ReplayBtn:hover {
    background-color: #2a2a2a;
    border-color: #444444;
    color: #ffffff;
}
QPushButton.ReplayBtn:checked {
    background-color: #173650;
    border-color: #2a629a;
    color: #ffffff;
}

/* Слайдер-скруббер времени */
QSlider::groove:horizontal {
    height: 4px;
    background: #222222;
    border: 1px solid #303030;
    border-radius: 0px;
}
QSlider::sub-page:horizontal {
    background: #6e5812;
}
QSlider::handle:horizontal {
    background: #c9b037;
    border: 1px solid #f1c40f;
    width: 10px;
    margin-top: -6px;
    margin-bottom: -6px;
    border-radius: 0px;
}
QSlider::handle:horizontal:hover {
    background: #ffd700;
}
"""
