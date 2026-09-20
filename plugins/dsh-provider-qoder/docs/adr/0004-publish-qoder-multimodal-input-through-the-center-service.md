# Publish Qoder multimodal input through the center service

Qoder transport publishes request images to the region's Qoder center service and places the returned object URLs in model requests. Publication remains an internal preparation step within the transport boundary defined by [ADR-0003](0003-centralize-qoder-upstream-access-in-qoder-transport.md), rather than a separate DSH upload capability.

Static validation of message shapes, advertised image support, and reasoning effort runs before credential resolution or provider I/O. Image publication requires signed credentials, so attachment reading, publication, and wire-message assembly follow authentication. This separates checks that need no I/O from preparation that does; it does not imply that every attachment error can be detected before authentication.

Publication results are held in a bounded, expiring cache, scoped by endpoint, subscriber, media type, and attachment request-variant identity. Concurrent callers share an in-flight publication with last-waiter cancellation. Cached URLs are reused while valid; expiry or eviction permits publication again. A finite lifetime avoids indefinitely replaying URLs whose upstream lifetime is unknown.

Publication failures fall back to inline image data and are logged as warnings, so an unavailable center service does not by itself abort model generation. Authorization rejection may retry once after credential refresh; other publication failures fall back without retrying. Caller cancellation still aborts the request. Model-generation retries remain DSH's responsibility.
