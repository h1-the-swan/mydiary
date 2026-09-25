# Remote access is tailnet-only

The diary is reachable off-host only over a private Tailscale tailnet, through
Tailscale Serve, with Funnel disabled (`AllowFunnel: false`). It has no public
hostname. We chose this over a public endpoint behind Cloudflare Tunnel and
Access because the app has no login of its own. Behind a public hostname, the
edge would be the only thing between the internet and the whole diary, and
Cloudflare would terminate TLS and see its contents in plaintext. On a tailnet,
nothing is internet-reachable, traffic is WireGuard-encrypted device to device,
and the app's own gaps (no app-level auth, `debug=True`, open CORS, the Vite dev
server) drop from critical to defense-in-depth concerns.

Setup and operational gotchas: [remote-access.md](../remote-access.md).

## Considered options

- **Cloudflare Tunnel + Cloudflare Access.** Gives browser access from any
  device, plus WAF/DDoS protection and automatic TLS on a custom domain. But
  the hostname is public (and shows up in Certificate Transparency logs), its
  safety rests entirely on Access being configured correctly, and Cloudflare is
  in the plaintext path. Worth reconsidering only if access from devices that
  can't run Tailscale, or public sharing, becomes a hard requirement.
- **Tailscale Funnel.** Re-exposes the service publicly, which brings back the
  Cloudflare threat model. Deliberately disabled.
- **Tailscale Services.** Host-independent identity and HA across several
  backing hosts, at the cost of tags, approvals and service definitions. None
  of that applies to one host and one user. Revisit if the diary ever runs on
  two or more hosts.
- **Subnet router, app connectors.** A subnet router exposes a whole LAN; app
  connectors are for egress to SaaS apps. Neither fits ingress to one
  self-hosted service.

## Consequences

- Every client device has to run Tailscale and be logged in. There's no access
  from a borrowed browser.
- Programmatic clients on the phone (the iOS Shortcut) reach the API over the
  tailnet too, so MagicDNS and Tailscale's HTTPS certs are load-bearing:
  Shortcuts refuses self-signed certs.
- App-level login and audit logging are still wanted, but as a second layer.
  Until they exist, individual routes that need authentication use a per-route
  API-token check (see [env-vars.md](../env-vars.md)).
