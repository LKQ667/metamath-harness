# DSH Qoder Subscription

This context describes how a Qoder subscription is made available to users through DSH.

## Language

**Qoder provider identity**:
The identity by which DSH selects this third-party integration with a Qoder subscription; it does not imply that Qoder publishes or endorses the plugin.
_Avoid_: official Qoder plugin identity

**Legacy Qoder provider alias**:
A previously published Qoder provider identity accepted for compatibility with existing model selections and callers, without being offered for new selections.
_Avoid_: second Qoder provider, official provider

**Qoder subscription**:
A user's existing Qoder entitlement that permits access to Qoder-hosted language models.
_Avoid_: Qoder API key, generic model subscription

**Qoder personal access token (PAT)**:
A revocable credential representing a Qoder user and carrying permissions selected when the token is created.
_Avoid_: job token, API response token

**Managed Qoder PAT**:
The single Qoder PAT stored for a DSH instance through its managed credential store.
_Avoid_: environment PAT, plugin API key

**Qoder job token**:
A short-lived credential obtained by exchanging a Qoder PAT and used to authorize Qoder model transport requests.
_Avoid_: Qoder PAT, refresh token

**Qoder model key**:
The provider-facing identifier of a Qoder model selected for a request.
_Avoid_: display name, DSH provider route

**Qoder context tier**:
A provider-advertised input-context capacity option for a Qoder model. The provider's default tier and the largest available tier may differ.
_Avoid_: output token limit, maximum context as default

**Qoder transport**:
The provider-side capability that owns all communication with Qoder: authenticating a subscriber, discovering models, reading subscriber profile and quota, translating model requests, and returning model stream events. It does not own agent tools or workspace operations.
_Avoid_: generic HTTP client, Qoder agent, Qoder Agent SDK

**Qoder multimodal input**:
Text and durable raster-image content accepted together by a Qoder vision-language model; it does not include arbitrary binary files such as PDFs, audio, video, or archives.
_Avoid_: Qoder image upload, arbitrary file upload

**Qoder image publication**:
The exchange that places one request image on the Qoder center service and yields the durable object URL a model request carries in place of inline bytes. It is per subscriber and per Qoder service region, and it degrades to inline content rather than failing the model turn.
_Avoid_: Qoder image upload, attachment sync, CDN push

**Qoder center service**:
The region-scoped Qoder service that owns durable image objects, distinct from the model transport and Open API hosts.
_Avoid_: OSS bucket, image CDN, upload gateway

**Qoder tool exchange**:
The provider-level representation of DSH tool definitions, model-requested tool calls, and correlated tool results transported across Qoder model turns. DSH remains responsible for executing tools.
_Avoid_: Qoder tool execution, Qoder agent loop

**Qoder reasoning content**:
Model-produced reasoning carried separately from user-visible response text, whether Qoder emits it through a dedicated field or embedded thinking tags.
_Avoid_: visible answer, tool output, chain-of-thought configuration

**Qoder reasoning effort**:
An optional, model-specific reasoning level explicitly advertised by Qoder and selected for a conversation. Its identifiers are provider-owned; absence means Qoder chooses its default behavior.
_Avoid_: synthetic off switch, token budget, global reasoning level

**Quick validation release**:
The first public release whose purpose is to prove that DSH can use a Qoder subscription for streaming text, reasoning, and tool-driven model turns.
_Avoid_: MVP, feature-complete release

**Public release**:
A distributable plugin release intended for installation by Qoder subscribers beyond the maintainers' own machines.
_Avoid_: local prototype, internal build

**Qoder subscriber profile**:
The verified identity details (user ID, display name, and email) associated with the authenticated Qoder subscription.
_Avoid_: account credential, user token

**Qoder quota usage**:
The point-in-time metrics of a Qoder subscriber's model consumption, remaining allowance, and reset horizon provided by the Qoder service.
_Avoid_: billing balance, token count

**Qoder dedicated resource package**:
An entitlement-scoped allowance carved out of a Qoder subscription that is drawn down ahead of the shared personal quota, such as SOTA credits that only apply to one model series. Each package carries its own size, consumption, expiry, and subscriber-facing copy localized by the provider, and it is reported independently of the organization resource package.
_Avoid_: add-on credits, top-up balance, organization resource pack

**Qoder service region**:
The target service environment (`global` or `china`) of the Qoder platform selected in settings. A Qoder model catalog belongs to exactly one service region and must not be merged with another region's catalog.
_Avoid_: endpoint mode, cluster, server flavor

**Global Qoder service**:
The Qoder service associated with `qoder.com` accounts and international endpoints.
_Avoid_: international endpoint, global cluster

**China Qoder service**:
The Qoder service associated with `qoder.com.cn` accounts and mainland China endpoints.
_Avoid_: domestic service, CN endpoint

**Qoder subscriber plan**:
The subscription tier, term validity, and organization entitlement associated with the authenticated Qoder account.
_Avoid_: subscription level, billing plan

**Qoder subscriber status**:
The operational account standing, security fingerprint linkage, and client feature switches evaluated by Qoder.
_Avoid_: account state, auth flags

**Qoder reasoning preservation**:
The provider-level mechanism that retains prior assistant reasoning content and carries it in the wire message `reasoning_content` across multi-turn exchanges.
_Avoid_: thinking cache, scratchpad replay

**Qoder web search**:
The provider-side web discovery capability that executes queries against the Qoder center service's search route authorized by the subscriber's COSY credentials.
_Avoid_: external search, Google search, crawler

**Qoder search route**:
The center-hosted API path (`/api/v1/webSearch/oneSearch`) that accepts query parameters and emits structured search results across service regions.
_Avoid_: unifiedSearch, search proxy

**Initiator-aware search routing**:
The provider-level mechanism that inspects the initiating agent's active model provider and routes queries to Qoder when a Qoder model is active, delegating to an ambient search provider otherwise.
_Avoid_: static search provider, fixed search binding

**Qoder settings RPC**:
The loopback exchange that answers the Qoder cards' model-catalog and subscriber-account reads from the host, carried as Connection exact Fetch routes on the shared `/api` channel using standard `ConnectionRpcResult` envelopes (`{ ok: true, value }` or `{ ok: false, error: { code, message } }`), rather than as a dedicated RPC channel or an ad-hoc REST endpoint.
_Avoid_: remote API client, quota webhook, HTTP proxy

**Qoder settings RPC error code**:
A standardized diagnostic identifier (`NO_CREDENTIALS`, `UNAUTHENTICATED`, `UPSTREAM_ERROR`, `TIMEOUT`, `ABORTED`, `UNKNOWN_ENDPOINT`, or `INTERNAL`) carried in a settings RPC failure envelope to drive UI state without inspecting free-form message strings.
_Avoid_: HTTP status mapping, ad-hoc string matching
