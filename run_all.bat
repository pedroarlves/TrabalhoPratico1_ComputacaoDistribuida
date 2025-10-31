@echo off
REM =========================================
REM Script para iniciar servidor e clientes
REM =========================================

REM Servidor burro
start cmd /k "python printer_server.py --port 50051"

REM Pausa curta para garantir que o servidor suba antes dos clientes
timeout /t 2 /nobreak >nul

REM Cliente 1
start cmd /k "python printing_client.py --id 1 --server localhost:50051 --port 50052 --clients localhost:50053,localhost:50054"

REM Cliente 2
start cmd /k "python printing_client.py --id 2 --server localhost:50051 --port 50053 --clients localhost:50052,localhost:50054"

REM Cliente 3
start cmd /k "python printing_client.py --id 3 --server localhost:50051 --port 50054 --clients localhost:50052,localhost:50053"

echo ==================================================
echo 🚀 Todos os processos iniciados!
echo ==================================================
pause
