#!/usr/bin/env python3
import socket
import sys
import os
import re


class FTPClient:
    def __init__(self, server_name):
        self.server_name = server_name
        self.server_port = 21
        self.control_socket = None
        self.username = None
        self.password = None

    def connect(self):
        """Establish control connection to FTP server"""
        try:
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.connect((self.server_name, self.server_port))

            # Read welcome message
            response = self.receive_response()
            print(response)

            if not response.startswith('220'):
                print("Failed to connect to server")
                return False
            return True

        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def receive_response(self):
        """Receive and return response from server"""
        try:
            response = ""
            while True:
                data = self.control_socket.recv(1024).decode('ascii')
                response += data
                # Check if we have complete response (ends with \r\n)
                if response.endswith('\r\n'):
                    break
            return response.strip()
        except Exception as e:
            print(f"Error receiving response: {e}")
            return ""

    def send_command(self, command):
        """Send command to server and return response"""
        try:
            # Add \r\n to command if not present
            if not command.endswith('\r\n'):
                command += '\r\n'

            self.control_socket.send(command.encode('ascii'))
            return self.receive_response()
        except Exception as e:
            print(f"Error sending command: {e}")
            return ""

    def login(self):
        """Handle user authentication"""
        # Get username
        self.username = input("Username: ")
        response = self.send_command(f"USER {self.username}")
        print(response)

        if response.startswith('331'):  # User name okay, need password
            self.password = input("Password: ")
            response = self.send_command(f"PASS {self.password}")
            print(response)

            if response.startswith('230'):  # User logged in
                print("Login successful")
                return True
            else:
                print("Login failed")
                return False
        else:
            print("Username not accepted")
            return False

    def parse_pasv_response(self, response):
        """Parse PASV response to get IP and port for data connection"""
        # PASV response format: 227 Entering Passive Mode (h1,h2,h3,h4,p1,p2)
        # IP = h1.h2.h3.h4, Port = p1*256 + p2

        match = re.search(r'\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)', response)
        if match:
            h1, h2, h3, h4, p1, p2 = map(int, match.groups())
            ip = f"{h1}.{h2}.{h3}.{h4}"
            port = p1 * 256 + p2
            return ip, port
        return None, None

    def create_data_connection(self):
        """Create data connection using PASV mode"""
        # Send PASV command
        response = self.send_command("PASV")
        print(response)

        if not response.startswith('227'):
            print("Failed to enter passive mode")
            return None

        # Parse IP and port from response
        ip, port = self.parse_pasv_response(response)
        if not ip or not port:
            print("Failed to parse passive mode response")
            return None

        # Create data socket and connect
        try:
            data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            data_socket.connect((ip, port))
            return data_socket
        except Exception as e:
            print(f"Failed to create data connection: {e}")
            return None

    def cmd_ls(self):
        """List files in current directory"""
        # Create data connection first
        data_socket = self.create_data_connection()
        if not data_socket:
            return

        # Send LIST command
        response = self.send_command("LIST")
        print(response)

        if response.startswith('150') or response.startswith('125'):
            # Receive file list from data connection
            file_list = ""
            while True:
                try:
                    data = data_socket.recv(1024).decode('ascii')
                    if not data:
                        break
                    file_list += data
                except:
                    break

            data_socket.close()
            print(file_list)

            # Get completion response
            final_response = self.receive_response()
            print(final_response)
        else:
            data_socket.close()
            print("Failed to list directory")

    def cmd_cd(self, directory):
        """Change working directory"""
        response = self.send_command(f"CWD {directory}")
        print(response)

        if response.startswith('250'):
            print(f"Directory changed to {directory}")
        else:
            print("Failed to change directory")

    def cmd_get(self, filename):
        """Download file from server"""
        # Create data connection first
        data_socket = self.create_data_connection()
        if not data_socket:
            return

        # Send RETR command
        response = self.send_command(f"RETR {filename}")
        print(response)

        if response.startswith('150') or response.startswith('125'):
            # Receive file data
            total_bytes = 0
            try:
                with open(filename, 'wb') as f:
                    while True:
                        data = data_socket.recv(1024)
                        if not data:
                            break
                        f.write(data)
                        total_bytes += len(data)

                data_socket.close()
                print(f"Successfully downloaded {filename} ({total_bytes} bytes)")

                # Get completion response
                final_response = self.receive_response()
                print(final_response)

            except Exception as e:
                print(f"Error downloading file: {e}")
                data_socket.close()
        else:
            data_socket.close()
            print("Failed to download file")

    def cmd_put(self, filename):
        """Upload file to server"""
        # Check if local file exists
        if not os.path.exists(filename):
            print(f"Local file {filename} not found")
            return

        # Create data connection first
        data_socket = self.create_data_connection()
        if not data_socket:
            return

        # Send STOR command
        response = self.send_command(f"STOR {filename}")
        print(response)

        if response.startswith('150') or response.startswith('125'):
            # Send file data
            total_bytes = 0
            try:
                with open(filename, 'rb') as f:
                    while True:
                        data = f.read(1024)
                        if not data:
                            break
                        data_socket.send(data)
                        total_bytes += len(data)

                data_socket.close()
                print(f"Successfully uploaded {filename} ({total_bytes} bytes)")

                # Get completion response
                final_response = self.receive_response()
                print(final_response)

            except Exception as e:
                print(f"Error uploading file: {e}")
                data_socket.close()
        else:
            data_socket.close()
            print("Failed to upload file")

    def cmd_delete(self, filename):
        """Delete file on server"""
        response = self.send_command(f"DELE {filename}")
        print(response)

        if response.startswith('250'):
            print(f"Successfully deleted {filename}")
        else:
            print("Failed to delete file")

    def cmd_quit(self):
        """Quit FTP session"""
        response = self.send_command("QUIT")
        print(response)
        self.control_socket.close()
        print("Goodbye!")
        return True

    def run_interactive(self):
        """Main interactive loop"""
        print(f"Connected to {self.server_name}")

        while True:
            try:
                command = input("myftp> ").strip()
                if not command:
                    continue

                parts = command.split()
                cmd = parts[0].lower()

                if cmd == 'ls':
                    self.cmd_ls()
                elif cmd == 'cd':
                    if len(parts) > 1:
                        self.cmd_cd(parts[1])
                    else:
                        print("Usage: cd <directory>")
                elif cmd == 'get':
                    if len(parts) > 1:
                        self.cmd_get(parts[1])
                    else:
                        print("Usage: get <remote-file>")
                elif cmd == 'put':
                    if len(parts) > 1:
                        self.cmd_put(parts[1])
                    else:
                        print("Usage: put <local-file>")
                elif cmd == 'delete':
                    if len(parts) > 1:
                        self.cmd_delete(parts[1])
                    else:
                        print("Usage: delete <remote-file>")
                elif cmd == 'quit' or cmd == 'exit':
                    if self.cmd_quit():
                        break
                else:
                    print("Available commands: ls, cd, get, put, delete, quit")

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python myftp.py <server-name>")
        sys.exit(1)

    server_name = sys.argv[1]

    # Create FTP client
    client = FTPClient(server_name)

    # Connect to server
    if not client.connect():
        sys.exit(1)

    # Login
    if not client.login():
        sys.exit(1)

    # Run interactive session
    client.run_interactive()


if __name__ == "__main__":
    main()