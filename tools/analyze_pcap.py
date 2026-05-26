#!/usr/bin/env python3
"""Quick analyzer for PCAPdroid raw-IP PCAP files.

For decrypted HTTP (peppertoken, Authorization, etc.) export PCAPdroid as text
or use TLS decryption; raw PCAP is usually TLS ciphertext only.
"""

from __future__ import annotations

import socket
import sys
from collections import Counter
from pathlib import Path

import dpkt


def analyze(path: Path) -> None:
    streams: dict[tuple, bytes] = {}
    rst_count = 0
    tls_alert = 0
    packets = 0
    dns_hosts: Counter[str] = Counter()

    with path.open("rb") as f:
        pcap = dpkt.pcap.Reader(f)
        linktype = pcap.datalink()
        for _ts, buf in pcap:
            packets += 1
            if len(buf) < 20 or (buf[0] >> 4) != 4:
                continue
            ihl = (buf[0] & 0xF) * 4
            proto = buf[9]
            src = socket.inet_ntoa(buf[12:16])
            dst = socket.inet_ntoa(buf[16:20])

            if proto == 17 and len(buf) >= ihl + 8:
                udp = dpkt.udp.UDP(buf[ihl:])
                if udp.dport == 53 and udp.data:
                    try:
                        dns = dpkt.dns.DNS(udp.data)
                        if dns.qr == dpkt.dns.DNS_A:
                            for an in dns.an or []:
                                if an.type == 1 and an.name:
                                    name = an.name.decode("ascii", "ignore").rstrip(".")
                                    if "pepper" in name:
                                        dns_hosts[name] += 1
                    except Exception:
                        pass

            if proto != 6:
                continue

            tcp = dpkt.tcp.TCP(buf[ihl:])
            if tcp.flags & dpkt.tcp.TH_RST:
                rst_count += 1
            if not tcp.data:
                continue

            key = (src, tcp.sport, dst, tcp.dport)
            streams[key] = streams.get(key, b"") + tcp.data
            if tcp.data[0:1] == b"\x15":
                tls_alert += 1

    raw = path.read_bytes()
    needles = [
        b"GET /account",
        b"peppertoken",
        b"AWS4-HMAC",
        b"HTTP/1.1",
        b"403 Forbidden",
        b"200 OK",
        b"502",
    ]

    big = sorted(streams.items(), key=lambda kv: len(kv[1]), reverse=True)[:10]

    print(f"=== {path.name} ===")
    print(f"size={path.stat().st_size} packets={packets} linktype={linktype}")
    print(f"tcp_rst_flags={rst_count} tls_alert_chunks={tls_alert}")
    if dns_hosts:
        print("dns:", dict(dns_hosts.most_common(8)))
    print("top streams:")
    for (src, sport, dst, dport), payload in big:
        tags = []
        if payload[:3] == b"\x16\x03":
            tags.append("TLS")
        if payload[:1] == b"\x15":
            tags.append("alert")
        for host in (b"api.pepperos.io", b"prod.move.pepperos.io", b"socket.pepperos.io"):
            if host in payload:
                tags.append(host.decode())
        print(
            f"  {src}:{sport} -> {dst}:{dport}  {len(payload)} bytes"
            + (f"  [{', '.join(tags)}]" if tags else "")
        )
    print("string search:")
    for needle in needles:
        print(f"  {needle!r}: {raw.count(needle)}")
    print()


def main() -> int:
    for arg in sys.argv[1:]:
        analyze(Path(arg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
