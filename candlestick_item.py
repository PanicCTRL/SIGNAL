"""
candlestick_item.py — Высокоскоростной графический элемент японских свечей для pyqtgraph.
Использует QPicture для запекания всех свечей в один векторный вызов отрисовки (60+ FPS).
"""

import pyqtgraph as pg
from PyQt6 import QtCore, QtGui


class CandlestickItem(pg.GraphicsObject):
    """
    Кастомный графический элемент для быстрого рендеринга японских свечей.
    data: список кортежей вида (x_index, open, close, low, high)
    """
    def __init__(self, data=None):
        super().__init__()
        self.data = data or []
        self.picture = QtGui.QPicture()
        if self.data:
            self.generate_picture()

    def set_data(self, data):
        """Обновить данные свечей и перерисовать кэш."""
        self.data = data
        self.generate_picture()
        self.update()

    def generate_picture(self):
        """Запекание всех свечей в QPicture."""
        self.picture = QtGui.QPicture()
        p = QtGui.QPainter(self.picture)

        # Цвета TradingView
        bull_color = QtGui.QColor('#26a69a')  # Зеленый (бычья)
        bear_color = QtGui.QColor('#ef5350')  # Красный (медвежья)

        pen_bull = pg.mkPen(color=bull_color, width=1.5)
        pen_bear = pg.mkPen(color=bear_color, width=1.5)
        brush_bull = pg.mkBrush(bull_color)
        brush_bear = pg.mkBrush(bear_color)

        body_width = 0.35  # Половина ширины тела свечи

        for item in self.data:
            x, o, c, l, h = item

            if c >= o:
                p.setPen(pen_bull)
                p.setBrush(brush_bull)
            else:
                p.setPen(pen_bear)
                p.setBrush(brush_bear)

            # 1. Фитиль свечи (вертикальная линия от Low до High)
            p.drawLine(QtCore.QPointF(x, l), QtCore.QPointF(x, h))

            # 2. Тело свечи (прямоугольник от Open до Close)
            top = max(o, c)
            bottom = min(o, c)
            height = top - bottom

            # Если свеча плоская (доджи, open == close), делаем минимальную высоту 1.0 пункт
            if height < 0.5:
                height = 1.0
                bottom = o - 0.5

            p.drawRect(QtCore.QRectF(x - body_width, bottom, body_width * 2, height))

        p.end()

    def paint(self, p, *args):
        """Мгновенная отрисовка готовой векторной картинки на холсте."""
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        """Границы элемента для автоматического масштабирования графика."""
        return QtCore.QRectF(self.picture.boundingRect())
