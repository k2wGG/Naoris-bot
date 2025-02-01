# Naoris Protocol Automation Bot / Автоматизация бота Naoris Protocol RU\ENG

Этот бот предназначен для автоматизации процесса heartbeat в протоколе Naoris. Бот будет периодически отправлять heartbeat для каждого зарегистрированного аккаунта, с поддержкой прокси для повышения приватности и безопасности.

This bot is designed to automate the heartbeat process on the Naoris Protocol. The bot will periodically send heartbeats for each registered account, with proxy support to enhance privacy and security.

---

## **Функции / Features**

- **Автоматическая отправка heartbeat.**  
  *Automatic sending of heartbeat.*

- **Поддержка использования прокси (HTTP, SOCKS4, SOCKS5).**  
  *Supports proxy usage (HTTP, SOCKS4, SOCKS5).*

- **Отображение статуса аккаунта и логов активности.**  
  *Displays account status and activity logs.*

- **Поддержка нескольких кошельков с разными цветами для каждого.**  
  *Multi-wallet support with different colors for each wallet.*

---

## **Требования / Requirements**

- **Python 3.7 или выше.**  
  *Python 3.7 or higher.*

- **Необходимые модули Python (см. ниже).**  
  *Required Python modules (see below).*

- **Прокси (если есть).**  
  *Proxy (if available).*

---

## **Установка / Installation**

1. **Клонирование репозитория и установка модулей / Clone Repository & Install Modules:**

   ```bash
   git clone https://github.com/k2wGG/Naoris-bot.git
   cd Naoris-bot
   ```
   ```bash
   pip install requests requests[socks] colorama pyjwt
   ```
---

2. **Запуск / How to Run**
- Получите токен, нажав F12 в расширении Naoris Protocol Node (пример токена начинается с "ey").

- Retrieve the token by inspecting it using the Naoris Protocol Node extension (example token starting with "ey").
![1](https://github.com/user-attachments/assets/4b9b53b1-7bdb-4073-9657-5476e24b380b)

- После получения токена вставьте его в файл data.txt.
- After obtaining the token, insert it into data.txt.

- Если есть прокси, добавьте их в файл proxy.txt в следующем формате (необязательно):
- If you have proxies, add them to proxy.txt in the following format (OPTIONAL):
```bash
http://username:password@host:port
http://host:port
socks4://username:password@host:port
socks4://host:port
socks5://username:password@host:port
socks5://host:port
```
- Запустите бота: / Run: 
```bash
Python main.py
```
