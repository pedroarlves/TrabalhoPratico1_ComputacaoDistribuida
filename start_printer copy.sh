#!/bin/bash
# Exemplo: ./start_client.sh 1 50052 50053 50054
cd C:\hHhH\PERIODO_6\ComputaçãoDistribuida\TrabalhoPratico1_ComputacaoDistribuida
ID=$1
PORT=$2
shift 2
PEERS=$@
python3 client.py --id $ID --port $PORT --peers $PEERS
