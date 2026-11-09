"""Start the application on loopback only."""
import argparse
import socket
import threading
import webbrowser

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Sherlock Local")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port 1–65535 arasında olmalıdır.")
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", args.port))
    except OSError:
        parser.exit(1, f"Port {args.port} kullanımda. Önce açık uygulamayı kapatın veya --port ile başka port seçin.\n")
    url = f"http://127.0.0.1:{args.port}"
    print(f"Sherlock Local: {url}\nDurdurmak için Ctrl+C.")
    if not args.no_browser:
        timer = threading.Timer(1.5, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    uvicorn.run("sherlock_local.app:app", host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
