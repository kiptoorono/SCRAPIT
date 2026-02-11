import json
import requests
from pathlib import Path

PROXIES_FILE = "proxies.json"
TEST_URL = "https://httpbin.org/ip"
TIMEOUT = 10

def load_proxies(path):
    with open(path, 'r') as f:
        return json.load(f)

def test_proxy(proxy):
    proxy_url = f"http://{proxy['username']}:{proxy['password']}@{proxy['address']}:{proxy['port']}"
    proxies = {
        'http': proxy_url,
        'https': proxy_url,
    }
    try:
        resp = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT)
        print(f"SUCCESS: {proxy['address']}:{proxy['port']} -> {resp.json()}")
    except Exception as e:
        print(f"FAIL: {proxy['address']}:{proxy['port']} - {e}")

def main():
    proxies = load_proxies(PROXIES_FILE)
    for proxy in proxies:
        test_proxy(proxy)

if __name__ == "__main__":
    main()
