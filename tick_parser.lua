-- tick_parser.lua
-- Модуль разбора тиковых файлов Финам и сборки 5-минутных свечей (M5)
-- Сохраняет результаты в 4 текстовых файла для робота и возвращает таблицу свечей:
-- 1. candles.txt      (date;time;open;high;low;close;volume)
-- 2. high_prices.txt  (date;time;high)
-- 3. low_prices.txt   (date;time;low)
-- 4. close_prices.txt (date;time;close)

function ParseTicks(input_file, output_dir, period_time)
    if not input_file then return nil, 'Не указан входной файл' end
    output_dir = output_dir or 'Y:\\SIGNAL'
    period_time = period_time or 300 -- 5 минут = 300 секунд

    local candles_file = output_dir .. '\\candles.txt'
    local high_file    = output_dir .. '\\high_prices.txt'
    local low_file     = output_dir .. '\\low_prices.txt'
    local close_file   = output_dir .. '\\close_prices.txt'

    local f_candles = io.open(candles_file, 'w')
    local f_high    = io.open(high_file, 'w')
    local f_low     = io.open(low_file, 'w')
    local f_close   = io.open(close_file, 'w')

    if not f_candles or not f_high or not f_low or not f_close then
        return nil, 'Ошибка создания выходных файлов'
    end

    local candles = {}
    local current_slot = -1
    local current_date = ''
    local current_time = ''

    local cur_open = 0
    local cur_high = 0
    local cur_low  = 0
    local cur_close = 0
    local cur_vol  = 0

    local function FlushBar()
        if current_slot < 0 then return end

        -- 1. Полная строка свечи: date;time;open;high;low;close;volume
        f_candles:write(string.format('%s;%s;%.1f;%.1f;%.1f;%.1f;%d\n',
            current_date, current_time, cur_open, cur_high, cur_low, cur_close, cur_vol))

        -- 2. Отдельные файлы с датой и временем свечи
        f_high:write(string.format('%s;%s;%.1f\n', current_date, current_time, cur_high))
        f_low:write(string.format('%s;%s;%.1f\n', current_date, current_time, cur_low))
        f_close:write(string.format('%s;%s;%.1f\n', current_date, current_time, cur_close))

        -- 3. Сохранение в массив Lua для прямой передачи в Python
        local c = {}
        c.date = current_date
        c.time = current_time
        c.open = cur_open
        c.high = cur_high
        c.low = cur_low
        c.close = cur_close
        c.volume = cur_vol
        table.insert(candles, c)
    end

    for line in io.lines(input_file) do
        if line and line ~= '' and not line:find('<TICKER>') then
            local ticker, per, d, t, p_str, v_str = line:match('^([^,]+),([^,]+),([^,]+),([^,]+),([^,]+),([^,]+)')
            if ticker and t and p_str then
                local price = tonumber(p_str)
                local vol   = tonumber(v_str) or 1

                if price and #t >= 6 then
                    local h = tonumber(t:sub(1, 2)) or 0
                    local m = tonumber(t:sub(3, 4)) or 0
                    local s = tonumber(t:sub(5, 6)) or 0
                    local sec_total = h * 3600 + m * 60 + s
                    local slot_idx = math.floor(sec_total / period_time)

                    if slot_idx ~= current_slot then
                        FlushBar()

                        current_slot = slot_idx
                        current_date = d

                        local slot_sec = slot_idx * period_time
                        local bar_h = math.floor(slot_sec / 3600)
                        local bar_m = math.floor((slot_sec % 3600) / 60)
                        current_time = string.format('%02d:%02d:00', bar_h, bar_m)

                        cur_open = price
                        cur_high = price
                        cur_low  = price
                        cur_close = price
                        cur_vol  = vol
                    else
                        if price > cur_high then cur_high = price end
                        if price < cur_low  then cur_low  = price end
                        cur_close = price
                        cur_vol = cur_vol + vol
                    end
                end
            end
        end
    end

    -- Записываем последнюю свечу
    FlushBar()

    f_candles:close()
    f_high:close()
    f_low:close()
    f_close:close()

    return candles
end
