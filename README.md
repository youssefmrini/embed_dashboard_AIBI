Databricks AI/BI Dashboard: External Embedding GuideThis documentation provides a comprehensive walkthrough for securely embedding Databricks AI/BI dashboards into external applications using User-Scoped Tokens.🏗️ Architecture & Authentication FlowThe embedding process utilizes a "Double Token Exchange" to ensure that your Service Principal's secret is never exposed to the client-side browser.Authenticated Request: The user signs into your app; your frontend requests a dashboard access token from your server.Service Principal Auth: Your server uses its secret to request a broad all-apis OAuth token from Databricks.Token Info Exchange: Your server calls the /tokeninfo endpoint with the broad token to provide user context (external_viewer_id).Scoped Token Generation: Your server generates a tightly-scoped token specifically for that user.Secure Rendering: The frontend uses the @databricks/aibi-client library and the scoped token to render the dashboard.🔐 Security & Data FilteringTo maintain data multi-tenancy (ensuring User A doesn't see User B's data), we use two specific identifiers:PropertyDescriptionPII Allowed?Use Caseexternal_viewer_idA unique, non-identifiable string for the user.NoAppears in Databricks Audit Logs.external_valueA dynamic value passed into the SQL query.YesUsed for row-level security/filtering.Using External Values in SQLIn your Databricks dataset, you can reference the external_value using the following syntax:SQLSELECT * FROM sales_data 
WHERE region = :__aibi_external_value
📋 PrerequisitesPermissions: CAN MANAGE permissions on a published dashboard.Databricks CLI: Version 0.205 or higher.Whitelisting: A workspace admin must add your application’s domain to the Approved Domains list in Databricks Settings.Identity: A Service Principal created in your Databricks workspace.🚀 Setup StepsStep 1: Create a Service PrincipalNavigate to Settings > Identity and access > Service principals.Click Add service principal > Add new.Record the Application Id.Step 2: Generate OAuth SecretOn the Service Principal details page, click the Secrets tab.Click Generate secret.Warning: Copy this secret immediately; it will not be shown again.Step 3: Assign Dashboard PermissionsOpen your published dashboard and click Share.Add your Service Principal and assign the CAN RUN permission level.Copy the Dashboard ID from the URL (the string following /dashboards/).🐍 Example Implementation (Python)Save this as app.py. Ensure you have the environment variables set before running.Python#!/usr/bin/env python3
import os
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

auth_payload = f"{CONFIG['service_principal_id']}:{CONFIG['service_principal_secret']}"
basic_auth = base64.b64encode(auth_payload.encode()).decode()

def get_scoped_token():
    # 1. Get broad all-apis token
    oidc_res = http_post(
        f"{CONFIG['instance_url']}/oidc/v1/token",
        headers={"Authorization": f"Basic {basic_auth}"},
        body={"grant_type": "client_credentials", "scope": "all-apis"}
    )
    oidc_token = oidc_res["access_token"]

    # 2. Get user context (Token Info)
    token_info_url = (
        f"{CONFIG['instance_url']}/api/2.0/lakeview/dashboards/"
        f"{CONFIG['dashboard_id']}/published/tokeninfo"
        f"?external_viewer_id={urllib.parse.quote(CONFIG['external_viewer_id'])}"
        f"&external_value={urllib.parse.quote(CONFIG['external_value'])}"
    )
    token_info = http_get(token_info_url, headers={"Authorization": f"Bearer {oidc_token}"})

    # 3. Generate the user-scoped token
    params = token_info.copy()
    auth_details = params.pop("authorization_details", None)
    params.update({
        "grant_type": "client_credentials",
        "authorization_details": json.dumps(auth_details)
    })

    scoped_res = http_post(
        f"{CONFIG['instance_url']}/oidc/v1/token",
        headers={"Authorization": f"Basic {basic_auth}"},
        body=params
    )
    return scoped_res["access_token"]

# (Helper functions for HTTP GET/POST omitted for brevity, similar to your source)
⚠️ Limitations & ConsiderationsRate Limits: External embedding is limited to 20 dashboard loads per second.Ask Genie: The natural language "Ask Genie" button is not supported for external embedding. To provide natural language querying to external users, use the Genie Conversation API.PII Security: Ensure external_viewer_id never contains personally identifiable information, as it is stored in system logs.
