; ─────────────────────────────────────────────────────────────────────────────
; Beckit Windows Installer
; Build with: makensis /DVERSION=X.Y.Z installer.nsi
; Requires: NSIS 3.x (no extra plugins needed)
; ─────────────────────────────────────────────────────────────────────────────

!ifndef VERSION
  !define VERSION "0.0.0"
!endif

Unicode True

; ── Modern UI ─────────────────────────────────────────────────────────────────
!include "MUI2.nsh"
!include "LogicLib.nsh"

Name "Beckit ${VERSION}"
OutFile "Beckit-Windows-${VERSION}-installer.exe"
InstallDir "$PROGRAMFILES64\Beckit"
InstallDirRegKey HKLM "Software\Beckit" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma

; ── Pages ─────────────────────────────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ── Helper macro: try winget, fall back to direct download via PowerShell ─────
; Usage: ${TryWinget} "Publisher.PackageId" "$TEMP\fallback.exe" "https://..." "/SILENT"
!macro _TryWinget PKG_ID FALLBACK_PATH FALLBACK_URL SILENT_FLAG
  nsExec::ExecToLog 'winget install --id ${PKG_ID} --exact --silent --accept-package-agreements --accept-source-agreements'
  Pop $0
  ${If} $0 != 0
    DetailPrint "winget unavailable or failed for ${PKG_ID}; downloading installer..."
    nsExec::ExecToLog 'powershell -NoProfile -Command "Invoke-WebRequest -Uri ''${FALLBACK_URL}'' -OutFile ''${FALLBACK_PATH}'' -UseBasicParsing"'
    Pop $1
    ${If} $1 == 0
      ExecWait '"${FALLBACK_PATH}" ${SILENT_FLAG}' $0
    ${Else}
      MessageBox MB_ICONEXCLAMATION "Download failed for ${PKG_ID}.$\nPlease install it manually."
    ${EndIf}
  ${EndIf}
!macroend
!define TryWinget "!insertmacro _TryWinget"

; ── Sections ──────────────────────────────────────────────────────────────────

Section "Pandoc" SecPandoc
  nsExec::ExecToLog 'pandoc --version'
  Pop $0
  ${If} $0 == 0
    DetailPrint "Pandoc already installed — skipping."
  ${Else}
    DetailPrint "Installing Pandoc..."
    ${TryWinget} "JohnMacFarlane.Pandoc" "$TEMP\pandoc-installer.msi" "https://github.com/jgm/pandoc/releases/latest/download/pandoc-3.6.2-windows-x86_64.msi" "/quiet /norestart"
  ${EndIf}
SectionEnd

Section "MiKTeX (LaTeX)" SecMiKTeX
  nsExec::ExecToLog 'pdflatex --version'
  Pop $0
  ${If} $0 == 0
    DetailPrint "LaTeX already installed — skipping."
  ${Else}
    DetailPrint "Installing MiKTeX (this may take several minutes)..."
    ${TryWinget} "MiKTeX.MiKTeX" "$TEMP\miktex-installer.exe" "https://miktex.org/download/ctan/systems/win32/miktex/setup/windows-x64/basic-miktex-24.1-x64.exe" "--unattended --shared=yes --auto-install=yes"
  ${EndIf}
SectionEnd

Section "Git" SecGit
  nsExec::ExecToLog 'git --version'
  Pop $0
  ${If} $0 == 0
    DetailPrint "Git already installed — skipping."
  ${Else}
    DetailPrint "Installing Git..."
    ${TryWinget} "Git.Git" "$TEMP\git-installer.exe" "https://github.com/git-for-windows/git/releases/latest/download/Git-2.47.1.2-64-bit.exe" "/VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS /COMPONENTS=icons,ext\reg\shellhere,assoc,assoc_sh"
  ${EndIf}
SectionEnd

Section "Beckit" SecApp
  SectionIn RO   ; required — cannot be deselected

  ; Copy the entire onedir bundle produced by flet pack -D
  SetOutPath "$INSTDIR"
  File /r "..\..\dist\Beckit\*.*"

  ; Start Menu shortcuts
  CreateDirectory "$SMPROGRAMS\Beckit"
  CreateShortcut "$SMPROGRAMS\Beckit\Beckit.lnk" "$INSTDIR\Beckit.exe"
  CreateShortcut "$SMPROGRAMS\Beckit\Uninstall.lnk"  "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\Beckit.lnk"               "$INSTDIR\Beckit.exe"

  ; Add/Remove Programs registry entries
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Beckit" \
                     "DisplayName"     "Beckit"
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Beckit" \
                     "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Beckit" \
                     "InstallLocation" "$INSTDIR"
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Beckit" \
                     "Publisher"       "Beckit contributors"
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Beckit" \
                     "DisplayVersion"  "${VERSION}"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Beckit" \
                     "NoModify"        1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Beckit" \
                     "NoRepair"        1

  WriteRegStr HKLM "Software\Beckit" "InstallDir" "$INSTDIR"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; ── Uninstaller ───────────────────────────────────────────────────────────────

Section "Uninstall"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR"

  Delete "$SMPROGRAMS\Beckit\Beckit.lnk"
  Delete "$SMPROGRAMS\Beckit\Uninstall.lnk"
  RMDir  "$SMPROGRAMS\Beckit"
  Delete "$DESKTOP\Beckit.lnk"

  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Beckit"
  DeleteRegKey HKLM "Software\Beckit"
SectionEnd
