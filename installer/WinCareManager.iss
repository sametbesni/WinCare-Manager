; WinCare Manager kurulum betigi (Inno Setup 6)
; Derlemek icin: scripts\build_installer.ps1
; Once scripts\build_windows.ps1 ile dist\WinCare Manager klasoru olusturulmus olmalidir.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "WinCare Manager"
#define AppExe "WinCare Manager.exe"
#define TaskName "WinCareManager AutoMaintenance"

[Setup]
; AppId kurulumu tanimlar; surum yukseltmelerinde DEGISTIRMEYIN.
AppId={{6F0E5C2A-3B7D-4C1E-9A58-2D4B7E1F0C93}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=WinCare Manager contributors
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Varsayilan: yalnizca bu kullanici icin, yonetici yetkisi gerekmez.
; Kurulum sirasinda "tum kullanicilar icin" secilirse yonetici yetkisi istenir.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=WinCareManager-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
turkish.DeleteUserData=WinCare Manager ayarları, işlem geçmişi ve yedekler de silinsin mi?%n%n%1%n%nBir yedeği daha sonra geri yüklemeyi düşünüyorsanız "Hayır"ı seçin.
english.DeleteUserData=Also delete WinCare Manager settings, operation history and backups?%n%n%1%n%nChoose "No" if you may want to restore a backup later.

[Tasks]
; Masaustu kisayolu varsayilan olarak isaretli gelir; kullanici kaldirabilir.
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\WinCare Manager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Otomatik Bakim acildiysa zamanlanmis gorevi de kaldir (yoksa hata vermeden gecer).
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN ""{#TaskName}"" /F"; Flags: runhidden; RunOnceId: "RemoveMaintenanceTask"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\WinCareManager');
    if DirExists(DataDir) then
      if SuppressibleMsgBox(FmtMessage(CustomMessage('DeleteUserData'), [DataDir]), mbConfirmation,
                            MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
