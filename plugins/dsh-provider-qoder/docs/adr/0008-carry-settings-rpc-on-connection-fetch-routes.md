# Carry the settings RPC on Connection exact Fetch routes

Qoder settings RPC uses Connection exact Fetch routes on the shared `/api` channel. The previous dedicated-channel registration depended on Connection's internal `webServer` injection scope and failed in `dsh-client-connection` 0.1.5-rc.2. Moving to the Fetch registry avoids that dependency without changing the upstream Connection implementation.

The account and model endpoints are `POST /api/qoder-subscription/account` and `POST /api/qoder-subscription/models`, registered through `connection.fetch.register()`. The browser calls them with `fetch`, using buffered JSON requests and standard `ConnectionRpcResult` envelopes: `{ ok: true, value }` or `{ ok: false, error: { code, message } }`. Structured error codes drive client state, while transport failures retain HTTP status diagnostics.

Connection owns the shared channel's browser authentication, Host/Origin checks, and request body limit. The plugin relies on those protections rather than mounting an independent HTTP surface. The browser-side plugin does not require the Connection client service, and host-side route registration does not require direct `webServer` access.

Settings RPC is optional to model generation and web search. Route-registration failures are caught and logged so a settings integration failure does not prevent those capabilities from loading. This avoids the dedicated-channel registration defect; it does not claim to fix that defect upstream or guarantee compatibility with future Connection versions.
