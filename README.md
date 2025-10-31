# 🖨️ Sistema Distribuído de Impressão com Exclusão Mútua (Ricart–Agrawala)
## 📖 Descrição
Este projeto implementa um sistema distribuído onde múltiplos clientes competem
pelo acesso exclusivo a um servidor de impressão **burro**, utilizando:

- **gRPC** para comunicação entre processos
- **Algoritmo de Ricart–Agrawala** para exclusão mútua distribuída
- **Relógios Lógicos de Lamport** para sincronização de eventos

---

## Autores

- Pedro Rodrigues Alves
- Lucas Quaresma
- Gabriel Gualtieri

## Orientador

- Matheus

## 🧱 Estrutura

- distributed_printing/
- ├── distributed_printing.proto
- ├── printer_server.py
- ├── printing_client.py
- ├── start_printer.sh
- ├── start_client.sh
- └── README.md
---

## ⚙️ Instalação
```bash 
 pip install grpcio grpcio-tools protobuf
```

## ⚙️ Execução
 
Para gerar os stubs:
```bash 
 python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. distributed_printing.proto
 ```

Para colocar em execução o server:
```bash
python3 printer_server.py --port 50051
 ```

Para colocar em execução o cliente:
```bash
python3 printing_client.py --id $ID --server localhost:50051 --port $PORT --clients localhost:$PEERS,localhost:$PEERS
```
Aonde esta os "$", deverão ter seus valores substituidos, por exemplo:
- python3 printing_client.py --id 1 --server localhost:50051 --port 50052 --clients localhost:50053,localhost:50054

### Exemplo de execução

No primeiro terminal faça:
```bash
    python3 printer_server.py --port 50051
```
No segundo terminal faça:
```bash
    python3 printing_client.py --id 1 --server localhost:50051 --port 50052 --clients localhost:50053,localhost:50054
```
No terceiro terminal faça:
```bash
    python3 printing_client.py --id 2 --server localhost:50051 --port 50053 --clients localhost:50052,localhost:50054
```
no quarto terminal faça:
```bash    
    python3 printing_client.py --id 3 --server localhost:50051 --port 50054 --clients localhost:50052,localhost:50053
```