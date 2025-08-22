# streamlit_app.py
import streamlit as st
import requests
import time

# --- Configuration ---
FLASK_API_BASE_URL = "http://127.0.0.1:5000"
# ---------------------

# --- Session State Initialization ---
SESSION_KEYS = ['logged_in', 'auth_token', 'leagues_teams_data', 'selected_country']
DEFAULTS = [False, None, None, ""]

for key, default in zip(SESSION_KEYS, DEFAULTS):
    if key not in st.session_state:
        st.session_state[key] = default
# ------------------------------------

# --- Helper Functions ---
def make_api_request(method, endpoint, data=None, params=None):
    """Helper function to make authenticated API requests."""
    url = f"{FLASK_API_BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if st.session_state.get('auth_token'):
        headers["Authorization"] = f"Bearer {st.session_state['auth_token']}"

    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json(), response.status_code
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response else 500
        error_msg = f"API request failed: {e}"
        try:
            if e.response:
                error_data = e.response.json()
                error_msg += f" | Details: {error_data}"
        except:
            if e.response:
                error_msg += f" | Response text: {e.response.text}"
        return {"error": error_msg}, status_code

def display_probability_card(label, probability, odds, column):
    """
    Helper to display a probability metric in a styled card using Streamlit elements.
    Uses st.card if available (Streamlit >= 1.33.0), otherwise a styled container.
    """
    with column:
        try:
            card = st.card()
            with card:
                st.markdown(f"**{label}**") # Use markdown for bold label
                st.metric(label="", value=f"{probability:.2%}") # Empty label for metric to avoid double label
                st.markdown(f"<small style='color: #888;'>Odds: **{odds:.2f}**</small>", unsafe_allow_html=True)
        except AttributeError:
            card_container = st.container()
            with card_container:
                st.markdown(f"**{label}**")
                st.metric(label="", value=f"{probability:.2%}")
                st.markdown(f"<small style='color: #888;'>Odds: **{odds:.2f}**</small>", unsafe_allow_html=True)
                st.markdown("---", unsafe_allow_html=True)

def handle_login():
    """Handles the login process."""
    st.title("Corner Stats Predictor - Login")
    st.markdown("Please log in with your Corner-Stats.com credentials.")

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="your.email@example.com")
        password = st.text_input("Password", type="password", placeholder="Your password")
        submitted = st.form_submit_button("🔐 Login")

        if not submitted:
            return

        if not email or not password:
            st.warning("⚠️ Please enter both email and password.")
            return

        with st.spinner("Logging in..."):
            login_data = {"email": email, "password": password}
            response_data, status_code = make_api_request('POST', '/api/login', data=login_data)

        if status_code == 200 and response_data and 'token' in response_data:
            st.session_state['logged_in'] = True
            st.session_state['auth_token'] = response_data['token']
            st.success("✅ Login successful!")
            time.sleep(0.5)
            st.rerun()
        elif status_code == 401:
            st.error("❌ Invalid email or password.")
        else:
            error_detail = response_data.get('error', 'Unknown error') if isinstance(response_data, dict) else response_data
            st.error(f"❌ Login failed (Status: {status_code}). {error_detail}")

def handle_logout():
    """Handles the logout process."""
    # Clear session state
    for key in SESSION_KEYS:
        st.session_state[key] = DEFAULTS[SESSION_KEYS.index(key)] # Reset to default
    st.success("You have been logged out.")
    time.sleep(0.5)
    st.rerun()

def render_sidebar():
    """Renders the sidebar content."""
    with st.sidebar:
        st.title("⚽ Predictor")
        st.markdown(f"**User:**")
        if st.button("🚪 Logout"):
            handle_logout()
        st.divider()
        st.markdown("**About**")
        st.info("Predict match outcomes using data from Corner-Stats.com.")

def fetch_leagues_teams():
    """Handles fetching leagues and teams."""
    if not st.session_state['selected_country'].strip():
        st.warning("⚠️ Please enter a country name.")
        return

    with st.spinner("Fetching data..."):
        data, status = make_api_request('GET', '/api/leagues_teams', params={'country_name': st.session_state['selected_country']})

    if status == 200 and data and 'leagues' in data:
        st.session_state['leagues_teams_data'] = data
        st.success(f"✅ Data fetched for **{data.get('country', 'Unknown')}**")
    elif status == 404:
        st.warning(f"⚠️ Country '{st.session_state['selected_country']}' not found.")
        st.session_state['leagues_teams_data'] = None
    elif status == 401:
        st.error("❌ Session expired. Please log in again.")
        st.session_state['logged_in'] = False
        st.session_state['auth_token'] = None
        st.rerun()
    else:
        error_detail = data.get('error', 'Unknown error') if isinstance(data, dict) else data
        st.error(f"❌ Failed to fetch data (Status: {status}). {error_detail}")
        st.session_state['leagues_teams_data'] = None

def select_teams_and_filters():
    """Handles team selection and filter configuration UI."""
    data = st.session_state['leagues_teams_data']
    country_name = data.get('country', 'Unknown')
    leagues = data.get('leagues', [])

    if not leagues:
        st.info("ℹ️ No leagues found for the selected country.")
        return None, None, None, None, None, None, None # Return Nones if no leagues

    league_names = [league['name'] for league in leagues]
    selected_league_name = st.selectbox("🏆 Select League:", league_names, key='league_select')
    selected_league = next((l for l in leagues if l['name'] == selected_league_name), None)

    if not selected_league or 'teams' not in selected_league:
        st.warning("⚠️ League data is incomplete.")
        return None, None, None, None, None, None, None

    teams = selected_league['teams']
    if len(teams) < 2:
        st.warning("⚠️ Not enough teams in the selected league.")
        return None, None, None, None, None, None, None

    team_names = [team['name'] for team in teams]
    col_host, col_guest = st.columns(2)
    with col_host:
        host_team_name = st.selectbox("HomeAsTeam:", team_names, key='host_team')
    with col_guest:
        # Allow selecting the same team, validation can be stricter if needed
        guest_team_name = st.selectbox("Away Team:", team_names, index=1 if len(team_names) > 1 else 0, key='guest_team')

    if host_team_name == guest_team_name:
        st.warning("⚠️ Home and Away teams are the same.")

    st.header("3️⃣ Configure Filters")
    filters_expander = st.expander("🔧 Show Filter Options", expanded=True)
    with filters_expander:
        col_filter1, col_filter2, col_filter3 = st.columns(3)
        with col_filter1:
            tournament_choice_display = st.selectbox(
                "Tournament Types:",
                options=[('Both Leagues & Cups', 'b'), ('League Only', 'l'), ('Cups Only', 'c'), ('Skip Filter', 's')],
                format_func=lambda x: x[0],
                help="Select tournament types."
            )
            tournament_choice = tournament_choice_display[1]

        with col_filter2:
            season_choice_display = st.selectbox(
                "Seasons:",
                options=[('All Seasons', 'all'), ('Skip Filter', 'skip')],
                format_func=lambda x: x[0],
                help="Select seasons."
            )
            season_choice = season_choice_display[1]

        with col_filter3:
            venue_choice_display = st.selectbox(
                "Venue:",
                options=[('Both Home & Away', 'b'), ('Home Only', 'h'), ('Away Only', 'a'), ('Skip Filter', 's')],
                format_func=lambda x: x[0],
                help="Select venue."
            )
            venue_choice = venue_choice_display[1]

    calculate_button = st.button("📊 Calculate Probabilities", type="primary", use_container_width=True)

    # Find team data objects
    host_team_data = next((t for t in teams if t['name'] == host_team_name), None)
    guest_team_data = next((t for t in teams if t['name'] == guest_team_name), None)

    return host_team_data, guest_team_data, country_name, tournament_choice, season_choice, venue_choice, calculate_button

def display_results(result_data, status_code):
    """Handles displaying the calculation results."""
    if status_code != 200:
        if status_code == 401:
            st.error("❌ Session expired. Please log in again.")
            st.session_state['logged_in'] = False
            st.session_state['auth_token'] = None
            st.rerun()
        else:
            error_detail = result_data.get('error', 'Unknown error') if isinstance(result_data, dict) else result_data
            st.error(f"❌ Calculation failed (Status: {status_code}). {error_detail}")
        return

    if not result_data:
         st.error("❌ No data received from calculation.")
         return

    if not result_data.get('success'):
        error_msg = result_data.get('error', 'Calculation could not be completed.')
        if any(phrase in error_msg for phrase in [
            "No match data available",
            "No valid historical match data found",
            "Insufficient valid odds data found",
            "No data extracted from table"
        ]):
            st.info(f"ℹ️ Prediction unavailable: {error_msg}")
        else:
            st.warning(f"⚠️ Calculation issue: {error_msg}")
        if 'host_team' in result_data and 'guest_team' in result_data:
            st.write(f"**Teams Analyzed:** {result_data['host_team']} vs {result_data['guest_team']}")
        return

    # --- Successful Result Display ---
    st.subheader(f"🎯 Prediction Results: {result_data['host_team']} vs {result_data['guest_team']}")

    st.markdown("**1️⃣ Match Outcome Probabilities (1X2):**")
    col1, col2, col3 = st.columns(3)
    display_probability_card(f"**{result_data['host_team']} Win**", result_data['probabilities']['host_win'], result_data['odds']['host_win'], col1)
    display_probability_card("**Draw**", result_data['probabilities']['draw'], result_data['odds']['draw'], col2)
    display_probability_card(f"**{result_data['guest_team']} Win**", result_data['probabilities']['guest_win'], result_data['odds']['guest_win'], col3)

    st.markdown("**2️⃣ ⚽ Goal-Based Probabilities:**")
    goal_cols = st.columns(4)
    display_probability_card("**Over 1.5 Goals**", result_data['probabilities']['over_1_5'], result_data['odds']['over_1_5'], goal_cols[0])
    display_probability_card("**Over 2.5 Goals**", result_data['probabilities']['over_2_5'], result_data['odds']['over_2_5'], goal_cols[1])
    display_probability_card("**Over 3.5 Goals**", result_data['probabilities']['over_3_5'], result_data['odds']['over_3_5'], goal_cols[2])
    display_probability_card("**Both Teams Score (BTTS)**", result_data['probabilities']['btts'], result_data['odds']['btts'], goal_cols[3])

    st.markdown("**3️⃣ handicap Probabilities:**")
    ah_cols = st.columns(4)
    display_probability_card(f"**{result_data['host_team']} -0.25**", result_data['probabilities']['ah_m0_25_home_prob'], result_data['odds']['ah_m0_25_home_odds'], ah_cols[0])
    display_probability_card(f"**{result_data['guest_team']} -0.25**", result_data['probabilities']['ah_m0_25_away_prob'], result_data['odds']['ah_m0_25_away_odds'], ah_cols[1])
    display_probability_card(f"**{result_data['host_team']} -2.5**", result_data['probabilities']['ah_m2_5_home_prob'], result_data['odds']['ah_m2_5_home_odds'], ah_cols[2])
    display_probability_card(f"**{result_data['guest_team']} -2.5**", result_data['probabilities']['ah_m2_5_away_prob'], result_data['odds']['ah_m2_5_away_odds'], ah_cols[3])
    
    st.divider()
    info_cols = st.columns(2)
    with info_cols[0]:
        st.metric("Total Matches Analyzed", result_data.get('total_matches_analyzed', 'N/A'))
    with info_cols[1]:
        confidence_val = result_data.get('confidence', 0)
        confidence_label = "High" if confidence_val > 0.7 else "Medium" if confidence_val > 0.5 else "Low"
        st.metric("Model Confidence", f"{confidence_val:.0%} ({confidence_label})")
    st.success(result_data.get('message', 'Calculation completed successfully.'))

def handle_prediction():
    """Handles the prediction workflow after teams/filters are selected."""
    selection_result = select_teams_and_filters()
    # Unpack results
    host_team_data, guest_team_data, country_name, tournament_choice, season_choice, venue_choice, calculate_button = selection_result

    # Check if we have valid data and button was pressed
    if not all([host_team_data, guest_team_data]) and calculate_button:
         st.error("❌ Error finding selected team data. Please try again.")
         return
    if not calculate_button:
        return # Do nothing if button not pressed

    # Prepare data for API call
    payload = {
        "host_team": host_team_data,
        "guest_team": guest_team_data,
        "country_name": country_name,
        "filters": {
            "tournament_type": tournament_choice,
            "seasons": season_choice,
            "venue": venue_choice
        }
    }

    st.header("4️⃣ Results")
    with st.spinner("🧠 Calculating probabilities..."):
        result_data, status_code = make_api_request('POST', '/api/compare_and_calculate', data=payload)

    display_results(result_data, status_code)
    
def render_main_app():
    """Renders the main application interface."""
    st.set_page_config(page_title="Corner Stats Predictor", page_icon="⚽", layout="wide")
    render_sidebar()
    
    # Wrap main content in a container for better control
    main_container = st.container()
    with main_container:
        st.title("⚽ Corner Stats Predictor")

        # Wrap section content in a container for padding/structure
        country_section = st.container()
        with country_section:
            st.header("1️⃣ Select Country")
            col_input, col_button = st.columns([3, 1])
            with col_input:
                st.session_state['selected_country'] = st.text_input(
                    "Enter Country Name:",
                    value=st.session_state['selected_country'],
                    placeholder="e.g., Bulgaria, England..."
                )
            with col_button:
                if st.button("🔍 Fetch", type="primary", use_container_width=True):
                    fetch_leagues_teams()

        # Only show if data is available, wrapped in a container
        if st.session_state['leagues_teams_data']:
            prediction_section = st.container()
            with prediction_section:
                st.header("2️⃣ Select League and Teams")
                handle_prediction() # This includes team selection, filters, and calculation trigger/display

def main():
    """Main Streamlit app logic."""
    if not st.session_state['logged_in']:
        handle_login()
    else:
        render_main_app()

if __name__ == "__main__":
    main()