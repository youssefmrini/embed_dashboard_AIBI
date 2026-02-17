Embedded Databricks AI/BI Dashboard
This repository contains a small web app that embeds a Databricks AI/BI dashboard into a custom UI (e.g. internal portal or customer-facing app).

Features
Embeds a published Databricks AI/BI dashboard in a web page.

Uses OAuth access tokens or personal access tokens to authenticate.

Supports configuration via environment variables.

Prerequisites
You need:

A Databricks workspace with AI/BI Dashboards enabled.
​

A published AI/BI dashboard (copy its dashboard ID from the URL).
​

A SQL Warehouse or Lakehouse connection configured for the dashboard.
​

Node.js (if using the provided frontend dev server) or any static web host.

If you embed for external users, you also need a service principal and OAuth client credentials configured in Databricks.

Configuration
Create a .env file (or use your hosting platform’s env vars):

bash
DATABRICKS_INSTANCE_URL="https://<your-instance>.cloud.databricks.com"
DATABRICKS_WORKSPACE_ID="<workspace-id>"
DATABRICKS_DASHBOARD_ID="<dashboard-id>"
DATABRICKS_TOKEN="<access-or-oauth-token>"
For production and external users, generate short‑lived OAuth tokens in your backend and inject them into the page at runtime.

Running locally
If this repo uses a simple static frontend (e.g. Vite, React, or plain HTML):

bash
npm install
npm run dev
Then open the printed local URL in your browser.

Example embed code
In a simple HTML page:

xml
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>AI/BI Dashboard</title>
  </head>
  <body>
    <div id="dashboard-content"></div>

    <script type="module">
      import { DatabricksDashboard } from "https://cdn.jsdelivr.net/npm/@databricks/aibi-client@0.0.0-alpha.7/+esm";

      const dashboard = new DatabricksDashboard({
        instanceUrl: import.meta.env.VITE_DATABRICKS_INSTANCE_URL,
        workspaceId: import.meta.env.VITE_DATABRICKS_WORKSPACE_ID,
        dashboardId: import.meta.env.VITE_DATABRICKS_DASHBOARD_ID,
        token: import.meta.env.VITE_DATABRICKS_TOKEN,
        container: document.getElementById("dashboard-content"),
      });

      dashboard.initialize();
    </script>
  </body>
</html>
This uses the official @databricks/aibi-client package to render the dashboard into a DOM container.

Security notes
Always use short‑lived tokens generated on the server side; never hard‑code long‑lived tokens in frontend code.

Restrict dashboard access via Databricks permissions and workspace‑level “allowed surfaces for embedding”.

For customer‑specific views, pass row‑level filters via external parameters (for example, customer ID) signed in the token payload.
