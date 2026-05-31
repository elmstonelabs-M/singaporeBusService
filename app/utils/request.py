from fastapi import Request


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip

    cf_connecting_ip = request.headers.get("cf-connecting-ip")
    if cf_connecting_ip:
        value = cf_connecting_ip.strip()
        if value:
            return value

    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        value = x_real_ip.strip()
        if value:
            return value

    if request.client and request.client.host:
        return request.client.host

    return "unknown"
