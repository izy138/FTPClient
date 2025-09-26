import os
import re
import sys
import socket

CRLF = "\r\n"
PASV_TUPLE_RE = re.compile(r"\((\d{1,3}(?:,\d{1,3}){5})\)")

def _send_cmd(sock, cmd):
    sock.sendall((cmd + CRLF).encode("ascii", errors="strict"))

def _read_reply(reader):
    line = reader.readline()
    if not line:
        raise RuntimeError("Server closed connection.")
    line = line.rstrip("\r\n")
    if len(line) < 3 or not line[:3].isdigit():
        raise RuntimeError(f"Bad reply: {line!r}")
    code = int(line[:3])
    if len(line) >= 4 and line[3] == "-":
        lines = [line]
        term = f"{code} "
        while True:
            l2 = reader.readline()
            if not l2:
                raise RuntimeError("Server closed connection in multi-line reply.")
            l2 = l2.rstrip("\r\n")
            lines.append(l2)
            if l2.startswith(term):
                break
        return code, "\n".join(lines)
    return code, line

def connectControl(host, port=21, timeout=10):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, port))
    r = s.makefile("r", encoding="utf-8", newline="\r\n")
    code, msg = _read_reply(r)
    if code != 220:
        raise RuntimeError(f"Greeting not 220: {code}\n{msg}")
    return s, r

def login(control, reader):
    user = input("Enter username: ").strip()
    _send_cmd(control, f"USER {user}")
    code, msg = _read_reply(reader)
    print(msg)
    if code == 331:
        pwd = input("Enter password: ").strip()
        _send_cmd(control, f"PASS {pwd}")
        code, msg = _read_reply(reader)
        print(msg)
    if code != 230:
        raise RuntimeError("Login failed.")

def modePASV(control, reader):
    _send_cmd(control, "PASV")
    code, msg = _read_reply(reader)
    if code != 227:
        return code, None
    m = PASV_TUPLE_RE.search(msg)
    if not m:
        digits = re.findall(r"(\d+)", msg)
        if len(digits) >= 6:
            nums = digits[-6:]
        else:
            return 227, None
    else:
        nums = m.group(1).split(",")
    h1, h2, h3, h4, p1, p2 = [int(x) for x in nums]
    ip = f"{h1}.{h2}.{h3}.{h4}"
    port = (p1 << 8) + p2
    ds = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ds.connect((ip, port))
    return 227, ds

def cmd_ls(control, reader):
    try:
        code, data = modePASV(control, reader)
        if code != 227 or data is None:
            print("Failure: PASV failed for LIST.")
            return
        _send_cmd(control, "LIST")
        code, msg = _read_reply(reader)
        print(msg)
        if code not in (125, 150):
            data.close()
            print("Failure: LIST not accepted.")
            return
        chunks = []
        while True:
            b = data.recv(8192)
            if not b:
                break
            chunks.append(b)
        data.close()
        listing = b"".join(chunks).decode("utf-8", errors="replace")
        if listing:
            print(listing.rstrip("\n"))
        code, msg = _read_reply(reader)
        print(msg)
        if code == 226:
            print("Success: ls completed.")
        else:
            print("Failure: ls did not complete cleanly.")
    except Exception as e:
        print(f"Failure: ls error: {e}")

def cmd_cd(control, reader, path):
    try:
        _send_cmd(control, f"CWD {path}")
        code, msg = _read_reply(reader)
        print(msg)
        if code in (200, 250):
            print("Success: changed directory.")
        else:
            print("Failure: could not change directory.")
    except Exception as e:
        print(f"Failure: cd error: {e}")

def cmd_get(control, reader, name):
    try:
        code, data = modePASV(control, reader)
        if code != 227 or data is None:
            print("Failure: PASV failed for RETR.")
            return
        _send_cmd(control, f"RETR {name}")
        code, msg = _read_reply(reader)
        print(msg)
        if code not in (125, 150):
            data.close()
            print("Failure: server did not start data transfer.")
            return
        local = os.path.basename(name)
        nbytes = 0
        with open(local, "wb") as f:
            while True:
                b = data.recv(8192)
                if not b:
                    break
                f.write(b)
                nbytes += len(b)
        data.close()
        code, msg = _read_reply(reader)
        print(msg)
        if code == 226:
            print(f"Success: downloaded {nbytes} bytes to '{local}'.")
        else:
            print("Failure: download did not complete cleanly.")
    except Exception as e:
        print(f"Failure: get error: {e}")

def cmd_put(control, reader, local_path):
    try:
        if not os.path.isfile(local_path):
            print(f"Failure: local file not found: {local_path}")
            return
        code, data = modePASV(control, reader)
        if code != 227 or data is None:
            print("Failure: PASV failed for STOR.")
            return
        remote = os.path.basename(local_path)
        _send_cmd(control, f"STOR {remote}")
        code, msg = _read_reply(reader)
        print(msg)
        if code not in (125, 150):
            data.close()
            print("Failure: server did not accept STOR.")
            return
        sent = 0
        with open(local_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                data.sendall(chunk)
                sent += len(chunk)
        data.close()
        code, msg = _read_reply(reader)
        print(msg)
        if code == 226:
            print(f"Success: uploaded {sent} bytes from '{local_path}'.")
        else:
            print("Failure: upload did not complete cleanly.")
    except Exception as e:
        print(f"Failure: put error: {e}")

def cmd_delete(control, reader, name):
    try:
        _send_cmd(control, f"DELE {name}")
        code, msg = _read_reply(reader)
        print(msg)
        if code in (200, 250):
            print("Success: file deleted.")
        else:
            print("Failure: could not delete file.")
    except Exception as e:
        print(f"Failure: delete error: {e}")

def quitFTP(control, reader):
    try:
        _send_cmd(control, "QUIT")
        code, msg = _read_reply(reader)
        print(msg)
    except Exception:
        pass
    finally:
        try:
            reader.close()
        except Exception:
            pass
        try:
            control.close()
        except Exception:
            pass

def repl(control, reader):
    while True:
        try:
            raw = input("myftp> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            quitFTP(control, reader)
            break
        if not raw:
            continue
        if raw == "ls":
            cmd_ls(control, reader)
        elif raw.startswith("cd "):
            _, path = raw.split(" ", 1)
            cmd_cd(control, reader, path)
        elif raw.startswith("get "):
            _, name = raw.split(" ", 1)
            cmd_get(control, reader, name)
        elif raw.startswith("put "):
            _, name = raw.split(" ", 1)
            cmd_put(control, reader, name)
        elif raw.startswith("delete "):
            _, name = raw.split(" ", 1)
            cmd_delete(control, reader, name)
        elif raw == "quit":
            quitFTP(control, reader)
            break
        else:
            print("Unknown command. Try: ls | cd <dir> | get <file> | put <file> | delete <file> | quit")

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 myftp.py <server-name-or-ip>")
        sys.exit(1)
    host = sys.argv[1]
    try:
        control, reader = connectControl(host)
        login(control, reader)
        repl(control, reader)
    except Exception as e:
        print(f"Error: {e}")
        try:
            reader.close()
        except Exception:
            pass
        try:
            control.close()
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()