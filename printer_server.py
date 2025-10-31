#!/usr/bin/env python3
import time
import random
import argparse
from concurrent import futures
import grpc
import printing_pb2
import printing_pb2_grpc

class PrintingServiceServicer(printing_pb2_grpc.PrintingServiceServicer):
    def SendToPrinter(self, request, content):
        # Simula impressão (servidor burro)
        ts = request.lamport_timestamp
        client_id = request.client_id
        content = request.message_content
        print(f"[TS: {ts}] CLIENTE {client_id}: {content}")
        # simula delay de 2-3 segundos
        delay = random.uniform(2.0, 3.0)
        time.sleep(delay)
        confirmation = f"Impressão concluída para cliente {client_id} (delay {delay:.2f}s)"
        # Retorna resposta com timestamp local simples (poderia ser 0, mas devolvemos a hora)
        return printing_pb2.PrintResponse(success=True, confirmation_message=confirmation, lamport_timestamp=int(time.time()))

def serve(port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    printing_pb2_grpc.add_PrintingServiceServicer_to_server(PrintingServiceServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"Printer server (burro) rodando na porta {port} ...")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Encerrando servidor de impressão...")
        server.stop(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor de Impressão (burro)")
    parser.add_argument("--port", type=int, default=50051)
    args = parser.parse_args()
    serve(args.port)
