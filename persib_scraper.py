"""
Persib Bandung FotMob Scraper
Scrapes league standings data from FotMob HTML and saves to JSON files.
"""

import json
import re
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime


def parse_standings_from_html(html_content: str) -> dict:
    """
    Parse league standings from FotMob HTML content.
    
    Args:
        html_content: Raw HTML string from FotMob standings page
        
    Returns:
        Dictionary containing league standings data
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    standings = {
        "scraped_at": datetime.now().isoformat(),
        "leagues": []
    }
    
    # Find all table containers (each represents a league)
    table_containers = soup.find_all('article', class_='TableContainer')
    
    for container in table_containers:
        league_data = parse_league_table(container)
        if league_data:
            standings["leagues"].append(league_data)
    
    return standings


def parse_league_table(container) -> dict:
    """
    Parse a single league table from its container element.
    
    Args:
        container: BeautifulSoup element for the table container
        
    Returns:
        Dictionary with league name and team standings
    """
    # Get league name from header
    header = container.find('header')
    if not header:
        return None
    
    league_link = header.find('a')
    league_name_elem = header.find('h3')
    
    league_name = league_name_elem.get_text(strip=True) if league_name_elem else "Unknown League"
    league_logo = None
    league_url = None
    
    if league_link:
        league_url = league_link.get('href', '')
        logo_img = league_link.find('img')
        if logo_img:
            league_logo = logo_img.get('src', '')
    
    league_data = {
        "name": league_name,
        "logo": league_logo,
        "url": f"https://www.fotmob.com{league_url}" if league_url else None,
        "groups": [],
        "teams": []
    }
    
    # Check if this is a grouped table (like AFC Champions League)
    sub_tables = container.find_all('section', class_=lambda x: x and 'SubTableCSS' in str(x))
    
    if sub_tables:
        # Parse grouped tables
        for sub_table in sub_tables:
            group_name_elem = sub_table.find('a', class_=lambda x: x and 'SubTableHeaderCSS' in str(x))
            group_name = group_name_elem.get_text(strip=True) if group_name_elem else "Unknown Group"
            
            group_data = {
                "name": group_name,
                "teams": parse_table_rows(sub_table)
            }
            league_data["groups"].append(group_data)
    else:
        # Parse single table
        league_data["teams"] = parse_table_rows(container)
    
    return league_data


def parse_table_rows(container) -> list:
    """
    Parse team rows from a table container.
    
    Args:
        container: BeautifulSoup element containing the table
        
    Returns:
        List of team dictionaries with standings data
    """
    teams = []
    
    # Find all table rows
    rows = container.find_all('div', class_=lambda x: x and 'TableRowCSS' in str(x))
    
    for row in rows:
        team_data = parse_team_row(row)
        if team_data:
            teams.append(team_data)
    
    return teams


def parse_team_row(row) -> dict:
    """
    Parse a single team row from the standings table.
    
    Args:
        row: BeautifulSoup element for the table row
        
    Returns:
        Dictionary with team standings data
    """
    try:
        # Get position
        position_elem = row.find('div', class_=lambda x: x and 'TablePositionCell' in str(x))
        position = int(position_elem.get_text(strip=True)) if position_elem else 0
        
        # Get team info
        team_cell = row.find('div', class_=lambda x: x and 'TableTeamCell' in str(x))
        team_name = ""
        team_logo = ""
        team_url = ""
        team_id = ""
        
        if team_cell:
            team_link = team_cell.find('a')
            if team_link:
                team_url = team_link.get('href', '')
                # Extract team ID from URL
                match = re.search(r'/teams/(\d+)/', team_url)
                if match:
                    team_id = match.group(1)
            
            team_name_elem = team_cell.find('span', class_='TeamName')
            team_name = team_name_elem.get_text(strip=True) if team_name_elem else ""
            
            team_logo_elem = team_cell.find('img')
            if team_logo_elem:
                team_logo = team_logo_elem.get('src', '')
        
        # Get stats - find all TableCell divs
        cells = row.find_all('div', class_=lambda x: x and 'TableCell' in str(x) and 'TableTeamCell' not in str(x) and 'TablePositionCell' not in str(x))
        
        # Parse stats from cells
        stats = []
        for cell in cells:
            # Check if this is a goals cell (contains spans for goals)
            spans = cell.find_all('span', recursive=False)
            if len(spans) == 2:
                # Goals for/against format
                stats.append(f"{spans[0].get_text(strip=True)}-{spans[1].get_text(strip=True)}")
            elif len(spans) == 1:
                stats.append(spans[0].get_text(strip=True))
            else:
                text = cell.get_text(strip=True)
                if text:
                    stats.append(text)
        
        # Parse form
        form = []
        form_section = row.find('section', class_='SingleTeamForm')
        if form_section:
            form_items = form_section.find_all('a')
            for item in form_items:
                result = item.get_text(strip=True)
                match_url = item.get('href', '')
                form.append({
                    "result": result,
                    "match_url": f"https://www.fotmob.com{match_url}" if match_url else None
                })
        
        # Parse next opponent
        next_opponent = None
        next_elem = row.find('a', class_=lambda x: x and 'NextOpponentCSS' in str(x))
        if next_elem:
            next_url = next_elem.get('href', '')
            next_logo = next_elem.find('img')
            next_opponent = {
                "match_url": f"https://www.fotmob.com{next_url}" if next_url else None,
                "logo": next_logo.get('src', '') if next_logo else None
            }
        
        # Map stats to fields (PL, W, D, L, +/-, GD, PTS)
        team_data = {
            "position": position,
            "team": {
                "id": team_id,
                "name": team_name,
                "logo": team_logo,
                "url": f"https://www.fotmob.com{team_url}" if team_url else None
            },
            "played": int(stats[0]) if len(stats) > 0 and stats[0].isdigit() else 0,
            "won": int(stats[1]) if len(stats) > 1 and stats[1].isdigit() else 0,
            "drawn": int(stats[2]) if len(stats) > 2 and stats[2].isdigit() else 0,
            "lost": int(stats[3]) if len(stats) > 3 and stats[3].isdigit() else 0,
            "goals": stats[4] if len(stats) > 4 else "0-0",
            "goal_difference": stats[5] if len(stats) > 5 else "0",
            "points": int(stats[6]) if len(stats) > 6 and stats[6].isdigit() else 0,
            "form": form,
            "next_match": next_opponent
        }
        
        return team_data
        
    except Exception as e:
        print(f"Error parsing team row: {e}")
        return None


def extract_persib_standings(standings: dict) -> dict:
    """
    Extract only Persib Bandung's standings from the full standings data.
    
    Args:
        standings: Full standings dictionary
        
    Returns:
        Dictionary with Persib's standings across all leagues
    """
    persib_data = {
        "scraped_at": standings.get("scraped_at"),
        "team": "Persib Bandung",
        "standings": []
    }
    
    for league in standings.get("leagues", []):
        # Check in groups
        for group in league.get("groups", []):
            for team in group.get("teams", []):
                if "Persib" in team.get("team", {}).get("name", ""):
                    persib_data["standings"].append({
                        "league": league.get("name"),
                        "group": group.get("name"),
                        "league_logo": league.get("logo"),
                        **team
                    })
        
        # Check in main teams list
        for team in league.get("teams", []):
            if "Persib" in team.get("team", {}).get("name", ""):
                persib_data["standings"].append({
                    "league": league.get("name"),
                    "group": None,
                    "league_logo": league.get("logo"),
                    **team
                })
    
    return persib_data


def save_to_json(data: dict, filename: str):
    """
    Save data to a JSON file.
    
    Args:
        data: Dictionary to save
        filename: Output filename
    """
    output_path = Path(__file__).parent / filename
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved: {output_path}")


def load_html_from_file(filepath: str) -> str:
    """
    Load HTML content from a file.
    
    Args:
        filepath: Path to the HTML file
        
    Returns:
        HTML content as string
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the HTML content (skip the first lines with description/URL)
    lines = content.split('\n')
    html_lines = []
    for line in lines:
        if line.strip().startswith('<'):
            html_lines.append(line)
    
    return '\n'.join(html_lines)


def parse_fixtures_from_html(html_content: str) -> dict:
    """
    Parse fixtures from FotMob HTML content.
    
    Args:
        html_content: Raw HTML string from FotMob fixtures page
        
    Returns:
        Dictionary containing fixtures data
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    fixtures_data = {
        "scraped_at": datetime.now().isoformat(),
        "fixtures": []
    }
    
    # Find all fixture links - usually <a> tags with specific classes or structure
    # Based on the file viewed: <a href="..." class="css-jiwnw2-FtContainer ...">
    fixture_links = soup.find_all('a', href=True, class_=lambda x: x and 'FtContainer' in str(x))
    
    for link in fixture_links:
        match_data = parse_match_element(link)
        if match_data:
            fixtures_data["fixtures"].append(match_data)
            
    # Parse Fixture Difficulty
    fixtures_data["fixture_difficulty"] = []
    diff_container = soup.find('div', class_=lambda x: x and 'FixtureDifficulties' in str(x))
    if diff_container:
        diff_items = diff_container.find_all('div', class_=lambda x: x and 'FixtureDifficultyMatch' in str(x))
        for item in diff_items:
            text = item.get_text(strip=True).replace('\u00a0', ' ')
            fixtures_data["fixture_difficulty"].append(text)
            
    # Parse Next Match
    fixtures_data["next_match"] = None
    next_match_section = soup.find('section', class_=lambda x: x and 'NextMatchBoxCSS' in str(x))
    if next_match_section:
        try:
            home_team = "Unknown"
            away_team = "Unknown"
            
            # Teams
            team_containers = next_match_section.find_all('div', class_=lambda x: x and 'TeamContainer' in str(x))
            if len(team_containers) >= 2:
                # The structure usually has opponent first or depends on home/away
                # In the txt, it's Persik (first) vs Persib (second)
                # Let's just grab names
                t1 = team_containers[0].find('div', class_=lambda x: x and 'TeamNameCSS' in str(x))
                t2 = team_containers[1].find('div', class_=lambda x: x and 'TeamNameCSS' in str(x))
                home_team = t1.get_text(strip=True) if t1 else ""
                away_team = t2.get_text(strip=True) if t2 else ""
                
            # Date/Time
            time_elem = next_match_section.find('div', class_=lambda x: x and 'NextMatchTime' in str(x))
            match_time = time_elem.get_text(strip=True) if time_elem else ""
            
            date_elem = next_match_section.find('div', class_=lambda x: x and 'NextMatchDate' in str(x))
            match_date = date_elem.get_text(strip=True) if date_elem else ""
            
            # Stats (Position, Goals per match, etc)
            stats = []
            stat_items = next_match_section.find_all('li', class_=lambda x: x and 'Stat' in str(x) and 'StatGroupContainer' not in str(x))
            for stat in stat_items:
                title_elem = stat.find('span', class_=lambda x: x and 'StatTitle' in str(x))
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                # Values (Left vs Right)
                values = stat.find_all('span', class_=lambda x: x and 'StatValue' in str(x))
                val_home = values[0].get_text(strip=True) if len(values) > 0 else ""
                val_away = values[1].get_text(strip=True) if len(values) > 1 else ""
                
                stats.append({
                    "title": title,
                    "home": val_home,
                    "away": val_away
                })
                
            fixtures_data["next_match"] = {
                "home_team": home_team,
                "away_team": away_team,
                "date": match_date,
                "time": match_time,
                "stats": stats
            }
        except Exception as e:
            print(f"Error parsing next match: {e}")

    return fixtures_data


def parse_match_element(element) -> dict:
    """
    Parse a single match element (usually an <a> tag).
    
    Args:
        element: BeautifulSoup element for the match
        
    Returns:
        Dictionary with match details
    """
    try:
        match_url = element.get('href', '')
        full_match_url = f"https://www.fotmob.com{match_url}" if match_url else None
        
        # 1. Date
        date_elem = element.find('span', class_=lambda x: x and 'StartDate' in str(x))
        date_str = date_elem.get_text(strip=True) if date_elem else ""
        
        # 2. League
        league_elem = element.find('span', class_=lambda x: x and 'LeagueName' in str(x))
        league_name = league_elem.get_text(strip=True) if league_elem else ""
        
        # 3. Teams
        # Usually distinct team names are in spans with 'TeamName' in class
        team_name_elems = element.find_all('span', class_=lambda x: x and 'TeamName' in str(x))
        
        home_team = "Unknown"
        away_team = "Unknown"
        
        if len(team_name_elems) >= 2:
            home_team = team_name_elems[0].get_text(strip=True)
            away_team = team_name_elems[1].get_text(strip=True)
            
        # 4. Score or Time
        score_elem = element.find('span', class_=lambda x: x and 'ScoreSpan' in str(x))
        time_elem = element.find('div', class_=lambda x: x and 'TimeCSS' in str(x))
        
        status = "Scheduled"
        score = None
        match_time = None
        
        if score_elem:
            status = "Finished"
            score = score_elem.get_text(strip=True)
        elif time_elem:
            match_time = time_elem.get_text(strip=True)
            # Clean up time string (sometimes has nested spans)
            
        return {
            "date": date_str,
            "league": league_name,
            "home_team": home_team,
            "away_team": away_team,
            "status": status,
            "score": score,
            "time": match_time,
            "url": full_match_url
        }
        
    except Exception as e:
        print(f"Error parsing match element: {e}")
        return None


def main():
    """Main function to run the scraper."""
    import os
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    input_dir = script_dir / "plan"  # Input HTML files are in the plan subdirectory
    output_dir = script_dir  # Output JSON files to main directory
    
    # Process table-all.txt (All matches standings)
    table_all_file = input_dir / "table-all.txt"
    if table_all_file.exists():
        print("Processing table-all.txt...")
        html_content = load_html_from_file(table_all_file)
        
        # Parse all standings
        all_standings = parse_standings_from_html(html_content)
        save_to_json(all_standings, "standings_all.json")
        
        # Extract Persib-specific data
        persib_standings = extract_persib_standings(all_standings)
        save_to_json(persib_standings, "persib_standings.json")
    else:
        print(f"File not found: {table_all_file}")
    
    # Process table-home.txt if exists
    table_home_file = input_dir / "table-home.txt"
    if table_home_file.exists():
        print("Processing table-home.txt...")
        html_content = load_html_from_file(table_home_file)
        home_standings = parse_standings_from_html(html_content)
        save_to_json(home_standings, "standings_home.json")
    
    # Process table-away.txt if exists
    table_away_file = input_dir / "table-away.txt"
    if table_away_file.exists():
        print("Processing table-away.txt...")
        html_content = load_html_from_file(table_away_file)
        away_standings = parse_standings_from_html(html_content)
        save_to_json(away_standings, "standings_away.json")

    # Process fixtures.txt if exists
    fixtures_file = input_dir / "fixtures.txt"
    if fixtures_file.exists():
        print("Processing fixtures.txt...")
        html_content = load_html_from_file(fixtures_file)
        fixtures_data = parse_fixtures_from_html(html_content)
        save_to_json(fixtures_data, "fixtures.json")
    
    # Process top stats
    stats_files = {
        "goals": "goal.txt",
        "assists": "assist.txt",
        "goals_assists": "goal-assist.txt",
        "yellow_cards": "yellow-cards.txt",
        "red_cards": "red-cards.txt"
    }
    
    top_stats = {
        "scraped_at": datetime.now().isoformat(),
        "stats": {}
    }
    
    has_stats = False
    for stat_type, filename in stats_files.items():
        file_path = input_dir / filename
        if file_path.exists():
            print(f"Processing {filename}...")
            html_content = load_html_from_file(file_path)
            stats_list = parse_top_stats_from_html(html_content, stat_type)
            top_stats["stats"][stat_type] = stats_list
            has_stats = True
        else:
            print(f"File not found: {filename} (skipping {stat_type})")
            
    if has_stats:
        save_to_json(top_stats, "top_stats.json")

    print("\nDone! JSON files created.")


def parse_top_stats_from_html(html_content: str, stat_type: str) -> list:
    """
    Parse top player stats from FotMob HTML content.
    
    Args:
        html_content: Raw HTML string
        stat_type: Type of statistic (e.g., 'goals', 'assists')
        
    Returns:
        List of player statistics
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    stats_list = []
    
    # Find all table rows
    # Rows usually have "LeagueSeasonStatsTableRowCSS" in their class
    rows = soup.find_all(['div', 'a'], class_=lambda x: x and 'LeagueSeasonStatsTableRowCSS' in str(x))
    
    for row in rows:
        player_data = parse_player_stat_row(row, stat_type)
        if player_data:
            stats_list.append(player_data)
            
    return stats_list


def parse_player_stat_row(row, stat_type: str) -> dict:
    """
    Parse a single player row from the top stats table.
    """
    try:
        # 1. Rank
        rank_elem = row.find('span', class_=lambda x: x and 'Rank' in str(x))
        rank = int(rank_elem.get_text(strip=True)) if rank_elem else 0
        
        # 2. Player Name
        name_elem = row.find('span', class_=lambda x: x and 'TeamOrPlayerName' in str(x))
        name = name_elem.get_text(strip=True) if name_elem else "Unknown"
        
        # 3. Stat Value
        value_elem = row.find('span', class_=lambda x: x and 'StatValue' in str(x))
        value = 0
        if value_elem:
            # value might be in a nested span
            val_text = value_elem.get_text(strip=True)
            if val_text.isdigit():
                value = int(val_text)
        
        # 4. Player ID and Image
        player_url = row.get('href', '') if row.name == 'a' else ''
        if not player_url:
            link = row.find('a')
            if link:
                player_url = link.get('href', '')
                
        player_id = ""
        if player_url:
            # /players/12345/name
            match = re.search(r'/players/(\d+)/', player_url)
            if match:
                player_id = match.group(1)
                
        img_elem = row.find('img', class_=lambda x: x and 'PlayerImage' in str(x))
        player_image = img_elem.get('src', '') if img_elem else ""
        
        # 5. Team Logo/ID (optional, usually small icon)
        team_img_elem = row.find('img', class_=lambda x: x and 'TeamIcon' in str(x))
        team_image = team_img_elem.get('src', '') if team_img_elem else ""
        
        # 6. Sub-stat (e.g. Penalty goals)
        sub_stat = None
        sub_stat_elem = row.find('span', class_=lambda x: x and 'SubStat' in str(x))
        if sub_stat_elem:
            sub_stat = sub_stat_elem.get_text(strip=True)

        return {
            "rank": rank,
            "player": {
                "id": player_id,
                "name": name,
                "image": player_image,
                "url": f"https://www.fotmob.com{player_url}" if player_url else None
            },
            "team_logo": team_image,
            "value": value,
            "sub_stat": sub_stat,
            "type": stat_type
        }
        
    except Exception as e:
        print(f"Error parsing player stat row: {e}")
        return None


if __name__ == "__main__":
    main()
