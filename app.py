from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from scraper import CornerStatsDataScraper, CornerStatsAuth
from functools import wraps
import time, os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

app = Flask(__name__)

# --- Security Configuration ---
# Use a strong secret key, ideally loaded from an environment variable
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your_default_secret_key_change_this') # CHANGE THIS!
# Token expires in 1 hour (3600 seconds)
app.config['TOKEN_EXPIRATION'] = 3600
# Create a serializer instance
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
# --------------------------------

def generate_token(email):
    """Generate a time-limited token for a user."""
    return serializer.dumps({'email': email})

def verify_token(token):
    """Verify a token and return the payload (email) or None."""
    try:
        payload = serializer.loads(token, max_age=app.config['TOKEN_EXPIRATION'])
        return payload['email']
    except (BadSignature, SignatureExpired):
        return None

@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        app.logger.info("Login endpoint called")
        data = request.get_json()
        app.logger.debug(f"Received data: {data}")

        if not data:
             app.logger.warning("No JSON data received")
             return jsonify({"error": "No JSON data provided"}), 400

        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            app.logger.warning("Missing email or password")
            return jsonify({"error": "Email and password are required"}), 400

        # --- Use CornerStatsAuth for login ---
        auth = CornerStatsAuth() # Instantiate the auth class

        with sync_playwright() as p:
            # Use headless=True for API calls
            browser = p.chromium.launch(headless=True, channel="msedge")
            page = browser.new_page()

            try:
                page.goto("https://corner-stats.com") # URL can be hardcoded or passed
                page.wait_for_load_state("networkidle")
                time.sleep(2)

                # --- Call the login method from CornerStatsAuth ---
                if auth.login(page, email, password): # Call the method on the auth instance
                    # Assuming CornerStatsAuth.login saves the session upon success
                    # If not, you might need to call session.save manually here,
                    # or ensure CornerStatsSession (used by CornerStatsDataScraper) loads it correctly later.
                    token = generate_token(email)
                    app.logger.info(f"Login successful for {email}")
                    return jsonify({"message": "Login successful", "token": token}), 200
                else:
                    app.logger.info(f"Login failed for {email}")
                    return jsonify({"error": "Login failed - Invalid credentials or site error"}), 401

            except Exception as e:
                app.logger.error(f"Error during Playwright operations in login for {email}: {e}", exc_info=True)
                return jsonify({"error": f"Login process error (Playwright): {str(e)}"}), 500
            finally:
                browser.close()

    except Exception as e:
        app.logger.error(f"Unhandled error in /api/login endpoint: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred during login."}), 500

def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        # Get token from the Authorization header (Bearer <token>)
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        if not token:
            return jsonify({'error': 'Token is missing!'}), 401

        email = verify_token(token)
        if not email:
            return jsonify({'error': 'Token is invalid or expired!'}), 401

        # Pass the email or user info to the function if needed
        # For now, we just check validity
        return f(*args, **kwargs)
    return decorated_function
# ------------------------------------------------

@app.route('/api/leagues_teams', methods=['GET'])
@token_required # Apply the decorator to protect this endpoint
def api_get_leagues_teams():
    # Get country name from query parameters
    country_name = request.args.get('country_name')

    if not country_name:
        return jsonify({"error": "Missing required parameter: country_name"}), 400

    scraper = CornerStatsDataScraper()
    data, status_code = scraper.get_leagues_and_teams(country_name)

    # Return the data or error with the appropriate status code
    return jsonify(data), status_code

@app.route('/api/compare_and_calculate', methods=['POST'])
@token_required # Apply the decorator to protect this endpoint
def api_compare_and_calculate():
    """API endpoint to compare teams, apply filters, and calculate win probability."""
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

    # Validate team data structure (accepting 'value' or 'id' for the ID field)
    if (not isinstance(host_team, dict) or
        'name' not in host_team or
        not ('id' in host_team or 'value' in host_team)):
        return jsonify({"error": "Invalid host_team format. Expected {'id'/'value': '...', 'name': '...'}"}), 400

    if (not isinstance(guest_team, dict) or
        'name' not in guest_team or
        not ('id' in guest_team or 'value' in guest_team)):
        return jsonify({"error": "Invalid guest_team format. Expected {'id'/'value': '...', 'name': '...'}"}), 400

    # Normalize team data to use 'id' internally if 'value' is provided
    if 'value' in host_team and 'id' not in host_team:
        host_team['id'] = host_team.pop('value')
    if 'value' in guest_team and 'id' not in guest_team:
        guest_team['id'] = guest_team.pop('value')

    # Validate filters data structure (basic)
    if not isinstance(filters, dict):
        return jsonify({"error": "Invalid filters format. Expected a JSON object."}), 400

    # Create scraper instance and call the method
    scraper = CornerStatsDataScraper()
    result_data, status_code = scraper.compare_and_calculate(host_team, guest_team, country_name, filters)

    # Return the result with the appropriate status code
    return jsonify(result_data), status_code

if __name__ == '__main__':
    # Make sure to run Flask in a production-like environment if exposing it beyond localhost
    app.run(debug=True, host='127.0.0.1', port=5000) # Default host/port, adjust if needed