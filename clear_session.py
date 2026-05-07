"""Удаление файлов сессии Telethon."""
import os
from pathlib import Path

data_dir = Path(__file__).parent / "data"

files_to_delete = [
    data_dir / "userbot.session",
    data_dir / "userbot.session-journal",
]

for f in files_to_delete:
    if f.exists():
        os.remove(f)
        print(f"Удалён: {f.name}")
    else:
        print(f"Не найден: {f.name}")

print("\nСессия очищена. Теперь запустите бота заново.")
























