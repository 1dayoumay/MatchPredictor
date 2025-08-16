import json, time, os, traceback
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
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

            # Wait for search results to appear
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
                time.sleep(2)
                return True

        except Exception as e:
            print(f"Error selecting team from search results: {e}")
            import traceback
            traceback.print_exc()
            return False

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

    def _configure_filters(self, page, filters):
        """Configure the filter options based on API input (no user interaction)"""
        try:
            print("\nConfiguring filters...")
            # Wait for filters to load
            filters_container = page.locator(".getmatches_filters")
            filters_container.wait_for(timeout=10000)

            # Set show results to maximum (100)
            show_select = page.locator("select.show_results")
            if show_select.count() > 0:
                show_select.select_option("100")
                print("Set results display to 100")
                time.sleep(2)  # Wait for page to load

            # 1. Tournament Type Filter
            tournament_choice = filters.get('tournament_type', 's').lower().strip()
            if tournament_choice in ['l', 'c', 'b']:
                if tournament_choice == 'l':
                    cups_checkbox = page.locator('input[name="filter_tourn[]"][value="2"]')
                    if cups_checkbox.is_checked():
                        cups_checkbox.uncheck()
                    print("   → Selected: League only")
                elif tournament_choice == 'c':
                    league_checkbox = page.locator('input[name="filter_tourn[]"][value="1"]')
                    if league_checkbox.is_checked():
                        league_checkbox.uncheck()
                    print("   → Selected: Cups only")
                elif tournament_choice == 'b':
                    print("   → Selected: Both League and Cups") # Both are checked by default usually

            # 2. Season Filter
            season_choice = filters.get('seasons', 'skip')
            if season_choice != 'skip':
                season_checkboxes = page.locator('input[name="filter_season[]"]')
                seasons_available = []
                for i in range(season_checkboxes.count()):
                    checkbox = season_checkboxes.nth(i)
                    value = checkbox.get_attribute('value')
                    label_span = checkbox.locator('xpath=following-sibling::span[@class="label-name"]')
                    label = label_span.text_content().strip() if label_span.count() > 0 else f"Season {value}"
                    seasons_available.append((value, label))

                if season_choice == 'all':
                    print("   → Selected: All seasons")
                elif isinstance(season_choice, list) and season_choice:
                    try:
                        # First uncheck all seasons
                        all_seasons_checkbox = page.locator('input.filter_quick_all_seasons')
                        if all_seasons_checkbox.is_checked():
                            all_seasons_checkbox.uncheck()
                        # Uncheck all individual season checkboxes
                        for season_value, _ in seasons_available:
                            season_checkbox = page.locator(f'input[name="filter_season[]"][value="{season_value}"]')
                            if season_checkbox.is_checked():
                                season_checkbox.uncheck()

                        # Check selected seasons
                        selected_seasons = []
                        for season_val_or_label in season_choice:
                             # Match by value or label
                             for s_val, s_label in seasons_available:
                                 if str(season_val_or_label) == str(s_val) or str(season_val_or_label).lower() == s_label.lower():
                                     season_checkbox = page.locator(f'input[name="filter_season[]"][value="{s_val}"]')
                                     season_checkbox.check()
                                     selected_seasons.append(s_label)
                                     break
                        if selected_seasons:
                            print(f"   → Selected seasons: {', '.join(selected_seasons)}")
                        else:
                             print("   → No valid seasons matched for selection, keeping defaults.")
                    except Exception as e:
                        print(f"   → Error processing season selection list: {e}. Keeping defaults.")

            # 3. Venue Filter
            venue_choice = filters.get('venue', 's').lower().strip()
            if venue_choice in ['h', 'a', 'b']:
                if venue_choice == 'h':
                    away_checkbox = page.locator('input[name="filter_home[]"][value="2"]')
                    if away_checkbox.is_checked():
                        away_checkbox.uncheck()
                    print("   → Selected: Home only")
                elif venue_choice == 'a':
                    home_checkbox = page.locator('input[name="filter_home[]"][value="1"]')
                    if home_checkbox.is_checked():
                        home_checkbox.uncheck()
                    print("   → Selected: Away only")
                elif venue_choice == 'b':
                    print("   → Selected: Both Home and Away") # Both are checked by default usually

            # Wait for filters to apply
            print("\nApplying filters...")
            time.sleep(3)
            print("="*50)
            print("Filters configured successfully")
            return True
        except Exception as e:
            print(f"Error configuring filters: {e}")
            return False

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
        """Calculate win probability for the host team using bookmaker odds with recency weighting"""
        print("\nCalculating head-to-head win probabilities...")
        if df is None or df.empty:
            print("No match data provided. Defaulting to 50% win probability.")
            return 0.5

        # Convert date to datetime and sort chronologically (oldest first)
        df = df.copy()
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Date']).sort_values('Date').reset_index(drop=True) # Drop rows with invalid dates

        if df.empty:
             print("No valid match data with dates found. Defaulting to 50% win probability.")
             return 0.5

        # Standardize perspective: Always treat Host as "Team A"
        # Assume columns are Team1, Team2, Win (Host odds), Draw, Loss (Guest odds)
        # Win column is odds for Team1 winning, Loss column is odds for Team2 winning
        df['host_win_odds'] = df['Win']
        df['host_loss_odds'] = df['Loss']
        df['draw_odds'] = df['Draw']

        # Convert odds to numeric and filter valid matches
        for col in ['host_win_odds', 'host_loss_odds', 'draw_odds']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        valid = df[
            (df['host_win_odds'] > 0) &
            (df['host_loss_odds'] > 0) &
            (df['draw_odds'] > 0)
        ].copy()

        if valid.empty:
            print("No valid odds data found. Defaulting to 50% win probability for Host.")
            return 0.5

        print(f"Analyzing {len(valid)} valid matches out of {len(df)} total matches")

        # Calculate normalized probabilities (remove bookmaker margin)
        valid['inv_win'] = 1 / valid['host_win_odds']
        valid['inv_loss'] = 1 / valid['host_loss_odds']
        valid['inv_draw'] = 1 / valid['draw_odds']
        valid['total_inv'] = valid['inv_win'] + valid['inv_loss'] + valid['inv_draw']
        valid['p_host_win'] = valid['inv_win'] / valid['total_inv']
        # valid['p_guest_win'] = valid['inv_loss'] / valid['total_inv'] # Not needed for return value
        # valid['p_draw'] = valid['inv_draw'] / valid['total_inv'] # Not needed for return value

        # Apply recency weighting (exponential decay)
        valid = valid.sort_values('Date', ascending=False)
        valid['weight'] = np.exp(-0.15 * np.arange(len(valid)))  # λ=0.15 for slower decay

        # Calculate weighted probabilities
        total_weight = valid['weight'].sum()
        host_win_prob = (valid['p_host_win'] * valid['weight']).sum() / total_weight
        # guest_win_prob = (valid['p_guest_win'] * valid['weight']).sum() / total_weight # Not needed
        # draw_prob = (valid['p_draw'] * valid['weight']).sum() / total_weight # Not needed

        # Calculate confidence metrics (simplified)
        win_std = valid['p_host_win'].std()
        confidence = max(0.3, 1 - win_std) if not pd.isna(win_std) else 0.5 # Minimum 30% confidence

        # Bayesian adjustment with prior (simplified)
        BAYESIAN_PRIOR = 0.5  # Neutral prior
        adjusted_host_prob = (host_win_prob * confidence) + (BAYESIAN_PRIOR * (1 - confidence))

        # Print results (optional for API, but good for logs)
        print(f"\n{'='*50}")
        print(f"Host Team Win Probability: {adjusted_host_prob:.2%} (Confidence: {confidence:.0%})")
        print(f"{'='*50}")

        return adjusted_host_prob # Return Host win probability


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
                win_probability = self._calculate_win_probability(df)

                # Return successful result
                return {
                    "success": True,
                    "host_team": host_team['name'],
                    "guest_team": guest_team['name'],
                    "win_probability": round(win_probability, 4), # Round for cleaner output
                    "confidence": "High" if win_probability > 0.6 or win_probability < 0.4 else "Medium" if 0.45 <= win_probability <= 0.55 else "Low",
                    "total_matches_analyzed": len(df),
                    "message": "Calculation completed successfully."
                }, 200

            except Exception as e:
                print(f"Error in compare_and_calculate: {e}")
                import traceback
                traceback.print_exc() # Log the full traceback
                return {"error": f"Scraping/calculation failed: {str(e)}"}, 500
            finally:
                browser.close()