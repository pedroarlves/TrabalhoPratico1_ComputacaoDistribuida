import time
from concurrent import futures
import grpc
import distributed_printing_pb2 as pb
import distributed_printing_pb2_grpc as rpc

PORT = 50051

class PrintingServiceServicer(rpc.PrintingServiceServicer):
    def SendToPrinter(self, request, context):
        print("\n=======================")
        print("🖨️  RECEBIDO PEDIDO DE IMPRESSÃO")
        print(f"Cliente: {request.client_id}")
        print(f"Mensagem: {request.message_content}")
        print(f"Timestamp Lamport: {request.lamport_timestamp}")
        print("=======================\n")

        # Simula o tempo de impressão
        time.sleep(2 + (time.time() % 1))
        response_msg = f"[TS: {request.lamport_timestamp}] CLIENTE {request.client_id}: {request.message_content}"

        print(f"✅ IMPRESSO: {response_msg}")
        print("📤 Enviando confirmação de impressão...\n")

        return pb.PrintResponse(
            success=True,
            confirmation_message="Impressão concluída com sucesso.",
            lamport_timestamp=request.lamport_timestamp
        )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    rpc.add_PrintingServiceServicer_to_server(PrintingServiceServicer(), server)
    server.add_insecure_port("0.0.0.0:50051")  # Aceita conexões externas
    server.start()
    print(f"🖨️  Servidor de impressão burro (modo DEBUG) rodando na porta {PORT}")
    print("=============================================")
    print("Aguardando requisições de impressão...\n")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
