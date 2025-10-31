import grpc
import time
import random
import argparse
import threading
from concurrent import futures
import distributed_printing_pb2 as pb
import distributed_printing_pb2_grpc as rpc

# ===========================
# Relógio de Lamport
# ===========================
lamport = 0
def increment():
    global lamport
    lamport += 1
    return lamport

def update(received_ts):
    global lamport
    lamport = max(lamport, received_ts) + 1

# ===========================
# Classe Ricart-Agrawala
# ===========================
class MutualExclusionService(rpc.MutualExclusionServiceServicer):
    def __init__(self, client):
        self.client = client

    def RequestAccess(self, request, context):
        update(request.lamport_timestamp)
        self.client.handle_request(request)
        return pb.AccessResponse(access_granted=True, lamport_timestamp=lamport)

    def ReleaseAccess(self, request, context):
        update(request.lamport_timestamp)
        self.client.handle_release(request)
        return pb.AccessResponse(access_granted=True, lamport_timestamp=lamport)

class PrintingClient:
    def __init__(self, id, port, printer_addr, peers):
        self.id = id
        self.port = port
        self.printer_addr = printer_addr
        self.peers = peers
        self.requesting = False
        self.request_ts = None
        self.deferred = set()
        self.replies = set()
        self.lock = threading.Lock()

    # ============ Comunicação Cliente-Cliente ============
    def start_server(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        rpc.add_MutualExclusionServiceServicer_to_server(MutualExclusionService(self), server)
        server.add_insecure_port(f"[::]:{self.port}")
        server.start()
        print(f"🛰️ [Cliente {self.id}] Servidor gRPC ativo na porta {self.port}")
        threading.Thread(target=server.wait_for_termination, daemon=True).start()

    def send_request_to_peers(self):
        for peer in self.peers:
            try:
                channel = grpc.insecure_channel(peer)
                stub = rpc.MutualExclusionServiceStub(channel)
                msg = pb.AccessRequest(
                    client_id=self.id,
                    lamport_timestamp=lamport,
                    request_number=0
                )
                stub.RequestAccess(msg)
                print(f"📤 [Cliente {self.id}] RequestAccess enviado para {peer}")
            except Exception as e:
                print(f"❌ [Cliente {self.id}] Falha ao contactar {peer}: {e}")

    def send_release_to_peers(self):
        for peer in self.peers:
            try:
                channel = grpc.insecure_channel(peer)
                stub = rpc.MutualExclusionServiceStub(channel)
                msg = pb.AccessRelease(
                    client_id=self.id,
                    lamport_timestamp=lamport,
                    request_number=0
                )
                stub.ReleaseAccess(msg)
            except Exception as e:
                print(f"❌ [Cliente {self.id}] Erro ao enviar Release: {e}")

    # ============ Algoritmo Ricart-Agrawala ============
    def handle_request(self, request):
        with self.lock:
            if (not self.requesting or
                (request.lamport_timestamp, request.client_id) <
                (self.request_ts, self.id)):
                self.send_reply(request.client_id)
            else:
                self.deferred.add(request.client_id)

    def handle_release(self, request):
        with self.lock:
            for cid in list(self.deferred):
                self.send_reply(cid)
                self.deferred.remove(cid)

    def send_reply(self, client_id):
        peer_addr = [p for p in self.peers if p.endswith(str(50050 + client_id + 1))]
        if not peer_addr:
            return
        try:
            channel = grpc.insecure_channel(peer_addr[0])
            stub = rpc.MutualExclusionServiceStub(channel)
            msg = pb.AccessResponse(access_granted=True, lamport_timestamp=lamport)
            stub.RequestAccess(msg)
        except Exception as e:
            print(f"❌ [Cliente {self.id}] Erro ao enviar ACK para {client_id}: {e}")

    # ============ Comunicação com o Servidor Burro ============
    def send_to_printer(self, message):
        try:
            channel = grpc.insecure_channel(self.printer_addr)
            stub = rpc.PrintingServiceStub(channel)
            msg = pb.PrintRequest(
                client_id=self.id,
                message_content=message,
                lamport_timestamp=lamport,
                request_number=0
            )
            response = stub.SendToPrinter(msg)
            print(f"🖨️ [Cliente {self.id}] Resposta da impressora: {response.confirmation_message}")
        except Exception as e:
            print(f"❌ [Cliente {self.id}] Falha ao enviar para impressora: {e}")

    # ============ Seção Crítica ============
    def critical_section(self):
        print(f"✅ [Cliente {self.id}] Entrou na seção crítica.")
        self.send_to_printer(f"Documento do cliente {self.id}")
        time.sleep(1)
        print(f"🚪 [Cliente {self.id}] Saindo da seção crítica.")
        self.send_release_to_peers()

    # ============ Loop Principal ============
    def run(self):
        while True:
            time.sleep(random.randint(5, 10))
            self.requesting = True
            ts = increment()
            self.request_ts = ts
            print(f"🆘 [Cliente {self.id}] Solicitando acesso (ts={ts})")
            self.send_request_to_peers()
            time.sleep(3)
            self.critical_section()
            self.requesting = False

# ===========================
# Execução Principal
# ===========================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, required=True)
    parser.add_argument("--server", type=str, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--clients", type=str, required=True)
    args = parser.parse_args()

    peers = args.clients.split(",")
    client = PrintingClient(args.id, args.port, args.server, peers)
    client.start_server()
    client.run()
    #def send_reply(peer_port, stub=None):
    #    if stub is None: