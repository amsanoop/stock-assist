from ipaddress import ip_address, ip_network

from flask import request


def is_cloudflare_ip(ip: str) -> bool:
    """Verify if an IP belongs to Cloudflare's network ranges.

    Args:
        ip (str): The IP address to check.

    Returns:
        bool: True if the IP is a Cloudflare IP, False otherwise.
    """
    cf_ips_v4 = [
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "108.162.192.0/18",
        "131.0.72.0/22",
        "141.101.64.0/18",
        "162.158.0.0/15",
        "172.64.0.0/13",
        "173.245.48.0/20",
        "188.114.96.0/20",
        "190.93.240.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
    ]
    try:
        addr = ip_address(ip)
        return any(addr in ip_network(net) for net in cf_ips_v4)
    except ValueError:
        return False


def get_ip() -> str:
    """Returns the IP address of the client making the request in a secure way.

    Returns:
        str: The IP address of the client.
    """
    if request.headers.get("CF-Connecting-IP") and request.headers.get("CF-RAY"):
        cloudflare_ip = request.remote_addr
        if is_cloudflare_ip(cloudflare_ip):
            return request.headers.get("CF-Connecting-IP")

    return request.remote_addr
