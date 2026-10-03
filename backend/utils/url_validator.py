"""URL validator — sanitizes and validates media URLs with SSRF protection"""
import re
import socket
import ipaddress
from urllib.parse import urlparse
from typing import Set

ALLOWED_SCHEMES = {"http", "https"}

# Private IP ranges (IPv4)
PRIVATE_IPV4_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local
    ipaddress.ip_network("0.0.0.0/8"),  # Reserved
]

# Cloud metadata IPs (AWS, GCP, Azure)
CLOUD_METADATA_IPS = {
    "169.254.169.254",  # AWS, GCP, Azure metadata
    "metadata.google.internal",  # GCP
}

# Private IPv6 ranges
PRIVATE_IPV6_RANGES = [
    ipaddress.ip_network("::1/128"),  # Loopback
    ipaddress.ip_network("fe80::/10"),  # Link-local
    ipaddress.ip_network("fc00::/7"),  # Unique local
    ipaddress.ip_network("fd00::/8"),  # Unique local
]


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is in private/reserved ranges."""
    try:
        ip = ipaddress.ip_address(ip_str)
        
        # Check IPv4 private ranges
        if ip.version == 4:
            for network in PRIVATE_IPV4_RANGES:
                if ip in network:
                    return True
            # Check cloud metadata IPs
            if ip_str in CLOUD_METADATA_IPS:
                return True
        
        # Check IPv6 private ranges
        elif ip.version == 6:
            for network in PRIVATE_IPV6_RANGES:
                if ip in network:
                    return True
            # Check IPv4-mapped IPv6 addresses
            if ip.ipv4_mapped:
                ipv4 = ip.ipv4_mapped
                for network in PRIVATE_IPV4_RANGES:
                    if ipv4 in network:
                        return True
        
        return False
    except ValueError:
        return False


def _resolve_hostname(hostname: str) -> Set[str]:
    """Resolve hostname to all IP addresses."""
    try:
        # Get all addresses (both IPv4 and IPv6)
        addrinfo = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        ips = {info[4][0] for info in addrinfo}
        return ips
    except (socket.gaierror, socket.error):
        return set()


def validate_url(url: str) -> tuple[bool, str]:
    """
    Returns (is_valid, reason)
    
    Performs comprehensive SSRF validation:
    - Checks URL scheme
    - Resolves hostname to all IPs
    - Validates each IP against private/reserved ranges
    - Handles IPv4-mapped IPv6 addresses
    """
    url = url.strip()
    if not url:
        return False, "Empty URL"
    
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Malformed URL"
    
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False, f"Scheme '{parsed.scheme}' not allowed"
    
    if not parsed.netloc:
        return False, "Missing host"

    # Extract hostname from netloc. Use urlparse's own .hostname property
    # rather than a manual netloc.split(":")[0] — the manual split mangles
    # bracketed IPv6 literals (e.g. "[::1]:8080" -> "[") into garbage that
    # fails DNS resolution and gets rejected as "unresolvable" instead of
    # being correctly identified (and blocked, if actually private) as an
    # IPv6 address. .hostname also lowercases and strips brackets for us.
    hostname = parsed.hostname
    if not hostname:
        return False, "Missing host"

    # Block literal localhost
    if hostname.lower() in ("localhost", "localhost.localdomain"):
        return False, "URL targets localhost"
    
    # Check if hostname is a literal IP address
    try:
        ip = ipaddress.ip_address(hostname)
        if _is_private_ip(str(ip)):
            return False, "URL targets a private IP address"
    except ValueError:
        # Not a literal IP, resolve the hostname
        ips = _resolve_hostname(hostname)
        
        if not ips:
            # Could not resolve - this might be a temporary DNS issue
            # For safety, we'll reject it
            return False, "Could not resolve hostname"
        
        # Check all resolved IPs
        for ip in ips:
            if _is_private_ip(ip):
                return False, f"URL resolves to private IP address: {ip}"
    
    return True, "ok"


def sanitize_filename(name: str) -> str:
    """Remove filesystem-unsafe characters from a filename."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()
