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
from PyQt6.QtGui import QColor, QPen, QFont
from candlestick_item import CandlestickItem
import theme

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

        # 6. Линия текущей цены (золотистый луч в стиле QUIK / STRG)
        pen_cur_price = pg.mkPen(color='#c9b037', width=1, style=Qt.PenStyle.SolidLine)
        pen_cur_price.setCosmetic(True)
        self.current_price_line = pg.InfiniteLine(pos=0, angle=0, pen=pen_cur_price)
        self.current_price_line.setVisible(False)
        self.plot_candles.addItem(self.current_price_line)

        # Текстовая плашка цены на правом краю
        self.price_label = pg.TextItem(
            text="", anchor=(0.0, 0.5), color="#111111",
            fill=pg.mkBrush("#c9b037")
        )
        self.price_label.setFont(QFont("Tahoma", 8, QFont.Weight.Bold))
        self.price_label.setVisible(False)
        self.plot_candles.addItem(self.price_label)

        # 7. Хранилище графических элементов первой линии ЗигЗага
        self.zigzag_items = []

        # 8. Хранилище графических элементов канала регрессии
        self.regression_items = []

        self.full_candles_count = 0
        self.last_channel = None

        # Динамическое продление регрессии до края вьюпорта при скролле и зуме
        self.plot_candles.getViewBox().sigRangeChanged.connect(self._on_view_range_changed)

    def _on_view_range_changed(self):
        if self.last_channel and self.regression_items:
            self.render_regression_channel(self.last_channel)

    def set_full_timeline(self, candles):
        """
        Установить фиксированную разметку нижней оси времени на весь день.
        Это предотвращает скачки меток времени при пошаговом воспроизведении.
        """
        if not candles:
            return
        time_labels = []
        all_lows = []
        all_highs = []
        for c in candles:
            t_str = c.get('time', '')
            time_labels.append(t_str[:5] if len(t_str) >= 5 else t_str)
            all_lows.append(c['low'])
            all_highs.append(c['high'])
        self.time_axis.set_labels(time_labels)
        self.full_candles_count = len(candles)
        self.full_min_price = min(all_lows) if all_lows else 0.0
        self.full_max_price = max(all_highs) if all_highs else 0.0

    def render_frame(self, candles, current_price=None, auto_range=False):
        """
        Отображает текущий срез свечей с честным живым морфингом крайней свечи.
        candles: срез словарей свечей
        current_price: float последняя цена тика
        """
        if not candles:
            self.candles_item.set_data([])
            self.current_price_line.setVisible(False)
            self.price_label.setVisible(False)
            return

        candle_data = [
            (i, c['open'], c['close'], c['low'], c['high'])
            for i, c in enumerate(candles)
        ]
        self.candles_item.set_data(candle_data)

        # Обновление линии текущей цены
        n = len(candles)
        p_val = current_price if current_price is not None else candles[-1]['close']
        self.current_price_line.setVisible(True)
        self.price_label.setVisible(True)
        self.current_price_line.setValue(p_val)
        self.price_label.setText(f" {int(p_val):,} ".replace(",", " "))
        self.price_label.setPos(n + 0.3, p_val)

        if auto_range:
            min_p = getattr(self, 'full_min_price', min(c['low'] for c in candles))
            max_p = getattr(self, 'full_max_price', max(c['high'] for c in candles))
            pad = (max_p - min_p) * 0.08
            if pad == 0:
                pad = 100
            total_n = max(self.full_candles_count, n)
            self.plot_candles.setXRange(-2, total_n + 3, padding=0.01)
            self.plot_candles.setYRange(min_p - pad, max_p + pad, padding=0.01)

    def set_candles(self, candles):
        """
        Загрузить и отобразить массив свечей на верхнем графике на весь день.
        """
        if not candles:
            self.clear_plots()
            return
        self.set_full_timeline(candles)
        self.render_frame(candles, auto_range=True)

    def render_zigzag(self, pivots):
        """
        Отрисовать опорную линию ЗигЗага:
        - Линия небесно-голубого цвета (#00e5ff, 2.5px)
        - Круглые маркеры на вершине (зеленый) и впадине (красный)
        - Плашки цен с цифрами
        """
        for item in self.zigzag_items:
            self.plot_candles.removeItem(item)
        self.zigzag_items.clear()

        if not pivots or len(pivots) < 2:
            return

        x_coords = [float(p["bar_idx"]) for p in pivots]
        y_coords = [float(p["price"]) for p in pivots]

        pen_zigzag = pg.mkPen(color='#00e5ff', width=2.5)
        curve = pg.PlotCurveItem(x=x_coords, y=y_coords, pen=pen_zigzag)
        self.plot_candles.addItem(curve)
        self.zigzag_items.append(curve)

        for p in pivots:
            bx = float(p["bar_idx"])
            py = float(p["price"])
            is_high = (p["type"] == "HIGH")
            dot_color = '#00e676' if is_high else '#ff1744'

            # Круглый маркер вершины/впадины
            sp_dot = pg.ScatterPlotItem(
                x=[bx], y=[py], symbol='o', size=9,
                pen=pg.mkPen(color='#111111', width=1.5),
                brush=pg.mkBrush(dot_color)
            )
            self.plot_candles.addItem(sp_dot)
            self.zigzag_items.append(sp_dot)

            # Текстовая плашка цены над вершиной / под низиной
            badge = pg.TextItem(
                text=f" {int(py):,} ".replace(",", " "),
                color='#ffffff',
                fill=pg.mkBrush(dot_color if is_high else '#b71c1c'),
                anchor=(0.5, 1.4 if is_high else -0.4)
            )
            badge.setFont(QFont("Tahoma", 8, QFont.Weight.Bold))
            badge.setPos(bx, py)
            self.plot_candles.addItem(badge)
            self.zigzag_items.append(badge)

    def render_regression_channel(self, ch):
        """
        Отрисовать канал линейной регрессии в стиле TradingView / STRG:
        - Линии продолжаются вправо до бесконечности (до правого края холста / вьюпорта)
        - Верхняя граница (Upper): яркая синяя (#2962ff, 1.8px)
        - Нижняя граница (Lower): насыщенная красная (#ef5350, 1.8px)
        - Центральная линия (Mid): пунктирная красная (#ef5350, 1.5px, DashLine)
        - Двухцветная заливка TradingView:
            * Верхняя половина (Mid -> Upper): синяя полупрозрачная (41, 98, 255, 45)
            * Нижняя половина (Lower -> Mid): красная полупрозрачная (239, 83, 80, 45)
        - Точки на финише базовой волны (круглые синяя и красная, квадратная центральная)
        - Информационная плашка параметров тренда (наклон, r, R2)
        """
        for item in self.regression_items:
            self.plot_candles.removeItem(item)
        self.regression_items.clear()

        self.last_channel = ch
        if not ch:
            return

        pi = self.plot_candles
        vb = pi.getViewBox()

        # Вычисляем правый край вьюпорта (с запасом 200 баров), чтобы линии уходили строго за край экрана
        right_bound = vb.viewRange()[0][1] if vb else ch.get("x_inf", [0, 500])[1]
        x_end = max(float(ch.get("x_inf", [0, 500])[1]), float(right_bound) + 200.0)

        x_start = float(ch["x"][0])
        slope = float(ch["slope"])
        intercept = float(ch["intercept"])
        se = float(ch["std_error"])
        k = float(ch["k"])

        x_bars_end = x_end - x_start + 1
        inf_mid = slope * x_bars_end + intercept
        inf_up = inf_mid + k * se
        inf_dn = inf_mid - k * se

        # Округление до биржевого шага цены 25 пт
        inf_mid_round = round(inf_mid / 25.0) * 25.0
        inf_up_round = round(inf_up / 25.0) * 25.0
        inf_dn_round = round(inf_dn / 25.0) * 25.0

        x_coords = [x_start, x_end]
        y_mid = [float(ch["y_mid"][0]), inf_mid_round]
        y_up = [float(ch["y_upper"][0]), inf_up_round]
        y_dn = [float(ch["y_lower"][0]), inf_dn_round]

        # 1. Линии канала (в палитре STRG / TradingView)
        pen_up = pg.mkPen(color=theme.REGRESSION_TW_BLUE, width=1.8)
        pen_up.setCosmetic(True)

        pen_dn = pg.mkPen(color=theme.REGRESSION_TW_RED, width=1.8)
        pen_dn.setCosmetic(True)

        pen_mid = pg.mkPen(color=theme.REGRESSION_TW_MID, width=1.5, style=Qt.PenStyle.DashLine)
        pen_mid.setCosmetic(True)

        curve_up = pg.PlotCurveItem(x=x_coords, y=y_up, pen=pen_up)
        curve_mid = pg.PlotCurveItem(x=x_coords, y=y_mid, pen=pen_mid)
        curve_dn = pg.PlotCurveItem(x=x_coords, y=y_dn, pen=pen_dn)

        # 2. Двухцветная заливка TradingView:
        # Верхняя половина (синяя) и нижняя половина (красная)
        brush_blue = pg.mkBrush(*theme.REGRESSION_TW_BLUE_FILL)
        fill_upper = pg.FillBetweenItem(curve_up, curve_mid, brush=brush_blue)
        pi.addItem(fill_upper, ignoreBounds=True)

        brush_red = pg.mkBrush(*theme.REGRESSION_TW_RED_FILL)
        fill_lower = pg.FillBetweenItem(curve_mid, curve_dn, brush=brush_red)
        pi.addItem(fill_lower, ignoreBounds=True)

        pi.addItem(curve_up, ignoreBounds=True)
        pi.addItem(curve_dn, ignoreBounds=True)
        pi.addItem(curve_mid, ignoreBounds=True)

        self.regression_items.extend([fill_upper, fill_lower, curve_up, curve_dn, curve_mid])

        # 3. Маркеры на окончании базовой волны ЗигЗага (как в STRG)
        curr_x = float(ch["x"][1])
        for py, color_hex, symbol in [
            (float(ch["curr_upper_round"]), theme.REGRESSION_TW_BLUE, "o"),
            (float(ch["curr_mid_round"]), theme.REGRESSION_TW_MID, "s"),
            (float(ch["curr_lower_round"]), theme.REGRESSION_TW_RED, "o"),
        ]:
            dot = pg.ScatterPlotItem(
                x=[curr_x], y=[py], symbol=symbol, size=7,
                pen=pg.mkPen(color="#111111", width=1.2),
                brush=pg.mkBrush(color_hex)
            )
            pi.addItem(dot, ignoreBounds=True)
            self.regression_items.append(dot)

        # 4. Информационная плашка параметров тренда (наклон, Пирсон r, R2)
        r_val = float(ch["r"])
        slope_val = float(ch["slope"])
        r2_val = float(ch["r2"])
        info_text = f" r = {r_val:+.3f} | R² = {r2_val:.1%} | наклон: {slope_val:+.1f} пт/бар "
        info_badge = pg.TextItem(
            text=info_text,
            color="#ffffff",
            fill=pg.mkBrush(16, 20, 32, 230),
            border=pg.mkPen(theme.REGRESSION_TW_BLUE, width=1.0),
            anchor=(0.0, 1.2)
        )
        info_badge.setFont(QFont("Tahoma", 8, QFont.Weight.Bold))
        info_badge.setPos(float(ch["x"][0]), float(ch["y_upper"][0]))
        pi.addItem(info_badge, ignoreBounds=True)
        self.regression_items.append(info_badge)

    def clear_plots(self):
        """Очистить оба графика перед повторным расчетом или загрузкой нового дня."""
        self.candles_item.set_data([])
        self.time_axis.set_labels([])
        self.current_price_line.setVisible(False)
        self.price_label.setVisible(False)
        for item in self.zigzag_items:
            self.plot_candles.removeItem(item)
        self.zigzag_items.clear()
        for item in self.regression_items:
            self.plot_candles.removeItem(item)
        self.regression_items.clear()
        self.plot_macd.clear()
        self.plot_macd.addItem(self.macd_zero_line)  # Возвращаем нулевую линию обратно
