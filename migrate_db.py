"""
Миграция базы данных.

Добавляет недостающие колонки в существующую базу данных.
"""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "data" / "digest.db"

print(f"Миграция базы данных: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Получаем текущую структуру таблицы users
cursor.execute("PRAGMA table_info(users)")
columns = {row[1] for row in cursor.fetchall()}
print(f"Текущие колонки в users: {columns}")

migrations = []

# Проверяем и добавляем недостающие колонки
if "id" not in columns:
    # Таблица users не имеет колонки id
    # Нужно пересоздать таблицу с правильной структурой
    print("⚠️ Таблица users требует пересоздания...")
    
    # Сохраняем данные — используем только те колонки, которые есть
    cursor.execute("SELECT telegram_id, digest_interval, last_digest_at, is_active, created_at FROM users")
    users_data = cursor.fetchall()
    print(f"Сохранено {len(users_data)} пользователей")
    
    # Получаем значения новых колонок если есть
    extra_data = {}
    if "digest_news_limit" in columns:
        cursor.execute("SELECT telegram_id, digest_news_limit FROM users")
        for row in cursor.fetchall():
            if row[0] not in extra_data:
                extra_data[row[0]] = {}
            extra_data[row[0]]["digest_news_limit"] = row[1]
    
    if "digest_channel_id" in columns:
        cursor.execute("SELECT telegram_id, digest_channel_id FROM users")
        for row in cursor.fetchall():
            if row[0] not in extra_data:
                extra_data[row[0]] = {}
            extra_data[row[0]]["digest_channel_id"] = row[1]
    
    if "digest_thread_id" in columns:
        cursor.execute("SELECT telegram_id, digest_thread_id FROM users")
        for row in cursor.fetchall():
            if row[0] not in extra_data:
                extra_data[row[0]] = {}
            extra_data[row[0]]["digest_thread_id"] = row[1]
    
    # Удаляем старую таблицу
    cursor.execute("DROP TABLE users")
    
    # Создаём новую таблицу
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username VARCHAR(255),
            digest_interval INTEGER DEFAULT 24,
            digest_news_limit INTEGER DEFAULT 20,
            last_digest_at DATETIME,
            digest_channel_id INTEGER,
            digest_thread_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX ix_users_telegram_id ON users (telegram_id)")
    
    # Восстанавливаем данные
    for row in users_data:
        telegram_id, digest_interval, last_digest_at, is_active, created_at = row
        
        # Получаем дополнительные данные
        extra = extra_data.get(telegram_id, {})
        news_limit = extra.get("digest_news_limit", 20)
        channel_id = extra.get("digest_channel_id")
        thread_id = extra.get("digest_thread_id")
        
        cursor.execute("""
            INSERT INTO users (telegram_id, digest_interval, digest_news_limit, last_digest_at, 
                              digest_channel_id, digest_thread_id, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (telegram_id, digest_interval, news_limit, last_digest_at, 
              channel_id, thread_id, is_active, created_at))
    
    print(f"✅ Таблица users пересоздана, данные восстановлены")
    migrations.append("users: пересоздана таблица с id")

else:
    # Добавляем недостающие колонки
    if "digest_news_limit" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN digest_news_limit INTEGER DEFAULT 20")
        migrations.append("users: добавлена digest_news_limit")
    
    if "digest_channel_id" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN digest_channel_id INTEGER")
        migrations.append("users: добавлена digest_channel_id")
    
    if "digest_thread_id" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN digest_thread_id INTEGER")
        migrations.append("users: добавлена digest_thread_id")
    
    if "username" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN username VARCHAR(255)")
        migrations.append("users: добавлена username")

conn.commit()
conn.close()

if migrations:
    print("\n=== Выполненные миграции ===")
    for m in migrations:
        print(f"  ✅ {m}")
else:
    print("✅ База данных актуальна, миграции не требуются")

print("\nГотово!")
