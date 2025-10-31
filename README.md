# 🖨️ Sistema Distribuído de Impressão com Exclusão Mútua (Ricart–Agrawala)

## 📖 Descrição
Este projeto implementa um sistema distribuído onde múltiplos clientes competem
pelo acesso exclusivo a um servidor de impressão **burro**, utilizando:

- **gRPC** para comunicação entre processos
- **Algoritmo de Ricart–Agrawala** para exclusão mútua distribuída
- **Relógios Lógicos de Lamport** para sincronização de eventos

---

## 🧱 Estrutura

distributed_printing/
├── distributed_printing.proto
├── printer_server.py
├── client.py
├── start_printer.sh
├── start_client.sh
└── README.md
---

## ⚙️ Instalação

```bash
pip install grpcio grpcio-tools protobuf
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. distributed_printing.proto

## ⚙️ Execução

./start_printer.sh

 
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