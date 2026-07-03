@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM Claude Code / Gemini CLI Telemetry Setup
REM Run once per machine. No administrator rights required.
REM ============================================================

echo.
echo ============================================================
echo  Telemetry Setup
echo ============================================================
echo.

REM Set this to your OTEL collector's endpoint before running, e.g.:
REM   set OTEL_ENDPOINT=http://otel-collector.example.com:4317
if "%OTEL_ENDPOINT%"=="" (
    echo ERROR: OTEL_ENDPOINT is not set.
    echo   Run: set OTEL_ENDPOINT=http://<your-collector-host>:4317 ^&^& %~nx0
    goto :error
)

REM ------------------------------------------------------------
REM 1. Set user-scoped environment variables
REM ------------------------------------------------------------
echo [1/3] Setting environment variables...

setx CLAUDE_CODE_ENABLE_TELEMETRY "1" >nul 2>&1
setx GEMINI_TELEMETRY_ENABLED "true" >nul 2>&1
setx GEMINI_TELEMETRY_USE_COLLECTOR "true" >nul 2>&1
setx OTEL_METRICS_EXPORTER "otlp" >nul 2>&1
setx OTEL_LOGS_EXPORTER "otlp" >nul 2>&1
setx OTEL_EXPORTER_OTLP_PROTOCOL "grpc" >nul 2>&1
setx OTEL_EXPORTER_OTLP_ENDPOINT "%OTEL_ENDPOINT%" >nul 2>&1

echo     Done.

REM ------------------------------------------------------------
REM 2. Install PowerShell profile hook
REM ------------------------------------------------------------
echo.
echo [2/3] Installing PowerShell profile hook...

REM Determine the CurrentUser,CurrentHost profile path
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$PROFILE.CurrentUserCurrentHost"`) do set "PS_PROFILE=%%P"

if "%PS_PROFILE%"=="" (
    echo     ERROR: Could not determine PowerShell profile path.
    goto :error
)

REM Create the profile directory if it does not exist
for %%D in ("%PS_PROFILE%") do set "PS_PROFILE_DIR=%%~dpD"
if not exist "%PS_PROFILE_DIR%" mkdir "%PS_PROFILE_DIR%" >nul 2>&1

REM Write the installer .ps1 to a temp file using >> appends
REM (avoids the ( ... ) block paren-counting issue that broke the previous version)
set "TMP_PS1=%TEMP%\install-telemetry-hook.ps1"
if exist "%TMP_PS1%" del "%TMP_PS1%" >nul 2>&1

>"%TMP_PS1%"  echo $marker = '# ^>^>^> telemetry-project-hook ^>^>^>'
>>"%TMP_PS1%" echo $endMarker = '# ^<^<^< telemetry-project-hook ^<^<^<'
>>"%TMP_PS1%" echo.
>>"%TMP_PS1%" echo $hook = @'
>>"%TMP_PS1%" echo # ^>^>^> telemetry-project-hook ^>^>^>
>>"%TMP_PS1%" echo function global:Set-OtelProjectFromEnvFile {
>>"%TMP_PS1%" echo     $dir = Get-Location
>>"%TMP_PS1%" echo     while ^($true^) {
>>"%TMP_PS1%" echo         $candidate = Join-Path $dir.Path '.env.project'
>>"%TMP_PS1%" echo         if ^(Test-Path $candidate^) {
>>"%TMP_PS1%" echo             $line = Get-Content $candidate ^| Where-Object { $_ -match '^^PROJECT_SLUG=' } ^| Select-Object -First 1
>>"%TMP_PS1%" echo             if ^($line^) {
>>"%TMP_PS1%" echo                 $slug = $line -replace '^^PROJECT_SLUG=', '' -replace '[\r\n]', ''
>>"%TMP_PS1%" echo                 $env:OTEL_RESOURCE_ATTRIBUTES = "project=$slug"
>>"%TMP_PS1%" echo                 return
>>"%TMP_PS1%" echo             }
>>"%TMP_PS1%" echo         }
>>"%TMP_PS1%" echo         $parent = Split-Path $dir.Path -Parent
>>"%TMP_PS1%" echo         if ^(-not $parent -or $parent -eq $dir.Path^) { break }
>>"%TMP_PS1%" echo         $dir = Get-Item $parent
>>"%TMP_PS1%" echo     }
>>"%TMP_PS1%" echo     $env:OTEL_RESOURCE_ATTRIBUTES = $null
>>"%TMP_PS1%" echo }
>>"%TMP_PS1%" echo.
>>"%TMP_PS1%" echo if ^(-not ^(Test-Path Function:\global:_TelemetryOriginalPrompt^)^) {
>>"%TMP_PS1%" echo     Copy-Item Function:\prompt Function:\global:_TelemetryOriginalPrompt -ErrorAction SilentlyContinue
>>"%TMP_PS1%" echo }
>>"%TMP_PS1%" echo function global:prompt {
>>"%TMP_PS1%" echo     Set-OtelProjectFromEnvFile
>>"%TMP_PS1%" echo     if ^(Test-Path Function:\global:_TelemetryOriginalPrompt^) {
>>"%TMP_PS1%" echo         ^& $function:_TelemetryOriginalPrompt
>>"%TMP_PS1%" echo     } else {
>>"%TMP_PS1%" echo         'PS ' + ^(Get-Location^) + '^> '
>>"%TMP_PS1%" echo     }
>>"%TMP_PS1%" echo }
>>"%TMP_PS1%" echo # ^<^<^< telemetry-project-hook ^<^<^<
>>"%TMP_PS1%" echo '@
>>"%TMP_PS1%" echo.
>>"%TMP_PS1%" echo $profilePath = '%PS_PROFILE%'
>>"%TMP_PS1%" echo $existing = if ^(Test-Path $profilePath^) { Get-Content $profilePath -Raw } else { '' }
>>"%TMP_PS1%" echo $start = $existing.IndexOf^($marker^)
>>"%TMP_PS1%" echo $end   = $existing.IndexOf^($endMarker^)
>>"%TMP_PS1%" echo if ^($start -ge 0 -and $end -ge 0^) {
>>"%TMP_PS1%" echo     $before   = $existing.Substring^(0, $start^)
>>"%TMP_PS1%" echo     $after    = $existing.Substring^($end + $endMarker.Length^)
>>"%TMP_PS1%" echo     $existing = $before + $hook.Trim^(^) + $after
>>"%TMP_PS1%" echo } else {
>>"%TMP_PS1%" echo     $existing = $existing.TrimEnd^(^) + "`n`n" + $hook.Trim^(^) + "`n"
>>"%TMP_PS1%" echo }
>>"%TMP_PS1%" echo Set-Content -Path $profilePath -Value $existing -Encoding UTF8

powershell -NoProfile -ExecutionPolicy Bypass -File "%TMP_PS1%"

if %errorlevel% neq 0 (
    echo     ERROR: Failed to write PowerShell profile.
    del "%TMP_PS1%" >nul 2>&1
    goto :error
)

del "%TMP_PS1%" >nul 2>&1
echo     Written to: %PS_PROFILE%

REM ------------------------------------------------------------
REM 3. Done
REM ------------------------------------------------------------
echo.
echo [3/3] Setup complete.
echo.
echo  Next steps:
echo   - Close and reopen any PowerShell or Windows Terminal windows.
echo   - Restart VS Code if it is open.
echo   - In each repo, the .env.project file handles project tagging
echo     automatically when you cd into the folder.
echo   - Run verify.ps1 (see setup guide) to confirm everything is set.
echo.
pause
exit /b 0

:error
echo.
echo  Setup did not complete successfully.
echo  Check the error above and retry, or run the manual steps in the setup guide.
echo.
pause
exit /b 1