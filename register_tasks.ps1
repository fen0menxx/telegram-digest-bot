# Регистрация задач Windows Task Scheduler для автоматических дайджестов.
#
# Создаёт 3 задачи:
#   1. TG_Digest_Morning  — ежедневно в 08:03
#   2. TG_Digest_Evening  — ежедневно в 19:03
#   3. TG_Digest_OnLogon  — при входе в Windows
#
# Все задачи:
#   - Запускают run_digest.bat (=> venv\python make_digest.py)
#   - Работают только когда пользователь залогинен (без сохранения пароля)
#   - При пропущенном времени — выполняются при первой возможности
#   - Будят ПК из режима сна
#   - Перезапускаются 3 раза с интервалом 5 мин при сбое
#
# Антидубль (2 часа) реализован внутри make_digest.py — даже если задачи
# совпадут по времени, дайджест отправится только один раз.
#
# Запуск:
#   Откройте PowerShell в этой папке:
#     powershell -ExecutionPolicy Bypass -File register_tasks.ps1
#
# Удаление:
#   powershell -ExecutionPolicy Bypass -File register_tasks.ps1 -Unregister

param(
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"

# Корень проекта — папка, где лежит этот скрипт
$ProjectDir = $PSScriptRoot
$BatchFile  = Join-Path $ProjectDir "run_digest.bat"

$TaskNames = @("TG_Digest_Morning", "TG_Digest_Evening", "TG_Digest_OnLogon")

# === UNREGISTER ===
if ($Unregister) {
    foreach ($name in $TaskNames) {
        if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
            Write-Host "[OK] Удалена задача: $name" -ForegroundColor Yellow
        } else {
            Write-Host "[--] Задача не найдена: $name" -ForegroundColor DarkGray
        }
    }
    exit 0
}

# === REGISTER ===
if (-not (Test-Path $BatchFile)) {
    Write-Host "[ERROR] Не найден файл: $BatchFile" -ForegroundColor Red
    Write-Host "Убедитесь, что register_tasks.ps1 лежит рядом с run_digest.bat" -ForegroundColor Red
    exit 1
}

Write-Host "Проект: $ProjectDir" -ForegroundColor Cyan
Write-Host "Скрипт: $BatchFile" -ForegroundColor Cyan
Write-Host ""

# Общее действие — запуск .bat в директории проекта
$Action = New-ScheduledTaskAction `
    -Execute $BatchFile `
    -WorkingDirectory $ProjectDir

# Общие настройки для всех задач
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew

# Принципал — текущий пользователь, без сохранения пароля
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

# === Задача 1: утро 08:03 ===
$TriggerMorning = New-ScheduledTaskTrigger -Daily -At "08:03"
Register-ScheduledTask `
    -TaskName "TG_Digest_Morning" `
    -Description "Telegram-дайджест: утренний выпуск (08:03)" `
    -Action $Action `
    -Trigger $TriggerMorning `
    -Settings $Settings `
    -Principal $Principal `
    -Force | Out-Null
Write-Host "[OK] TG_Digest_Morning  — ежедневно 08:03" -ForegroundColor Green

# === Задача 2: вечер 19:03 ===
$TriggerEvening = New-ScheduledTaskTrigger -Daily -At "19:03"
Register-ScheduledTask `
    -TaskName "TG_Digest_Evening" `
    -Description "Telegram-дайджест: вечерний выпуск (19:03)" `
    -Action $Action `
    -Trigger $TriggerEvening `
    -Settings $Settings `
    -Principal $Principal `
    -Force | Out-Null
Write-Host "[OK] TG_Digest_Evening  — ежедневно 19:03" -ForegroundColor Green

# === Задача 3: при логине ===
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# Задержка 1 минута после логина, чтобы система успела подключиться к сети.
# В некоторых версиях PowerShell свойство Delay не присваивается напрямую —
# оборачиваем в try/catch: если не получилось, задача отработает без задержки
# (не критично, но сеть может быть ещё не готова).
try {
    $TriggerLogon.Delay = "PT1M"
} catch {
    Write-Host "[WARN] Не удалось задать задержку 1 мин для OnLogon: $_" -ForegroundColor Yellow
    Write-Host "       Задача будет срабатывать сразу при логине (без задержки)" -ForegroundColor Yellow
}
Register-ScheduledTask `
    -TaskName "TG_Digest_OnLogon" `
    -Description "Telegram-дайджест: запуск при входе в Windows (антидубль 2ч в скрипте)" `
    -Action $Action `
    -Trigger $TriggerLogon `
    -Settings $Settings `
    -Principal $Principal `
    -Force | Out-Null
Write-Host "[OK] TG_Digest_OnLogon  — при логине (с задержкой 1 мин)" -ForegroundColor Green

Write-Host ""
Write-Host "Готово. Проверить задачи: taskschd.msc" -ForegroundColor Cyan
Write-Host "Запустить вручную сейчас:" -ForegroundColor Cyan
Write-Host "    Start-ScheduledTask -TaskName TG_Digest_Morning" -ForegroundColor DarkGray
Write-Host "Удалить все задачи:" -ForegroundColor Cyan
Write-Host "    powershell -ExecutionPolicy Bypass -File register_tasks.ps1 -Unregister" -ForegroundColor DarkGray
