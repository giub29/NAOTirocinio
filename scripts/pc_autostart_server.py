# -*- coding: utf-8 -*-

import os
import sys
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WATCHDOG_PATH = os.path.join(PROJECT_ROOT, "scripts", "autonomous_watchdog.py")

WATCHDOG_PROCESS = None


class AutostartHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        return

    def _send(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

    def do_GET(self):
        global WATCHDOG_PROCESS

        if self.path == "/ping":
            self._send(200, "PC_AUTOSTART_SERVER_OK")
            return

        if self.path == "/start":
            if WATCHDOG_PROCESS is not None and WATCHDOG_PROCESS.poll() is None:
                self._send(200, "WATCHDOG_ALREADY_RUNNING")
                return

            try:
                print("[AUTOSTART] Avvio watchdog:", WATCHDOG_PATH)

                WATCHDOG_PROCESS = subprocess.Popen(
                    [sys.executable, WATCHDOG_PATH],
                    cwd=PROJECT_ROOT
                )

                self._send(200, "WATCHDOG_STARTED")

            except Exception as e:
                self._send(500, "ERROR_STARTING_WATCHDOG: %s" % str(e))

            return

        if self.path == "/status":
            if WATCHDOG_PROCESS is not None and WATCHDOG_PROCESS.poll() is None:
                self._send(200, "WATCHDOG_RUNNING")
            else:
                self._send(200, "WATCHDOG_STOPPED")
            return

        self._send(404, "UNKNOWN_COMMAND")


def main():
    host = "0.0.0.0"
    port = 8765

    print("[AUTOSTART] Server PC in ascolto su porta %d" % port)
    print("[AUTOSTART] Project root:", PROJECT_ROOT)
    print("[AUTOSTART] Watchdog:", WATCHDOG_PATH)

    server = HTTPServer((host, port), AutostartHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()