"""仅本地 HTTPS 演练用途，非生产反向代理。

固定监听/转发到 127.0.0.1，不提供证书信任、限流、流式传输或生产部署能力。
例如：python scripts/local_tls_proxy.py --cert <证书> --key <私钥>
"""

from __future__ import annotations

import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ssl

HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade",
}
MAX_BODY = 32 * 1024 * 1024


class LocalProxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _forward(self):
        allowed_hosts = {
            f"localhost:{self.server.server_port}",
            f"127.0.0.1:{self.server.server_port}",
        }
        if self.headers.get("Host", "").lower() not in allowed_hosts:
            self.send_error(400, "Only localhost / 127.0.0.1 are supported")
            return
        if not self.path.startswith("/") or self.path.startswith("//"):
            self.send_error(400, "Only origin-form paths are supported")
            return
        if self.headers.get("Transfer-Encoding"):
            self.send_error(400, "Chunked requests are not supported in this drill")
            return
        lengths = self.headers.get_all("Content-Length", [])
        try:
            if len(lengths) > 1:
                raise ValueError
            length = int(lengths[0]) if lengths else 0
            if length < 0:
                raise ValueError
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return
        if length > MAX_BODY:
            self.send_error(413, "Request too large for this drill")
            return
        self.connection.settimeout(30)
        upstream = http.client.HTTPConnection(
            "127.0.0.1", self.server.upstream_port, timeout=30,
        )
        try:
            body = self.rfile.read(length) if length else None
            if body is not None and len(body) != length:
                self.send_error(400, "Incomplete request body")
                return
            connection_headers = {
                part.strip().lower()
                for part in self.headers.get("Connection", "").split(",")
            }
            headers = {
                name: value for name, value in self.headers.items()
                if name.lower() not in HOP_HEADERS | connection_headers
            }
            headers["Connection"] = "close"
            upstream.request(self.command, self.path, body=body, headers=headers)
            response = upstream.getresponse()
            payload = response.read()
            self.send_response(response.status, response.reason)
            response_hops = {
                part.strip().lower()
                for part in (response.getheader("Connection") or "").split(",")
            }
            # 用列表逐条转发，不能把多个 Set-Cookie 合成一个逗号分隔值。
            for name, value in response.getheaders():
                if name.lower() not in HOP_HEADERS | response_hops | {"content-length"}:
                    self.send_header(name, value)
            size = response.getheader("Content-Length") if self.command == "HEAD" else len(payload)
            if size is not None:
                self.send_header("Content-Length", str(size))
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)
        except (OSError, http.client.HTTPException):
            self.send_error(502, "Local upstream is unavailable")
        finally:
            upstream.close()
            self.close_connection = True

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = _forward


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--port", type=int, default=5443)
    parser.add_argument("--upstream-port", type=int, default=5330)
    args = parser.parse_args()
    if not all(1 <= port <= 65535 for port in (args.port, args.upstream_port)):
        parser.error("ports must be between 1 and 65535")
    if args.port == args.upstream_port:
        parser.error("TLS and upstream ports must differ")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.cert, args.key)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), LocalProxy)
    server.upstream_port = args.upstream_port
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print(f"Local drill only: https://localhost:{args.port} -> 127.0.0.1:{args.upstream_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
