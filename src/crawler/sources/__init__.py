"""Source extractors: one module per site.

Importing this package triggers registration of every installed source via the
side-effecting `register_source(...)` call at the bottom of each module.
"""

from crawler.sources import artmap  # noqa: F401 — import for side effect (registration)
