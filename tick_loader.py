"""
tick_loader.py — Мост между Python и Lua через библиотеку Lupa + потоковый агрегатор тиков.
1. Запускает tick_parser.lua прямо в оперативной памяти Python без внешних процессов (CP1251).
2. Загружает сырые тики через pandas для посекундного/потикового воспроизведения (Replayer).
3. Обеспечивает честное "живое дыхание" формирующейся свечи (Candle Morphing).
"""

import os
import glob
import pandas as pd
import numpy as np
from lupa import LuaRuntime


class TickLoader:
    def __init__(self, script_path="tick_parser.lua"):
        self.script_path = script_path
        self.lua = LuaRuntime(unpack_returned_tuples=True)

        if not os.path.exists(self.script_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.script_path = os.path.join(base_dir, "tick_parser.lua")

        # Читаем скрипт Lua в правильной кодировке Windows-1251
        with open(self.script_path, "r", encoding="cp1251") as f:
            lua_code = f.read()

        self.lua.execute(lua_code)
        self.parse_fn = self.lua.globals().ParseTicks

        # Хранилище данных
        self.current_file = None
        self.candles_full = []
        self.df_ticks = None
        self.candle_times_np = np.array([])
        self.tick_times_np = np.array([])
        self.tick_prices_np = np.array([])
        self.tick_vols_np = np.array([])

    def load_file(self, input_file, output_dir="Y:/SIGNAL", period_sec=300):
        """
        Загружает тиковый файл:
        1. Парсит свечи M5 через Lua и формирует candles.txt / high_prices.txt / ...
        2. Загружает сырые тики в pandas для пошагового плеера.
        """
        self.current_file = os.path.abspath(input_file)

        # 1. Запуск Lua-парсера свечей
        lua_candles = self.parse_fn(self.current_file, output_dir, period_sec)
        if lua_candles is None:
            self.candles_full = []
            return []

        candles = []
        count = len(lua_candles)
        for i in range(1, count + 1):
            c = lua_candles[i]
            candles.append({
                "date": str(c.date),
                "time": str(c.time),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": int(c.volume),
            })
        self.candles_full = candles

        # 2. Быстрая загрузка сырых тиков через pandas
        df = pd.read_csv(
            self.current_file,
            usecols=[2, 3, 4, 5],
            names=["DATE", "TIME", "PRICE", "VOL"],
            header=0,
            dtype={"DATE": str, "TIME": str, "PRICE": float, "VOL": int}
        )
        time_str = df["TIME"].str.zfill(6)
        df["DATETIME"] = pd.to_datetime(df["DATE"] + time_str, format="%Y%m%d%H%M%S")
        df = df.sort_values("DATETIME", kind="stable").reset_index(drop=True)
        self.df_ticks = df

        # 3. Подготовка векторных массивов для быстрого поиска (O(log N))
        self.candle_times_np = np.array([
            np.datetime64(pd.to_datetime(c["date"] + " " + c["time"]))
            for c in self.candles_full
        ])
        self.tick_times_np = self.df_ticks["DATETIME"].values
        self.tick_prices_np = self.df_ticks["PRICE"].values
        self.tick_vols_np = self.df_ticks["VOL"].values

        return self.candles_full

    def parse(self, input_file, output_dir="Y:/SIGNAL", period_sec=300):
        """Алиас для обратной совместимости."""
        return self.load_file(input_file, output_dir, period_sec)

    def get_num_ticks(self):
        """Количество загруженных тиков."""
        return len(self.df_ticks) if self.df_ticks is not None else 0

    def get_visible_frame(self, tick_idx):
        """
        Возвращает состояние рынка в момент tick_idx:
        (curr_time, curr_price, visible_candles, candle_idx)
        С честным живым морфингом крайней формирующейся свечи!
        """
        if self.df_ticks is None or len(self.df_ticks) == 0:
            return None, None, [], 0

        idx = max(0, min(tick_idx, len(self.df_ticks) - 1))
        curr_time = self.df_ticks.iloc[idx]["DATETIME"]
        curr_price = float(self.tick_prices_np[idx])

        target_np = np.datetime64(curr_time)
        c_idx = int(np.searchsorted(self.candle_times_np, target_np, side="right"))
        if c_idx <= 0:
            c_idx = 1
        c_idx = min(c_idx, len(self.candles_full))

        # Срез закрытых свечей
        visible = [dict(c) for c in self.candles_full[:c_idx]]

        # Честный морфинг текущей (крайней) свечи
        bar_start_np = self.candle_times_np[c_idx - 1]
        start_tick_idx = int(np.searchsorted(self.tick_times_np, bar_start_np, side="left"))
        start_tick_idx = min(start_tick_idx, idx)

        bar_prices = self.tick_prices_np[start_tick_idx : idx + 1]
        if len(bar_prices) > 0:
            visible[-1]["open"] = float(bar_prices[0])
            visible[-1]["high"] = float(bar_prices.max())
            visible[-1]["low"] = float(bar_prices.min())
            visible[-1]["close"] = curr_price
            bar_vols = self.tick_vols_np[start_tick_idx : idx + 1]
            visible[-1]["volume"] = int(bar_vols.sum())

        return curr_time, curr_price, visible, c_idx - 1

    def get_next_price_change_tick(self, tick_idx):
        """Шаг вперед до следующего тика с изменением цены."""
        if self.df_ticks is None or len(self.tick_prices_np) == 0:
            return tick_idx
        n = len(self.tick_prices_np)
        curr_p = self.tick_prices_np[tick_idx]
        idx = tick_idx + 1
        while idx < n and self.tick_prices_np[idx] == curr_p:
            idx += 1
        return min(idx, n - 1)

    def get_prev_price_change_tick(self, tick_idx):
        """Шаг назад до предыдущего тика с изменением цены."""
        if self.df_ticks is None or len(self.tick_prices_np) == 0:
            return tick_idx
        curr_p = self.tick_prices_np[tick_idx]
        idx = tick_idx - 1
        while idx >= 0 and self.tick_prices_np[idx] == curr_p:
            idx -= 1
        return max(0, idx)

    def get_next_candle_tick(self, tick_idx):
        """Шаг вперед на 1 свечу вперед."""
        if self.df_ticks is None or len(self.candle_times_np) == 0:
            return tick_idx
        curr_time = self.df_ticks.iloc[tick_idx]["DATETIME"]
        target_np = np.datetime64(curr_time)
        curr_c_idx = int(np.searchsorted(self.candle_times_np, target_np, side="right")) - 1
        next_c_idx = curr_c_idx + 1
        if next_c_idx < len(self.candle_times_np):
            next_time = self.candle_times_np[next_c_idx]
            next_tick = int(np.searchsorted(self.tick_times_np, next_time, side="left"))
            return min(next_tick, len(self.df_ticks) - 1)
        return len(self.df_ticks) - 1

    def get_prev_candle_tick(self, tick_idx):
        """Шаг назад на 1 свечу назад."""
        if self.df_ticks is None or len(self.candle_times_np) == 0:
            return tick_idx
        curr_time = self.df_ticks.iloc[tick_idx]["DATETIME"]
        target_np = np.datetime64(curr_time)
        curr_c_idx = int(np.searchsorted(self.candle_times_np, target_np, side="right")) - 1
        prev_c_idx = curr_c_idx - 1
        if prev_c_idx >= 0:
            prev_time = self.candle_times_np[prev_c_idx]
            prev_tick = int(np.searchsorted(self.tick_times_np, prev_time, side="left"))
            return max(0, prev_tick)
        return 0

    @staticmethod
    def find_latest_file(preferred_dir="."):
        """
        Ищет самый свежий тиковый файл в текущей папке или на диске Y:\\.
        Игнорирует системные файлы экспорта (candles.txt, close_prices.txt и т.д.).
        """
        ignore = {"candles.txt", "high_prices.txt", "low_prices.txt", "close_prices.txt"}

        local_files = glob.glob(os.path.join(preferred_dir, "*.txt"))
        candidates = [f for f in local_files if os.path.basename(f) not in ignore]

        if not candidates and os.path.exists("Y:/"):
            root_files = glob.glob("Y:/*.txt")
            candidates = [f for f in root_files if os.path.basename(f) not in ignore]

        if not candidates:
            return None

        candidates.sort(key=os.path.getmtime)
        return candidates[-1]
