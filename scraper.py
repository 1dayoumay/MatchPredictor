import json, time, os, traceback
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import playwright
from playwright.sync_api import sync_playwright

class CornerStatsSession:
    def __init__(self, session_file="session_data.json"):
        self.session_file = session_file
        self.headers = {
            "accept": "text/html, */*; q=0.01",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9,bg;q=0.8",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
            "x-requested-with": "XMLHttpRequest"
        }

    def save(self, page, email, password):
        try:
            data = {
                "email": email,
                "password": password,
                "cookies": page.context.cookies(),
                "headers": self.headers,
                "timestamp": datetime.now().isoformat(),
                "expires": (datetime.now() + timedelta(hours=24)).isoformat()
            }
            with open(self.session_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to save session: {e}")
            return False

    def load(self):
        """Load session data"""
        if not os.path.exists(self.session_file):
            return None
        try:
            with open(self.session_file, 'r') as f:
                data = json.load(f)
            
            # Basic expiry check (optional but good practice)
            if 'expires' in data:
                if datetime.now() > datetime.fromisoformat(data['expires']):
                    print("Session expired")
                    # Optionally remove the expired file
                    # os.remove(self.session_file)
                    return None

            print("Session loaded successfully")
            return data
        except Exception as e:
            print(f"Failed to load session: {e}")
            return None
        
    def apply(self, page, session_data):
        try:
            if 'cookies' in session_data:
                page.context.add_cookies(session_data['cookies'])
            if 'headers' in session_data:
                page.set_extra_http_headers(session_data['headers'])
            return True
        except Exception as e:
            print(f"Failed to apply session: {e}")
            return False

class CornerStatsAuth: # Keep this for API 1 if needed, though login is now in CornerStatsDataScraper
    def _is_logged_in(self, page):
        return page.locator('a.btn.btn-confirm:has-text("Login")').count() == 0

    def login(self, page, email, password):
        try:
            if self._is_logged_in(page):
                return True

            page.locator('a.btn.btn-confirm:has-text("Login")').click()
            page.wait_for_selector("#form_login", timeout=10000)
            page.locator("#email_login").fill(email)
            page.locator("#password_login").fill(password)
            page.locator("button.btn__button.sign-in").click()
            time.sleep(3)

            if self._is_logged_in(page):
                session_manager = CornerStatsSession()
                session_manager.save(page, email, password)
                return True
            else:
                error_msgs = []
                for selector in [".errorTxt_login", ".errorTxt_password_login"]:
                    elem = page.locator(selector)
                    if elem.count() > 0:
                        error_msgs.append(elem.text_content().strip())
                return False
        except Exception as e:
            print(f"Login error: {e}")
            return False
        
class CornerStatsDataScraper: # Renamed to DataScraper for clarity, inheriting structure
    """Main scraper class for corner-stats.com, adapted for API use"""
    def __init__(self):
        self.session = CornerStatsSession() # <-- FIXED: Initialize session
        self.url = "https://corner-stats.com"

    def _is_logged_in(self, page):
        """Check if user is logged in"""
        return page.locator('a.btn.btn-confirm:has-text("Login")').count() == 0

    # --- Methods for API 2: /api/leagues_teams ---
    def get_leagues_and_teams(self, country_name):
        """Get leagues and teams for a given country"""
        session_data = self.session.load()
        if not session_data:
             return {"error": "No valid session found. Please log in first."}, 401

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel="msedge")
            page = browser.new_page()

            try:
                # Apply session
                self.session.apply(page, session_data)
                page.goto(self.url)
                page.wait_for_load_state("networkidle")
                time.sleep(2)

                if not self._is_logged_in(page):
                     return {"error": "Session invalid or expired. Please log in again."}, 401

                # --- Mimic the logic from _interactive_team_selection ---

                # Wait for the team selection block to be visible
                team_block = page.locator("#block1.team").first
                team_block.wait_for(timeout=10000) # Adjust timeout as needed

                # Get available countries
                country_options = []
                country_select = page.locator("select.select-control_1").first
                options = country_select.locator("option")
                for i in range(options.count()):
                    option = options.nth(i)
                    value = option.get_attribute("value")
                    text = option.text_content().strip()
                    if value and value != "0":
                        country_options.append({"value": value, "name": text})

                # Find the selected country
                selected_country = None
                for country in country_options:
                    # Match by name (case-insensitive partial match might be needed depending on input)
                    if country['name'].lower() == country_name.lower():
                        selected_country = country
                        break

                if not selected_country:
                    return {"error": f"Country '{country_name}' not found."}, 404

                # Select the country
                country_select.select_option(selected_country['value'])
                time.sleep(2) # Wait for leagues to load via AJAX

                # Get available leagues
                league_options = []
                league_select = page.locator("select.select-control_2").first
                league_opts = league_select.locator("option")
                for i in range(league_opts.count()):
                    option = league_opts.nth(i)
                    value = option.get_attribute("value")
                    text = option.text_content().strip()
                    if value and value != "0":
                        league_options.append({"value": value, "name": text})

                if not league_options:
                     # Return empty structure if no leagues
                     return {
                        "country": selected_country['name'],
                        "leagues": []
                    }, 200

                # --- Collect data for each league ---
                result_data = {
                    "country": selected_country['name'],
                    "leagues": []
                }

                for league in league_options:
                    # Select the league
                    league_select.select_option(league['value'])
                    time.sleep(2) # Wait for teams to load via AJAX

                    # Get available teams for this league
                    team_options = []
                    team_select = page.locator("select.select-control_3").first
                    team_opts = team_select.locator("option")
                    for i in range(team_opts.count()):
                        option = team_opts.nth(i)
                        value = option.get_attribute("value")
                        text = option.text_content().strip()
                        if value and value != "0":
                            team_options.append({"value": value, "name": text})

                    # Add league and its teams to the result
                    result_data["leagues"].append({
                        "id": league['value'], # Using 'value' as ID
                        "name": league['name'],
                        "teams": team_options # Each team is {'value': '...', 'name': '...'}
                    })

                return result_data, 200

            except Exception as e:
                print(f"Error in get_leagues_and_teams: {e}")
                traceback.print_exc()
                return {"error": f"Scraping failed: {str(e)}"}, 500
            finally:
                browser.close()

    # --- Methods for API 3: /api/compare_and_calculate ---
    def _select_team_from_search_results(self, page, team_name, input_selector, results_container_selector):
        """Helper method to select a team from search results (no user interaction)"""
        try:
            print(f"Searching for team: {team_name}")
            # Clear and type in the team name
            input_field = page.locator(input_selector)
            input_field.clear()
            input_field.fill(team_name)
            # Trigger the search by typing (simulate keyup event)
            input_field.press("Space")
            input_field.press("Backspace")
            time.sleep(3)  # Wait longer for search results to populate

            # Wait for search results container
            results_container = page.locator(results_container_selector)
            results_list = results_container.locator("li.match-creator-selectblock-searchresult-item")

            # Wait a bit more for results to fully load and check multiple times
            for attempt in range(3):
                page.wait_for_timeout(1000)
                if results_list.count() > 0:
                    break
                print(f"Attempt {attempt + 1}: Waiting for search results...")

            results_count = results_list.count()
            print(f"Found {results_count} search results")

            if results_count == 0:
                print(f"No search results found for team: {team_name}")
                return False
            elif results_count >= 1: # Select the first result automatically
                # Even if multiple, API picks the first one
                team_link = results_list.first.locator("a.team_row")
                team_text = team_link.text_content().strip()
                print(f"Selected team (first match): {team_text}")
                team_link.click()
                time.sleep(2) # Wait after click
                return True

        except Exception as e:
            print(f"Error selecting team from search results: {e}")
            traceback.print_exc()
            return False # Return False on exception

    def _enter_teams_in_compare_form(self, page, host_team, guest_team, country_name):
        """Enter the selected teams in the Compare Teams form"""
        try:
            print(f"\nEntering teams in compare form:")
            print(f"Host: {host_team['name']}")
            print(f"Guest: {guest_team['name']}")
            print(f"Country: {country_name}")

            # Wait for the compare teams form to be available
            compare_form = page.locator("form#match-form_1")
            compare_form.wait_for(timeout=10000)

            # Prepare team names with country suffix
            host_team_search = f"{host_team['name']}({country_name})"
            guest_team_search = f"{guest_team['name']}({country_name})"

            # Select host team
            print(f"\nSelecting host team: {host_team_search}")
            if not self._select_team_from_search_results(
                page,
                host_team_search,
                "#input_team_1_1",
                "#div_input_team_1_1 .match-creator-selectblock-searchresult"
            ):
                # Fallback: try without country name
                print(f"Retrying host team without country: {host_team['name']}")
                if not self._select_team_from_search_results(
                    page,
                    host_team['name'],
                    "#input_team_1_1",
                    "#div_input_team_1_1 .match-creator-selectblock-searchresult"
                ):
                    print("Failed to select host team")
                    return False

            # Select guest team
            print(f"\nSelecting guest team: {guest_team_search}")
            if not self._select_team_from_search_results(
                page,
                guest_team_search,
                "#input_team_2_1",
                "#div_input_team_2_1 .match-creator-selectblock-searchresult"
            ):
                # Fallback: try without country name
                print(f"Retrying guest team without country: {guest_team['name']}")
                if not self._select_team_from_search_results(
                    page,
                    guest_team['name'],
                    "#input_team_2_1",
                    "#div_input_team_2_1 .match-creator-selectblock-searchresult"
                ):
                    print("Failed to select guest team")
                    return False

            # Wait a moment for the form to process the selections
            time.sleep(3)
            print("Teams entered successfully in compare form")
            return True
        except Exception as e:
            print(f"Error entering teams in compare form: {e}")
            return False

        # Inside CornerStatsDataScraper class in scraper.py
    def _configure_filters(self, page, filters):
        """Configure the filter options based on API input (no user interaction)"""
        try:
            print("\nConfiguring filters...")
            
            # --- CRITICAL: Wait for the filter container to be visible ---
            filters_container = page.locator(".getmatches_filters")
            filters_container.wait_for(timeout=15000, state='visible') # Wait up to 15s for visibility
            print("Filters container is visible.")
            # --- END CRITICAL ---

            # Set show results to maximum (100)
            show_select = page.locator("select.show_results")
            if show_select.count() > 0:
                show_select.select_option("100")
                print("Set results display to 100")
                # Wait a bit for the change to potentially trigger updates
                page.wait_for_timeout(2000) 

            # --- Wait for filter elements to be attached to the DOM ---
            # This is often enough before interacting, visibility can be flaky
            page.locator('input[name="filter_tourn[]"]').first.wait_for(timeout=10000, state='attached')
            page.locator('input[name="filter_season[]"]').first.wait_for(timeout=10000, state='attached')
            page.locator('input[name="filter_home[]"]').first.wait_for(timeout=10000, state='attached')
            print("Core filter elements are attached.")
            # --- End Wait for attachment ---

            # 1. Tournament Type Filter
            tournament_choice = filters.get('tournament_type', 's').lower().strip()
            if tournament_choice in ['l', 'c', 'b']:
                # Get locators for the specific checkboxes
                league_checkbox = page.locator('input[name="filter_tourn[]"][value="1"]')
                cups_checkbox = page.locator('input[name="filter_tourn[]"][value="2"]')
                
                # Small wait to ensure they are interactable
                page.wait_for_timeout(1000) 

                if tournament_choice == 'l':
                    # Goal: League only -> Uncheck Cups
                    # Check if Cups checkbox is currently checked *before* trying to uncheck
                    # Use a short timeout for the check, as it might not be visible but still checkable
                    try:
                        if cups_checkbox.is_checked(timeout=2000): # Shorter timeout for check
                            print("   Unchecking Cups...")
                            cups_checkbox.uncheck()
                        else:
                            print("   Cups already unchecked.")
                    except playwright._impl._errors.TimeoutError:
                         # If checking state timed out, assume it's not checked or not interactable in a standard way
                         # We might still try to uncheck it, or log a warning and proceed
                         print("   Warning: Could not determine Cups checkbox state quickly, assuming unchecked or proceeding.")
                    print("   → Selected: League only")
                    
                elif tournament_choice == 'c':
                    # Goal: Cups only -> Uncheck League
                    try:
                        if league_checkbox.is_checked(timeout=2000):
                            print("   Unchecking League...")
                            league_checkbox.uncheck()
                        else:
                           print("   League already unchecked.")
                    except playwright._impl._errors.TimeoutError:
                         print("   Warning: Could not determine League checkbox state quickly, assuming unchecked or proceeding.")
                    print("   → Selected: Cups only")
                    
                elif tournament_choice == 'b':
                    # Goal: Both League and Cups (usually default)
                    # The original logic didn't explicitly check/uncheck both here,
                    # implying they are checked by default or the default is acceptable.
                    # We can leave them as is, or explicitly ensure they are checked.
                    # Let's assume default is fine for 'b'.
                    print("   → Selected: Both League and Cups") # Both are checked by default usually

            # 2. Season Filter
            season_choice = filters.get('seasons', 'skip')
            if season_choice != 'skip':
                 # Small wait before interacting with season filters
                 page.wait_for_timeout(1000)
                 season_checkboxes = page.locator('input[name="filter_season[]"]')
                 seasons_available = []
                 # Extract season values and labels from the page
                 for i in range(season_checkboxes.count()):
                     checkbox = season_checkboxes.nth(i)
                     value = checkbox.get_attribute('value')
                     # Get the label text from the span element next to the checkbox
                     label_span = checkbox.locator('xpath=following-sibling::span[@class="label-name"]')
                     label = label_span.text_content().strip() if label_span.count() > 0 else f"Season {value}"
                     seasons_available.append((value, label))

                 if season_choice == 'all':
                     print("   → Selected: All seasons")
                     # If 'all' means keeping the default (often all are selected or a 'select all' is checked),
                     # we might not need to do anything here, or ensure the 'all' checkbox is checked.
                     # Let's assume default selection for 'all' is fine.
                     
                 elif isinstance(season_choice, list) and season_choice:
                     try:
                         # First uncheck all seasons
                         all_seasons_checkbox = page.locator('input.filter_quick_all_seasons')
                         # Check if 'select all' is checked and uncheck it if so
                         try:
                             if all_seasons_checkbox.is_checked(timeout=2000):
                                 all_seasons_checkbox.uncheck()
                                 print("   Unchecked 'Select All' seasons checkbox.")
                         except playwright._impl._errors.TimeoutError:
                              print("   Warning: Could not determine 'Select All' season checkbox state quickly.")
                              
                         # Uncheck all individual season checkboxes that might be checked
                         # Small wait
                         page.wait_for_timeout(500)
                         for season_value, _ in seasons_available:
                             season_checkbox = page.locator(f'input[name="filter_season[]"][value="{season_value}"]')
                             try:
                                 # Check state with a short timeout
                                 if season_checkbox.is_checked(timeout=1500):
                                     season_checkbox.uncheck()
                                     # print(f"   Unchecked season {season_value}") # Optional verbose log
                             except playwright._impl._errors.TimeoutError:
                                  # If we can't check the state quickly, it might not be relevant or checkable right now
                                  pass # Proceed

                         # Check selected seasons
                         selected_seasons = []
                         for season_val_or_label in season_choice:
                              # Match by value or label
                              for s_val, s_label in seasons_available:
                                  if str(season_val_or_label) == str(s_val) or str(season_val_or_label).lower() == s_label.lower():
                                      season_checkbox = page.locator(f'input[name="filter_season[]"][value="{s_val}"]')
                                      # Add a tiny wait before checking
                                      page.wait_for_timeout(200)
                                      season_checkbox.check() # Check the desired ones
                                      selected_seasons.append(s_label)
                                      break
                         if selected_seasons:
                             print(f"   → Selected seasons: {', '.join(selected_seasons)}")
                         else:
                              print("   → No valid seasons matched for selection, keeping defaults (or none).")
                     except Exception as e:
                         print(f"   → Error processing season selection list: {e}. Keeping defaults.")
                         traceback.print_exc()

            # 3. Venue Filter
            venue_choice = filters.get('venue', 's').lower().strip()
            if venue_choice in ['h', 'a', 'b']:
                # Get locators for the specific checkboxes
                home_checkbox = page.locator('input[name="filter_home[]"][value="1"]')
                away_checkbox = page.locator('input[name="filter_home[]"][value="2"]')
                
                # Small wait to ensure they are interactable
                page.wait_for_timeout(1000) 

                if venue_choice == 'h':
                    # Goal: Home only -> Uncheck Away
                    try:
                        if away_checkbox.is_checked(timeout=2000):
                            print("   Unchecking Away...")
                            away_checkbox.uncheck()
                        else:
                           print("   Away already unchecked.")
                    except playwright._impl._errors.TimeoutError:
                         print("   Warning: Could not determine Away checkbox state quickly, assuming unchecked or proceeding.")
                    print("   → Selected: Home only")
                    
                elif venue_choice == 'a':
                    # Goal: Away only -> Uncheck Home
                    try:
                        if home_checkbox.is_checked(timeout=2000):
                            print("   Unchecking Home...")
                            home_checkbox.uncheck()
                        else:
                           print("   Home already unchecked.")
                    except playwright._impl._errors.TimeoutError:
                         print("   Warning: Could not determine Home checkbox state quickly, assuming unchecked or proceeding.")
                    print("   → Selected: Away only")
                    
                elif venue_choice == 'b':
                    # Goal: Both Home and Away (usually default)
                    print("   → Selected: Both Home and Away") # Both are checked by default usually

            # Wait for filters to apply (might involve AJAX)
            print("\nApplying filters...")
            time.sleep(3) # Keep this for now, might need adjustment
            print("="*50)
            print("Filters configured successfully")
            return True
        except Exception as e:
            print(f"Error configuring filters: {e}")
            # Print the full traceback for better debugging
            traceback.print_exc()
            return False
        # Add import at the top of scraper.py if not already there
        # import playwright._impl._errors 

    def _navigate_to_start_of_table(self, page):
        """Navigate to the start of the data table by clicking Previous until disabled"""
        try:
            print("\nNavigating to start of table...")
            while True:
                prev_button = page.locator("button.button_prev_table")
                if prev_button.count() > 0:
                    # Check if button is active (not disabled)
                    if "not_active" in prev_button.get_attribute("class"):
                        print("Reached start of table")
                        break
                    else:
                        prev_button.click()
                        time.sleep(2)  # Wait for page to load
                        print("Clicked Previous button")
                else:
                    print("Previous button not found")
                    break
            return True
        except Exception as e:
            print(f"Error navigating to start of table: {e}")
            return False

    def _extract_table_data(self, page):
        """Extract table data from current page"""
        try:
            # Wait for table to be present
            table = page.locator("table.data-table")
            table.wait_for(timeout=10000)
            # Extract headers
            headers = []
            header_row = table.locator("thead tr").first
            header_cells = header_row.locator("th")
            for i in range(header_cells.count()):
                cell = header_cells.nth(i)
                # Skip hidden columns
                if "display:none" not in (cell.get_attribute("style") or ""):
                    headers.append(cell.text_content().strip())
            # Extract data rows
            rows_data = []
            tbody = table.locator("tbody.tableData")
            data_rows = tbody.locator("tr.tr__main")
            for i in range(data_rows.count()):
                row = data_rows.nth(i)
                row_data = []
                cells = row.locator("td")
                for j in range(cells.count()):
                    cell = cells.nth(j)
                    # Skip hidden columns and exclude/details columns
                    cell_class = cell.get_attribute("class") or ""
                    if "td__exclude" not in cell_class and "td__details" not in cell_class:
                        # Get text content, handling links
                        if cell.locator("a").count() > 0:
                            text = cell.locator("a").first.text_content().strip()
                        else:
                            text = cell.text_content().strip()
                        row_data.append(text)
                if row_data:  # Only add non-empty rows
                    rows_data.append(row_data)
            return headers, rows_data
        except Exception as e:
            print(f"Error extracting table data: {e}")
            return [], []

    def _extract_all_table_data(self, page):
        """Extract all table data by paginating through all pages"""
        try:
            print("\nExtracting table data from all pages...")
            all_headers = []
            all_rows = []
            page_num = 1
            while True:
                print(f"Extracting data from page {page_num}...")
                # Extract data from current page
                headers, rows_data = self._extract_table_data(page)
                if headers and not all_headers:
                    all_headers = headers
                if rows_data:
                    all_rows.extend(rows_data)
                    print(f"Extracted {len(rows_data)} rows from page {page_num}")
                # Check if Next button is available and active
                next_button = page.locator("button.button_next_table")
                if next_button.count() > 0:
                    if "not_active" in next_button.get_attribute("class"):
                        print("Reached end of table")
                        break
                    else:
                        next_button.click()
                        time.sleep(3)  # Wait for page to load
                        page_num += 1
                else:
                    print("Next button not found")
                    break
            print(f"\nTotal rows extracted: {len(all_rows)}")
            return all_headers, all_rows
        except Exception as e:
            print(f"Error extracting all table data: {e}")
            return [], []

    def _create_dataframe(self, headers, rows_data):
        """Create and format DataFrame"""
        if not rows_data:
            return None
        # Use headers or fallback names
        if len(headers) == len(rows_data[0]):
            columns = headers
        else:
            columns = ["Date", "Tournament", "Round", "Team1", "T1_Stats", "T2_Stats",
                      "Team2", "Win", "Draw", "Loss", "Exclude", "Details"][:len(rows_data[0])]
            # Pad if needed
            while len(columns) < len(rows_data[0]):
                columns.append(f"Column_{len(columns)+1}")
        df = pd.DataFrame(rows_data, columns=columns)
        # Convert numeric columns
        numeric_keywords = ['win', 'draw', 'loss', 'stats']
        for i, col in enumerate(df.columns):
            if any(kw in col.lower() for kw in numeric_keywords):
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df

    def _calculate_win_probability(self, df):
        """Calculate various match probabilities using bookmaker odds and simulation"""
        print("\nCalculating comprehensive match probabilities...")
        
        # Handle empty or invalid data - Return an error message
        if df is None or df.empty:
            print("No match data provided.")
            # Return a specific indicator that no data was found
            return {
                "error": "No match data available for the selected teams and filters. Cannot calculate probabilities."
            }
        
        # Convert date to datetime and sort chronologically
        df = df.copy()
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Date']).sort_values('Date').reset_index(drop=True)
        
        if df.empty:
            print("No valid match data with dates found.")
            return {
                "error": "No valid historical match data found for the selected teams. Cannot calculate probabilities."
            }
        
        # Standardize perspective: Always treat Host as "Team A"
        df['host_win_odds'] = df['Win']
        df['guest_win_odds'] = df['Loss']
        df['draw_odds'] = df['Draw']
        
        # Convert odds to numeric and filter valid matches
        for col in ['host_win_odds', 'guest_win_odds', 'draw_odds']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        valid = df[
            (df['host_win_odds'] > 0) &
            (df['guest_win_odds'] > 0) &
            (df['draw_odds'] > 0)
        ].copy()
        
        if valid.empty:
            print("No valid odds data found.")
            return {
                "error": "Insufficient valid odds data found in the historical matches. Cannot calculate probabilities."
            }
        
        print(f"Analyzing {len(valid)} valid matches out of {len(df)} total matches")
        
        # Calculate normalized probabilities (remove bookmaker margin)
        valid['inv_host_win'] = 1 / valid['host_win_odds']
        valid['inv_guest_win'] = 1 / valid['guest_win_odds']
        valid['inv_draw'] = 1 / valid['draw_odds']
        valid['total_inv'] = valid['inv_host_win'] + valid['inv_guest_win'] + valid['inv_draw']
        
        valid['p_host_win'] = valid['inv_host_win'] / valid['total_inv']
        valid['p_guest_win'] = valid['inv_guest_win'] / valid['total_inv']
        valid['p_draw'] = valid['inv_draw'] / valid['total_inv']
        
        # Apply recency weighting (exponential decay)
        valid = valid.sort_values('Date', ascending=False)
        valid['weight'] = np.exp(-0.15 * np.arange(len(valid)))
        
        # Calculate weighted probabilities
        total_weight = valid['weight'].sum()
        host_win_prob = (valid['p_host_win'] * valid['weight']).sum() / total_weight
        guest_win_prob = (valid['p_guest_win'] * valid['weight']).sum() / total_weight
        draw_prob = (valid['p_draw'] * valid['weight']).sum() / total_weight
        
        # Normalize to ensure they sum to 1
        total = host_win_prob + guest_win_prob + draw_prob
        host_win_prob /= total
        guest_win_prob /= total
        draw_prob /= total
        
        # Calculate confidence metrics
        win_std = valid['p_host_win'].std()
        confidence = max(0.3, 1 - win_std) if not pd.isna(win_std) else 0.5
        
        # Bayesian adjustment with prior
        BAYESIAN_PRIOR = 1/3  # Neutral prior for 3 outcomes
        adjusted_host_win = (host_win_prob * confidence) + (BAYESIAN_PRIOR * (1 - confidence))
        adjusted_guest_win = (guest_win_prob * confidence) + (BAYESIAN_PRIOR * (1 - confidence))
        adjusted_draw = (draw_prob * confidence) + (BAYESIAN_PRIOR * (1 - confidence))
        
        # Normalize again after Bayesian adjustment
        total = adjusted_host_win + adjusted_guest_win + adjusted_draw
        adjusted_host_win /= total
        adjusted_guest_win /= total
        adjusted_draw /= total
        
        # --- Run Monte Carlo simulation for goal probabilities ---
        num_simulations = 10000
        
        # Estimate average goals scored/conceded from valid data for simulation
        # This uses the implied probabilities to estimate goal expectations
        # A more sophisticated approach would use actual goal data if available
        
        # Simple heuristic to estimate goal expectations based on outcome probabilities
        # Higher win probability suggests higher expected goals for that team
        total_prob = adjusted_host_win + adjusted_draw + adjusted_guest_win
        if total_prob > 0:
            # Normalize probabilities for goal estimation
            norm_host_win = adjusted_host_win / total_prob
            norm_draw = adjusted_draw / total_prob
            norm_guest_win = adjusted_guest_win / total_prob
            
            # Estimate goal expectations based on outcome probabilities
            # These are rough estimates, could be refined with more domain knowledge or data
            expected_goals_home = 1.2 + (norm_host_win * 1.0) + (norm_draw * 0.3) # Base + Win bonus + Draw component
            expected_goals_away = 1.0 + (norm_guest_win * 1.0) + (norm_draw * 0.3)
            
            # Ensure a minimum expectation
            expected_goals_home = max(expected_goals_home, 0.5)
            expected_goals_away = max(expected_goals_away, 0.5)
        else:
            # Fallback if probabilities are somehow invalid
            expected_goals_home = 1.2
            expected_goals_away = 1.0

        # Run simulation
        over_15 = 0
        over_25 = 0
        over_35 = 0
        btts = 0
        
        for _ in range(num_simulations):
            # Determine match outcome based on adjusted probabilities
            rand = np.random.random()
            if rand < adjusted_host_win:
                # Home win scenario - higher home goals likely
                home_goals = np.random.poisson(expected_goals_home * 1.1) # Slightly boost home team
                away_goals = np.random.poisson(expected_goals_away * 0.9) # Slightly reduce away team
            elif rand < adjusted_host_win + adjusted_draw:
                # Draw scenario - more balanced goals
                home_goals = np.random.poisson(expected_goals_home)
                away_goals = np.random.poisson(expected_goals_away)
            else:
                # Away win scenario - higher away goals likely
                home_goals = np.random.poisson(expected_goals_home * 0.9) # Slightly reduce home team
                away_goals = np.random.poisson(expected_goals_away * 1.1) # Slightly boost away team
            
            # Calculate goal-based probabilities
            total_goals = home_goals + away_goals
            if total_goals > 1.5:
                over_15 += 1
            if total_goals > 2.5:
                over_25 += 1
            if total_goals > 3.5:
                over_35 += 1
            if home_goals > 0 and away_goals > 0:
                btts += 1

        # Calculate probabilities from simulation
        over_15_prob = over_15 / num_simulations
        over_25_prob = over_25 / num_simulations
        over_35_prob = over_35 / num_simulations
        btts_prob = btts / num_simulations
        
        # Calculate odds
        def probability_to_odds(prob):
            return round(1 / prob, 2) if prob > 0 else float('inf')
        
        # Format the results
        result = {
            'host_win_prob': round(adjusted_host_win, 4),
            'draw_prob': round(adjusted_draw, 4),
            'guest_win_prob': round(adjusted_guest_win, 4),
            'over_15_prob': round(over_15_prob, 4),
            'over_25_prob': round(over_25_prob, 4),
            'over_35_prob': round(over_35_prob, 4),
            'btts_prob': round(btts_prob, 4),
            'host_win_odds': probability_to_odds(adjusted_host_win),
            'draw_odds': probability_to_odds(adjusted_draw),
            'guest_win_odds': probability_to_odds(adjusted_guest_win),
            'over_15_odds': probability_to_odds(over_15_prob),
            'over_25_odds': probability_to_odds(over_25_prob),
            'over_35_odds': probability_to_odds(over_35_prob),
            'btts_odds': probability_to_odds(btts_prob),
            'confidence': round(confidence, 2),
            'total_matches': len(valid) # Include number of matches for context
        }
        
        # Print comprehensive results (optional for API, good for logs/development)
        # print(f"\n{'='*60}")
        # print(f"1X2 Probabilities:")
        # print(f"Host Win: {result['host_win_prob']:.2%} | Draw: {result['draw_prob']:.2%} | Guest Win: {result['guest_win_prob']:.2%}")
        # print(f"\nOver/Under Probabilities:")
        # print(f"Over 1.5: {result['over_15_prob']:.2%} | Over 2.5: {result['over_25_prob']:.2%} | Over 3.5: {result['over_35_prob']:.2%}")
        # print(f"\nBoth Teams to Score: {result['btts_prob']:.2%}")
        # print(f"\nConfidence: {confidence:.0%} (based on {len(valid)} matches)")
        # print(f"{'='*60}")
        
        return result


    def compare_and_calculate(self, host_team, guest_team, country_name, filters):
        """API-facing method to perform comparison and calculation"""
        session_data = self.session.load()
        if not session_data:
             return {"error": "No valid session found. Please log in first."}, 401

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel="msedge") # Headless for API
            page = browser.new_page()

            try:
                # Apply session
                self.session.apply(page, session_data)
                page.goto(self.url)
                page.wait_for_load_state("networkidle")
                time.sleep(2)

                if not self._is_logged_in(page):
                     return {"error": "Session invalid or expired. Please log in again."}, 401

                 # --- Perform the scraping steps ---

                # Enter teams in compare form
                if not self._enter_teams_in_compare_form(page, host_team, guest_team, country_name):
                    return {"error": "Failed to enter teams in compare form"}, 500

                # Configure filters
                if not self._configure_filters(page, filters):
                    return {"error": "Failed to configure filters"}, 500

                # Navigate to start of table
                if not self._navigate_to_start_of_table(page):
                    return {"error": "Failed to navigate to start of table"}, 500

                # Extract all table data
                headers, all_rows = self._extract_all_table_data(page)
                if not headers or not all_rows:
                    return {"error": "No data extracted from table"}, 404 # Not found might be appropriate

                # Create DataFrame
                df = self._create_dataframe(headers, all_rows)
                if df is None:
                    return {"error": "Failed to create DataFrame from scraped data"}, 500

                # Calculate win probability
                probabilities_result = self._calculate_win_probability(df)

                # Check if probabilities calculation returned an error
                if "error" in probabilities_result:
                    # Return the error message to the API client
                    return {
                        "success": False,
                        "host_team": host_team['name'],
                        "guest_team": guest_team['name'],
                        "error": probabilities_result["error"],
                        "total_matches_analyzed": len(df) if df is not None else 0,
                    }, 404 # Using 404 Not Found to indicate no data, or 200 OK with success=False

                # If successful, probabilities_result contains the data
                # Return successful result with all metrics
                return {
                    "success": True,
                    "host_team": host_team['name'],
                    "guest_team": guest_team['name'],
                    "probabilities": {
                        "host_win": probabilities_result['host_win_prob'],
                        "draw": probabilities_result['draw_prob'],
                        "guest_win": probabilities_result['guest_win_prob'],
                        "over_1_5": probabilities_result['over_15_prob'],
                        "over_2_5": probabilities_result['over_25_prob'],
                        "over_3_5": probabilities_result['over_35_prob'],
                        "btts": probabilities_result['btts_prob']
                    },
                    "odds": {
                        "host_win": probabilities_result['host_win_odds'],
                        "draw": probabilities_result['draw_odds'],
                        "guest_win": probabilities_result['guest_win_odds'],
                        "over_1_5": probabilities_result['over_15_odds'],
                        "over_2_5": probabilities_result['over_25_odds'],
                        "over_3_5": probabilities_result['over_35_odds'],
                        "btts": probabilities_result['btts_odds']
                    },
                    "confidence": probabilities_result['confidence'],
                    "total_matches_analyzed": probabilities_result['total_matches'],
                    "message": "Calculation completed successfully."
                }, 200

            except Exception as e:
                print(f"Error in compare_and_calculate: {e}")
                traceback.print_exc() # Log the full traceback
                return {"error": f"Scraping/calculation failed: {str(e)}"}, 500
            finally:
                browser.close()