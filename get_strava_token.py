#!/usr/bin/env python3
"""
Get Strava OAuth token with correct scopes
"""

import webbrowser
import http.server
import socketserver
import urllib.parse
from urllib.parse import urlparse, parse_qs
import requests
import json

# Your Strava app credentials
CLIENT_ID = input("Enter your Strava Client ID: ").strip()
CLIENT_SECRET = input("Enter your Strava Client Secret: ").strip()

# OAuth settings
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = "activity:read_all"  # Need this to read activities and download files

# Step 1: Generate authorization URL
auth_url = (
    f"https://www.strava.com/oauth/authorize"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    f"&response_type=code"
    f"&scope={SCOPES}"
)

print("\n" + "="*80)
print("STEP 1: Authorize the application")
print("="*80)
print(f"\nOpening browser to authorize...")
print(f"\nIf browser doesn't open, visit this URL:")
print(f"\n{auth_url}\n")

# Open browser
webbrowser.open(auth_url)

# Step 2: Start local server to catch the callback
print("Waiting for authorization callback...")

authorization_code = None

class CallbackHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global authorization_code
        
        # Parse the callback URL
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        if 'code' in params:
            authorization_code = params['code'][0]
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <body>
                    <h1>Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
            """)
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Error: No authorization code received</h1></body></html>")
    
    def log_message(self, format, *args):
        pass  # Suppress log messages

# Start server
with socketserver.TCPServer(("", 8000), CallbackHandler) as httpd:
    httpd.handle_request()

if not authorization_code:
    print("\nError: No authorization code received")
    exit(1)

print(f"\n✓ Authorization code received")

# Step 3: Exchange code for access token
print("\n" + "="*80)
print("STEP 2: Exchange code for access token")
print("="*80)

token_url = "https://www.strava.com/oauth/token"
token_data = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "code": authorization_code,
    "grant_type": "authorization_code"
}

response = requests.post(token_url, data=token_data)

if response.status_code == 200:
    tokens = response.json()
    
    print("\n✓ Tokens received successfully!\n")
    print("="*80)
    print("SAVE THESE TOKENS:")
    print("="*80)
    print(f"\nAccess Token:  {tokens['access_token']}")
    print(f"Refresh Token: {tokens['refresh_token']}")
    print(f"Expires At:    {tokens['expires_at']}")
    print(f"\nAthlete: {tokens['athlete']['firstname']} {tokens['athlete']['lastname']}")
    
    # Save to file
    with open('strava_tokens.json', 'w') as f:
        json.dump(tokens, f, indent=2)
    
    print(f"\n✓ Tokens saved to: strava_tokens.json")
    print("\n" + "="*80)
    
else:
    print(f"\n✗ Error getting tokens: {response.status_code}")
    print(response.text)
    exit(1)
