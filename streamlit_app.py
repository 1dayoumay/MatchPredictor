# streamlit_app.py
import streamlit as st
import requests
import time

# --- Configuration ---
FLASK_API_BASE_URL = "http://localhost:5000" # Adjust if your Flask API runs elsewhere
# ---------------------

# --- Session State Initialization ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'auth_token' not in st.session_state:
    st.session_state['auth_token'] = None
if 'leagues_teams_data' not in st.session_state:
    st.session_state['leagues_teams_data'] = None
if 'selected_country' not in st.session_state:
    st.session_state['selected_country'] = ""
# ------------------------------------

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
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        return response.json(), response.status_code
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
             try:
                 error_data = e.response.json()
                 st.error(f"Error details: {error_data}")
             except:
                 st.error(f"Response text: {e.response.text}")
        return None, (e.response.status_code if hasattr(e, 'response') and e.response else 500)


def login_page():
    """Display the login form and handle login logic."""
    st.title("Corner Stats Predictor - Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            if not email or not password:
                st.warning("Please enter both email and password.")
                return

            login_data = {"email": email, "password": password}
            response_data, status_code = make_api_request('POST', '/api/login', data=login_data)

            if status_code == 200 and response_data and 'token' in response_data:
                st.session_state['logged_in'] = True
                st.session_state['auth_token'] = response_data['token']
                st.success("Login successful!")
                time.sleep(1) # Brief pause before rerun
                st.rerun() # Rerun the script to switch to the main app
            elif status_code == 401:
                st.error("Invalid email or password.")
            else:
                st.error(f"Login failed (Status: {status_code}). Please check credentials and API.")

def main_app():
    """Display the main application interface after login."""
    st.title("⚽ Corner Stats Predictor")

    # Logout button in the sidebar
    with st.sidebar:
        st.write(f"Logged in")
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.session_state['auth_token'] = None
            st.session_state['leagues_teams_data'] = None
            st.session_state['selected_country'] = ""
            st.rerun()

    # --- Step 1: Select Country ---
    st.header("1. Select Country")
    # Simple input for country name for now. Could fetch list from API if needed.
    selected_country = st.text_input("Enter Country Name:", value=st.session_state['selected_country'])

    if st.button("Fetch Leagues & Teams") and selected_country:
        st.session_state['selected_country'] = selected_country
        with st.spinner("Fetching data..."):
            data, status = make_api_request('GET', '/api/leagues_teams', params={'country_name': selected_country})

        if status == 200 and data:
            st.session_state['leagues_teams_data'] = data
            st.success(f"Data fetched for {data.get('country', 'Unknown')}")
        elif status == 404:
            st.warning(f"Country '{selected_country}' not found.")
        elif status == 401:
             st.error("Session expired. Please log in again.")
             st.session_state['logged_in'] = False
             st.session_state['auth_token'] = None
             st.rerun()
        else:
            st.error(f"Failed to fetch data (Status: {status}).")

    # --- Step 2: Select League and Teams (only if data is available) ---
    if st.session_state['leagues_teams_data']:
        st.header("2. Select League and Teams")
        data = st.session_state['leagues_teams_data']
        country_name = data.get('country', 'Unknown')
        leagues = data.get('leagues', [])

        if not leagues:
            st.info("No leagues found for the selected country.")
        else:
            # Select League
            league_names = [league['name'] for league in leagues]
            selected_league_name = st.selectbox("Select League:", league_names)

            # Find selected league data
            selected_league = next((l for l in leagues if l['name'] == selected_league_name), None)

            if selected_league and 'teams' in selected_league:
                teams = selected_league['teams']
                if len(teams) < 2:
                    st.warning("Not enough teams in the selected league to compare.")
                else:
                    # Select Teams
                    team_names = [team['name'] for team in teams]
                    col1, col2 = st.columns(2)
                    with col1:
                        host_team_name = st.selectbox("Select Host Team:", team_names, key='host')
                    with col2:
                        # Filter guest teams to exclude the host team
                        guest_team_options = [name for name in team_names if name != host_team_name]
                        if guest_team_options:
                            guest_team_name = st.selectbox("Select Guest Team:", guest_team_options, key='guest')
                        else:
                            st.warning("No other teams available for guest selection.")
                            guest_team_name = None

                    # --- Step 3: Configure Filters ---
                    st.header("3. Configure Filters")
                    with st.form("filters_form"):
                        # Tournament Type
                        tournament_choice = st.selectbox(
                            "Tournament Types:",
                            options=[('Both', 'b'), ('League Only', 'l'), ('Cups Only', 'c'), ('Skip', 's')],
                            format_func=lambda x: x[0]
                        )[1] # Get the value ('b', 'l', etc.)

                        # Seasons - For simplicity, assuming 'all' or 'skip' for now in UI
                        # A more complex UI could allow selecting specific seasons if fetched
                        season_choice = st.selectbox(
                            "Seasons:",
                            options=[('All Seasons', 'all'), ('Skip', 'skip')],
                            format_func=lambda x: x[0]
                        )[1]

                        # Venue
                        venue_choice = st.selectbox(
                            "Venue:",
                            options=[('Both Home/Away', 'b'), ('Home Only', 'h'), ('Away Only', 'a'), ('Skip', 's')],
                            format_func=lambda x: x[0]
                        )[1]

                        submitted_filters = st.form_submit_button("Calculate Win Probability")

                        if submitted_filters and host_team_name and guest_team_name:
                            # Find team data (value/id and name)
                            host_team_data = next((t for t in teams if t['name'] == host_team_name), None)
                            guest_team_data = next((t for t in teams if t['name'] == guest_team_name), None)

                            if not host_team_data or not guest_team_data:
                                st.error("Error finding selected team data.")
                                return

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

                            # --- Step 4: Call Calculation API ---
                            st.header("4. Results")
                            with st.spinner("Calculating win probability..."):
                                result_data, status_code = make_api_request('POST', '/api/compare_and_calculate', data=payload)

                            if status_code == 200 and result_data:
                                if result_data.get('success'):
                                    st.subheader(f"Prediction Result")
                                    st.metric(
                                        label=f"Win Probability for {result_data['host_team']}",
                                        value=f"{result_data['win_probability']:.2%}",
                                        delta=f"Confidence: {result_data.get('confidence', 'N/A')}"
                                    )
                                    st.write(f"**Total Matches Analyzed:** {result_data.get('total_matches_analyzed', 'N/A')}")
                                    st.success(result_data.get('message', 'Calculation completed.'))
                                else:
                                    st.error(f"Calculation error: {result_data.get('error', 'Unknown error')}")
                            elif status_code == 401:
                                st.error("Session expired. Please log in again.")
                                st.session_state['logged_in'] = False
                                st.session_state['auth_token'] = None
                                st.rerun()
                            else:
                                st.error(f"Calculation failed (Status: {status_code}). Please try again.")

def main():
    """Main Streamlit app logic."""
    if not st.session_state['logged_in']:
        login_page()
    else:
        main_app()

if __name__ == "__main__":
    main()