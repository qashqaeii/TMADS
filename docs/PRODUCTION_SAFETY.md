# Production safety

The existing compose file is development-only and publishes ports to loopback.
The production settings module fails closed for missing or unsafe configuration.
Use an explicit production settings module, a unique long random SECRET_KEY, a
non-wildcard ALLOWED_HOSTS list, PostgreSQL, real configured payment credentials,
PAYMENT_FAKE_ENABLED=false and ZARINPAL_SANDBOX=false. Keep Telegram write and paid
submission flags false until the operator authorization and launch gates are met.
Never place credentials in the build context or image.

Deploy behind a trusted HTTPS reverse proxy that overwrites
X-Forwarded-Proto and does not permit direct untrusted access to the upstream.
Provide private media storage, persistent volumes, backups and monitored workers.
This change does not deploy anything or certify production readiness. Live
payments and Telegram writes are not part of automated verification.
