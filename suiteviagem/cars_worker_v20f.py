"""SuiteViagem v20F — Browser API transport.

Base: v20E champion.

A v20E already cut DOM parsing/collection to zero. The remaining easy target is
the Python urllib transport used by autocomplete/create-search. v20F keeps the
same v20E result API fast-path, but routes engine._json_request through fetch()
inside the already-warm Chromium session.

Expected gain:
- reuse Chromium's warm TLS/HTTP2 connection to discovercars.com;
- avoid opening a separate Python HTTPS path for create-search;
- preserve all v20E validation and automatic DOM fallback.
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from suiteviagem.cars_worker import emit
from suiteviagem.cars_worker_v20e import WarmCarsWorkerV20E


class WarmCarsWorkerV20F(WarmCarsWorkerV20E):
    def new_driver(self):
        super().new_driver()

        # After v20E completed its normal prewarm, all runtime API calls used by
        # criar_busca_direta() are moved into the same warm browser connection pool.
        self.engine._json_request = self._browser_json_request
        emit("CAR_LOG:", {
            "message": (
                "v20F ativo: autocomplete/create-search agora usam fetch() "
                "na conexão aquecida do Chromium."
            )
        })

    def _browser_json_request(self, url, *, payload=None, timeout=20):
        driver = self.driver
        previous_timeout = None
        try:
            # Selenium does not expose a getter consistently; simply set a bounded
            # timeout for this small API call.
            driver.set_script_timeout(timeout + 3)
            result = driver.execute_async_script(
                r"""
                const url = arguments[0];
                const payload = arguments[1];
                const timeoutMs = arguments[2];
                const done = arguments[arguments.length - 1];

                const ctrl = new AbortController();
                const timer = setTimeout(() => ctrl.abort(), timeoutMs);

                const opts = {
                    method: payload === null ? 'GET' : 'POST',
                    credentials: 'same-origin',
                    cache: 'no-store',
                    signal: ctrl.signal,
                    headers: {
                        'Accept': 'application/json, text/plain, */*'
                    }
                };
                if (payload !== null) {
                    opts.headers['Content-Type'] = 'application/json';
                    opts.body = JSON.stringify(payload);
                }

                fetch(url, opts)
                    .then(async (resp) => {
                        const text = await resp.text();
                        clearTimeout(timer);
                        done({
                            ok: resp.ok,
                            status: resp.status,
                            text: text
                        });
                    })
                    .catch((err) => {
                        clearTimeout(timer);
                        done({
                            ok: false,
                            status: 0,
                            error: String(err)
                        });
                    });
                """,
                url,
                payload,
                int(timeout * 1000),
            )
        except Exception as exc:
            raise ValueError(
                f"Browser API fetch falhou: {type(exc).__name__}: {str(exc)[:300]}"
            ) from exc

        if not isinstance(result, dict) or not result.get("ok"):
            status = result.get("status") if isinstance(result, dict) else None
            error = result.get("error") if isinstance(result, dict) else None
            raise ValueError(
                f"DiscoverCars API via browser respondeu HTTP {status}: "
                f"{str(error or '')[:240]}"
            )

        try:
            return json.loads(result.get("text") or "")
        except Exception as exc:
            raise ValueError("DiscoverCars API via browser não devolveu JSON válido.") from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()

    worker = WarmCarsWorkerV20F(args.db)
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
                    emit("CAR_PONG:", {"ok": True, "variant": "v20f-browser-api"})
                elif command.get("op") == "quit":
                    break
            except (ValueError, TypeError, KeyError) as exc:
                emit("CAR_PROTOCOL_ERROR:", {"message": str(exc)[:500]})
    finally:
        worker.close()


if __name__ == "__main__":
    main()
