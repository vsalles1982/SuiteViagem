#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import queue
import subprocess
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent
OUTDIR = ROOT / "resultados_paralelo"
BASE_SHOTGUN = "https://shotgun.live"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
ALIASES = {
    "lisboa": "lisbon", "londres": "london", "roma": "rome",
    "milao": "milan", "munique": "munich", "viena": "vienna",
    "nova york": "new-york", "nova iorque": "new-york",
    "cidade do mexico": "mexico-city",
}


class ProcessWorker:
    def __init__(self, module):
        self.module = module
        self.q = queue.Queue()
        # v3.8.4 — isola TMPDIR por worker (evita encher /tmp com scoped_dir do Chrome)
        import os as _os
        _tmpdir = _os.path.expanduser(f"~/.cache/suiteviagem/tmp_{module}")
        _os.makedirs(_tmpdir, exist_ok=True)
        _env = _os.environ.copy()
        _env["TMPDIR"] = _tmpdir

        self.p = subprocess.Popen(
            [sys.executable, str(HERE / "module_worker_v3.py"), module],
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=_env,
        )
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

    def _reader(self):
        for raw in self.p.stdout:
            raw = raw.rstrip()
            if raw.startswith(("READY:", "WARM:", "DONE:")):
                prefix, payload = raw.split(":", 1)
                try:
                    self.q.put((prefix, json.loads(payload)))
                except Exception:
                    print(f"[{self.module}] {raw}", flush=True)
            else:
                print(f"[{self.module}] {raw}", flush=True)

    def send(self, obj):
        self.p.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.p.stdin.flush()

    def wait(self, wanted, timeout):
        end = time.monotonic() + timeout
        stash = []
        while time.monotonic() < end:
            try:
                item = self.q.get(timeout=min(0.25, max(0.01, end-time.monotonic())))
            except queue.Empty:
                continue
            if item[0] == wanted:
                for x in stash:
                    self.q.put(x)
                return item[1]
            stash.append(item)
        for x in stash:
            self.q.put(x)
        raise TimeoutError(f"{self.module}: timeout aguardando {wanted}")

    def close(self):
        try:
            if self.p.poll() is None:
                self.send({"op": "quit"})
                self.p.wait(timeout=8)
        except Exception:
            try:
                self.p.kill()
            except Exception:
                pass


def slugify(texto):
    t = texto.strip().lower()
    if t in ALIASES:
        return ALIASES[t]
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")
    return "-".join(t.split())


def shotgun_links(html):
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "/events/" not in href:
            continue
        u = urljoin(BASE_SHOTGUN, href)
        if u not in seen:
            seen.add(u); out.append(u)
    return out


def music_event(html):
    soup = BeautifulSoup(html, "html.parser")
    for block in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            obj = json.loads(block.string or block.get_text())
        except Exception:
            continue
        for item in (obj if isinstance(obj, list) else [obj]):
            if isinstance(item, dict) and item.get("@type") == "MusicEvent":
                return item
    return None


def event_detail(url):
    s = requests.Session()
    s.headers.update(HEADERS)
    r = s.get(url, timeout=20)
    r.raise_for_status()
    ev = music_event(r.text)
    if isinstance(ev, dict) and not ev.get("url"):
        ev["url"] = url
    return ev


def _event_date(ev):
    raw = ev.get("startDate")
    if not raw:
        return None
    try:
        # Preserve the calendar day encoded by Shotgun whenever an offset is
        # present. This avoids moving a late-night event to the next/previous
        # day just because of UTC conversion.
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except Exception:
        return None


def _event_price(ev):
    offers = ev.get("offers", [])
    if isinstance(offers, dict):
        offers = [offers]
    prices = []
    for offer in offers or []:
        if not isinstance(offer, dict):
            continue
        value = offer.get("price")
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            prices.append(value)
    return min(prices) if prices else None


def _event_venue(ev):
    loc = ev.get("location", {})
    if not isinstance(loc, dict):
        return None
    return loc.get("name") or (
        loc.get("address", {}).get("streetAddress")
        if isinstance(loc.get("address"), dict) else None
    )


def _compact_event(ev):
    return {
        "name": ev.get("name") or "Evento",
        "startDate": ev.get("startDate"),
        "date": ev.get("startDate"),
        "venue": _event_venue(ev),
        "price": _event_price(ev),
        "url": ev.get("url"),
    }


def _city_page_links(session, base_url, page_number):
    url = base_url if page_number == 1 else f"{base_url}?page={page_number}"
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return shotgun_links(r.text)


def run_events(city, start, end, limit):
    """Fast Shotgun collector with bounded intelligent pagination.

    Pages are consumed in small batches. Event detail pages inside each batch
    are fetched in parallel. We stop as soon as enough events in the requested
    interval have been confirmed, or when Shotgun stops yielding new links.
    """
    t0 = time.monotonic()
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    limit = max(1, int(limit))

    session = requests.Session()
    session.headers.update(HEADERS)
    base_url = f"{BASE_SHOTGUN}/en/cities/{slugify(city)}"

    seen_links = set()
    found_by_url = {}
    pages_scanned = 0
    MAX_PAGES = 15
    PAGE_BATCH = 3

    for batch_start in range(1, MAX_PAGES + 1, PAGE_BATCH):
        page_numbers = list(range(batch_start, min(MAX_PAGES + 1, batch_start + PAGE_BATCH)))

        page_links = {}
        with ThreadPoolExecutor(max_workers=len(page_numbers)) as page_pool:
            futs = {
                page_pool.submit(_city_page_links, session, base_url, p): p
                for p in page_numbers
            }
            for fut in as_completed(futs):
                p = futs[fut]
                pages_scanned = max(pages_scanned, p)
                try:
                    page_links[p] = fut.result()
                except Exception:
                    page_links[p] = []

        new_links = []
        for p in sorted(page_links):
            for url in page_links[p]:
                if url not in seen_links:
                    seen_links.add(url)
                    new_links.append(url)

        # No new cards in an entire batch means pagination is exhausted.
        if not new_links:
            break

        with ThreadPoolExecutor(max_workers=min(8, len(new_links))) as detail_pool:
            futs = {detail_pool.submit(event_detail, u): u for u in new_links}
            for fut in as_completed(futs):
                url = futs[fut]
                try:
                    ev = fut.result()
                except Exception:
                    continue
                if not ev:
                    continue
                event_day = _event_date(ev)
                if event_day is None or not (d0 <= event_day <= d1):
                    continue
                compact = _compact_event(ev)
                compact["url"] = compact.get("url") or url
                found_by_url[compact["url"]] = compact

        # City pages are chronological in normal Shotgun navigation. Once we
        # have enough confirmed events for the requested window, don't keep
        # walking the agenda just to inflate latency.
        if len(found_by_url) >= limit:
            break

    found = list(found_by_url.values())
    found.sort(key=lambda x: (x.get("startDate") or "", x.get("name") or ""))
    selected = found[:limit]

    return {
        "module": "events",
        "ok": True,
        "seconds": round(time.monotonic() - t0, 3),
        "count": len(selected),
        "results": selected,
        "pages_scanned": pages_scanned,
        "links_seen": len(seen_links),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flight-origin", default="RIO")
    ap.add_argument("--flight-dest", default="SAO")
    ap.add_argument("--hotel-city", default="Petrópolis")
    ap.add_argument("--car-location",
                    default="Sao Paulo Guarulhos Airport (GRU), Sao Paulo, Brazil")
    ap.add_argument("--event-city", default="São Paulo")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    print("="*72)
    print(" SUITEVIAGEM — PARALLEL ARENA v3.7 EARLY RELEASE")
    print(" Cada engine vive e consulta no MESMO processo/thread de origem")
    print("="*72)

    workers = {}
    try:
        print("\n=== SUBINDO WORKERS PERSISTENTES (ESCALONADO) ===", flush=True)
        # Startup é fora da latência do usuário. Sobe um por vez para evitar
        # três navegadores disputando CPU/RAM exatamente na inicialização.
        for name in ("flights", "cars", "hotels"):
            workers[name] = ProcessWorker(name)
            try:
                ready = workers[name].wait("READY", timeout=120)
                print(f"{name.upper()} READY: {ready}", flush=True)
            except Exception as exc:
                print(f"{name.upper()} READY falhou: {exc}", flush=True)

        print("\n=== WARMUP FORA DO CRONÔMETRO (SEQUENCIAL) ===", flush=True)
        warm_commands = (
            ("flights", {"op":"warm","origin":args.flight_origin,
                         "dest":args.flight_dest,"start":args.start}),
            ("cars", {"op":"warm"}),
            ("hotels", {"op":"warm","city":args.hotel_city,
                        "start":args.start,"end":args.end}),
        )
        for name, cmd in warm_commands:
            try:
                workers[name].send(cmd)
                r = workers[name].wait("WARM", timeout=120)
                print(f"{name.upper()} WARM: {r}", flush=True)
            except Exception as exc:
                print(f"{name.upper()} WARM timeout/falha: {exc}", flush=True)

        # Em produção, warmup acontece antes da consulta real. O Booking pode
        # continuar com rede/JS por instantes após devolver WARM. Damos um curto
        # período de assentamento fora do cronômetro do usuário.
        print("\n=== SETTLE 3s FORA DO CRONÔMETRO ===", flush=True)
        time.sleep(3.0)

        print("\n>>> BUSCA DO USUÁRIO DISPARADA <<<", flush=True)
        t0 = time.monotonic()

        def wait_remote(name):
            try:
                return workers[name].wait("DONE", timeout=120)
            except Exception as exc:
                return {"module": name, "ok": False,
                        "seconds": round(time.monotonic()-t0, 3),
                        "error": str(exc)}

        executor = ThreadPoolExecutor(max_workers=4)

        # FASE A: Flights absolutamente sozinho em atividade.
        # Cars e Booking ficam apenas residentes/ociosos; Events também espera.
        workers["flights"].send({"op":"search","origin":args.flight_origin,
                                 "dest":args.flight_dest,"start":args.start})
        print("  0.00s  → FLIGHTS sozinho em atividade", flush=True)
        flights_future = executor.submit(wait_remote, "flights")

        flight_result = None
        gate_reason = None
        try:
            flight_result = flights_future.result(timeout=9.0)
            gate_reason = "flights_done"
            print(f"{time.monotonic()-t0:6.2f}s  → FLIGHTS liberou FASE B", flush=True)
        except Exception:
            gate_reason = "gate_timeout_9s"
            print(f"{time.monotonic()-t0:6.2f}s  → FASE B liberada por timeout de 9s", flush=True)

        # FASE B: depois da janela crítica do RPC, entra o restante.
        def _events_later(city, start, end, limit):
            time.sleep(20)
            return run_events(city, start, end, limit)
        events_future = executor.submit(
            _events_later, args.event_city, args.start, args.end, args.limit
        )
        print(f"{time.monotonic()-t0:6.2f}s  → EVENTS disparado", flush=True)

        workers["cars"].send({"op":"search","location":args.car_location,
                              "start":args.start,"end":args.end,"limit":args.limit})
        cars_future = executor.submit(wait_remote, "cars")
        print(f"{time.monotonic()-t0:6.2f}s  → CARS disparado", flush=True)

        time.sleep(0.20)
        workers["hotels"].send({"op":"search","city":args.hotel_city,
                                "start":args.start,"end":args.end})
        hotels_future = executor.submit(wait_remote, "hotels")
        print(f"{time.monotonic()-t0:6.2f}s  → HOTELS disparado", flush=True)

        futmap = {
            flights_future: "flights",
            events_future: "events",
            cars_future: "cars",
            hotels_future: "hotels",
        }

        results = {}
        if flight_result is not None:
            results["flights"] = flight_result
            mark = "✓" if flight_result.get("ok") else "✗"
            detail = (
                f" | mínimo R$ {flight_result.get('price')}"
                if flight_result.get("ok")
                else f" | {flight_result.get('error')}"
            )
            print(f"{time.monotonic()-t0:6.2f}s  {mark} FLIGHTS {detail}", flush=True)

        try:
            for fut in as_completed(futmap):
                name = futmap[fut]
                if name in results:
                    continue
                try:
                    r = fut.result()
                except Exception as exc:
                    r = {"module": name, "ok": False,
                         "seconds": round(time.monotonic()-t0, 3),
                         "error": f"{type(exc).__name__}: {exc}"}
                results[name] = r
                wall = time.monotonic()-t0
                mark = "✓" if r.get("ok") else "✗"
                if name == "flights" and r.get("ok"):
                    detail = f" | mínimo R$ {r.get('price')}"
                elif r.get("ok"):
                    detail = f" | {r.get('count', 0)} resultado(s)"
                else:
                    detail = f" | {r.get('error')}"
                print(f"{wall:6.2f}s  {mark} {name.upper():8s}{detail}", flush=True)
        finally:
            executor.shutdown(wait=False, cancel_futures=False)

        total = round(time.monotonic()-t0, 3)
        print(f"\nLATÊNCIA PERCEBIDA TOTAL: {total:.3f}s", flush=True)

        payload = {
            "variant": "suiteviagem-parallel-arena-v3.7-early-release",
            "requested": vars(args),
            "user_query_wall_seconds": total,
            "heavy_gate_reason": gate_reason,
            "results": results,
        }
        OUTDIR.mkdir(exist_ok=True)
        out = OUTDIR / ("parallel_arena_v3_" +
                        datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json")
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                       encoding="utf-8")
        print(f"ARENA_SALVA: {out}", flush=True)

    finally:
        for w in workers.values():
            w.close()


if __name__ == "__main__":
    main()
