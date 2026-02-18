# -*- coding: utf-8 -*-
import requests
from datetime import datetime

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.sofascore.com",
    "Accept": "application/json"
}

BASE_URL  = "https://api.sofascore.com/api/v1"
PERSIB_ID = 64289

h2h_results = []
page = 0

print("Mencari riwayat H2H Persib vs Persita...\n")

while True:
    url = f"{BASE_URL}/team/{PERSIB_ID}/events/last/{page}"
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        break

    data   = res.json()
    events = data.get("events", [])

    if not events:
        break

    for match in events:
        home_name = match["homeTeam"]["name"]
        away_name = match["awayTeam"]["name"]

        is_vs_persita = (
            "persita" in home_name.lower() or
            "persita" in away_name.lower()
        )

        if is_vs_persita:
            home_score = match.get("homeScore", {}).get("current", None)
            away_score = match.get("awayScore", {}).get("current", None)

            if home_score is None or away_score is None:
                continue

            timestamp   = match["startTimestamp"]
            tanggal     = datetime.utcfromtimestamp(timestamp).strftime("%d %b %Y")

            # Ambil nama kompetisi dan musim
            tournament  = match.get("tournament", {}).get("name", "-")
            season      = match.get("season", {}).get("name", "-")
            kompetisi   = f"{tournament} {season}"

            # Tentukan hasil dari perspektif Persib
            is_home = "persib" in home_name.lower()
            if int(home_score) == int(away_score):
                hasil = "Seri"
            elif (is_home and int(home_score) > int(away_score)) or \
                 (not is_home and int(away_score) > int(home_score)):
                hasil = "Menang"
            else:
                hasil = "Kalah"

            h2h_results.append({
                "timestamp" : timestamp,
                "tanggal"   : tanggal,
                "home"      : home_name,
                "away"      : away_name,
                "home_score": home_score,
                "away_score": away_score,
                "hasil"     : hasil,
                "kompetisi" : kompetisi
            })

    page += 1
    if page > 20:
        break

# Urutkan by tanggal terbaru
h2h_results.sort(key=lambda x: x["timestamp"], reverse=True)

# --- Tampilkan hasil ---
if not h2h_results:
    print("Tidak ditemukan riwayat H2H dengan skor valid.")
else:
    print("=" * 95)
    print(f"  HEAD-TO-HEAD : Persib Bandung vs Persita Tangerang")
    print(f"  Total        : {len(h2h_results)} Pertandingan (skor valid)")
    print("=" * 95)
    print(f"{'No':<4} {'Tanggal':<14} {'Tim Kandang':<25} {'Skor':<9} {'Tim Tandang':<25} {'Hasil':<8} {'Kompetisi'}")
    print("-" * 95)

    for i, m in enumerate(h2h_results, 1):
        skor = f"{m['home_score']} - {m['away_score']}"
        print(f"{i:<4} {m['tanggal']:<14} {m['home']:<25} {skor:<9} {m['away']:<25} {m['hasil']:<8} {m['kompetisi']}")

    # Ringkasan
    menang = sum(1 for m in h2h_results if m["hasil"] == "Menang")
    seri   = sum(1 for m in h2h_results if m["hasil"] == "Seri")
    kalah  = sum(1 for m in h2h_results if m["hasil"] == "Kalah")

    print("=" * 95)
    print(f"  RINGKASAN (perspektif Persib Bandung)")
    print(f"  Menang : {menang}   Seri : {seri}   Kalah : {kalah}")
    print("=" * 95)
