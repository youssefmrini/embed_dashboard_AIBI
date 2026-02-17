"""
Flask backend for Databricks AI/BI external dashboard embedding (connection UI).

Flow:
  1. User opens app → connection UI (email + password).
  2. User submits → backend validates; if ok, session created.
  3. Frontend calls /api/dashboard/embed-config → backend mints user-scoped token.
  4. Token is passed to @databricks/aibi-client; dashboard is filtered by logged-in user's email.

The email used to log in is sent to the dashboard as __aibi_external_value.
Ref: https://docs.databricks.com/aws/en/dashboards/embedding/external-embed
"""

import json
import os
import time
import base64
import urllib.parse
from datetime import datetime
from pathlib import Path
from functools import wraps

import requests
from flask import Flask, jsonify, request, session, send_from_directory
from flask_cors import CORS

try:
    from dotenv import load_dotenv
    load_dotenv('.env')
except ImportError:
    pass

try:
    from werkzeug.middleware.proxy_fix import ProxyFix
except ImportError:
    ProxyFix = None


# -----------------------------------------------------------------------------
# App and config
# -----------------------------------------------------------------------------

app = Flask(__name__, static_folder='static', static_url_path='')

if ProxyFix:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-for-demo')
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

_ON_DATABRICKS = os.environ.get('DATABRICKS_APP_PORT') is not None
app.config['SESSION_COOKIE_SAMESITE'] = 'None' if _ON_DATABRICKS else 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True

allowed_origins = ['http://localhost:3000', 'http://127.0.0.1:3000']
if os.environ.get('CORS_ORIGIN'):
    allowed_origins.append(os.environ.get('CORS_ORIGIN').rstrip('/'))
CORS(app, supports_credentials=True, origins=allowed_origins)


@app.after_request
def _cors_databricks_apps(response):
    if not _ON_DATABRICKS:
        return response
    origin = request.headers.get('Origin')
    if origin and '.databricksapps.com' in origin and request.path.startswith('/api/'):
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


def _env(key: str, fallback_key: str = None, default: str = '') -> str:
    value = os.environ.get(key) or (os.environ.get(fallback_key) if fallback_key else None)
    return (value or default).rstrip('/') if value else default


# -----------------------------------------------------------------------------
# Allowed users: email + password. Logged-in email is passed to dashboard as __aibi_external_value.
# -----------------------------------------------------------------------------

# Passwords stored here for demo; use a proper auth store in production.
ALLOWED_USERS = {
    'youssef.mrini@databricks.com': {
        'id': 'user_youssef',
        'name': 'Youssef Mrini',
        'email': 'youssef.mrini@databricks.com',
        'department': 'Viewer',
        'password': 'realmadrid10.!',
    },
    'hanane.oudnia@databricks.com': {
        'id': 'user_hanane',
        'name': 'Hanane Oudnia',
        'email': 'hanane.oudnia@databricks.com',
        'department': 'Viewer',
        'password': 'realmadrid10.!',
    },
}


def _user_for_response(user: dict) -> dict:
    """Return user dict without password for API responses."""
    return {k: v for k, v in user.items() if k != 'password'}


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return wrapped


# -----------------------------------------------------------------------------
# Databricks OAuth: mint user-scoped token (same as dashboard_embed)
# -----------------------------------------------------------------------------

def mint_databricks_token(user_data: dict) -> dict:
    """Mint token; user_data['email'] is sent as external_viewer_id and external_value (__aibi_external_value)."""
    workspace_url = _env('INSTANCE_URL', 'DATABRICKS_WORKSPACE_URL')
    client_id = _env('OAUTH_CLIENT_ID', 'DATABRICKS_CLIENT_ID')
    client_secret = _env('OAUTH_SECRET', 'DATABRICKS_CLIENT_SECRET')
    dashboard_id = _env('DASHBOARD_ID', 'DATABRICKS_DASHBOARD_ID')

    if not all([workspace_url, client_id, client_secret, dashboard_id]):
        raise Exception('Missing config. Set INSTANCE_URL, OAUTH_CLIENT_ID, OAUTH_SECRET, DASHBOARD_ID, WORKSPACE_ID.')

    basic_auth = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
    user_email = (user_data.get('email') or '').strip()

    oidc = requests.post(
        f'{workspace_url}/oidc/v1/token',
        headers={'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': f'Basic {basic_auth}'},
        data=urllib.parse.urlencode({'grant_type': 'client_credentials', 'scope': 'all-apis'}),
    )
    if oidc.status_code != 200:
        raise Exception(f'OIDC token failed: {oidc.status_code} - {oidc.text}')
    oidc_token = oidc.json()['access_token']

    tokeninfo_url = (
        f'{workspace_url}/api/2.0/lakeview/dashboards/{dashboard_id}/published/tokeninfo'
        f'?external_viewer_id={urllib.parse.quote(user_email)}&external_value={urllib.parse.quote(user_email)}'
    )
    ti = requests.get(tokeninfo_url, headers={'Authorization': f'Bearer {oidc_token}'})
    if ti.status_code != 200:
        raise Exception(f'Token info failed: {ti.status_code} - {ti.text}')
    token_info = ti.json()

    params = token_info.copy()
    auth_details = params.pop('authorization_details', None)
    params['grant_type'] = 'client_credentials'
    params['authorization_details'] = json.dumps(auth_details)
    scoped = requests.post(
        f'{workspace_url}/oidc/v1/token',
        headers={'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': f'Basic {basic_auth}'},
        data=urllib.parse.urlencode(params),
    )
    if scoped.status_code != 200:
        raise Exception(f'Scoped token failed: {scoped.status_code} - {scoped.text}')

    data = scoped.json()
    return {
        'access_token': data['access_token'],
        'token_type': 'Bearer',
        'expires_in': data.get('expires_in', 3600),
        'created_at': int(time.time()),
    }


# -----------------------------------------------------------------------------
# API: Auth (email + password connection)
# -----------------------------------------------------------------------------

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Log in with email and password. The email is the one passed to the dashboard as __aibi_external_value."""
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    user = ALLOWED_USERS.get(email)
    if not user or user.get('password') != password:
        return jsonify({'error': 'Invalid email or password'}), 401

    session['user_id'] = user['id']
    session['username'] = email
    return jsonify({'success': True, 'user': _user_for_response(user)})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})


@app.route('/api/auth/current-user', methods=['GET'])
@login_required
def get_current_user():
    username = session.get('username')
    user = ALLOWED_USERS.get(username)
    if not user:
        session.clear()
        return jsonify({'error': 'User not found'}), 401
    return jsonify(_user_for_response(user))


# -----------------------------------------------------------------------------
# API: Dashboard embed config
# -----------------------------------------------------------------------------

@app.route('/api/dashboard/embed-config', methods=['GET'])
@login_required
def get_embed_config():
    """Return embed config and token; logged-in user's email is sent to the dashboard."""
    username = session.get('username')
    user = ALLOWED_USERS.get(username)
    if not user:
        session.clear()
        return jsonify({'error': 'User not found'}), 401

    try:
        token_data = mint_databricks_token(user)
    except Exception as e:
        app.logger.exception('Token minting failed')
        return jsonify({'error': str(e)}), 500

    return jsonify({
        'workspace_url': _env('INSTANCE_URL', 'DATABRICKS_WORKSPACE_URL'),
        'workspace_id': str(_env('WORKSPACE_ID', 'DATABRICKS_WORKSPACE_ID') or ''),
        'dashboard_id': str(_env('DASHBOARD_ID', 'DATABRICKS_DASHBOARD_ID') or ''),
        'warehouse_id': os.environ.get('DATABRICKS_WAREHOUSE_ID'),
        'embed_token': token_data['access_token'],
        'token_expires_in': token_data['expires_in'],
        'user_context': _user_for_response(user),
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})


@app.route('/api/config-check', methods=['GET'])
def config_check():
    return jsonify({
        'INSTANCE_URL': _env('INSTANCE_URL', 'DATABRICKS_WORKSPACE_URL') or '(not set)',
        'WORKSPACE_ID': _env('WORKSPACE_ID', 'DATABRICKS_WORKSPACE_ID') or '(not set)',
        'DASHBOARD_ID': _env('DASHBOARD_ID', 'DATABRICKS_DASHBOARD_ID') or '(not set)',
        'OAUTH_CLIENT_ID_set': bool(_env('OAUTH_CLIENT_ID', 'DATABRICKS_CLIENT_ID')),
        'OAUTH_SECRET_set': bool(_env('OAUTH_SECRET', 'DATABRICKS_CLIENT_SECRET')),
    })


# -----------------------------------------------------------------------------
# Static frontend
# -----------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / 'static'
if STATIC_DIR.exists() and (STATIC_DIR / 'index.html').exists():
    @app.route('/')
    def index():
        return send_from_directory(STATIC_DIR, 'index.html')

    @app.route('/<path:path>')
    def serve_static(path):
        if (STATIC_DIR / path).is_file():
            return send_from_directory(STATIC_DIR, path)
        return send_from_directory(STATIC_DIR, 'index.html')


if __name__ == '__main__':
    port = int(os.environ.get('DATABRICKS_APP_PORT') or os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])
