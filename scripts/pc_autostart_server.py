# -*- coding: utf-8 -*-

import os
import sys
import socket
import subprocess
import threading

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from socketserver import ThreadingMixIn
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from SocketServer import ThreadingMixIn


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WATCHDOG_PATH = os.path.join(PROJECT_ROOT, "scripts", "autonomous_watchdog.py")

ROBOT_IP = os.environ.get("NAO_ROBOT_IP", "172.16.165.86")
ROBOT_PORT = int(os.environ.get("NAO_ROBOT_PORT", "9559"))

WATCHDOG_PROCESS = None
LOCK = threading.Lock()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def robot_raggiungibile(timeout=3):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        sock.connect((ROBOT_IP, ROBOT_PORT))
        return True
    except Exception:
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


class AutostartHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print("[HTTP] %s - %s" % (self.client_address[0], format % args))

    def _send(self, code, message):
        if not isinstance(message, bytes):
            message = message.encode("utf-8")

        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(message)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(message)
        self.wfile.flush()
        self.close_connection = True

    def do_GET(self):
        global WATCHDOG_PROCESS

        print("[AUTOSTART] Richiesta da %s: %s" % (self.client_address[0], self.path))

        if self.path == "/ping":
            self._send(200, "PC_AUTOSTART_SERVER_OK")
            return

        if self.path == "/robot":
            if robot_raggiungibile():
                self._send(200, "ROBOT_REACHABLE")
            else:
                self._send(200, "ROBOT_NOT_REACHABLE")
            return

        if self.path == "/status":
            with LOCK:
                running = WATCHDOG_PROCESS is not None and WATCHDOG_PROCESS.poll() is None

            if running:
                self._send(200, "WATCHDOG_RUNNING")
            else:
                self._send(200, "WATCHDOG_STOPPED")
            return

        if self.path == "/start":
            with LOCK:
                if WATCHDOG_PROCESS is not None and WATCHDOG_PROCESS.poll() is None:
                    self._send(200, "WATCHDOG_ALREADY_RUNNING")
                    return

                if not robot_raggiungibile():
                    print("[AUTOSTART] Robot non raggiungibile: %s:%s" % (ROBOT_IP, ROBOT_PORT))
                    self._send(503, "ROBOT_NOT_REACHABLE")
                    return

                try:
                    python_exe = os.environ.get("NAO_PYTHON", sys.executable)

                    print("[AUTOSTART] Avvio watchdog: %s" % WATCHDOG_PATH)
                    print("[AUTOSTART] Python per watchdog: %s" % python_exe)

                    WATCHDOG_PROCESS = subprocess.Popen(
                        [python_exe, WATCHDOG_PATH],
                        cwd=PROJECT_ROOT
                    )

                    self._send(200, "WATCHDOG_STARTED")
                    return

                except Exception as e:
                    self._send(500, "ERROR_STARTING_WATCHDOG: %s" % str(e))
                    return

        self._send(404, "UNKNOWN_COMMAND")


def main():
    host = "0.0.0.0"
    port = 8765

    print("[AUTOSTART] Server PC in ascolto su porta %d" % port)
    print("[AUTOSTART] Project root: %s" % PROJECT_ROOT)
    print("[AUTOSTART] Watchdog: %s" % WATCHDOG_PATH)
    print("[AUTOSTART] Python server: %s" % sys.executable)
    print("[AUTOSTART] NAO_PYTHON: %s" % os.environ.get("NAO_PYTHON", "NON DEFINITO"))
    print("[AUTOSTART] Robot atteso: %s:%s" % (ROBOT_IP, ROBOT_PORT))
    print("[AUTOSTART] Endpoint disponibili:")
    print("  http://127.0.0.1:8765/ping")
    print("  http://127.0.0.1:8765/robot")
    print("  http://127.0.0.1:8765/status")
    print("  http://127.0.0.1:8765/start")
    print("")

    server = ThreadedHTTPServer((host, port), AutostartHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()