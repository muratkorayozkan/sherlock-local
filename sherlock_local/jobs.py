"""Bounded, ephemeral scan state and subprocess lifecycle."""
import copy
import json
import subprocess
import sys
import threading
import time
import uuid
from collections import OrderedDict


class BusyError(Exception):
    pass


class JobManager:
    def __init__(self, command_factory=None, max_jobs=20, max_seconds=600):
        self.command_factory = command_factory or (lambda payload: [sys.executable, "-u", "-m", "sherlock_local.worker"])
        self.max_jobs = max_jobs
        self.max_seconds = max_seconds
        self.jobs = OrderedDict()
        self.processes = {}
        self.lock = threading.RLock()

    def start(self, username, sites, timeout):
        with self.lock:
            if any(job["state"] == "running" for job in self.jobs.values()):
                raise BusyError("Önce devam eden aramayı durdurun veya tamamlanmasını bekleyin.")
            while len(self.jobs) >= self.max_jobs:
                self.jobs.popitem(last=False)
            job_id = uuid.uuid4().hex
            job = {"id": job_id, "username": username, "state": "running", "total": len(sites),
                   "results": [], "error": None, "started_at": time.time()}
            payload = {"username": username, "sites": sites, "timeout": timeout}
            process = subprocess.Popen(self.command_factory(payload), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            self.jobs[job_id] = job
            self.processes[job_id] = process
            threading.Thread(target=self._watch, args=(job_id, process, payload), daemon=True).start()
            return copy.deepcopy(job)

    def _watch(self, job_id, process, payload):
        watchdog = threading.Timer(self.max_seconds, self._expire, args=(job_id,))
        watchdog.daemon = True
        watchdog.start()
        done = False
        try:
            try:
                process.stdin.write(json.dumps(payload) + "\n")
                process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
            for line in process.stdout:
                try:
                    event = json.loads(line)
                except (ValueError, TypeError):
                    continue
                with self.lock:
                    job = self.jobs[job_id]
                    if job["state"] != "running":
                        break
                    if event.get("type") == "started":
                        job["total"] = event["total"]
                    elif event.get("type") == "result":
                        job["results"].append({k: v for k, v in event.items() if k != "type"})
                    elif event.get("type") == "error":
                        job["error"] = event["message"]
                    elif event.get("type") == "done":
                        done = True
            code = process.wait()
            with self.lock:
                job = self.jobs[job_id]
                if job["state"] == "running":
                    job["state"] = "completed" if done and code == 0 and not job["error"] else "failed"
                    if job["state"] == "failed" and not job["error"]:
                        job["error"] = "Arama işlemi beklenmedik şekilde kapandı. Yeniden deneyin."
        finally:
            watchdog.cancel()
            process.stdout.close()
            with self.lock:
                self.processes.pop(job_id, None)

    def _expire(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if job and job["state"] == "running":
                job["state"] = "failed"
                job["error"] = "Arama süre sınırına ulaştı (10 dakika). Daha az platformla yeniden deneyin."
                process = self.processes.get(job_id)
                if process and process.poll() is None:
                    process.kill()

    def get(self, job_id):
        with self.lock:
            return copy.deepcopy(self.jobs[job_id])

    def cancel(self, job_id):
        with self.lock:
            job = self.jobs[job_id]
            if job["state"] == "running":
                job["state"] = "cancelled"
                process = self.processes.get(job_id)
                if process and process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
            return copy.deepcopy(job)

    def close(self):
        for job_id in list(self.jobs):
            self.cancel(job_id)
