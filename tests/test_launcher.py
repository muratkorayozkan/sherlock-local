import socket
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows launcher")
def test_launcher_uses_existing_environment_and_reports_occupied_port():
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "start.ps1"), "-NoBrowser", "-Port", str(port)],
                                cwd=root, capture_output=True, text=True, errors="replace", timeout=15)
    assert result.returncode == 1
    assert "Installing dependencies" not in result.stdout
    assert "NameError" not in result.stderr
    assert str(port) in result.stderr
