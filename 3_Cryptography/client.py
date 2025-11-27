import socket
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend

class CryptoClient:
    def __init__(self, server_host='127.0.0.1', server_port=8080):
        self.server_host = server_host
        self.server_port = server_port
        self.private_key = None
        self.public_key = None
        self.server_public_key = None
        self.command_socket = None
        self.data_socket = None
        
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
        
    def connect_to_server(self):
        """Connect to the server and establish data connection"""
        print("Starting client...")
        self.generate_keypair()
        
        print("Creating client socket")
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        print("Connecting to server")
        self.command_socket.connect((self.server_host, self.server_port))
        
        # Send connect command
        self.command_socket.send("connect".encode('utf-8'))
        
        # Receive data port
        data_port = int(self.command_socket.recv(1024).decode('utf-8'))
        
        print("Creating data socket")
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_socket.connect((self.server_host, data_port))
        
    def establish_tunnel(self):
        """Exchange public keys with server"""
        print("Requesting tunnel")
        self.command_socket.send("tunnel".encode('utf-8'))
        
        # Send client's public key
        client_public_key_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self.data_socket.send(client_public_key_pem)
        
        # Receive server's public key
        server_public_key_pem = self.data_socket.recv(4096)
        self.server_public_key = serialization.load_pem_public_key(
            server_public_key_pem,
            backend=default_backend()
        )
        print("Server public key received")
        print("Tunnel established")
        
    def send_message(self, message):
        """Encrypt and send message to server"""
        print(f"Encrypting message: {message}")
        
        # Encrypt message with server's public key
        encrypted_message = self.server_public_key.encrypt(
            message.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        print(f"Sending encrypted message: {encrypted_message.hex()}")
        
        # Send post command
        self.command_socket.send("post".encode('utf-8'))
        
        # Send encrypted message
        self.data_socket.send(encrypted_message)
        
        # Receive encrypted hash from server
        print("Received hash")
        encrypted_hash = self.data_socket.recv(4096)
        
        # Decrypt hash using client's private key
        decrypted_hash = self.private_key.decrypt(
            encrypted_hash,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Compute local hash
        print("Computing hash")
        local_hash = hashlib.sha256(message.encode('utf-8')).digest()
        
        # Compare hashes
        if local_hash == decrypted_hash:
            print("Secure")
        else:
            print("Compromised")
            
    def close(self):
        """Close connections"""
        if self.command_socket:
            self.command_socket.send("exit".encode('utf-8'))
            self.command_socket.close()
        if self.data_socket:
            self.data_socket.close()

if __name__ == "__main__":
    client = CryptoClient()
    
    try:
        # Connect to server
        client.connect_to_server()
        
        # Establish secure tunnel
        client.establish_tunnel()
        
        # Send message
        client.send_message("Hello")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()
