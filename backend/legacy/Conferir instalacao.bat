@echo off
rem Confere o que o app de tubuloes precisa (Python 3.13, numpy, matplotlib, Pillow, pacote e instalacao do TQS, Edge).
setlocal
cd /d "%~dp0"
call "%~dp0_achar_python.bat"
if errorlevel 1 goto sem_python
"%PY313%" "%~dp0dependencias.py"
echo.
pause
exit /b 0

:sem_python
echo.
echo  Nao achei o Python 3.13 neste computador. Veja o LEIA-ME.md.
echo.
pause
exit /b 1
