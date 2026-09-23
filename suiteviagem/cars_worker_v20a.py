"""v20A: worker persistente com pageLoadStrategy=eager."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time

from selenium import webdriver

from suiteviagem.cars_worker import WarmCarsWorker, DriverLease, emit


class WarmCarsWorkerV20A(WarmCarsWorker):
    def new_driver(self):
        binary = shutil.which("chromium")
        if not binary:
            raise RuntimeError("Chromium não encontrado.")

        options = webdriver.ChromeOptions()
        options.binary_location = binary
        options.add_argument("--window-size=1200,800")
        options.add_argument("--lang=en-US")
        options.add_argument("--ozone-platform=x11")

        # ÚNICA mudança da v20A:
        # driver.get() retorna no DOMContentLoaded, enquanto o engine mantém
        # seus waits explícitos para cartões, ordenação e estabilidade.
        options.page_load_strategy = "eager"

        started = time.monotonic()
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)

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
            "experiment": "v20a-eager",
        })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()

    worker = WarmCarsWorkerV20A(args.db)
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
                    emit("CAR_PONG:", {"ok": True, "experiment": "v20a-eager"})
                elif command.get("op") == "quit":
                    break
            except (ValueError, TypeError, KeyError) as exc:
                emit("CAR_PROTOCOL_ERROR:", {"message": str(exc)[:500]})
    finally:
        worker.close()


if __name__ == "__main__":
    main()
