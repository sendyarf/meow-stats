from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import json
import re
from datetime import datetime
from collections import defaultdict

def fetch_full_html(url):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    
    print("Mengakses halaman dan memuat semua pertandingan...")
    driver.get(url)
    
    while True:
        try:
            show_more = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.wclButtonLink"))
            )
            driver.execute_script("arguments[0].click();", show_more)
            time.sleep(2)
        except Exception:
            print("Semua pertandingan telah dimuat.")
            break
    
    html = driver.page_source
    driver.quit()
    return html

def extract_matches(html):
    soup = BeautifulSoup(html, 'html.parser')
    matches = []
    current_round = None
    
    for element in soup.find_all('div'):
        classes = element.get('class', [])
        
        if 'event__round' in classes:
            text = element.get_text(strip=True)
            if text.startswith("Round"):
                current_round = text
        
        elif 'event__match' in classes:
            if not current_round:
                continue
                
            home_div = element.find('div', class_='event__homeParticipant')
            away_div = element.find('div', class_='event__awayParticipant')
            
            if not home_div or not away_div:
                continue
                
            home_name_span = home_div.find('span', class_='wcl-name_jjfMf')
            away_name_span = away_div.find('span', class_='wcl-name_jjfMf')
            
            if not home_name_span or not away_name_span:
                continue
                
            home_team = home_name_span.get_text(strip=True)
            away_team = away_name_span.get_text(strip=True)
            
            # Normalisasi nama tim
            if home_team == "Borneo FC":
                home_team = "Borneo"
            if away_team == "Borneo FC":
                away_team = "Borneo"
            
            home_score_span = element.find('span', class_='event__score--home')
            away_score_span = element.find('span', class_='event__score--away')
            
            if not home_score_span or not away_score_span:
                continue
            
            try:
                home_score = int(home_score_span.get_text(strip=True))
                away_score = int(away_score_span.get_text(strip=True))
            except:
                continue
            
            # Kartu merah
            home_reds = 0
            away_reds = 0
            
            for svg in home_div.find_all('svg', {'data-testid': 'wcl-icon-incidents-red-card'}):
                text = svg.find('text')
                home_reds += int(text.get_text(strip=True)) if text else 1
                
            for svg in away_div.find_all('svg', {'data-testid': 'wcl-icon-incidents-red-card'}):
                text = svg.find('text')
                away_reds += int(text.get_text(strip=True)) if text else 1
            
            # Kartu kuning
            home_yellows = 0
            away_yellows = 0
            
            for svg in home_div.find_all('svg', {'data-testid': 'wcl-icon-incidents-yellow-card'}):
                text = svg.find('text')
                home_yellows += int(text.get_text(strip=True)) if text else 1
                
            for svg in away_div.find_all('svg', {'data-testid': 'wcl-icon-incidents-yellow-card'}):
                text = svg.find('text')
                away_yellows += int(text.get_text(strip=True)) if text else 1
            
            matches.append({
                'round': current_round,
                'home': home_team,
                'away': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'home_reds': home_reds,
                'away_reds': away_reds,
                'home_yellows': home_yellows,
                'away_yellows': away_yellows
            })
    
    matches.sort(key=lambda x: int(re.search(r'\d+', x['round']).group()))
    print(f"Total pertandingan selesai: {len(matches)}")
    return matches

def compute_standings_per_round(matches):
    teams = set(m['home'] for m in matches) | set(m['away'] for m in matches)
    
    # Stats tim dengan fair play (kartu kuning dan merah)
    stats = {team: {
        'P': 0, 'W': 0, 'D': 0, 'L': 0, 
        'GF': 0, 'GA': 0, 'Pts': 0, 
        'Reds': 0, 'Yellows': 0
    } for team in teams}
    
    # H2H data: h2h[teamA][teamB] = {'pts': 0, 'gf': 0, 'ga': 0, 'matches': 0}
    h2h = defaultdict(lambda: defaultdict(lambda: {'pts': 0, 'gf': 0, 'ga': 0, 'matches': 0}))
    
    standings_per_round = {}
    current_round = None
    
    for match in matches:
        if match['round'] != current_round:
            if current_round:
                standings_per_round[current_round] = build_standings_with_liga1_rules(stats, teams, h2h)
            current_round = match['round']
        
        h = match['home']
        a = match['away']
        hs = match['home_score']
        asa = match['away_score']
        
        # Update overall stats
        stats[h]['GF'] += hs
        stats[h]['GA'] += asa
        stats[a]['GF'] += asa
        stats[a]['GA'] += hs
        stats[h]['Reds'] += match['home_reds']
        stats[a]['Reds'] += match['away_reds']
        stats[h]['Yellows'] += match['home_yellows']
        stats[a]['Yellows'] += match['away_yellows']
        
        stats[h]['P'] += 1
        stats[a]['P'] += 1
        
        if hs > asa:
            stats[h]['W'] += 1
            stats[h]['Pts'] += 3
            stats[a]['L'] += 1
        elif hs < asa:
            stats[a]['W'] += 1
            stats[a]['Pts'] += 3
            stats[h]['L'] += 1
        else:
            stats[h]['D'] += 1
            stats[a]['D'] += 1
            stats[h]['Pts'] += 1
            stats[a]['Pts'] += 1
        
        # Update H2H records
        h2h[h][a]['gf'] += hs
        h2h[h][a]['ga'] += asa
        h2h[h][a]['matches'] += 1
        h2h[a][h]['gf'] += asa
        h2h[a][h]['ga'] += hs
        h2h[a][h]['matches'] += 1
        
        if hs > asa:
            h2h[h][a]['pts'] += 3
        elif hs < asa:
            h2h[a][h]['pts'] += 3
        else:
            h2h[h][a]['pts'] += 1
            h2h[a][h]['pts'] += 1
    
    if current_round:
        standings_per_round[current_round] = build_standings_with_liga1_rules(stats, teams, h2h)
    
    return standings_per_round

def calculate_fair_play_points(yellows, reds):
    """
    Sesuai Lampiran 1 PT LIB:
    - Kartu kuning: 1 poin
    - Kartu merah (langsung): 3 poin
    - Kartu kuning kedua -> merah: 3 poin (1+3=4 total, tapi biasanya dihitung 3)
    Untuk simplifikasi: Yellow = 1, Red = 3
    Semakin rendah = semakin baik (fair play lebih baik)
    """
    return yellows * 1 + reds * 3

def check_h2h_eligibility(group, h2h):
    """
    Cek apakah semua tim dalam grup memiliki:
    - Jumlah pertandingan yang sama (played)
    - Semua tim sudah bertemu satu sama lain dengan jumlah pertemuan yang sama
    """
    if len(group) < 2:
        return False
    
    # Cek apakah semua tim memiliki played yang sama
    played_counts = set(row['played'] for row in group)
    if len(played_counts) > 1:
        return False
    
    # Cek apakah semua tim sudah bertemu dengan jumlah yang sama
    team_names = [row['team'] for row in group]
    meeting_counts = set()
    
    for i, team in enumerate(team_names):
        for opponent in team_names[i+1:]:
            meetings = h2h[team][opponent]['matches']
            meeting_counts.add(meetings)
    
    # Semua pertemuan harus memiliki jumlah yang sama dan > 0
    if len(meeting_counts) != 1 or 0 in meeting_counts:
        return False
    
    return True

def calculate_h2h_stats(team, opponents, h2h):
    """Hitung statistik H2H tim terhadap grup lawan"""
    h2h_pts = 0
    h2h_gf = 0
    h2h_ga = 0
    
    for opponent in opponents:
        record = h2h[team].get(opponent, {'pts': 0, 'gf': 0, 'ga': 0})
        h2h_pts += record['pts']
        h2h_gf += record['gf']
        h2h_ga += record['ga']
    
    h2h_gd = h2h_gf - h2h_ga
    return h2h_pts, h2h_gd, h2h_gf

def sort_group_by_h2h(group, h2h):
    """
    Urutkan grup berdasarkan kriteria H2H Liga 1:
    a) H2H points
    b) H2H goal difference  
    c) H2H goals scored
    """
    team_names = [row['team'] for row in group]
    
    def h2h_key(row):
        team = row['team']
        opponents = [t for t in team_names if t != team]
        h2h_pts, h2h_gd, h2h_gf = calculate_h2h_stats(team, opponents, h2h)
        return (h2h_pts, h2h_gd, h2h_gf)
    
    group.sort(key=h2h_key, reverse=True)
    return group

def h2h_resolves_tie(group, h2h):
    """
    Cek apakah H2H bisa memisahkan peringkat.
    Return True jika semua tim memiliki H2H stats yang berbeda.
    """
    team_names = [row['team'] for row in group]
    h2h_stats = []
    
    for row in group:
        team = row['team']
        opponents = [t for t in team_names if t != team]
        stats = calculate_h2h_stats(team, opponents, h2h)
        h2h_stats.append(stats)
    
    # Cek apakah ada duplikat
    return len(h2h_stats) == len(set(h2h_stats))

def try_tiebreaker_subgroups(group, h2h):
    """
    Jika H2H utama tidak berhasil, coba tie-breaker untuk subgrup.
    Mencoba memecah grup yang masih tied berdasarkan H2H di antara mereka.
    """
    team_names = [row['team'] for row in group]
    
    # Hitung H2H stats untuk setiap tim
    h2h_data = {}
    for row in group:
        team = row['team']
        opponents = [t for t in team_names if t != team]
        h2h_data[team] = calculate_h2h_stats(team, opponents, h2h)
    
    # Kelompokkan tim dengan H2H stats yang sama
    stats_to_teams = defaultdict(list)
    for team, stats in h2h_data.items():
        stats_to_teams[stats].append(team)
    
    result = []
    # Urutkan berdasarkan H2H stats (descending)
    for stats in sorted(stats_to_teams.keys(), reverse=True):
        teams_with_same_stats = stats_to_teams[stats]
        if len(teams_with_same_stats) == 1:
            # Sudah terpecah
            team = teams_with_same_stats[0]
            result.append(next(row for row in group if row['team'] == team))
        else:
            # Masih tied, coba tie-breaker rekursif untuk subgrup ini
            subgroup = [row for row in group if row['team'] in teams_with_same_stats]
            if len(subgroup) > 1:
                # Hitung H2H hanya di antara tim yang masih tied
                subgroup_names = [row['team'] for row in subgroup]
                
                def subgroup_h2h_key(row):
                    team = row['team']
                    sub_opponents = [t for t in subgroup_names if t != team]
                    return calculate_h2h_stats(team, sub_opponents, h2h)
                
                subgroup.sort(key=subgroup_h2h_key, reverse=True)
            result.extend(subgroup)
    
    return result

def build_standings_with_liga1_rules(stats, teams, h2h):
    """
    Membangun klasemen sesuai regulasi Liga 1:
    
    1. Jumlah poin
    2. Head-to-head (jika eligible):
       a) H2H points
       b) H2H goal difference
       c) H2H goals scored
       + Tie-breaker untuk subgrup jika perlu
    3. Jika H2H gagal/tidak eligible:
       a) Overall goal difference
       b) Overall goals scored
       c) Fair play (lebih sedikit = lebih baik)
    """
    table = []
    for team in teams:
        s = stats[team]
        gd = s['GF'] - s['GA']
        fair_play = calculate_fair_play_points(s['Yellows'], s['Reds'])
        table.append({
            'team': team,
            'played': s['P'],
            'win': s['W'],
            'draw': s['D'],
            'loss': s['L'],
            'gf': s['GF'],
            'ga': s['GA'],
            'gd': gd,
            'points': s['Pts'],
            'yellows': s['Yellows'],
            'reds': s['Reds'],
            'fair_play': fair_play
        })
    
    # Sort awal: descending points, lalu overall criteria sebagai fallback awal
    table.sort(key=lambda x: (-x['points'], -x['gd'], -x['gf'], x['fair_play']))
    
    # Proses grup yang memiliki poin sama
    i = 0
    while i < len(table):
        start = i
        current_points = table[i]['points']
        
        # Temukan semua tim dengan poin yang sama
        while i < len(table) and table[i]['points'] == current_points:
            i += 1
        
        group = table[start:i]
        
        if len(group) > 1:
            # Cek apakah H2H eligible
            if check_h2h_eligibility(group, h2h):
                # Coba H2H
                sorted_group = sort_group_by_h2h(group.copy(), h2h)
                
                if h2h_resolves_tie(sorted_group, h2h):
                    # H2H berhasil memisahkan semua tim
                    table[start:i] = sorted_group
                else:
                    # H2H tidak memisahkan semua, coba tie-breaker subgrup
                    sorted_group = try_tiebreaker_subgroups(sorted_group, h2h)
                    
                    # Cek lagi apakah tie-breaker berhasil
                    if h2h_resolves_tie(sorted_group, h2h):
                        table[start:i] = sorted_group
                    else:
                        # H2H dan tie-breaker gagal, kembali ke overall criteria
                        # ii. Overall GD, iii. Overall GF, iv. Fair play
                        group.sort(key=lambda x: (-x['gd'], -x['gf'], x['fair_play']))
                        table[start:i] = group
            else:
                # H2H tidak eligible (pertandingan/pertemuan tidak lengkap)
                # Langsung ke overall criteria
                group.sort(key=lambda x: (-x['gd'], -x['gf'], x['fair_play']))
                table[start:i] = group
    
    # Assign rank
    for rank, row in enumerate(table, 1):
        row['rank'] = rank
    
    return table

# === MAIN ===
url = "https://www.flashscore.com/football/indonesia/super-league/results/"

html = fetch_full_html(url)
matches = extract_matches(html)
standings_per_round = compute_standings_per_round(matches)

output = {
    "league": "BRI Liga 1 Indonesia",
    "season": "2025/2026",
    "generated_at": datetime.now().isoformat(),
    "note": "Tie-breaker sesuai regulasi PT LIB: 1. Points, 2a. H2H Points, 2b. H2H GD, 2c. H2H GF (jika eligible), 3. Overall GD, 4. Overall GF, 5. Fair Play (kuning×1 + merah×3)",
    "total_matches": len(matches),
    "standings": standings_per_round
}

with open("perweek.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\nFile perweek.json berhasil diperbarui!")
print(f"Total pekan: {len(standings_per_round)}")
print("Regulasi tie-breaker Liga 1 telah diterapkan:")
print("  1. Poin")
print("  2. Head-to-head (jika eligible):")
print("     a) H2H points")
print("     b) H2H goal difference")
print("     c) H2H goals scored")
print("  3. Jika H2H gagal/tidak eligible:")
print("     - Overall goal difference")
print("     - Overall goals scored")
print("     - Fair play (kartu kuning × 1 + kartu merah × 3)")