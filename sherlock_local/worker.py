"""Isolated Sherlock worker. stdin: request JSON; stdout: JSON-line events."""
import contextlib
import copy
import json
import sys

from sherlock_project.notify import QueryNotify
from sherlock_project.sherlock import sherlock

from sherlock_local.catalog import site_catalog


def run_scan(payload, emit):
    catalog = site_catalog()
    names = payload.get("sites") or list(catalog)
    data = {name: copy.deepcopy(catalog[name]) for name in names}
    emit({"type": "started", "total": len(data)})

    class Notify(QueryNotify):
        def update(self, result):
            status = {"Claimed": "found", "Available": "absent"}.get(result.status.value, "unknown")
            detail = str(result.context or "")
            # Sherlock 0.16 calls every non-2xx status_code response Available.
            # Its completed future lets the adapter distinguish errors from 404.
            future = data[result.site_name].get("request_future")
            if future is not None and future.done():
                try:
                    code = future.result().status_code
                    if code >= 400 and code not in (404, 410):
                        status = "unknown"
                        detail = f"Platform HTTP {code} yanıtı verdi; hesap durumu doğrulanamadı."
                except Exception:
                    status = "unknown"
            if result.status.value == "Illegal":
                detail = "Kullanıcı adı bu platformun biçimine uygun değil."
            elif result.status.value == "WAF":
                detail = "Platform otomatik isteği engelledi."
            emit({"type": "result", "site": result.site_name, "url": result.site_url_user,
                  "status": status, "detail": detail, "elapsed": result.query_time})

    sherlock(payload["username"], data, Notify(), timeout=payload.get("timeout", 15))
    emit({"type": "done"})


def main():
    output = sys.stdout

    def emit(event):
        output.write(json.dumps(event, ensure_ascii=True) + "\n")
        output.flush()

    try:
        payload = json.loads(sys.stdin.readline())
        # Upstream diagnostics must not corrupt the JSON protocol.
        with contextlib.redirect_stdout(sys.stderr):
            run_scan(payload, emit)
    except Exception:
        emit({"type": "error", "message": "Sherlock araması tamamlanamadı. Bağlantınızı kontrol edip yeniden deneyin."})
        sys.exit(1)


if __name__ == "__main__":
    main()
