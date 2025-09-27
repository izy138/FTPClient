
import os
import re
import sys
import socket

CRLF = "\r\n"
BUF = 8192


class SimpleFTP:
    def __init__(self, host, port=21):
        self.host = host
        self.port = port
        self.ctrl_sock = None
        self.ctrl_reader = None

    
    def connect(self):
        """Open control connection and read server greeting."""
        try:
            self.ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.ctrl_sock.connect((self.host, self.port))
            self.ctrl_reader = self.ctrl_sock.makefile("r", encoding="utf-8", newline="\r\n")
            code, msg = self._read_reply()
            print(msg)
            return code == 220
        except Exception as e:
            print(f"Failure: cannot connect ({e})")
            return False

    def _send(self, line: str):
        """Send a single FTP command with CRLF."""
        self.ctrl_sock.sendall((line + CRLF).encode("ascii", errors="strict"))

    def _read_reply(self):
       
        line = self.ctrl_reader.readline()
        if not line:
            raise RuntimeError("Server closed connection.")
        line = line.rstrip("\r\n")
        if len(line) < 3 or not line[:3].isdigit():
            return 0, line
        code = int(line[:3])
        # Multi-line reply
        if len(line) >= 4 and line[3] == "-":
            lines = [line]
            term = f"{code} "
            while True:
                nxt = self.ctrl_reader.readline()
                if not nxt:
                    raise RuntimeError("Server closed during multi-line reply.")
                nxt = nxt.rstrip("\r\n")
                lines.append(nxt)
                if nxt.startswith(term):
                    break
            return code, "\n".join(lines)
        return code, line

    
    def login(self):
        user = input("Username: ").strip()
        self._send(f"USER {user}")
        code, msg = self._read_reply()
        print(msg)
        if code == 331:
            pwd = input("Password: ").strip()
            self._send(f"PASS {pwd}")
            code, msg = self._read_reply()
            print(msg)
        if code == 230:
            print("Login successful.")
            return True
        print("Login failed.")
        return False

    
    def _open_data_socket(self):
        """Enter PASV and connect a data socket to the provided host/port."""
        self._send("PASV")
        code, msg = self._read_reply()
        print(msg)
        if code != 227:
            print("Failure: PASV not accepted.")
            return None
        
        nums = re.findall(r"(\d+)", msg)
        if len(nums) < 6:
            print("Failure: could not parse PASV tuple.")
            return None
        h1, h2, h3, h4, p1, p2 = [int(x) for x in nums[-6:]]
        ip = f"{h1}.{h2}.{h3}.{h4}"
        port = (p1 << 8) + p2
        try:
            ds = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ds.connect((ip, port))
            return ds
        except Exception as e:
            print(f"Failure: cannot create data connection ({e})")
            return None

    
    def do_ls(self):
        ds = self._open_data_socket()
        if not ds:
            return
        self._send("LIST")
        code, msg = self._read_reply()
        if code not in (125, 150):
            print("Failure: LIST not accepted by server.")
            ds.close()
            return
        data = []
        while True:
            b = ds.recv(BUF)
            if not b:
                break
            data.append(b)
        ds.close()
        listing = b"".join(data).decode("utf-8", errors="replace").strip()
        if listing:
            print(listing)
        code, msg = self._read_reply()
        print(msg)
        if code == 226:
            print("Success: ls completed.")

    def do_cd(self, path: str):
        self._send(f"CWD {path}")
        code, msg = self._read_reply()
        print(msg)
        if code == 250:
            print("Success: changed directory.")
        else:
            print("Failure: could not change directory.")

    def do_get(self, remote: str):
        ds = self._open_data_socket()
        if not ds:
            return
        self._send(f"RETR {remote}")
        code, msg = self._read_reply()
        print(msg)
        if code not in (125, 150):
            print("Failure: server refused RETR.")
            ds.close()
            return
        local = os.path.basename(remote) or "downloaded.file"
        n = 0
        with open(local, "wb") as f:
            while True:
                b = ds.recv(BUF)
                if not b:
                    break
                f.write(b)
                n += len(b)
        ds.close()
        code, msg = self._read_reply()
        print(msg)
        if code == 226:
            print(f"Success: downloaded {n} bytes to '{local}'.")

    def do_put(self, local: str):
        if not os.path.isfile(local):
            print(f"Failure: local file not found: {local}")
            return
        ds = self._open_data_socket()
        if not ds:
            return
        remote = os.path.basename(local) or "uploaded.file"
        self._send(f"STOR {remote}")
        code, msg = self._read_reply()
        print(msg)
        if code not in (125, 150):
            print("Failure: server refused STOR.")
            ds.close()
            return
        sent = 0
        with open(local, "rb") as f:
            while True:
                chunk = f.read(BUF)
                if not chunk:
                    break
                ds.sendall(chunk)
                sent += len(chunk)
        ds.close()
        code, msg = self._read_reply()
        print(msg)
        if code == 226:
            print(f"Success: uploaded {sent} bytes from '{local}'.")

    def do_delete(self, remote: str):
        self._send(f"DELE {remote}")
        code, msg = self._read_reply()
        print(msg)
        if code in (200, 250):
            print("Success: file deleted.")
        else:
            print("Failure: could not delete file.")

    def do_quit(self):
        try:
            self._send("QUIT")
            code, msg = self._read_reply()
            print(msg)
        except Exception:
            pass
        finally:
            try:
                self.ctrl_reader.close()
            except Exception:
                pass
            try:
                self.ctrl_sock.close()
            except Exception:
                pass
        print("Goodbye.")

    
    def loop(self):
        while True:
            try:
                raw = input("myftp> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                self.do_quit()
                break
            if not raw:
                continue
            parts = raw.split()
            cmd = parts[0].lower()
            if cmd == "ls":
                self.do_ls()
            elif cmd == "cd" and len(parts) > 1:
                self.do_cd(parts[1])
            elif cmd == "get" and len(parts) > 1:
                self.do_get(parts[1])
            elif cmd == "put" and len(parts) > 1:
                self.do_put(parts[1])
            elif cmd == "delete" and len(parts) > 1:
                self.do_delete(parts[1])
            elif cmd == "quit":
                self.do_quit()
                break
            else:
                print("Commands: ls | cd <dir> | get <file> | put <file> | delete <file> | quit")


def main():
    if len(sys.argv) != 2:
        print("Usage: python myftp_martin.py <server>")
        sys.exit(1)
    host = sys.argv[1]
    client = SimpleFTP(host)
    if not client.connect():
        sys.exit(1)
    if not client.login():
        sys.exit(1)
    client.loop()


if __name__ == "__main__":
    main()
