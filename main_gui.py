from datetime import datetime
import requests
import time
import MetaTrader5 as mt5
import pandas as pd
import tkinter as tk
from threading import Thread
import sys

# Валютные пары
selected_pairs = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDCAD", "AUDJPY", "AUDUSD",
    "EURAUD", "EURCAD", "EURCHF", "EURGBP", "EURJPY", "GBPAUD",
    "GBPCHF", "GBPJPY", "GBPNZD", "NZDJPY", "NZDUSD", "USDCAD",
    "USDCHF", "BTCUSDT"
]

# таймфреймы
timeframes = [mt5.TIMEFRAME_M2, mt5.TIMEFRAME_M3, mt5.TIMEFRAME_M4, mt5.TIMEFRAME_M5, mt5.TIMEFRAME_M6,
              mt5.TIMEFRAME_M10,
              mt5.TIMEFRAME_M12, mt5.TIMEFRAME_M15]


class TelegramBot:

    def __init__(self, token, channel_id):
        self.token = token
        self.channel_id = channel_id

    def send_message(self, message):
        url = f'https://api.telegram.org/bot{self.token}/sendMessage'
        data = {
            'chat_id': self.channel_id,
            'text': message,
            'parse_mode': 'Markdown'  # Используем Markdown для форматирования сообщения
        }
        requests.post(url, data)


class MarketAnalyzer:
    def __init__(self, selected_pairs, timeframes):
        self.selected_pairs = selected_pairs
        self.timeframes = timeframes
        self.ensure_mt5_connection()

    def ensure_mt5_connection(self):
        """ Проверка подключения к MT5 и переподключение при необходимости. """
        if not mt5.terminal_info():
            print("Подключение к MT5 отсутствует. Попытка переподключения...")
            if not mt5.initialize():
                print("Ошибка инициализации MetaTrader 5, пытаюсь переподключиться...")
                time.sleep(10)  # задержка перед следующей попыткой
                return False
        else:
            print("Подключение к MT5 - активно!")
        return True

    def get_candle_data(self, symbol, timeframe):
        candles = mt5.copy_rates_from_pos(symbol, timeframe, 0, 200)
        if candles is not None:
            df = pd.DataFrame(candles)
            # Конвертация цвета свечей в строку 'К', 'З' или 'Н'
            color_sequence = ''.join(
                ['К' if row['close'] < row['open'] else ('З' if row['close'] > row['open'] else 'Н') for _, row in
                 df.iterrows()])
            return color_sequence
        else:
            return None

    def find_longest_repeating_combination_from_end(self, color_sequence):
        max_length = len(color_sequence)
        end_combo = color_sequence[-max_length:]
        # Поиск последнего вхождения комбинации в строку до конца
        last_occurrence = -1
        for length in range(len(end_combo), 0, -1):
            sub_combo = end_combo[-length:]
            occurrence = color_sequence.rfind(sub_combo, 0, max_length - length)
            if occurrence != -1:
                last_occurrence = occurrence
                end_combo = sub_combo
                break
        return end_combo, last_occurrence

    def analyze(self):
        signals = []
        for pair in self.selected_pairs:
            for timeframe in self.timeframes:
                color_sequence = self.get_candle_data(pair, timeframe)
                if color_sequence:
                    combo, position = self.find_longest_repeating_combination_from_end(color_sequence)
                    MIN_LEN_COMBO = 18
                    if combo and position != -1 and len(combo) >= MIN_LEN_COMBO:
                        direction_sequence = [self.candle_direction(candle) for candle in
                                              color_sequence[position + len(combo):position + len(combo) + 10]]
                        direction_message = ', '.join(direction_sequence)
                        message = f"*ВНИМАНИЕ СИГНАЛ*!\nАктив: {pair}\nТаймфрем: М{timeframe}\n" \
                                  f"Сила сигнала: {len(combo)}\n" \
                                  f"Код: {200 - position}" \
                                  f"\nОткрываешь свечи *М{timeframe}*, проверяешь что последняя свеча и предыдущие закрылись так:\n" \
                                  f">> {combo[:-4]}*{combo[-4:]}* <<\n" \
                                  f"(_достаточно посмотреть на послдение 4 свечи и уже ясно что сигнал подтвердился. Остальные свечи указаны на всякий случай._\n" \
                                  f"\nКак только текущая свеча *М{timeframe}* цвета *{combo[-1]}* закроется, открывайся по очереди на каждую следущую свечу, до первого плюса:\n" \
                                  f"*{direction_message}*\n" \
                                  f"\nКак только был плюс, дальше по направлениям не идти! Сигнал уже будет не актуальным"
                        signals.append(message)
        return signals

    def candle_direction(self, candle):
        return "Вверх" if candle == 'К' else ("Нейтрал" if candle == 'Н' else "Вниз")


class TextRedirector(object):
    def __init__(self, widget):
        self.widget = widget

    def write(self, str):
        self.widget.insert(tk.END, str)
        self.widget.see(tk.END)

    def flush(self):
        pass


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()

    def create_widgets(self):
        self.text_area = tk.Text(self)
        self.text_area.pack(side="top", fill="both", expand=True)

    def update_text_area(self, message):
        self.text_area.insert(tk.END, message + '\n')
        self.text_area.see(tk.END)  # Прокрутка до последнего сообщения


def run_bot(app, analyzer, bot):
    while True:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        app.update_text_area(f"Текущее время, скрипт идет по циклу: {current_time}")
        if analyzer.ensure_mt5_connection():
            signals = analyzer.analyze()
            for message in signals:
                app.update_text_area(message)
                bot.send_message(message)
        time.sleep(60)


# Настройки бота и анализатора
bot = TelegramBot('6522358778:AAGJrRU9w2S8Jo0U8YpbVIRN3uFbYNPJrx8', '@DragonSignalNews')
analyzer = MarketAnalyzer(selected_pairs, timeframes)

root = tk.Tk()
app = Application(master=root)
app.master.title("Trading Bot")

# Перенаправляем стандартный вывод в текстовое поле GUI
sys.stdout = TextRedirector(app.text_area)

# Запуск бота в отдельном потоке
thread = Thread(target=run_bot, args=(app, analyzer, bot))
thread.daemon = True
thread.start()

# Запуск графического интерфейса
app.mainloop()
