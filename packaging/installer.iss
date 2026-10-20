; Inno Setup script for Peão Bilíngue's installer: per user, no admin rights.
;
;   powershell -ExecutionPolicy Bypass -File packaging\build_installer.ps1
;
; builds dist\PeaoBilingue first and stages the license page and the third-party notices
; in dist\installer\, then compiles this into dist\PeaoBilingue-Setup-<version>.exe. Kept
; in UTF-8 with a BOM: Inno Setup needs it to read the accents.

#ifndef AppVersion
  #error Pass the version: iscc /DAppVersion=x.y.z packaging\installer.iss
#endif
#ifndef SiteUrl
  #define SiteUrl "https://github.com/gvieiragoulart/peao-bilingue/releases"
#endif

#define AppName "Peão Bilíngue"
#define AppExe "PeaoBilingue.exe"

[Setup]
; Never change it: it is how Windows knows a new version updates this installation.
AppId={{AF43A9A0-5FF6-42E8-925A-78850309F08D}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Gabriel Vieira
AppPublisherURL={#SiteUrl}
AppSupportURL={#SiteUrl}
AppUpdatesURL={#SiteUrl}
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
; Per user: {autopf} is %LOCALAPPDATA%\Programs, the same folder deploy.ps1 installs to,
; so an installation made by hand is updated in place.
PrivilegesRequired=lowest
DefaultDirName={autopf}\PeaoBilingue
DisableProgramGroupPage=yes
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=..\src\peao_bilingue\ui\peao_bilingue.ico
LicenseFile=..\dist\installer\license.txt
OutputDir=..\dist
OutputBaseFilename=PeaoBilingue-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; The window, or a collection in progress, holds the files: offer to close it first.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; PyInstaller's libraries change between versions: an old one left behind could be loaded.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\PeaoBilingue\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\installer\THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; The daily collection calls this .exe: without it, it would fail every day once the
; files are gone. The data in %LOCALAPPDATA%\PeaoBilingue stays.
Filename: "{app}\{#AppExe}"; Parameters: "schedule disable"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveDailyCollection"
