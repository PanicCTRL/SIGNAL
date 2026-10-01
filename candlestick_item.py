"""
candlestick_item.py — Графический элемент японских свечей для pyqtgraph.
Монохромная палитра в строгом стиле STRG / QUIK:
- Растущие (Up) свечи: светлое тело (#c0c0c0), контур (#cccccc)
- Падающие (Down) свечи: темное полое тело в цвет фона (#111111), контур (#555555)
- Косметические фитили 1px (setCosmetic) для четкости при любом зуме
"""

import pyqtgraph as pg
from PyQt6 import QtCore, QtGui


class CandlestickItem(pg.GraphicsObject):
    """
    Кастомный графический элемент для быстрого рендеринга японских свечей.
    data: список кортежей вида (x_index, open, close, low, high)
    """

    # Цветовая палитра STRG (строгий классический QUIK)
    UP_BODY_COLOR     = QtGui.QColor('#c0c0c0')  # Светлое тело растущей свечи
    UP_BORDER_COLOR   = QtGui.QColor('#cccccc')  # Светлая рамка
    UP_WICK_COLOR     = QtGui.QColor('#888888')  # Фитиль растущей свечи

    DOWN_BODY_COLOR   = QtGui.QColor('#111111')  # Темная заливка в цвет фона
    DOWN_BORDER_COLOR = QtGui.QColor('#555555')  # Тонкая серая рамка
    DOWN_WICK_COLOR   = QtGui.QColor('#666666')  # Фитиль падающей свечи

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
        """Запекание всех свечей в QPicture для сверхбыстрого рендеринга."""
        self.picture = QtGui.QPicture()
        p = QtGui.QPainter(self.picture)

        body_width = 0.35  # Половина ширины тела свечи

        # Настройка перьев (косметические 1px - не искажаются при зуме)
        pen_wick_up = pg.mkPen(color=self.UP_WICK_COLOR, width=1.0)
        pen_wick_up.setCosmetic(True)

        pen_wick_down = pg.mkPen(color=self.DOWN_WICK_COLOR, width=1.0)
        pen_wick_down.setCosmetic(True)

        pen_body_up = pg.mkPen(color=self.UP_BORDER_COLOR, width=1.0)
        pen_body_up.setCosmetic(True)
        brush_body_up = pg.mkBrush(self.UP_BODY_COLOR)

        pen_body_down = pg.mkPen(color=self.DOWN_BORDER_COLOR, width=1.0)
        pen_body_down.setCosmetic(True)
        brush_body_down = pg.mkBrush(self.DOWN_BODY_COLOR)

        for item in self.data:
            x, o, c, l, h = item
            is_up = (c >= o)

            # 1. Фитиль (рисуем первым от Low до High)
            p.setPen(pen_wick_up if is_up else pen_wick_down)
            p.drawLine(QtCore.QPointF(x, l), QtCore.QPointF(x, h))

            # 2. Тело свечи (рисуем вторым поверх фитиля)
            p.setPen(pen_body_up if is_up else pen_body_down)
            p.setBrush(brush_body_up if is_up else brush_body_down)

            top = max(o, c)
            bottom = min(o, c)
            height = top - bottom

            if height < 0.5:
                # Плоская свеча / Доджи — рисуем тонкую поперечную черточку
                p.drawLine(QtCore.QPointF(x - body_width, o), QtCore.QPointF(x + body_width, o))
            else:
                p.drawRect(QtCore.QRectF(x - body_width, bottom, body_width * 2, height))

        p.end()

    def paint(self, p, *args):
        """Мгновенная отрисовка векторного метафайла."""
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        """Границы элемента для масштабирования ViewBox."""
        return QtCore.QRectF(self.picture.boundingRect())
