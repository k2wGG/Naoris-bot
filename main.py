import uuid
import jwt
import time
import requests
from datetime import datetime
from typing import List, Optional
from colorama import init, Fore, Style
import os

# Инициализация colorama
init(autoreset=True)


def display_banner():
    """Отображает баннер при запуске программы."""
    print(Fore.GREEN + "[+]===============================[+]")
    print(Fore.GREEN + "[+]  NAORIS PROTOCOL АВТОФАРМ     [+]")
    print(Fore.GREEN + "[+]     https://t.me/nod3r        [+]")
    print(Fore.GREEN + "[+]===============================[+]")
    print()  

# Утилиты
def generate_device_hash() -> str:
    """Генерирует уникальный хеш устройства."""
    return str(int(uuid.uuid4().hex.replace("-", "")[:8], 16))

def decode_token(token: str) -> Optional[dict]:
    """Декодирует JWT токен и извлекает соответствующие данные."""
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
        print(f"{Fore.RED}[ERROR] Ошибка декодирования токена: {e}")
        return None

def is_token_expired(account: dict) -> bool:
    """Проверяет, истёк ли токен аккаунта."""
    if not account.get("decoded") or not account["decoded"].get("exp"):
        return True
    return time.time() >= account["decoded"]["exp"]

def load_proxies(proxy_file: str) -> List[str]:
    """Загружает прокси из текстового файла."""
    try:
        with open(proxy_file, "r") as file:
            proxies = [line.strip() for line in file if line.strip()]
        return proxies
    except Exception as e:
        print(f"{Fore.RED}[ERROR] Не удалось загрузить прокси: {e}")
        return []

def ask_proxy_usage():
    """Спрашивает пользователя, хочет ли он использовать прокси."""
    while True:
        choice = input(f"{Fore.CYAN}[?] Хотите использовать прокси? (y/n): ").strip().lower()
        if choice in ["y", "n"]:
            return choice == "y"
        else:
            print(f"{Fore.RED}[ERROR] Введите 'y' для Да или 'n' для Нет.")

# Конфигурация
API_CONFIG = {
    "base_url": "https://naorisprotocol.network",
    "endpoints": {
        "heartbeat": "/sec-api/api/produce-to-kafka",
    },
    "headers": {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "chrome-extension://cpikainghpmifinihfeigiboilmmp",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    },
}

APP_CONFIG = {
    "heartbeat_interval": 6000,  # 6 секунд
    "data_file": "data.txt",  
    "proxy_file": "proxy.txt",  
}

# Сервис Heartbeat с поддержкой прокси
class HeartbeatService:
    def __init__(self, use_proxy: bool):
        self.accounts: List[dict] = []
        self.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.wallet_colors = [Fore.GREEN, Fore.CYAN]  # Цвет для каждого кошелька
        self.proxies = load_proxies(APP_CONFIG["proxy_file"]) if use_proxy else []
        self.use_proxy = use_proxy

    def load_accounts(self):
        """Загружает аккаунты из файла данных."""
        try:
            with open(APP_CONFIG["data_file"], "r") as file:
                tokens = file.read().splitlines()

            self.accounts = []
            for idx, token in enumerate(tokens):
                decoded = decode_token(token.strip())
                if not decoded or not decoded.get("wallet_address"):
                    print(f"{Fore.RED}[ERROR] Не удалось декодировать токен: {token[:20]}...")
                    continue

                # Назначает прокси для аккаунта (если используется прокси)
                proxy = self.proxies[idx % len(self.proxies)] if self.use_proxy and self.proxies else None

                self.accounts.append({
                    "token": token.strip(),
                    "decoded": decoded,
                    "device_hash": generate_device_hash(),
                    "status": "initialized",
                    "wallet_number": idx + 1,  # Номер кошелька (Кошелек 1, Кошелек 2)
                    "proxy": proxy,  
                })

            if not self.accounts:
                raise ValueError("Не загружено ни одного валидного аккаунта")

            print(f"{Fore.CYAN}[INFO] Успешно загружено {len(self.accounts)} аккаунтов.")
        except Exception as e:
            print(f"{Fore.RED}[ERROR] Ошибка при загрузке аккаунтов: {e}")
            raise

    def get_session(self, proxy: Optional[str] = None):
        """Создает сессию requests с поддержкой прокси."""
        session = requests.Session()
        if proxy:
            session.proxies = {
                "http": proxy,
                "https": proxy,
            }
        return session

    def send_heartbeat(self, account: dict):
        """Отправляет запрос heartbeat для данного аккаунта."""
        try:
            session = self.get_session(account["proxy"])
            headers = API_CONFIG["headers"].copy()
            headers["Authorization"] = f"Bearer {account['token']}"
            payload = {
                "topic": "device-heartbeat",
                "deviceHash": account["device_hash"],
                "walletAddress": account["decoded"]["wallet_address"],
            }
            response = session.post(
                f"{API_CONFIG['base_url']}{API_CONFIG['endpoints']['heartbeat']}",
                headers=headers,
                json=payload,
            )
            account["last_heartbeat"] = datetime.now().strftime("%H:%M:%S")
            account["status"] = "active"

            wallet_color = self.wallet_colors[(account["wallet_number"] - 1) % len(self.wallet_colors)]

            # Отображает сообщение об успешной отправке, с использованием прокси или без него
            if account["proxy"]:
                print(f"{wallet_color}[SUCCESS] Кошелек {account['wallet_number']}: Heartbeat отправлен для кошелька {account['decoded']['wallet_address']} (с прокси)")
            else:
                print(f"{wallet_color}[SUCCESS] Кошелек {account['wallet_number']}: Heartbeat отправлен для кошелька {account['decoded']['wallet_address']} (без прокси)")

            return response.json()
        except Exception as e:
            account["status"] = "error"
            print(f"{Fore.RED}[ERROR] Кошелек {account['wallet_number']}: Ошибка при отправке heartbeat для кошелька {account['decoded']['wallet_address']}: {e}")
            return None

    def start(self):
        """Запускает сервис heartbeat."""
        self.load_accounts()
        print(f"{Fore.CYAN}[INFO] Сервис heartbeat запущен в {self.start_time}.")

        # Отображает активные аккаунты (без специального выделения)
        print(f"\n[ACCOUNTS] Активные аккаунты:")
        for account in self.accounts:
            last_heartbeat = account.get("last_heartbeat", "Никогда")
            exp_date = datetime.fromtimestamp(account["decoded"]["exp"]).strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"  - Кошелек {account['wallet_number']}: {account['decoded']['wallet_address'][:10]}... | "
                f"Последний Heartbeat: {last_heartbeat} | "
                f"Истекает: {exp_date} | "
                f"Статус: {account.get('status', 'ожидание')}"
            )

        # Пустая строка перед началом отправки heartbeat
        print()

        # Начинает отправку heartbeat
        while True:
            for account in self.accounts:
                if is_token_expired(account):
                    print(f"{Fore.YELLOW}[WARNING] Кошелек {account['wallet_number']}: Токен истек для кошелька {account['decoded']['wallet_address']}")
                    account["status"] = "expired"
                    continue

                self.send_heartbeat(account)
                time.sleep(1)  # Задержка 1 секунда между аккаунтами

            time.sleep(APP_CONFIG["heartbeat_interval"] / 1000)  # Задержка согласно интервалу

# Основная функция для запуска бота
def main():
    """Основная функция для запуска бота."""
    display_banner()  # Отображает баннер

    # Спрашивает пользователя, хочет ли он использовать прокси
    use_proxy = ask_proxy_usage()

    # Запускает сервис heartbeat
    service = HeartbeatService(use_proxy)
    try:
        service.start()
    except KeyboardInterrupt:
        print(f"\n{Fore.CYAN}[INFO] Сервис heartbeat остановлен.")

if __name__ == "__main__":
    main()
