#===============================================================================
# ssh-setup-local.ps1 - Настройка SSH ключей (запускать на Windows)
# Использование: .\ssh-setup-local.ps1
#===============================================================================

$VPS_IP = "141.227.152.143"
$VPS_USER = "root"
$VPS_HOSTNAME = "vps-ec36a417.vps.ovh.net"
$KEY_NAME = "id_ed25519_ovh"
$SSH_DIR = "$env:USERPROFILE\.ssh"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Настройка SSH ключей для VPS"
Write-Host "  $VPS_HOSTNAME ($VPS_IP)"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Создание .ssh директории
if (-not (Test-Path $SSH_DIR)) {
    New-Item -ItemType Directory -Path $SSH_DIR -Force | Out-Null
    Write-Host "[+] Создана директория $SSH_DIR" -ForegroundColor Green
}

# 2. Генерация ключа
$KEY_PATH = "$SSH_DIR\$KEY_NAME"

if (Test-Path $KEY_PATH) {
    Write-Host "[!] Ключ уже существует: $KEY_PATH" -ForegroundColor Yellow
    $overwrite = Read-Host "Перезаписать? (y/n)"
    if ($overwrite -ne "y") {
        Write-Host "Используем существующий ключ" -ForegroundColor Yellow
    } else {
        Remove-Item "$KEY_PATH*" -Force
    }
}

if (-not (Test-Path $KEY_PATH)) {
    Write-Host "[*] Генерация ED25519 ключа..." -ForegroundColor Cyan
    ssh-keygen -t ed25519 -f $KEY_PATH -C "news-bot@$VPS_HOSTNAME" -N '""'
    Write-Host "[+] Ключ создан: $KEY_PATH" -ForegroundColor Green
}

# 3. Настройка SSH config
$CONFIG_FILE = "$SSH_DIR\config"
$CONFIG_ENTRY = @"

# News Assistant Bot VPS (OVH Amsterdam)
Host ovh-bot
    HostName $VPS_IP
    User $VPS_USER
    IdentityFile $KEY_PATH
    IdentitiesOnly yes
    ServerAliveInterval 60
    ServerAliveCountMax 3

Host $VPS_IP
    User $VPS_USER
    IdentityFile $KEY_PATH
    IdentitiesOnly yes
"@

# Проверяем есть ли уже запись
$configExists = $false
if (Test-Path $CONFIG_FILE) {
    $configContent = Get-Content $CONFIG_FILE -Raw
    if ($configContent -match "ovh-bot") {
        $configExists = $true
        Write-Host "[!] Конфигурация ovh-bot уже есть в $CONFIG_FILE" -ForegroundColor Yellow
    }
}

if (-not $configExists) {
    Add-Content -Path $CONFIG_FILE -Value $CONFIG_ENTRY
    Write-Host "[+] Добавлена конфигурация в $CONFIG_FILE" -ForegroundColor Green
}

# 4. Копирование ключа на сервер
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Копирование ключа на сервер"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Сейчас потребуется ввести пароль от VPS (последний раз!)" -ForegroundColor Yellow
Write-Host ""

$PUB_KEY = Get-Content "$KEY_PATH.pub"

# Используем ssh напрямую для добавления ключа
$command = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '$PUB_KEY' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && echo 'OK'"

Write-Host "Выполняю: ssh $VPS_USER@$VPS_IP ..." -ForegroundColor Cyan
ssh "$VPS_USER@$VPS_IP" $command

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[+] Ключ успешно скопирован!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[!] Ошибка копирования. Попробуйте вручную:" -ForegroundColor Red
    Write-Host "    type $KEY_PATH.pub | ssh $VPS_USER@$VPS_IP `"cat >> ~/.ssh/authorized_keys`"" -ForegroundColor Yellow
    exit 1
}

# 5. Тест подключения
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Тест подключения без пароля"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

ssh -o BatchMode=yes -o ConnectTimeout=5 ovh-bot "echo 'SSH ключ работает!'"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[+] Успех! Теперь можно подключаться без пароля:" -ForegroundColor Green
    Write-Host ""
    Write-Host "    ssh ovh-bot" -ForegroundColor White
    Write-Host "    или" -ForegroundColor Gray
    Write-Host "    ssh $VPS_USER@$VPS_IP" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "[!] Тест не прошел. Проверьте настройки SSH на сервере" -ForegroundColor Red
}

# 6. Рекомендации
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Следующие шаги (на сервере)"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "После проверки работы ключа, отключите пароли:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  ssh ovh-bot" -ForegroundColor White
Write-Host "  sudo nano /etc/ssh/sshd_config" -ForegroundColor White
Write-Host ""
Write-Host "  # Установить:" -ForegroundColor Gray
Write-Host "  PasswordAuthentication no" -ForegroundColor White
Write-Host "  PubkeyAuthentication yes" -ForegroundColor White
Write-Host ""
Write-Host "  sudo systemctl reload sshd" -ForegroundColor White
Write-Host ""
