"""
Простая программа для тестирования прокси в браузере Firefox.
Введите прокси, и откроется Firefox с этим прокси.
"""

import subprocess
import sys
import os
import platform


def parse_proxy(proxy_input: str) -> dict:
    """
    Парсит прокси в формате:
    - host:port
    - user:pass@host:port
    - http://host:port
    - socks5://host:port
    """
    proxy_input = proxy_input.strip()
    
    # Убираем протокол если есть
    if proxy_input.startswith("http://"):
        proxy_input = proxy_input[7:]
        proxy_type = "http"
    elif proxy_input.startswith("https://"):
        proxy_input = proxy_input[8:]
        proxy_type = "http"
    elif proxy_input.startswith("socks5://"):
        proxy_input = proxy_input[9:]
        proxy_type = "socks5"
    elif proxy_input.startswith("socks4://"):
        proxy_input = proxy_input[9:]
        proxy_type = "socks4"
    else:
        proxy_type = "http"  # По умолчанию HTTP
    
    # Проверяем наличие авторизации
    if "@" in proxy_input:
        auth_part, host_part = proxy_input.split("@", 1)
        if ":" in auth_part:
            username, password = auth_part.split(":", 1)
        else:
            username = auth_part
            password = ""
    else:
        username = ""
        password = ""
        host_part = proxy_input
    
    # Парсим host:port
    if ":" in host_part:
        host, port = host_part.split(":", 1)
    else:
        host = host_part
        port = "8080"  # Порт по умолчанию
    
    return {
        "type": proxy_type,
        "host": host,
        "port": port,
        "username": username,
        "password": password,
    }


def open_firefox_with_proxy(proxy_info: dict):
    """Открывает Firefox с указанным прокси."""
    
    system = platform.system().lower()
    
    # Определяем путь к Firefox
    if system == "windows":
        # Стандартные пути Firefox на Windows
        firefox_paths = [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            os.path.expanduser(r"~\AppData\Local\Mozilla Firefox\firefox.exe"),
        ]
    elif system == "darwin":  # macOS
        firefox_paths = [
            "/Applications/Firefox.app/Contents/MacOS/firefox",
        ]
    else:  # Linux
        firefox_paths = [
            "/usr/bin/firefox",
            "/usr/local/bin/firefox",
        ]
    
    firefox_exe = None
    for path in firefox_paths:
        if os.path.exists(path):
            firefox_exe = path
            break
    
    if not firefox_exe:
        print("❌ Firefox не найден!")
        print("Установите Firefox или укажите путь к firefox.exe вручную")
        return False
    
    # Формируем параметры прокси для Firefox
    proxy_host = proxy_info["host"]
    proxy_port = proxy_info["port"]
    proxy_type = proxy_info["type"]
    
    # Firefox использует параметры командной строки для прокси
    # Для HTTP прокси
    if proxy_type in ["http", "https"]:
        proxy_arg = f"--proxy-server={proxy_type}://{proxy_host}:{proxy_port}"
    elif proxy_type == "socks5":
        proxy_arg = f"--proxy-server=socks5://{proxy_host}:{proxy_port}"
    elif proxy_type == "socks4":
        proxy_arg = f"--proxy-server=socks4://{proxy_host}:{proxy_port}"
    else:
        proxy_arg = f"--proxy-server=http://{proxy_host}:{proxy_port}"
    
    # Если есть авторизация, нужно использовать профиль с настройками
    if proxy_info["username"]:
        print("⚠️  Авторизация прокси через командную строку не поддерживается.")
        print("   Firefox откроется с прокси, но авторизацию нужно будет ввести вручную.")
        print(f"   Логин: {proxy_info['username']}")
        print(f"   Пароль: {proxy_info['password']}")
    
    try:
        # Запускаем Firefox с прокси
        cmd = [firefox_exe, proxy_arg, "--new-instance"]
        
        print(f"🚀 Запускаю Firefox с прокси: {proxy_type}://{proxy_host}:{proxy_port}")
        
        if system == "windows":
            # На Windows используем CREATE_NO_WINDOW чтобы не показывать консоль
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("✅ Firefox запущен!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при запуске Firefox: {e}")
        return False


def main():
    """Главная функция."""
    print("=" * 60)
    print("  ПРОГРАММА ДЛЯ ТЕСТИРОВАНИЯ ПРОКСИ В FIREFOX")
    print("=" * 60)
    print()
    print("Форматы прокси:")
    print("  - host:port")
    print("  - user:pass@host:port")
    print("  - http://host:port")
    print("  - socks5://host:port")
    print()
    
    while True:
        try:
            proxy_input = input("Введите прокси (или 'exit' для выхода): ").strip()
            
            if proxy_input.lower() in ["exit", "quit", "q", "выход"]:
                print("До свидания!")
                break
            
            if not proxy_input:
                print("❌ Прокси не может быть пустым!")
                continue
            
            # Парсим прокси
            proxy_info = parse_proxy(proxy_input)
            
            print()
            print(f"📋 Прокси: {proxy_info['type']}://{proxy_info['host']}:{proxy_info['port']}")
            if proxy_info["username"]:
                print(f"   Логин: {proxy_info['username']}")
            
            print()
            
            # Открываем Firefox
            success = open_firefox_with_proxy(proxy_info)
            
            if success:
                print()
                print("💡 Для проверки прокси откройте: https://whatismyipaddress.com/")
                print()
            
            # Спрашиваем, хотите ли еще один прокси
            if success:
                again = input("Открыть еще один прокси? (y/n): ").strip().lower()
                if again not in ["y", "yes", "да", "д"]:
                    break
            
        except KeyboardInterrupt:
            print("\n\nДо свидания!")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            print()


if __name__ == "__main__":
    main()

