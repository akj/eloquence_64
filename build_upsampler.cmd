@echo off

echo Building upsampler DLLs...

set "MSYS2_CANDIDATES=C:\msys64"
if not "%MSYS2_ROOT%" == "" set "MSYS2_CANDIDATES=%MSYS2_CANDIDATES%;%MSYS2_ROOT%"
if not "%MSYS2_LOCATION%" == "" set "MSYS2_CANDIDATES=%MSYS2_CANDIDATES%;%MSYS2_LOCATION%"
if not "%CD%" == "" set "MSYS2_CANDIDATES=%MSYS2_CANDIDATES%;%CD%\msys64"
if not "%GITHUB_WORKSPACE%" == "" set "MSYS2_CANDIDATES=%MSYS2_CANDIDATES%;%GITHUB_WORKSPACE%\msys64"
if not "%RUNNER_TEMP%" == "" set "MSYS2_CANDIDATES=%MSYS2_CANDIDATES%;%RUNNER_TEMP%\setup-msys2\msys64"
if not "%RUNNER_TEMP%" == "" set "MSYS2_CANDIDATES=%MSYS2_CANDIDATES%;%RUNNER_TEMP%\setup-msys2"

REM --- 64-bit build ---
set "MINGW64_BIN="
for %%R in ("%MSYS2_CANDIDATES:;=" "%") do (
    if exist "%%~R\mingw64\bin\gcc.exe" set "MINGW64_BIN=%%~R\mingw64\bin"
)
if "%MINGW64_BIN%" == "" (
    echo MinGW64 not found!
    echo Checked MSYS2 roots: %MSYS2_CANDIDATES%
    exit /b 1
)

echo Building 64-bit...
set "PATH=%MINGW64_BIN%;%PATH%"
"%MINGW64_BIN%\gcc.exe" -shared -static-libgcc -o upsampler64.dll upsampler.c
if %errorlevel% neq 0 exit /b %errorlevel%

REM --- 32-bit build ---
set "MINGW32_BIN="
for %%R in ("%MSYS2_CANDIDATES:;=" "%") do (
    if exist "%%~R\mingw32\bin\gcc.exe" set "MINGW32_BIN=%%~R\mingw32\bin"
)
if "%MINGW32_BIN%" == "" (
    echo MinGW32 not found!
    echo Checked MSYS2 roots: %MSYS2_CANDIDATES%
    exit /b 1
)

echo Building 32-bit...
set "PATH=%MINGW32_BIN%;%PATH%"
"%MINGW32_BIN%\gcc.exe" -shared -static-libgcc -o upsampler32.dll upsampler.c
if %errorlevel% neq 0 exit /b %errorlevel%

echo Copying DLLs...

copy /Y upsampler64.dll addon\synthDrivers\
copy /Y upsampler32.dll addon\synthDrivers\

echo Done!
