@echo off
chcp 65001 >nul
cls
echo.
echo ╔═══════════════════════════════════════════════════════════╗
echo ║           SISTEMA ACADÊMICO - INICIANDO COM WEBSOCKET     ║
echo ╚═══════════════════════════════════════════════════════════╝
echo.

:: ========================================
:: 1. Inicia o servidor
:: ========================================
echo [1/3] Iniciando servidor FastAPI + WebSocket...
start /B python servidor.py > backend.log 2>&1

:: ========================================
:: 2. Espera o WebSocket estar ATIVO
:: ========================================
echo [2/3] Testando conexão com WebSocket (máx. 30s)...
set "count=0"

:check_websocket
set /a count+=1
timeout /t 2 >nul

:: Testa se a rota do Socket.IO responde
curl -s "http://localhost:8000/socket.io/?EIO=4&transport=polling" | findstr /C:"sid" >nul 2>&1
if %errorlevel% == 0 (
    echo [OK] WebSocket CONECTADO! (tentativa %count%)
    goto :websocket_ok
)

if %count% geq 15 (
    echo.
    echo [ERRO] WebSocket NÃO respondeu após 30 segundos.
    echo        Verifique:
    echo        • servidor.py está rodando?
    echo        • porta 8000 livre?
    echo        • log em backend.log
    echo.
    type backend.log
    echo.
    pause
    exit /b 1
)

echo    Aguardando... (tentativa %count%/15)
goto :check_websocket

:websocket_ok

:: ========================================
:: 3. Abre a interface
:: ========================================
echo [3/3] Abrindo interface gráfica...
echo.
echo    WebSocket: ATIVO
echo    Interface: ABRINDO...
echo.
start "" /wait "dist\sistema.exe"

:: ========================================
:: 4. Fecha tudo ao final
:: ========================================
echo.
echo [FECHANDO] Encerrando servidor...
taskkill /F /IM python.exe >nul 2>&1
echo [OK] Sistema encerrado com sucesso.
echo.
pause
