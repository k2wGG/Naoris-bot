import threading  # Для работы с потоками
import uuid
import time
import json
import random
import jwt
import cloudscraper
import os
from datetime import datetime
from typing import List, Optional
from colorama import init, Fore

# Инициализация colorama для цветного вывода
init(autoreset=True)

SESSION_FILE = "wallet_session.json"

def display_banner():
    print(Fore.GREEN + "[+]===============================[+]")
    print(Fore.GREEN + "[+]  NAORIS PROTOCOL АВТОФАРМ     [+]")
    print(Fore.GREEN + "[+]     https://t.me/nod3r        [+]")
    print(Fore.GREEN + "[+]===============================[+]")
    print()

def generate_device_hash() -> str:
    """Генерирует уникальный хеш устройства."""
    return str(int(uuid.uuid4().hex.replace("-", "")[:8], 16))

def decode_token(token: str) -> Optional[dict]:
    """Декодирует JWT-токен без проверки подписи (используется в старом формате)."""
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
        print(Fore.RED + f"[ERROR] Ошибка декодирования токена: {e}")
        return None

def is_token_expired(account: dict) -> bool:
    """Проверяет, истёк ли токен аккаунта."""
    if not account.get("decoded") or not account["decoded"].get("exp"):
        return True
    return time.time() >= account["decoded"]["exp"]

def load_proxies(proxy_file: str) -> List[str]:
    """
    Загружает прокси из текстового файла и нормализует их формат.
    Если строка не содержит '://', добавляет 'http://'.
    """
    proxies = []
    try:
        with open(proxy_file, "r", encoding="utf-8") as file:
            for line in file:
                proxy = line.strip()
                if not proxy:
                    continue
                if "://" not in proxy:
                    proxy = "http://" + proxy
                proxies.append(proxy)
        return proxies
    except Exception as e:
        print(Fore.RED + f"[ERROR] Не удалось загрузить прокси: {e}")
        return []

def ask_proxy_usage() -> bool:
    """Спрашивает пользователя, хочет ли он использовать прокси."""
    while True:
        choice = input(Fore.CYAN + "[?] Хотите использовать прокси? (y/n): ").strip().lower()
        if choice in ["y", "n"]:
            return choice == "y"
        else:
            print(Fore.RED + "Введите 'y' для Да или 'n' для Нет.")

def get_realistic_headers(identifier: str) -> dict:
    """Формирует реалистичные заголовки для запросов."""
    return {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "chrome-extension://cpikalnagknmlfhnilhfelifgbollmmp",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        "Authorization": f"Bearer {identifier}"
    }

# Конфигурация API и приложения
API_CONFIG = {
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

APP_CONFIG = {
    "heartbeat_interval": 1500,  # базовый интервал (4.5 секунд)
    "data_file": "accounts.json",   # Файл с аккаунтами (формат: [{ "Address": ..., "deviceHash": ..., "token": "..." }, ...])
    "proxy_file": "proxy.txt",
    "session_refresh_interval": 5,
}

class DeviceHeartbeatBot:
    def __init__(self, account: dict, proxy: Optional[str] = None):
        self.account = account
        self.proxy = proxy
        self.uptime_minutes = 0
        self.deviceHash = account.get("deviceHash") or generate_device_hash()
        self.toggle_state = True  # по умолчанию ON
        self.whitelisted_urls = ["naorisprotocol.network", "google.com"]
        self.is_installed = True
        self.scraper = self.create_scraper(self.proxy)
        self.load_wallet_session()
        try:
            self.scraper.get(API_CONFIG["base_url"], timeout=30)
            print(Fore.CYAN + "[INFO] Сессия успешно разогрета.")
        except Exception as e:
            print(Fore.YELLOW + f"[WARNING] Не удалось разогреть сессию: {e}")

    def save_wallet_session(self):
        """Сохраняет cookies (сессионные данные) в файл."""
        try:
            cookies = self.scraper.cookies.get_dict()
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(cookies, f)
            print(Fore.CYAN + f"[INFO] Сессионные данные сохранены в {SESSION_FILE}")
        except Exception as e:
            print(Fore.YELLOW + f"[WARNING] Не удалось сохранить сессионные данные: {e}")

    def load_wallet_session(self):
        """Загружает cookies (сессионные данные) из файла, если он существует."""
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                self.scraper.cookies.update(cookies)
                print(Fore.CYAN + f"[INFO] Сессионные данные загружены из {SESSION_FILE}")
            except Exception as e:
                print(Fore.YELLOW + f"[WARNING] Не удалось загрузить сессионные данные: {e}")

    @staticmethod
    def load_accounts(data_file: str = APP_CONFIG["data_file"]) -> List[dict]:
        """
        Загружает аккаунты из файла accounts.json.
        Формат файла:
        [
            {
                "Address": "Your evm address 1",
                "deviceHash": "Your device hash 1",
                "token": "JWT token (опционально)"
            },
            {
                "Address": "Your evm address 2",
                "deviceHash": "Your device hash 2",
                "token": "JWT token (опционально)"
            }
        ]
        """
        accounts = []
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data:
                if "Address" not in entry or "deviceHash" not in entry:
                    print(Fore.RED + f"[ERROR] Неверный формат аккаунта: {entry}")
                    continue
                accounts.append({
                    "token": entry.get("token", ""),
                    "decoded": {"wallet_address": entry["Address"]},
                    "wallet_address": entry["Address"],
                    "deviceHash": entry["deviceHash"]
                })
            if not accounts:
                raise ValueError("Не загружено ни одного валидного аккаунта")
            print(Fore.CYAN + f"[INFO] Успешно загружено {len(accounts)} аккаунтов из {APP_CONFIG['data_file']}.")
            return accounts
        except Exception as e:
            print(Fore.RED + f"[ERROR] Не удалось загрузить аккаунты: {e}")
            exit(1)

    @staticmethod
    def load_proxies(proxy_file: str = APP_CONFIG["proxy_file"]) -> List[str]:
        return load_proxies(proxy_file)

    def get_request_headers(self) -> dict:
        identifier = self.account.get("token") or self.account.get("wallet_address")
        headers = get_realistic_headers(identifier)
        headers["Referer"] = API_CONFIG["base_url"]
        return headers

    def create_scraper(self, proxy: Optional[str] = None):
        scraper = cloudscraper.create_scraper(delay=10, browser={'custom': 'Chrome/132.0.0.0'})
        if proxy:
            scraper.proxies = {"http": proxy, "https": proxy}
        return scraper

    def refresh_session(self):
        """Обновляет сессию через GET на базовый URL."""
        try:
            self.scraper.get(API_CONFIG["base_url"], timeout=30)
            print(Fore.CYAN + "[INFO] Сессия обновлена (GET на базовый URL).")
        except Exception as e:
            print(Fore.YELLOW + f"[WARNING] Не удалось обновить сессию: {e}")

    def toggle_device(self, state: str = "ON"):
        try:
            print(Fore.CYAN + f"Отправка запроса Toggle ({state}) для {self.account['wallet_address']}...")
            payload = {
                "walletAddress": self.account["wallet_address"],
                "state": state,
                "deviceHash": self.deviceHash
            }
            response = self.scraper.post(
                f"{API_CONFIG['base_url']}{API_CONFIG['endpoints']['toggle']}",
                json=payload,
                headers=self.get_request_headers(),
                timeout=30
            )
            self.toggle_state = (state.upper() == "ON")
            print(Fore.GREEN + f"[✔] Toggle {state} выполнен. Ответ: {response}")
            self.save_wallet_session()
        except Exception as e:
            print(Fore.RED + f"[✖] Toggle Error: {e}")

    def send_heartbeat(self):
        try:
            self.refresh_session()
            print(Fore.CYAN + "Отправка Heartbeat...")
            payload = {
                "topic": "device-heartbeat",
                "inputData": {
                    "walletAddress": self.account["wallet_address"],
                    "deviceHash": str(self.account.get("deviceHash") or generate_device_hash()),
                    "isInstalled": self.is_installed,
                    "toggleState": self.toggle_state,
                    "whitelistedUrls": self.whitelisted_urls,
                    "timestamp": int(time.time()),
                    "clientVersion": "4.30.0"
                }
            }
            response = self.scraper.post(
                f"{API_CONFIG['base_url']}{API_CONFIG['endpoints']['heartbeat']}",
                json=payload,
                headers=self.get_request_headers(),
                timeout=30
            )
            if response.status_code == 401:
                print(Fore.YELLOW + "[WARNING] Heartbeat вернул 401. Восстанавливаем сессию через toggle.")
                self.toggle_device("ON")
            print(Fore.GREEN + f"[✔] Heartbeat отправлен. Ответ: {response}")
        except Exception as e:
            print(Fore.RED + f"[✖] Heartbeat Error: {e}")

    def send_ping(self):
        """
        Отправляет пинг-запрос для эмуляции активности.
        Используем топик "ping" с дополнительными полями.
        """
        try:
            print(Fore.CYAN + "Отправка Ping...")
            payload = {
                "topic": "ping",
                "inputData": {
                    "walletAddress": self.account["wallet_address"],
                    "deviceHash": str(self.account.get("deviceHash") or generate_device_hash()),
                    "timestamp": int(time.time()),
                    "clientVersion": "4.30.0"
                }
            }
            response = self.scraper.post(
                f"{API_CONFIG['base_url']}{API_CONFIG['endpoints']['heartbeat']}",
                json=payload,
                headers=self.get_request_headers(),
                timeout=30
            )
            print(Fore.GREEN + f"[✔] Ping отправлен. Ответ: {response}")
        except Exception as e:
            print(Fore.RED + f"[✖] Ping Error: {e}")

    def ping_loop(self):
        """Петля, отправляющая пинг каждые 5-10 секунд."""
        while True:
            time.sleep(random.uniform(1, 5))
            self.send_ping()

    def get_wallet_details(self):
        try:
            payload = {"walletAddress": self.account["wallet_address"]}
            response = self.scraper.post(
                f"{API_CONFIG['base_url']}{API_CONFIG['endpoints']['walletDetails']}",
                json=payload,
                headers=self.get_request_headers(),
                timeout=30
            )
            try:
                data = response.json()
            except Exception as json_err:
                print(Fore.RED + f"[✖] Wallet Details JSON Parse Error: {json_err}")
                return

            if not data.get("error", False):
                details = data.get("details", {})
                self.log_wallet_details(details)
            else:
                print(Fore.RED + f"[✖] Wallet Details Error: {data}")
        except Exception as e:
            print(Fore.RED + f"[✖] Wallet Details Fetch Error: {e}")

    def log_wallet_details(self, details: dict):
        active_rate = details.get("activeRatePerMinute", 0)
        earnings = self.uptime_minutes * active_rate
        print("\n" + Fore.WHITE + f"📊 Wallet Details for {self.account['wallet_address']}:")
        print(Fore.CYAN + f"  Total Earnings: {details.get('totalEarnings')}")
        print(Fore.CYAN + f"  Today's Earnings: {details.get('todayEarnings')}")
        print(Fore.CYAN + f"  Today's Referral Earnings: {details.get('todayReferralEarnings')}")
        print(Fore.CYAN + f"  Today's Uptime Earnings: {details.get('todayUptimeEarnings')}")
        print(Fore.CYAN + f"  Active Rate: {active_rate} per minute")
        print(Fore.CYAN + f"  Estimated Session Earnings: {earnings:.4f}")
        print(Fore.CYAN + f"  Uptime: {self.uptime_minutes} minutes")
        print(Fore.CYAN + f"  Rank: {details.get('rank')}\n")

    def start_heartbeat_cycle(self):
        # Запускаем отдельный поток для отправки пинга каждые 5-10 секунд
        ping_thread = threading.Thread(target=self.ping_loop, daemon=True)
        ping_thread.start()
        try:
            self.toggle_device("ON")
            self.send_heartbeat()
            while True:
                time.sleep(30)
                self.uptime_minutes += 1
                if not self.toggle_state:
                    self.toggle_device("ON")
                self.send_heartbeat()
                self.get_wallet_details()
                current_time = datetime.now().strftime("%H:%M:%S")
                print(f"{Fore.GREEN}[{current_time}] Minute {self.uptime_minutes} completed.")
        except KeyboardInterrupt:
            print(Fore.YELLOW + f"\nBot остановлен. Финальный uptime: {self.uptime_minutes} минут")
            self.toggle_device("OFF")
            exit(0)
        except Exception as e:
            print(Fore.RED + f"[✖] Heartbeat Cycle Error: {e}")

def main():
    display_banner()
    use_proxy = ask_proxy_usage()
    try:
        with open("accounts.json", "r", encoding="utf-8") as f:
            accounts_data = json.load(f)
    except Exception as e:
        print(Fore.RED + f"[ERROR] Не удалось загрузить accounts.json: {e}")
        exit(1)
    
    accounts = []
    for entry in accounts_data:
        if "Address" not in entry or "deviceHash" not in entry:
            print(Fore.RED + f"[ERROR] Неверный формат аккаунта: {entry}")
            continue
        accounts.append({
            "token": entry.get("token", ""),
            "decoded": {"wallet_address": entry["Address"]},
            "wallet_address": entry["Address"],
            "deviceHash": entry["deviceHash"]
        })
    if not accounts:
        print(Fore.RED + "[ERROR] Нет валидных аккаунтов в accounts.json")
        exit(1)
    print(Fore.CYAN + f"[INFO] Загружено {len(accounts)} аккаунтов из accounts.json.")
    
    proxies = DeviceHeartbeatBot.load_proxies() if use_proxy else []

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

if __name__ == "__main__":
    main()
