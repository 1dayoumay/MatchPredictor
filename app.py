from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from scraper import CornerStatsAuth, CornerStatsDataScraper
import time

app = Flask(__name__)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    print(data)
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    auth = CornerStatsAuth()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        page = browser.new_page()
        
        try:
            page.goto("https://corner-stats.com")
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            
            if auth.login(page, email, password):
                return jsonify({"message": "Login successful"}), 200
            else:
                return jsonify({"error": "Login failed"}), 401
                
        except Exception as e:
            return jsonify({"error": f"Login process error: {str(e)}"}), 500
        finally:
            browser.close()

@app.route('/api/leagues_teams', methods=['GET'])
def api_get_leagues_teams():
    country_name = request.args.get('country_name')

    if not country_name:
        return jsonify({"error": "Missing required parameter: country_name"}), 400

    scraper = CornerStatsDataScraper()
    data, status_code = scraper.get_leagues_and_teams(country_name)

    return jsonify(data), status_code

@app.route('/api/compare_and_calculate', methods=['POST'])
def api_compare_and_calculate():
    """API endpoint to compare teams, apply filters, scrape data, and calculate win probability."""
    # Get JSON data from request
    data = request.get_json()

    # Validate input data
    required_fields = ['host_team', 'guest_team', 'country_name', 'filters']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    host_team = data['host_team']
    guest_team = data['guest_team']
    country_name = data['country_name']
    filters = data['filters']

    # Validate team data structure
    if not isinstance(host_team, dict) or 'id' not in host_team or 'name' not in host_team:
        return jsonify({"error": "Invalid host_team format. Expected {'id': '...', 'name': '...'}"}), 400
    if not isinstance(guest_team, dict) or 'id' not in guest_team or 'name' not in guest_team:
        return jsonify({"error": "Invalid guest_team format. Expected {'id': '...', 'name': '...'}"}), 400

    # Validate filters data structure (basic)
    if not isinstance(filters, dict):
        return jsonify({"error": "Invalid filters format. Expected a JSON object."}), 400

    # Create scraper instance and call the method
    scraper = CornerStatsDataScraper()
    result_data, status_code = scraper.compare_and_calculate(host_team, guest_team, country_name, filters)

    # Return the result with the appropriate status code
    return jsonify(result_data), status_code

if __name__ == '__main__':
    app.run(debug=True)