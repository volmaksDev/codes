import json
import requests
from bs4 import BeautifulSoup

URL = "https://www.g2a.com/news/features/games-codes/roblox-blox-fruits-codes/"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

response = requests.get(URL, headers=headers, timeout=30)

print("Status:", response.status_code)

response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

codes = []

for table in soup.find_all("table"):
    headers_row = table.find("thead")

    if not headers_row:
        continue

    headers_text = [
        x.get_text(strip=True).lower()
        for x in headers_row.find_all(["th", "td"])
    ]

    if "code" not in headers_text or "reward" not in headers_text:
        continue

    for row in table.find("tbody").find_all("tr"):
        cells = row.find_all(["td", "th"])

        if len(cells) < 2:
            continue

        code = cells[0].get_text("", strip=False)
        reward = cells[1].get_text(" ", strip=True)

        codes.append({
            "code": code,
            "reward": reward
        })

    break

with open("codes.json", "w", encoding="utf-8") as file:
    json.dump(codes, file, ensure_ascii=False, indent=2)

print(f"Found {len(codes)} codes")
