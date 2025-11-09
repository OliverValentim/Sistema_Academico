@echo off
title SISTEMA ACADEMICO COLABORATIVO - PIM [DS2P44]
color 0A
mode con: cols=90 lines=30
cls

echo.
echo ╔═══════════════════════════════════════════════════════════════════════════╗
echo ║     SISTEMA ACADEMICO COLABORATIVO - PIM                                  ║
echo ║     Turma: DS2P44                                                         ║
echo ║     Lider: Oliver Valentim Carvalho Santos                                ║
echo ╚═══════════════════════════════════════════════════════════════════════════╝
echo.
echo [1/4] Mudando para pasta do projeto...
cd /d "%~dp0"

echo.
echo [2/4] Verificando ambiente virtual...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo     Ambiente virtual ativado!
) else (
    echo     Sem venv - usando Python global
)

echo.
echo [3/4] Instalando/atualizando dependencias...
pip install -q fastapi uvicorn python-socketio[asyncio] psycopg2-binary passlib[bcrypt] python-jose[cryptography] pydantic

echo.
echo [4/4] INICIANDO SERVIDOR EM SEGUNDO PLANO...
echo.
echo ╔═══════════════════════════════════════════════════════════════════════════╗
echo ║   SERVIDOR: http://localhost:8000                                         ║
echo ║   CLIENTE:  Abrindo automaticamente em 5 segundos...                     ║
echo ╚═══════════════════════════════════════════════════════════════════════════╝
echo.

:: === RODA O SERVIDOR EM SEGUNDO PLANO ===
start "" /min cmd /c "uvicorn servidor:app_sio --host 0.0.0.0 --port 8000 --log-level info"

:: === ESPERA O SERVIDOR SUBIR ===
timeout /t 5 >nul

:: === ABRE O CLIENTE ===
echo.
echo [OK] SERVIDOR RODANDO! INICIANDO CLIENTE...
start "" "dist\ClienteApp.exe"

echo.
echo ╔═══════════════════════════════════════════════════════════════════════════╗
echo ║                         SISTEMA RODANDO!                                  ║
echo ║   - Servidor: http://localhost:8000                                       ║
echo ║   - Cliente aberto automaticamente                                        ║
echo ║   - Para parar: Feche esta janela ou Ctrl+C no servidor                   ║
echo ╚═══════════════════════════════════════════════════════════════════════════╝
echo.

:: === MANTÉM A JANELA ABERTA ===
pause