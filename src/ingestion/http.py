import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Connection and read timeouts in seconds; a stalled answer fails fast and is retried
TIMEOUT = (10, 60)


# Retries timeouts, dropped connections and 429/5xx answers, waiting longer each time
# (about 2, 4, 8 and 16 seconds), because both public APIs fail now and then
def session_with_retries(attempts: int = 4) -> requests.Session:
    retry = Retry(
        total=attempts,
        connect=attempts,
        read=attempts,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


HTTP = session_with_retries()
