"""Interface web v19: carros com Xvfb + Chromium persistentes."""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import threading
import time

from suiteviagem.web import server as base


class CarWorker:
    def __init__(self, db, owner):
        self.db = db
        self.owner = owner
        self.lock = threading.RLock()
        self.process = None

    def command(self):
        return [
            "xvfb-run", "-a",
            "-s", "-screen 0 1920x1080x24 -nolisten tcp",
            "env", "-u", "WAYLAND_DISPLAY", "-u", "WAYLAND_SOCKET",
            base.sys.executable, "-u", "-m", "suiteviagem.cars_worker",
            "--db", str(self.db),
        ]

    def ensure(self):
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                return self.process
            proc = subprocess.Popen(
                self.command(),
                cwd=base.ROOT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            self.process = proc
            threading.Thread(target=self._read, args=(proc,), daemon=True).start()
            return proc

    def warm_async(self):
        def start():
            try:
                self.ensure()
            except Exception as exc:
                print(f"Carros v19: pré-aquecimento indisponível: {exc}", flush=True)
        threading.Thread(target=start, daemon=True).start()

    def submit(self, data, job_id):
        proc = self.ensure()
        message = {
            "op": "search",
            "job_id": job_id,
            "location": data["destination"].strip(),
            "start": data["start"].strip(),
            "end": data["end"].strip(),
            "limit": int(data.get("limit", 5)),
        }
        with self.lock:
            if proc.poll() is not None or proc.stdin is None:
                raise RuntimeError("Worker de carros encerrou antes da busca.")
            proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            proc.stdin.flush()

    def _read(self, proc):
        if proc.stdout is not None:
            for raw in proc.stdout:
                self.owner._car_line(proc, raw.rstrip("\n"))
        code = proc.wait()
        self.owner._car_exit(proc, code)
        with self.lock:
            if self.process is proc:
                self.process = None

    @staticmethod
    def _signal(proc, sig):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass

    def stop(self):
        with self.lock:
            proc = self.process
            self.process = None
        if proc is None or proc.poll() is not None:
            return
        self._signal(proc, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._signal(proc, signal.SIGKILL)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass


class JobsV19(base.Jobs):
    def __init__(self, db):
        super().__init__(db)
        self.car_worker = CarWorker(db, self)
        # O Chrome começa a aquecer assim que o servidor sobe.
        self.car_worker.warm_async()

    def start(self, data):
        if data.get("module") != "cars":
            return super().start(data)

        # Reutiliza toda a validação já existente no servidor congelado.
        base.command(data, self.db)
        if not all(base.shutil.which(name) for name in ("xvfb-run", "Xvfb", "xauth")):
            raise ValueError(
                "Display virtual indisponível. Instale xorg-server-xvfb e xorg-xauth."
            )

        with self.lock:
            if self.job and self.job["status"] in {"running", "cancelling"}:
                raise ValueError(
                    "Uma busca está em andamento. Aguarde ou cancele antes de iniciar outra."
                )
            self.job = {
                "id": str(base.uuid4()),
                "module": "cars",
                "status": "running",
                "started": time.time(),
                "query_id": None,
                "logs": base.deque(maxlen=180),
                "preview": None,
                "first_preview": None,
                "preview_version": 0,
            }
            self.process = None
            try:
                self.car_worker.submit(data, self.job["id"])
            except Exception:
                self.job.update(status="failed", finished=time.time())
                raise
            return self.state()

    def _car_line(self, proc, line):
        if line.startswith("CAR_READY:"):
            try:
                payload = json.loads(line[len("CAR_READY:"):])
                seconds = payload.get("boot_seconds")
                suffix = (
                    f" em {seconds:.1f}s" if isinstance(seconds, (int, float)) else ""
                )
                print(f"Carros v19: Chromium persistente aquecido{suffix}.", flush=True)
                if payload.get("warm_error"):
                    print(
                        "Carros v19: homepage não pré-aqueceu por completo; "
                        "o worker continuará disponível.",
                        flush=True,
                    )
            except Exception:
                pass
            return

        if line.startswith("CAR_LOG:"):
            try:
                payload = json.loads(line[len("CAR_LOG:"):])
                with self.lock:
                    if (
                        self.job
                        and self.job.get("module") == "cars"
                        and payload.get("job_id") == self.job.get("id")
                    ):
                        message = str(payload.get("message", ""))
                        if message:
                            self.job["logs"].append(message)
                            match = re.search(
                                r"(?:Consulta registrada|Histórico salvo): ([0-9a-f-]{36})",
                                message,
                            )
                            if match:
                                self.job["query_id"] = match[1]
            except Exception:
                pass
            return

        if line.startswith("CAR_DONE:"):
            try:
                payload = json.loads(line[len("CAR_DONE:"):])
                with self.lock:
                    if (
                        self.job
                        and self.job.get("module") == "cars"
                        and payload.get("job_id") == self.job.get("id")
                    ):
                        if payload.get("query_id"):
                            self.job["query_id"] = payload["query_id"]
                        status = payload.get("status")
                        if status not in {"succeeded", "failed", "cancelled"}:
                            status = "failed"
                        self.job.update(status=status, finished=time.time())
            except Exception:
                pass
            return

        # Não polui a tela durante o boot. Só mostra saída inesperada se uma
        # consulta de carros estiver realmente em andamento.
        with self.lock:
            if (
                line
                and self.job
                and self.job.get("module") == "cars"
                and self.job.get("status") in {"running", "cancelling"}
            ):
                self.job["logs"].append("worker: " + line[:900])

    def _car_exit(self, proc, code):
        with self.lock:
            if (
                self.job
                and self.job.get("module") == "cars"
                and self.job.get("status") == "running"
            ):
                self.job["logs"].append(
                    f"Worker persistente encerrou inesperadamente (código {code})."
                )
                self.job.update(status="failed", finished=time.time())

    def cancel(self):
        with self.lock:
            is_car = bool(
                self.job
                and self.job.get("module") == "cars"
                and self.job.get("status") in {"running", "cancelling"}
            )
            if not is_car:
                return super().cancel()
            self.job["status"] = "cancelling"
            qid = self.job.get("query_id")

        # Cancelar uma busca Selenium de forma confiável exige matar o worker;
        # a próxima busca ganha automaticamente um worker/Chrome novo.
        self.car_worker.stop()

        if qid:
            try:
                with base.History(self.db) as history:
                    current = history.get(qid)
                    if current["status"] == "running":
                        history.finish(
                            qid,
                            status="cancelled",
                            results=[],
                            coverage={
                                "status": "partial",
                                "scope": "Busca de carros cancelada pelo usuário.",
                                "limitations": ["Coleta encerrada antecipadamente."],
                                "metrics": [],
                                "stop_reason": "cancelled",
                            },
                            warnings=["Worker persistente reiniciado após cancelamento."],
                        )
            except Exception:
                pass

        with self.lock:
            if self.job:
                self.job.update(status="cancelled", finished=time.time())

        self.car_worker.warm_async()
        return self.state()

    def close(self):
        self.car_worker.stop()
        # Se houver um processo convencional de voos/hotéis/eventos, usa o
        # fechamento original.
        if self.process is not None:
            super().close()


def main():
    # O servidor congelado resolve Jobs pelo namespace global em runtime.
    # Trocamos apenas a classe de Jobs durante esta execução experimental.
    original = base.Jobs
    base.Jobs = JobsV19
    try:
        base.main()
    finally:
        base.Jobs = original


if __name__ == "__main__":
    main()
