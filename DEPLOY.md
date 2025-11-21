# 🚀 Развертывание бота на Яндекс.Облако

## 📦 Работа с GitHub

### Первая загрузка кода на GitHub

1. **Инициализация репозитория (если еще не сделано):**
```bash
cd C:\Users\uirya\Desktop\Girl-Guy.Ai
git init
git add .
git commit -m "Initial commit"
```

2. **Подключение к GitHub репозиторию:**
```bash
git remote add origin https://github.com/DangerZoneOff/girl-guy.ai.git
git branch -M main
git push -u origin main
```

**Если репозиторий уже существует и нужно обновить:**
```bash
git remote set-url origin https://github.com/DangerZoneOff/girl-guy.ai.git
git push -u origin main
```

### Обновление кода на GitHub

После внесения изменений в код:

```bash
# Перейти в папку проекта
cd C:\Users\uirya\Desktop\Girl-Guy.Ai

# Посмотреть изменения
git status

# Добавить все изменения
git add .

# Создать коммит
git commit -m "Описание изменений"

# Отправить на GitHub
git push origin main
```

### Клонирование с GitHub на сервер

```bash
cd ~
git clone https://github.com/DangerZoneOff/girl-guy.ai.git
cd girl-guy.ai
```

---

## ☁️ Работа через Cloud Shell (Яндекс.Облако)

### Подключение к Cloud Shell

1. Откройте [консоль Яндекс.Облака](https://console.cloud.yandex.ru/)
2. Нажмите на иконку **Cloud Shell** в правом верхнем углу (терминал)
3. Cloud Shell откроется в браузере

### Первая настройка на сервере через Cloud Shell

1. **Подключитесь к вашей виртуальной машине:**
```bash
ssh ubuntu@ваш_внешний_IP
```

2. **Обновите систему:**
```bash
sudo apt update
sudo apt upgrade -y
```

3. **Установите Git (если еще не установлен):**
```bash
sudo apt install -y git python3.11 python3.11-venv python3-pip
```

4. **Клонируйте проект с GitHub:**
```bash
cd ~
git clone https://github.com/DangerZoneOff/girl-guy.ai.git
cd girl-guy.ai
```

5. **Создайте виртуальное окружение:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

6. **Создайте файл `.env`:**
```bash
nano .env
```

Добавьте туда (замените на свои значения):
```env
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TELEGRAM_BOT_USERNAME=имя_вашего_бота_без_@
OPENROUTER_API_KEY=ваш_ключ_openrouter

STORAGE_TYPE=yandex
YANDEX_BUCKET=имя_вашего_бакета
YANDEX_ACCESS_KEY_ID=ваш_access_key
YANDEX_SECRET_ACCESS_KEY=ваш_secret_key
YANDEX_REGION=ru-central1
YANDEX_ENDPOINT=https://storage.yandexcloud.net
```

**Сохранение в nano:** `Ctrl + O`, `Enter`, `Ctrl + X`

7. **Загрузите базы данных из бакета (если нужно):**
Базы данных будут автоматически загружены при первом запуске, если их нет локально.

---

## 🔄 Обновление кода на сервере через Cloud Shell

### Способ 1: Через Git (рекомендуется)

1. **Откройте Cloud Shell** в консоли Яндекс.Облака
2. **Подключитесь к серверу:**
```bash
ssh ubuntu@ваш_внешний_IP
```

3. **Перейдите в папку проекта:**
```bash
cd ~/girl-guy.ai
```

4. **Остановите бота (если запущен через systemd):**
```bash
sudo systemctl stop bot.service
```

5. **Обновите код с GitHub:**
```bash
git pull origin main
```

6. **Активируйте виртуальное окружение и обновите зависимости (если нужно):**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

7. **Запустите бота снова:**
```bash
sudo systemctl start bot.service
```

8. **Проверьте статус:**
```bash
sudo systemctl status bot.service
```

### Способ 2: Прямая загрузка через Cloud Shell

Если нужно загрузить файлы напрямую:

1. **В Cloud Shell загрузите файлы:**
   - Нажмите на иконку загрузки (стрелка вверх) в Cloud Shell
   - Выберите файлы с вашего компьютера

2. **На сервере переместите файлы:**
```bash
# Остановите бота
sudo systemctl stop bot.service

# Скопируйте файлы в нужную папку
cp загруженный_файл.py ~/girl-guy.ai/

# Запустите бота
sudo systemctl start bot.service
```

---

## 🗄️ Работа с базами данных

### Загрузка БД из бакета Яндекса

Базы данных (`users.db` и `pers/personas.db`) автоматически загружаются из бакета при старте бота, если их нет локально.

**Путь в бакете:**
- `databases/users.db`
- `databases/personas.db`

### Ручная загрузка БД из бакета

Если нужно загрузить БД вручную:

```bash
# Установите AWS CLI (если еще не установлен)
sudo apt install -y awscli

# Настройте доступ (используйте ключи из .env)
aws configure --profile yandex
# AWS Access Key ID: ваш YANDEX_ACCESS_KEY_ID
# AWS Secret Access Key: ваш YANDEX_SECRET_ACCESS_KEY
# Default region: ru-central1

# Или используйте переменные окружения
export AWS_ACCESS_KEY_ID=ваш_ключ
export AWS_SECRET_ACCESS_KEY=ваш_секрет
export AWS_DEFAULT_REGION=ru-central1

# Загрузите БД
aws --endpoint-url=https://storage.yandexcloud.net s3 cp s3://имя_бакета/databases/users.db ~/girl-guy.ai/users.db
aws --endpoint-url=https://storage.yandexcloud.net s3 cp s3://имя_бакета/databases/personas.db ~/girl-guy.ai/pers/personas.db
```

### Сохранение БД в бакет

БД автоматически сохраняются в бакет при остановке бота.

**Ручное сохранение:**
```bash
aws --endpoint-url=https://storage.yandexcloud.net s3 cp ~/girl-guy.ai/users.db s3://имя_бакета/databases/users.db
aws --endpoint-url=https://storage.yandexcloud.net s3 cp ~/girl-guy.ai/pers/personas.db s3://имя_бакета/databases/personas.db
```

---

## 🚀 Настройка автозапуска (systemd)

Создайте сервис для автозапуска:

```bash
sudo nano /etc/systemd/system/bot.service
```

Добавьте:
```ini
[Unit]
Description=Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/girl-guy.ai
Environment="PATH=/home/ubuntu/girl-guy.ai/venv/bin"
ExecStart=/home/ubuntu/girl-guy.ai/venv/bin/python /home/ubuntu/girl-guy.ai/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Важно:** Замените `/home/ubuntu/girl-guy.ai` на реальный путь к вашему проекту!

Затем:
```bash
sudo systemctl daemon-reload
sudo systemctl enable bot.service
sudo systemctl start bot.service
sudo systemctl status bot.service
```

---

## 📋 Полезные команды

### Управление ботом
```bash
# Посмотреть логи
sudo journalctl -u bot.service -f

# Остановить бота
sudo systemctl stop bot.service

# Запустить бота
sudo systemctl start bot.service

# Перезапустить бота
sudo systemctl restart bot.service

# Статус бота
sudo systemctl status bot.service
```

### Работа с Git
```bash
# Обновить код с GitHub
git pull origin main

# Посмотреть изменения
git status

# Посмотреть историю коммитов
git log --oneline
```

### Работа с БД
```bash
# Проверить размер БД
ls -lh users.db pers/personas.db

# Открыть БД (если установлен sqlite3)
sqlite3 users.db
```

---

## 🔧 Решение проблем

### Бот не запускается

1. Проверьте логи:
```bash
sudo journalctl -u bot.service -n 50
```

2. Проверьте `.env` файл:
```bash
cat .env
```

3. Проверьте зависимости:
```bash
source venv/bin/activate
pip list
```

### Ошибка подключения к бакету

1. Проверьте переменные окружения:
```bash
cat .env | grep YANDEX
```

2. Проверьте доступ к бакету:
```bash
aws --endpoint-url=https://storage.yandexcloud.net s3 ls s3://имя_бакета/
```

### БД не загружается из бакета

1. Проверьте, что файлы есть в бакете:
```bash
aws --endpoint-url=https://storage.yandexcloud.net s3 ls s3://имя_бакета/databases/
```

2. Проверьте права доступа ключа (должен быть `storage.editor` или `storage.admin`)

---

## 📝 Быстрая шпаргалка

### Обновление кода на сервере:
```bash
ssh ubuntu@IP
cd ~/girl-guy.ai
sudo systemctl stop bot.service
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl start bot.service
```

### Загрузка кода на GitHub:
```bash
cd C:\Users\uirya\Desktop\Girl-Guy.Ai
git add .
git commit -m "Описание"
git push origin main
```

### Просмотр логов:
```bash
ssh ubuntu@IP
sudo journalctl -u bot.service -f
```
