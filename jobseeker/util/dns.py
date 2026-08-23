"""A minimal DNS client, enough to ask whether a domain can receive mail.

There is no MX lookup in the standard library, and pulling in a resolver
library for one question would break the project's no dependency rule. This
builds the query packet by hand over UDP, which is about sixty lines and
answers the only question that matters before sending: is there a mail server
at the other end.

Failing open is deliberate. A DNS timeout must not silently stop an
application going out, so an unknown answer is treated as sendable and the
send path logs it.
"""

from __future__ import annotations

import secrets
import socket
import struct
from functools import lru_cache

DEFAULT_RESOLVERS = ("8.8.8.8", "1.1.1.1")
TYPE_MX = 15
TYPE_A = 1


def _encode_name(domain: str) -> bytes:
    parts = [p for p in domain.strip(".").split(".") if p]
    return b"".join(bytes([len(p)]) + p.encode("idna") for p in parts) + b"\x00"


def _query(domain: str, record_type: int, resolver: str, timeout: float) -> int | None:
    """Return the answer count, or None when the lookup could not be made."""
    transaction_id = secrets.randbits(16)
    header = struct.pack(">HHHHHH", transaction_id, 0x0100, 1, 0, 0, 0)
    question = _encode_name(domain) + struct.pack(">HH", record_type, 1)
    packet = header + question

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(packet, (resolver, 53))
            response, _ = sock.recvfrom(2048)
    except (OSError, socket.timeout):
        return None

    if len(response) < 12:
        return None
    reply_id, flags, _, answers, _, _ = struct.unpack(">HHHHHH", response[:12])
    if reply_id != transaction_id:
        return None

    rcode = flags & 0x000F
    if rcode == 3:          # NXDOMAIN: the domain does not exist at all
        return 0
    if rcode != 0:
        return None
    return answers


@lru_cache(maxsize=2048)
def can_receive_mail(domain: str, timeout: float = 3.0) -> bool | None:
    """True if the domain has a mail route, False if it certainly does not,
    None if the question could not be answered."""
    domain = (domain or "").strip().lower().rstrip(".")
    if not domain or "." not in domain:
        return False

    for resolver in DEFAULT_RESOLVERS:
        answers = _query(domain, TYPE_MX, resolver, timeout)
        if answers is None:
            continue
        if answers > 0:
            return True
        # No MX is not conclusive: a domain with an A record still accepts mail
        # at that host under the fallback rule, so that is checked too.
        a_answers = _query(domain, TYPE_A, resolver, timeout)
        if a_answers is None:
            continue
        return a_answers > 0

    return None


def address_deliverable(email: str) -> tuple[bool, str]:
    """Check the domain half of an address. The mailbox itself cannot be tested
    without sending, so this only rules out domains that cannot receive at all."""
    if "@" not in (email or ""):
        return False, "not an email address"
    domain = email.rsplit("@", 1)[1]
    verdict = can_receive_mail(domain)
    if verdict is True:
        return True, ""
    if verdict is False:
        return False, f"{domain} has no mail server, anything sent there will bounce"
    return True, f"could not check DNS for {domain}, sending anyway"
