# printing_client.py
import grpc
import time
import random
import argparse
import threading
from concurrent import futures
import distributed_printing_pb2 as pb
import distributed_printing_pb2_grpc as rpc

# ===========================
# Lamport clock (thread-safe)
# ===========================
lamport = 0
_lamport_lock = threading.Lock()

def increment():
    global lamport
    with _lamport_lock:
        lamport += 1
        return lamport

def update(received_ts):
    global lamport
    with _lamport_lock:
        lamport = max(lamport, received_ts) + 1
        return lamport

# =================================
# Servidor gRPC para cliente-cliente
# =================================
class MutualExclusionService(rpc.MutualExclusionServiceServicer):
    def __init__(self, client_obj):
        self.client = client_obj

    # Handler para RequestAccess (bloqueante): retorna AccessResponse quando concede
    def RequestAccess(self, request, context):
        # Atualiza relógio local ao receber
        update(request.lamport_timestamp)
        print(f"📨 [Cliente {self.client.id}] RequestAccess recebido de {request.client_id} (ts={request.lamport_timestamp})")
        # Implementação bloqueante: se eu estou pedindo e tenho prioridade, o servidor espera até liberar
        with self.client.lock:
            # Enquanto eu estiver requisitando e eu tiver prioridade sobre o requester, aguarda
            while self.client.requesting and (self.client.request_ts, self.client.id) < (request.lamport_timestamp, request.client_id):
                # aguardando até ser notificado por ReleaseAccess
                print(f"⏳ [Cliente {self.client.id}] Deferindo pedido de {request.client_id} (meu ts={self.client.request_ts})")
                self.client.wait_cv.wait()
            # conceder acesso (retorna imediatamente)
            # atualizar lamport antes de responder
            t = increment()
            print(f"✅ [Cliente {self.client.id}] Concedendo acesso a {request.client_id} (resposta ts={t})")
            return pb.AccessResponse(ack=True, lamport_timestamp=t)

    # Handler para ReleaseAccess: notifica blocked request handlers para reavaliar
    def ReleaseAccess(self, request, context):
        update(request.lamport_timestamp)
        print(f"🔔 [Cliente {self.client.id}] ReleaseAccess recebido de {request.client_id} (ts={request.lamport_timestamp})")
        with self.client.lock:
            # notificar possiveis handlers bloqueados
            self.client.wait_cv.notify_all()
        return pb.EmptyResponse()

class PrintingClient:
    def __init__(self, id, port, printer_addr, peers):
        """
        peers: lista de strings 'host:port' dos outros clientes (não inclui o próprio cliente).
        """
        self.id = id
        self.port = port
        self.printer_addr = printer_addr
        self.peers = peers[:]  # lista de "host:port"
        # Estado do algoritmo
        self.requesting = False
        self.request_ts = None
        self.lock = threading.Lock()
        self.wait_cv = threading.Condition(self.lock)  # usado para handlers bloqueados e wait/notify
        # para contagem de acks (quando chamamos RequestAccess em peers)
        # nós adotamos RequestAccess bloqueante: cada call retorna ack quando concedido
        # dessa forma, só precisamos contar quantas respostas recebemos (chamada retorna)
        self.running = True

    # ============ servidor cliente-cliente ============
    def start_server(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=20))
        rpc.add_MutualExclusionServiceServicer_to_server(MutualExclusionService(self), server)
        server.add_insecure_port(f"[::]:{self.port}")
        server.start()
        print(f"🛰️ [Cliente {self.id}] Servidor gRPC ativo na porta {self.port}")
        threading.Thread(target=server.wait_for_termination, daemon=True).start()

    # ============ Comunicação com peers usando RequestAccess (bloqueante) ============
    def send_request_to_peers(self, ts):
        """
        Envia RequestAccess para todos os peers. Como a versão que implementamos é bloqueante,
        cada stub.RequestAccess(msg) só retorna quando o peer concede (ou dá erro/timeout).
        """
        responses = 0
        for peer in self.peers:
            try:
                channel = grpc.insecure_channel(peer)
                stub = rpc.MutualExclusionServiceStub(channel)
                msg = pb.AccessRequest(
                    client_id=self.id,
                    lamport_timestamp=ts,
                    request_number=0
                )
                # Chamada bloqueante: retorna quando o peer concede
                # Colocamos timeout para não travar indefinidamente (p.ex.: 10s)
                resp = stub.RequestAccess(msg, timeout=10)
                # Atualiza local Lamport com o timestamp que recebemos em resp (se houver)
                try:
                    update(resp.lamport_timestamp)
                except Exception:
                    pass
                if getattr(resp, "ack", False):
                    responses += 1
                    print(f"📥 [Cliente {self.id}] Ack recebido de {peer}")
                else:
                    print(f"⚠️ [Cliente {self.id}] Peer {peer} respondeu sem ack (possível política).")
            except grpc.RpcError as e:
                print(f"❌ [Cliente {self.id}] Falha RequestAccess em {peer}: {e}")
        return responses

    def send_release_to_peers(self):
        """
        Notifica peers que eu liberei (ReleaseAccess). Isso faz com que os servidores dos peers
        notifiquem handlers bloqueados e reavaliem pedidos.
        """
        # incrementa lamport antes de enviar release
        ts = increment()
        for peer in self.peers:
            try:
                channel = grpc.insecure_channel(peer)
                stub = rpc.MutualExclusionServiceStub(channel)
                msg = pb.AccessRelease(
                    client_id=self.id,
                    lamport_timestamp=ts,
                    request_number=0
                )
                stub.ReleaseAccess(msg, timeout=5)
                # não esperamos resposta além do retorno do RPC
            except grpc.RpcError as e:
                print(f"❌ [Cliente {self.id}] Erro ao enviar Release para {peer}: {e}")

    # ============ Comunicação com o servidor burro ============
    def send_to_printer(self, message):
        try:
            # incrementa lamport pois está enviando mensagem externa (regra prática)
            ts = increment()
            channel = grpc.insecure_channel(self.printer_addr)
            stub = rpc.PrintingServiceStub(channel)
            msg = pb.PrintRequest(
                client_id=self.id,
                message_content=message,
                lamport_timestamp=ts,
                request_number=0
            )
            response = stub.SendToPrinter(msg, timeout=10)
            # atualiza com timestamp retornado
            try:
                update(response.lamport_timestamp)
            except Exception:
                pass
            print(f"🖨️ [Cliente {self.id}] Resposta da impressora: {response.confirmation_message}")
        except grpc.RpcError as e:
            print(f"❌ [Cliente {self.id}] Falha ao enviar para impressora: {e}")

    # ============ Seção Crítica ============
    def critical_section(self):
        print(f"✅ [Cliente {self.id}] Entrou na seção crítica.")
        # Exemplo de conteúdo da impressão: pode ser modificado para incluir request_ts, etc.
        self.send_to_printer(f"Documento do cliente {self.id} (ts={self.request_ts})")
        # simula trabalho na seção crítica
        time.sleep(1)
        print(f"🚪 [Cliente {self.id}] Saindo da seção crítica.")
        # libera e notifica peers
        with self.lock:
            self.requesting = False
            self.request_ts = None
            # notifica handlers locais que possam estar aguardando
            self.wait_cv.notify_all()
        # envia Release para peers
        self.send_release_to_peers()

    # ============ Loop Principal ============
    def run(self):
        print(f"🏃 [Cliente {self.id}] Iniciando loop principal. Peers: {self.peers}")
        while self.running:
            # espera aleatória entre tentativas de entrar na seção crítica
            time.sleep(random.randint(5, 10))
            # preparar pedido
            with self.lock:
                self.requesting = True
                ts = increment()
                self.request_ts = ts
                print(f"🆘 [Cliente {self.id}] Solicitando acesso (ts={ts})")
            # enviar RequestAccess para todos os peers (blocking calls)
            responses = self.send_request_to_peers(ts)
            # se conseguimos ack de todos os peers (respostas = len(peers)), entra na seção crítica
            if responses >= len(self.peers):
                # entrou na seção crítica
                self.critical_section()
            else:
                # caso algum peer não tenha respondido, liberar estado e tentar depois
                print(f"⚠️ [Cliente {self.id}] Não obteve ack de todos os peers ({responses}/{len(self.peers)}). Abortando pedido e tentando depois.")
                with self.lock:
                    self.requesting = False
                    self.request_ts = None
                    self.wait_cv.notify_all()
                # opcional: esperar um tempo antes de tentar novamente
                time.sleep(1)

    def stop(self):
        self.running = False

# ===========================
# Execução principal
# ===========================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, required=True, help="ID do cliente (inteiro único)")
    parser.add_argument("--server", type=str, required=True, help="Endereço do servidor de impressão (host:port)")
    parser.add_argument("--port", type=int, required=True, help="Porta em que este cliente serve (ex: 50052)")
    parser.add_argument("--clients", type=str, required=True,
                        help="Lista de peers separada por vírgula (ex: localhost:50053,localhost:50054). NÃO inclua este próprio cliente.")
    args = parser.parse_args()

    peers = [p.strip() for p in args.clients.split(",") if p.strip()]
    client = PrintingClient(args.id, args.port, args.server, peers)
    client.start_server()
    try:
        client.run()
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário. Encerrando...")
        client.stop()
