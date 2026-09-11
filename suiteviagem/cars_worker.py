"""Worker persistente do DiscoverCars para a interface web v19."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time

from selenium import webdriver
from selenium.common.exceptions import WebDriverException

from suiteviagem.adapters import discovercars as adapter
from suiteviagem.history import History


class DriverLease:
    """Proxy: o coletor pode chamar quit(), mas o Chrome compartilhado permanece vivo."""
    def __init__(self, driver):
        object.__setattr__(self, "_driver", driver)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_driver"), name)

    def __setattr__(self, name, value):
        return setattr(object.__getattribute__(self, "_driver"), name, value)

    def quit(self):
        return None


def emit(prefix, payload):
    print(prefix + json.dumps(payload, ensure_ascii=False), flush=True)


class WarmCarsWorker:
    def __init__(self, db):
        self.db = db
        self.engine, self.version = adapter.load_engine()
        self.driver = None
        self._original_chrome = self.engine.webdriver.Chrome
        # Faz o adapter reutilizar exatamente o engine v18 carregado aqui,
        # preservando também collector_version no histórico.
        adapter.load_engine = lambda: (self.engine, self.version)

    def new_driver(self):
        binary = shutil.which("chromium")
        if not binary:
            raise RuntimeError("Chromium não encontrado.")
        options = webdriver.ChromeOptions()
        options.binary_location = binary
        options.add_argument("--window-size=1200,800")
        options.add_argument("--lang=en-US")
        options.add_argument("--ozone-platform=x11")

        started = time.monotonic()
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)

        # Pré-aquece DNS/TLS/JS/CSS/cookies antes do primeiro clique do usuário.
        warm_error = None
        try:
            driver.get("https://www.discovercars.com/")
        except Exception as exc:
            warm_error = f"{type(exc).__name__}: {str(exc)[:240]}"

        self.driver = driver
        self.engine.webdriver.Chrome = lambda *args, **kwargs: DriverLease(self.driver)
        emit("CAR_READY:", {
            "boot_seconds": round(time.monotonic() - started, 3),
            "warm_error": warm_error,
        })

    def ensure_driver(self):
        if self.driver is None:
            self.new_driver()
            return
        try:
            _ = self.driver.current_url
        except WebDriverException:
            self.restart_driver()

    def restart_driver(self):
        old = self.driver
        self.driver = None
        if old is not None:
            try:
                old.quit()
            except Exception:
                pass
        self.new_driver()

    def run_search(self, command):
        job_id = command["job_id"]
        self.ensure_driver()

        def log(message):
            emit("CAR_LOG:", {"job_id": job_id, "message": str(message)})

        result = None
        try:
            with History(self.db) as history:
                result = adapter.search(
                    history,
                    command["location"],
                    command["start"],
                    command["end"],
                    int(command["limit"]),
                    log=log,
                )

            # Mantém no log web o mesmo fechamento amigável do CLI.
            log(f"✓ Histórico salvo: {result['query_id']}")
            log(
                f"Estado: {result['status']} | Carros: {len(result['results'])} | "
                f"Cobertura: {result['coverage']['status']}"
            )
            for item in result["results"]:
                cents = item["price"]["amount_minor"]
                log(
                    f"{item['title']} | {item['details']['supplier']} | "
                    f"Total anunciado: R$ {cents//100},{cents%100:02d}"
                )
            for error in result["errors"]:
                log("Erro: " + error["message"])

            emit("CAR_DONE:", {
                "job_id": job_id,
                "query_id": result["query_id"],
                "status": result["status"],
            })

            # Se a consulta revelou uma sessão quebrada, prepara Chrome novo
            # para a próxima busca sem derrubar o servidor web.
            if result["status"] == "failed":
                joined = " ".join(
                    str(e.get("message", "")) for e in result.get("errors", [])
                ).lower()
                if any(token in joined for token in (
                    "invalid session", "disconnected", "chrome not reachable",
                    "target window already closed", "web view not found"
                )):
                    self.restart_driver()

        except BaseException as exc:
            emit("CAR_LOG:", {
                "job_id": job_id,
                "message": f"Worker v19 falhou: {type(exc).__name__}: {str(exc)[:900]}",
            })
            emit("CAR_DONE:", {
                "job_id": job_id,
                "query_id": result.get("query_id") if isinstance(result, dict) else None,
                "status": "failed",
            })
            try:
                self.restart_driver()
            except Exception:
                pass

    def close(self):
        self.engine.webdriver.Chrome = self._original_chrome
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()

    worker = WarmCarsWorker(args.db)
    try:
        worker.new_driver()
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                command = json.loads(raw)
                if command.get("op") == "search":
                    worker.run_search(command)
                elif command.get("op") == "ping":
                    emit("CAR_PONG:", {"ok": True})
                elif command.get("op") == "quit":
                    break
            except (ValueError, TypeError, KeyError) as exc:
                emit("CAR_PROTOCOL_ERROR:", {"message": str(exc)[:500]})
    finally:
        worker.close()


if __name__ == "__main__":
    main()
