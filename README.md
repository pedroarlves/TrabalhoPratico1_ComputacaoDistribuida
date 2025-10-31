# 🖨️ Sistema Distribuído de Impressão com Exclusão Mútua (Ricart–Agrawala)

## 📖 Descrição

Este projeto implementa um **sistema distribuído de impressão** no qual múltiplos clientes competem pelo acesso exclusivo a um **servidor de impressão burro**.
A coordenação entre os clientes é feita através do **algoritmo de Ricart–Agrawala**, garantindo exclusão mútua sem a necessidade de um coordenador central.

São utilizados:

* **gRPC** → comunicação entre processos distribuídos
* **Relógios Lógicos de Lamport** → ordenação de eventos
* **Python 3.10+** → linguagem de implementação

---

## 👨‍💻 Autores

* Pedro Rodrigues Alves
* Lucas Gualtieri Firace Evangelista
* Gabriel Felipe Quaresma de Oliveira

### 👨‍🏫 Orientador

* Matheus Barros Pereira


---

## 🧱 Estrutura do Projeto

```
distributed_printing/
├── distributed_printing.proto       # Definições dos serviços e mensagens gRPC
├── printer_server.py                # Servidor burro de impressão
├── printing_client.py               # Cliente com exclusão mútua (Ricart–Agrawala)
├── run_all.bat                      # Execução automática no Windows
└── README.md                        # Este arquivo
```

---

## ⚙️ Instalação

Antes de executar, instale as dependências:

```bash
pip install grpcio grpcio-tools protobuf
```

---

## ⚙️ Geração dos Stubs gRPC

Após criar ou editar o arquivo `.proto`, gere os stubs Python com:

```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. distributed_printing.proto
```

---

## 🚀 Execução

### 🖨️ Servidor de impressão (burro)

O servidor apenas **recebe requisições** e “imprime” (mostra no terminal).

```bash
python printer_server.py --port 50051
```

Saída esperada:

```
🖨️  Servidor de impressão burro rodando na porta 50051
```

---

### 💻 Cliente

Cada cliente roda em um terminal separado e precisa conhecer:

* seu **ID** único
* sua **porta local**
* o **endereço do servidor de impressão**
* os **endereços dos outros clientes** (peers)

Exemplo geral:

```bash
python printing_client.py --id $ID --server localhost:50051 --port $PORT --clients localhost:$PEER1,localhost:$PEER2
```

Substitua `$ID`, `$PORT`, `$PEER1`, `$PEER2` pelos valores reais.

---

## 🧩 Exemplos de Execução

### 🔹 Cenário com 3 clientes

No **primeiro terminal**:

```bash
python printer_server.py --port 50051
```

No **segundo terminal**:

```bash
python printing_client.py --id 1 --server localhost:50051 --port 50052 --clients localhost:50053,localhost:50054
```

No **terceiro terminal**:

```bash
python printing_client.py --id 2 --server localhost:50051 --port 50053 --clients localhost:50052,localhost:50054
```

No **quarto terminal**:

```bash
python printing_client.py --id 3 --server localhost:50051 --port 50054 --clients localhost:50052,localhost:50053
```

Durante a execução, somente **um cliente por vez** acessará a impressora, respeitando a exclusão mútua.

---

### 🔹 Cenário com 1 cliente

No **primeiro terminal**:

```bash
python printer_server.py --port 50051
```

No **segundo terminal**:

```bash
python printing_client.py --id 1 --server localhost:50051 --port 50052 --clients ""
```

Neste caso, o cliente **entra diretamente na seção crítica**, já que não há peers.

---

## 🪵 Logs do Sistema

### 🖨️ Logs do Servidor

Exemplo:

```
🖨️  Servidor de impressão burro rodando na porta 50051

🖨️  RECEBIDO PEDIDO DE IMPRESSÃO
  Cliente: 1
  Mensagem: Doc cliente 1 (ts=13)
  Timestamp Lamport (do cliente): 18
✅ IMPRESSO: [TS: 18] CLIENTE 1: Doc cliente 1 (ts=13)
```

🟢 **Significados:**

* `RECEBIDO PEDIDO DE IMPRESSÃO`: uma requisição chegou.
* `Timestamp Lamport`: tempo lógico do cliente.
* `✅ IMPRESSO`: a mensagem foi “impressa” com sucesso.

---

### 💬 Logs do Cliente

Durante a execução, cada cliente exibe logs que mostram o estado do algoritmo.

#### 🛰️ Inicialização

```
🛰️ [Cliente 1] Servidor gRPC ativo na porta 50052
🏃 [Cliente 1] Iniciando loop principal. Peers: ['localhost:50053', 'localhost:50054']
```

> O cliente está online e pronto para participar da exclusão mútua.

#### 🆘 Pedido de acesso à seção crítica

```
🆘 [Cliente 1] Solicitando acesso (ts=12)
```

> Cliente deseja entrar na seção crítica (impressão). `ts=12` é seu timestamp Lamport.

#### 📨 Pedido recebido por outro cliente

```
📨 [Cliente 2] RequestAccess recebido de 1 (ts=12)
```

> O cliente 2 recebeu o pedido do cliente 1 e vai decidir se concede ou adia.

#### ⏳ Pedido adiado (deferido)

```
⏳ [Cliente 2] Deferindo pedido de 1 (meu ts=14)
```

> Cliente 2 está com prioridade (ts menor) e adia o pedido de 1 até liberar.

#### ✅ Concessão de acesso

```
✅ [Cliente 2] Concedendo acesso a 1 (resposta ts=15)
📥 [Cliente 1] Ack recebido de localhost:50053
```

> Cliente 2 concedeu permissão; Cliente 1 recebeu o ACK.

#### ✅ Entrada na seção crítica

```
✅ [Cliente 1] Entrou na seção crítica.
🖨️ [Cliente 1] Resposta da impressora: Impressão concluída
```

> Cliente 1 tem acesso exclusivo ao servidor e envia seu documento.

#### 🚪 Saída da seção crítica

```
🚪 [Cliente 1] Saindo da seção crítica.
🔔 [Cliente 2] ReleaseAccess recebido de 1 (ts=18)
```

> Cliente 1 terminou e liberou o acesso; clientes aguardando são notificados.

#### ⚠️ Falha ou timeout

```
⚠️ [Cliente 1] Não obteve ack de todos os peers (1/2). Abortando pedido e tentando depois.
```

> Indica que algum peer não respondeu — o cliente libera o pedido e tentará novamente.

#### ❌ Erros de comunicação

```
❌ [Cliente 3] Falha RequestAccess em localhost:50053: StatusCode.UNAVAILABLE
```

> O peer estava offline ou inacessível (timeout ou erro de rede).

---

## 🕰️ Relógio Lógico de Lamport

Cada evento importante (envio, recebimento, impressão) é acompanhado de um timestamp `ts` lógico.
Regras aplicadas:

1. Antes de **enviar** qualquer mensagem → `increment()`
2. Ao **receber** uma mensagem → `update(received_ts) = max(local, recebido) + 1`

Isso garante que os eventos sejam **ordenados causalmente** no sistema.

---

## 🔒 Algoritmo de Ricart–Agrawala 


* O cliente solicita acesso (`RequestAccess`) a todos os peers.
* Cada peer:

  * **Concede** acesso se não estiver usando nem pedindo a seção crítica, ou
  * **Adia** a resposta se tiver prioridade.
* O cliente só entra na seção crítica **após receber ACK de todos os peers**.
* Ao liberar (`ReleaseAccess`), notifica todos os peers para reavaliar seus pedidos pendentes.

---

## 💡 Observações Finais

* O sistema garante **exclusão mútua distribuída**: apenas um cliente imprime por vez.
* O uso de **Lamport clocks** assegura ordenação consistente de eventos.
* O código inclui **timeouts e logs detalhados** para depuração.

---

## 🧩 Scripts adicionais

### ▶️ Execução automática (Windows)

Use o arquivo `run_all.bat` para iniciar servidor e três clientes automaticamente:

```
run_all.bat
```

Cada processo abre em um novo terminal.

---

## ✅ Conclusão

Este projeto demonstra de forma prática como sistemas distribuídos podem coordenar o acesso a recursos compartilhados (como uma impressora) **sem servidor central**, utilizando apenas mensagens, tempos lógicos e cooperação entre nós.
O resultado é um sistema **seguro, determinístico e escalável**.
