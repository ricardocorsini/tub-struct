@echo off
rem Acha o Python 3.13 e define PY313 (python.exe) e PYW313 (pythonw.exe).
rem Usado pelos atalhos do app de tubuloes curtos (copia portatil; o mesmo das estacas). Sai com erro 1 se nao achar.
set "PY313="
set "PYW313="
rem 1) lancador "py" do Python do python.org
for /f "usebackq delims=" %%i in (`py -3.13 -c "import sys; print(sys.executable)" 2^>nul`) do set "PY313=%%i"
if defined PY313 if exist "%PY313%" goto achou
set "PY313="
rem 2) pastas usuais de instalacao
for %%d in ("%LOCALAPPDATA%\Programs\Python\Python313" "%ProgramFiles%\Python313" "C:\Python313") do (
    if not defined PY313 if exist "%%~d\python.exe" set "PY313=%%~d\python.exe"
)
if defined PY313 goto achou
rem 3) python do PATH, se for o 3.13
for /f "delims=" %%i in ('where python 2^>nul') do (
    if not defined PY313 (
        "%%i" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else 1)" >nul 2>nul && set "PY313=%%i"
    )
)
if not defined PY313 exit /b 1
:achou
for %%f in ("%PY313%") do set "PYW313=%%~dpfpythonw.exe"
if not exist "%PYW313%" set "PYW313=%PY313%"
exit /b 0
