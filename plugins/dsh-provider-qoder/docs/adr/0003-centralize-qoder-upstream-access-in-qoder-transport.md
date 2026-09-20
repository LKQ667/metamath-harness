# Centralize Qoder upstream access in Qoder transport

All Qoder upstream communication belongs to Qoder transport, exposed through provider capabilities rather than a generic HTTP client. DSH owns registration, configuration, credential storage, and model-generation retries; the transport owns authentication and Qoder protocol behavior. This keeps provider details behind one boundary without duplicating DSH's agent responsibilities.

Each transport instance binds one immutable Qoder service region. Model catalogs are configured and persisted separately by region; switching region replaces the active instance while allowing already-started requests to finish. Shared reads use last-waiter cancellation, and internal metadata retries are limited to idempotent reads.

The original capabilities were model streaming, model discovery, and account reading. [ADR-0004](0004-publish-qoder-multimodal-input-through-the-center-service.md) adds image publication inside model-request preparation, and [ADR-0006](0006-route-web-search-by-initiating-model.md) adds web search. Both preserve the same ownership boundary; authentication refresh and retry behavior for those operations are defined separately from model-generation retries.

Connection pools, background refresh, circuit breakers, dynamic rate limiting, and full tracing remain outside scope until demonstrated needs justify them.
