from playwright.sync_api import sync_playwright
import json
import time
import logging
import os
import datetime
import re
from supabase import create_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

logging.info("Script started at %s", time.strftime("%H:%M:%S"))

# Initialize Supabase client with hardcoded credentials
SUPABASE_URL = "https://uaihjkawqvhrcozxvvpd.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVhaWhqa2F3cXZocmNvenh2dnBkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzkzMTA4MTUsImV4cCI6MjA1NDg4NjgxNX0.mM1QqSxDbJt8LChJYJDlvXGqHMM22ZvvvodkdtuSqsc"

# Import requests for direct API calls
import requests

# Create Supabase client - we'll use direct REST API calls to bypass RLS
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
logging.info("Supabase client initialized with hardcoded credentials")

# Debug mode removed
DEBUG_MODE = False  # Debug functionality has been removed
    
# Helper function to take screenshots in debug mode
def take_screenshot(page, filename):
    """
    Placeholder function that does nothing - screenshots disabled
    """
    pass

# Function to save data to database
def save_to_database(data, odds_type):
    """Save the scraped data to the Supabase database"""
    batch_data = []

    # Prepare data for batch insert
    for league_name, matches in data.items():
        # Clean up the league name - extract just the main part
        clean_league_name = league_name
        
        # If the league name contains numbers or odds column headers, clean it up
        if '\n' in league_name:
            # Take only the first line which should be the actual league name
            clean_league_name = league_name.split('\n')[0].strip()
        
        # Remove any event count numbers that might be at the end
        clean_league_name = re.sub(r'\s+\d+$', '', clean_league_name)
        
        # Remove odds column headers if present
        odds_headers = ['1', 'X', '2', 'Yes', 'No', 'No goal']
        for header in odds_headers:
            if clean_league_name.endswith(header):
                clean_league_name = clean_league_name.replace(header, '').strip()
        
        logging.info(f"Cleaned league name from '{league_name}' to '{clean_league_name}'")
        
        for match in matches:
            # Get current timestamp in ISO format
            current_time = datetime.datetime.now().isoformat()

            batch_data.append({
                "league_name": clean_league_name,
                "team1": match.get('team1'),
                "team2": match.get('team2'),
                "over_odds": match.get('Over'),
                "under_odds": match.get('Under'),
                "home_odds": match.get('1'),
                "draw_odds": match.get('X'),
                "away_odds": match.get('2'),
                "btts_yes": match.get('BTTS_Yes'),
                "btts_no": match.get('BTTS_No'),
                "odds_type": odds_type,
                "created_at": current_time
            })

    try:
        # Insert data directly into Supabase table with RLS bypass
        if batch_data:
            import requests
            import json as json_lib
            
            # Direct REST API call to bypass RLS policies
            url = f"{SUPABASE_URL}/rest/v1/football_odds"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            
            logging.info(f"Inserting {len(batch_data)} records directly to Supabase for odds type {odds_type}")
            response = requests.post(url, headers=headers, data=json_lib.dumps(batch_data))
            
            if response.status_code == 201:
                logging.info(f"Successfully saved {len(batch_data)} records to Supabase for odds type {odds_type}")
            else:
                logging.error(f"Failed to save to Supabase: Status {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to save to Supabase: {response.text}")
        else:
            logging.warning(f"No data to save for odds type {odds_type}")
    except Exception as e:
        logging.error(f"Error saving to Supabase: {e}")
        raise  # Raise the exception to stop script execution if database save fails

def extract_team_names(match, match_index):
    """Extract team names from a match element."""
    team1 = None
    team2 = None
    
    # Try to get team names from Angular components
    try:
        team_components = match.locator("asw-mini-scoreboard-competitors, [class*='team-name'], [class*='competitor'], [class*='team'], span.name, div.name").all()
        if team_components and len(team_components) >= 2:
            try:
                team1 = team_components[0].inner_text().strip()
                team2 = team_components[1].inner_text().strip()
                
                # Validate team names - make sure they don't contain date/time terms
                if (team1 and team2 and
                    not any(term in team1.lower() for term in ['today', 'tomorrow', 'yesterday', 'starts', 'min']) and
                    not any(term in team2.lower() for term in ['today', 'tomorrow', 'yesterday', 'starts', 'min'])):
                    logging.info(f"Found teams using Angular components: {team1} vs {team2}")
                    return team1, team2
            except Exception as e:
                logging.warning(f"Error extracting team names from components: {e}")
    except Exception as e:
        logging.warning(f"Error finding team components: {e}")

    # Try to get the inner text of the match element
    try:
        text = match.inner_text()
        logging.info(f"Match text: {text[:100]}..." if len(text) > 100 else f"Match text: {text}")
        
        # Direct approach for the most common format: first two lines are team names
        # This is the most reliable for many betting sites
        lines = text.strip().split('\n')
        if len(lines) >= 2:
            first_line = lines[0].strip()
            second_line = lines[1].strip()
            
            # Check if these look like team names (not too long, not containing odds values)
            if (first_line and second_line and
                len(first_line) <= 30 and len(second_line) <= 30 and
                not first_line.isdigit() and not second_line.isdigit() and
                not re.search(r'\d\.\d', first_line) and not re.search(r'\d\.\d', second_line) and
                not re.search(r'\d{2}:\d{2}', first_line) and not re.search(r'\d{2}:\d{2}', second_line) and
                not re.search(r'\d{1,2}/\d{1,2}', first_line) and not re.search(r'\d{1,2}/\d{1,2}', second_line) and
                not any(term in first_line.lower() for term in ['today', 'tomorrow', 'yesterday', 'starts in', 'min']) and
                not any(term in second_line.lower() for term in ['today', 'tomorrow', 'yesterday', 'starts in', 'min'])):
                logging.info(f"Extracted teams from first two lines directly: {first_line} vs {second_line}")
                return first_line, second_line
        
        # If direct approach failed, try more sophisticated filtering
        # Most reliable approach: The first two non-empty lines that look like team names
        clean_lines = []
        for line in lines:
            line = line.strip()
            if line and len(line) > 1:  # Non-empty lines with meaningful content
                # Skip lines that are clearly not team names
                if (not line.isdigit() and 
                    not re.search(r'\d{2}:\d{2}', line) and  # Skip times
                    not re.search(r'\d{1,2}/\d{1,2}', line) and  # Skip dates
                    not re.match(r'^\d+\.\d+$', line) and  # Skip odds values (e.g., 1.75, 3.20)
                    not re.search(r'\d+\s*(min|st half|nd half)', line.lower()) and  # Skip match status
                    not re.search(r'starts\s+in', line.lower()) and  # Skip "starts in" lines
                    not any(term in line.lower() for term in ['today', 'tomorrow', 'yesterday', 'am', 'pm',
                                                             'odds', 'prize', 'draw', 'jackpot', 'lotto', '>>', 'not started']) and
                    not re.search(r'^[0-9]+$', line) and  # Skip lines with just numbers
                    not re.search(r'^[0-9]+:[0-9]+$', line)):  # Skip score lines
                    clean_lines.append(line)
        
        # If we have at least 2 clean lines, the first two are likely team names
        if len(clean_lines) >= 2:
            team1 = clean_lines[0]
            team2 = clean_lines[1]
            # Verify these look like team names (not too long, not containing odds values)
            if (len(team1) <= 30 and len(team2) <= 30 and
                not re.search(r'\d\.\d', team1) and not re.search(r'\d\.\d', team2)):
                logging.info(f"Extracted teams from first two clean lines: {team1} vs {team2}")
                return team1, team2
                
        # If the above approach didn't work, try more selective filtering
        potential_team_lines = []
        for line in lines:
            line = line.strip()
            # Skip empty lines, dates, times, odds values, and lines with special characters
            if (line and 
                not line.isdigit() and 
                not re.search(r'\d{2}:\d{2}', line) and  # Skip times
                not re.search(r'\d{1,2}/\d{1,2}', line) and  # Skip dates
                not re.match(r'^\d+\.\d+$', line) and  # Skip odds values (e.g., 1.75, 3.20)
                not any(term in line.lower() for term in ['today', 'tomorrow', 'yesterday', 'starts in', 'min', 'odds', 
                                                         'prize', 'draw', 'jackpot', 'lotto', '>>', 'am', 'pm', 'not started', 
                                                         'league', 'bundesliga', 'premier', 'serie', 'ligue', 'laliga', 
                                                         'relegation', 'playoffs', 'championship', 'england', 'spain', 
                                                         'italy', 'germany', 'france', 'austria', 'scotland', 'denmark', 
                                                         'sweden', 'norway', 'netherlands', 'belgium', 'portugal', 'türkiye',
                                                         '1st half', '2nd half', 'half time']) and
                len(line.split()) <= 3 and  # Team names are typically 1-3 words
                len(line) <= 30):  # Team names are typically not too long
                # Additional check to ensure we don't get odds values as team names
                if not re.search(r'\d\.\d', line):
                    potential_team_lines.append(line)
        
        if len(potential_team_lines) >= 2:
            team1 = potential_team_lines[0]
            team2 = potential_team_lines[1]
            logging.info(f"Extracted teams from lines: {team1} vs {team2}")
            return team1, team2
        
        # Try to find a pattern like "Team1 - Team2" or "Team1 vs Team2"
        # This is common in many betting sites
        for line in lines:
            # Look for patterns like "Team1 - Team2" or "Team1 vs Team2" or "Team1 @ Team2"
            match_pattern = re.search(r'(.+?)(?:\s*[-vs@]\s*|\s+(?:vs|at|@)\s+)(.+)', line, re.IGNORECASE)
            if match_pattern:
                team1 = match_pattern.group(1).strip()
                team2 = match_pattern.group(2).strip()
                
                # Remove any odds or scores that might be part of the team name
                team1 = re.sub(r'\s+\d+\.\d+\s*$', '', team1)  # Remove trailing odds
                team2 = re.sub(r'\s+\d+\.\d+\s*$', '', team2)  # Remove trailing odds
                team1 = re.sub(r'\s+\d+:\d+\s*$', '', team1)  # Remove trailing scores
                team2 = re.sub(r'\s+\d+:\d+\s*$', '', team2)  # Remove trailing scores
                
                # Validate the team names
                if (team1 and team2 and 
                    not any(term in team1.lower() for term in ['today', 'tomorrow', 'yesterday', 'starts']) and
                    not any(term in team2.lower() for term in ['today', 'tomorrow', 'yesterday', 'starts']) and
                    not team1.isdigit() and not team2.isdigit() and
                    len(team1) <= 30 and len(team2) <= 30):  # Team names shouldn't be too long
                    logging.info(f"Extracted teams from pattern: {team1} vs {team2}")
                    return team1, team2
        
        # Try one more approach - look for any text that might be team names
        try:
            # Get all text nodes in the match element
            all_text_nodes = match.evaluate("Array.from(document.querySelectorAll('*')).filter(el => el.childNodes.length === 1 && el.childNodes[0].nodeType === 3).map(el => el.textContent.trim()).filter(text => text.length > 0)")
            
            # Filter potential team names
            potential_teams = []
            for text_node in all_text_nodes:
                if (text_node and isinstance(text_node, str) and
                    len(text_node) >= 2 and len(text_node) <= 30 and
                    not text_node.isdigit() and
                    not re.search(r'\d{2}:\d{2}', text_node) and
                    not re.search(r'\d{1,2}/\d{1,2}', text_node) and
                    not re.match(r'^\d+\.\d+$', text_node) and
                    not re.search(r'\d+\s*(min|st half|nd half)', text_node.lower()) and
                    not any(term in text_node.lower() for term in ['today', 'tomorrow', 'yesterday', 'am', 'pm', 'odds', 'prize'])):
                    potential_teams.append(text_node)
            
            if len(potential_teams) >= 2:
                team1 = potential_teams[0]
                team2 = potential_teams[1]
                logging.info(f"Extracted teams from text nodes: {team1} vs {team2}")
                return team1, team2
        except Exception as e:
            logging.error(f"Error in last attempt to extract team names: {e}")
        
        # Try to find team names in the DOM structure
        try:
            # Look for elements with specific selectors that are likely to contain team names
            # This is a more comprehensive selector that targets elements commonly used for team names
            team_elements = match.locator('span.ng-star-inserted, [class*="team"], [class*="competitor"], div.name, span.name, .event-name, .match-name, .team-name, .participant, .competitor').all()
            
            # Filter out elements that are not likely to be team names
            filtered_team_elements = []
            for elem in team_elements:
                try:
                    text = elem.inner_text().strip()
                    # Clean up the text - remove any odds or scores
                    text = re.sub(r'\s+\d+\.\d+\s*$', '', text)  # Remove trailing odds
                    text = re.sub(r'\s+\d+:\d+\s*$', '', text)  # Remove trailing scores
                    
                    if (text and 
                        not text.isdigit() and 
                        not re.search(r'\d{2}:\d{2}', text) and  # Skip times
                        not re.search(r'\d{1,2}/\d{1,2}', text) and  # Skip dates
                        not re.match(r'^\d+\.\d+$', text) and  # Skip odds values
                        not re.search(r'\d+\s*(min|st half|nd half)', text.lower()) and  # Skip match status
                        not re.search(r'starts\s+in', text.lower()) and  # Skip "starts in" lines
                        not any(term in text.lower() for term in ['today', 'tomorrow', 'yesterday', 'am', 'pm',
                                                                'odds', 'prize', 'draw', 'jackpot', 'lotto',
                                                                'bet', 'win', 'lose', 'tie', 'push']) and
                        len(text) <= 30 and  # Team names are typically not too long
                        len(text) >= 2):  # Team names should have at least 2 characters
                        # Don't add duplicates
                        if text not in filtered_team_elements:
                            filtered_team_elements.append(text)
                except Exception:
                    continue
            
            # If we have at least 2 filtered elements, use the first two as team names
            if len(filtered_team_elements) >= 2:
                team1 = filtered_team_elements[0]
                team2 = filtered_team_elements[1]
                # Validate the team names
                if (team1 and team2 and 
                    not any(term in team1.lower() for term in ['today', 'tomorrow', 'yesterday', 'starts']) and
                    not any(term in team2.lower() for term in ['today', 'tomorrow', 'yesterday', 'starts']) and
                    not team1.isdigit() and not team2.isdigit() and
                    team1.lower() != team2.lower()):  # Team names should be different
                    logging.info(f"Extracted teams from elements: {team1} vs {team2}")
                    return team1, team2
        except Exception as e:
            logging.error(f"Error extracting team names from elements: {e}")
        
        # If we still couldn't extract team names, use better placeholders
        fallback_team1 = f"Unknown Team 1"
        fallback_team2 = f"Unknown Team 2"
        logging.warning(f"Could not extract team names, using placeholders: {fallback_team1} vs {fallback_team2}")
        return fallback_team1, fallback_team2
    
    except Exception as e:
        logging.error(f"Error extracting team names: {e}")
        return f"Unknown Team 1", f"Unknown Team 2"

def extract_odds(match, selector_used):
    """
    Extract odds from a match element.
    """
    odds = {
        '1': None,      # Home win
        'X': None,      # Draw
        '2': None,      # Away win
        'Over': None,   # Over 2.5 goals
        'Under': None,  # Under 2.5 goals
        'BTTS_Yes': None,  # Both teams to score - Yes
        'BTTS_No': None    # Both teams to score - No
    }
    
    # Set a shorter timeout for operations
    try:
        page = match.page
        original_timeout = 30000  # Default Playwright timeout is 30 seconds
        page.set_default_timeout(5000)  # 5 seconds timeout
    except Exception as e:
        logging.warning(f"Could not set timeout in extract_odds: {e}")
        original_timeout = None
    
    try:
        # First, try to extract all numbers from the match text to find potential odds
        try:
            match_text = match.inner_text()
            # Find all decimal numbers (potential odds)
            all_numbers = re.findall(r'\b(\d+\.\d+)\b', match_text)
            all_numbers = [float(n) for n in all_numbers]
            
            # If we have enough numbers, they're likely odds
            if len(all_numbers) >= 3:
                logging.info(f"Found {len(all_numbers)} potential odds values in text")
                
                # Filter to keep only numbers that look like odds (typically between 1.01 and 30.0)
                odds_values = [n for n in all_numbers if 1.01 <= n <= 30.0]
                
                # Assign odds in order if we have enough values
                if len(odds_values) >= 3:
                    # First 3 values are typically 1X2 odds
                    odds['1'] = odds_values[0]
                    odds['X'] = odds_values[1]
                    odds['2'] = odds_values[2]
                    logging.info(f"Assigned 1X2 odds from text: {odds['1']}/{odds['X']}/{odds['2']}")
                
                # If we have more values, they might be Over/Under and BTTS odds
                if len(odds_values) >= 5:
                    odds['Over'] = odds_values[3]
                    odds['Under'] = odds_values[4]
                    logging.info(f"Assigned Over/Under odds from text: {odds['Over']}/{odds['Under']}")
                
                if len(odds_values) >= 7:
                    odds['BTTS_Yes'] = odds_values[5]
                    odds['BTTS_No'] = odds_values[6]
                    logging.info(f"Assigned BTTS odds from text: {odds['BTTS_Yes']}/{odds['BTTS_No']}")
                
                # If we have all the odds we need, return early
                if all(value is not None for value in odds.values()):
                    return odds
            
        except Exception as e:
            logging.warning(f"Error extracting odds from text: {e}")
        
        # Try multiple approaches to find odds
        
        # Approach 1: Look for specific odds elements
        for selector in [
            "button.odds-button",
            "span[class*='odd'], div[class*='odd']",
            "span[class*='price'], div[class*='price']",
            "span.ng-star-inserted"
        ]:
            try:
                odds_elements = match.locator(selector).all()
                if len(odds_elements) >= 3:
                    # Filter elements to only include those with numeric values
                    valid_odds = []
                    for elem in odds_elements:
                        text = elem.inner_text().strip()
                        if re.match(r'^\d+\.\d+$', text):
                            valid_odds.append(text)
                    
                    if len(valid_odds) >= 3:
                        odds['1'] = valid_odds[0]
                        odds['X'] = valid_odds[1]
                        odds['2'] = valid_odds[2]
                        logging.info(f"Assigned 1X2 odds from elements: {odds['1']}/{odds['X']}/{odds['2']}")
                        
                        if len(valid_odds) >= 5:
                            odds['Over'] = valid_odds[3]
                            odds['Under'] = valid_odds[4]
                            logging.info(f"Assigned Over/Under odds from elements: {odds['Over']}/{odds['Under']}")
                            
                            if len(valid_odds) >= 7:
                                odds['BTTS_Yes'] = valid_odds[5]
                                odds['BTTS_No'] = valid_odds[6]
                                logging.info(f"Assigned BTTS odds from elements: {odds['BTTS_Yes']}/{odds['BTTS_No']}")
                        
                        return odds
            except Exception as e:
                logging.warning(f"Error getting odds elements with selector {selector}: {e}")
        
        # Approach 2: Extract from match text
        match_text = match.inner_text()
        potential_odds = re.findall(r'\b\d+\.\d+\b', match_text)
        logging.info(f"Found {len(potential_odds)} potential odds values in text")
        
        if len(potential_odds) >= 3:
            odds['1'] = potential_odds[0]
            odds['X'] = potential_odds[1]
            odds['2'] = potential_odds[2]
            logging.info(f"Assigned 1X2 odds from text: {odds['1']}/{odds['X']}/{odds['2']}")
            
            if len(potential_odds) >= 5:
                odds['Over'] = potential_odds[3]
                odds['Under'] = potential_odds[4]
                logging.info(f"Assigned Over/Under odds from text: {odds['Over']}/{odds['Under']}")
            
            if len(potential_odds) >= 7:
                odds['BTTS_Yes'] = potential_odds[5]
                odds['BTTS_No'] = potential_odds[6]
                logging.info(f"Assigned BTTS odds from text: {odds['BTTS_Yes']}/{odds['BTTS_No']}")
            
            return odds
        
        # Approach 3: Try to find odds in the parent element
        try:
            parent_text = match.evaluate("el => el.parentElement ? el.parentElement.innerText : ''")
            if parent_text:
                parent_odds = re.findall(r'\b\d+\.\d+\b', parent_text)
                logging.info(f"Found {len(parent_odds)} potential odds values in parent element")
                
                if len(parent_odds) >= 3:
                    odds['1'] = parent_odds[0]
                    odds['X'] = parent_odds[1]
                    odds['2'] = parent_odds[2]
                    logging.info(f"Assigned 1X2 odds from parent: {odds['1']}/{odds['X']}/{odds['2']}")
                
                    if len(parent_odds) >= 5:
                        odds['Over'] = parent_odds[3]
                        odds['Under'] = parent_odds[4]
                        logging.info(f"Assigned Over/Under odds from parent: {odds['Over']}/{odds['Under']}")
                
                    if len(parent_odds) >= 7:
                        odds['BTTS_Yes'] = parent_odds[5]
                        odds['BTTS_No'] = parent_odds[6]
                        logging.info(f"Assigned BTTS odds from parent: {odds['BTTS_Yes']}/{odds['BTTS_No']}")
                
                    return odds
        except Exception as e:
            logging.warning(f"Error extracting odds from parent element: {e}")
        
        # Approach 4: Try to extract from HTML content directly
        try:
            html_content = match.evaluate("el => el.outerHTML")
            # Look for patterns in the HTML that might indicate odds values
            all_odds_values = re.findall(r'data-odds="([\d\.]+)"', html_content)
            if len(all_odds_values) >= 3:
                odds['1'] = all_odds_values[0]
                odds['X'] = all_odds_values[1]
                odds['2'] = all_odds_values[2]
                logging.info(f"Assigned 1X2 odds from HTML attributes: {odds['1']}/{odds['X']}/{odds['2']}")
                
                if len(all_odds_values) >= 5:
                    odds['Over'] = all_odds_values[3]
                    odds['Under'] = all_odds_values[4]
                    
                    if len(all_odds_values) >= 7:
                        odds['BTTS_Yes'] = all_odds_values[5]
                        odds['BTTS_No'] = all_odds_values[6]
                
                return odds
                
            # Alternative pattern
            all_odds_values = re.findall(r'class="[^"]*odds[^"]*"[^>]*>([\d\.]+)<', html_content)
            if len(all_odds_values) >= 3:
                odds['1'] = all_odds_values[0]
                odds['X'] = all_odds_values[1]
                odds['2'] = all_odds_values[2]
                logging.info(f"Assigned 1X2 odds from HTML content: {odds['1']}/{odds['X']}/{odds['2']}")
                
                if len(all_odds_values) >= 5:
                    odds['Over'] = all_odds_values[3]
                    odds['Under'] = all_odds_values[4]
                    
                    if len(all_odds_values) >= 7:
                        odds['BTTS_Yes'] = all_odds_values[5]
                        odds['BTTS_No'] = all_odds_values[6]
                
                return odds
        except Exception as e:
            logging.warning(f"Error extracting odds from HTML: {e}")
        
        # If we still haven't found any odds, use placeholders
        if all(value is None for value in odds.values()):
            logging.warning("No odds values found, using placeholders")
            # We don't set placeholder values anymore, we'll just return None values
    
    except Exception as e:
        logging.warning(f"Error extracting odds: {e}")
        # We don't set placeholder values anymore, we'll just return None values
    
    # Reset timeout to original value if it was set
    if original_timeout is not None:
        try:
            page.set_default_timeout(original_timeout)
        except Exception:
            pass
    
    return odds

def expand_league(page, league, league_name):
    """
    Try multiple approaches to expand a league and confirm expansion
    Returns True if expansion was successful, False otherwise
    """
    # Take screenshot before expansion attempt
    take_screenshot(page, f"before_expand_{league_name.replace(' ', '_')}")
    
    # Check if the league has any events before trying to expand
    try:
        event_count_elem = league.locator("span[id*='eventCount']").first
        if event_count_elem:
            event_count_text = event_count_elem.inner_text()
            logging.info(f"League {league_name} has event count: {event_count_text}")
            if event_count_text == "0":
                logging.info(f"League {league_name} has 0 events, no expansion needed")
                return False
    except Exception as e:
        logging.warning(f"Could not check event count: {e}")
    
    # Try multiple approaches to expand the league
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            logging.info(f"Expansion attempt {attempt+1} for {league_name}")
            
            # Check if already expanded
            is_expanded = False
            try:
                # Try different ways to check if expanded
                is_expanded = league.evaluate('el => el.hasAttribute("expanded") || el.classList.contains("expanded") || getComputedStyle(el).height > "50px"')
            except Exception as e:
                logging.info(f"Could not check if expanded: {e}")
            
            if is_expanded:
                logging.info(f"League {league_name} is already expanded")
                # Even if it says it's expanded, we need to verify that match content is loaded
                break
                
            # Different click approaches based on attempt number
            if attempt == 0:
                # First try clicking the league itself
                league.click(force=True)  # Force click to bypass any overlays
                logging.info("Clicked league element directly")
            elif attempt == 1:
                # Try clicking the header/name
                header = league.locator("span, div.league-name, div.header").first
                header.click(force=True)
                logging.info("Clicked league header")
            else:
                # Try JavaScript click as last resort
                league.evaluate('el => el.click()')
                logging.info("Used JavaScript click")
            
            # Wait for expansion animation
            page.wait_for_timeout(5000)
            
            # Take screenshot after click
            take_screenshot(page, f"after_click_{league_name.replace(' ', '_')}_{attempt}")
            
            # Verify expansion worked
            try:
                is_expanded = league.evaluate('el => el.hasAttribute("expanded") || el.classList.contains("expanded") || getComputedStyle(el).height > "50px"')
                if is_expanded:
                    logging.info("League expansion confirmed")
                    break
                else:
                    logging.warning("League may not have expanded properly")
            except Exception as e:
                logging.warning(f"Could not verify expansion: {e}")
                
        except Exception as e:
            logging.warning(f"Expansion attempt {attempt+1} failed: {e}")
    
    # After expansion attempts, verify that match content is actually loaded
    # This is critical because sometimes the league appears expanded but content isn't loaded
    try:
        # HTML saving disabled
        
        # Wait for match content to appear with a timeout
        wait_selectors = [
            "asw-match-row", 
            "asw-match-card",
            "div.sports-grid-row",
            "div.match-element",
            "asw-mini-scoreboard",
            "div:has-text('vs')"
        ]
        
        # Try to find any match-related elements
        for selector in wait_selectors:
            try:
                # Check if any elements with this selector exist within the league
                elements = league.locator(selector).all()
                if elements and len(elements) > 0:
                    logging.info(f"Found {len(elements)} {selector} elements after expansion")
                    return True
            except Exception:
                continue
        
        # If we get here, we didn't find any match elements
        # Try scrolling within the league to trigger lazy loading
        try:
            height = league.evaluate("el => el.scrollHeight")
            for scroll_pos in range(0, height, 100):
                league.evaluate(f"el => el.scrollTo(0, {scroll_pos})")
                page.wait_for_timeout(200)  # Short wait between scrolls
            
            # After scrolling, check again for match elements
            for selector in wait_selectors:
                try:
                    elements = league.locator(selector).all()
                    if elements and len(elements) > 0:
                        logging.info(f"Found {len(elements)} {selector} elements after scrolling")
                        return True
                except Exception:
                    continue
        except Exception as e:
            logging.warning(f"Error during scroll: {e}")
    
    except Exception as e:
        logging.warning(f"Error verifying match content: {e}")
    
    # If we get here, we couldn't verify that match content is loaded
    logging.warning(f"Could not verify match content loaded for {league_name}")
    return False

def find_matches(page, league, league_name):
    """
    Find matches within a league element
    Returns a list of match elements
    """
    matches = []
    selector_used = "unknown"
    
    # Set a shorter timeout for operations to avoid long waits
    try:
        original_timeout = 30000  # Default Playwright timeout is 30 seconds
        page.set_default_timeout(10000)  # 10 seconds timeout
    except Exception as e:
        logging.warning(f"Could not set timeout: {e}")
        original_timeout = None
    
    # Check if the league has any events before trying to find matches
    try:
        # Reduce timeout to avoid long waits
        event_count_elem = league.locator("span[id*='eventCount']").first
        if event_count_elem:
            try:
                # Set a shorter timeout for inner_text
                page.set_default_timeout(5000)  # 5 seconds timeout
                event_count_text = event_count_elem.inner_text()
                page.set_default_timeout(30000)  # Reset to default
                
                if event_count_text == "0":
                    logging.info(f"League {league_name} has 0 events, skipping match search")
                    return [], "no-events"
            except Exception:
                # If we can't get the text, just continue
                logging.info(f"Could not get event count text for {league_name}, continuing anyway")
                page.set_default_timeout(30000)  # Reset to default
    except Exception as e:
        logging.warning(f"Could not check event count: {e}")
        # Continue anyway, we'll try to find matches
    
    # Try to ensure content is loaded by waiting and scrolling
    try:
        # Wait a moment for any dynamic content to load
        page.wait_for_timeout(2000)
        
        # Try scrolling within the league to trigger lazy loading
        try:
            height = league.evaluate("el => el.scrollHeight || 200")
            for scroll_pos in range(0, min(height, 1000), 100):
                league.evaluate(f"el => el.scrollTo ? el.scrollTo(0, {scroll_pos}) : null")
                page.wait_for_timeout(200)  # Short wait between scrolls
            logging.info(f"Scrolled through league {league_name} to trigger lazy loading")
        except Exception as e:
            logging.warning(f"Error during scroll: {e}")
    except Exception as e:
        logging.warning(f"Error during pre-search preparation: {e}")

    # Debug code removed

    # Try different selectors to find matches
    try:
        # First try page-level search for this league's matches
        # This is important because sometimes matches are not directly under the league element
        try:
            # Get the league ID if available
            league_id = league.evaluate("el => el.id || ''")
            if league_id:
                logging.info(f"League {league_name} has ID: {league_id}")

                # Try to find matches related to this league ID at the page level
                related_matches = page.locator(f"[data-league-id='{league_id}'], [data-category-id='{league_id}'], [data-group-id='{league_id}']").all()
                if related_matches and len(related_matches) > 0:
                    logging.info(f"Found {len(related_matches)} matches using league ID relation")
                    matches = related_matches
                    selector_used = "league-id-relation"
                    return matches, selector_used
        except Exception as e:
            logging.warning(f"Error during page-level search: {e}")

        # Try to find match elements using Angular-specific selectors
        # 1. Try to find match rows
        match_rows = league.locator("asw-match-row, .match-row, [id*='match'], [id*='event'], [class*='match'], [class*='event']").all()
        if match_rows and len(match_rows) > 0:
            # Filter out any rows that don't have enough content
            filtered_rows = []
            try:
                for match in match_rows:
                    try:
                        # Check if it has enough content to be a valid match
                        text = match.inner_text()
                        # Must have reasonable length and not be the league name itself
                        if len(text) > 20 and not text.startswith(league_name):
                            # Check if it contains numbers (likely odds)
                            if re.search(r'\d\.\d', text):
                                filtered_rows.append(match)
                    except Exception:
                        pass
                
                if filtered_rows and len(filtered_rows) > 0:
                    logging.info(f"Found {len(filtered_rows)} matches using asw-match-row selector")
                    matches = filtered_rows
                    selector_used = "asw-match-row"
                    return matches, selector_used
            except Exception as e:
                logging.warning(f"Error filtering match rows: {e}")
                
        # 1.5 Try to find match elements with a more aggressive approach
        try:
            # Look for any elements that contain team names and odds
            all_elements = league.locator("div, li, tr").all()
            potential_matches = []
            
            for element in all_elements:
                try:
                    text = element.inner_text()
                    # Must have reasonable length and not be the league name itself
                    if len(text) > 30 and not text.startswith(league_name):
                        # Check if it contains numbers (likely odds)
                        if re.search(r'\d\.\d', text) and re.search(r'\s+vs\s+|\n', text):
                            potential_matches.append(element)
                except Exception:
                    pass
            
            if potential_matches and len(potential_matches) > 0:
                logging.info(f"Found {len(potential_matches)} matches using aggressive selector")
                matches = potential_matches
                selector_used = "aggressive-search"
                return matches, selector_used
        except Exception as e:
            logging.warning(f"Error during aggressive match search: {e}")

        # 2. Try to find match cards
        match_cards = league.locator("asw-match-card, .match-card").all()
        if match_cards and len(match_cards) > 0:
            logging.info(f"Found {len(match_cards)} matches using asw-match-card selector")
            matches = match_cards
            selector_used = "asw-match-card"
            return matches, selector_used

        # 3. Try to find sports grid rows with odds buttons
        sports_grid_rows = league.locator("div.sports-grid-row:has(button), div[class*='sports-grid']:has(button), div[class*='event-row']:has(button)").all()
        if sports_grid_rows and len(sports_grid_rows) > 0:
            logging.info(f"Found {len(sports_grid_rows)} matches using sports-grid-row:has(button) selector")
            matches = sports_grid_rows
            selector_used = "sports-grid-row-with-buttons"
            return matches, selector_used

        # 4. Try to find match elements
        match_elements = league.locator("div.match-element, div[class*='match'], div[class*='event']").all()
        if match_elements and len(match_elements) > 0:
            logging.info(f"Found {len(match_elements)} matches using match-element selector")
            matches = match_elements
            selector_used = "match-element"
            return matches, selector_used

        # 5. Try to find sports grid rows (more general)
        sports_grid_rows = league.locator("div.sports-grid-row, div[class*='sports-grid-row'], div[class*='event-row']").all()
        if sports_grid_rows and len(sports_grid_rows) > 0:
            logging.info(f"Found {len(sports_grid_rows)} matches using sports-grid-row selector")
            matches = sports_grid_rows
            selector_used = "sports-grid-row"
            return matches, selector_used

        # 6. Try to find mini-scoreboard elements (common in Angular sports apps)
        scoreboard_elements = league.locator("asw-mini-scoreboard, [class*='scoreboard'], [class*='score']").all()
        if scoreboard_elements and len(scoreboard_elements) > 0:
            logging.info(f"Found {len(scoreboard_elements)} matches using scoreboard selector")
            matches = scoreboard_elements
            selector_used = "scoreboard"
            return matches, selector_used

        # 7. Try to find competitor elements (common in Angular sports apps)
        competitor_elements = league.locator("div:has(asw-mini-scoreboard-competitors), div:has([class*='competitor']), div:has([class*='team'])").all()
        if competitor_elements and len(competitor_elements) > 0:
            logging.info(f"Found {len(competitor_elements)} matches using competitors selector")
            matches = competitor_elements
            selector_used = "competitors"
            return matches, selector_used

        # 8. Try to find any divs that might contain match information
        potential_matches = league.locator("div:has(div > div > div)").all()
        if potential_matches and len(potential_matches) > 0:
            # Filter out divs that are too small or don't have enough content
            filtered_matches = []
            for match in potential_matches:
                try:
                    # Check if the div has enough content to be a match
                    text = match.inner_text()
                    # Only consider elements that have both team names and likely contain odds
                    if len(text) > 20 and ('vs' in text.lower() or ' - ' in text) and re.search(r'\b\d+\.\d+\b', text):
                        # Get bounding box to check element size
                        bounding_box = match.bounding_box()
                        # Only include elements with reasonable dimensions
                        if bounding_box and bounding_box['width'] > 150 and bounding_box['height'] > 50:
                            filtered_matches.append(match)
                except Exception:
                    pass

            if filtered_matches and len(filtered_matches) > 0:
                logging.info(f"Found {len(filtered_matches)} matches using filtered div selector")
                matches = filtered_matches
                selector_used = "filtered-div"
                return matches, selector_used

        # If we still haven't found matches, try a more generic approach
        logging.warning(f"No matches found in league {league_name} using specific selectors, trying generic approach")

        # Debug code removed


        try:
            # Get visible text of the league to use as a search term
            league_text = league.inner_text().strip()
            if league_text:
                # Find all elements on the page that might be matches
                page_elements = page.locator("div, tr, li").all()
                related_matches = []
                
                for element in page_elements:
                    try:
                        element_text = element.inner_text()
                        # Check if this element contains team names or odds
                        if ('vs' in element_text.lower() or ' - ' in element_text or 
                            re.search(r'\b\d+\.\d+\b', element_text)):
                            # Check if it's related to our league
                            if league_name.lower() in element_text.lower():
                                related_matches.append(element)
                    except Exception:
                        continue
                
                if related_matches and len(related_matches) > 0:
                    logging.info(f"Found {len(related_matches)} matches at page level related to {league_name}")
                    matches = related_matches
                    selector_used = "page-level-search"
                    return matches, selector_used
        except Exception as e:
            logging.warning(f"Error during page-level search: {e}")
        
        # 9. Try to find any elements that might contain team names (vs pattern)
        all_elements = league.locator("div, span, p, li, tr").all()
        vs_matches = []
        for element in all_elements:
            try:
                text = element.inner_text()
                if 'vs' in text.lower() or ' - ' in text:
                    # Check if this element has a reasonable size to be a match
                    bounding_box = element.bounding_box()
                    if bounding_box and bounding_box['width'] > 100 and bounding_box['height'] > 20:
                        vs_matches.append(element)
            except Exception:
                pass
        
        if vs_matches and len(vs_matches) > 0:
            logging.info(f"Found {len(vs_matches)} potential matches using 'vs' pattern")
            matches = vs_matches
            selector_used = "vs-pattern"
            return matches, selector_used
        
        # 10. Last resort: Try to find elements with decimal numbers (odds)
        odds_elements = []
        for element in all_elements:
            try:
                text = element.inner_text()
                # Look for patterns that might be odds (decimal numbers)
                if re.search(r'\b\d+\.\d+\b', text):
                    # Check if this element has a reasonable size
                    bounding_box = element.bounding_box()
                    if bounding_box and bounding_box['width'] > 100 and bounding_box['height'] > 20:
                        odds_elements.append(element)
            except Exception:
                pass
        
        if odds_elements and len(odds_elements) > 0:
            logging.info(f"Found {len(odds_elements)} potential matches using odds pattern")
            matches = odds_elements
            selector_used = "odds-pattern"
            return matches, selector_used
        
        # If we still haven't found matches, check if we need to click something to show matches
        try:
            # Look for buttons or tabs that might show matches
            match_tabs = league.locator("button:has-text('Matches'), a:has-text('Matches'), [role='tab']:has-text('Matches')").all()
            if match_tabs and len(match_tabs) > 0:
                logging.info(f"Found {len(match_tabs)} potential match tabs, trying to click")
                match_tabs[0].click()
                page.wait_for_timeout(3000)  # Wait for content to load
                
                # Try to find matches again after clicking
                return find_matches(page, league, league_name)
        except Exception as e:
            logging.warning(f"Error trying to click match tabs: {e}")
        
        # If we still haven't found matches, log a warning and return an empty list
        logging.warning(f"No matches found in league {league_name} using any selector")
        return [], "no-matches-found"
        
    except Exception as e:
        logging.error(f"Error finding matches in league {league_name}: {e}")
        # Reset timeout to original value if it was set
        if original_timeout is not None:
            try:
                page.set_default_timeout(original_timeout)
            except Exception as timeout_error:
                logging.warning(f"Could not reset timeout: {timeout_error}")
        return [], "error-finding-matches"
    
    # Reset timeout to original value if it was set
    if original_timeout is not None:
        try:
            page.set_default_timeout(original_timeout)
        except Exception as timeout_error:
            logging.warning(f"Could not reset timeout: {timeout_error}")
    return matches, selector_used


def process_league(page, league_elements, i, league_count, data):
    """
    Process a single league: expand it, collect data, then move to the next.
    """
    try:
        # Get the league element and name
        league = league_elements.nth(i)
        
        # First, scroll to make sure the league is visible in the viewport
        try:
            # Scroll the league into view
            league.scroll_into_view_if_needed()
            page.wait_for_timeout(1000)  # Wait after scrolling
            logging.info(f"Scrolled league {i+1} into view")
        except Exception as e:
            logging.warning(f"Error scrolling league into view: {e}")
        
        # Try to get the league name
        try:
            league_name_elem = league.locator("span.name, div.name, h3, h4, [class*='title'], [class*='header']").first
            league_name = league_name_elem.inner_text().strip()
            
            # Clean up the league name - remove any event count numbers
            league_name = re.sub(r'\s+\d+$', '', league_name)
            
            # If the league name contains newlines, take only the first line
            if '\n' in league_name:
                league_name = league_name.split('\n')[0].strip()
        except Exception:
            # If we can't get the name, use a placeholder with the index
            league_name = f"League {i+1}"
        
        logging.info(f"\nProcessing league {i+1}/{league_count}: {league_name}")
        
        # Check if the league has any events before trying to expand
        try:
            event_count_elem = league.locator("span[id*='eventCount']").first
            if event_count_elem:
                event_count_text = event_count_elem.inner_text()
                logging.info(f"League {league_name} has event count: {event_count_text}")
                if event_count_text == "0":
                    logging.info(f"League {league_name} has 0 events, skipping")
                    data[league_name] = []
                    return
        except Exception as e:
            logging.warning(f"Could not check event count: {e}")
        
        # For leagues that are later in the list, we need to make sure they're expanded
        # Try clicking directly on the league element first
        try:
            league.click(force=True)
            page.wait_for_timeout(2000)  # Wait after clicking
            logging.info(f"Clicked directly on league {league_name}")
        except Exception as e:
            logging.warning(f"Error clicking league directly: {e}")
        
        # Now try to expand the league if it's not already expanded
        expanded = expand_league(page, league, league_name)
        if not expanded:
            logging.warning(f"Could not expand league {league_name}, trying to process anyway")
            
            # One more attempt - try to click any visible element in the league
            try:
                elements = league.locator("div, span, h3, h4").all()
                for elem in elements[:5]:  # Try first 5 elements
                    try:
                        if elem.is_visible():
                            elem.click(force=True)
                            page.wait_for_timeout(2000)
                            logging.info(f"Clicked on visible element in league {league_name}")
                            break
                    except Exception:
                        continue
            except Exception as e:
                logging.warning(f"Error in final click attempt: {e}")
        
        # Find matches within the league
        match_elements, selector_used = find_matches(page, league, league_name)
        match_count = len(match_elements)
        
        if match_count == 0:
            logging.warning(f"No matches found for {league_name} after trying all selectors")
            
            # Try one more approach - look for matches at the page level
            try:
                # Get all elements that might be matches
                all_elements = page.locator("div, tr, li").all()
                potential_matches = []
                
                for element in all_elements:
                    try:
                        text = element.inner_text()
                        # Check if this element contains the league name and team names or odds
                        if league_name.lower() in text.lower() and ('vs' in text.lower() or ' - ' in text or 
                                                                     re.search(r'\b\d+\.\d+\b', text)):
                            potential_matches.append(element)
                    except Exception:
                        continue
                
                if potential_matches and len(potential_matches) > 0:
                    logging.info(f"Found {len(potential_matches)} potential matches at page level for {league_name}")
                    match_elements = potential_matches
                    match_count = len(match_elements)
                else:
                    # No matches found, store empty data
                    data[league_name] = []
                    return
            except Exception as e:
                logging.warning(f"Error during last resort page search: {e}")
                data[league_name] = []
                return
                
        logging.info(f"Found {match_count} matches in {league_name}")
        
        # Filter match elements to remove likely duplicates before processing
        filtered_match_elements = []
        seen_texts = set()
        
        # First pass: collect unique match elements based on their text content
        for j in range(match_count):
            try:
                match = match_elements[j]
                text = match.inner_text().strip()
                
                # Skip if this is just a league header with event count
                if re.search(r'^[\w\s,-]+\n\d+$', text.strip()) or re.match(r'^[\w\s,-]+,\s*[\w\s]+\n\d+$', text.strip()):
                    logging.info(f"Skipping league header element: {text}")
                    continue
                    
                # Skip elements that are too short to be matches
                if len(text.strip()) < 15:
                    logging.info(f"Skipping too short match text: {text}")
                    continue
                    
                # Skip elements that don't have any odds values (decimal numbers)
                if not re.search(r'\d\.\d', text):
                    logging.info(f"Skipping match without odds values: {text}")
                    continue
                
                # Use a hash of the text to identify unique matches
                text_hash = hash(text)
                if text_hash not in seen_texts and len(text) > 20:  # Only consider substantial content
                    seen_texts.add(text_hash)
                    filtered_match_elements.append(match)
            except Exception as e:
                logging.warning(f"Error during match filtering: {e}")
                
        logging.info(f"Filtered {match_count} matches down to {len(filtered_match_elements)} unique matches")
        
        # Process each unique match in this league
        match_data = []
        for j, match in enumerate(filtered_match_elements):
            try:
                match.scroll_into_view_if_needed()
                page.wait_for_timeout(500)  # Short wait to ensure element is loaded
                
                # Get match text for logging
                try:
                    match_text = match.inner_text()
                    logging.info(f"Match text: {match_text}")
                except Exception:
                    match_text = "<unable to get text>"

                # Extract team names using improved function
                team1, team2 = extract_team_names(match, j)

                # Extract odds
                odds_data = extract_odds(match, selector_used)
                
                # Skip matches with no odds data
                if not odds_data or not any(odds_data.values()):
                    logging.warning(f"No odds data found for match {j+1}, skipping")
                    continue
                
                # Create match data dictionary
                match_info = {
                    'team1': team1,
                    'team2': team2,
                    **odds_data  # Unpack odds data into the match info
                }
                
                # Add match data to the list
                match_data.append(match_info)
                logging.info(f"Added match data for {team1} vs {team2}")
                
            except Exception as e:
                logging.error(f"Error processing match {j+1}: {e}")
        
        # Store the match data for this league
        data[league_name] = match_data
        logging.info(f"Completed processing {league_name} with {len(match_data)} matches")
        
        # Try to collapse the league to save resources
        try:
            logging.info(f"Attempting to collapse league {league_name}")
            # Try clicking the league again to collapse it
            league.click(force=True)
            page.wait_for_timeout(1000)  # Short wait after collapse attempt
        except Exception as e:
            logging.warning(f"Error collapsing league: {e}")
            
    except Exception as e:
        logging.error(f"Error processing league {i+1}: {e}")
        # Ensure we have an entry for this league even if processing failed
        if league_name not in data:
            data[league_name] = []
        

        
        logging.info(f"Filtered {match_count} matches down to {len(filtered_match_elements)} unique matches")
        
        # Process each unique match in this league
        for j, match in enumerate(filtered_match_elements):
            try:
                match.scroll_into_view_if_needed()
                page.wait_for_timeout(500)  # Short wait to ensure element is loaded
                
                # Debug code removed
                
                # Get match text for logging
                try:
                    match_text = match.inner_text()
                    # Skip league headers with event counts
                    if re.search(r'^[\w\s,-]+\n\d+$', match_text.strip()) or re.match(r'^[\w\s,-]+,\s*[\w\s]+\n\d+$', match_text.strip()):
                        logging.info(f"Skipping league header element: {match_text}")
                        continue
                    
                    # Skip elements that are too short to be matches
                    if len(match_text.strip()) < 15:
                        logging.info(f"Skipping too short match text: {match_text}")
                        continue
                        
                    # Skip elements that don't have any odds values (decimal numbers)
                    if not re.search(r'\d\.\d', match_text):
                        logging.info(f"Skipping match without odds values: {match_text}")
                        continue
                        
                    logging.info(f"Match text: {match_text}")
                except Exception:
                    match_text = "<unable to get text>"

                # HTML saving disabled

                # Extract team names using improved function
                team1, team2 = extract_team_names(match, j)

                # Try to extract team names from the match text if we got placeholders
                if team1.startswith("Team1_") and team2.startswith("Team2_"):
                    try:
                        match_text = match.inner_text()
                        
                        # For Swisslos, the team names are typically the first two lines of the match text
                        # Let's extract them directly from the match text structure
                        
                        # First, split the text by lines and clean it
                        lines = [line.strip() for line in match_text.strip().split('\n') if line.strip()]
                        
                        # Approach 1: The first two non-empty lines are typically team names in Swisslos
                        if len(lines) >= 2:
                            # Get the first two non-empty lines that don't look like odds or dates
                            potential_team_lines = []
                            
                            for line in lines[:4]:  # Check only the first few lines
                                # Skip lines that look like odds, dates, times, or other non-team information
                                if (not line.isdigit() and 
                                    not re.search(r'\d{2}:\d{2}', line) and  # Skip times
                                    not re.search(r'\d{1,2}/\d{1,2}', line) and  # Skip dates
                                    not re.match(r'^\d+\.\d+$', line) and  # Skip odds values (e.g., 1.75, 3.20)
                                    not any(term in line.lower() for term in ['today', 'tomorrow', 'yesterday', 'starts in', 'min', 'odds', 
                                                                             'prize', 'draw', 'jackpot', 'lotto', '>>', 'am', 'pm', 'not started', 'half']) and
                                    len(line) <= 30 and  # Team names are typically not too long
                                    not re.search(r'\d\.\d', line)):  # Ensure it's not an odds value
                                    potential_team_lines.append(line)
                            
                            if len(potential_team_lines) >= 2:
                                team1 = potential_team_lines[0]
                                team2 = potential_team_lines[1]
                                logging.info(f"Extracted teams from lines: {team1} vs {team2}")
                                # Don't return, just break out of this approach
                                break
                        
                        # Approach 2: Try to extract using specific selectors for Swisslos
                        try:
                            # For matches 2, 3, 7, 8, 9 in Premier League, we need a more targeted approach
                            # These matches have a specific structure in the HTML
                            
                            # First, try to get team names from the match text directly
                            # In Swisslos, team names are often the first two lines of text
                            if len(lines) >= 2 and len(lines[0]) < 20 and len(lines[1]) < 20:
                                # Verify these look like team names (not odds or dates)
                                if (not re.search(r'\d\.\d', lines[0]) and not re.search(r'\d\.\d', lines[1]) and
                                    not any(term in lines[0].lower() for term in ['today', 'tomorrow', 'yesterday', 'starts']) and
                                    not any(term in lines[1].lower() for term in ['today', 'tomorrow', 'yesterday', 'starts'])):
                                    team1 = lines[0]
                                    team2 = lines[1]
                                    logging.info(f"Extracted teams from first two lines: {team1} vs {team2}")
                                    break
                            
                            # If that didn't work, try with specific selectors
                            selectors = [
                                "asw-mini-scoreboard-competitors",
                                "[class*='team-name']", 
                                "[class*='competitor']", 
                                "[class*='team']",
                                "span.name", 
                                "div.name",
                                "span.ng-star-inserted"
                            ]
                            
                            for selector in selectors:
                                team_elements = match.locator(selector).all()
                                if len(team_elements) >= 2:
                                    team1_candidate = team_elements[0].inner_text().strip()
                                    team2_candidate = team_elements[1].inner_text().strip()
                                    
                                    # Validate team names
                                    if (team1_candidate and team2_candidate and 
                                        not re.search(r'\d\.\d', team1_candidate) and not re.search(r'\d\.\d', team2_candidate) and
                                        not any(term in team1_candidate.lower() for term in ['today', 'tomorrow', 'yesterday', 'starts']) and
                                        not any(term in team2_candidate.lower() for term in ['today', 'tomorrow', 'yesterday', 'starts'])):
                                        team1 = team1_candidate
                                        team2 = team2_candidate
                                        logging.info(f"Extracted teams using selector {selector}: {team1} vs {team2}")
                                        break
                            
                            # If that didn't work, try to extract team names from the raw match text
                            # Look for the first two lines that look like team names
                            raw_lines = match_text.strip().split('\n')
                            potential_teams = []
                            
                            for line in raw_lines:
                                line = line.strip()
                                # Skip lines that don't look like team names
                                if (line and 
                                    not line.isdigit() and 
                                    not re.search(r'\d{2}:\d{2}', line) and
                                    not re.search(r'\d{1,2}/\d{1,2}', line) and
                                    not re.match(r'^\d+\.\d+$', line) and
                                    not re.search(r'\d\.\d', line) and
                                    len(line) < 20 and
                                    not any(term in line.lower() for term in ['today', 'tomorrow', 'yesterday', 'starts', 'min', 'half'])):
                                    potential_teams.append(line)
                            
                            if len(potential_teams) >= 2:
                                team1 = potential_teams[0]
                                team2 = potential_teams[1]
                                logging.info(f"Extracted teams from raw text: {team1} vs {team2}")
                        except Exception as e:
                            logging.warning(f"Error extracting teams using selectors: {e}")
                    except Exception as e:
                        logging.warning(f"Error extracting teams from text: {e}")

                # Create match info dictionary
                match_info = {
                    'team1': team1,
                    'team2': team2,
                    '1': None,      # Home win
                    'X': None,      # Draw
                    '2': None,      # Away win
                    'Over': None,   # Over 2.5 goals
                    'Under': None,  # Under 2.5 goals
                    'BTTS_Yes': None,  # Both teams to score - Yes
                    'BTTS_No': None    # Both teams to score - No
                }
                
                # Extract odds using improved function
                odds = extract_odds(match, selector_used)
                
                # Update match info with odds
                for key, value in odds.items():
                    if key in match_info:
                        match_info[key] = value
                
                # Check if we have at least some odds data
                has_odds = any(odds.values())
                
                # Only add the match if we have valid team names (not placeholders)
                if not (team1.startswith("Team1_") and team2.startswith("Team2_")):
                    # Check if this match is a duplicate (same teams)
                    is_duplicate = False
                    for existing_match in league_data:
                        # Check if the same teams exist in any order
                        if ((existing_match['team1'] == team1 and existing_match['team2'] == team2) or
                            (existing_match['team1'] == team2 and existing_match['team2'] == team1)):
                            is_duplicate = True
                            logging.info(f"Skipping duplicate match: {team1} vs {team2}")
                            break
                    
                    if not is_duplicate:
                        if has_odds:
                            league_data.append(match_info)
                            logging.info(f"Added match data for {team1} vs {team2}")
                        else:
                            logging.warning(f"Skipping match with no odds data: {team1} vs {team2}")
                else:
                    # If we have odds data but couldn't extract team names, try to use the league name
                    if has_odds and len(match_text) > 30:
                        # Use the league name as a prefix for the team names
                        team1 = f"{league_name}_Team1_{j+1}"
                        team2 = f"{league_name}_Team2_{j+1}"
                        match_info['team1'] = team1
                        match_info['team2'] = team2
                        league_data.append(match_info)
                        logging.info(f"Added match data with synthetic team names: {team1} vs {team2}")
                    else:
                        logging.warning(f"Skipping match with placeholder team names: {team1} vs {team2}")
                
            except Exception as e:
                logging.warning(f"Error processing match {j+1} in {league_name}: {str(e)}")
                continue
        
        # Store the league data
        data[league_name] = league_data
        logging.info(f"Completed processing {league_name} with {len(league_data)} matches")
        
        # Try to collapse the league if it was expanded
        if expanded:
            try:
                logging.info(f"Attempting to collapse league {league_name}")
                league.click()
                page.wait_for_timeout(2000)
            except Exception as e:
                logging.warning(f"Could not collapse league: {e}")
        
    except Exception as e:
        logging.error(f"Error processing league {i+1}/{league_count}: {str(e)}")
        data[league_name if 'league_name' in locals() else f"League_{i+1}"] = []

# Main script execution
logging.info("Initializing Playwright")
with sync_playwright() as p:
    # Launch browser in headful mode (visible browser window)
    logging.info("Launching browser in headful mode")
    browser = p.firefox.launch(headless=True)
    context = browser.new_context(viewport={'width': 1920, 'height': 1080})  # Set larger viewport
    page = context.new_page()

    # Take screenshot of initial state
    take_screenshot(page, "initial_state")

    # Navigate to the URL
    logging.info("Navigating to website")
    try:
        page.goto("https://www.swisslos.ch/en/sporttip/sports/football", timeout=600000)
        logging.info("Page loaded successfully")
        take_screenshot(page, "page_loaded")
    except Exception as e:
        logging.error(f"Error loading page: {e}")
        take_screenshot(page, "page_load_error")
        browser.close()
        raise

    # Try closing popup if it appears
    try:
        logging.info("Checking for popup")
        popup_selectors = [
            "#gb-form > div > button.btn.btn-secondary.gb-push-denied",
            "button.btn-close",
            "button.close",
            "[aria-label='Close']",
            "button:has-text('Close')",
            "button:has-text('No thanks')",
            "button:has-text('Reject')",
            "button:has-text('Later')"
        ]
        
        for selector in popup_selectors:
            try:
                popup = page.locator(selector)
                if popup.is_visible(timeout=2000):
                    logging.info(f"Popup detected with selector {selector}, closing")
                    popup.click()
                    logging.info("Popup closed")
                    break
            except Exception:
                continue
        else:
            logging.info("No popup detected or all close attempts failed")
    except Exception as e:
        logging.warning(f"Error handling popup: {e}")

    # Initialize data structure
    data = {}
    logging.info("Starting data collection")

    # Wait for content to load
    logging.info("Waiting for content to load")
    page.wait_for_timeout(5000)  # Longer wait for content
    take_screenshot(page, "after_initial_wait")
    
    # Try to find and set up filters
    try:
        # Look for filter dropdowns
        filter_selectors = [
            "#sportsSportsGrid_filter_col1_input",  # Original selector
            "[id*='filter_col1']",                # Partial ID
            "button:has-text('Select market')",    # Text-based
            ".dropdown-toggle",                   # Class-based
            "button.btn-filter"                   # Generic filter button
        ]
        
        # Try to find and click the first filter dropdown
        first_filter_clicked = False
        for selector in filter_selectors:
            try:
                filter_button = page.locator(selector).first
                if filter_button.is_visible(timeout=2000):
                    logging.info(f"Found first filter with selector: {selector}")
                    filter_button.click()
                    page.wait_for_timeout(2000)
                    take_screenshot(page, "after_first_filter_click")
                    first_filter_clicked = True
                    break
            except Exception as e:
                logging.warning(f"Error with filter selector {selector}: {e}")
        
        if not first_filter_clicked:
            logging.warning("Could not find or click any filter dropdown")
        
        # Try to select Over/Under 2.5 in the dropdown if it was opened
        if first_filter_clicked:
            try:
                # Look for Over/Under 2.5 option with multiple approaches
                ou_option_selectors = [
                    ".dropdown-menu.show .dropdown-item:has-text('Over/Under 2.5')",
                    ".dropdown-menu.show span:text-is('Over/Under 2.5')",
                    "li:has-text('Over/Under 2.5')",
                    "div:has-text('Over/Under 2.5')"
                ]
                
                for selector in ou_option_selectors:
                    try:
                        option = page.locator(selector).first
                        if option.is_visible(timeout=2000):
                            logging.info(f"Found Over/Under 2.5 option with selector: {selector}")
                            option.click()
                            page.wait_for_timeout(3000)
                            take_screenshot(page, "after_ou_option_selected")
                            break
                    except Exception:
                        continue
            except Exception as e:
                logging.warning(f"Error selecting Over/Under 2.5: {e}")
        
        # Try to find and click the second filter dropdown
        second_filter_clicked = False
        for selector in filter_selectors:
            try:
                # Skip the first filter we already clicked
                if first_filter_clicked:
                    filters = page.locator(selector).all()
                    if len(filters) > 1:
                        filter_button = filters[1]  # Use the second filter
                    else:
                        continue
                else:
                    filter_button = page.locator(selector).first
                    
                if filter_button.is_visible(timeout=2000):
                    logging.info(f"Found second filter with selector: {selector}")
                    filter_button.click()
                    page.wait_for_timeout(2000)
                    take_screenshot(page, "after_second_filter_click")
                    second_filter_clicked = True
                    break
            except Exception as e:
                logging.warning(f"Error with second filter selector {selector}: {e}")
        
        # Try to select Both teams score in the dropdown if it was opened
        if second_filter_clicked:
            try:
                # Look for Both teams score option with multiple approaches
                btts_option_selectors = [
                    "button[id*='Both teams score']",
                    ".dropdown-menu.show .dropdown-item:has-text('Both teams score')",
                    "li:has-text('Both teams score')",
                    "div:has-text('Both teams score')"
                ]
                
                for selector in btts_option_selectors:
                    try:
                        option = page.locator(selector).first
                        if option.is_visible(timeout=2000):
                            logging.info(f"Found Both teams score option with selector: {selector}")
                            option.click()
                            page.wait_for_timeout(3000)
                            take_screenshot(page, "after_btts_option_selected")
                            break
                    except Exception:
                        continue
            except Exception as e:
                logging.warning(f"Error selecting Both teams score: {e}")
    except Exception as e:
        logging.error(f"Error setting up filters: {e}")
    
    # Take screenshot of the page after filter setup
    take_screenshot(page, "after_filter_setup")
    
    # Try to find leagues with multiple selectors
    logging.info("Looking for leagues")
    league_selectors = [
        "asw-sports-grid-expandable",  # Original selector
        "div.league-container",        # Alternative 1
        "div[class*='league']",        # Alternative 2
        "div.accordion-item",          # Alternative 3 (common for expandable sections)
        "div[role='region']",          # Alternative 4
        "div.panel",                   # Alternative 5
        "section",                     # Alternative 6 (very generic)
        "div:has(h3, h4)",             # Alternative 7 (headers often indicate leagues)
        "div:has(div.match-container)" # Alternative 8 (containers with matches)
    ]
    
    league_elements = None
    league_count = 0
    selector_used = None
    
    for selector in league_selectors:
        try:
            league_elements = page.locator(selector)
            count = league_elements.count()
            if count > 0:
                logging.info(f"Found {count} leagues using selector: {selector}")
                league_count = count
                selector_used = selector
                break
            else:
                logging.info(f"No leagues found with selector: {selector}")
        except Exception as e:
            logging.warning(f"Error using league selector {selector}: {e}")
    
    if league_count == 0:
        logging.error("No leagues found with any selector")
        # Debug code removed
        # HTML saving disabled
    else:
        # Process each league one by one
        for i in range(league_count):
            # Process one league at a time
            process_league(page, league_elements, i, league_count, data)
            # Add a short delay between leagues to avoid overloading the page
            page.wait_for_timeout(1000)
    
        logging.info("Completed processing all leagues")
    
        # Save data to database
        logging.info("Saving data to database")
        save_to_database(data, "2.5_BTTS")  # For the combined 2.5 and BTTS data
    
        # No JSON files - data is only saved to Supabase database
        logging.info("Data successfully saved to Supabase database")
    
    # Take final screenshot
    take_screenshot(page, "final_state")
    
    logging.info("Closing browser")
    browser.close()
    logging.info("Script completed at %s", time.strftime("%H:%M:%S"))
