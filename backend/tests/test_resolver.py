import socket
import struct

import httpx
import pytest

from app.comfy import resolver


def _build_dns_response(ips: list[str]) -> bytes:
    qname = b"\x07example\x03com\x00"
    header = struct.pack(">HHHHHH", 0x1234, 0x8180, 1, len(ips), 0, 0)
    question = qname + struct.pack(">HH", 1, 1)
    answers = b"".join(
        b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 60, 4) + socket.inet_aton(ip)
        for ip in ips
    )
    return header + question + answers


def test_parse_a_answers() -> None:
    assert resolver._parse_a_answers(_build_dns_response(["1.2.3.4", "5.6.7.8"])) == [
        "1.2.3.4",
        "5.6.7.8",
    ]
    assert resolver._parse_a_answers(b"short") == []


class _FakeSocket:
    def __init__(self, response: bytes) -> None:
        self.response = response

    def __enter__(self) -> "_FakeSocket":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def sendto(self, data: bytes, addr) -> None:
        self.sent = (data, addr)

    def recvfrom(self, size: int) -> tuple[bytes, tuple[str, int]]:
        return self.response, ("223.5.5.5", 53)

    def close(self) -> None:
        pass


class _FakeTcpSocket:
    def __init__(self, response: bytes) -> None:
        self.length = struct.pack(">H", len(response))
        self.response = response
        self.calls = 0

    def __enter__(self) -> "_FakeTcpSocket":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def settimeout(self, timeout: float) -> None:
        pass

    def sendall(self, data: bytes) -> None:
        self.sent = data

    def recv(self, size: int) -> bytes:
        if self.calls == 0:
            self.calls += 1
            return self.length
        return self.response

    def close(self) -> None:
        pass


def test_query_a_uses_public_dns(monkeypatch) -> None:
    response = _build_dns_response(["104.16.230.132"])
    monkeypatch.setattr(
        socket, "socket", lambda family, type_: _FakeSocket(response)
    )

    ips = resolver.query_a("example.com", servers=("223.5.5.5",))

    assert ips == ["104.16.230.132"]


def test_query_a_uses_tcp_after_udp_failure(monkeypatch) -> None:
    response = _build_dns_response(["1.2.3.4"])
    monkeypatch.setattr(
        socket, "socket", lambda family, type_: _FakeSocket(b"\x00" * 12)
    )
    monkeypatch.setattr(
        socket, "create_connection", lambda *args, **kwargs: _FakeTcpSocket(response)
    )

    ips = resolver.query_a("example.com", servers=("223.5.5.5",))

    assert ips == ["1.2.3.4"]


def test_query_a_uses_doh_after_udp_and_tcp_failure(monkeypatch) -> None:
    payload = {"Answer": [{"name": "example.com", "type": 1, "data": "9.9.9.9"}]}

    class _FakeDohClient:
        def __init__(self, **kwargs) -> None:
            pass

        def __enter__(self) -> "_FakeDohClient":
            return self

        def __exit__(self, *args) -> None:
            pass

        def get(self, url: str, headers: dict) -> "_FakeResponse":
            return _FakeResponse(payload)

    class _FakeResponse:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return self.payload

    monkeypatch.setattr(
        socket, "socket", lambda family, type_: _FakeSocket(b"\x00" * 12)
    )

    def dead_connection(*args, **kwargs):
        raise OSError("tcp blocked")

    monkeypatch.setattr(socket, "create_connection", dead_connection)
    monkeypatch.setattr(httpx, "Client", _FakeDohClient)

    ips = resolver.query_a("example.com", servers=("223.5.5.5",))

    assert ips == ["9.9.9.9"]


def test_fallback_getaddrinfo_after_system_dns_failure(monkeypatch) -> None:
    def boom(host, port, *args, **kwargs):
        raise socket.gaierror(11001, "getaddrinfo failed")

    monkeypatch.setattr(resolver, "_original_getaddrinfo", boom)
    monkeypatch.setattr(resolver, "query_a", lambda host: ["104.16.230.132"])
    original = socket.getaddrinfo
    resolver.install_fallback_resolver()
    try:
        results = socket.getaddrinfo("x.trycloudflare.com", 443)
        assert ("104.16.230.132", 443) in {item[4] for item in results}
    finally:
        socket.getaddrinfo = original


def test_fallback_getaddrinfo_reports_clear_error_when_all_fail(
    monkeypatch,
) -> None:
    resolver.clear_cache()

    def boom(host, port, *args, **kwargs):
        raise socket.gaierror(11001, "getaddrinfo failed")

    monkeypatch.setattr(resolver, "_original_getaddrinfo", boom)
    monkeypatch.setattr(resolver, "query_a", lambda host: [])
    original = socket.getaddrinfo
    resolver.install_fallback_resolver()
    try:
        with pytest.raises(socket.gaierror) as excinfo:
            socket.getaddrinfo("never-resolved.example", 443)
        assert "系统 DNS 解析失败" in str(excinfo.value)
    finally:
        socket.getaddrinfo = original
        resolver.clear_cache()


def test_fallback_getaddrinfo_passes_through_when_dns_works(monkeypatch) -> None:
    called: list[tuple] = []

    def real(host, port, *args, **kwargs):
        called.append((host, port))
        return [("fake-result",)]

    monkeypatch.setattr(resolver, "_original_getaddrinfo", real)
    original = socket.getaddrinfo
    resolver.install_fallback_resolver()
    try:
        assert socket.getaddrinfo("example.com", 443) == [("fake-result",)]
    finally:
        socket.getaddrinfo = original


def test_successful_resolution_is_cached(monkeypatch) -> None:
    resolver.clear_cache()
    calls = {"count": 0}

    def real(host, port, *args, **kwargs):
        calls["count"] += 1
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("104.16.1.1", port))]

    def boom(host, port, *args, **kwargs):
        raise socket.gaierror(11001, "getaddrinfo failed")

    monkeypatch.setattr(resolver, "_original_getaddrinfo", real)
    original = socket.getaddrinfo
    resolver.install_fallback_resolver()
    try:
        assert socket.getaddrinfo("x.trycloudflare.com", 443)[0][4][0] == "104.16.1.1"
        monkeypatch.setattr(resolver, "_original_getaddrinfo", boom)
        assert socket.getaddrinfo("x.trycloudflare.com", 443)[0][4][0] == "104.16.1.1"
        assert calls["count"] == 1
    finally:
        socket.getaddrinfo = original
        resolver.clear_cache()


def test_cache_skips_public_dns_after_successful_fallback(monkeypatch) -> None:
    resolver.clear_cache()
    original = socket.getaddrinfo
    resolver.install_fallback_resolver()
    queries = {"count": 0}

    def boom(host, port, *args, **kwargs):
        raise socket.gaierror(11001, "getaddrinfo failed")

    def fake_query(host: str) -> list[str]:
        queries["count"] += 1
        return ["104.16.2.2"]

    monkeypatch.setattr(resolver, "_original_getaddrinfo", boom)
    monkeypatch.setattr(resolver, "query_a", fake_query)
    try:
        assert socket.getaddrinfo("x.trycloudflare.com", 443)[0][4][0] == "104.16.2.2"
        assert socket.getaddrinfo("x.trycloudflare.com", 443)[0][4][0] == "104.16.2.2"
        assert queries["count"] == 1
    finally:
        socket.getaddrinfo = original
        resolver.clear_cache()
