#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path.cwd()
for p in (ROOT, ROOT / "booking-hotel-scraper", ROOT / "passagens" / "google-flights"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)


def emit(prefix, payload):
    print(prefix + json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def car_details(rows):
    import math

    def value(row, *keys):
        return next((row[k] for k in keys if row.get(k) not in (None, "")), None)

    results = []
    for row in (rows or [])[:30]:
        if not isinstance(row, dict):
            continue
        raw_price = row.get("TotalBRL")
        try:
            price = float(raw_price) if raw_price is not None else None
        except (TypeError, ValueError, OverflowError):
            price = None
        if price is not None and (not math.isfinite(price) or price < 0):
            price = None
        results.append({
            "name": value(row, "Carro", "CarName", "Car", "Name", "name", "Modelo", "model"),
            "supplier": value(row, "Fornecedor", "Supplier", "supplier", "Locadora", "RentalCompany"),
            "price": price,
            "currency": "BRL",
            "url": value(row, "URL", "Url", "url", "Link", "link", "OfferURL", "BookingURL"),
        })
    return results


def flights_worker():
    from google_flights_fastpath import run_fast_search, close_fast_session
    emit("READY:", {"module": "flights"})
    try:
        for line in sys.stdin:
            cmd = json.loads(line)
            if cmd.get("op") == "quit":
                break
            if cmd.get("op") == "warm":
                t = time.monotonic()
                try:
                    r = run_fast_search(cmd["origin"], cmd["dest"], cmd["start"], headless=True)
                    emit("WARM:", {"module": "flights", "ok": True,
                                   "seconds": round(time.monotonic()-t, 3),
                                   "price": r.get("price")})
                except Exception as exc:
                    emit("WARM:", {"module": "flights", "ok": False,
                                   "seconds": round(time.monotonic()-t, 3),
                                   "error": f"{type(exc).__name__}: {exc}"})
            if cmd.get("op") == "search":
                t = time.monotonic()
                try:
                    r = run_fast_search(cmd["origin"], cmd["dest"], cmd["start"], headless=True)
                    emit("DONE:", {"module": "flights", "ok": True,
                                   "seconds": round(time.monotonic()-t, 3),
"price": r.get("price"),
                                    "price_count": r.get("price_count"),
                                    "top_prices": r.get("top5_prices") or [],
                                    "session_reused": r.get("session_reused")})
                except Exception as exc:
                    emit("DONE:", {"module": "flights", "ok": False,
                                   "seconds": round(time.monotonic()-t, 3),
                                   "error": f"{type(exc).__name__}: {exc}"})
    finally:
        try:
            close_fast_session()
        except Exception:
            pass


def hotels_worker():
    import hotels_booking
    emit("READY:", {"module": "hotels"})
    try:
        for line in sys.stdin:
            cmd = json.loads(line)
            if cmd.get("op") == "quit":
                break
            if cmd.get("op") in {"warm", "search"}:
                t = time.monotonic()
                prefix = "WARM:" if cmd["op"] == "warm" else "DONE:"
                try:
                    r = hotels_booking.run_fast_search(
                        cmd["city"], cmd["start"], cmd["end"], headless=False
                    )
                    records = r.get("records", [])
                    top = []
                    for row in records[:5]:
                        top.append({
                            "name": row.get("Hotel Name"),
                            "price": row.get("Price"),
                            "total": row.get("Total Displayed (BRL)") or row.get("Price"),
                            "currency": row.get("Currency", "BRL"),
                            "url": row.get("Hotel URL"),
                        })
                    confirmed = [
                        x.get("total") for x in top
                        if isinstance(x.get("total"), (int, float)) and x.get("total") > 0
                    ]
                    emit(prefix, {"module": "hotels", "ok": True,
                                  "seconds": round(time.monotonic()-t, 3),
                                  "count": len(records),
                                  "best_price": min(confirmed) if confirmed else None,
"top": top,
                                    "results": [{
                                        "name": row.get("Hotel Name"),
                                        "price": row.get("Price"),
                                        "total": row.get("Total Displayed (BRL)") or row.get("Price"),
                                        "currency": row.get("Currency", "BRL"),
                                        "url": row.get("Hotel URL"),
                                        "stars": row.get("Stars", row.get("Star Rating")),
                                    } for row in records[:30]] if cmd["op"] == "search" else [],
                                    "timings": r.get("timings")})
                except Exception as exc:
                    emit(prefix, {"module": "hotels", "ok": False,
                                  "seconds": round(time.monotonic()-t, 3),
                                  "error": f"{type(exc).__name__}: {exc}"})
    finally:
        try:
            if hasattr(hotels_booking, "close_fast_booking_drivers"):
                hotels_booking.close_fast_booking_drivers()
        except Exception:
            pass


def cars_worker():
    from suiteviagem.cars_worker_v20g import WarmCarsWorkerV20G
    db = ROOT / "data" / "parallel_arena_v3.sqlite3"
    db.parent.mkdir(parents=True, exist_ok=True)
    engine = WarmCarsWorkerV20G(str(db))

    t = time.monotonic()
    try:
        engine.new_driver()
        emit("READY:", {"module": "cars", "ok": True,
                        "boot_seconds": round(time.monotonic()-t, 3)})
    except Exception as exc:
        emit("READY:", {"module": "cars", "ok": False,
                        "boot_seconds": round(time.monotonic()-t, 3),
                        "error": f"{type(exc).__name__}: {exc}"})

    try:
        for line in sys.stdin:
            cmd = json.loads(line)
            if cmd.get("op") == "quit":
                break
            if cmd.get("op") == "warm":
                # new_driver() já aqueceu a origem; /search/ é consultado via API.
                emit("WARM:", {"module": "cars", "ok": True, "seconds": 0.0})
            if cmd.get("op") == "search":
                t = time.monotonic()
                logs = []

                def _driver_alive():
                    try:
                        _ = engine.driver.current_url
                        return True
                    except Exception:
                        return False

                def _is_dead_driver(exc):
                    name = type(exc).__name__
                    msg = str(exc).lower()
                    return ("NoSuchWindow" in name
                            or "WebDriver" in name
                            or "invalid session" in msg
                            or ("not found" in msg and "web view" in msg))

                def _rebuild():
                    try:
                        engine.close()
                    except Exception:
                        pass
                    engine.new_driver()

                try:
                    # Mesmo com um driver morto no boot, a busca sempre precisa emitir DONE:.
                    if not _driver_alive():
                        emit("CAR_LOG:", {"message": "driver indisponível; recriando antes do search"})
                        _rebuild()

                    try:
                        r = engine.coletar_ofertas_direct(
                            cmd["location"], cmd["start"], cmd["end"], int(cmd["limit"]),
                            log=lambda m: logs.append(str(m)),
                        )
                    except Exception as first_exc:
                        if not _is_dead_driver(first_exc):
                            raise
                        emit("CAR_LOG:", {"message": f"driver caiu no search ({type(first_exc).__name__}); recriando"})
                        _rebuild()
                        logs.clear()
                        r = engine.coletar_ofertas_direct(
                            cmd["location"], cmd["start"], cmd["end"], int(cmd["limit"]),
                            log=lambda m: logs.append(str(m)),
                        )
                    import re
                    top = []
                    for line in logs:
                        m = re.match(r"(.+?)\s*\|\s*(.+?)\s*\|\s*R\$\s*([0-9.]+(?:,[0-9]{2})?)\s*$", line)
                        if not m:
                            continue
                        price = float(m.group(3).replace(".", "").replace(",", "."))
                        top.append({"name": m.group(1).strip(),
                                    "supplier": m.group(2).strip(),
                                    "price": price,
                                    "currency": "BRL"})
                        if len(top) >= int(cmd["limit"]):
                            break
                    emit("DONE:", {"module": "cars", "ok": True,
                                   "seconds": round(time.monotonic()-t, 3),
                                   "count": len(r.get("resultados", [])),
                                   "best_price": top[0]["price"] if top else None,
                                   "top": top,
                                   "results": car_details(r.get("resultados")),
                                   "timings": r.get("timings"),
                                   "logs_tail": logs[-5:]})
                except Exception as exc:
                    emit("DONE:", {"module": "cars", "ok": False,
                                   "seconds": round(time.monotonic()-t, 3),
                                   "error": f"{type(exc).__name__}: {exc}",
                                   "logs_tail": logs[-5:]})
    finally:
        try:
            engine.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("module", choices=["flights", "hotels", "cars"])
    args = ap.parse_args()
    {"flights": flights_worker, "hotels": hotels_worker, "cars": cars_worker}[args.module]()


if __name__ == "__main__":
    main()
