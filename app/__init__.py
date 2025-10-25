"""Application package initialisation."""

import os

# Disable outbound proxies so httpx AsyncClient(app=...) tests work without
# external network access. httpx honours these environment variables when
# `trust_env=True` (its default), which would otherwise forward requests to
# a proxy and result in 403 responses.
for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(key, None)

os.environ.setdefault("NO_PROXY", "*")
