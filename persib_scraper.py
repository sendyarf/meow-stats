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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
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
                args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
            )
            context = browser.new_context(user_agent=HEADERS['User-Agent'])
            page = context.new_page()
            
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

# --- Main Logic ---

def main():
    # 1. Fetch Fixtures HTML directly
    print("Fetching Fixtures HTML...")
    fixtures_url = f"https://www.fotmob.com/teams/{TEAM_ID}/fixtures/persib-bandung"
    # Use Playwright for fixtures to get dynamic content
    fixtures_html = fetch_with_playwright(fixtures_url, wait_selector='section[class*="NextMatchBoxCSS"]')

    # 2. Fetch Team API directly (for standings)
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

    # 3. Fetch Player JSON Stats
    api_stats_tasks = {
        "goals": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/goals.json",
        "assists": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/goal_assist.json",
        "goals_assists": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/_goals_and_goal_assist.json",
        "yellow_cards": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/yellow_card.json",
        "red_cards": f"https://data.fotmob.com/stats/{LEAGUE_ID}/season/{SEASON_ID}/red_card.json",
    }
    
    # 4. Parsing
    print("\nParsing data to JSON...")
    
    # Standings (from API)
    if team_api_data:
        for t_type in ["all", "home", "away"]:
            s_data = parse_standings_from_api(team_api_data, t_type)
            save_to_json(s_data, f"standings_{t_type}.json")
            if t_type == "all":
                save_to_json(extract_persib_standings(s_data), "persib_standings.json")
    
    # Fixtures (from HTML) and Head-to-Head
    fixtures_data = None
    if fixtures_html:
        fixtures_data = parse_fixtures_from_html(fixtures_html)
        
        # Fetch H2H data if next_match URL is available
        if fixtures_data.get("next_match") and fixtures_data["next_match"].get("url"):
            next_match_url = fixtures_data["next_match"]["url"]
            # Construct the H2H tab URL
            h2h_url = f"{next_match_url}:tab=h2h"
            print(f"Fetching H2H page: {h2h_url}...")
            
            h2h_html = fetch_with_playwright(h2h_url, wait_selector='div[class*="H2hContainerCSS"]')
            if h2h_html:
                h2h_data = parse_head_to_head(h2h_html)
                fixtures_data["next_match"]["head_to_head"] = h2h_data
            else:
                fixtures_data["next_match"]["head_to_head"] = None
        
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
