; ─────────────────────────────────────────────────────────────────────────────
; BookEditor Windows Installer
; Build with: makensis /DVERSION=X.Y.Z installer.nsi
; Requires: NSIS 3.x with inetc plugin (bundled with NSIS on GitHub Actions)
; ─────────────────────────────────────────────────────────────────────────────

!ifndef VERSION
  !define VERSION "0.0.0"
!endif

Unicode True

; ── Modern UI ─────────────────────────────────────────────────────────────────
!include "MUI2.nsh"
!include "LogicLib.nsh"

Name "Book Editor ${VERSION}"
OutFile "BookEditor-Windows-${VERSION}-installer.exe"
InstallDir "$PROGRAMFILES64\BookEditor"
InstallDirRegKey HKLM "Software\BookEditor" "InstallDir"
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

; ── Helper macro: try winget, fall back to direct download ────────────────────
; Usage: ${TryWinget} "Publisher.PackageId" "$TEMP\fallback.exe" "https://..." "/SILENT"
!macro _TryWinget PKG_ID FALLBACK_PATH FALLBACK_URL SILENT_FLAG
  nsExec::ExecToLog 'winget install --id ${PKG_ID} --exact --silent --accept-package-agreements --accept-source-agreements'
  Pop $0
  ${If} $0 != 0
    DetailPrint "winget unavailable or failed for ${PKG_ID}; downloading installer..."
    inetc::get /NOUNLOAD /SILENT "${FALLBACK_URL}" "${FALLBACK_PATH}"
    Pop $1
    ${If} $1 == "OK"
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
    ${TryWinget} "JohnMacFarlane.Pandoc" \
      "$TEMP\pandoc-installer.msi" \
      "https://github.com/jgm/pandoc/releases/latest/download/pandoc-3.6.2-windows-x86_64.msi" \
      "/quiet /norestart"
  ${EndIf}
SectionEnd

Section "MiKTeX (LaTeX)" SecMiKTeX
  nsExec::ExecToLog 'pdflatex --version'
  Pop $0
  ${If} $0 == 0
    DetailPrint "LaTeX already installed — skipping."
  ${Else}
    DetailPrint "Installing MiKTeX (this may take several minutes)..."
    ${TryWinget} "MiKTeX.MiKTeX" \
      "$TEMP\miktex-installer.exe" \
      "https://miktex.org/download/ctan/systems/win32/miktex/setup/windows-x64/basic-miktex-24.1-x64.exe" \
      "--unattended --shared=yes --auto-install=yes"
  ${EndIf}
SectionEnd

Section "Git" SecGit
  nsExec::ExecToLog 'git --version'
  Pop $0
  ${If} $0 == 0
    DetailPrint "Git already installed — skipping."
  ${Else}
    DetailPrint "Installing Git..."
    ${TryWinget} "Git.Git" \
      "$TEMP\git-installer.exe" \
      "https://github.com/git-for-windows/git/releases/latest/download/Git-2.47.1.2-64-bit.exe" \
      "/VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS /COMPONENTS=icons,ext\reg\shellhere,assoc,assoc_sh"
  ${EndIf}
SectionEnd

Section "Book Editor" SecApp
  SectionIn RO   ; required — cannot be deselected

  SetOutPath "$INSTDIR"
  File /r "..\..\dist\BookEditor\*.*"

  ; Start Menu shortcuts
  CreateDirectory "$SMPROGRAMS\Book Editor"
  CreateShortcut "$SMPROGRAMS\Book Editor\Book Editor.lnk" "$INSTDIR\BookEditor.exe"
  CreateShortcut "$SMPROGRAMS\Book Editor\Uninstall.lnk"  "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\Book Editor.lnk"               "$INSTDIR\BookEditor.exe"

  ; Add/Remove Programs registry entries
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BookEditor" \
                     "DisplayName"     "Book Editor"
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BookEditor" \
                     "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BookEditor" \
                     "InstallLocation" "$INSTDIR"
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BookEditor" \
                     "Publisher"       "Book Editor contributors"
  WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BookEditor" \
                     "DisplayVersion"  "${VERSION}"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BookEditor" \
                     "NoModify"        1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BookEditor" \
                     "NoRepair"        1

  WriteRegStr HKLM "Software\BookEditor" "InstallDir" "$INSTDIR"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; ── Uninstaller ───────────────────────────────────────────────────────────────

Section "Uninstall"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR"

  Delete "$SMPROGRAMS\Book Editor\Book Editor.lnk"
  Delete "$SMPROGRAMS\Book Editor\Uninstall.lnk"
  RMDir  "$SMPROGRAMS\Book Editor"
  Delete "$DESKTOP\Book Editor.lnk"

  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\BookEditor"
  DeleteRegKey HKLM "Software\BookEditor"
SectionEnd
