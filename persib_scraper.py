"""
Persib Bandung FotMob Scraper
Fetches data using requests, saves snippets to plan/*.txt, and parses them to JSON.
"""

import json
import re
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Configuration
TEAM_ID = "165196"
LEAGUE_ID = "8983"
SEASON_ID = "27434"

SCRIPT_DIR = Path(__file__).parent
PLAN_DIR = SCRIPT_DIR / "plan"
PLAN_DIR.mkdir(exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def save_to_json(data: dict, filename: str):
    """Save data to JSON file."""
    path = SCRIPT_DIR / filename
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved JSON: {path}")

def save_to_txt(filepath: Path, url: str, content: str):
    """Save HTML snippet to txt file with URL header."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"{url}\n\n{content}")
    print(f"Saved TXT: {filepath.name}")

def load_html_from_file(filepath: Path) -> str:
    """Load HTML from file, skipping the first lines (URL/Header)."""
    if not filepath.exists():
        return ""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the start of HTML
    first_tag_pos = content.find('<')
    if first_tag_pos == -1:
        return ""
    return content[first_tag_pos:]

def fetch_content(url: str) -> str:
    """Fetch content with requests."""
    print(f"Fetching {url}...")
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return ""

def fetch_with_playwright(url: str, wait_selector: Optional[str] = None) -> str:
    """Fetch content with Playwright for dynamic rendering."""
    print(f"Fetching with Playwright: {url}...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=HEADERS['User-Agent'])
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=60000)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=15000)
                except:
                    print(f"  Timeout waiting for selector: {wait_selector}")
            
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        print(f"  Playwright error fetching {url}: {e}")
        return ""

# --- Parsing Functions (Robust logic) ---

def parse_standings_from_html(html_content: str) -> dict:
    soup = BeautifulSoup(html_content, 'html.parser')
    standings = {"scraped_at": datetime.now().isoformat(), "leagues": []}
    containers = soup.select('article[class*="TableContainer"]')
    if not containers:
        containers = soup.find_all('article', class_=lambda x: x and 'TableContainer' in x)
        
    for container in containers:
        header = container.find('header')
        if not header: continue
        league_name_elem = header.find('h3')
        league_name = re.sub(r'\s+\d{4}/\d{4}$', '', league_name_elem.get_text(strip=True)) if league_name_elem else "Unknown League"
        league_link = header.find('a')
        league_logo = league_link.find('img')['src'] if league_link and league_link.find('img') else None
        league_url = f"https://www.fotmob.com{league_link['href']}" if league_link else None
        
        league_data = {"name": league_name, "logo": league_logo, "url": league_url, "groups": [], "teams": []}
        
        sub_tables = container.select('section[class*="SubTable"]')
        if sub_tables:
            for sub_table in sub_tables:
                group_name_elem = sub_table.find('a', class_=re.compile(r'SubTableHeader', re.I))
                group_name = group_name_elem.get_text(strip=True) if group_name_elem else "Unknown Group"
                league_data["groups"].append({"name": group_name, "teams": parse_table_rows(sub_table)})
        else:
            league_data["teams"] = parse_table_rows(container)
        
        if league_data["teams"] or league_data["groups"]:
            standings["leagues"].append(league_data)
            
    return standings

def parse_table_rows(container) -> List[Dict]:
    teams = []
    rows = container.select('div[class*="TableRow"]')
    for row in rows:
        try:
            pos_elem = row.select_one('div[class*="PositionCell"]')
            position = int(pos_elem.get_text(strip=True)) if pos_elem else 0
            team_cell = row.select_one('div[class*="TeamCell"]')
            team_name = team_logo = team_url = team_id = ""
            if team_cell:
                team_link = team_cell.find('a')
                if team_link:
                    team_url = team_link['href']
                    match = re.search(r'/teams/(\d+)/', team_url)
                    team_id = match.group(1) if match else ""
                team_name_elem = team_cell.select_one('span[class*="TeamName"]')
                team_name = team_name_elem.get_text(strip=True) if team_name_elem else ""
                team_logo_elem = team_cell.find('img')
                team_logo = team_logo_elem['src'] if team_logo_elem else ""
            
            cells = row.select('div[class*="TableCell"]:not([class*="TeamCell"]):not([class*="PositionCell"])')
            stats = [cell.get_text(strip=True) for cell in cells]
            form = [item.get_text(strip=True) for item in row.select('section[class*="SingleTeamForm"] a')]
            
            teams.append({
                "position": position,
                "team": {"id": team_id, "name": team_name, "logo": team_logo, "url": f"https://www.fotmob.com{team_url}" if team_url else None},
                "played": int(stats[0]) if stats and stats[0].isdigit() else 0,
                "won": int(stats[1]) if len(stats)>1 and stats[1].isdigit() else 0,
                "drawn": int(stats[2]) if len(stats)>2 and stats[2].isdigit() else 0,
                "lost": int(stats[3]) if len(stats)>3 and stats[3].isdigit() else 0,
                "goals": stats[4] if len(stats)>4 else "0-0",
                "goal_difference": stats[5] if len(stats)>5 else "0",
                "points": int(stats[6]) if len(stats)>6 and stats[6].isdigit() else 0,
                "form": form
            })
        except: continue
    return teams

def extract_persib_standings(standings: dict) -> dict:
    persib_data = {"scraped_at": standings.get("scraped_at"), "team": "Persib Bandung", "standings": []}
    for league in standings.get("leagues", []):
        for group in league.get("groups", []):
            for team in group.get("teams", []):
                if "Persib" in team["team"]["name"]:
                    persib_data["standings"].append({"league": league["name"], "group": group["name"], "league_logo": league["logo"], **team})
        for team in league.get("teams", []):
            if "Persib" in team["team"]["name"]:
                persib_data["standings"].append({"league": league["name"], "group": None, "league_logo": league["logo"], **team})
    return persib_data

def parse_fixtures_from_html(html_content: str) -> dict:
    soup = BeautifulSoup(html_content, 'html.parser')
    fixtures_data = {
        "scraped_at": datetime.now().isoformat(),
        "fixtures": [],
        "fixture_difficulty": [],
        "next_match": None
    }
    
    # Identify primary league for fallback (Matches often don't label the primary league)
    primary_league_name = "Unknown League"
    primary_league_logo = None
    # Try finding the league link with the league ID
    league_link = soup.select_one(f'a[href*="/leagues/{LEAGUE_ID}/"]')
    league_header_txt = league_link.get_text(strip=True) if league_link else ""
    
    if not league_header_txt:
        # Fallback to any league link that looks like a header (e.g. in NextMatchSection)
        alt_league = soup.select_one('a[class*="LeagueName"]')
        if alt_league: 
            primary_league_name = alt_league.get_text(strip=True)
            img = alt_league.find('img')
            if img: primary_league_logo = img.get('src')
    else:
        primary_league_name = league_header_txt
        img = league_link.find('img')
        if img: primary_league_logo = img.get('src')

    # 1. Parse all fixtures from HTML (for previous match history)
    seen_urls = set()
    for link in soup.select('a[href*="/matches/"]'):
        try:
            href = link.get('href', '')
            if not href or "/matches/" not in href: continue
            match_url = f"https://www.fotmob.com{href}" if href.startswith('/') else href
            if match_url in seen_urls: continue
            
            # Skip links that are just icons or team logos if they don't have enough data
            if not link.select_one('span[class*="TeamName"]'): continue

            date_elem = link.select_one('span[class*="StartDate"]')
            date_str = date_elem.get_text(strip=True) if date_elem else ""
            
            league_name = primary_league_name
            league_logo = primary_league_logo
            league_container = link.select_one('div[class*="LeagueNameAndIcon"]')
            if league_container:
                name_elem = league_container.select_one('span[class*="LeagueName"]')
                if name_elem: league_name = name_elem.get_text(strip=True)
                logo_elem = league_container.select_one('img')
                if logo_elem: league_logo = logo_elem['src']
            
            team_elems = link.select('span[class*="TeamName"]')
            # Handle NextMatchContainerCSS structure which might use different classes
            if not team_elems:
                team_elems = link.select('div[class*="TeamNameCSS"]')
                
            home_team = team_elems[0].get_text(strip=True) if len(team_elems) >= 1 else "Unknown"
            away_team = team_elems[1].get_text(strip=True) if len(team_elems) >= 2 else "Unknown"
            
            time_elem = link.select_one('div[class*="TimeCSS"]')
            if not time_elem: time_elem = link.select_one('div[class*="NextMatchTime"]')
                
            time_str = time_elem.get_text(strip=True).strip() if time_elem else None
            score_elem = link.select_one('span[class*="ScoreSpan"]')
            score = score_elem.get_text(strip=True) if score_elem else None
            
            fixtures_data["fixtures"].append({
                "date": date_str, "league": league_name, "league_logo": league_logo,
                "home_team": home_team, "away_team": away_team, "status": "Finished" if score else "Scheduled",
                "score": score, "time": time_str, "url": match_url
            })
            seen_urls.add(match_url)
        except: continue

    # 2. Parse Fixture Difficulty from HTML (using provided classes)
    diff_elems = soup.select('div[class*="FixtureDifficultyMatch"]')
    fixtures_data["fixture_difficulty"] = [el.get_text(strip=True).replace('\u00a0', ' ') for el in diff_elems]

    # 3. Parse Next Match from HTML (using provided classes)
    next_match_box = soup.select_one('section[class*="NextMatchBoxCSS"]')
    if next_match_box:
        try:
            # Teams
            team_names = [el.get_text(strip=True) for el in next_match_box.select('div[class*="TeamNameCSS"]')]
            # In the snippet order: Persik, (Time), Persib Bandung
            # Usually Away vs Home or Home vs Away.
            # Let's assume the first is Guest and second is Home if Persib is in the list
            if len(team_names) >= 2:
                home = team_names[0]
                away = team_names[1]
            else:
                home = "Unknown"
                away = "Unknown"
            
            m_time = next_match_box.select_one('div[class*="NextMatchTime"]').get_text(strip=True) if next_match_box.select_one('div[class*="NextMatchTime"]') else ""
            m_date = next_match_box.select_one('div[class*="NextMatchDate"]').get_text(strip=True) if next_match_box.select_one('div[class*="NextMatchDate"]') else ""
            
            stats = []
            for stat_li in next_match_box.select('li[class*="Stat"]'):
                title_elem = stat_li.select_one('span[class*="StatTitle"]')
                if not title_elem: continue
                title = title_elem.get_text(strip=True)
                
                # Snippet shows values inside spans
                values = [v.get_text(strip=True) for v in stat_li.select('span[class*="StatValue"]')]
                if len(values) >= 2:
                    stats.append({
                        "title": title,
                        "home": values[0],
                        "away": values[1]
                    })
            
            fixtures_data["next_match"] = {
                "home_team": home,
                "away_team": away,
                "date": m_date,
                "time": m_time,
                "stats": stats
            }
        except Exception as e:
            print(f"Error parsing next match HTML: {e}")

    return fixtures_data

def parse_player_stats() -> Dict:
    """Fetch and parse player stats using direct API approach for better reliability."""
    all_stats = {}
    
    # API endpoints for different stat types
    # We use the league API which is more comprehensive
    base_api = f"https://www.fotmob.com/api/leagues?id={LEAGUE_ID}&season={SEASON_ID}"
    
    stat_types = {
        "goals": "goals",
        "assists": "goal_assist",
        "red_cards": "red_cards",
        "yellow_cards": "yellow_cards"
    }

    for key, api_stat_name in stat_types.items():
        print(f"Fetching API stats: {key}...")
        try:
            response = requests.get(f"{base_api}&stat={api_stat_name}", headers=HEADERS, timeout=30)
            if response.status_code == 200:
                json_data = response.json()
                # Use the existing parse_top_stats_from_json to process the fetched data
                all_stats[key] = parse_top_stats_from_json(json_data, key)
            else:
                print(f"  Failed to fetch {key}: {response.status_code}")
                all_stats[key] = []
        except Exception as e:
            print(f"  Error fetching {key}: {e}")
            all_stats[key] = []
            
    return all_stats

def parse_top_stats_from_json(json_data: dict, stat_type: str, team_name: str = "Persib Bandung") -> List[Dict]:
    """Parse player statistics from FotMob API JSON data."""
    stats_list = []
    top_lists = json_data.get('TopLists', [])
    if not top_lists:
        # Fallback if structure is different
        data_list = json_data.get('StatList', []) or json_data.get('topStatList', []) or (json_data if isinstance(json_data, list) else [])
    else:
        data_list = top_lists[0].get('StatList', [])

    for idx, item in enumerate(data_list):
        try:
            # Filter by team
            current_team = item.get("TeamName", "") or item.get("teamName", "")
            if team_name.lower() not in current_team.lower():
                continue
                
            p_id = str(item.get("ParticiantId", "") or item.get("ParticipantId", "") or item.get("participantId", ""))
            name = item.get("ParticipantName", "") or item.get("participantName", "")
            rank = item.get("Rank", item.get("rank", idx + 1))
            val = item.get("StatValue", item.get("statValue", 0))
            if isinstance(val, (int, float, str)) and str(val).replace('.', '', 1).isdigit():
                val = int(float(val))
            
            stats_list.append({
                "rank": rank,
                "player": {
                    "id": p_id,
                    "name": name,
                    "image": f"https://images.fotmob.com/image_resources/playerimages/{p_id}.png",
                    "url": f"https://www.fotmob.com/players/{p_id}/{name.lower().replace(' ', '-')}" if p_id else None
                },
                "team_logo": f"https://images.fotmob.com/image_resources/logo/teamlogo/{TEAM_ID}.png",
                "value": val,
                "sub_stat": item.get("StatValueSuffix", item.get("statValueSuffix", None)),
                "type": stat_type
            })
        except: continue
    return stats_list

# --- Main Logic ---

def main():
    # 1. Fetch HTML and Save Snipets (for Table and Fixtures)
    html_tasks = [
        {"id": "table-all", "url": f"https://www.fotmob.com/teams/{TEAM_ID}/table/persib-bandung?filter=all", "sel": 'article[class*="TableContainer"]'},
        {"id": "table-home", "url": f"https://www.fotmob.com/teams/{TEAM_ID}/table/persib-bandung?filter=home", "sel": 'article[class*="TableContainer"]'},
        {"id": "table-away", "url": f"https://www.fotmob.com/teams/{TEAM_ID}/table/persib-bandung?filter=away", "sel": 'article[class*="TableContainer"]'},
        {"id": "fixtures", "url": f"https://www.fotmob.com/teams/{TEAM_ID}/fixtures/persib-bandung", "sel": 'section[class*="FixturesContainer"], div[class*="FixDiffContainer"], section[class*="NextMatchBox"], section[class*="NextMatchSection"]'},
    ]
    
    for t in html_tasks:
        if t["id"] == "fixtures":
            # Use Playwright for fixtures to get dynamic content
            html = fetch_with_playwright(t["url"], wait_selector='section[class*="NextMatchBoxCSS"]')
        else:
            # Use standard requests for tables (static)
            html = fetch_content(t["url"])
            
        if not html: continue
        
        # Save full HTML for fixtures to avoid missing dynamic content
        if t["id"] == "fixtures":
            save_to_txt(PLAN_DIR / f"{t['id']}.txt", t["url"], html)
            continue
            
        soup = BeautifulSoup(html, 'html.parser')
        snippet = ""
        selectors = t["sel"].split(', ')
        for sel in selectors:
            elems = soup.select(sel)
            for el in elems:
                snippet += el.prettify() + "\n"
        
        if not snippet:
             snippet = html # Fallback to full HTML if selector fails
        save_to_txt(PLAN_DIR / f"{t['id']}.txt", t["url"], snippet)

    # 2. Fetch JSON Stats directly from FotMob Data API
    api_stats_tasks = {
        "goals": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/goals.json",
        "assists": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/goal_assist.json",
        "goals_assists": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/_goals_and_goal_assist.json",
        "yellow_cards": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/yellow_card.json",
        "red_cards": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/red_card.json",
    }
    
    # 3. Parsing
    print("\nParsing data to JSON...")
    
    # Standings
    h_all = load_html_from_file(PLAN_DIR / "table-all.txt")
    if h_all:
        all_s = parse_standings_from_html(h_all)
        save_to_json(all_s, "standings_all.json")
        save_to_json(extract_persib_standings(all_s), "persib_standings.json")
    
    h_home = load_html_from_file(PLAN_DIR / "table-home.txt")
    if h_home: save_to_json(parse_standings_from_html(h_home), "standings_home.json")
    
    h_away = load_html_from_file(PLAN_DIR / "table-away.txt")
    if h_away: save_to_json(parse_standings_from_html(h_away), "standings_away.json")
    
    # Fixtures
    h_fix = load_html_from_file(PLAN_DIR / "fixtures.txt")
    if h_fix: save_to_json(parse_fixtures_from_html(h_fix), "fixtures.json")
    
    # Players Stats (API)
    top = {"scraped_at": datetime.now().isoformat(), "team": "Persib Bandung", "stats": {}}
    for stat_key, api_url in api_stats_tasks.items():
        print(f"Fetching API stats: {stat_key}...")
        try:
            resp = requests.get(api_url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                top["stats"][stat_key] = parse_top_stats_from_json(resp.json(), stat_key)
            else:
                print(f"  Failed to fetch {stat_key}: {resp.status_code}")
                top["stats"][stat_key] = []
        except Exception as e:
            print(f"  Error fetching {stat_key}: {e}")
            top["stats"][stat_key] = []
            
    save_to_json(top, "top_stats.json")

if __name__ == "__main__":
    main()
