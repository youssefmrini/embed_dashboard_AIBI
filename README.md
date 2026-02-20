## Embed Databricks AI/BI Dashboard for External Users

This example shows how to securely embed a Databricks AI/BI dashboard into an external web application using a service principal and user‑scoped tokens. It follows the Databricks “embedding for external users” flow and uses the `@databricks/aibi-client` library in the frontend.

### How it works

1. **User authentication and request**  
   The user signs in to your application, and the frontend sends an authenticated request to your backend asking for a dashboard access token.

2. **Service principal authentication**  
   Your server authenticates to Databricks using a service principal (client ID and secret) and requests an OAuth token scoped to `all-apis` from the Databricks OIDC endpoint.

3. **Token info request**  
   Using the broad OAuth token, your server calls the `tokeninfo` endpoint for the published dashboard, passing `external_viewer_id` and `external_value` for the current user.

4. **User‑scoped token generation**  
   Your server uses the response from `tokeninfo` together with the OIDC token endpoint to generate a tightly scoped user token that encodes the viewer’s identity and filtering context.

5. **Dashboard rendering and data filtering**  
   The frontend instantiates `DatabricksDashboard` from `@databricks/aibi-client`, passing the user‑scoped token so the dashboard renders in the user’s context. Queries can reference `__aibi_external_value` in SQL to enforce per‑user row‑level filters, for example:

```sql
SELECT *
FROM sales
WHERE region = __aibi_external_value
