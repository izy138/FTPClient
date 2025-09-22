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