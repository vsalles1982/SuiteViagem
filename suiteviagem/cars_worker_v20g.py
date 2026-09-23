"""SuiteViagem v20G — direct search API.

Base: v20F transport + v20E structured-offer parser.

Hipótese validada pela v20D:
- página canônica: /search/<search_uuid>?sq=...
- payload real:     /api/v2/search/<search_uuid>

A v20G não abre mais a página /search/.
Depois do create-search, extrai <search_uuid> da própria URL e consulta diretamente
/api/v2/search/<search_uuid>, com polling curto até data.offers ficar disponível.

Fallback em camadas:
1) direct API v20G
2) fast-path v20E (abre /search/ e captura Network.responseReceived)
3) DOM legado via fallback interno da v20E
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from suiteviagem.cars_worker import emit
from suiteviagem.cars_worker_v20f import WarmCarsWorkerV20F


_SEARCH_ID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")


class WarmCarsWorkerV20G(WarmCarsWorkerV20F):
    def __init__(self, db):
        super().__init__(db)
        # WarmCarsWorkerV20E.__init__ já guardou o DOM collector e substituiu
        # engine.coletar_ofertas pelo método v20E. Aqui promovemos a v20G.
        self._v20e_collector = self.coletar_ofertas_api
        self.engine.coletar_ofertas = self.coletar_ofertas_direct

    @staticmethod
    def _search_id_from_url(url):
        path = urlparse(url).path.rstrip("/")
        parts = path.split("/")
        if len(parts) < 2 or parts[-2] != "search":
            raise ValueError("URL canônica não contém /search/<uuid>.")
        search_id = parts[-1]
        if not _SEARCH_ID_RE.fullmatch(search_id):
            raise ValueError("ID de busca inesperado na URL canônica.")
        return search_id

    def _poll_direct_search_api(self, search_id, *, timeout=25):
        endpoint = f"https://www.discovercars.com/api/v2/search/{search_id}"
        deadline = time.monotonic() + timeout
        attempts = 0
        last_error = None

        while time.monotonic() < deadline:
            attempts += 1
            try:
                payload = self._browser_json_request(endpoint, timeout=min(8, timeout))
                data = payload.get("data") if isinstance(payload, dict) else None
                offers = data.get("offers") if isinstance(data, dict) else None
                if payload.get("success") is True and isinstance(offers, list) and offers:
                    return payload, attempts
            except Exception as exc:
                last_error = exc

            time.sleep(0.12)

        suffix = ""
        if last_error:
            suffix = f" Último erro: {type(last_error).__name__}: {str(last_error)[:180]}"
        raise TimeoutError(
            f"Direct search API não entregou offers em {timeout}s após {attempts} tentativas."
            + suffix
        )

    def coletar_ofertas_direct(
        self, destino, data_retirada, data_devolucao, limite_resultados, log=print
    ):
        timings = {}
        total_started = time.monotonic()
        stage_started = total_started

        def enter(name):
            nonlocal stage_started
            now = time.monotonic()
            if timings:
                # stage anterior já foi finalizado explicitamente onde necessário
                pass
            stage_started = now

        def elapsed():
            return time.monotonic() - stage_started

        try:
            retirada = datetime.strptime(data_retirada, "%Y-%m-%d").date()
            devolucao = datetime.strptime(data_devolucao, "%Y-%m-%d").date()
            if devolucao <= retirada:
                raise ValueError("A devolução precisa ser posterior à retirada.")
            limite = int(limite_resultados)
            if not 1 <= limite <= 100:
                raise ValueError("Escolha de 1 a 100 ofertas.")

            # Sem driver.get() da página de resultados.
            timings["driver_seconds"] = 0.0

            t_fast = time.monotonic()
            if destino.strip().startswith(("https://", "http://")):
                # Para links fornecidos, só usamos v20G se forem /search/<uuid>.
                url = destino.strip()
                consulta = self.engine.ler_consulta(url)
                local_selecionado = "Conforme link informado"
            else:
                url, consulta, local_selecionado = self.engine.criar_busca_direta(
                    destino.strip(), retirada, devolucao, log
                )
            timings["fast_path_seconds"] = round(time.monotonic() - t_fast, 4)
            timings["fast_path_used"] = 1
            timings["navigation_seconds"] = timings["fast_path_seconds"]

            log(
                "Datas conferidas: "
                + consulta["PickupDateTime"]
                + " → "
                + consulta["DropOffDateTime"]
            )

            search_id = self._search_id_from_url(url)
            t_wait = time.monotonic()
            payload, attempts = self._poll_direct_search_api(search_id, timeout=25)
            timings["results_wait_seconds"] = round(time.monotonic() - t_wait, 4)

            t_sort = time.monotonic()
            offers = payload["data"]["offers"]
            rows, errors = [], set()

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
                    "Direct API retornou offers, mas nenhum passou pela validação. "
                    + "; ".join(sorted(errors))[:700]
                )

            rows.sort(key=lambda r: r["TotalBRL"])
            resultados = rows[:limite]
            timings["sorting_seconds"] = round(time.monotonic() - t_sort, 4)

            timings["first_batch_seconds"] = round(
                time.monotonic() - total_started, 4
            )
            timings["collection_seconds"] = 0.0

            t_export = time.monotonic()
            pasta = Path.cwd() / "resultados_carros"
            pasta.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            path = pasta / f"discovercars_direct_api_{stamp}.csv"
            with path.open("x", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(
                    f, fieldnames=list(resultados[0]), delimiter=";"
                )
                writer.writeheader()
                writer.writerows(resultados)
            timings["export_seconds"] = round(time.monotonic() - t_export, 4)
            timings["cleanup_seconds"] = 0.0
            timings["total_seconds"] = round(time.monotonic() - total_started, 4)

            log(
                f"v20G DIRECT API: /api/v2/search/{search_id} respondeu "
                f"com offers em {attempts} tentativa(s)."
            )
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

            return {
                "consulta": consulta,
                "resultados": resultados,
                "erros": sorted(errors),
                "csv": str(path),
                "ofertas_coletadas": len(resultados),
                "motivo": "result_limit" if len(resultados) >= limite else "api_exhausted",
                "timings": timings,
            }

        except Exception as exc:
            reason = f"{type(exc).__name__}: {str(exc)[:420]}"
            log("v20G direct API indisponível; fallback v20E: " + reason)
            report = self._v20e_collector(
                destino, data_retirada, data_devolucao, limite_resultados, log
            )
            report.setdefault("erros", []).append(
                "v20G fallback direct API: " + reason
            )
            return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()

    worker = WarmCarsWorkerV20G(args.db)
    try:
        worker.new_driver()
        emit("CAR_LOG:", {
            "message": (
                "v20G ativo: /search/ não será aberto no caminho principal; "
                "o endpoint /api/v2/search/<uuid> será consultado diretamente."
            )
        })
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                command = json.loads(raw)
                if command.get("op") == "search":
                    worker.run_search(command)
                elif command.get("op") == "ping":
                    emit("CAR_PONG:", {"ok": True, "variant": "v20g-direct-search-api"})
                elif command.get("op") == "quit":
                    break
            except (ValueError, TypeError, KeyError) as exc:
                emit("CAR_PROTOCOL_ERROR:", {"message": str(exc)[:500]})
    finally:
        worker.close()


if __name__ == "__main__":
    main()
