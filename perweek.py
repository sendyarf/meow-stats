import requests
import json
from collections import defaultdict

# Konfigurasi
LEAGUE_ID = "8983"   # BRI Liga 1
SEASON_ID = "27434"  # 2025/2026

url = f"https://www.fotmob.com/api/leagues?id={LEAGUE_ID}&season={SEASON_ID}"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)
if response.status_code != 200:
    print(f"Error API: {response.status_code}")
    exit()

data = response.json()

# Akses fixtures dari key 'fixtures' (dari log kamu)
if 'fixtures' not in data:
    print("Fixtures tidak ditemukan di 'fixtures'")
    print("Key yang ada:", list(data.keys()))
    exit()

# Asumsi fixtures adalah list langsung atau di sub-key seperti 'matches' atau 'allMatches'
matches = data['fixtures']
if isinstance(matches, dict):
    # Coba sub-key umum
    if 'allMatches' in matches:
        matches = matches['allMatches']
    elif 'matches' in matches:
        matches = matches['matches']
    else:
        print("Sub-key fixtures tidak dikenal:", list(matches.keys()))
        exit()

if not isinstance(matches, list):
    print("Fixtures bukan list")
    exit()

print(f"Total pertandingan ditemukan: {len(matches)}\n")

# Sort berdasarkan round dan time
matches.sort(key=lambda m: (int(m.get('round', 999)), m.get('utcTime', '') or m.get('date', '')))

# Inisialisasi
standings = defaultdict(lambda: {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "gd": 0, "points": 0})
team_names = {}

all_round_standings = []

current_round = None

for match in matches:
    status = match.get('status', {})
    if not status.get('finished'):
        continue  # Skip upcoming

    round_num = match.get('roundName') or match.get('round') or "Unknown"
    round_name = f"Matchday {round_num}"

    # Jika round baru, simpan standings pekan sebelumnya
    if round_name != current_round and current_round is not None:
        sorted_teams = sorted(standings.items(), key=lambda x: (-x[1]['points'], -x[1]['gd'], -x[1]['gf']))
        standings_list = []
        for pos, (tid, stats) in enumerate(sorted_teams, 1):
            standings_list.append({
                "position": pos,
                "team_id": tid,
                "team_name": team_names.get(tid, "Unknown"),
                "played": stats['played'],
                "won": stats['won'],
                "drawn": stats['drawn'],
                "lost": stats['lost'],
                "gf": stats['gf'],
                "ga": stats['ga'],
                "gd": stats['gd'],
                "points": stats['points']
            })
        all_round_standings.append({"round": current_round, "standings": standings_list})

    current_round = round_name

    home = match.get('home', {})
    away = match.get('away', {})
    if not home or not away:
        continue

    home_id = str(home['id'])
    away_id = str(away['id'])
    team_names[home_id] = home.get('name', "Unknown")
    team_names[away_id] = away.get('name', "Unknown")

    score_str = status.get('scoreStr', '0 - 0')
    home_goals, away_goals = map(int, score_str.split(' - '))

    # Update standings
    for tid, gf, ga in [(home_id, home_goals, away_goals), (away_id, away_goals, home_goals)]:
        standings[tid]['played'] += 1
        standings[tid]['gf'] += gf
        standings[tid]['ga'] += ga
        standings[tid]['gd'] = standings[tid]['gf'] - standings[tid]['ga']
        if gf > ga:
            standings[tid]['won'] += 1
            standings[tid]['points'] += 3
        elif gf == ga:
            standings[tid]['drawn'] += 1
            standings[tid]['points'] += 1
        else:
            standings[tid]['lost'] += 1

# Simpan round terakhir
if current_round:
    sorted_teams = sorted(standings.items(), key=lambda x: (-x[1]['points'], -x[1]['gd'], -x[1]['gf']))
    standings_list = []
    for pos, (tid, stats) in enumerate(sorted_teams, 1):
        standings_list.append({
            "position": pos,
            "team_id": tid,
            "team_name": team_names.get(tid, "Unknown"),
            "played": stats['played'],
            "won": stats['won'],
            "drawn": stats['drawn'],
            "lost": stats['lost'],
            "gf": stats['gf'],
            "ga": stats['ga'],
            "gd": stats['gd'],
            "points": stats['points']
        })
    all_round_standings.append({"round": current_round, "standings": standings_list})

# Output
print("\nKlasemen Per Pekan (Semua Tim):")
print(json.dumps(all_round_standings, indent=2, ensure_ascii=False))

# Simpan ke file
with open('per_week.json', 'w', encoding='utf-8') as f:
    json.dump(all_round_standings, f, indent=2, ensure_ascii=False)
print("\nFile disimpan: per_week.json")