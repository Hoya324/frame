"""Source extractors: one module per site.

Importing this package triggers registration of every installed source via the
side-effecting `register_source(...)` call at the bottom of each module.
"""

# Order doesn't matter; we just need each module to be imported.
from crawler.sources import (
    artmap,  # noqa: F401
    canon_gallery,  # noqa: F401
    gallery_kong,  # noqa: F401
    gallery_lux,  # noqa: F401
    goeun,  # noqa: F401
    ilwoo_space,  # noqa: F401
    koba,  # noqa: F401
    museum_hanmi,  # noqa: F401
    photo_sema,  # noqa: F401
    ryugaheon,  # noqa: F401
    sangsangmadang,  # noqa: F401
)

# BLOCKED in M3: Naver requires either OAuth (Open API) or JS rendering (Playwright).
# Deferred to v1.5. See docs/sources/naver.md for recon details.
# from crawler.sources import naver  # noqa: F401
