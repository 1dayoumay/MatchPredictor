import secrets
import os

# Generate a strong random key
secret_key = secrets.token_hex(32) # 64-character hexadecimal string

# Set it as an environment variable
os.environ['FLASK_SECRET_KEY'] = secret_key

print(f"Generated and set FLASK_SECRET_KEY: {secret_key}")
# Note: This sets it only for the current Python process and its children.
# It will not persist after the script finishes.