#!/usr/bin/env python3
import socket
import sys
import os
import re


class FTPClient:

    # store the serve name, set the default port, and initializ the constrol socker
    # initialize the username and password as None for the user to fill out
    def __init__(self, server_name):
        self.server_name = server_name
        self.server_port = 21
        self.control_socket = None
        self.username = None
        self.password = None

        # the ftp protocol uses the control connection at port 21 for commands and responses between the server
        # and the data connection is used for file transfering.

    def connect(self):
        """ Establishes the connection to the FTP server"""
        try:
            
            # create the socket using AF_INET and the stream protocol
            # and create a control channel to send the FTP commands
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.connect((self.server_name, self.server_port))

            # Read welcome message and look for code 220
            response = self.receive_response()
            print(response)

            if not response.startswith('220'): # 220 means the service is ready for the new user
                print("Failed to connect to server")
                return False
            return True

        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def receive_response(self):
        """ Receive and returns the response we get from the server"""
        try:
            response = "" # response init to empty string
            while True:
                # receives up to 1024 bytes from the server and decodes it converting bytes into string
                data = self.control_socket.recv(1024).decode('ascii')
                response += data
                # Check if its a complete response which should end with \r\n
                if response.endswith('\r\n'):
                    break
            return response.strip() # this removes the trailing \r\n at the end 

        except Exception as e:
            print(f"Error receiving response: {e}")
            return ""

    def send_command(self, command):
        """ Send a command to the server and return the response"""
        try:
            # makes sure to add \r\n to command if its not present
            if not command.endswith('\r\n'):
                command += '\r\n'
            # encodes the command into bytes and sends the command through the control socket
            # it waits and receives the server response and resturns it.
            self.control_socket.send(command.encode('ascii'))
            return self.receive_response()
        except Exception as e:
            print(f"Error sending command: {e}")
            return ""

    def login(self):
        """Handles login to the server, gets username and password"""
        self.username = input("Username: ") #prompt the user for login
        response = self.send_command(f"USER {self.username}") #sends to server
        print(response)
        # checks if the username passes with 331, and prompts next for the password
        if response.startswith('331'):  
            self.password = input("Password: ")
            response = self.send_command(f"PASS {self.password}")
            print(response)
            # checks for successful login response with code 230
            if response.startswith('230'): 
                print("Login successful")
                return True
            else:
                print("Login failed")
                return False
        else:
            print("Username not accepted")
            return False

    def parse_passive_response(self, response):
        """ Parse PASV response to get IP and port for data connection"""

        # PASV format: 227 Entering Passive Mode (h1,h2,h3,h4,p1,p2)
        # where the IP = h1.h2.h3.h4 and Port = p1*256 + p2
        #example:
        # 227 Entering Passive Mode (192,168,1,100,20,21)
        # Where: IP = 192.168.1.100, Port = 20*256 + 21 = 5141
        match = re.search(r'\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)', response)
        if match:
            h1, h2, h3, h4, p1, p2 = map(int, match.groups())
            ip = f"{h1}.{h2}.{h3}.{h4}"
            port = p1 * 256 + p2
            return ip, port
        return None, None

    def create_data_connection(self):
        """Create data connection using passive mode"""
        # send PASV command, this tells the server to open the data port and wait
        response = self.send_command("PASV")
        print(response)
        # this checks if the server is in passive mode with code 227
        if not response.startswith('227'):
            print("Failed to enter passive mode")
            return None

        # Parse IP and port from response by extracting from the response
        ip, port = self.parse_passive_response(response)
        if not ip or not port:
            print("Failed to parse passive mode response")
            return None

        # create data socket and connect for data transfering
        try:
            # creates a new TCP socket for the data connect and connects to the servers port
            data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            data_socket.connect((ip, port))
            return data_socket
        except Exception as e:
            print(f"Failed to create data connection: {e}")
            return None

    def ls_command(self):
        """List files in current directory"""
        # Creates the data connection 
        data_socket = self.create_data_connection()
        if not data_socket:
            return

        # Sends the LIST command on the control connection
        response = self.send_command("LIST")
        print(response)
        # checks if the server is ready to send the data
        # checks for code 150 which means the file status is okay and can open a connection
        # code 125 means the data connection is already open and the file transfer is starting
        if response.startswith('150') or response.startswith('125'):
            # Receive the directory list from data connection
            file_list = ""
            while True:
                try:
                    # receives the data in chunks
                    data = data_socket.recv(1024).decode('ascii')
                    if not data: # no more data check means the trasnwfer is complete
                        break
                    file_list += data
                except:
                    break

            data_socket.close()
            print(file_list)

            # gets completion response from the control connection
            final_response = self.receive_response()
            print(final_response)
        else:
            data_socket.close()
            print("Failed to list directory")

    def cd_command(self, directory):
        """Change the working directory"""

        # send the cd (CWD) command 
        response = self.send_command(f"CWD {directory}")
        print(response)
        # Checks for code 250 which means the file action is completed
        if response.startswith('250'):
            print(f"Directory changed to {directory}")
        else:
            print("Failed to change directory")

    def get_command(self, filename):
        """Download file from server"""
        # create data connection first
        data_socket = self.create_data_connection()
        if not data_socket:
            return

        # Send RETR command to reques the file download to the server
        response = self.send_command(f"RETR {filename}")
        print(response)

        # check the server is ready to send the file
        #  code 150 means the file status is okay to send and opens the data connection
        if response.startswith('150') or response.startswith('125'):
            # Receive the file data
            total_bytes = 0
            try:
                # open file in binary write 
                with open(filename, 'wb') as f:
                    while True:
                        # receieve the daya in 1024 byte chunks
                        data = data_socket.recv(1024)
                        if not data: # transfer is complete
                            break
                        f.write(data)
                        total_bytes += len(data)

                data_socket.close()
                print(f"Successfully downloaded {filename} ({total_bytes} bytes)")

                # get completion response from the control connection
                final_response = self.receive_response()
                print(final_response)

            except Exception as e:
                print(f"Error downloading file: {e}")
                data_socket.close()
        else:
            data_socket.close()
            print("Failed to download file")

    def put_command(self, filename):
        """Upload file to server"""
        # Check if local file exists
        if not os.path.exists(filename):
            print(f"Local file {filename} not found")
            return

        # create data connection for the file to transfer 
    
        data_socket = self.create_data_connection()
        if not data_socket:
            return

        # Send STOR command to get and store the file in the directory
        response = self.send_command(f"STOR {filename}")
        print(response)

        if response.startswith('150') or response.startswith('125'):
            # read the local file and send the file data
            total_bytes = 0
            try:
                # read file in binary mode
                with open(filename, 'rb') as f:
                    while True:
                        data = f.read(1024) #reads the file in 1024 byte chunks
                        if not data:
                            break
                        data_socket.send(data) #sends the data chunks to the server
                        total_bytes += len(data)

                data_socket.close()
                # server knows the transfer is done when the connection is closed
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

    def delete_command(self, filename):
        """Delete file on server"""
        # sends the delete command with the name of file
        response = self.send_command(f"DELE {filename}")
        print(response)
        # checks if the delete was successsfulby checking for code 250
        if response.startswith('250'):
            print(f"Successfully deleted {filename}")
        else:
            print("Failed to delete file")

    def quit_command(self):
        """Quit FTP session"""
        # QUIT command tells the server the session is endding
        response = self.send_command("QUIT")
        print(response)
        self.control_socket.close() #terminates the connection to server
        print("Goodbye!")
        return True

    def run_connection(self):
        # there is where the server handles user commands
        # confirms successful connection
        print(f"Connected to {self.server_name}")

        # the main loop to process the user's functions
        while True:
            try:
                #Gets the user's input
                command = input("myftp> ").strip()
                if not command:
                    continue
                
                # splits on any white space 
                parts = command.split()
                cmd = parts[0].lower() 

                if cmd == 'ls':
                    self.ls_command()
                elif cmd == 'cd':
                    if len(parts) > 1:
                        self.cd_command(parts[1])
                    else:
                        print("Enter: cd <directory>")
                elif cmd == 'get':
                    if len(parts) > 1:
                        self.get_command(parts[1])
                    else:
                        print("Enter: get <remote-file>")
                elif cmd == 'put':
                    if len(parts) > 1:
                        self.put_command(parts[1])
                    else:
                        print("Enter: put <local-file>")
                elif cmd == 'delete':
                    if len(parts) > 1:
                        self.delete_command(parts[1])
                    else:
                        print("Enter: delete <remote-file>")
                elif cmd == 'quit' or cmd == 'exit' or cmd == 'logout':
                    if self.quit_command():
                        break
                else:
                    print("Available commands: ls, cd, get, put, delete, quit")

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
def main():
    # checks the command line arguments
    if len(sys.argv) != 2:
        print("Enter: python myftp.py <server-name>")
        sys.exit(1)

    server_name = sys.argv[1]

    #Creates the FTP client
    client = FTPClient(server_name)

    # connect to server
    if not client.connect():
        sys.exit(1)

    # Login for the user
    if not client.login():
        sys.exit(1)

    # run the user's commands by processing commands in a loop
    client.run_connection() 


if __name__ == "__main__":
    main()
    
    
    