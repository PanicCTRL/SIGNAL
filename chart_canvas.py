"""
chart_canvas.py — Графический холст проекта SIGNAL
Двухпанельный график на базе PyQt6 и pyqtgraph:
- Верхняя панель (plot_candles): свечи, регрессионные каналы, уровни.
- Нижняя панель (plot_macd): индикатор MACD, волны гистограммы, нулевая линия.
- Оси X панелей синхронизированы (setXLink).
- Нижняя шкала времени форматирует индексы свечей в реальное время (ЧЧ:ММ).
"""

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPen
from candlestick_item import CandlestickItem

# Глобальные настройки pyqtgraph: тёмная палитра и сглаживание
pg.setConfigOption('background', '#111111')   # Глубокий тёмно-серый фон графика
pg.setConfigOption('foreground', '#d1d4dc')   # Светло-серый цвет осей и текста шкалы
pg.setConfigOptions(antialias=True)          # Сглаживание тонких линий


class TimeAxisItem(pg.AxisItem):
    """
    Кастомная ось времени: преобразует порядковый индекс свечи (0, 1, 2...)
    в отображаемое время свечи (например, "10:30").
    Это исключает разрывы на графике во время ночного клиринга и выходных.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.time_labels = []

    def set_labels(self, labels):
        self.time_labels = labels
        self.picture = None
        self.update()

    def tickStrings(self, values, scale, spacing):
        strings = []
        n = len(self.time_labels)
        for val in values:
            # Отсекаем дробные засечки между целыми свечами
            if abs(val - round(val)) > 0.05:
                strings.append("")
                continue
            idx = int(round(val))
            if 0 <= idx < n:
                strings.append(self.time_labels[idx])
            else:
                strings.append("")
        return strings


class ChartCanvas(pg.GraphicsLayoutWidget):
    """
    Класс холста с двумя синхронизированными графиками.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. Настройка сетки холста (Layout)
        # Строка 0 (свечи) получает 70% высоты, строка 1 (MACD) — 30%
        self.ci.layout.setRowStretchFactor(0, 7)
        self.ci.layout.setRowStretchFactor(1, 3)
        self.ci.layout.setSpacing(2)  # Минимальный зазор между графиками в пикселях

        # 2. Верхняя панель: График цены и трендов
        self.plot_candles = self.addPlot(row=0, col=0)
        self.plot_candles.showGrid(x=True, y=True, alpha=0.15)  # Сетка графика
        self.plot_candles.setClipToView(True)                   # Оптимизация: рендерить только то, что в кадре
        self.plot_candles.getAxis('left').setWidth(75)          # Фиксированная ширина ценовой шкалы
        self.plot_candles.hideAxis('bottom')                    # Скрываем нижнюю ось времени у свечей

        # Добавляем векторный элемент отрисовки японских свечей
        self.candles_item = CandlestickItem()
        self.plot_candles.addItem(self.candles_item)

        # 3. Нижняя панель: Осциллятор MACD с кастомной шкалой времени
        self.time_axis = TimeAxisItem(orientation='bottom')
        self.plot_macd = self.addPlot(row=1, col=0, axisItems={'bottom': self.time_axis})
        self.plot_macd.showGrid(x=True, y=True, alpha=0.15)     # Сетка индикатора
        self.plot_macd.setClipToView(True)
        self.plot_macd.getAxis('left').setWidth(75)             # Выравниваем шкалу строго под шкалой свечей

        # 4. Намертво сцепляем ось времени X нижнего графика с верхним
        self.plot_macd.setXLink(self.plot_candles)

        # 5. Нулевая линия на графике MACD (уровень раздела холмов и впадин)
        zero_pen = pg.mkPen(color='#555555', width=1, style=Qt.PenStyle.DashLine)
        self.macd_zero_line = pg.InfiniteLine(pos=0.0, angle=0, pen=zero_pen)
        self.plot_macd.addItem(self.macd_zero_line)

    def set_candles(self, candles):
        """
        Загрузить и отобразить массив свечей на верхнем графике.
        candles: список словарей [{'date': ..., 'time': ..., 'open': ..., 'high': ..., 'low': ..., 'close': ...}]
        """
        if not candles:
            self.clear_plots()
            return

        # Формируем данные для CandlestickItem: (x, open, close, low, high)
        candle_data = []
        time_labels = []

        for i, c in enumerate(candles):
            candle_data.append((i, c['open'], c['close'], c['low'], c['high']))
            # Время свечи без секунд (например, '10:30')
            t_str = c['time']
            time_labels.append(t_str[:5] if len(t_str) >= 5 else t_str)

        # Передаем метки времени в нижнюю ось
        self.time_axis.set_labels(time_labels)

        # Обновляем графический элемент свечей
        self.candles_item.set_data(candle_data)

        # Автомасштабирование по осям X и Y с небольшим отступом
        self.plot_candles.enableAutoRange()
        self.plot_candles.setXRange(-1, len(candles) + 1, padding=0.02)

    def clear_plots(self):
        """Очистить оба графика перед повторным расчетом или загрузкой нового дня."""
        self.candles_item.set_data([])
        self.time_axis.set_labels([])
        self.plot_macd.clear()
        self.plot_macd.addItem(self.macd_zero_line)  # Возвращаем нулевую линию обратно
