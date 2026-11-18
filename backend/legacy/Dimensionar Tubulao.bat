@echo off
rem Abre o aplicativo de dimensionamento de tubuloes curtos (copia portatil) no Python 3.13.
setlocal
cd /d "%~dp0"
call "%~dp0_achar_python.bat"
if errorlevel 1 goto sem_python
start "" "%PYW313%" "%~dp0tubulao_app.pyw" %*
exit /b 0

:sem_python
echo.
echo  Nao achei o Python 3.13 neste computador.
echo.
echo  1. Instale o Python 3.13 (python.org), marcando "tcl/tk and IDLE" e o lancador "py".
echo  2. Nesta pasta:  py -3.13 -m pip install -r requirements.txt
echo  3. Para gravar o DWG: com o TQS fechado, rode o EXEC\X64\TQSPYINST.EXE da instalacao do TQS.
echo.
echo  Detalhes no LEIA-ME.md.
echo.
pause
exit /b 1
