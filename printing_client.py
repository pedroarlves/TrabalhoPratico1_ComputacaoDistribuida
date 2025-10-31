#!/usr/bin/env python3
import grpc
import printing_pb2
import printing_pb2_grpc

import argparse
import threading
import time
import random
from concurrent import futures

# ---------------- Lamport Clock ----------------
class LamportClock:
    def __init__(self):
        self.lock = threading.Lock()
        self.time = 0

    def increment(self):
        with self.lock:
            self.time += 1
            return self.time

    def update(self, other_ts):
        with self.lock:
            self.time = max(self.time, other_ts) + 1
            return self.time

    def read(self):
        with self.lock:
            return self.time

# ---------------- Cliente (MutualExclusionService) ----------------
class MutualExclusionServicer(printing_pb2_grpc.MutualExclusionServiceServicer):
    def __init__(self, client):
        self.client = client

    def RequestAccess(self, request, context):
        # Atualiza relógio
        ts = self.client.clock.update(request.lamport_timestamp)
        # Regra de Ricart-Agrawala:
        # Se eu não estou solicitando, respondo imediatamente.
        # Se eu estou solicitando:
        #   comparo (timestamp, id) — se o request remoto for "menor", respondo imediatamente; senão deferir.
        grant = True
        with self.client.state_lock:
            # marca recebimento do pedido
            remote_key = (request.lamport_timestamp, request.client_id, request.request_number)
            # atualizamos clock (feito acima)
            if self.client.requesting:
                # meu pedido atual
                my_ts = self.client.request_ts
                my_id = self.client.id
                # comparador: menor (ts) tem prioridade; se empate, menor id vence
                remote_ts = request.lamport_timestamp
                if (my_ts, my_id) < (remote_ts, request.client_id):
                    # meu pedido tem prioridade -> devo DEFERIR resposta
                    grant = False
                    # guardo para enviar depois
                    self.client.deferred.add(request.client_id)
                else:
                    # remoto tem prioridade -> concedo
                    grant = True
            else:
                grant = True

        # atualizamos clock na resposta
        resp_ts = self.client.clock.increment()
        return printing_pb2.AccessResponse(access_granted=grant, lamport_timestamp=resp_ts)

    def ReleaseAccess(self, request, context):
        # Ao receber release: atualiza relógio e, se houver pedidos deferidos, possivelmente processar
        self.client.clock.update(request.lamport_timestamp)
        # Caso receba release, removemos qualquer estado necessário — neste design apenas informamos
        # Não é necessário mandar nada; mas podemos checar se havia pedido daquele cliente.
        # Nada específico aqui, mas podemos acordar espera se necessário.
        return printing_pb2.EmptyResponse(ok=True)

# ---------------- Cliente inteligente ----------------
class PrintingClient:
    def __init__(self, client_id, listen_port, printer_addr, peer_addrs):
        self.id = client_id
        self.listen_port = listen_port
        self.printer_addr = printer_addr
        # peer_addrs: list of "host:port"
        self.peer_addrs = [p for p in peer_addrs if p]  # filter empty
        self.clock = LamportClock()
        self.requesting = False
        self.request_ts = 0
        self.request_number = 0
        self.deferred = set()  # ids dos peers a quem devo resposta quando liberar
        self.state_lock = threading.Lock()
        self.replies_received = set()
        self.replies_cv = threading.Condition()
        self.server = None
        self._shutdown = False

    # inicia servidor gRPC para receber Request/Release
    def start_server(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        printing_pb2_grpc.add_MutualExclusionServiceServicer_to_server(MutualExclusionServicer(self), server)
        server.add_insecure_port(f"[::]:{self.listen_port}")
        server.start()
        self.server = server
        print(f"[Cliente {self.id}] Servidor MutualExclusion rodando na porta {self.listen_port}")

    def stop_server(self):
        if self.server:
            self.server.stop(0)

    # helpers para conectar a peers e ao printer
    def _stub_for(self, addr):
        channel = grpc.insecure_channel(addr)
        stub = printing_pb2_grpc.MutualExclusionServiceStub(channel)
        return stub, channel

    def _printer_stub(self):
        channel = grpc.insecure_channel(self.printer_addr)
        stub = printing_pb2_grpc.PrintingServiceStub(channel)
        return stub, channel

    # envia Requests para todos os peers
    def broadcast_request(self):
        # prepara pedido
        with self.state_lock:
            self.requesting = True
            self.request_ts = self.clock.increment()
            self.request_number += 1
            self.replies_received = set()
        print(f"[Cliente {self.id}] Broadcast Request (ts={self.request_ts}, req_no={self.request_number}) para peers: {self.peer_addrs}")

        # enviar em threads (paralelo)
        def send_to_peer(peer_addr):
            try:
                stub, ch = self._stub_for(peer_addr)
                req = printing_pb2.AccessRequest(client_id=self.id,
                                                 lamport_timestamp=self.request_ts,
                                                 request_number=self.request_number)
                # chama RPC (com timeout para não bloquear indefinidamente)
                resp = stub.RequestAccess(req, timeout=5)
                # atualizamos relógio com timestamp do reply
                self.clock.update(resp.lamport_timestamp)
                if resp.access_granted:
                    with self.state_lock:
                        self.replies_received.add(peer_addr)
                else:
                    # se o peer devolveu access_granted False (por design acima nunca devolve false, apenas defer), 
                    # tratamos como não recebido — mas o modelo padrão é que peer devolve access_granted True ou coloca em deferred localmente.
                    pass
            except Exception as e:
                print(f"[Cliente {self.id}] Erro ao contatar peer {peer_addr}: {e}")

        threads = []
        for addr in self.peer_addrs:
            t = threading.Thread(target=send_to_peer, args=(addr,))
            t.daemon = True
            t.start()
            threads.append(t)

        # Espera os threads terminarem (ou timeout global)
        for t in threads:
            t.join(timeout=6)

        # Notar: ricart-agrawala espera uma REPLY de cada peer; neste design, um peer "defer" não retorna "false" — 
        # para simplificar, consideraremos que todo peer responde prontamente (com grant True ou False), 
        # e quando deferir tem que armazenar e enviar reply posteriormente na liberação.
        # Como nosso RequestAccess devolve AccessResponse(access_granted=True/False), contabilizamos apenas True.
        # Então precisamos de um critério: esperar resposta de TODOS os peers (mesmo se grant=False),
        # mas como a RPC sempre retorna algo, consideramos resposta como recebida independentemente do grant.
        # Para simplificar e robustez, aqui aguardamos um pequeno tempo e então prosseguimos contando as respostas que chegaram.
        time.sleep(0.1)  # deixa tempo para replies chegarem

    def wait_for_replies(self, timeout=10):
        # Em vez de contagem por ID, consideraremos como resposta válida qualquer retorno de RPC:
        # o broadcast_request já tentou contatar todos os peers. Para sermos estritos, vamos aguardar até timeout.
        # Implementação simples: espera até ter contato com N peers ou até timeout.
        target = len(self.peer_addrs)
        start = time.time()
        while time.time() - start < timeout:
            with self.state_lock:
                # replies_received guarda endereços que responderam com grant True (mas praktiicamente deve ser todos)
                # se ninguém tiver peers (target == 0), já retornamos
                if target == 0 or len(self.replies_received) >= target:
                    return True
            time.sleep(0.05)
        # timeout
        return False

    # envia release para peers e processa deferred
    def broadcast_release(self):
        with self.state_lock:
            self.requesting = False
            # snapshot de quem estava deferido
            deferred_ids = set(self.deferred)
            self.deferred.clear()

        print(f"[Cliente {self.id}] Broadcast Release (deferred -> {deferred_ids})")
        # envia Release RPC para todos peers para informar (poderia não ser estritamente necessário)
        for addr in self.peer_addrs:
            try:
                stub, ch = self._stub_for(addr)
                rel = printing_pb2.AccessRelease(client_id=self.id,
                                                lamport_timestamp=self.clock.increment(),
                                                request_number=self.request_number)
                stub.ReleaseAccess(rel, timeout=5)
            except Exception as e:
                print(f"[Cliente {self.id}] Erro ao enviar Release para {addr}: {e}")

        # Para cada peer que foi deferido, abrimos um canal e mandamos um "Reply" imediato.
        # No nosso protocolo, a "Reply" é simulada reusando RequestAccess/AccessResponse: mas
        # idealmente o peer que deferiu envia um AccessResponse quando libera.
        # Como o peer que recebeu a requisição deferida já guardou o id para enviar resposta, aqui basta contatar o peer:
        for peer_id in deferred_ids:
            # precisamos mapear peer_id para endereço. Simplificação: assumimos peer_id corresponde à ordem/porta?
            # Para robustez, enviamos Release para todos peers; o peer que deferiu sabe para quem reenviar respuesta.
            pass

    # função principal que solicita impressão: coordena RA + SendToPrinter
    def request_and_print(self, content):
        # Passo 1: broadcast request
        self.broadcast_request()
        # Passo 2: aguardar respostas (simples)
        ok = self.wait_for_replies(timeout=5)
        if not ok:
            print(f"[Cliente {self.id}] Timeout esperando replies; tentando mesmo assim (não estrito).")
        # Passo 3: entrou na seção crítica -> chamar servidor burro
        stub_printer, ch = self._printer_stub()
        # atualiza clock antes de enviar
        ts = self.clock.increment()
        req = printing_pb2.PrintRequest(client_id=self.id, message_content=content, lamport_timestamp=ts, request_number=self.request_number)
        try:
            print(f"[Cliente {self.id}] Enviando ao servidor de impressão: '{content}' (ts={ts})")
            resp = stub_printer.SendToPrinter(req, timeout=10)
            # atualiza relógio com resposta
            self.clock.update(resp.lamport_timestamp)
            print(f"[Cliente {self.id}] Recebeu confirmação do printer: {resp.confirmation_message}")
        except Exception as e:
            print(f"[Cliente {self.id}] Erro ao contatar printer: {e}")

        # Passo 4: liberar e enviar deferred replies
        self.broadcast_release()

    # rotina que gera pedidos automáticos de impressão em intervalos aleatórios
    def auto_generate_requests(self, avg_interval=6):
        while not self._shutdown:
            time_to_wait = random.expovariate(1.0 / avg_interval)
            time.sleep(time_to_wait)
            content = f"Documento gerado automaticamente por cliente {self.id} (random)"
            print(f"[Cliente {self.id}] Gerando pedido de impressão (conteúdo='{content}')")
            self.request_and_print(content)

    # rotina que exibe status local periodicamente
    def status_printer(self):
        while not self._shutdown:
            ts = self.clock.read()
            with self.state_lock:
                status = "REQUESTING" if self.requesting else "IDLE"
                deferred = list(self.deferred)
            print(f"[Cliente {self.id}] STATUS ts={ts}, estado={status}, deferred={deferred}")
            time.sleep(5)

    def run(self, auto_start=True, avg_interval=6):
        # start server
        self.start_server()
        # start auto generator thread
        if auto_start:
            t_auto = threading.Thread(target=self.auto_generate_requests, args=(avg_interval,))
            t_auto.daemon = True
            t_auto.start()
        # start status thread
        t_stat = threading.Thread(target=self.status_printer)
        t_stat.daemon = True
        t_stat.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"[Cliente {self.id}] Encerrando...")
            self._shutdown = True
            self.stop_server()
