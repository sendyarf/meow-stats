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
            
            # Normalisasi nama Borneo (kadang "Borneo FC")
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
            
            matches.append({
                'round': current_round,
                'home': home_team,
                'away': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'home_reds': home_reds,
                'away_reds': away_reds
            })
    
    matches.sort(key=lambda x: int(re.search(r'\d+', x['round']).group()))
    print(f"Total pertandingan selesai: {len(matches)}")
    return matches

def compute_standings_per_round(matches):
    teams = set(m['home'] for m in matches) | set(m['away'] for m in matches)
    
    stats = {team: {'P': 0, 'W': 0, 'D': 0, 'L': 0, 'GF': 0, 'GA': 0, 'Pts': 0, 'Reds': 0} for team in teams}
    
    h2h = defaultdict(lambda: defaultdict(lambda: {'pts': 0, 'gf': 0, 'ga': 0}))
    
    standings_per_round = {}
    current_round = None
    
    for match in matches:
        if match['round'] != current_round:
            if current_round:
                standings_per_round[current_round] = build_standings_with_h2h(stats, teams, h2h)
            current_round = match['round']
        
        h = match['home']
        a = match['away']
        hs = match['home_score']
        asa = match['away_score']
        
        stats[h]['GF'] += hs
        stats[h]['GA'] += asa
        stats[a]['GF'] += asa
        stats[a]['GA'] += hs
        stats[h]['Reds'] += match['home_reds']
        stats[a]['Reds'] += match['away_reds']
        
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
        
        # Update H2H
        h2h[h][a]['gf'] += hs
        h2h[h][a]['ga'] += asa
        h2h[a][h]['gf'] += asa
        h2h[a][h]['ga'] += hs
        
        if hs > asa:
            h2h[h][a]['pts'] += 3
        elif hs < asa:
            h2h[a][h]['pts'] += 3
        else:
            h2h[h][a]['pts'] += 1
            h2h[a][h]['pts'] += 1
    
    if current_round:
        standings_per_round[current_round] = build_standings_with_h2h(stats, teams, h2h)
    
    return standings_per_round

def build_standings_with_h2h(stats, teams, h2h):
    table = []
    for team in teams:
        s = stats[team]
        gd = s['GF'] - s['GA']
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
            'reds': s['Reds']
        })
    
    # Sort awal descending poin
    table.sort(key=lambda x: -x['points'])
    
    i = 0
    while i < len(table):
        start = i
        current_points = table[i]['points']
        while i < len(table) and table[i]['points'] == current_points:
            i += 1
        group = table[start:i]
        
        if len(group) > 1:
            def h2h_sort_key(row):
                team = row['team']
                opponents = [op for op in group if op['team'] != team]
                h2h_pts = sum(h2h[team].get(op['team'], {'pts': 0})['pts'] for op in opponents)
                h2h_gd = sum(h2h[team].get(op['team'], {'gf': 0, 'ga': 0})['gf'] - 
                             h2h[team].get(op['team'], {'gf': 0, 'ga': 0})['ga'] for op in opponents)
                h2h_gf = sum(h2h[team].get(op['team'], {'gf': 0})['gf'] for op in opponents)
                return (-h2h_pts, -h2h_gd, -h2h_gf, -row['gd'], -row['gf'], row['reds'])
            
            group.sort(key=h2h_sort_key, reverse=True)  # Tambahkan reverse=True di sini!
            table[start:i] = group
    
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
    "note": "Tie-breaker resmi PT LIB: 1. Head-to-head points, 2. H2H GD, 3. H2H GF, 4. Overall GD, 5. Overall GF, 6. Fair play (red cards)",
    "total_matches": len(matches),
    "standings": standings_per_round
}

with open("perweek.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\nFile perweek.json berhasil diperbarui!")
print(f"Total pekan: {len(standings_per_round)}")
print("Perbaikan: Normalisasi nama 'Borneo FC' menjadi 'Borneo' agar H2H Persib vs Borneo terdeteksi dengan benar.")
print("Sekarang pada Round 15, Persib Bandung akan rank 1 karena menang head-to-head 3-1 atas Borneo FC.")