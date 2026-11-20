# WinCare Manager kurulum dosyasini (Setup.exe) olusturur.
# Gerekenler: scripts\build_windows.ps1 ile olusturulmus dist\WinCare Manager klasoru ve Inno Setup 6.
#   Inno Setup kurulumu:  winget install --id JRSoftware.InnoSetup -e
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path "dist\WinCare Manager\WinCare Manager.exe")) {
    throw "dist\WinCare Manager bulunamadi. Once scripts\build_windows.ps1 calistirin."
}

$candidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$iscc = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) {
    $command = Get-Command iscc -ErrorAction SilentlyContinue
    if ($command) { $iscc = $command.Source }
}
if (-not $iscc) {
    throw "Inno Setup 6 bulunamadi. Kurmak icin: winget install --id JRSoftware.InnoSetup -e"
}

# Surum numarasi tek kaynaktan (app\__init__.py) okunur.
$match = Select-String -Path "app\__init__.py" -Pattern '__version__\s*=\s*"([^"]+)"'
if (-not $match) { throw "Surum numarasi okunamadi." }
$version = $match.Matches[0].Groups[1].Value

& $iscc "/DAppVersion=$version" "installer\WinCareManager.iss"
if ($LASTEXITCODE -ne 0) { throw "Kurulum dosyasi olusturulamadi." }

$setup = "dist\installer\WinCareManager-Setup-$version.exe"
$hash = (Get-FileHash $setup -Algorithm SHA256).Hash.ToLower()
"$hash  WinCareManager-Setup-$version.exe" | Out-File -Encoding ascii "dist\installer\SHA256SUMS.txt"
Write-Host "Tamamlandi: $setup"
Write-Host "SHA-256: $hash"
