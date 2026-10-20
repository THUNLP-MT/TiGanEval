INC-6108 · Checkout sessions bouncing between pods · assigned to you by Idris Sarr, ingress platform

Support closed eleven abandoned-cart tickets before lunch, every one the same shopper hitting a different pod mid-checkout. It started the afternoon checkout went from two pods to six.

Joana tried a fix on the drill box last night: lay `config/policies/checkout-affinity.json` over the fleet policy key by key, route wins. The counts through her push looked no better to me, and `edge/compile.py` still only takes the header lines out of a policy.

Please make the same shopper land on the same pod through a checkout. I can watch the pod counts and I will tell you what I see.
