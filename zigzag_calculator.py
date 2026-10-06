"""
zigzag_calculator.py — Модуль расчета канонического ЗигЗага через Lua (Lupa).
"""

import os
from lupa import LuaRuntime


class ZigzagCalculator:
    def __init__(self, script_path="sf_zigzag.lua"):
        self.script_path = script_path
        self.lua = LuaRuntime(unpack_returned_tuples=True)

        if not os.path.exists(self.script_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.script_path = os.path.join(base_dir, "sf_zigzag.lua")

        with open(self.script_path, "r", encoding="cp1251", errors="replace") as f:
            code = f.read()

        self.lua.execute(code)
        self.calc_fn = self.lua.globals().CalculateZigzag or self.lua.globals().CalculateFirstLine
        self.last_line = {}

    def calculate_zigzag(self, candles, dev_percent=0.9):
        """
        Передает массивы high и low в Lua-скрипт и возвращает:
        - pivots: список всех вершин для визуализации в Python
        """
        if not candles or len(candles) < 2:
            return []

        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]

        h_tbl = self.lua.table_from(highs)
        l_tbl = self.lua.table_from(lows)

        trend_dir, line_start, start_bar, line_end, end_bar, all_pivots = self.calc_fn(
            h_tbl, l_tbl, float(dev_percent)
        )

        if int(trend_dir) == 0:
            return []

        # Сохраняем состояние последней активной линии (для логики робота)
        self.last_line = {
            "trend_dir": int(trend_dir),
            "line_start": float(line_start),
            "start_bar": int(start_bar),
            "line_end": float(line_end),
            "end_bar": int(end_bar),
        }

        # Преобразуем массив вершин из Lua для холста Python (0-indexed по оси X)
        pivots = []
        if all_pivots is not None:
            count = len(all_pivots)
            for i in range(1, count + 1):
                p = all_pivots[i]
                bar_num = int(p.bar)
                idx = bar_num - 1
                t_str = candles[idx].get("time", "") if 0 <= idx < len(candles) else ""
                pivots.append({
                    "idx": idx,
                    "bar_idx": float(idx),
                    "time": t_str,
                    "price": float(p.price),
                    "type": str(p.type),
                })

        return pivots

    # Алиас для обратной совместимости
    calculate_first_line = calculate_zigzag