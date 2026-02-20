Databricks AI/BI Dashboard External Embedding GuideThis guide outlines the process for securely embedding Databricks AI/BI dashboards into external applications using service principals and user-scoped tokens.Table of ContentsAuthentication FlowSecurity & Data FilteringSetup OverviewPrerequisitesStep-by-Step ImplementationExample Application (Python)Rate Limits & LimitationsAuthentication FlowThe embedding process uses a multi-step token exchange to ensure that the end-user never sees the high-level service principal credentials.User Authentication: User signs into your application.Service Principal Auth: Your server uses a Service Principal Secret to request an OIDC OAuth token (scoped to all-apis) from Databricks.Token Info Exchange: Your server calls the /tokeninfo endpoint using the broad token, passing user-specific identifiers (external_viewer_id).User-Scoped Token Generation: Your server generates a tightly-scoped token based on the /tokeninfo response.Dashboard Rendering: The frontend uses the @databricks/aibi-client library to render the dashboard using this specific user-scoped token.Security & Data FilteringTo ensure users only see the data they are authorized to view, we use two primary identifiers:IdentifierDescriptionPII Allowed?external_viewer_idUnique ID used for audit logs. Must be unique per user.Noexternal_valueA global variable passed into SQL queries for filtering.YesDynamic Filtering in SQLIn your Databricks dataset, you can reference the external_value using the prefix __aibi_external_value:SQLSELECT * FROM sales_data 
WHERE region = :__aibi_external_value
PrerequisitesPermissions: CAN MANAGE permissions on a published dashboard.Databricks CLI: Version 0.205 or higher.Domain Whitelisting: Workspace admins must add your application's domain to the "Approved Domains" list in Databricks settings.Network: An external application or server to host the embedded content.Step-by-Step ImplementationStep 1: Create a Service PrincipalGo to Settings > Identity and access > Service principals.Click Add service principal > Add new.Record the Application ID.Ensure Databricks SQL access and Workspace access are enabled.Step 2: Generate OAuth SecretOn the Service Principal page, go to the Secrets tab.Click Generate secret.Copy the secret immediately. You will not be able to see it again.Step 3: Assign Dashboard PermissionsOpen the dashboard you wish to embed.Click Share.Search for your Service Principal and grant CAN RUN permissions.Note the Dashboard ID from the URL (the UUID between /dashboards/ and the next slash).Example Application (Python)Save this file as example.py. It handles the token exchange and serves a basic HTML page containing the embedded dashboard.Python#!/usr/bin/env python3
import os
import sys
import json
import base64
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- Configuration ---
CONFIG = {
    "instance_url": os.environ.get("INSTANCE_URL"),
    "dashboard_id": os.environ.get("DASHBOARD_ID"),
    "service_principal_id": os.environ.get("SERVICE_PRINCIPAL_ID"),
    "service_principal_secret": os.environ.get("SERVICE_PRINCIPAL_SECRET"),
    "external_viewer_id": os.environ.get("EXTERNAL_VIEWER_ID"),
    "external_value": os.environ.get("EXTERNAL_VALUE"),
    "workspace_id": os.environ.get("WORKSPACE_ID"),
    "port": int(os.environ.get("PORT", 3000)),
}

auth_str = f"{CONFIG['service_principal_id']}:{CONFIG['service_principal_secret']}"
basic_auth = base64.b64encode(auth_str.encode()).decode()

def http_request(url, method="GET", headers=None, body=None):
    headers = headers or {}
    req = urllib.request.Request(url, method=method, headers=headers)
    if body:
        req.data = body.encode() if isinstance(body, str) else body
    
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode()
            return {"data": json.loads(data)}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()}")

def get_scoped_token():
    # 1. Get all-api token
    oidc_res = http_request(
        f"{CONFIG['instance_url']}/oidc/v1/token",
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {basic_auth}",
        },
        body=urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "all-apis"})
    )
    oidc_token = oidc_res["data"]["access_token"]

    # 2. Get token info
    token_info_url = (
        f"{CONFIG['instance_url']}/api/2.0/lakeview/dashboards/"
        f"{CONFIG['dashboard_id']}/published/tokeninfo"
        f"?external_viewer_id={urllib.parse.quote(CONFIG['external_viewer_id'])}"
        f"&external_value={urllib.parse.quote(CONFIG['external_value'])}"
    )
    token_info = http_request(
        token_info_url,
        headers={"Authorization": f"Bearer {oidc_token}"}
    )["data"]

    # 3. Generate scoped token
    params = token_info.copy()
    auth_details = params.pop("authorization_details", None)
    params.update({
        "grant_type": "client_credentials",
        "authorization_details": json.dumps(auth_details)
    })

    scoped_res = http_request(
        f"{CONFIG['instance_url']}/oidc/v1/token",
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {basic_auth}",
        },
        body=urllib.parse.urlencode(params)
    )
    return scoped_res["data"]["access_token"]

def generate_html(token):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Databricks Embedded Dashboard</title>
        <style>
            body {{ font-family: system-ui; margin: 0; padding: 20px; background: #f5f5f5; }}
            #dashboard-content {{ height: calc(100vh - 40px); width: 100%; border: 1px solid #ccc; }}
        </style>
    </head>
    <body>
        <div id="dashboard-content"></div>
        <script type="module">
            import {{ DatabricksDashboard }} from "https://cdn.jsdelivr.net/npm/@databricks/aibi-client@0.0.0-alpha.7/+esm";
            const dashboard = new DatabricksDashboard({{
                instanceUrl: "{CONFIG['instance_url']}",
                workspaceId: "{CONFIG['workspace_id']}",
                dashboardId: "{CONFIG['dashboard_id']}",
                token: "{token}",
                container: document.getElementById("dashboard-content")
            }});
            dashboard.initialize();
        </script>
    </body>
    </html>
    """

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return

        try:
            token = get_scoped_token()
            html = generate_html(token)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}".encode())

if __name__ == "__main__":
    server = HTTPServer(("localhost", CONFIG["port"]), RequestHandler)
    print(f"Server running on http://localhost:{CONFIG['port']}")
    server.serve_forever()
Rate Limits & LimitationsRate Limits: There is a limit of 20 dashboard loads per second. While you can have more than 20 dashboards open simultaneously, no more than 20 can initiate the loading process in the same second.Ask Genie: The "Ask Genie" natural language button is not supported in external embedding.Solution: Use the Genie Conversation API to integrate natural language querying programmatically into your application.
