$ErrorActionPreference = "Continue"
$env:Path = "C:\Program Files\nodejs;" + $env:Path

Write-Host "HRV dashboard keep-alive runner"
Write-Host "URL: http://127.0.0.1:5173/"
Write-Host "Close this window or press Ctrl+C to stop."

while ($true) {
  Write-Host "Starting Vite dashboard..."
  & "C:\Program Files\nodejs\npm.cmd" run dev -- --host 127.0.0.1 --port 5173
  $exitCode = $LASTEXITCODE
  Write-Host "Dashboard process exited with code $exitCode. Restarting in 2 seconds..."
  Start-Sleep -Seconds 2
}
