import socket
import threading
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend

class CryptoServer:
    def __init__(self, host='127.0.0.1', port=8080):
        self.host = host
        self.port = port
        self.private_key = None
        self.public_key = None
        self.client_public_keys = {}
        
    def generate_keypair(self):
        """Generate RSA public-private key pair"""
        print("Creating RSA keypair")
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
        print("RSA keypair created")
        
    def start(self):
        """Start the server"""
        print("Starting server...")
        self.generate_keypair()
        
        print("Creating server socket")
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        
        print("Awaiting connections...")
        
        while True:
            client_socket, address = server_socket.accept()
            print("Connection requested.")
            client_thread = threading.Thread(
                target=self.handle_client, 
                args=(client_socket, address)
            )
            client_thread.start()
    
    def handle_client(self, client_socket, address):
        """Handle individual client connection"""
        data_socket = None
        client_id = f"{address[0]}:{address[1]}"
        
        try:
            while True:
                # Receive command from client
                command = client_socket.recv(1024).decode('utf-8').strip()
                
                if not command:
                    break
                    
                if command == "connect":
                    # Respond with data port
                    print("Creating data socket")
                    data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    data_socket.bind((self.host, 0))  # Bind to any available port
                    data_socket.listen(1)
                    data_port = data_socket.getsockname()[1]
                    
                    # Send data port to client
                    client_socket.send(str(data_port).encode('utf-8'))
                    
                    # Accept data connection
                    data_conn, _ = data_socket.accept()
                    
                elif command == "tunnel":
                    print("Tunnel requested.")
                    # Receive client's public key
                    client_public_key_pem = data_conn.recv(4096)
                    client_public_key = serialization.load_pem_public_key(
                        client_public_key_pem,
                        backend=default_backend()
                    )
                    self.client_public_keys[client_id] = client_public_key
                    
                    # Send server's public key
                    print("Sending public key")
                    server_public_key_pem = self.public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                    data_conn.send(server_public_key_pem)
                    
                elif command == "post":
                    print("Post requested.")
                    # Receive encrypted message
                    encrypted_message = data_conn.recv(4096)
                    print(f"Received encrypted message: {encrypted_message.hex()}")
                    
                    # Decrypt message using server's private key
                    decrypted_message = self.private_key.decrypt(
                        encrypted_message,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(),
                            label=None
                        )
                    ).decode('utf-8')
                    print(f"Decrypted message: {decrypted_message}")
                    
                    # Compute SHA256 hash
                    print("Computing hash")
                    message_hash = hashlib.sha256(decrypted_message.encode('utf-8')).digest()
                    print(f"Responding with hash: {message_hash.hex()}")
                    
                    # Encrypt hash with client's public key
                    client_public_key = self.client_public_keys[client_id]
                    encrypted_hash = client_public_key.encrypt(
                        message_hash,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(),
                            label=None
                        )
                    )
                    
                    # Send encrypted hash back to client
                    data_conn.send(encrypted_hash)
                    
                elif command == "exit":
                    break
                    
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client_socket.close()
            if data_socket:
                data_socket.close()

if __name__ == "__main__":
    server = CryptoServer()
    server.start()
