import socket
import sys
import threading
import time
from datetime import datetime

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Include milliseconds

class BackendProcess:
    def __init__(self, port):
        self.port = port
        self.host = 'localhost'
        self.running = False
        self.is_started = False
        self.event_timer = None
        self.last_client_addr = None
        
    def start_server(self):
        print("[{}] Backend starting on port {}".format(get_timestamp(), self.port))
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen()
            
            print("[{}] Listening for connections...".format(get_timestamp()))
            
            while True:
                try:
                    client_socket, addr = server_socket.accept()
                    self.last_client_addr = addr  # Store the client address
                    with client_socket:
                        message = client_socket.recv(1024).decode()
                        self.handle_message(message, addr)
                except KeyboardInterrupt:
                    print("\n[{}] Server shutting down...".format(get_timestamp()))
                    break
                except Exception as e:
                    print("[{}] Error: {}".format(get_timestamp(), str(e)))
    
    def send_ready_message(self):
        timestamp = get_timestamp()
        print(f"[{timestamp}] Event timer completed. Sending READY message to control app")
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)  # Increase timeout for reliability
                s.connect((self.last_client_addr[0], self.last_client_addr[1]))
                s.sendall("READY".encode())
                print(f"[{timestamp}] READY message sent successfully")
        except Exception as e:
            print(f"[{timestamp}] Failed to send READY message: {str(e)}")
            # Try to resend after 1 second if failed
            print(f"[{timestamp}] Will retry sending READY message in 1 second")
            self.event_timer = threading.Timer(1.0, self.send_ready_message)
            self.event_timer.start()
            return
        
        self.event_timer = None
    
    def handle_message(self, message, addr):
        timestamp = get_timestamp()
        print(f"[{timestamp}] Message from {addr}: {message}")
        print(f"[{timestamp}] Current state: {'STARTED' if self.is_started else 'NOT STARTED'}")
        
        if message.startswith("CONNECTION_FAIL:"):
            # Reset state to NOT STARTED when connection failure is detected
            failed_backends = message.split(":")[1].split(",")
            print(f"[{timestamp}] Connection failure detected from backends: {failed_backends}")
            print(f"[{timestamp}] Resetting state to NOT STARTED")
            self.is_started = False
            # Cancel any pending event timer
            if self.event_timer and self.event_timer.is_alive():
                self.event_timer.cancel()
                self.event_timer = None
            return
            
        if message == "ERROR":
            # Reset state to NOT STARTED when error message is received
            print(f"[{timestamp}] Error message received, resetting state to NOT STARTED")
            self.is_started = False
            # Cancel any pending event timer
            if self.event_timer and self.event_timer.is_alive():
                self.event_timer.cancel()
                self.event_timer = None
            return
            
        if message == "START":
            if not self.is_started:
                self.is_started = True
                print(f"[{timestamp}] State changed to: STARTED")
            else:
                print(f"[{timestamp}] Already in STARTED state")
        elif message == "END":
            if self.is_started:
                self.is_started = False
                print(f"[{timestamp}] State changed to: NOT STARTED")
                # Cancel any pending event timer
                if self.event_timer and self.event_timer.is_alive():
                    self.event_timer.cancel()
                    self.event_timer = None
            else:
                print(f"[{timestamp}] Already in NOT STARTED state")
        elif message == "EVENT":
            if self.is_started:
                print(f"[{timestamp}] Event received while STARTED")
                # Cancel existing timer if there is one
                if self.event_timer and self.event_timer.is_alive():
                    self.event_timer.cancel()
                
                # Start new 30-second timer
                print(f"[{timestamp}] Starting 30-second event timer")
                self.event_timer = threading.Timer(30.0, self.send_ready_message)
                self.event_timer.start()
                
                # Send acknowledgment of event receipt
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(0.5)
                        s.connect((addr[0], addr[1]))
                        s.sendall("EVENT_RECEIVED".encode())
                        print(f"[{timestamp}] Event receipt acknowledgment sent")
                except Exception as e:
                    print(f"[{timestamp}] Failed to send event acknowledgment: {str(e)}")
            else:
                print(f"[{timestamp}] Event ignored - not in STARTED state")

def main():
    if len(sys.argv) != 2:
        print("Usage: python backend_process.py <port>")
        print("Example: python backend_process.py 12345")
        sys.exit(1)
    
    try:
        port = int(sys.argv[1])
        if port < 1024 or port > 65535:
            raise ValueError("Port must be between 1024 and 65535")
    except ValueError as e:
        print("Error: {}".format(str(e)))
        sys.exit(1)
    
    backend = BackendProcess(port)
    try:
        backend.start_server()
    except KeyboardInterrupt:
        print("\nBackend process terminated by user")

if __name__ == "__main__":
    main() 