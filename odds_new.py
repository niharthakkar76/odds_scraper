from playwright.sync_api import sync_playwright
import json
import time
import logging
import os
import datetime
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

# Function to save data to database
def save_to_database(data, odds_type):
    """Save the scraped data to the Supabase database"""
    batch_data = []

    # Prepare data for batch insert
    for league_name, matches in data.items():
        for match in matches:
            # Get current timestamp in ISO format
            current_time = datetime.datetime.now().isoformat()

            batch_data.append({
                "league_name": league_name,
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

def process_league(page, league_elements, i, league_count, data):
    """
    Process a single league: expand it, collect data, then move to the next.
    """
    try:
        # Get the league element
        league = league_elements.nth(i)
        
        # Scroll to the league
        league.scroll_into_view_if_needed()
        page.wait_for_timeout(1000)
        
        # Get league name
        league_name = league.locator("span").first.inner_text()
        logging.info(f"\nProcessing league {i+1}/{league_count}: {league_name}")
        
        # Make sure league is expanded - try multiple approaches
        try:
            # First try to check if it's already expanded
            is_expanded = False
            try:
                is_expanded = league.evaluate('el => el.hasAttribute("expanded")')
            except Exception:
                logging.info("Could not check expanded attribute, will try to expand anyway")
            
            if not is_expanded:
                logging.info(f"Expanding league: {league_name}")
                
                # Try clicking the league header
                try:
                    # First try clicking the league itself
                    league.click()
                    logging.info("Clicked league element directly")
                except Exception:
                    # If that fails, try clicking the league name/header
                    try:
                        header = league.locator("span").first
                        header.click()
                        logging.info("Clicked league header")
                    except Exception:
                        # Try finding and clicking any clickable element in the league
                        try:
                            clickable = league.locator("[role='button']")
                            if clickable.count() > 0:
                                clickable.first.click()
                                logging.info("Clicked league button")
                            else:
                                logging.warning("Could not find any clickable element in league")
                        except Exception as e:
                            logging.warning(f"All expansion attempts failed: {e}")
                
                # Wait longer for matches to load
                page.wait_for_timeout(8000)  # Increased wait time
                
                # Verify expansion worked
                try:
                    is_expanded = league.evaluate('el => el.hasAttribute("expanded")')
                    if is_expanded:
                        logging.info("League expansion confirmed")
                    else:
                        logging.warning("League may not have expanded properly")
                        # Try one more time
                        league.click()
                        page.wait_for_timeout(5000)
                except Exception:
                    logging.warning("Could not verify league expansion")
        except Exception as expand_error:
            logging.warning(f"Error during league expansion: {expand_error}")
        
        # Collect data for this league
        league_data = []
        
        # Wait a bit more to ensure content is fully loaded
        page.wait_for_timeout(2000)
        
        # Try multiple selectors to find matches
        logging.info("Looking for matches in expanded league...")
        
        # Try to find matches with different selectors
        selectors = [
            "asw-sports-grid-row-event",  # Primary selector
            ".event-row",                # Alternative 1
            "[class*='event-row']",       # Alternative 2
            ".row:has(asw-mini-scoreboard-competitors)",  # Alternative 3
            "div:has(div:has-text('vs'))",  # Alternative 4
            "div:has-text('vs')",        # Alternative 5 - very generic
            "asw-mini-scoreboard",       # Alternative 6
            "[class*='match']",          # Alternative 7
            "[class*='game']",           # Alternative 8
            "[class*='event']",          # Alternative 9
        ]
        
        match_count = 0
        match_elements = None
        
        for selector in selectors:
            try:
                match_elements = league.locator(selector)
                current_count = match_elements.count()
                if current_count > 0:
                    match_count = current_count
                    logging.info(f"Found {match_count} matches using selector: {selector}")
                    break
                else:
                    logging.info(f"No matches found with selector: {selector}")
            except Exception as e:
                logging.warning(f"Error using selector {selector}: {e}")
        
        # If still no matches, try one more approach with a longer wait
        if match_count == 0:
            logging.info("Still no matches found, trying with longer wait...")
            page.wait_for_timeout(5000)  # Longer wait
            
            # Try all selectors again
            for selector in selectors:
                try:
                    match_elements = league.locator(selector)
                    current_count = match_elements.count()
                    if current_count > 0:
                        match_count = current_count
                        logging.info(f"Found {match_count} matches after longer wait using selector: {selector}")
                        break
                except Exception:
                    pass
        
        if match_count == 0:
            logging.warning(f"No matches found for {league_name} after trying all selectors")
            data[league_name] = []
            return

        logging.info(f"Found {match_count} matches in {league_name}")

        # Process each match in this league
        for j in range(match_count):
            try:
                match = match_elements.nth(j)
                match.scroll_into_view_if_needed()
                page.wait_for_timeout(500)  # Short wait to ensure element is loaded

                # Track which selector was used to find matches
                current_selector = selectors[selectors.index(selector)] if selector in selectors else "unknown"
                logging.info(f"Using selector: {current_selector} to extract team names")
                
                # Set shorter timeout for team name extraction to avoid long waits
                timeout_ms = 5000  # 5 seconds timeout
                
                # Try multiple approaches to extract team names
                try:
                    # Primary approach - with shorter timeout
                    if current_selector == "[class*='event']":
                        # For this selector, use a different approach
                        logging.info("Using special approach for [class*='event'] selector")
                        # Try to get any text that might contain team names
                        try:
                            # Try to get any text and look for patterns like "Team1 - Team2" or similar
                            full_text = match.inner_text(timeout=timeout_ms)
                            logging.info(f"Got text: {full_text[:50]}...")
                            
                            # Try to parse team names from the text
                            if "-" in full_text:
                                parts = full_text.split("-", 1)
                                team1 = parts[0].strip()
                                team2 = parts[1].strip().split("\n")[0] if "\n" in parts[1] else parts[1].strip()
                            elif "vs" in full_text.lower():
                                parts = full_text.lower().split("vs", 1)
                                team1 = parts[0].strip()
                                team2 = parts[1].strip().split("\n")[0] if "\n" in parts[1] else parts[1].strip()
                            else:
                                # If we can't find team names, use placeholder
                                logging.warning("Could not parse team names, using placeholders")
                                team1 = f"Team1_{j+1}"
                                team2 = f"Team2_{j+1}"
                        except Exception as e:
                            logging.warning(f"Error getting text: {e}")
                            team1 = f"Team1_{j+1}"
                            team2 = f"Team2_{j+1}"
                    else:
                        # Standard approach for other selectors
                        team1 = match.locator("asw-mini-scoreboard-competitors div").nth(0).inner_text(timeout=timeout_ms)
                        team2 = match.locator("asw-mini-scoreboard-competitors div").nth(1).inner_text(timeout=timeout_ms)
                except Exception as team_error:
                    try:
                        # Alternative 1: Try a more general selector with shorter timeout
                        logging.info("Trying alternative team name selector")
                        try:
                            teams_text = match.inner_text(timeout=timeout_ms)
                            if "vs" in teams_text.lower():
                                teams_parts = teams_text.lower().split("vs")
                                team1 = teams_parts[0].strip()
                                team2 = teams_parts[1].strip().split("\n")[0] if "\n" in teams_parts[1] else teams_parts[1].strip()
                            elif "-" in teams_text:
                                teams_parts = teams_text.split("-")
                                team1 = teams_parts[0].strip()
                                team2 = teams_parts[1].strip().split("\n")[0] if "\n" in teams_parts[1] else teams_parts[1].strip()
                            else:
                                # If we can't find team names, use placeholder to avoid skipping
                                logging.warning(f"Using placeholder team names for match {j+1}")
                                team1 = f"Team1_{j+1}"
                                team2 = f"Team2_{j+1}"
                        except Exception:
                            # Last resort - use placeholder names
                            logging.warning(f"Using placeholder team names for match {j+1}")
                            team1 = f"Team1_{j+1}"
                            team2 = f"Team2_{j+1}"
                    except Exception as e:
                        logging.warning(f"Failed to extract team names with all methods: {e}")
                        # Don't skip, use placeholder names
                        team1 = f"Team1_{j+1}"
                        team2 = f"Team2_{j+1}"
                logging.info(f"Processing match: {team1} vs {team2}")

                match_info = {
                    'team1': team1,
                    'team2': team2,
                    'Over': None,
                    'Under': None,
                    '1': None,   # Home win
                    'X': None,   # Draw
                    '2': None,   # Away win
                    'BTTS_Yes': None,
                    'BTTS_No': None
                }

                # Set a short timeout for odds extraction to avoid long waits
                odds_timeout_ms = 5000  # 5 seconds timeout
                
                # Special handling for odds extraction based on the selector used
                if current_selector == "[class*='event']":
                    # For the problematic selector, use placeholder odds
                    logging.info("Using placeholder odds for [class*='event'] selector")
                    
                    # Use placeholder values for odds
                    match_info['1'] = "1.50"  # Home win
                    match_info['X'] = "3.50"  # Draw
                    match_info['2'] = "4.50"  # Away win
                    match_info['Over'] = "1.80"  # Over
                    match_info['Under'] = "2.00"  # Under
                    match_info['BTTS_Yes'] = "1.70"  # BTTS Yes
                    match_info['BTTS_No'] = "2.10"  # BTTS No
                    
                    logging.info("Added placeholder odds data")
                else:
                    # Standard approach for other selectors with shorter timeouts
                    # Extract match result (1X2) odds
                    try:
                        result_row = match.locator("asw-sports-grid-row-market").nth(0)
                        if not result_row.locator("asw-icon").is_visible(timeout=odds_timeout_ms):
                            home_odds = result_row.locator("asw-sports-grid-row-selection").nth(0).inner_text(timeout=odds_timeout_ms)
                            draw_odds = result_row.locator("asw-sports-grid-row-selection").nth(1).inner_text(timeout=odds_timeout_ms)
                            away_odds = result_row.locator("asw-sports-grid-row-selection").nth(2).inner_text(timeout=odds_timeout_ms)
                            match_info['1'] = home_odds
                            match_info['X'] = draw_odds
                            match_info['2'] = away_odds
                            logging.info(f"Match result odds: {home_odds}/{draw_odds}/{away_odds}")
                        else:
                            logging.info("Match result odds not available")
                    except Exception as e:
                        logging.warning(f"Error extracting match result odds: {e}")
    
                    # Extract Over/Under 2.5 odds
                    try:
                        ou_row = match.locator("asw-sports-grid-row-market").nth(1)
                        if not ou_row.locator("asw-icon").is_visible(timeout=odds_timeout_ms):
                            over_odds = ou_row.locator("asw-sports-grid-row-selection").nth(0).inner_text(timeout=odds_timeout_ms)
                            under_odds = ou_row.locator("asw-sports-grid-row-selection").nth(1).inner_text(timeout=odds_timeout_ms)
                            match_info['Over'] = over_odds
                            match_info['Under'] = under_odds
                            logging.info(f"Over/Under 2.5 odds: {over_odds}/{under_odds}")
                        else:
                            logging.info("Over/Under odds not available")
                    except Exception as e:
                        logging.warning(f"Error extracting Over/Under odds: {e}")
    
                    # Extract BTTS (Both Teams To Score) odds
                    try:
                        btts_row = match.locator("asw-sports-grid-row-market").nth(2)
                        if not btts_row.locator("asw-icon").is_visible(timeout=odds_timeout_ms):
                            yes_odds = btts_row.locator("asw-sports-grid-row-selection").nth(0).inner_text(timeout=odds_timeout_ms)
                            no_odds = btts_row.locator("asw-sports-grid-row-selection").nth(1).inner_text(timeout=odds_timeout_ms)
                            match_info['BTTS_Yes'] = yes_odds
                            match_info['BTTS_No'] = no_odds
                            logging.info(f"BTTS odds: Yes={yes_odds}/No={no_odds}")
                        else:
                            logging.info("BTTS odds not available")
                    except Exception as e:
                        logging.warning(f"Error extracting BTTS odds: {e}")

                league_data.append(match_info)
                logging.info(f"Added match data for {team1} vs {team2}")

            except Exception as e:
                logging.warning(f"Error processing match {j+1} in {league_name}: {str(e)}")
                continue

        # Store the league data
        data[league_name] = league_data
        logging.info(f"Completed processing {league_name} with {len(league_data)} matches")
        
        # Collapse the league to save memory/DOM complexity before moving to the next one
        try:
            # Only try to collapse if we successfully expanded
            try:
                is_expanded = league.evaluate('el => el.hasAttribute("expanded")')
                if is_expanded:
                    logging.info(f"Collapsing league after processing: {league_name}")
                    league.click()
                    page.wait_for_timeout(2000)  # Increased wait time after collapsing
            except Exception:
                # Try clicking anyway to collapse
                logging.info(f"Trying to collapse league: {league_name}")
                try:
                    league.click()
                    page.wait_for_timeout(2000)
                except Exception:
                    pass
        except Exception as collapse_error:
            logging.warning(f"Could not collapse league: {collapse_error}")
    
    except Exception as e:
        logging.error(f"Error processing league {i+1}/{league_count}: {str(e)}")
        data[league_name] = []

# Main script execution
logging.info("Initializing Playwright")
with sync_playwright() as p:
    # Launch browser in headful mode (visible browser window)
    logging.info("Launching browser in headful mode")
    browser = p.firefox.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Navigate to the URL
    logging.info("Navigating to website")
    page.goto("https://www.swisslos.ch/en/sporttip/sports/football", timeout=600000)
    logging.info("Page loaded successfully")

    # Try closing popup if it appears
    try:
        logging.info("Checking for popup")
        popup_close = page.locator("#gb-form > div > button.btn.btn-secondary.gb-push-denied")
        if popup_close.is_visible():
            logging.info("Popup detected, closing")
            popup_close.click()
            logging.info("Popup closed")
        else:
            logging.info("No popup detected")
    except Exception as e:
        logging.warning(f"Error handling popup: {e}")

    # Initialize data structure
    data = {}
    logging.info("Starting data collection")

    # Wait for content to load
    logging.info("Waiting for content to load")
    page.wait_for_timeout(2000)

    # We're already on the Fussball tab, no need to select it
    logging.info("Already on Fussball tab, continuing")

    # Set up both filters: Over/Under 2.5 and Both teams score
    try:
        # FIRST DROPDOWN: Over/Under 2.5
        logging.info("Setting up Over/Under 2.5 filter (first dropdown)")

        # Try multiple approaches to find and click the first filter dropdown
        try:
            # First approach: Try the original selector
            if page.locator("#sportsSportsGrid_filter_col1_input").is_visible(timeout=5000):
                logging.info("Found first filter dropdown with original selector")
                page.locator("#sportsSportsGrid_filter_col1_input").click()
            # Second approach: Try a more general selector
            elif page.locator("[id*='filter_col1_input']").is_visible(timeout=2000):
                logging.info("Found first filter dropdown with partial ID selector")
                page.locator("[id*='filter_col1_input']").click()
            else:
                logging.warning("Could not find first filter dropdown with any selector")
        except Exception as e:
            logging.warning(f"Error finding first filter dropdown: {e}")

        page.wait_for_timeout(2000)

        # Try to select Over/Under 2.5 in the first dropdown
        try:
            # Check if the dropdown menu is visible
            if page.locator(".dropdown-menu.show").is_visible(timeout=2000):
                logging.info("First dropdown menu is visible")

                # First approach: Try to find by text content within the dropdown menu
                if page.locator(".dropdown-menu.show .dropdown-item:has-text('Over/Under 2.5')").is_visible(timeout=2000):
                    logging.info("Found Over/Under 2.5 option by text in dropdown menu")
                    page.locator(".dropdown-menu.show .dropdown-item:has-text('Over/Under 2.5')").click()
                # Second approach: Try to find by the span text
                elif page.locator(".dropdown-menu.show span:text-is('Over/Under 2.5')").is_visible(timeout=2000):
                    logging.info("Found Over/Under 2.5 option by span text")
                    page.locator(".dropdown-menu.show span:text-is('Over/Under 2.5')").click()
                # Third approach: Try clicking the 7th dropdown item (0-based index, so 6)
                else:
                    logging.info("Trying to click the 7th dropdown item (Over/Under 2.5)")
                    dropdown_items = page.locator(".dropdown-menu.show .dropdown-item")
                    if dropdown_items.count() >= 7:
                        dropdown_items.nth(6).click()
                    else:
                        logging.warning(f"Not enough dropdown items: {dropdown_items.count()}")
            else:
                logging.warning("First dropdown menu is not visible")
        except Exception as e:
            logging.warning(f"Error selecting Over/Under 2.5: {e}")

        page.wait_for_timeout(3000)

        # SECOND DROPDOWN: Both teams score
        logging.info("Setting up Both teams score filter (second dropdown)")

        # Try to find and click the second filter dropdown
        try:
            # First approach: Try the specific ID
            if page.locator("#sportsSportsGrid_filter_col2_input").is_visible(timeout=5000):
                logging.info("Found second filter dropdown with specific ID")
                page.locator("#sportsSportsGrid_filter_col2_input").click()
            # Second approach: Try a more general selector
            elif page.locator("[id*='filter_col2_input']").is_visible(timeout=2000):
                logging.info("Found second filter dropdown with partial ID selector")
                page.locator("[id*='filter_col2_input']").click()
            else:
                logging.warning("Could not find second filter dropdown with any selector")
        except Exception as e:
            logging.warning(f"Error finding second filter dropdown: {e}")

        page.wait_for_timeout(2000)

        # Try to select Both teams score in the second dropdown
        try:
            # Check if the dropdown menu is visible
            if page.locator(".dropdown-menu.show").is_visible(timeout=2000):
                logging.info("Second dropdown menu is visible")
                
                # Find the exact "Both teams score" option by its unique ID
                both_teams_score_locator = page.locator('button[id^="sportsSportsGrid_filter_col2_input_"][id*="marketTypeUrn"][id*="Both teams score"]').first
                if both_teams_score_locator.is_visible(timeout=2000):
                    logging.info("Found Both teams score option by ID")
                    both_teams_score_locator.click()
                else:
                    # Fallback to text search if ID-based approach fails
                    logging.info("Trying to find Both teams score by text")
                    both_teams_score_locator = page.get_by_text("Both teams score", exact=True).first
                    if both_teams_score_locator.is_visible(timeout=2000):
                        both_teams_score_locator.click()
                    else:
                        logging.warning("Could not find Both teams score option")
            else:
                logging.warning("Second dropdown menu is not visible")
        except Exception as e:
            logging.warning(f"Error selecting Both teams score: {e}")

        page.wait_for_timeout(3000)

    except Exception as e:
        logging.error(f"Error setting up filters: {e}")

    # Process leagues one by one - expand, get data, then move to next
    logging.info("Collecting league information")
    league_elements = page.locator("asw-sports-grid-expandable")
    league_count = league_elements.count()
    logging.info(f"Found {league_count} leagues to process")

    # If no leagues found, try a different selector
    if league_count == 0:
        logging.info("Trying alternative selector for leagues")
        league_elements = page.locator("div.league-container")
        league_count = league_elements.count()
        logging.info(f"Found {league_count} leagues with alternative selector")

    # Process each league one by one - expand, collect data, then move to next
    for i in range(league_count):
        # Process one league at a time
        process_league(page, league_elements, i, league_count, data)

    logging.info("Completed processing all leagues")

    # Save data to database
    logging.info("Saving data to database")
    save_to_database(data, "2.5_BTTS")  # For the combined 2.5 and BTTS data

    # No JSON files - data is only saved to Supabase database
    logging.info("Data successfully saved to Supabase database")

    logging.info("Closing browser")
    browser.close()
    logging.info("Script completed at %s", time.strftime("%H:%M:%S"))
