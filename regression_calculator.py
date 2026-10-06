"""
regression_calculator.py — Модуль расчета линейной регрессии и канала через Lua (Lupa).
Поддерживает округление цен до биржевого шага инструмента (по умолчанию 25 для MIX).
"""

import os
from lupa import LuaRuntime


class RegressionCalculator:
    def __init__(self, script_path="sf_regression.lua", price_step=25.0):
        self.script_path = script_path
        self.price_step = float(price_step)
        self.lua = LuaRuntime(unpack_returned_tuples=True)

        if not os.path.exists(self.script_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.script_path = os.path.join(base_dir, "sf_regression.lua")

        with open(self.script_path, "r", encoding="cp1251", errors="replace") as f:
            code = f.read()

        self.lua.execute(code)
        self.calc_fn = self.lua.globals().CalculateRegression

    def round_to_step(self, price):
        """Округляет цену до ближайшего биржевого шага цены (25 пт для MIX)."""
        if self.price_step <= 0:
            return round(price)
        return round(price / self.price_step) * self.price_step

    def calculate_channel(self, candles, start_bar=None, end_bar=None, k=2.0, price_key="close"):
        """
        Рассчитывает регрессионный канал по свечам через Lua.
        :param candles: список словарей свечей [{'close': ..., 'time': ...}]
        :param start_bar: номер бара начала отрезка (1-indexed)
        :param end_bar: номер бара конца отрезка (1-indexed)
        :param k: множитель стандартной ошибки Se (обычно 2.0 = 2 сигмы)
        :param price_key: поле цены для регрессии ("close", "high", "low")
        :return: словарь с параметрами тренда, точками на текущей свече и линиями для холста
        """
        if not candles or len(candles) < 3:
            return None

        total_bars = len(candles)
        start_bar = int(start_bar or 1)
        end_bar = int(end_bar or total_bars)

        if start_bar < 1:
            start_bar = 1
        if end_bar > total_bars:
            end_bar = total_bars

        if end_bar - start_bar + 1 < 3:
            return None

        prices = [float(c.get(price_key, c.get("close", 0))) for c in candles]
        highs = [float(c.get("high", 0)) for c in candles]
        lows = [float(c.get("low", 0)) for c in candles]

        prices_tbl = self.lua.table_from(prices)
        highs_tbl = self.lua.table_from(highs)
        lows_tbl = self.lua.table_from(lows)

        lua_res = self.calc_fn(prices_tbl, start_bar, end_bar, float(k), highs_tbl, lows_tbl)
        if not lua_res:
            return None

        r = float(lua_res.r)
        slope = float(lua_res.slope)
        intercept = float(lua_res.intercept)
        r2 = float(lua_res.r2)
        se = float(lua_res.stdError)

        # Точные математические цены из Lua
        curr_mid = float(lua_res.currMid)
        curr_upper = float(lua_res.currUpper)
        curr_lower = float(lua_res.currLower)

        start_mid = float(lua_res.startMid)
        start_upper = float(lua_res.startUpper)
        start_lower = float(lua_res.startLower)

        # Округление до шага цены (25 пт для фьючерса MIX)
        step = self.price_step
        curr_mid_round = self.round_to_step(curr_mid)
        curr_upper_round = self.round_to_step(curr_upper)
        curr_lower_round = self.round_to_step(curr_lower)

        start_mid_round = self.round_to_step(start_mid)
        start_upper_round = self.round_to_step(start_upper)
        start_lower_round = self.round_to_step(start_lower)

        # Координаты для отрисовки на холсте pyqtgraph (0-indexed по X)
        x_coords = [float(start_bar - 1), float(end_bar - 1)]

        # Параметры продолжения линий канала вперед
        ext_bar = int(lua_res.extBar or end_bar)
        ext_mid = float(lua_res.extMid or curr_mid)
        ext_upper = float(lua_res.extUpper or curr_upper)
        ext_lower = float(lua_res.extLower or curr_lower)

        ext_mid_round = self.round_to_step(ext_mid)
        ext_upper_round = self.round_to_step(ext_upper)
        ext_lower_round = self.round_to_step(ext_lower)

        has_extension = (ext_bar > end_bar)
        x_ext = [float(end_bar - 1), float(ext_bar - 1)] if has_extension else []

        return {
            "r": r,
            "slope": slope,
            "intercept": intercept,
            "r2": r2,
            "std_error": se,
            "k": float(k),
            "start_bar": start_bar,
            "end_bar": end_bar,
            "start_time": candles[start_bar - 1].get("time", ""),
            "end_time": candles[end_bar - 1].get("time", ""),
            # Точки на финише волны ЗигЗага (без текстовых плашек)
            "curr_mid": curr_mid,
            "curr_upper": curr_upper,
            "curr_lower": curr_lower,
            "curr_mid_round": curr_mid_round,
            "curr_upper_round": curr_upper_round,
            "curr_lower_round": curr_lower_round,
            # Координаты основного канала для холста
            "x": x_coords,
            "y_mid": [start_mid_round, curr_mid_round],
            "y_upper": [start_upper_round, curr_upper_round],
            "y_lower": [start_lower_round, curr_lower_round],
            # Координаты продолжения линий вперед
            "has_extension": has_extension,
            "ext_bar": ext_bar,
            "ext_time": candles[ext_bar - 1].get("time", "") if ext_bar <= len(candles) else "",
            "x_ext": x_ext,
            "y_ext_mid": [curr_mid_round, ext_mid_round],
            "y_ext_upper": [curr_upper_round, ext_upper_round],
            "y_ext_lower": [curr_lower_round, ext_lower_round],
        }