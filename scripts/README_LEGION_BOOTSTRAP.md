# AUREM Legion Daemon — Windows Bootstrap

`start_legion.ps1` is a 1-click PowerShell script that brings the Legion
reverse-poll daemon back online after a laptop reboot or sleep.

## What it does
1. Reads `LEGION_DAEMON_TOKEN` from your user environment (prompts + persists if missing).
2. Auto-detects whether the daemon lives in WSL Ubuntu or native Windows.
3. Kills any stale daemon instance.
4. Relaunches the daemon detached with full logging.
5. Polls `https://aurem.live/api/system/uptime` for up to 90 s and reports
   success only after the daemon actually checked in with the cloud.

## One-time setup
1. Download `start_legion.ps1` to `C:\Users\tejis\start_legion.ps1`.
2. Open PowerShell as Administrator (once) and allow local scripts:
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
   ```
3. (Optional) Pin to the Windows Startup folder so it runs on boot:
   ```powershell
   $startup = [Environment]::GetFolderPath('Startup')
   Copy-Item C:\Users\tejis\start_legion.ps1 "$startup\start_legion.ps1"
   New-Item -ItemType File -Path "$startup\start_legion.cmd" -Value "powershell.exe -ExecutionPolicy Bypass -File `"$startup\start_legion.ps1`""
   ```

## Daily usage
After laptop wakes from sleep, just open PowerShell and run:
```powershell
C:\Users\tejis\start_legion.ps1
```

Expected end-of-run output:
```
✅ AUREM Legion daemon is online.
```

## If it fails
The script prints the last 20 lines of `legion_daemon.log`. Common causes:
- **Token expired** — re-paste it when prompted (script will persist it).
- **Ollama not running** — `ollama serve` in a separate window first, then re-run.
- **WSL distro name differs** — pass it explicitly: `.\start_legion.ps1 -WslDistro Ubuntu-22.04`.
- **Cloudflare tunnel down** — open the `cloudflare-tunnel` Windows Terminal tab and confirm the tunnel is healthy.
