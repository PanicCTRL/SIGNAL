"""
tick_loader.py — Мост между Python и Lua через библиотеку Lupa.
Запускает tick_parser.lua прямо в оперативной памяти Python без внешних процессов.
"""

import os
import glob
from lupa import LuaRuntime


class TickLoader:
    def __init__(self, script_path="tick_parser.lua"):
        self.script_path = script_path
        self.lua = LuaRuntime(unpack_returned_tuples=True)

        if not os.path.exists(self.script_path):
            # Пробуем найти рядом с модулем
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.script_path = os.path.join(base_dir, "tick_parser.lua")

        # Читаем скрипт Lua в правильной кодировке Windows-1251
        with open(self.script_path, "r", encoding="cp1251") as f:
            lua_code = f.read()

        self.lua.execute(lua_code)
        self.parse_fn = self.lua.globals().ParseTicks

    def parse(self, input_file, output_dir="Y:/SIGNAL", period_sec=300):
        """
        Разбирает тиковый файл и возвращает список свечей:
        [{'date': ..., 'time': ..., 'open': ..., 'high': ..., 'low': ..., 'close': ..., 'volume': ...}, ...]
        """
        input_file = os.path.abspath(input_file)
        lua_candles = self.parse_fn(input_file, output_dir, period_sec)
        if lua_candles is None:
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
        return candles

    @staticmethod
    def find_latest_file(preferred_dir="."):
        """
        Ищет самый свежий тиковый файл в текущей папке или на диске Y:\.
        Игнорирует системные файлы экспорта (candles.txt, close_prices.txt и т.д.).
        """
        ignore = {"candles.txt", "high_prices.txt", "low_prices.txt", "close_prices.txt"}

        # 1. Поиск в рабочей папке
        local_files = glob.glob(os.path.join(preferred_dir, "*.txt"))
        candidates = [f for f in local_files if os.path.basename(f) not in ignore]

        # 2. Если в локальной папке нет — ищем на диске Y:\
        if not candidates and os.path.exists("Y:/"):
            root_files = glob.glob("Y:/*.txt")
            candidates = [f for f in root_files if os.path.basename(f) not in ignore]

        if not candidates:
            return None

        # Сортируем по времени последней модификации файла
        candidates.sort(key=os.path.getmtime)
        return candidates[-1]
