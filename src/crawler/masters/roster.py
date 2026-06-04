"""Curated roster of public-domain photography masters (MVP).

Foreign 19th–early-20th-c masters form the backbone (verified PD coverage at the
Art Institute of Chicago); a few early Japan/Korea seeds are best-effort via the
Met. A master with zero usable PD works is dropped at build time."""

from __future__ import annotations

from crawler.masters.models import MasterSeed, SourceQuery

ROSTER: list[MasterSeed] = [
    MasterSeed(
        id="julia-margaret-cameron", name="Julia Margaret Cameron", region="foreign",
        nationality="GB", birth_year=1815, death_year=1879, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Julia Margaret Cameron")],  # AIC 39
    ),
    MasterSeed(
        id="alfred-stieglitz", name="Alfred Stieglitz", region="foreign", nationality="US",
        birth_year=1864, death_year=1946, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Alfred Stieglitz")],  # AIC 10+
    ),
    MasterSeed(
        id="eugene-atget", name="Eugène Atget", region="foreign", nationality="FR",
        birth_year=1857, death_year=1927, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Eugène Atget")],  # AIC: some PD
    ),
    MasterSeed(
        id="carleton-watkins", name="Carleton Watkins", region="foreign", nationality="US",
        birth_year=1829, death_year=1916, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Carleton Watkins")],  # AIC 35
    ),
    MasterSeed(
        id="gustave-le-gray", name="Gustave Le Gray", region="foreign", nationality="FR",
        birth_year=1820, death_year=1884, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Gustave Le Gray")],  # AIC 40
    ),
    MasterSeed(
        id="nadar", name="Nadar (Gaspard-Félix Tournachon)", region="foreign",
        nationality="FR", birth_year=1820, death_year=1910, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Nadar")],  # AIC 28
    ),
    MasterSeed(
        id="roger-fenton", name="Roger Fenton", region="foreign", nationality="GB",
        birth_year=1819, death_year=1869, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Roger Fenton")],  # AIC 40
    ),
    MasterSeed(
        id="william-henry-fox-talbot", name="William Henry Fox Talbot", region="foreign",
        nationality="GB", birth_year=1800, death_year=1877, portrait_url=None,
        sources=[SourceQuery(source="aic", query="William Henry Fox Talbot")],  # AIC 40
    ),
    MasterSeed(
        id="charles-marville", name="Charles Marville", region="foreign", nationality="FR",
        birth_year=1813, death_year=1879, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Charles Marville")],  # AIC 14
    ),
    MasterSeed(
        id="edward-curtis", name="Edward S. Curtis", region="foreign", nationality="US",
        birth_year=1868, death_year=1952, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Edward S. Curtis")],  # AIC 26
    ),
    MasterSeed(
        id="peter-henry-emerson", name="Peter Henry Emerson", region="foreign",
        nationality="GB", birth_year=1856, death_year=1936, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Peter Henry Emerson")],  # AIC 40
    ),
    MasterSeed(
        id="eadweard-muybridge", name="Eadweard Muybridge", region="foreign",
        nationality="GB", birth_year=1830, death_year=1904, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Eadweard Muybridge")],  # AIC 5
    ),
    # Japan/Korea seeds — early photography, best-effort via the Met (AIC CC0
    # coverage is thin). Dropped at build time if no usable PD works return.
    MasterSeed(
        id="felice-beato", name="Felice Beato", region="jp", nationality="IT",
        birth_year=1832, death_year=1909, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Felice Beato"),
                 SourceQuery(source="aic", query="Felice Beato")],
    ),
    MasterSeed(
        id="kusakabe-kimbei", name="Kusakabe Kimbei (日下部金兵衛)", region="jp",
        nationality="JP", birth_year=1841, death_year=1934, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Kusakabe Kimbei")],
    ),
    MasterSeed(
        id="early-korea-photography", name="조선 풍경 사진 (19c)", region="kr",
        nationality="KR", birth_year=None, death_year=None, portrait_url=None,
        sources=[SourceQuery(source="the_met", query="Korea")],
    ),
]
