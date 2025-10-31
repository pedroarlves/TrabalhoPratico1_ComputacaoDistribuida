# TrabalhoPratico1_ComputacaoDistribuida
 
 Para gerar os stubs faça:
    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. distributed_printing.proto

No primeiro terminal faça:
    python printer_server.py

No segundo terminal faça:
    python client.py --id 1 --port 50052 --peers 50053 50054

No terceiro terminal faça:
    python client.py --id 2 --port 50053 --peers 50052 50054

no quarto terminal faça:
    python client.py --id 3 --port 50054 --peers 50052 50053