@echo off
title SISTEMA ACADEMICO COLABORATIVO - PIM [DS2P44]
color 0A
mode con: cols=95 lines=35
cls
echo.
echo ╔══════════════════════════════════════════════════════════════════════════════╗
echo ║    SISTEMA ACADEMICO COLABORATIVO - PIM    ║
echo ║    Turma: DS2P44    ║
echo ║    Lider: Oliver V. C. Santos    ║
echo ╚══════════════════════════════════════════════════════════════════════════════╝
echo.

:: [1/4] Mudando para pasta do projeto
echo [1/4] Acessando pasta do projeto...
cd /d "%~dp0"
echo.

:: [BONUS] Criar venv se não existir
if not exist "venv\" (
    echo [BONUS] Criando ambiente virtual (venv)...
    python -m venv venv
    echo.
)

:: [2/4] Ativar venv
echo [2/4] Ativando ambiente virtual...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] Ambiente virtual ativado!
) else (
    echo [AVISO] Sem venv - usando Python global
)
echo.

:: [3/4] Atualizar pip + instalar dependências
echo [3/4] Atualizando pip e instalando dependencias...
python -m pip install --upgrade pip -q
pip install -q fastapi uvicorn "python-socketio[asyncio]" psycopg2-binary passlib[bcrypt] python-jose[cryptography] pydantic
echo [OK] Dependencias prontas!
echo.

:: Verificar arquivos críticos
if not exist "servidor.py" (
    echo [ERRO] Arquivo servidor.py nao encontrado!
    pause
    exit /b 1
)

:: [4/4] Iniciar servidor em segundo plano
echo [4/4] Iniciando servidor FastAPI...
start "" /min cmd /c "uvicorn servidor:app_sio --host 0.0.0.0 --port 8000 --log-level info"
timeout /t 5 >nul
echo [OK] Servidor rodando em http://localhost:8000
echo.

:: Abrir cliente .exe
if exist "dist\SistemaAcademico.exe" (
    echo [OK] Iniciando interface grafica...
    start "" "dist\SistemaAcademico.exe"
) else (
    echo [ERRO] Cliente nao encontrado: dist\SistemaAcademico.exe
    echo Execute: pyinstaller --onefile --windowed --icon=frontend/icon.ico --name SistemaAcademico frontend/cliente.py
    pause
    exit /b 1
)

echo.
echo ╔══════════════════════════════════════════════════════════════════════════════╗
echo ║                         SISTEMA EM EXECUCAO!                         ║
echo ║  Servidor: http://localhost:8000                                     ║
echo ║  Cliente: Aberto automaticamente                                     ║
echo ║  Para parar: Feche esta janela ou Ctrl+C no terminal do servidor     ║
echo ╚══════════════════════════════════════════════════════════════════════════════╝
echo.
pause