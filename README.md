Embed Dashboard AIBI
This repository contains a web application that embeds a Databricks AI/BI dashboard into a custom user interface for internal users or external customers.

Table of Contents
Overview

Features

Architecture

Prerequisites

Configuration

Getting Started

Usage

Security

Development

Troubleshooting

License

Overview
Enbed Dashboard AIBI provides a simple way to integrate Databricks AI/BI dashboards into your own web applications, portals, or customer-facing products.

Features
Embedded Databricks AI/BI dashboard inside a standard web page.

Token‑based authentication (PAT or OAuth) for secure access.

Environment‑based configuration for different workspaces and dashboards.

Ready to deploy to any static or Node.js‑based hosting environment.

Architecture
Frontend: <React/Vue/Plain HTML – describe your stack>

Backend (optional): <Node/Java/Spring/etc. if applicable>

Analytics: Databricks AI/BI dashboard rendered through the Databricks embedding API or client SDK.

Include a simple diagram image here if you have one.

Prerequisites
Databricks workspace with AI/BI dashboards enabled.

A published AI/BI dashboard and its dashboard ID.

A SQL Warehouse or Lakehouse connection configured for that dashboard.

Node.js and npm (or your chosen runtime) installed locally.

Configuration
Create a .env or similar configuration file in the project root:

bash
DATABRICKS_INSTANCE_URL="https://<your-instance>.cloud.databricks.com"
DATABRICKS_WORKSPACE_ID="<workspace-id>"
DATABRICKS_DASHBOARD_ID="<dashboard-id>"
DATABRICKS_TOKEN="<access-or-oauth-token>"
If you are using a frontend build tool (like Vite/Next.js), adapt the variable names (for example, prefix with VITE_, NEXT_PUBLIC_, etc.).

Getting Started
Clone the repository:

bash
git clone https://github.com/<your-org>/<your-repo>.git
cd <your-repo>
Install dependencies:

bash
npm install
Configure environment variables as described in Configuration.

Start the development server:

bash
npm run dev
Open the local URL shown in your terminal (for example, http://localhost:5173).

Usage
Embed the AI/BI dashboard in your app code (example for a simple HTML/JS setup):

xml
<div id="dashboard-content"></div>

<script type="module">
  import { DatabricksDashboard } from "@databricks/aibi-client";

  const dashboard = new DatabricksDashboard({
    instanceUrl: import.meta.env.VITE_DATABRICKS_INSTANCE_URL,
    workspaceId: import.meta.env.VITE_DATABRICKS_WORKSPACE_ID,
    dashboardId: import.meta.env.VITE_DATABRICKS_DASHBOARD_ID,
    token: import.meta.env.VITE_DATABRICKS_TOKEN,
    container: document.getElementById("dashboard-content"),
  });

  dashboard.initialize();
</script>
Adapt this example to your framework (React component, Next.js page, etc.) as needed.

Security
Do not hard‑code long‑lived tokens in frontend code or in the repository.

Generate short‑lived tokens on the backend and inject them into the page at runtime.

Restrict access to the dashboard using Databricks workspace permissions.

Rotate credentials regularly and use a secret manager in production.

Development
Common scripts (adapt names to your package.json):

npm run dev – start the development server.

npm run build – create a production build.

npm run preview – preview the production build locally.

npm test – run tests (if configured).

Troubleshooting
The dashboard does not load:

Check that DATABRICKS_INSTANCE_URL, WORKSPACE_ID, and DASHBOARD_ID are correct.

Verify that the token is valid and has permission to view the dashboard.

CORS or iframe errors:

Confirm that embedding is allowed in your Databricks workspace settings.

Ensure you are using HTTPS in production.
