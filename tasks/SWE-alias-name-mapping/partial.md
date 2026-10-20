Handing this one to you; I am on the Dorado onboarding all week. I need you to make one field able to accept more than one incoming key.

Two partners post `userId`, and one of them `orderTs`, where the loader only looks under the key it publishes that field as. We keep a configuration per partner to cope, and last Tuesday's cutover cost finance a day of re-posting. `MappingConfig` already carries `aliases` and `alias_style`; nothing in `intake/mapper.py` reads either. My plan: when the loader looks a field up, try the mapped key first, then the listed spellings in order, and take the first one present.

Every post from those two has bounced as a missing field since March.

Hanne
