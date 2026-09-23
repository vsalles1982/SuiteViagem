from __future__ import annotations

import re
import time
from urllib.parse import quote

from playwright.sync_api import sync_playwright

TARGET = "FlightsFrontendService/GetShoppingResults"

PRICE_PATTERNS = [
    re.compile(r'\[\[null,([0-9]+(?:\.[0-9]+)?)\],\\\"[A-Za-z0-9_+/=-]{20,}'),
    re.compile(r'\[\[null,([0-9]+(?:\.[0-9]+)?)\],"[A-Za-z0-9_+/=-]{20,}'),
    # v3.8.8 — fallback genérico: o Google varia a forma do token após o preço.
    re.compile(r'\[\[null,([0-9]+(?:\.[0-9]+)?)\]'),
]

BLOCK_TYPES = {"image", "font", "media"}
BLOCK_HOST_SNIPPETS = (
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick.net",
    "gstatic.com/images",
)

_FAST_SESSION = None


def _montar_url(origem: str, destino: str, data: str) -> str:
    q = f"Flights from {origem} to {destino} on {data} oneway"
    return f"https://www.google.com/travel/flights?q={quote(q)}&curr=BRL&hl=pt-BR"


def _extract_prices(body: str) -> list[float]:
    values = []
    for rx in PRICE_PATTERNS:
        for m in rx.finditer(body):
            try:
                value = float(m.group(1))
            except ValueError:
                continue
            if 1 <= value <= 100000:
                values.append(value)
        if values:
            break
    return values


def _safe_sync_playwright_start():
    """v3.8.5 — Playwright sync falha se houver asyncio loop no thread atual.
    Roda numa thread limpa para garantir ausência de loop."""
    try:
        import asyncio
        asyncio.get_running_loop()
        in_loop = True
    except RuntimeError:
        in_loop = False

    if not in_loop:
        return sync_playwright().start()

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(sync_playwright().start).result()


class GoogleFlightsFastSession:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.pw = _safe_sync_playwright_start()
        self.browser = self.pw.chromium.launch(headless=headless)
        self.context = self.browser.new_context(
            viewport={"width": 1000, "height": 700},
            locale="pt-BR",
            service_workers="block",
        )

        def route_handler(route):
            req = route.request
            if req.resource_type in BLOCK_TYPES:
                return route.abort()
            low = req.url.lower()
            if any(s in low for s in BLOCK_HOST_SNIPPETS):
                return route.abort()
            return route.continue_()

        self.context.route("**/*", route_handler)
        self.page = self.context.new_page()
        self.consent_checked = False

    def alive(self) -> bool:
        try:
            return self.browser.is_connected()
        except Exception:
            return False

    def close(self):
        try:
            self.browser.close()
        finally:
            self.pw.stop()

    def search(self, origem: str, destino: str, data: str) -> dict:
        url = _montar_url(origem, destino, data)
        t0 = time.monotonic()
        captured = {}
        diag = {"rpc_seen": 0, "no_price_bodies": 0}

        def on_response(response):
            diag["rpc_seen"] += 1
            if TARGET not in response.url or captured:
                return
            try:
                body = response.text()
            except Exception:
                diag["no_price_bodies"] += 1
                return

            prices = _extract_prices(body)
            if not prices:
                diag["no_price_bodies"] += 1
                return

            captured.update(
                status=response.status,
                response_chars=len(body),
                prices=prices,
                rpc_seconds=time.monotonic() - t0,
            )

        self.page.on("response", on_response)
        try:
            # v3.8.8 — sob carga (booking+events em paralelo) o RPC chega atrasado.
            # Rounds com 20/25/25/30s; 4ª tentativa é o desempate sob contenção.
            attempts = 0
            waits = (20, 25, 25, 30)
            for target in (url, None, None, None):
                if captured:
                    break
                attempts += 1
                try:
                    if target is None:
                        self.page.reload(wait_until="commit", timeout=60000)
                    else:
                        self.page.goto(target, wait_until="commit", timeout=60000)
                except Exception:
                    pass

                if not self.consent_checked:
                    try:
                        consent = self.page.get_by_role(
                            "button",
                            name=re.compile(r"Aceitar tudo|Accept all|Concordo", re.I),
                        )
                        if consent.count() and consent.first.is_visible(timeout=250):
                            consent.first.click(timeout=500)
                    except Exception:
                        pass
                    self.consent_checked = True

                deadline = time.monotonic() + waits[attempts - 1]
                while time.monotonic() < deadline and not captured:
                    self.page.wait_for_timeout(10)

            if not captured:
                raise RuntimeError(
                    f"GetShoppingResults não capturado após {attempts} tentativas "
                    f"(~100s). diag: rpc_seen={diag['rpc_seen']} "
                    f"no_price_bodies={diag['no_price_bodies']}"
                )

            prices = captured["prices"]
            return {
                "price": min(prices),
                "prices": prices,
                "price_count": len(prices),
                "top5_prices": sorted(prices)[:5],
                "url": url,
                "rpc_seconds": round(captured["rpc_seconds"], 3),
                "total_seconds": round(time.monotonic() - t0, 3),
                "response_chars": captured["response_chars"],
                "status": captured["status"],
                "rpc_seen": diag["rpc_seen"],
                "no_price_bodies": diag["no_price_bodies"],
                "source": "google_flights_rpc",
            }
        finally:
            self.page.remove_listener("response", on_response)


def _get_session(headless: bool = True):
    global _FAST_SESSION
    reused = False

    if _FAST_SESSION is not None and _FAST_SESSION.alive():
        reused = True
    else:
        if _FAST_SESSION is not None:
            try:
                _FAST_SESSION.close()
            except Exception:
                pass
        _FAST_SESSION = GoogleFlightsFastSession(headless=headless)

    return _FAST_SESSION, reused


def close_fast_session():
    global _FAST_SESSION
    if _FAST_SESSION is not None:
        try:
            _FAST_SESSION.close()
        finally:
            _FAST_SESSION = None


def run_fast_search(origem: str, destino: str, data: str, *, headless: bool = True) -> dict:
    session, reused = _get_session(headless=headless)
    result = session.search(origem, destino, data)
    result["session_reused"] = reused
    return result
