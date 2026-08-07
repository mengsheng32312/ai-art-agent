"""系统 DNS 解析失败时，用公共 DNS 兜底解析域名。"""

import socket
import struct
import urllib.parse

import httpx

PUBLIC_DNS_SERVERS: tuple[str, ...] = (
    "223.5.5.5",
    "119.29.29.29",
    "8.8.8.8",
    "1.1.1.1",
)

_original_getaddrinfo = socket.getaddrinfo


def _encode_qname(host: str) -> bytes:
    return (
        b"".join(
            bytes([len(label)]) + label.encode("ascii", "ignore")
            for label in host.rstrip(".").split(".")
        )
        + b"\x00"
    )


def _skip_name(data: bytes, offset: int) -> int:
    while True:
        if offset >= len(data):
            return offset
        length = data[offset]
        if length & 0xC0 == 0xC0:
            return offset + 2
        if length == 0:
            return offset + 1
        offset += length + 1


def _parse_a_answers(data: bytes) -> list[str]:
    if len(data) < 12:
        return []
    answer_count = struct.unpack(">H", data[6:8])[0]
    offset = _skip_name(data, 12) + 4
    ips: list[str] = []
    for _ in range(answer_count):
        offset = _skip_name(data, offset)
        if offset + 10 > len(data):
            break
        rtype, _rclass, _ttl, rdlength = struct.unpack(
            ">HHIH", data[offset : offset + 10]
        )
        offset += 10
        if offset + rdlength > len(data):
            break
        if rtype == 1 and rdlength == 4:
            ips.append(socket.inet_ntoa(data[offset : offset + 4]))
        offset += rdlength
    return ips


def query_a(
    host: str,
    servers: tuple[str, ...] = PUBLIC_DNS_SERVERS,
    timeout: float = 3.0,
) -> list[str]:
    qname = _encode_qname(host)
    query = (
        struct.pack(">HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
        + qname
        + struct.pack(">HH", 1, 1)
    )
    for server in servers:
        ips = _query_udp(server, query, timeout)
        if not ips:
            ips = _query_tcp(server, query, timeout)
        if ips:
            return ips
    for endpoint in ("https://8.8.8.8/resolve", "https://1.1.1.1/dns-query"):
        ips = _query_doh(endpoint, host, timeout)
        if ips:
            return ips
    return []


def _query_udp(server: str, query: bytes, timeout: float) -> list[str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(query, (server, 53))
            data, _ = sock.recvfrom(4096)
        return _parse_a_answers(data)
    except OSError:
        return []


def _query_tcp(server: str, query: bytes, timeout: float) -> list[str]:
    try:
        with socket.create_connection((server, 53), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(struct.pack(">H", len(query)) + query)
            length = struct.unpack(">H", sock.recv(2))[0]
            data = b""
            while len(data) < length:
                chunk = sock.recv(length - len(data))
                if not chunk:
                    break
                data += chunk
        return _parse_a_answers(data)
    except OSError:
        return []


def _query_doh(endpoint: str, host: str, timeout: float) -> list[str]:
    url = f"{endpoint}?name={urllib.parse.quote(host)}&type=A"
    headers = {"Accept": "application/dns-json"}
    try:
        with httpx.Client(trust_env=False, timeout=timeout) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
        return [
            str(answer["data"])
            for answer in payload.get("Answer", [])
            if int(answer.get("type", -1)) == 1
        ]
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return []


def _fallback_getaddrinfo(
    host: str | None,
    port: int | str,
    family: int = 0,
    type: int = 0,
    proto: int = 0,
    flags: int = 0,
):
    try:
        return _original_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror:
        if not isinstance(host, str) or not host or family not in (0, socket.AF_INET):
            raise
        ips = query_a(host)
        if not ips:
            raise socket.gaierror(
                11001,
                "系统 DNS 解析失败，公共 DNS 兜底也未成功："
                "请检查网络连接、代理或防火墙设置后重试",
            ) from None
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, int(port)))
            for ip in ips
        ]


def install_fallback_resolver() -> None:
    """替换全局 getaddrinfo：系统 DNS 失败时回退到公共 DNS，避免域名解析失败。"""
    if socket.getaddrinfo is not _fallback_getaddrinfo:
        socket.getaddrinfo = _fallback_getaddrinfo  # type: ignore[assignment]
