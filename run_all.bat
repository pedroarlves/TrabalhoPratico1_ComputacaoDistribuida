@echo off
REM ==========================================
REM Executa o servidor burro e 3 clientes
REM ==========================================
set SERVER_PORT=50051
set CLIENT1_PORT=50052
set CLIENT2_PORT=50053
set CLIENT3_PORT=50054

echo Iniciando servidor de impressão...
start cmd /k python printer_server.py --port %SERVER_PORT%

timeout /t 2 >nul

echo Iniciando Cliente 1...
start cmd /k python printing_client.py --id 1 --server localhost:%SERVER_PORT% --port %CLIENT1_PORT% --clients localhost:%CLIENT2_PORT%,localhost:%CLIENT3_PORT%

timeout /t 1 >nul

echo Iniciando Cliente 2...
start cmd /k python printing_client.py --id 2 --server localhost:%SERVER_PORT% --port %CLIENT2_PORT% --clients localhost:%CLIENT1_PORT%,localhost:%CLIENT3_PORT%

timeout /t 1 >nul

echo Iniciando Cliente 3...
start cmd /k python printing_client.py --id 3 --server localhost:%SERVER_PORT% --port %CLIENT3_PORT% --clients localhost:%CLIENT1_PORT%,localhost:%CLIENT2_PORT%

echo Todos os processos foram iniciados.
pause
