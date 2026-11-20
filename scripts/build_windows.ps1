# "Continue": PyInstaller/pip bilgi mesajlarini stderr'e yazar; PowerShell 5.1 bunlari hata sanmasin.
# Her adimin basarisi $LASTEXITCODE ile ayrica kontrol edilir.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "WinCare Manager Windows paketleme islemi baslatiliyor..."

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Sanal ortam bulunamadi. Once scripts\setup_windows.ps1 dosyasini calistirin."
}
$python = ".venv\Scripts\python.exe"

# 0.1.0 hatasi duzeltildi: pytest artik requirements-dev.txt ile kuruluyor.
& $python -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Paketler yuklenemedi." }

& $python -m pytest
if ($LASTEXITCODE -ne 0) { throw "Testler basarisiz oldu; paketleme durduruldu." }

if (-not (Test-Path "assets\app.ico")) {
    & $python scripts\make_icon.py
}

# 0.1.0 hatasi duzeltildi: tema dosyasi (theme.qss) ve ikon artik pakete ekleniyor.
& $python -m PyInstaller --noconfirm --clean --windowed `
    --name "WinCare Manager" `
    --icon "assets\app.ico" `
    --add-data "locales;locales" `
    --add-data "ui\styles\theme.qss;ui\styles" `
    --add-data "assets;assets" `
    main.py
if ($LASTEXITCODE -ne 0) { throw "EXE paketleme basarisiz oldu." }

$exe = "dist\WinCare Manager\WinCare Manager.exe"
if (-not (Test-Path $exe)) { throw "EXE olusturulamadi: $exe" }

$hash = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
"$hash  WinCare Manager.exe" | Out-File -Encoding ascii "dist\WinCare Manager\SHA256SUMS.txt"

Write-Host "Tamamlandi: $exe"
Write-Host "SHA-256: $hash"
