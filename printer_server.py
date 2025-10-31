# printer_server.py
import time
from concurrent import futures
import grpc
import distributed_printing_pb2 as pb
import distributed_printing_pb2_grpc as rpc

PORT = 50051

class PrintingServiceServicer(rpc.PrintingServiceServicer):
    def SendToPrinter(self, request, context):
        # Simula impressão
        ts = request.lamport_timestamp
        client_id = request.client_id
        content = request.message_content
        print(f"[TS: {ts}] CLIENTE {client_id}: {content}")
        # Delay de 2-3s
        time.sleep(2 + (time.time() % 1))
        resp = pb.PrintResponse(success=True, confirmation_message="Impressão concluída", lamport_timestamp=ts)
        return resp

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    rpc.add_PrintingServiceServicer_to_server(PrintingServiceServicer(), server)
    server.add_insecure_port(f'[::]:{PORT}')
    server.start()
    print(f"O servidor esta funcionando {PORT}")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
