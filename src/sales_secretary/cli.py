"""CLI : serve | poll | status."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path

import uvicorn

from sales_secretary.poller import poll_once
from sales_secretary.tenant import load_tenant, public_tenant


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sales-secretary")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="API + poller en arrière-plan")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=int(os.environ.get("SECRETARY_PORT", "8080")))

    sub.add_parser("poll", help="un cycle d'ingest")
    sub.add_parser("status", help="état tenant + ledger")

    args = parser.parse_args(argv)
    data = Path(os.environ.get("SECRETARY_DATA", "/data"))

    if args.cmd == "status":
        print(json.dumps(public_tenant(load_tenant(data)), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "poll":
        print(json.dumps(poll_once(data), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "serve":
        _start_poller_thread(data)
        uvicorn.run(
            "sales_secretary.api:app",
            host=args.host,
            port=args.port,
            log_level="info",
        )
        return 0
    return 1


def _start_poller_thread(data: Path) -> None:
    def loop() -> None:
        while True:
            tenant = load_tenant(data)
            interval = tenant.poll.interval_seconds if tenant else 180
            if tenant and tenant.configured():
                try:
                    poll_once(data, tenant)
                except Exception:
                    pass
            time.sleep(max(30, interval))

    thread = threading.Thread(target=loop, name="poller", daemon=True)
    thread.start()


if __name__ == "__main__":
    raise SystemExit(main())
