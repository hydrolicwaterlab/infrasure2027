"""App-wide rate limiter (slowapi)."""

from slowapi import Limiter
from slowapi.util import get_ipaddr

limiter = Limiter(key_func=get_ipaddr, default_limits=["120/minute"])