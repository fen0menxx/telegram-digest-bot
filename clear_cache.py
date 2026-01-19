"""Очистка кэша обработанных сообщений."""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "data" / "digest.db"

print(f"База данных: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Считаем сколько записей
cursor.execute("SELECT COUNT(*) FROM processed_messages")
count = cursor.fetchone()[0]
print(f"Записей в кэше: {count}")

# Удаляем
cursor.execute("DELETE FROM processed_messages")
conn.commit()
conn.close()

print(f"Удалено {count} записей. Кэш очищен!")

