"""Dual-stack listener: uvicorn on 0.0.0.0 (fly-proxy) + TCP proxy for Fly 6pn IPv6.

fly-proxy requires the app to listen on 0.0.0.0:<port>. The Fly private
network (6pn) is IPv6-only, and 0.0.0.0 does not accept IPv6 connections.
This entrypoint starts uvicorn on 0.0.0.0:8000 and a small asyncio TCP
forwarder :: → 127.0.0.1:8000 so both worlds work.
"""

import asyncio
import os
import subprocess
import sys

API_PORT = int(os.environ.get("PORT", "8000"))


async def forward(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        upstream_reader, upstream_writer = await asyncio.open_connection(
            "127.0.0.1", API_PORT
        )
    except Exception:
        writer.close()
        return

    async def pipe(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
        try:
            while True:
                data = await src.read(65536)
                if not data:
                    break
                dst.write(data)
                await dst.drain()
        except Exception:
            pass
        finally:
            try:
                dst.close()
            except Exception:
                pass

    await asyncio.gather(
        pipe(reader, upstream_writer), pipe(upstream_reader, writer)
    )


async def serve_ipv6() -> None:
    server = await asyncio.start_server(forward, "::", API_PORT)
    print(f"[dualstack] IPv6 forwarder listening on [::]:{API_PORT} -> 127.0.0.1:{API_PORT}", flush=True)
    async with server:
        await server.serve_forever()


def main() -> None:
    loop = asyncio.new_event_loop()
    ipv6_task = loop.create_task(serve_ipv6())
    uvicorn = loop.run_in_executor(
        None,
        lambda: subprocess.call(
            [
                sys.executable, "-m", "uvicorn", "app.main:app",
                "--host", "0.0.0.0", "--port", str(API_PORT),
            ]
        ),
    )
    try:
        loop.run_until_complete(asyncio.gather(ipv6_task, uvicorn))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
