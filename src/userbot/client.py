"""
Клиент Telethon для работы с Telegram API.

Userbot нужен для:
- Сканирования каналов пользователя
- Получения сообщений из каналов
"""

import sys
import asyncio
from pathlib import Path

from telethon import TelegramClient
from telethon import connection as tg_connection
from telethon.tl.functions.auth import ExportLoginTokenRequest, AcceptLoginTokenRequest
from loguru import logger

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import settings

# Глобальный клиент
client: TelegramClient | None = None


def _build_proxy() -> tuple | None:
    """Собирает кортеж прокси для Telethon из settings, либо None.

    Поддерживаемые типы:
      - socks5 / socks4 / http — обычный SOCKS/HTTP-прокси
      - mtproto — MTProto-прокси Telegram (TG_PROXY_PASS = secret)
    """
    if not settings.PROXY_TYPE or not settings.PROXY_PORT:
        return None

    ptype = settings.PROXY_TYPE

    if ptype == "mtproto":
        # Для MTProto secret кладём в TG_PROXY_PASS
        secret = settings.PROXY_PASS
        if not secret:
            logger.warning("TG_PROXY_TYPE=mtproto, но TG_PROXY_PASS (secret) пустой — прокси отключён")
            return None
        logger.info(f"Telethon: MTProto-прокси {settings.PROXY_HOST}:{settings.PROXY_PORT}")
        return (settings.PROXY_HOST, settings.PROXY_PORT, secret)

    if ptype not in {"socks5", "socks4", "http"}:
        logger.warning(f"Неизвестный TG_PROXY_TYPE={ptype!r}, прокси отключён")
        return None

    proxy = (ptype, settings.PROXY_HOST, settings.PROXY_PORT)
    if settings.PROXY_USER:
        # Telethon поддерживает кортеж с авторизацией:
        # (type, host, port, rdns, username, password)
        proxy = (ptype, settings.PROXY_HOST, settings.PROXY_PORT,
                 True, settings.PROXY_USER, settings.PROXY_PASS)

    logger.info(f"Telethon: используем прокси {ptype}://{settings.PROXY_HOST}:{settings.PROXY_PORT}")
    return proxy


async def init_client() -> TelegramClient:
    """Инициализация и авторизация Telethon клиента."""
    global client

    logger.info("Инициализация Telethon клиента...")

    proxy = _build_proxy()
    client_kwargs = dict(
        session=str(settings.SESSION_PATH),
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
        proxy=proxy,
    )
    # MTProto-прокси требует особого класса соединения
    if settings.PROXY_TYPE == "mtproto" and proxy is not None:
        client_kwargs["connection"] = tg_connection.ConnectionTcpMTProxyRandomizedIntermediate

    client = TelegramClient(**client_kwargs)

    await client.connect()
    logger.info("Подключение к Telegram серверам: OK")
    
    if not await client.is_user_authorized():
        print("\n=== СПОСОБ АВТОРИЗАЦИИ ===")
        print("[1] QR-код (рекомендуется — отсканируйте камерой в Telegram)")
        print("[2] Номер телефона + код")
        method = input("Выберите (1/2): ").strip()
        
        if method == "1":
            await _auth_qr(client)
        else:
            await _auth_phone(client)
    
    me = await client.get_me()
    logger.success(f"Авторизован как: {me.first_name} (@{me.username})")
    
    return client


async def _auth_qr(cl: TelegramClient) -> None:
    """Авторизация через QR-код."""
    print("\n=== АВТОРИЗАЦИЯ ЧЕРЕЗ QR-КОД ===")
    print("1. Откройте Telegram на телефоне")
    print("2. Настройки -> Устройства -> Подключить устройство")
    
    qr_login = await cl.qr_login()
    
    if HAS_QRCODE:
        print("3. Отсканируйте QR-код ниже:\n")
        qr = qrcode.QRCode(version=1, box_size=1, border=1)
        qr.add_data(qr_login.url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    else:
        print(f"\n3. Откройте эту ссылку для генерации QR:")
        print(f"   https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={qr_login.url}")
        print("   Или установите: pip install qrcode")
    
    print("\nОжидание сканирования (120 сек)...")
    
    try:
        await qr_login.wait(timeout=120)
        logger.success("QR-авторизация успешна!")
    except asyncio.TimeoutError:
        logger.error("Таймаут — QR-код не был отсканирован за 120 секунд")
        raise
    except Exception as e:
        if "password" in str(e).lower() or "2fa" in str(e).lower():
            password = input("Введите пароль двухфакторной аутентификации: ").strip()
            await cl.sign_in(password=password)
        else:
            raise


async def _auth_phone(cl: TelegramClient) -> None:
    """Авторизация через номер телефона."""
    phone = input("Введите номер телефона (с +7...): ").strip()
    
    logger.info(f"Отправляем запрос кода на {phone}...")
    result = await cl.send_code_request(phone)
    code_type = result.type.__class__.__name__
    logger.info(f"Тип доставки: {code_type}")
    
    if "App" in code_type:
        logger.info("Код отправлен В ПРИЛОЖЕНИЕ Telegram -> чат 'Telegram'")
    elif "Sms" in code_type:
        logger.info("Код отправлен по SMS")
    
    action = input("\n[1] Ввести код\n[2] Переотправить через SMS\nВыберите (1/2): ").strip()
    
    if action == "2":
        result = await cl.send_code_request(phone, force_sms=True)
        logger.info(f"Переотправлено! Тип: {result.type.__class__.__name__}")
    
    code = input("Введите код: ").strip()
    
    try:
        await cl.sign_in(phone, code)
    except Exception as e:
        if "Two-steps verification" in str(e) or "password" in str(e).lower():
            password = input("Введите пароль двухфакторной аутентификации: ").strip()
            await cl.sign_in(password=password)
        else:
            raise


async def get_client() -> TelegramClient:
    """Получить клиент, инициализировать если нужно."""
    global client
    
    if client is None:
        return await init_client()
    
    return client


async def disconnect_client() -> None:
    """Отключение клиента."""
    global client
    
    if client is not None:
        await client.disconnect()
        client = None
        logger.info("Telethon клиент отключён")





























