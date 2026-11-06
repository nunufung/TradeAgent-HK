---
title: TradeAgent HK FCC Gateway
emoji: 🔐
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

Authenticated research gateway for TradeAgent-HK. Only health, model listing,
Messages and token counting are exposed. FCC and its administration routes bind
only to loopback and are not forwarded. No public browser key entry is provided.

Required runtime secrets: FCC_API_KEY (32+ characters), DEEPSEEK_API_KEY.
FCC_ALLOWED_MODELS defaults to deepseek/deepseek-chat. Additional models require
corresponding provider keys. No free Claude entitlement is included.

FCC v6.18.11 is installed from immutable upstream commit
65d9f29788392d6e9948bfdee6519a44b1ceaad3 under AGPL-3.0-only.
Upstream source and license: https://github.com/Alishahryar1/free-claude-code/tree/65d9f29788392d6e9948bfdee6519a44b1ceaad3
This independently authored edge does not modify FCC source.
