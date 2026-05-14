#requires -Version 5.1
<#
.SYNOPSIS
  AUREM Legion Daemon — 1-click bootstrap for Windows.

.DESCRIPTION
  Single command to bring the Legion reverse-poll daemon back online.
  Auto-detects if the daemon lives in WSL Ubuntu, Docker, or native
  Windows. Kills any stale instance first, then relaunches detached
  with full logging. Verifies the daemon polled the cloud queue at
  least once before returning.

  Run this once after a reboot or laptop sleep. Idempotent — safe to
  run repeatedly.

.PARAMETER BackendUrl
  AUREM cloud backend (default: https://aurem.live).

.PARAMETER Token
  Reads LEGION_DAEMON_TOKEN from this env var or user-scope variable.
  If unset, prompts once and persists to the user environment.

.PARAMETER WslDistro
  WSL distro name (default: Ubuntu).

.EXAMPLE
  PS> .\start_legion.ps1
#>

[CmdletBinding()]
param(
    [string]$BackendUrl = "https://aurem.live",
    [string]$Token      = $env:LEGION_DAEMON_TOKEN,
    [string]$WslDistro  = "Ubuntu"
)

$ErrorActionPreference = "Stop"
$logFile = "$env:USERPROFILE\legion_bootstrap.log"
function Log($msg) {
    $stamp = (Get-Date).ToString("HH:mm:ss")
    Write-Host "[$stamp] $msg" -ForegroundColor Cyan
    Add-Content -Path $logFile -Value "[$stamp] $msg"
}

Log "AUREM Legion bootstrap starting…"

# ─── Step 1: ensure token is set ──────────────────────────────────────
if (-not $Token) {
    Log "LEGION_DAEMON_TOKEN not found in environment."
    $Token = Read-Host -Prompt "Paste your LEGION_DAEMON_TOKEN (will be saved to user env)"
    if (-not $Token) { throw "Token is required." }
    [Environment]::SetEnvironmentVariable("LEGION_DAEMON_TOKEN", $Token, "User")
    $env:LEGION_DAEMON_TOKEN = $Token
    Log "Token persisted to user environment."
}

# ─── Step 2: detect where the daemon lives ────────────────────────────
$location = $null
$daemonPath = $null

# 2a. Check WSL.
try {
    $wslCheck = & wsl.exe -d $WslDistro -e bash -c "command -v python3 && find ~ /opt /home -maxdepth 4 -name 'legion_daemon.py' 2>/dev/null | head -1" 2>$null
    if ($wslCheck -and $wslCheck -match "legion_daemon\.py") {
        $location = "wsl"
        $daemonPath = ($wslCheck | Select-String "legion_daemon\.py").Line.Trim()
        Log "Detected daemon in WSL ($WslDistro): $daemonPath"
    }
} catch { }

# 2b. Check native Windows.
if (-not $location) {
    $found = Get-ChildItem -Path "$env:USERPROFILE", "C:\AUREM", "C:\opt" `
        -Filter "legion_daemon.py" -Recurse -ErrorAction SilentlyContinue `
        | Select-Object -First 1
    if ($found) {
        $location = "windows"
        $daemonPath = $found.FullName
        Log "Detected daemon in Windows: $daemonPath"
    }
}

if (-not $location) {
    throw @"
legion_daemon.py not found in WSL Ubuntu OR Windows user dirs.

Options:
  1. Paste the file path manually:  .\start_legion.ps1 -DaemonPath <full path>
  2. Re-clone the AUREM repo on this machine
  3. Open the cloudflare-tunnel tab — daemon may be inside another container
"@
}

# ─── Step 3: kill any existing instance ───────────────────────────────
Log "Killing any zombie daemon processes…"
if ($location -eq "wsl") {
    & wsl.exe -d $WslDistro -e bash -c "pkill -9 -f legion_daemon.py 2>/dev/null; sleep 1; pgrep -f legion_daemon.py | wc -l" | Out-Null
} else {
    Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -and (Get-Content -Path "$($_.Path).cmdline" -ErrorAction SilentlyContinue) -match "legion_daemon"
    } | Stop-Process -Force -ErrorAction SilentlyContinue
}

# ─── Step 4: relaunch detached ────────────────────────────────────────
Log "Launching daemon detached…"
if ($location -eq "wsl") {
    $cmd = @"
export LEGION_DAEMON_TOKEN='$Token'
export AUREM_BACKEND_URL='$BackendUrl'
cd `$(dirname '$daemonPath')
nohup python3 '$daemonPath' > ~/legion_daemon.log 2>&1 &
echo `$!
"@
    $pid = & wsl.exe -d $WslDistro -e bash -c $cmd
    Log "Daemon launched in WSL (pid=$pid). Log: ~/legion_daemon.log"
} else {
    $logPath = "$env:USERPROFILE\legion_daemon.log"
    $proc = Start-Process -FilePath "python" `
        -ArgumentList "`"$daemonPath`"" `
        -RedirectStandardOutput $logPath `
        -RedirectStandardError "$logPath.err" `
        -WindowStyle Hidden -PassThru
    Log "Daemon launched in Windows (pid=$($proc.Id)). Log: $logPath"
}

# ─── Step 5: verify ───────────────────────────────────────────────────
Log "Verifying daemon checks in with cloud backend (up to 90s)…"
$verified = $false
for ($i = 1; $i -le 18; $i++) {
    Start-Sleep -Seconds 5
    try {
        $resp = Invoke-RestMethod -Uri "$BackendUrl/api/system/uptime" -TimeoutSec 8
        $status = $resp.ora.status
        $age = $resp.ora.daemon_last_poll_seconds_ago
        Log "Attempt $i/18 — ora.status=$status, last_poll=${age}s ago"
        if ($status -eq "online") {
            $verified = $true
            break
        }
    } catch {
        Log "Attempt $i/18 — backend probe failed: $($_.Exception.Message)"
    }
}

if ($verified) {
    Log "✅ Daemon is ONLINE. Campaign engine + ORA chat are live."
    Write-Host "`n✅ AUREM Legion daemon is online." -ForegroundColor Green
    exit 0
} else {
    Log "❌ Daemon launched but never polled the cloud queue. Check logs."
    if ($location -eq "wsl") {
        Write-Host "`nLast 20 lines of daemon log:" -ForegroundColor Yellow
        & wsl.exe -d $WslDistro -e bash -c "tail -20 ~/legion_daemon.log"
    } else {
        Write-Host "`nLast 20 lines of daemon log:" -ForegroundColor Yellow
        Get-Content "$env:USERPROFILE\legion_daemon.log" -Tail 20
    }
    exit 1
}
