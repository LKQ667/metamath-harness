# Support Global and China service regions via settings configuration

We support both Global (`qoder.com`) and China (`qoder.com.cn`) Qoder services via a single `region` setting in the `provider-qoder` settings namespace, rather than requiring users to manually input arbitrary endpoint URLs or maintaining separate provider plugins.

While both regions share the same underlying COSY authentication algorithm and request payload formats, they operate on separate network endpoints:
- Global: `https://api3.qoder.sh/` (Algo) and `https://openapi.qoder.sh` (OpenAPI)
- China: `https://gateway.qoder.com.cn/` (Algo) and `https://openapi.qoder.com.cn` (OpenAPI)

Storing `region` in DSH Settings preserves the single managed PAT credential while allowing users to switch regions, invalidate short-lived in-memory job tokens, and dynamically discover the model catalog associated with their subscription region.

