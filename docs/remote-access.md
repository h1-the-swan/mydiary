# Remote access (Tailscale)

The app is reachable off-host only over a private Tailscale tailnet, never
publicly. Serve proxies `https://mydiary.<tailnet>.ts.net` →
`proxy-vue:80`. The design and its tradeoffs are Part B of
`notes/auth-security-monitoring-plan-tailscale.md`.

| File | Purpose |
|------|---------|
| `tailscale/serve.json` | Serve config. `AllowFunnel: false`, so it can never go public. Mounted as a directory — tailscaled only picks up changes when the parent dir is bind-mounted. |
| `tailscale/policy.hujson` | Reference copy of the tailnet ACL. The source of truth is the admin console → Access Controls; editing this file changes nothing until it is pasted there. |

- The node is tagged `tag:mydiary`, so the ACL can scope it to port 443 alone,
  and its node key never expires (tagged nodes don't) — deliberate for an
  unattended server.
- Port 8086 is published on all host interfaces, and the WSL host is its own
  tailnet node, so `http://<host-node>.<tailnet>.ts.net:8086` also reaches the
  app — over plain HTTP, outside the 443-only scoping. Known and accepted;
  tailnet traffic is WireGuard-encrypted regardless.
- **A missing cert makes the first request hang.** With no cert cached, Serve
  fetches one from Let's Encrypt (DNS-01) inside the first TLS handshake, which
  takes ~30s. A browser timeout or `SSL_ERROR_INTERNAL_ERROR_ALERT` means that
  fetch failed; `docker compose logs tailscale` has the ACME error. Don't keep
  reloading — every failure counts toward Let's Encrypt's limit of 5 failed
  validations per hour, and Serve already retries in the background. Renewal
  (~every 60 days) is automatic.
- Don't wipe the `tailscale_state` volume casually: it holds the node identity,
  so wiping it registers a new node and forces a fresh cert.
