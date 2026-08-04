; ============================================================
;  PrintNest Pro - instalador Windows (Inno Setup 6)
;
;  Build em 2 passos (ver docs/build/BUILD.md):
;    1) build.bat                       -> gera PrintNest_Build\
;    2) ISCC installer\printnest.iss    -> gera dist_installer\PrintNest-Setup-<versao>.exe
;
;  O instalador empacota a pasta PrintNest_Build INTEIRA (exe, VERSAO.txt,
;  README, Tutor IA em PDF e o Plugin CorelDRAW). A desinstalacao remove so
;  o que foi instalado — %APPDATA%\PrintNest (configuracoes + LICENCA do
;  cliente) fica intacto de proposito: desinstalar/reinstalar nao pode
;  derrubar a ativacao.
; ============================================================

#define MyAppName "PrintNest Pro"
; ATENCAO: alinhar com app/__init__.py (__version__) e docs/build/VERSAO.txt.
#define MyAppVersion "1.1.1"
#define MyAppPublisher "PrintNest — Philipe Fernandes"
#define MyAppExeName "PrintNest.exe"

[Setup]
; AppId identifica o programa no Windows entre versoes — NUNCA mudar.
AppId={{B7F31E9C-5D24-4A86-9C1D-3A7F0E52C816}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PrintNest
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=EULA.txt
OutputDir=..\dist_installer
OutputBaseFilename=PrintNest-Setup-{#MyAppVersion}
SetupIconFile=..\assets\printnest.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
; App aberto durante a instalacao = erro de arquivo em uso no meio do processo.
; A instancia unica do PrintNest usa QLocalServer, que o Inno nao enxerga; o
; app cria este mutex no startup (APP_MUTEX_NAME em app/presentation/__main__.py)
; so para o instalador poder avisar antes. Os dois nomes: o "Global\" e o da
; sessao (usuario comum pode nao ter privilegio para criar o global).
AppMutex=PrintNestAppMutex,Global\PrintNestAppMutex

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; a pasta de build inteira, com subpastas (Plugin CorelDRAW etc.)
Source: "..\PrintNest_Build\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Tutor IA - PrintNest (PDF)"; Filename: "{app}\Tutor IA - PrintNest.pdf"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; "unchecked" de proposito (04/08/2026). O instalador acabou de gravar um .exe
; de 116 MB e o antivirus comeca a varre-lo NA HORA. Abrir o programa nesse
; instante faz a extracao do Python para o %TEMP% disputar com a varredura, e
; o programa morre com "Failed to load Python DLL" — instalou, mas nao abre.
; Aconteceu na primeira instalacao em maquina de terceiro; abriu normal na
; segunda tentativa, sem mexer em nada.
; O cliente comum nao tenta de novo: ele conclui que o produto esta quebrado.
; Deixando a caixa desmarcada, o caminho padrao e abrir pelo atalho alguns
; segundos depois, com a varredura ja concluida.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent unchecked
