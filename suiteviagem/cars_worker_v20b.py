"""Worker v20B: v19 persistente + Chromium enxuto para reduzir tempo até os primeiros cards.

Experimento deliberadamente pequeno:
- mantém a arquitetura/worker persistente da v19;
- usa pageLoadStrategy=none para não esperar recursos que não participam da coleta;
- bloqueia imagens, fontes e mídia pesada no Chromium compartilhado;
- não altera scraper_carro/discovercars.py, ordenação, parsing, validações ou coleta.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

from suiteviagem.cars_worker import WarmCarsWorker, emit, DriverLease


BLOCKED_URLS = [
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.avif", "*.svg",
    "*.woff", "*.woff2", "*.ttf", "*.otf",
    "*.mp4", "*.webm", "*.m4v", "*.mp3", "*.ogg",
]


class WarmCarsWorkerV20B(WarmCarsWorker):
    def new_driver(self):
        binary = shutil.which("chromium")
        if not binary:
            raise RuntimeError("Chromium não encontrado.")

        options = webdriver.ChromeOptions()
        options.binary_location = binary
        options.page_load_strategy = "none"
        options.add_argument("--window-size=1200,800")
        options.add_argument("--lang=en-US")
        options.add_argument("--ozone-platform=x11")
        options.add_argument("--blink-settings=imagesEnabled=false")
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.images": 2,
            "profile.default_content_setting_values.notifications": 2,
        })

        started = time.monotonic()
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)

        # Bloqueio adicional pelo DevTools. Se Chromium mudar a API, a busca
        # continua funcionando apenas com as preferências acima.
        cdp_error = None
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": BLOCKED_URLS})
        except Exception as exc:
            cdp_error = f"{type(exc).__name__}: {str(exc)[:200]}"

        # Pré-aquecimento continua existindo, mas não espera imagens/fontes/mídia.
        warm_error = None
        try:
            driver.get("https://www.discovercars.com/")
            WebDriverWait(driver, 15, poll_frequency=0.1).until(
                lambda d: d.execute_script("return !!document.body")
            )
        except Exception as exc:
            warm_error = f"{type(exc).__name__}: {str(exc)[:240]}"

        self.driver = driver
        self.engine.webdriver.Chrome = lambda *args, **kwargs: DriverLease(self.driver)
        emit("CAR_READY:", {
            "variant": "v20b-lean",
            "page_load_strategy": "none",
            "heavy_resources_blocked": True,
            "boot_seconds": round(time.monotonic() - started, 3),
            "warm_error": warm_error,
            "cdp_error": cdp_error,
        })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()

    worker = WarmCarsWorkerV20B(args.db)
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
                    emit("CAR_PONG:", {"ok": True, "variant": "v20b-lean"})
                elif command.get("op") == "quit":
                    break
            except (ValueError, TypeError, KeyError) as exc:
                emit("CAR_PROTOCOL_ERROR:", {"message": str(exc)[:500]})
    finally:
        worker.close()


if __name__ == "__main__":
    main()
