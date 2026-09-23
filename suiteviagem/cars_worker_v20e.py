"""SuiteViagem v20E — API fast-path do DiscoverCars.

Usa o endpoint JSON que a v20D revelou:
    /api/v2/search/<uuid>

Fluxo:
create-search -> driver.get(search URL) -> capturar resposta JSON -> ordenar price.raw
-> devolver os 5 menores

Fallback seguro:
se o payload da API não puder ser lido/validado, executa a coleta normal da v20C.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sys
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from suiteviagem.cars_worker import emit, DriverLease
from suiteviagem.cars_worker_v20c import WarmCarsWorkerV20C, BLOCKED_URLS


SEARCH_API_FRAGMENT = "/api/v2/search/"


class WarmCarsWorkerV20E(WarmCarsWorkerV20C):
    def __init__(self, db):
        super().__init__(db)
        self._dom_collector = self.engine.coletar_ofertas
        # O adapter continuará vendo o mesmo "engine" e o mesmo collector_version,
        # mas a função pública de coleta passa a usar a fast-path da rede.
        self.engine.coletar_ofertas = self.coletar_ofertas_api

    def new_driver(self):
        binary = shutil.which("chromium")
        if not binary:
            raise RuntimeError("Chromium não encontrado.")

        options = webdriver.ChromeOptions()
        options.binary_location = binary
        # v3.8.5 — perfil NOVO a cada sessão. mkdtemp garante diretório único
        # mesmo em rebuild (onde o PID não muda) — evitava lock do Chrome.
        import os
        import tempfile
        from pathlib import Path as _Path
        _cache = _Path.home() / ".cache" / "suiteviagem"
        _cache.mkdir(parents=True, exist_ok=True)
        _profile = _Path(tempfile.mkdtemp(prefix=f"chrome_cars_{os.getpid()}_", dir=_cache))
        options.add_argument(f"--user-data-dir={_profile}")
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

        # Necessário para observar Network.responseReceived pelo ChromeDriver.
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        started = time.monotonic()
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)

        cdp_error = None
        try:
            driver.execute_cdp_cmd("Network.enable", {
                "maxTotalBufferSize": 50_000_000,
                "maxResourceBufferSize": 15_000_000,
                "maxPostDataSize": 1_000_000,
            })
            driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": BLOCKED_URLS})
        except Exception as exc:
            cdp_error = f"{type(exc).__name__}: {str(exc)[:220]}"

        home_error = None
        try:
            driver.get("https://www.discovercars.com/")
            WebDriverWait(driver, 15, poll_frequency=0.1).until(
                lambda d: d.execute_script("return !!document.body")
            )
        except Exception as exc:
            home_error = f"{type(exc).__name__}: {str(exc)[:240]}"

        # v3.8.5 — prewarm /search/ REMOVIDO. A v20G consulta /api/v2/search
        # diretamente; abrir /search/ no boot derrubava a única aba do Chrome.
        search_warm_error = None
        search_warm_seconds = None
        try:
            _ = driver.current_window_handle
        except Exception:
            try:
                driver.quit()
            except Exception:
                pass
            try:
                shutil.rmtree(_profile, ignore_errors=True)
            except Exception:
                pass
            raise

        try:
            driver.get_log("performance")
        except Exception:
            pass

        self.driver = driver
        self._profile_dir = _profile
        self.engine.webdriver.Chrome = lambda *args, **kwargs: DriverLease(self.driver)
        emit("CAR_READY:", {
            "variant": "v20e-api-fastpath",
            "page_load_strategy": "none",
            "api_fastpath": True,
            "search_route_prewarmed": search_warm_error is None,
            "search_warm_seconds": search_warm_seconds,
            "boot_seconds": round(time.monotonic() - started, 3),
            "home_error": home_error,
            "search_warm_error": search_warm_error,
            "cdp_error": cdp_error,
        })

    def _drain_performance_log(self):
        try:
            self.driver.get_log("performance")
        except Exception:
            pass

    def _wait_search_payload(self, timeout=35):
        """Espera a primeira resposta JSON /api/v2/search/<id> com offers."""
        deadline = time.monotonic() + timeout
        request_ids = []
        seen = set()
        last_error = None

        while time.monotonic() < deadline:
            try:
                entries = self.driver.get_log("performance")
            except Exception as exc:
                last_error = exc
                entries = []

            for entry in entries:
                try:
                    outer = json.loads(entry.get("message", "{}"))
                    msg = outer.get("message", {})
                    if msg.get("method") != "Network.responseReceived":
                        continue
                    params = msg.get("params", {})
                    response = params.get("response", {})
                    url = response.get("url", "")
                    status = int(response.get("status") or 0)
                    mime = (response.get("mimeType") or "").lower()
                    rid = params.get("requestId")
                    if (
                        rid
                        and rid not in seen
                        and SEARCH_API_FRAGMENT in url
                        and "discovercars.com" in url
                        and 200 <= status < 300
                        and ("json" in mime or params.get("type") in ("XHR", "Fetch"))
                    ):
                        request_ids.append(rid)
                        seen.add(rid)
                except Exception:
                    continue

            # getResponseBody pode ficar disponível alguns milissegundos depois de responseReceived.
            for rid in list(request_ids):
                try:
                    body_info = self.driver.execute_cdp_cmd(
                        "Network.getResponseBody", {"requestId": rid}
                    )
                    body = body_info.get("body", "")
                    if body_info.get("base64Encoded"):
                        import base64
                        body = base64.b64decode(body).decode("utf-8", errors="replace")
                    payload = json.loads(body)
                    data = payload.get("data") if isinstance(payload, dict) else None
                    offers = data.get("offers") if isinstance(data, dict) else None
                    if payload.get("success") is True and isinstance(offers, list) and offers:
                        return payload
                except Exception as exc:
                    last_error = exc

            time.sleep(0.05)

        if last_error:
            raise TimeoutError(
                "Resposta /api/v2/search não ficou disponível: "
                + f"{type(last_error).__name__}: {str(last_error)[:220]}"
            )
        raise TimeoutError("Nenhuma resposta /api/v2/search com offers foi capturada.")

    @staticmethod
    def _days(consulta):
        a = datetime.fromisoformat(consulta["PickupDateTime"])
        b = datetime.fromisoformat(consulta["DropOffDateTime"])
        return math.ceil((b - a).total_seconds() / 86400)

    def _offer_to_row(self, offer, consulta, local_selecionado, search_url):
        if not isinstance(offer, dict):
            raise ValueError("Oferta API inválida.")

        price = offer.get("price") or {}
        raw_price = price.get("raw")
        try:
            total = Decimal(str(raw_price))
        except Exception as exc:
            raise ValueError("Oferta API sem price.raw válido.") from exc
        if total <= 0:
            raise ValueError("Oferta API com preço não positivo.")

        vehicle = offer.get("vehicle") or {}
        supplier = offer.get("supplier") or {}
        rating = supplier.get("rating") or {}
        car_name = str(vehicle.get("carName") or "").strip()
        supplier_name = str(supplier.get("name") or "").strip()
        book_url = str(offer.get("bookUrl") or "").strip()

        if not car_name or not supplier_name or not book_url:
            raise ValueError("Oferta API incompleta.")

        link = urljoin(search_url, book_url)
        # Esta validação reaproveita exatamente a regra já usada pelo adapter:
        # o sq do link precisa representar a mesma consulta efetiva.
        source = self.engine.ler_consulta(link)
        if self.engine.identidade(source) != self.engine.identidade(consulta):
            raise ValueError("Oferta API pertence a outra consulta.")

        group = str(vehicle.get("sippGroup") or "").strip()
        category = ("or similar " + group) if group else "Não informado"
        reviews = rating.get("countryReviewCount")
        reviews_text = (
            f"{int(reviews):,} ratings" if isinstance(reviews, int) else "Não informado"
        )
        rating_score = rating.get("score")
        now = datetime.now().astimezone().isoformat()

        return {
            "Modelo": car_name,
            "Categoria": category,
            "Locadora": supplier_name,
            "TotalBRL": total,
            "Moeda": "BRL",
            "Periodo": f"Total for {self._days(consulta)} day"
                       + ("" if self._days(consulta) == 1 else "s"),
            "Nota": str(rating_score) if rating_score not in (None, "") else "Não informado",
            "Avaliacoes": reviews_text,
            "Link": link,
            "Retirada": consulta["PickupDateTime"],
            "Devolucao": consulta["DropOffDateTime"],
            "LocalRetiradaId": consulta["PickupLocationId"],
            "LocalDevolucaoId": consulta["DropOffLocationId"],
            "Residencia": consulta["ResidenceCountry"],
            "Idade": consulta["DriverAge"],
            "LocalSelecionado": local_selecionado,
            "CoberturaAdicional": "Não incluída",
            "ColetadoEm": now,
            "Escopo": (
                "Menores totais entre ofertas retornadas pela API do DiscoverCars; "
                "não garante todas as ofertas disponíveis"
            ),
        }

    def coletar_ofertas_api(
        self, destino, data_retirada, data_devolucao, limite_resultados, log=print
    ):
        """Compatível com o relatório de scraper_carro.discovercars.coletar_ofertas."""
        tempos = self.engine.TemposCarros()
        fallback_reason = None

        try:
            retirada = datetime.strptime(data_retirada, "%Y-%m-%d").date()
            devolucao = datetime.strptime(data_devolucao, "%Y-%m-%d").date()
            if devolucao <= retirada:
                raise ValueError("A devolução precisa ser posterior à retirada.")
            limite = int(limite_resultados)
            if not 1 <= limite <= 100:
                raise ValueError("Escolha de 1 a 100 ofertas.")

            tempos.enter("driver_seconds")
            driver = self.engine.webdriver.Chrome()
            local_selecionado = "Conforme link informado"
            tempos.enter("navigation_seconds")

            url = destino.strip()
            por_link = url.startswith(("https://", "http://"))
            if por_link:
                consulta = self.engine.ler_consulta(url)
            else:
                t_fast = time.monotonic()
                url, consulta, local_selecionado = self.engine.criar_busca_direta(
                    destino.strip(), retirada, devolucao, log
                )
                self._drain_performance_log()
                driver.get(url)
                tempos.values["fast_path_seconds"] = round(
                    time.monotonic() - t_fast, 4
                )
                tempos.values["fast_path_used"] = 1

            if por_link:
                self._drain_performance_log()
                driver.get(url)

            log(
                "Datas conferidas: "
                + consulta["PickupDateTime"]
                + " → "
                + consulta["DropOffDateTime"]
            )

            tempos.enter("results_wait_seconds")
            payload = self._wait_search_payload(timeout=35)

            tempos.enter("sorting_seconds")
            offers = payload["data"]["offers"]
            rows = []
            errors = set()
            for offer in offers:
                try:
                    rows.append(
                        self._offer_to_row(
                            offer, consulta, local_selecionado, url
                        )
                    )
                except ValueError as exc:
                    errors.add(str(exc))

            if not rows:
                raise ValueError(
                    "API retornou offers, mas nenhum passou pela validação. "
                    + "; ".join(sorted(errors))[:700]
                )

            # Ordenação local pelo total bruto da própria resposta.
            rows.sort(key=lambda r: r["TotalBRL"])
            resultados = rows[:limite]
            tempos.first_batch()

            tempos.enter("collection_seconds")
            # A fast-path já tem dados estruturados; não há estabilização de DOM.
            ofertas_coletadas = len(resultados)

            tempos.enter("export_seconds")
            pasta = Path.cwd() / "resultados_carros"
            pasta.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            path = pasta / f"discovercars_api_{stamp}.csv"
            with path.open("x", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(
                    f, fieldnames=list(resultados[0]), delimiter=";"
                )
                writer.writeheader()
                writer.writerows(resultados)

            log("API fast-path v20E: ofertas estruturadas capturadas antes do DOM.")
            log("Menores totais API:")
            for r in resultados:
                log(
                    f"{r['Modelo']} | {r['Locadora']} | "
                    f"{self.engine.formatar_preco(r['TotalBRL'])}"
                )
            log(
                f"Exportadas: {len(resultados)} | Limite solicitado: {limite} | "
                "Cobertura: Não incluída"
            )

            tempos.enter("cleanup_seconds")
            tempos.finish()
            return {
                "consulta": consulta,
                "resultados": resultados,
                "erros": sorted(errors),
                "csv": str(path),
                "ofertas_coletadas": ofertas_coletadas,
                "motivo": "result_limit" if len(resultados) >= limite else "api_exhausted",
                "timings": tempos.values,
            }

        except Exception as exc:
            fallback_reason = f"{type(exc).__name__}: {str(exc)[:420]}"
            log("v20E API fast-path indisponível; fallback DOM v20C: " + fallback_reason)

            # Importante: o coletor legado faz sua própria medição e mantém toda
            # a validação existente. O fallback garante que uma mudança do endpoint
            # não derrube a SuiteViagem.
            report = self._dom_collector(
                destino, data_retirada, data_devolucao, limite_resultados, log
            )
            report.setdefault("erros", []).append(
                "v20E fallback API: " + fallback_reason
            )
            return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()

    worker = WarmCarsWorkerV20E(args.db)
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
                    emit("CAR_PONG:", {"ok": True, "variant": "v20e-api-fastpath"})
                elif command.get("op") == "quit":
                    break
            except (ValueError, TypeError, KeyError) as exc:
                emit("CAR_PROTOCOL_ERROR:", {"message": str(exc)[:500]})
    finally:
        worker.close()


if __name__ == "__main__":
    main()
