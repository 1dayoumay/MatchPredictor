import requests

BASE_URL = "http://localhost:5000"
EMAIL = "test12233@abv.bg"
PASSWORD = "test12233"
COUNTRY_NAME = "Bulgaria" # Change as needed

def main():
    print("="*20 + " Testing /api/login " + "="*20)
    login_url = f"{BASE_URL}/api/login"
    login_data = {
        "email": EMAIL,
        "password": PASSWORD
    }

    try:
        login_response = requests.post(login_url, json=login_data)
        print(f"POST {login_url}")
        print(f"Status Code: {login_response.status_code}")
        
        if login_response.status_code == 200:
            print("Login successful!")
        else:
            print(f"Login failed.")
            try:
                error_data = login_response.json()
                print(f"Error: {error_data}")
            except requests.exceptions.JSONDecodeError:
                print(f"Error (non-JSON): {login_response.text}")
            return # Stop if login fails

    except requests.exceptions.RequestException as e:
        print(f"An error occurred during login request: {e}")
        return
    return
    print("\n" + "="*20 + " Testing /api/leagues_teams " + "="*20)
    leagues_teams_url = f"{BASE_URL}/api/leagues_teams"
    params = {'country_name': COUNTRY_NAME}

    try:
        response = requests.get(leagues_teams_url, params=params)
        print(f"GET {leagues_teams_url}?country_name={params['country_name']}")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            try:
                response_data = response.json()
                print("Leagues and Teams Data:")
                print(response_data)
                
                host_team_info = None
                guest_team_info = None
                if 'leagues' in response_data and response_data['leagues']:
                    for league in response_data['leagues']:
                        if 'teams' in league and league['teams']:
                            teams = league['teams']
                            if len(teams) >= 2:
                                raw_host_team = teams[0]
                                raw_guest_team = teams[1]
                                host_team_info = {"id": raw_host_team.get("value"), "name": raw_host_team.get("name")}
                                guest_team_info = {"id": raw_guest_team.get("value"), "name": raw_guest_team.get("name")}
                                print(f"\nSelected teams for comparison:")
                                print(f"  Host Team: {host_team_info}")
                                print(f"  Guest Team: {guest_team_info}")
                                break
                            elif len(teams) == 1:
                                raw_team = teams[0]
                                host_team_info = {"id": raw_team.get("value"), "name": raw_team.get("name")}
                                guest_team_info = {"id": raw_team.get("value"), "name": raw_team.get("name")} # Same team
                                print(f"\nSelected teams for comparison (same team for demo):")
                                print(f"  Host Team: {host_team_info}")
                                print(f"  Guest Team: {guest_team_info}")
                                break
                
                if not host_team_info or not guest_team_info:
                     print("\nCould not find two distinct teams in the response for the next step.")

            except requests.exceptions.JSONDecodeError:
                print("Error: Response body is not valid JSON:")
                print(response.text)
        else:
            print(f"Failed to get leagues/teams.")
            try:
                error_data = response.json()
                print(f"Error: {error_data}")
            except requests.exceptions.JSONDecodeError:
                print(f"Error (non-JSON): {response.text}")
                
    except requests.exceptions.RequestException as e:
        print(f"An error occurred during leagues/teams request: {e}")


    if host_team_info and guest_team_info:
        print("\n" + "="*20 + " Testing /api/compare_and_calculate " + "="*20)
        compare_url = f"{BASE_URL}/api/compare_and_calculate"
        
        compare_data = {
            "host_team": host_team_info, # {"id": "...", "name": "..."}
            "guest_team": guest_team_info, # {"id": "...", "name": "..."}
            "country_name": COUNTRY_NAME,
            "filters": {
                # Use values that make sense or are likely to return data
                "tournament_type": "b",  # 'l', 'c', 'b', 's' 
                "seasons": "all",        # 'all', 'skip', or list like ["2023/2024"]
                "venue": "b"             # 'h', 'a', 'b', 's'
            }
        }

        try:
            compare_response = requests.post(compare_url, json=compare_data)
            print(f"POST {compare_url}")
            print(f"Status Code: {compare_response.status_code}")
            
            if compare_response.status_code == 200:
                try:
                    result_data = compare_response.json()
                    print("Comparison and Calculation Result:")
                    print(result_data)
                except requests.exceptions.JSONDecodeError:
                    print("Error: Response body is not valid JSON:")
                    print(compare_response.text)
            else:
                print(f"Comparison/Calculation failed.")
                try:
                    error_data = compare_response.json()
                    print(f"Error: {error_data}")
                except requests.exceptions.JSONDecodeError:
                    print(f"Error (non-JSON): {compare_response.text}")

        except requests.exceptions.RequestException as e:
            print(f"An error occurred during compare/calculate request: {e}")
    else:
        print("\nSkipping /api/compare_and_calculate as team data was not available.")

if __name__ == "__main__":
    main()