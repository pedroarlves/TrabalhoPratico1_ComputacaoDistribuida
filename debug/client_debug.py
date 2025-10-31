import grpc
import threading
import time
import random
from concurrent import futures
import argparse
import distributed_printing_pb2 as pb
import distributed_printing_pb2_grpc as rpc

# ---------------- CONFIGURAÇÃO ----------------
parser = argparse.ArgumentParser()
parser.add_argument("--id", type=int, required=True)
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--peers", nargs="*", type=int, default=[])
parser.add_argument("--printer_host", type=str, default="localhost:50051")
args = parser.parse_args()

CLIENT_ID = args.id
MY_PORT = args.port
PEER_PORTS = args.peers
PRINTER_ADDR = args.printer_host

# ---------------- VARIÁVEIS ----------------
lamport = 0
lamport_lock = threading.Lock()

requesting = False
in_critical = False
request_ts = None
deferred = set()
replies_received = set()
peers = {}

# ---------------- RELÓGIO LÓGICO ----------------
def increment():
    global lamport
    with lamport_lock:
        lamport += 1
        return lamport

def update(ts_remote):
    global lamport
    with lamport_lock:
        lamport = max(lamport, ts_remote) + 1
        return lamport

# ---------------- SERVIÇOS ----------------
class MutualExclusionServicer(rpc.MutualExclusionServiceServicer):
    def RequestAccess(self, request, context):
        update(request.lamport_timestamp)
        sender = request.client_id
        ts_sender = request.lamport_timestamp

        print(f"📥 [Cliente {CLIENT_ID}] Recebeu RequestAccess de {sender} (ts={ts_sender})")

        if in_critical or (requesting and (request_ts, CLIENT_ID) < (ts_sender, sender)):
            deferred.add(sender)
            print(f"⏳ [Cliente {CLIENT_ID}] Adiou resposta para {sender}")
        else:
            print(f"✅ [Cliente {CLIENT_ID}] Respondendo ACK para {sender}")
            threading.Thread(target=send_reply, args=(sender,)).start()

        return pb.AccessResponse(ack=True, lamport_timestamp=increment())

    def SendReply(self, request, context):
        update(request.lamport_timestamp)
        sender = request.from_client_id
        replies_received.add(sender)
        print(f"📨 [Cliente {CLIENT_ID}] Recebeu ACK de {sender}")
        return pb.EmptyResponse()

    def ReleaseAccess(self, request, context):
        update(request.lamport_timestamp)
        print(f"🔓 [Cliente {CLIENT_ID}] Recebeu ReleaseAccess de {request.client_id}")
        return pb.EmptyResponse()

# ---------------- COMUNICAÇÃO ----------------
def connect_peers():
    for port in PEER_PORTS:
        addr = f"localhost:{port}"
        print(f"🔌 [Cliente {CLIENT_ID}] Tentando conectar ao peer {addr}...")
        try:
            channel = grpc.insecure_channel(addr)
            stub = rpc.MutualExclusionServiceStub(channel)
            peers[port] = stub
        except Exception as e:
            print(f"❌ Falha ao conectar ao peer {addr}: {e}")
    print(f"✅ [Cliente {CLIENT_ID}] Conectado aos peers: {list(peers.keys())}")

def send_request_to_all(ts):
    global replies_received
    replies_received = set()
    for port, stub in peers.items():
        req = pb.AccessRequest(client_id=CLIENT_ID, lamport_timestamp=ts, request_number=0)
        print(f"📤 [Cliente {CLIENT_ID}] Enviando RequestAccess para {port}")
        try:
            stub.RequestAccess(req)
        except Exception as e:
            print(f"❌ [Cliente {CLIENT_ID}] Falha ao contactar peer {port}: {e}")

def send_reply(peer_port):
    ts = increment()
    stub = peers.get(peer_port)
    if not stub:
        try:
            channel = grpc.insecure_channel(f"localhost:{peer_port}")
            stub = rpc.MutualExclusionServiceStub(channel)
        except Exception as e:
            print(f"❌ Erro ao conectar ao peer {peer_port} para ACK: {e}")
            return
    msg = pb.ReplyMessage(from_client_id=CLIENT_ID, lamport_timestamp=ts)
    try:
        print(f"📤 [Cliente {CLIENT_ID}] Enviando ACK para {peer_port}")
        stub.SendReply(msg)
    except Exception as e:
        print(f"❌ Erro ao enviar ACK: {e}")

def send_deferred_replies():
    global deferred
    for peer in list(deferred):
        print(f"🕒 [Cliente {CLIENT_ID}] Enviando resposta adiada para {peer}")
        send_reply(peer)
    deferred.clear()

# ---------------- IMPRESSÃO ----------------
def send_to_printer(message):
    ts = increment()
    print(f"🖨️ [Cliente {CLIENT_ID}] Enviando mensagem ao servidor burro: {PRINTER_ADDR}")
    try:
        channel = grpc.insecure_channel(PRINTER_ADDR)
        stub = rpc.PrintingServiceStub(channel)
        req = pb.PrintRequest(
            client_id=CLIENT_ID,
            message_content=message,
            lamport_timestamp=ts,
            request_number=0
        )
        resp = stub.SendToPrinter(req)
        update(resp.lamport_timestamp)
        print(f"✅ [Cliente {CLIENT_ID}] Confirmação recebida: {resp.confirmation_message}")
    except Exception as e:
        print(f"❌ [Cliente {CLIENT_ID}] Erro ao imprimir: {e}")

# ---------------- CICLO PRINCIPAL ----------------
def critical_section():
    global in_critical
    in_critical = True
    print(f"🔒 [Cliente {CLIENT_ID}] Entrou na seção crítica.")
    send_to_printer(f"Documento do cliente {CLIENT_ID}")
    print(f"🔓 [Cliente {CLIENT_ID}] Saindo da seção crítica.")
    in_critical = False
    send_deferred_replies()

def request_access():
    global requesting, request_ts
    requesting = True
    request_ts = increment()
    print(f"🆘 [Cliente {CLIENT_ID}] Solicitando acesso (ts={request_ts})")
    send_request_to_all(request_ts)

    while len(replies_received) < len(peers):
        time.sleep(0.1)

    print(f"✅ [Cliente {CLIENT_ID}] Recebeu todos os ACKs, entrando na seção crítica...")
    critical_section()
    requesting = False

def auto_loop():
    while True:
        time.sleep(random.uniform(5, 12))
        request_access()

# ---------------- SERVIDOR ----------------
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    rpc.add_MutualExclusionServiceServicer_to_server(MutualExclusionServicer(), server)
    server.add_insecure_port(f"0.0.0.0:{MY_PORT}")
    server.start()
    print(f"🛰️ [Cliente {CLIENT_ID}] Servidor gRPC ativo na porta {MY_PORT}")
    return server

# ---------------- MAIN ----------------
if __name__ == "__main__":
    connect_peers()
    server = serve()
    threading.Thread(target=auto_loop, daemon=True).start()

    try:
        while True:
            time.sleep(2)
            with lamport_lock:
                print(f"[Status Cliente {CLIENT_ID}] Lamport={lamport}, Req={requesting}, Deferidos={deferred}")
    except KeyboardInterrupt:
        print("Encerrando cliente...")
