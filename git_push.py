"""Push to GitHub."""
import subprocess
import os

os.chdir(r"C:\Users\roman\Бот ТГ дайджест курсор")

commands = [
    # Настройка git identity
    ["git", "config", "user.email", "fen0menxx@users.noreply.github.com"],
    ["git", "config", "user.name", "fen0menxx"],
    # Git операции
    ["git", "add", "."],
    ["git", "commit", "-m", "Initial commit: Telegram Digest Bot"],
    ["git", "branch", "-M", "main"],
    ["git", "remote", "add", "origin", "https://github.com/fen0menxx/telegram-digest-bot.git"],
    ["git", "push", "-u", "origin", "main"],
]

for cmd in commands:
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    # Игнорируем ошибку если remote уже существует
    if result.returncode != 0:
        if "remote add" in ' '.join(cmd) and "already exists" in result.stderr:
            print("Remote already exists, continuing...")
            continue
        if "config" in ' '.join(cmd):
            continue
        print(f"Exit code: {result.returncode}")

print("\nDone!")
