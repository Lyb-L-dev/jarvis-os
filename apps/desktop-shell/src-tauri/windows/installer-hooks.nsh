!macro NSIS_HOOK_PREINSTALL
  ; Tauri's current-user default is $LOCALAPPDATA\${PRODUCTNAME}, which is
  ; also Jarvis OS's durable data root. Keep binaries in Programs so an
  ; uninstall can never remove configuration, backups, or update evidence.
  StrCpy $INSTDIR "$LOCALAPPDATA\Programs\${PRODUCTNAME}"
  ; Upgrade in place can otherwise retain resources removed by a newer
  ; release. This path contains bundle-owned files only; durable data lives
  ; in the separate $LOCALAPPDATA\Jarvis OS tree.
  RMDir /r "$INSTDIR\resources"
  SetOutPath $INSTDIR
!macroend

!macro NSIS_HOOK_POSTINSTALL
  ; Preserve the exact signed installer as the binary rollback entry for the
  ; next update. User data and database files are not stored in $INSTDIR.
  CreateDirectory "$LOCALAPPDATA\Jarvis OS\updates\rollback"
  CopyFiles /SILENT "$EXEPATH" "$LOCALAPPDATA\Jarvis OS\updates\rollback\previous-installer.exe"
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  ; Remove only reversible Windows integrations. User configuration, secrets,
  ; backups and PostgreSQL volumes intentionally remain untouched.
  ExecWait '"$INSTDIR\${MAINBINARYNAME}.exe" --cleanup-integrations' $0
!macroend
