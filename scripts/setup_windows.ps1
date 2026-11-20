# "Continue": pip uyarilarini stderr'e yazar; PowerShell 5.1 bunlari hata sanmasin.
# Her adimin basarisi $LASTEXITCODE ile ayrica kontrol edilir.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "WinCare Manager kurulum hazirligi baslatiliyor..."

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python Launcher (py) bulunamadi. python.org adresinden Python 3.12 veya daha yeni bir surum yukleyin."
}

& py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.12 veya daha yeni bir surum gerekli." }

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Sanal ortam olusturulamadi." }
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip guncellenemedi." }

# Gelistirme bagimliliklari (pytest, PyInstaller) da kurulur; boylece testler ve EXE paketleme hazir olur.
& ".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Gerekli paketler yuklenemedi." }

Write-Host "Kurulum tamamlandi. Uygulamayi run_windows.bat ile baslatabilir, EXE icin scripts\build_windows.ps1 calistirabilirsiniz."
