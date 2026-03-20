import requests
from bs4 import BeautifulSoup

url = "https://en.wikipedia.org/wiki/M142_HIMARS"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
print(resp.status_code)
soup = BeautifulSoup(resp.content, "html.parser")
text = soup.get_text(separator="\n", strip=True)
print(len(text))
