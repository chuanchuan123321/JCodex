!include "MUI2.nsh"

Name "JCodex"
OutFile "JCodex-Setup-${VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\JCodex"
Icon "build\icon.ico"
UninstallIcon "build\icon.ico"
RequestExecutionLevel user
SetCompressor lzma

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "dist\JCodex-win32-x64\*.*"
  WriteUninstaller "$INSTDIR\uninstall.exe"
  CreateShortcut "$SMPROGRAMS\JCodex.lnk" "$INSTDIR\JCodex.exe"
  CreateShortcut "$DESKTOP\JCodex.lnk" "$INSTDIR\JCodex.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JCodex" "DisplayName" "JCodex"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JCodex" "DisplayIcon" "$INSTDIR\JCodex.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JCodex" "UninstallString" '"$INSTDIR\uninstall.exe"'
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\uninstall.exe"
  RMDir /r "$INSTDIR"
  Delete "$SMPROGRAMS\JCodex.lnk"
  Delete "$DESKTOP\JCodex.lnk"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\JCodex"
SectionEnd
