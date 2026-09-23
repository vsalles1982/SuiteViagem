"""Worker v20C: v20B + aceleração do tempo até o primeiro card.

Objetivo único: reduzir o intervalo navigation -> first SearchList-Card sem mexer
na validação/ordenação/coleta do scraper.

Mudanças em relação à v20B:
- mantém pageLoadStrategy=none e bloqueio de recursos pesados;
- bloqueia telemetria/ads de terceiros que competem por rede/CPU;
- impede throttling de timers/renderização em janela Xvfb/oculta;
- pré-aquece uma rota /search/ no boot para cachear os bundles da página de resultados.

O scraper_carro/discovercars.py continua intocado.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import date, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from suiteviagem.cars_worker import WarmCarsWorker, emit, DriverLease


BLOCKED_URLS = [
    # recursos visuais não necessários para extrair os cards
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.avif", "*.svg",
    "*.woff", "*.woff2", "*.ttf", "*.otf",
    "*.mp4", "*.webm", "*.m4v", "*.mp3", "*.ogg",

    # publicidade/telemetria de terceiros: não participam dos resultados
    "*://www.googletagmanager.com/*",
    "*://googletagmanager.com/*",
    "*://www.google-analytics.com/*",
    "*://google-analytics.com/*",
    "*://googleads.g.doubleclick.net/*",
    "*://*.doubleclick.net/*",
    "*://www.googleadservices.com/*",
    "*://googleadservices.com/*",
    "*://connect.facebook.net/*",
    "*://www.facebook.com/tr/*",
    "*://static.hotjar.com/*",
    "*://script.hotjar.com/*",
    "*://*.clarity.ms/*",
    "*://bat.bing.com/*",
    "*://analytics.tiktok.com/*",
]


class WarmCarsWorkerV20C(WarmCarsWorker):
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

        # Não deixar o Chromium reduzir timers/renderização só porque está em Xvfb
        # ou sem foco visual. A aba da coleta deve trabalhar em velocidade normal.
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")

        # Menos serviços paralelos que não têm relação com a busca.
        options.add_argument("--disable-component-update")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-translate")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")

        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.images": 2,
            "profile.default_content_setting_values.notifications": 2,
        })

        started = time.monotonic()
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)

        cdp_error = None
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": BLOCKED_URLS})
        except Exception as exc:
            cdp_error = f"{type(exc).__name__}: {str(exc)[:200]}"

        # 1) aquece origem/cookies/conexões
        home_error = None
        try:
            driver.get("https://www.discovercars.com/")
            WebDriverWait(driver, 15, poll_frequency=0.1).until(
                lambda d: d.execute_script("return !!document.body")
            )
        except Exception as exc:
            home_error = f"{type(exc).__name__}: {str(exc)[:240]}"

        # 2) aquece especificamente a rota de RESULTADOS. Isso acontece no boot,
        # fora do relógio da consulta do usuário, e carrega/cacheia os chunks JS
        # e estruturas usados por /search/.
        search_warm_error = None
        search_warm_seconds = None
        try:
            tomorrow = date.today() + timedelta(days=1)
            day_after = tomorrow + timedelta(days=1)
            warm_started = time.monotonic()
            url, _, _ = self.engine.criar_busca_direta(
                "GRU", tomorrow, day_after, lambda *_: None
            )
            driver.get(url)
            WebDriverWait(driver, 30, poll_frequency=0.1).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, ".SearchList-Card")
            )
            search_warm_seconds = round(time.monotonic() - warm_started, 3)
        except Exception as exc:
            search_warm_error = f"{type(exc).__name__}: {str(exc)[:240]}"

        self.driver = driver
        self.engine.webdriver.Chrome = lambda *args, **kwargs: DriverLease(self.driver)
        emit("CAR_READY:", {
            "variant": "v20c-renderfast",
            "page_load_strategy": "none",
            "heavy_resources_blocked": True,
            "third_party_noise_blocked": True,
            "background_throttling_disabled": True,
            "search_route_prewarmed": search_warm_error is None,
            "search_warm_seconds": search_warm_seconds,
            "boot_seconds": round(time.monotonic() - started, 3),
            "home_error": home_error,
            "search_warm_error": search_warm_error,
            "cdp_error": cdp_error,
        })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()

    worker = WarmCarsWorkerV20C(args.db)
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
                    emit("CAR_PONG:", {"ok": True, "variant": "v20c-renderfast"})
                elif command.get("op") == "quit":
                    break
            except (ValueError, TypeError, KeyError) as exc:
                emit("CAR_PROTOCOL_ERROR:", {"message": str(exc)[:500]})
    finally:
        worker.close()


if __name__ == "__main__":
    main()
