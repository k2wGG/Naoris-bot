import threading
import uuid
import time
import json
import random
import jwt
import cloudscraper
import os
from datetime import datetime
from typing import List, Optional
from colorama import init, Fore, Style

# Инициализация colorama для цветного вывода
init(autoreset=True)

# Создаём папку для хранения сессионных данных
SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

def показать_баннер():
    print(Fore.GREEN + "╔══════════════════════════════════╗")
    print(Fore.GREEN + "║        NAORIS PROTOCOL           ║")
    print(Fore.GREEN + "║         АВТОФАРМ                 ║")
    print(Fore.GREEN + "║    https://t.me/nod3r            ║")
    print(Fore.GREEN + "╚══════════════════════════════════╝")
    print()

def сгенерировать_хеш_устройства() -> str:
    """Генерирует уникальный хеш устройства."""
    return str(int(uuid.uuid4().hex.replace("-", "")[:8], 16))

def декодировать_токен(token: str) -> Optional[dict]:
    """Декодирует JWT-токен без проверки подписи."""
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        if not decoded:
            raise ValueError("Неверный формат токена")
        return {
            "wallet_address": decoded.get("wallet_address"),
            "id": decoded.get("id"),
            "exp": decoded.get("exp"),
        }
    except Exception as e:
        print(Fore.RED + f"[ОШИБКА] Ошибка декодирования токена: {e}")
        return None

def токен_истёк(account: dict) -> bool:
    """Проверяет, истёк ли токен аккаунта."""
    if not account.get("decoded") or not account["decoded"].get("exp"):
        return True
    return time.time() >= account["decoded"]["exp"]

def загрузить_прокси(файл: str) -> List[str]:
    """
    Загружает прокси из текстового файла и нормализует их формат.
    Если строка не содержит '://', добавляет 'http://'.
    """
    proxies = []
    try:
        with open(файл, "r", encoding="utf-8") as f:
            for line in f:
                proxy = line.strip()
                if not proxy:
                    continue
                if "://" not in proxy:
                    proxy = "http://" + proxy
                proxies.append(proxy)
        return proxies
    except Exception as e:
        print(Fore.RED + f"[ОШИБКА] Не удалось загрузить прокси: {e}")
        return []

def спросить_о_прокси() -> bool:
    """Спрашивает, использовать ли прокси."""
    while True:
        choice = input(Fore.CYAN + "[?] Хотите использовать прокси? (y/n): ").strip().lower()
        if choice in ["y", "n"]:
            return choice == "y"
        else:
            print(Fore.RED + "Введите 'y' для Да или 'n' для Нет.")

def получить_заголовки(идентификатор: str) -> dict:
    """Формирует реалистичные заголовки для запросов."""
    return {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "chrome-extension://cpikalnagknmlfhnilhfelifgbollmmp",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        "Authorization": f"Bearer {идентификатор}"
    }

# Конфигурация API и приложения
API_КОНФИГ = {
    "base_url": "https://naorisprotocol.network",
    "endpoints": {
        "heartbeat": "/sec-api/api/produce-to-kafka",
        "toggle": "/sec-api/api/toggle",
        "walletDetails": "/testnet-api/api/testnet/walletDetails"
    },
    "headers": {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "chrome-extension://cpikalnagknmlfhnilhfelifgbollmmp",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    },
}

APP_КОНФИГ = {
    "heartbeat_interval": 60,   # Интервал в секундах (60 секунд = 1 минута)
    "data_file": "accounts.json",   # Файл с аккаунтами
    "proxy_file": "proxy.txt",
    "session_refresh_interval": 5,
}

class DeviceHeartbeatBot:
    def __init__(self, account: dict, proxy: Optional[str] = None):
        self.account = account
        self.proxy = proxy
        self.uptime_minutes = 0
        self.deviceHash = account.get("deviceHash") or сгенерировать_хеш_устройства()
        self.toggle_state = True  # по умолчанию ВКЛ
        self.whitelisted_urls = ["naorisprotocol.network", "google.com"]
        self.is_installed = True
        # Файл для сессии уникален для каждого аккаунта
        self.session_file = os.path.join(SESSIONS_DIR, f"wallet_session_{self.account['wallet_address']}.json")
        self.scraper = self.create_scraper(self.proxy)
        self.load_wallet_session()
        try:
            self.scraper.get(API_КОНФИГ["base_url"], timeout=30)
            print(Fore.CYAN + "[ИНФО] Сессия успешно разогрета.")
        except Exception as e:
            print(Fore.YELLOW + f"[ПРЕДУПРЕЖДЕНИЕ] Не удалось разогреть сессию: {e}")

    def save_wallet_session(self):
        """Сохраняет cookies (сессионные данные) в файл."""
        try:
            cookies = self.scraper.cookies.get_dict()
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(cookies, f)
            print(Fore.CYAN + f"[ИНФО] Сессионные данные сохранены в {self.session_file}")
        except Exception as e:
            print(Fore.YELLOW + f"[ПРЕДУПРЕЖДЕНИЕ] Не удалось сохранить сессионные данные: {e}")

    def load_wallet_session(self):
        """Загружает cookies (сессионные данные) из файла, если он существует."""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                self.scraper.cookies.update(cookies)
                print(Fore.CYAN + f"[ИНФО] Сессионные данные загружены из {self.session_file}")
            except Exception as e:
                print(Fore.YELLOW + f"[ПРЕДУПРЕЖДЕНИЕ] Не удалось загрузить сессионные данные: {e}")

    @staticmethod
    def load_accounts(data_file: str = APP_КОНФИГ["data_file"]) -> List[dict]:
        """
        Загружает аккаунты из файла accounts.json.
        Формат файла:
        [
            {
                "Address": "Ваш EVM адрес 1",
                "deviceHash": "Ваш хеш устройства 1",
                "token": "JWT токен (опционально)"
            },
            {
                "Address": "Ваш EVM адрес 2",
                "deviceHash": "Ваш хеш устройства 2",
                "token": "JWT токен (опционально)"
            }
        ]
        """
        accounts = []
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data:
                if "Address" not in entry or "deviceHash" not in entry:
                    print(Fore.RED + f"[ОШИБКА] Неверный формат аккаунта: {entry}")
                    continue
                accounts.append({
                    "token": entry.get("token", ""),
                    "decoded": {"wallet_address": entry["Address"]},
                    "wallet_address": entry["Address"],
                    "deviceHash": entry["deviceHash"]
                })
            if not accounts:
                raise ValueError("Не загружено ни одного валидного аккаунта")
            print(Fore.CYAN + f"[ИНФО] Успешно загружено {len(accounts)} аккаунтов из {APP_КОНФИГ['data_file']}.")
            return accounts
        except Exception as e:
            print(Fore.RED + f"[ОШИБКА] Не удалось загрузить аккаунты: {e}")
            exit(1)

    @staticmethod
    def load_proxies(proxy_file: str = APP_КОНФИГ["proxy_file"]) -> List[str]:
        return загрузить_прокси(proxy_file)

    def get_request_headers(self) -> dict:
        идентификатор = self.account.get("token") or self.account.get("wallet_address")
        headers = получить_заголовки(идентификатор)
        headers["Referer"] = API_КОНФИГ["base_url"]
        return headers

    def create_scraper(self, proxy: Optional[str] = None):
        scraper = cloudscraper.create_scraper(delay=10, browser={'custom': 'Chrome/132.0.0.0'})
        if proxy:
            scraper.proxies = {"http": proxy, "https": proxy}
        return scraper

    def refresh_session(self):
        """Обновляет сессию через GET на базовый URL."""
        try:
            self.scraper.get(API_КОНФИГ["base_url"], timeout=30)
            print(Fore.CYAN + "[ИНФО] Сессия обновлена (GET на базовый URL).")
        except Exception as e:
            print(Fore.YELLOW + f"[ПРЕДУПРЕЖДЕНИЕ] Не удалось обновить сессию: {e}")

    def toggle_device(self, state: str = "ON"):
        try:
            print(Fore.CYAN + f"Отправка запроса Toggle ({state}) для {self.account['wallet_address']}...")
            payload = {
                "walletAddress": self.account["wallet_address"],
                "state": state,
                "deviceHash": self.deviceHash
            }
            response = self.scraper.post(
                f"{API_КОНФИГ['base_url']}{API_КОНФИГ['endpoints']['toggle']}",
                json=payload,
                headers=self.get_request_headers(),
                timeout=30
            )
            self.toggle_state = (state.upper() == "ON")
            print(Fore.GREEN + f"[✔] Toggle {state} выполнен. Ответ: {response.text}")
            self.save_wallet_session()
        except Exception as e:
            print(Fore.RED + f"[ОШИБКА] Toggle Error: {e}")

    def send_heartbeat(self):
        try:
            self.refresh_session()
            print(Fore.CYAN + "Отправка Heartbeat...")
            payload = {
                "topic": "device-heartbeat",
                "inputData": {
                    "walletAddress": self.account["wallet_address"],
                    "deviceHash": str(self.deviceHash),
                    "isInstalled": self.is_installed,
                    "toggleState": self.toggle_state,
                    "whitelistedUrls": self.whitelisted_urls,
                    "timestamp": int(time.time()),
                    "clientVersion": "4.30.0"
                }
            }
            response = self.scraper.post(
                f"{API_КОНФИГ['base_url']}{API_КОНФИГ['endpoints']['heartbeat']}",
                json=payload,
                headers=self.get_request_headers(),
                timeout=30
            )
            if response.status_code == 401:
                print(Fore.YELLOW + "[ПРЕДУПРЕЖДЕНИЕ] Heartbeat вернул 401. Восстанавливаем сессию через toggle.")
                self.toggle_device("ON")
            print(Fore.GREEN + f"[✔] Heartbeat отправлен. Ответ: {response.text}")
        except Exception as e:
            print(Fore.RED + f"[ОШИБКА] Heartbeat Error: {e}")

    def send_ping(self):
        """
        Отправляет ping-запрос для эмуляции активности.
        Используется топик "ping" с дополнительными полями.
        """
        try:
            print(Fore.CYAN + "Отправка Ping...")
            payload = {
                "topic": "ping",
                "inputData": {
                    "walletAddress": self.account["wallet_address"],
                    "deviceHash": str(self.deviceHash),
                    "timestamp": int(time.time()),
                    "clientVersion": "4.30.0"
                }
            }
            response = self.scraper.post(
                f"{API_КОНФИГ['base_url']}{API_КОНФИГ['endpoints']['heartbeat']}",
                json=payload,
                headers=self.get_request_headers(),
                timeout=30
            )
            print(Fore.GREEN + f"[✔] Ping отправлен. Ответ: {response.text}")
        except Exception as e:
            print(Fore.RED + f"[ОШИБКА] Ping Error: {e}")

    def ping_loop(self):
        """Петля для отправки ping каждые 5-10 секунд."""
        while True:
            time.sleep(random.uniform(5, 10))
            self.send_ping()

    def get_wallet_details(self):
        try:
            payload = {"walletAddress": self.account["wallet_address"]}
            response = self.scraper.post(
                f"{API_КОНФИГ['base_url']}{API_КОНФИГ['endpoints']['walletDetails']}",
                json=payload,
                headers=self.get_request_headers(),
                timeout=30
            )
            try:
                data = response.json()
            except Exception as json_err:
                print(Fore.RED + f"[ОШИБКА] Ошибка парсинга JSON: {json_err}")
                return

            if not data.get("error", False):
                details = data.get("details", {})
                self.log_wallet_details(details)
            else:
                print(Fore.RED + f"[ОШИБКА] Ошибка получения данных кошелька: {data}")
        except Exception as e:
            print(Fore.RED + f"[ОШИБКА] Не удалось получить данные кошелька: {e}")

    def log_wallet_details(self, details: dict):
        active_rate = details.get("activeRatePerMinute", 0)
        earnings = self.uptime_minutes * active_rate
        # Если есть поле "points", используем его, иначе totalEarnings или 0
        points = details.get("points", details.get("totalEarnings", 0))
        
        print("\n" + Fore.WHITE + f"📊 Детали кошелька для {self.account['wallet_address']}:")
        print(Fore.CYAN + f"  Общий заработок: {details.get('totalEarnings')}")
        print(Fore.CYAN + f"  Заработок за сегодня: {details.get('todayEarnings')}")
        print(Fore.CYAN + f"  Реферальный заработок за сегодня: {details.get('todayReferralEarnings')}")
        print(Fore.CYAN + f"  Заработок за время работы: {details.get('todayUptimeEarnings')}")
        print(Fore.CYAN + f"  Активная ставка: {active_rate} в минуту")
        print(Fore.CYAN + f"  Оценка заработка за сессию: {earnings:.4f}")
        print(Fore.CYAN + f"  Время работы: {self.uptime_minutes} минут")
        print(Fore.CYAN + f"  Ранг: {details.get('rank')}")
        print(Fore.MAGENTA + f"  Поинты: {points}\n")

    def start_heartbeat_cycle(self):
        # Запускаем отдельный поток для отправки ping каждые 5-10 секунд
        ping_thread = threading.Thread(target=self.ping_loop, daemon=True)
        ping_thread.start()
        try:
            self.toggle_device("ON")
            self.send_heartbeat()
            while True:
                time.sleep(APP_КОНФИГ["heartbeat_interval"])
                self.uptime_minutes += 1
                if not self.toggle_state:
                    self.toggle_device("ON")
                self.send_heartbeat()
                self.get_wallet_details()
                current_time = datetime.now().strftime("%H:%M:%S")
                print(Fore.GREEN + f"[{current_time}] Прошла {self.uptime_minutes} минута(ы).")
        except KeyboardInterrupt:
            print(Fore.YELLOW + f"\nБот остановлен. Итоговое время работы: {self.uptime_minutes} минут")
            self.toggle_device("OFF")
            exit(0)
        except Exception as e:
            print(Fore.RED + f"[ОШИБКА] Цикл Heartbeat: {e}")

def показать_меню() -> str:
    """Отображает интерактивное меню и возвращает выбор пользователя."""
    print(Fore.MAGENTA + "\n╔═════════════════════════════════════════╗")
    print(Fore.MAGENTA + "║             ГЛАВНОЕ МЕНЮ                ║")
    print(Fore.MAGENTA + "╠═════════════════════════════════════════╣")
    print(Fore.YELLOW + "║ 1. Запустить бота                       ║")
    print(Fore.YELLOW + "║ 2. Выход                                ║")
    print(Fore.MAGENTA + "╚═════════════════════════════════════════╝")
    choice = input(Fore.CYAN + "Ваш выбор (1/2): ").strip()
    return choice

def main():
    показать_баннер()
    while True:
        choice = показать_меню()
        if choice == "1":
            использовать_прокси = спросить_о_прокси()
            try:
                with open("accounts.json", "r", encoding="utf-8") as f:
                    accounts_data = json.load(f)
            except Exception as e:
                print(Fore.RED + f"[ОШИБКА] Не удалось загрузить accounts.json: {e}")
                exit(1)
            
            accounts = []
            for entry in accounts_data:
                if "Address" not in entry or "deviceHash" not in entry:
                    print(Fore.RED + f"[ОШИБКА] Неверный формат аккаунта: {entry}")
                    continue
                accounts.append({
                    "token": entry.get("token", ""),
                    "decoded": {"wallet_address": entry["Address"]},
                    "wallet_address": entry["Address"],
                    "deviceHash": entry["deviceHash"]
                })
            if not accounts:
                print(Fore.RED + "[ОШИБКА] Нет валидных аккаунтов в accounts.json")
                exit(1)
            print(Fore.CYAN + f"[ИНФО] Загружено {len(accounts)} аккаунтов из {APP_КОНФИГ['data_file']}.")
            
            proxies = DeviceHeartbeatBot.load_proxies() if использовать_прокси else []

            bots = []
            for idx, account in enumerate(accounts):
                proxy = proxies[idx % len(proxies)] if proxies else None
                bot = DeviceHeartbeatBot(account, proxy)
                bots.append(bot)

            threads = []
            for bot in bots:
                t = threading.Thread(target=bot.start_heartbeat_cycle, daemon=True)
                t.start()
                threads.append(t)

            try:
                for t in threads:
                    t.join()
            except KeyboardInterrupt:
                print(Fore.YELLOW + "\nЗавершение работы ботов.")
            break
        elif choice == "2":
            print(Fore.YELLOW + "Выход из программы...")
            exit(0)
        else:
            print(Fore.RED + "Неверный выбор. Попробуйте снова.")

if __name__ == "__main__":
    main()
