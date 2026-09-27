"""The test suite is offline, always.

`api` loads `.env` on import, which is what makes "paste a key and it runs online" work.
The same convenience would quietly make the suite non-deterministic on a developer's
machine — a recorded replay would be replaced by a live call, and the eval gates would
score a different answer than CI did. Pinning the mode here removes that class of
Heisenbug: tests that want a provider set it themselves, explicitly.
"""

import os

os.environ.setdefault("SAHAYAK_MODE", "offline")
