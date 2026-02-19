"""
Persib Bandung FotMob Scraper
Fetches data using requests and Playwright, and parses them directly to JSON.
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

# Sofascore Configuration
SOFASCORE_TEAM_ID = "64289"

# Sofascore Competitions (list of tournaments Persib participates in)
SOFASCORE_COMPETITIONS = [
    {
        "name": "Indonesia Super League",
        "tournament_id": "1015",
        "season_id": "78590",
        "season_name": "25/26"
    },
    {
        "name": "AFC Champions League Two",
        "tournament_id": "668",
        "season_id": "77009",
        "season_name": "25/26"
    }
]

SCRIPT_DIR = Path(__file__).parent

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1'
}

SOFASCORE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Cache-Control': 'max-age=0',
    'Referer': 'https://www.sofascore.com/',
    'Origin': 'https://www.sofascore.com',
    'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site'
}

def save_to_json(data: dict, filename: str):
    """Save data to JSON file."""
    path = SCRIPT_DIR / filename
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved JSON: {path}")


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
    
    # Try multiple wait strategies in order of preference
    wait_strategies = ["domcontentloaded", "load", "commit"]
    
    for strategy in wait_strategies:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
                )
                context = browser.new_context(user_agent=HEADERS['User-Agent'])
                page = context.new_page()
                print(f"  Trying wait strategy: {strategy}")
                page.goto(url, wait_until=strategy, timeout=90000)
                
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=30000)
                    except:
                        print(f"  Timeout waiting for selector: {wait_selector}, continuing anyway...")
                else:
                    # Wait a bit for dynamic content to render
                    page.wait_for_timeout(5000)
                
                content = page.content()
                browser.close()
                if content and len(content) > 1000:  # Ensure we got real content
                    return content
                else:
                    print(f"  Content too short with strategy {strategy}, trying next...")
        except Exception as e:
            print(f"  Playwright error with strategy {strategy}: {e}")
    
    print(f"  All Playwright strategies failed for {url}")
    return ""

# --- Parsing Functions (Robust logic) ---

def parse_standings_from_api(api_data: dict, table_type: str = "all") -> dict:
    """Parse standings from FotMob Team API response, supporting both single-table and composite groups."""
    standings = {"scraped_at": datetime.now().isoformat(), "leagues": []}
    
    if "table" not in api_data or not api_data["table"]:
        return standings
        
    for table_entry in api_data["table"]:
        data = table_entry.get("data", {})
        league_name = data.get("leagueName", "Unknown League")
        league_id = data.get("leagueId")
        league_url = f"https://www.fotmob.com{data.get('pageUrl')}" if data.get('pageUrl') else None
        league_logo = f"https://images.fotmob.com/image_resources/logo/leaguelogo/{league_id}.png" if league_id else None
        
        league_data = {
            "name": league_name,
            "logo": league_logo,
            "url": league_url,
            "groups": [],
            "teams": []
        }

        def process_rows(rows_data):
            teams_list = []
            for row in rows_data:
                scores = row.get("scoresStr", "0-0").split("-")
                gs = int(scores[0]) if len(scores) > 0 else 0
                gc = int(scores[1]) if len(scores) > 1 else 0
                
                teams_list.append({
                    "position": row.get("idx"),
                    "team": {
                        "id": str(row.get("id")),
                        "name": row.get("name"),
                        "logo": f"https://images.fotmob.com/image_resources/logo/teamlogo/{row.get('id')}.png",
                        "url": f"https://www.fotmob.com{row.get('pageUrl')}" if row.get('pageUrl') else None
                    },
                    "played": row.get("played", 0),
                    "won": row.get("wins", 0),
                    "drawn": row.get("draws", 0),
                    "lost": row.get("losses", 0),
                    "gs": gs,
                    "gc": gc,
                    "gd": row.get("goalConDiff", 0),
                    "pts": row.get("pts", 0)
                })
            return teams_list
        
        # 1. Check for standard single table
        table_obj = data.get("table", {})
        if table_obj:
            rows = table_obj.get(table_type, [])
            league_data["teams"] = process_rows(rows)
        
        # 2. Check for composite tables (groups)
        elif "tables" in data and isinstance(data["tables"], list):
            for group_table in data["tables"]:
                g_name = group_table.get("leagueName", "Unknown Group")
                g_rows = group_table.get("table", {}).get(table_type, [])
                if g_rows:
                    league_data["groups"].append({
                        "name": g_name,
                        "teams": process_rows(g_rows)
                    })
            
        if league_data["teams"] or league_data["groups"]:
            standings["leagues"].append(league_data)
            
    return standings

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
                "stats": stats,
                "url": None  # Will be populated below
            }
            
            # Get match URL from the next match link
            match_link = next_match_box.select_one('a[class*="NextMatchContainerCSS"]')
            if match_link:
                href = match_link.get('href', '')
                if href:
                    fixtures_data["next_match"]["url"] = f"https://www.fotmob.com{href}" if href.startswith('/') else href
        except Exception as e:
            print(f"Error parsing next match HTML: {e}")

    return fixtures_data

def parse_head_to_head(html_content: str) -> dict:
    """Parse head-to-head data from the H2H tab of a match page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    h2h_data = {
        "summary": None,
        "matches": []
    }
    
    # Find the H2H container
    h2h_container = soup.select_one('div[class*="H2hContainerCSS"]')
    if not h2h_container:
        return h2h_data
    
    try:
        # Parse H2H Summary (header with wins/draws)
        header = h2h_container.select_one('div[class*="H2hHeader"]')
        if header:
            # Get team logos/names from header
            team_icons = header.select('img.TeamIcon')
            team1_logo = team_icons[0]['src'] if len(team_icons) > 0 else None
            team2_logo = team_icons[1]['src'] if len(team_icons) > 1 else None
            
            # Get wins and draws numbers
            wins_containers = header.select('div[class*="WinsContainer"]')
            summary_values = []
            summary_labels = []
            
            for container in wins_containers:
                value_elem = container.select_one('span[class*="NumberOfWins"]')
                label_elem = container.select_one('span[class*="HeaderText"]')
                if value_elem:
                    summary_values.append(value_elem.get_text(strip=True))
                if label_elem:
                    summary_labels.append(label_elem.get_text(strip=True))
            
            # Typically: [Team1 Wins, Draws, Team2 Wins]
            h2h_data["summary"] = {
                "team1_logo": team1_logo,
                "team2_logo": team2_logo,
                "team1_wins": int(summary_values[0]) if len(summary_values) > 0 else 0,
                "draws": int(summary_values[1]) if len(summary_values) > 1 else 0,
                "team2_wins": int(summary_values[2]) if len(summary_values) > 2 else 0
            }
        
        # Parse individual match history
        match_items = h2h_container.select('li[class*="MatchContainer"]')
        for match_item in match_items:
            try:
                # Date
                date_elem = match_item.select_one('span[class*="TimeTxt"]')
                date_str = date_elem.get_text(strip=True) if date_elem else ""
                
                # League
                league_elem = match_item.select_one('a[class*="LeagueName"]')
                league_name = ""
                league_logo = None
                if league_elem:
                    league_span = league_elem.select_one('span')
                    league_name = league_span.get_text(strip=True) if league_span else ""
                    league_img = league_elem.select_one('img')
                    if league_img:
                        league_logo = league_img.get('src')
                
                # Teams and Score
                match_link = match_item.select_one('a[class*="MatchLink"]')
                if not match_link:
                    continue
                    
                match_url = match_link.get('href', '')
                if match_url and match_url.startswith('/'):
                    match_url = f"https://www.fotmob.com{match_url}"
                
                team_divs = match_link.select('div[class*="Team"]')
                teams = []
                for team_div in team_divs[:2]:  # Only first two are teams
                    team_name_elem = team_div.select_one('span[class*="TeamName"]')
                    team_logo_elem = team_div.select_one('img.TeamIcon')
                    teams.append({
                        "name": team_name_elem.get_text(strip=True) if team_name_elem else "",
                        "logo": team_logo_elem.get('src') if team_logo_elem else None
                    })
                
                # Score or scheduled time
                score_elem = match_link.select_one('span[class*="LSMatchStatusScore"]')
                time_elem = match_link.select_one('span[class*="LSMatchStatusTime"]')
                
                score = score_elem.get_text(strip=True) if score_elem else None
                match_time = time_elem.get_text(strip=True) if time_elem else None
                
                match_data = {
                    "date": date_str,
                    "league": league_name,
                    "league_logo": league_logo,
                    "home_team": teams[0] if len(teams) > 0 else {"name": "", "logo": None},
                    "away_team": teams[1] if len(teams) > 1 else {"name": "", "logo": None},
                    "score": score,
                    "time": match_time,
                    "status": "Finished" if score else "Scheduled",
                    "url": match_url
                }
                
                h2h_data["matches"].append(match_data)
            except Exception as e:
                print(f"Error parsing H2H match item: {e}")
                continue
                
    except Exception as e:
        print(f"Error parsing H2H data: {e}")
    
    return h2h_data

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
            
            sub_val = item.get("SubStatValue", item.get("subStatValue"))
            if sub_val is not None and isinstance(sub_val, (int, float, str)):
                try:
                    if float(sub_val) > 0:
                        sub_val = int(float(sub_val))
                    else:
                        sub_val = None
                except:
                    sub_val = None
            else:
                sub_val = None

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
                "sub_stat": sub_val,
                "type": stat_type
            })
        except: continue
    return stats_list

def fetch_json_with_playwright(url: str) -> dict:
    """Fetch JSON content with Playwright (useful for APIs blocked by standard requests)."""
    print(f"Fetching JSON with Playwright: {url}...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox', 
                    '--disable-gpu', 
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled'  # Stealth arg
                ]
            )
            context = browser.new_context(
                user_agent=HEADERS['User-Agent'],
                viewport={'width': 1920, 'height': 1080}
            )
            
            # Stealth: inject script to hide webdriver property
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page = context.new_page()
            
            # Warmup: Visit homepage first to set cookies/session
            try:
                print("  Warmup: Visiting homepage...")
                page.goto("https://www.sofascore.com", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)
            except Exception as e:
                print(f"  Warmup failed (continuing): {e}")
            
            # Use domcontentloaded instead of networkidle for reliability
            response = page.goto(url, wait_until="domcontentloaded", timeout=90000)
            
            # Check if response was successful
            if not response or not response.ok:
                print(f"  Playwright response not OK: {response.status if response else 'No Response'}")
                browser.close()
                return {}

            # Get the text content, which should be the JSON string
            # Sometimes APIs return HTML-wrapped JSON (e.g. <pre>...</pre>), so we handle that:
            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')
            # Try to find JSON in body text or pre tag
            body_text = soup.get_text()
            
            # Attempt to parse
            try:
                data = json.loads(body_text)
            except json.JSONDecodeError:
                # If direct body text fails, maybe it's inside a <pre>?
                pre = soup.find('pre')
                if pre:
                    data = json.loads(pre.get_text())
                else:
                    print("  Could not parse JSON from Playwright content")
                    data = {}
            
            browser.close()
            return data
    except Exception as e:
        print(f"  Playwright JSON error fetching {url}: {e}")
        return {}

def fetch_sofascore_team_statistics() -> dict:
    """Fetch team statistics from Sofascore API for all competitions."""
    all_stats = {
        "scraped_at": datetime.now().isoformat(),
        "team": "Persib Bandung",
        "team_id": SOFASCORE_TEAM_ID,
        "competitions": []
    }
    
    for competition in SOFASCORE_COMPETITIONS:
        comp_name = competition["name"]
        tournament_id = competition["tournament_id"]
        season_id = competition["season_id"]
        season_name = competition["season_name"]
        
        api_url = f"https://api.sofascore.com/api/v1/team/{SOFASCORE_TEAM_ID}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
        print(f"Fetching Sofascore statistics for {comp_name} ({season_name})...")
        
        comp_stats = {
            "name": comp_name,
            "tournament_id": tournament_id,
            "season": season_name,
            "season_id": season_id,
            "summary": {},
            "attacking": {},
            "passes": {},
            "defending": {},
            "other": {}
        }
        
        try:
            # Use Playwright instead of requests to avoid 403
            data = fetch_json_with_playwright(api_url)
            
            if not data:
                print(f"  Failed to fetch {comp_name} (Empty Data)")
                all_stats["competitions"].append(comp_stats)
                continue
            
            stats = data.get("statistics", {})
            
            # Parse Summary
            comp_stats["summary"] = {
                "matches": stats.get("matches", 0),
                "goals_scored": stats.get("goalsScored", 0),
                "goals_conceded": stats.get("goalsConceded", 0),
                "assists": stats.get("assists", 0),
                "awarded_matches": stats.get("awardedMatches", 0),
                "rating": stats.get("avgRating", 0)
            }
            
            # Parse Attacking stats
            comp_stats["attacking"] = {
                "goals_per_game": round(stats.get("goalsScored", 0) / max(stats.get("matches", 1), 1), 2),
                "penalty_goals": stats.get("penaltyGoals", 0),
                "penalties_taken": stats.get("penaltiesTaken", 0),
                "total_shots": stats.get("shots", 0),
                "shots_on_target": stats.get("shotsOnTarget", 0),
                "shots_off_target": stats.get("shotsOffTarget", 0),
                "blocked_shots": stats.get("blockedScoringAttempt", 0),
                "shots_inside_box": stats.get("shotsFromInsideTheBox", 0),
                "shots_outside_box": stats.get("shotsFromOutsideTheBox", 0),
                "goals_inside_box": stats.get("goalsFromInsideTheBox", 0),
                "goals_outside_box": stats.get("goalsFromOutsideTheBox", 0),
                "left_foot_goals": stats.get("leftFootGoals", 0),
                "right_foot_goals": stats.get("rightFootGoals", 0),
                "headed_goals": stats.get("headedGoals", 0),
                "big_chances_created": stats.get("bigChancesCreated", 0),
                "big_chances_scored": stats.get("bigChancesScored", 0), # Note: API might not have this explicit key, often calculated or named differently. Debug data didn't show 'bigChancesScored', only 'bigChances', 'bigChancesCreated', 'bigChancesMissed'.
                "big_chances_missed": stats.get("bigChancesMissed", 0),
                "successful_dribbles": stats.get("successfulDribbles", 0),
                "dribble_attempts": stats.get("dribbleAttempts", 0),
                "corners": stats.get("corners", 0),
                # ISL uses 'freeKicks' (~51), AFC uses 'freeKickShots' (~1). Prioritize 'freeKicks' if available and > 0, else 'freeKickShots'.
                "free_kicks": stats.get("freeKicks") if stats.get("freeKicks", 0) > 0 else stats.get("freeKickShots", 0),
                "hit_woodwork": stats.get("hitWoodwork", 0),
                "offsides": stats.get("offsides", 0)
            }
            
            # Parse Passes stats
            comp_stats["passes"] = {
                "ball_possession": stats.get("averageBallPossession", 0),
                "total_passes": stats.get("totalPasses", 0),
                "accurate_passes": stats.get("accuratePasses", 0),
                "accurate_passes_pct": stats.get("accuratePassesPercentage", 0),
                "long_balls": stats.get("totalLongBalls", 0),
                "accurate_long_balls": stats.get("accurateLongBalls", 0),
                "accurate_long_balls_pct": stats.get("accurateLongBallsPercentage", 0),
                "crosses": stats.get("totalCrosses", 0),
                "accurate_crosses": stats.get("accurateCrosses", 0),
                "accurate_crosses_pct": stats.get("accurateCrossesPercentage", 0),
                "passes_own_half": stats.get("totalOwnHalfPasses", 0),
                "accurate_passes_own_half": stats.get("accurateOwnHalfPasses", 0),
                "accurate_passes_own_half_pct": stats.get("accurateOwnHalfPassesPercentage", 0),
                "passes_opposition_half": stats.get("totalOppositionHalfPasses", 0),
                "accurate_passes_opposition_half": stats.get("accurateOppositionHalfPasses", 0),
                "accurate_passes_opposition_half_pct": stats.get("accurateOppositionHalfPassesPercentage", 0)
            }
            
            # Parse Defending stats
            comp_stats["defending"] = {
                "clean_sheets": stats.get("cleanSheets", 0),
                "goals_conceded_per_game": round(stats.get("goalsConceded", 0) / max(stats.get("matches", 1), 1), 2),
                "tackles": stats.get("tackles", 0),
                "interceptions": stats.get("interceptions", 0),
                "saves": stats.get("saves", 0),
                "clearances": stats.get("clearances", 0),
                "clearances_off_line": stats.get("clearancesOffLine", 0),
                "balls_recovered": stats.get("ballRecovery", 0),
                "errors_leading_to_shot": stats.get("errorsLeadingToShot", 0),
                "errors_leading_to_goal": stats.get("errorsLeadingToGoal", 0),
                "penalties_committed": stats.get("penaltiesCommited", 0),
                "last_man_tackles": stats.get("lastManTackles", 0)
            }
            
            # Parse Other stats
            comp_stats["other"] = {
                "total_duels": stats.get("totalDuels", 0),
                "duels_won": stats.get("duelsWon", 0),
                "duels_lost": stats.get("totalDuels", 0) - stats.get("duelsWon", 0),
                "duels_won_pct": stats.get("duelsWonPercentage", 0),
                "aerial_duels_won": stats.get("aerialDuelsWon", 0),
                "aerial_duels_won_pct": stats.get("aerialDuelsWonPercentage", 0),
                "ground_duels_won": stats.get("groundDuelsWon", 0),
                "ground_duels_won_pct": stats.get("groundDuelsWonPercentage", 0),
                "yellow_cards": stats.get("yellowCards", 0),
                "red_cards": stats.get("redCards", 0),
                "fouls": stats.get("fouls", 0),
                "throw_ins": stats.get("throwIns", 0),
                "goal_kicks": stats.get("goalKicks", 0),
                "possession_lost": stats.get("possessionLost", 0)
            }
            
            print(f"  Successfully fetched {comp_name}: {comp_stats['summary']['matches']} matches")
            
        except Exception as e:
            print(f"  Error fetching {comp_name}: {e}")
            import traceback
            traceback.print_exc()
        
        all_stats["competitions"].append(comp_stats)
    
    return all_stats

# --- SofaScore Fixtures ---

def fetch_fixtures_sofascore() -> dict:
    """Fetch all Persib fixtures (past and upcoming) from SofaScore API."""
    from datetime import timezone, timedelta
    import traceback
    
    print("\nFetching fixtures from SofaScore API...")
    
    fixtures_data = {
        "scraped_at": datetime.now().isoformat(),
        "fixtures": [],
        "next_match": None
    }
    
    all_events = []
    seen_ids = set()
    
    # Current season start (Aug 2025) as a filter
    season_start_ts = int(datetime(2025, 7, 1, tzinfo=timezone(timedelta(hours=7))).timestamp())
    
    # Step 1: Fetch PAST events (paginated)
    page = 0
    while True:
        try:
            url = f"https://api.sofascore.com/api/v1/team/{SOFASCORE_TEAM_ID}/events/last/{page}"
            data = fetch_json_with_playwright(url)
            
            if not data:
                print(f"  Failed to fetch past events page {page} (Empty Data)")
                break
            
            events = data.get("events", [])
            if not events:
                break
            
            # Filter events that are in current season (after July 2025)
            for ev in events:
                ev_id = ev.get("id")
                start_ts = ev.get("startTimestamp", 0)
                if ev_id in seen_ids:
                    continue
                if start_ts < season_start_ts:
                    continue
                seen_ids.add(ev_id)
                all_events.append(ev)
            
            # If the oldest event on this page is before season start, stop paginating
            oldest_ts = min(ev.get("startTimestamp", 0) for ev in events)
            if oldest_ts < season_start_ts:
                break
            
            page += 1
            if page > 10:  # Safety limit
                break
        except Exception as e:
            print(f"  Error fetching past events page {page}: {e}")
            break
    
    print(f"  Fetched {len(all_events)} past events")
    
    # Step 2: Fetch NEXT/upcoming events (paginated)
    page = 0
    while True:
        try:
            url = f"https://api.sofascore.com/api/v1/team/{SOFASCORE_TEAM_ID}/events/next/{page}"
            data = fetch_json_with_playwright(url)
            
            if not data:
                print(f"  Failed to fetch next events page {page} (Empty Data)")
                break
            
            events = data.get("events", [])
            if not events:
                break
            
            for ev in events:
                ev_id = ev.get("id")
                if ev_id in seen_ids:
                    continue
                seen_ids.add(ev_id)
                all_events.append(ev)
            
            page += 1
            if page > 5:  # Safety limit
                break
        except Exception as e:
            print(f"  Error fetching next events page {page}: {e}")
            break
    
    print(f"  Total events: {len(all_events)}")
    
    # Step 3: Sort all events by start timestamp
    all_events.sort(key=lambda ev: ev.get("startTimestamp", 0))
    
    # Step 4: Parse each event into fixtures format
    for ev in all_events:
        try:
            home_team = ev.get("homeTeam", {})
            away_team = ev.get("awayTeam", {})
            tournament = ev.get("tournament", {})
            unique_tournament = tournament.get("uniqueTournament", {})
            start_ts = ev.get("startTimestamp", 0)
            home_score = ev.get("homeScore", {})
            away_score = ev.get("awayScore", {})
            status_obj = ev.get("status", {})
            status_type = status_obj.get("type", "")
            slug = ev.get("slug", "")
            custom_id = ev.get("customId", "")
            
            # Convert timestamp to GMT+7
            match_dt = datetime.fromtimestamp(start_ts, tz=timezone(timedelta(hours=7)))
            date_str = match_dt.strftime("%b %d, %Y")  # e.g. "Feb 18, 2026"
            time_str = match_dt.strftime("%I:%M %p").lstrip('0')  # e.g. "8:30 PM"
            
            # Determine status and score
            if status_type == "finished":
                status = "Finished"
                h_score = home_score.get("current", home_score.get("display", 0))
                a_score = away_score.get("current", away_score.get("display", 0))
                score = f"{h_score} - {a_score}"
                display_time = None
            elif status_type == "notstarted":
                status = "Scheduled"
                score = None
                display_time = time_str
            elif status_type == "inprogress":
                status = "Live"
                h_score = home_score.get("current", home_score.get("display", 0))
                a_score = away_score.get("current", away_score.get("display", 0))
                score = f"{h_score} - {a_score}"
                display_time = None
            else:
                status = status_obj.get("description", status_type.capitalize())
                score = None
                display_time = time_str
            
            # League info
            league_name = unique_tournament.get("name", tournament.get("name", "Unknown"))
            tournament_id = unique_tournament.get("id", tournament.get("id"))
            league_logo = f"https://api.sofascore.com/api/v1/unique-tournament/{tournament_id}/image" if tournament_id else None
            
            home_team_id = home_team.get("id")
            away_team_id = away_team.get("id")
            home_team_logo = f"https://img.sofascore.com/api/v1/team/{home_team_id}/image" if home_team_id else None
            away_team_logo = f"https://img.sofascore.com/api/v1/team/{away_team_id}/image" if away_team_id else None
            
            fixtures_data["fixtures"].append({
                "date": date_str,
                "league": league_name,
                "league_logo": league_logo,
                "home_team": home_team.get("name", "Unknown"),
                "home_team_logo": home_team_logo,
                "away_team": away_team.get("name", "Unknown"),
                "away_team_logo": away_team_logo,
                "status": status,
                "score": score,
                "time": display_time,
                "url": f"https://www.sofascore.com/{slug}/{custom_id}" if slug and custom_id else None
            })
        except Exception as e:
            print(f"  Error parsing event: {e}")
            continue
    
    print(f"  Parsed {len(fixtures_data['fixtures'])} fixtures")
    return fixtures_data

# --- SofaScore Next Match & H2H ---

def fetch_next_match_sofascore() -> dict:
    """Fetch next match data, pregame stats, and H2H from SofaScore API."""
    print("\nFetching next match data from SofaScore API...")
    
    next_match_data = None
    
    try:
        # Step 1: Get next match event
        next_url = f"https://api.sofascore.com/api/v1/team/{SOFASCORE_TEAM_ID}/events/next/0"
        data = fetch_json_with_playwright(next_url)
        
        if not data:
            print(f"  Failed to fetch SofaScore next match (Empty Data)")
            return None
        
        events = data.get("events", [])
        if not events:
            print("  No upcoming events found from SofaScore")
            return None
        
        event = events[0]  # First upcoming match
        event_id = event.get("id")
        home_team = event.get("homeTeam", {})
        away_team = event.get("awayTeam", {})
        tournament = event.get("tournament", {})
        unique_tournament = tournament.get("uniqueTournament", {})
        season = event.get("season", {})
        start_ts = event.get("startTimestamp", 0)
        round_info = event.get("roundInfo", {})
        
        # Convert timestamp to readable date/time
        from datetime import timezone, timedelta
        match_dt = datetime.fromtimestamp(start_ts, tz=timezone(timedelta(hours=7)))  # GMT+7
        date_str = match_dt.strftime("%b %d")
        time_str = match_dt.strftime("%I:%M %p").lstrip('0')
        
        home_team_id = home_team.get("id")
        away_team_id = away_team.get("id")
        
        next_match_data = {
            "home_team": home_team.get("name", "Unknown"),
            "away_team": away_team.get("name", "Unknown"),
            "date": date_str,
            "time": time_str,
            "league": unique_tournament.get("name", tournament.get("name", "Unknown")),
            "round": round_info.get("round"),
            "stats": [],
            "url": f"https://www.sofascore.com/{event.get('slug', '')}/{event.get('customId', '')}",
            "head_to_head": None
        }
        
        print(f"  Next match: {next_match_data['home_team']} vs {next_match_data['away_team']} ({date_str} {time_str})")
        
        # Step 2: Fetch pregame form (positions, points, form)
        try:
            form_url = f"https://api.sofascore.com/api/v1/event/{event_id}/pregame-form"
            form_data = fetch_json_with_playwright(form_url)
            
            if form_data:
                home_form = form_data.get("homeTeam", {})
                away_form = form_data.get("awayTeam", {})
                label = form_data.get("label", "Pts")
                
                # Table position
                next_match_data["stats"].append({
                    "title": "Table position",
                    "home": str(home_form.get("position", "-")),
                    "away": str(away_form.get("position", "-"))
                })
                
                # Points
                next_match_data["stats"].append({
                    "title": label,
                    "home": str(home_form.get("value", "-")),
                    "away": str(away_form.get("value", "-"))
                })
                
                # Form (last 5 matches: W/D/L)
                home_form_str = "".join(home_form.get("form", []))
                away_form_str = "".join(away_form.get("form", []))
                next_match_data["stats"].append({
                    "title": "Form (last 5)",
                    "home": home_form_str,
                    "away": away_form_str
                })
                
                print(f"  Pregame form: Home pos {home_form.get('position')}, Away pos {away_form.get('position')}")
                print(f"  Pregame form: Home pos {home_form.get('position')}, Away pos {away_form.get('position')}")
            else:
                print(f"  Failed to fetch pregame form (Empty Data)")
        except Exception as e:
            print(f"  Error fetching pregame form: {e}")
        
        # Step 3: Fetch team statistics for goals per match
        tournament_id = unique_tournament.get("id")
        season_id = season.get("id")
        
        if tournament_id and season_id:
            for team_key, team_id in [("home", home_team_id), ("away", away_team_id)]:
                try:
                    stats_url = f"https://api.sofascore.com/api/v1/team/{team_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
                    stats_data_root = fetch_json_with_playwright(stats_url)
                    
                    if stats_data_root:
                        stats_data = stats_data_root.get("statistics", {})
                        goals_scored = stats_data.get("goalsScored", 0)
                        goals_conceded = stats_data.get("goalsConceded", 0)
                        matches_total = stats_data.get("matches", 1)
                        
                        gpg = round(goals_scored / max(matches_total, 1), 2) if goals_scored else 0
                        gcpg = round(goals_conceded / max(matches_total, 1), 2) if goals_conceded else 0
                        
                        # Find and update or append stats
                        gpg_stat = next((s for s in next_match_data["stats"] if s["title"] == "Goals per match"), None)
                        if not gpg_stat:
                            gpg_stat = {"title": "Goals per match", "home": "-", "away": "-"}
                            next_match_data["stats"].append(gpg_stat)
                        gpg_stat[team_key] = f"{gpg:.2f}"
                        
                        gcpg_stat = next((s for s in next_match_data["stats"] if s["title"] == "Goals conceded per match"), None)
                        if not gcpg_stat:
                            gcpg_stat = {"title": "Goals conceded per match", "home": "-", "away": "-"}
                            next_match_data["stats"].append(gcpg_stat)
                        gcpg_stat[team_key] = f"{gcpg:.2f}"
                except Exception as e:
                    print(f"  Error fetching team stats for {team_key}: {e}")
        
        # Step 4: Fetch H2H data (summary + match history)
        try:
            h2h_url = f"https://api.sofascore.com/api/v1/event/{event_id}/h2h"
            h2h_data = fetch_json_with_playwright(h2h_url)
            
            home_team_logo = f"https://api.sofascore.com/api/v1/team/{home_team_id}/image" if home_team_id else None
            away_team_logo = f"https://api.sofascore.com/api/v1/team/{away_team_id}/image" if away_team_id else None
            
            team_duel = {}
            if h2h_data:
                team_duel = h2h_data.get("teamDuel", {})
            
            # Fetch H2H match history by scanning Persib's past events for opponent matches
            opponent_id = away_team_id if home_team_id == int(SOFASCORE_TEAM_ID) else home_team_id
            h2h_matches = []
            
            for pg in range(10):  # Scan up to 10 pages of past events
                try:
                    past_url = f"https://api.sofascore.com/api/v1/team/{SOFASCORE_TEAM_ID}/events/last/{pg}"
                    past_data = fetch_json_with_playwright(past_url)
                    
                    if not past_data:
                        break
                    past_events = past_data.get("events", [])
                    if not past_events:
                        break
                    
                    for ev in past_events:
                        ev_home_id = ev.get("homeTeam", {}).get("id")
                        ev_away_id = ev.get("awayTeam", {}).get("id")
                        ev_status = ev.get("status", {}).get("type", "")
                        
                        if ev_status != "finished":
                            continue
                        if opponent_id not in (ev_home_id, ev_away_id):
                            continue
                        
                        ev_ts = ev.get("startTimestamp", 0)
                        ev_dt = datetime.fromtimestamp(ev_ts, tz=timezone(timedelta(hours=7)))
                        ev_hs = ev.get("homeScore", {}).get("current", 0)
                        ev_as = ev.get("awayScore", {}).get("current", 0)
                        
                        h2h_matches.append({
                            "_ts": ev_ts,
                            "date": ev_dt.strftime("%b %d, %Y"),
                            "home_team": ev.get("homeTeam", {}).get("name", "Unknown"),
                            "away_team": ev.get("awayTeam", {}).get("name", "Unknown"),
                            "score": f"{ev_hs} - {ev_as}"
                        })
                except Exception:
                    break
            
            # Sort by date descending (most recent first) and take top 5
            h2h_matches.sort(key=lambda x: x["_ts"], reverse=True)
            h2h_matches = h2h_matches[:5]
            # Remove internal timestamp
            for m in h2h_matches:
                del m["_ts"]
            
            next_match_data["head_to_head"] = {
                "summary": {
                    "team1_name": home_team.get("name", "Unknown"),
                    "team2_name": away_team.get("name", "Unknown"),
                    "team1_logo": home_team_logo,
                    "team2_logo": away_team_logo,
                    "team1_wins": team_duel.get("homeWins", 0),
                    "draws": team_duel.get("draws", 0),
                    "team2_wins": team_duel.get("awayWins", 0)
                },
                "matches": h2h_matches
            }
            
            print(f"  H2H: {team_duel.get('homeWins', 0)}W - {team_duel.get('draws', 0)}D - {team_duel.get('awayWins', 0)}L ({len(h2h_matches)} matches)")
            for m in h2h_matches:
                print(f"    {m['date']}: {m['home_team']} {m['score']} {m['away_team']}")
        except Exception as e:
            print(f"  Error fetching H2H: {e}")
        
    except Exception as e:
        print(f"  Error in SofaScore next match fetch: {e}")
        traceback.print_exc()
    
    return next_match_data

# --- Main Logic ---

def main():
    # 1. Fetch Team API directly (for standings)
    print("Fetching Team API data...")
    team_api_url = f"https://www.fotmob.com/api/teams?id={TEAM_ID}"
    team_api_data = {}
    try:
        resp = requests.get(team_api_url, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            team_api_data = resp.json()
        else:
            print(f"  Failed to fetch Team API: {resp.status_code}")
    except Exception as e:
        print(f"  Error fetching Team API: {e}")

    # 2. Fetch Player JSON Stats
    api_stats_tasks = {
        "goals": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/goals.json",
        "assists": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/goal_assist.json",
        "goals_assists": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/_goals_and_goal_assist.json",
        "yellow_cards": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/yellow_card.json",
        "red_cards": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/red_card.json",
    }
    
    # 3. Parsing
    print("\nParsing data to JSON...")
    
    # Standings (from API)
    if team_api_data:
        for t_type in ["all", "home", "away"]:
            s_data = parse_standings_from_api(team_api_data, t_type)
            save_to_json(s_data, f"standings_{t_type}.json")
            if t_type == "all":
                save_to_json(extract_persib_standings(s_data), "persib_standings.json")
    
    # Fixtures (from SofaScore API)
    fixtures_data = fetch_fixtures_sofascore()
    
    # Next match data with pregame stats & H2H (from SofaScore API)
    sofascore_next = fetch_next_match_sofascore()
    if sofascore_next:
        fixtures_data["next_match"] = sofascore_next
    
    save_to_json(fixtures_data, "fixtures.json")
    
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
    
    # 5. Fetch Sofascore Team Statistics
    # print("\nFetching Sofascore team statistics...")
    # sofascore_stats = fetch_sofascore_team_statistics()
    # save_to_json(sofascore_stats, "team_statistics.json")

if __name__ == "__main__":
    main()
