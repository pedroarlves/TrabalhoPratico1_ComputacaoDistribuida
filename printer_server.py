# printer_server.py
import time
import grpc
from concurrent import futures
import argparse
import distributed_printing_pb2 as pb
import distributed_printing_pb2_grpc as rpc

class PrintingService(rpc.PrintingServiceServicer):
    def SendToPrinter(self, request, context):
        print("\n🖨️  RECEBIDO PEDIDO DE IMPRESSÃO")
        print(f"  Cliente: {request.client_id}")
        print(f"  Mensagem: {request.message_content}")
        print(f"  Timestamp Lamport (do cliente): {request.lamport_timestamp}")
        # Simula tempo de impressão
        time.sleep(2)
        print(f"✅ IMPRESSO: [TS: {request.lamport_timestamp}] CLIENTE {request.client_id}: {request.message_content}\n")
        return pb.PrintResponse(
            success=True,
            confirmation_message="Impressão concluída",
            lamport_timestamp=request.lamport_timestamp
        )

def serve(port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    rpc.add_PrintingServiceServicer_to_server(PrintingService(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"🖨️  Servidor de impressão burro rodando na porta {port}")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\nEncerrando servidor...")
        server.stop(0)
        print("Servidor encerrado com sucesso.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=50051, help="Porta do servidor de impressão")
    args = parser.parse_args()
    serve(args.port)
