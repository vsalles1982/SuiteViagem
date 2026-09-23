"""SuiteViagem v20D — network scout.

Objetivo: descobrir qual resposta XHR/fetch alimenta os cards do DiscoverCars,
preservando a execução normal da v20C.

Esta versão NÃO tenta ainda substituir o DOM. Ela registra apenas respostas JSON
do próprio discovercars.com, sem headers/cookies e sem query strings de URLs.

Depois de uma busca, gera:
  resultados_carros/v20d_network_<timestamp>.json

Esse arquivo permite construir a próxima fast-path usando o payload da rede
antes de o React terminar de renderizar os cards.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import sys
import time
from datetime import date, timedelta, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from suiteviagem.cars_worker import emit, DriverLease
from suiteviagem.cars_worker_v20c import WarmCarsWorkerV20C, BLOCKED_URLS


def _redact_url(value):
    if not isinstance(value, str):
        return value
    try:
        u = urlsplit(value)
        if not u.scheme or not u.netloc:
            return value
        return urlunsplit((u.scheme, u.netloc, u.path, "", ""))
    except Exception:
        return value


def _redact_obj(value, depth=0):
    if depth > 12:
        return "<depth-limit>"
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            # Não guardar tokens/cookies/headers se aparecerem embutidos.
            lk = str(k).lower()
            if any(t in lk for t in ("cookie", "authorization", "token")):
                out[k] = "<redacted>"
            else:
                out[k] = _redact_obj(v, depth + 1)
        return out
    if isinstance(value, list):
        return [_redact_obj(v, depth + 1) for v in value[:500]]
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            return _redact_url(value)
        # remove sq= caso apareça dentro de texto maior
        return re.sub(r'([?&]sq=)[A-Za-z0-9_+/=%.-]+', r'\1<redacted>', value)
    return value


def _walk_keys(value, depth=0):
    if depth > 10:
        return []
    keys = []
    if isinstance(value, dict):
        keys.extend(str(k) for k in value.keys())
        for v in value.values():
            keys.extend(_walk_keys(v, depth + 1))
    elif isinstance(value, list):
        for v in value[:50]:
            keys.extend(_walk_keys(v, depth + 1))
    return keys


def _score_json(value):
    keys = " ".join(k.lower() for k in _walk_keys(value))
    text = json.dumps(value, ensure_ascii=False)[:100000].lower()
    score = 0
    for token, weight in (
        ("offer", 5),
        ("price", 5),
        ("vehicle", 4),
        ("car", 3),
        ("supplier", 4),
        ("rental", 3),
        ("search", 2),
        ("total", 2),
        ("currency", 2),
    ):
        if token in keys:
            score += weight
        if token in text:
            score += 1
    return score


class WarmCarsWorkerV20D(WarmCarsWorkerV20C):
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
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
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

        # Única adição funcional da v20D:
        # ChromeDriver guarda os eventos CDP Network no log "performance".
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        started = time.monotonic()
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)

        cdp_error = None
        try:
            driver.execute_cdp_cmd("Network.enable", {
                "maxTotalBufferSize": 50_000_000,
                "maxResourceBufferSize": 10_000_000,
                "maxPostDataSize": 1_000_000,
            })
            driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": BLOCKED_URLS})
        except Exception as exc:
            cdp_error = f"{type(exc).__name__}: {str(exc)[:200]}"

        home_error = None
        try:
            driver.get("https://www.discovercars.com/")
            WebDriverWait(driver, 15, poll_frequency=0.1).until(
                lambda d: d.execute_script("return !!document.body")
            )
        except Exception as exc:
            home_error = f"{type(exc).__name__}: {str(exc)[:240]}"

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

        # Descartar rede do boot/prewarm; queremos só a próxima pesquisa do usuário.
        try:
            driver.get_log("performance")
        except Exception:
            pass

        self.driver = driver
        self.engine.webdriver.Chrome = lambda *args, **kwargs: DriverLease(self.driver)
        emit("CAR_READY:", {
            "variant": "v20d-network-scout",
            "page_load_strategy": "none",
            "performance_network_capture": True,
            "search_route_prewarmed": search_warm_error is None,
            "search_warm_seconds": search_warm_seconds,
            "boot_seconds": round(time.monotonic() - started, 3),
            "home_error": home_error,
            "search_warm_error": search_warm_error,
            "cdp_error": cdp_error,
        })

    def _capture_network(self, job_id):
        events = []
        try:
            raw_entries = self.driver.get_log("performance")
        except Exception as exc:
            return None, f"performance log: {type(exc).__name__}: {str(exc)[:240]}"

        seen = set()
        for entry in raw_entries:
            try:
                outer = json.loads(entry.get("message", "{}"))
                msg = outer.get("message", {})
                if msg.get("method") != "Network.responseReceived":
                    continue
                params = msg.get("params", {})
                response = params.get("response", {})
                url = response.get("url", "")
                rtype = params.get("type", "")
                mime = (response.get("mimeType") or "").lower()
                status = int(response.get("status") or 0)
                if "discovercars.com" not in url:
                    continue
                if rtype not in ("XHR", "Fetch") and "json" not in mime:
                    continue
                request_id = params.get("requestId")
                if not request_id or request_id in seen:
                    continue
                seen.add(request_id)

                item = {
                    "request_id": request_id,
                    "url": _redact_url(url),
                    "resource_type": rtype,
                    "mime_type": mime,
                    "status": status,
                    "encoded_data_length": response.get("encodedDataLength"),
                    "score": 0,
                    "json": None,
                    "body_error": None,
                }

                # Só tentamos corpo de respostas plausíveis e bem-sucedidas.
                if 200 <= status < 300:
                    try:
                        body_info = self.driver.execute_cdp_cmd(
                            "Network.getResponseBody", {"requestId": request_id}
                        )
                        body = body_info.get("body", "")
                        if body_info.get("base64Encoded"):
                            body = base64.b64decode(body).decode("utf-8", errors="replace")
                        if len(body) <= 2_000_000:
                            parsed = json.loads(body)
                            item["score"] = _score_json(parsed)
                            if item["score"] > 0:
                                item["json"] = _redact_obj(parsed)
                    except Exception as exc:
                        item["body_error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
                events.append(item)
            except Exception:
                continue

        # Prioriza payloads que parecem conter ofertas/preços.
        events.sort(key=lambda x: (x.get("score", 0), x.get("encoded_data_length") or 0), reverse=True)
        candidates = [e for e in events if e.get("score", 0) > 0][:12]
        if not candidates:
            candidates = events[:12]

        out_dir = Path.cwd() / "resultados_carros"
        out_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = out_dir / f"v20d_network_{stamp}.json"
        report = {
            "schema_version": 1,
            "variant": "v20d-network-scout",
            "job_id": job_id,
            "captured_response_count": len(events),
            "candidate_count": len(candidates),
            "note": (
                "Somente XHR/fetch do domínio DiscoverCars. "
                "URLs sem query string; headers/cookies/tokens não são armazenados."
            ),
            "candidates": candidates,
        }
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
                        encoding="utf-8")
        return path, None

    def run_search(self, command):
        job_id = command["job_id"]

        # Esvaziar qualquer resto de rede antes da consulta real.
        try:
            self.driver.get_log("performance")
        except Exception:
            pass

        super().run_search(command)

        path, err = self._capture_network(job_id)
        if path:
            emit("CAR_LOG:", {
                "job_id": job_id,
                "message": "v20D network scout salvo: " + str(path),
            })
        elif err:
            emit("CAR_LOG:", {
                "job_id": job_id,
                "message": "v20D network scout falhou: " + err,
            })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()

    worker = WarmCarsWorkerV20D(args.db)
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
                    emit("CAR_PONG:", {"ok": True, "variant": "v20d-network-scout"})
                elif command.get("op") == "quit":
                    break
            except (ValueError, TypeError, KeyError) as exc:
                emit("CAR_PROTOCOL_ERROR:", {"message": str(exc)[:500]})
    finally:
        worker.close()


if __name__ == "__main__":
    main()
