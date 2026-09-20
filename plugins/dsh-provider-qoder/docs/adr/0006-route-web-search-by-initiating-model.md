# Route web search by initiating agent model

We implement Qoder web search as an initiator-aware search provider within `dsh-provider-qoder`. By default (`webSearchMode: 'auto'`), search queries inspect `ctx.agents.currentInitiator()`: turns using a Qoder model (`qoder-official`) execute against the Qoder center service's `oneSearch` route authorized by the subscriber's COSY credentials; turns using non-Qoder models delegate to the ambient search provider.

A dedicated `webSearchMode` setting allows users to choose between `'auto'` (model-aware delegation), `'always'` (route all searches through Qoder), and `'disabled'` (opt out of search registration). Requests automatically refresh credentials and retry once on HTTP 401/403 status codes.

This avoids DSH's `WEB_PROVIDER_AMBIGUOUS` registry conflict while preserving a seamless user experience across model switches.
