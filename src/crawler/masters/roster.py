"""Curated roster of public-domain photography masters.

Foreign 19th–early-20th-c masters form the backbone (verified PD coverage at
the Art Institute of Chicago). Japan and Korea ride on Wikimedia Commons: the
Met flags most photography images as not-open-access, so Commons is the only
free source with real coverage there. Korean photographers of the modern era
(임응식 등) are still in copyright (death + 70y), so the Korea section is
honest about what IS public domain: foreign masters who documented Joseon,
plus a hand-picked open-era (개화기) archive. A master with zero usable PD
works is dropped at build time."""

from __future__ import annotations

from crawler.masters.models import MasterSeed, SourceQuery

ROSTER: list[MasterSeed] = [
    # ── Korea ────────────────────────────────────────────────────────────
    MasterSeed(
        id="percival-lowell", name="Percival Lowell", region="kr", nationality="US",
        birth_year=1855, death_year=1916, portrait_url=None,
        # 1883–84 조선 방문, 『Chosön: The Land of the Morning Calm』 — Commons 19 PD
        sources=[SourceQuery(source="wikimedia", query="Percival Lowell Korea",
                             artist="Lowell")],
    ),
    MasterSeed(
        id="joseon-photo-archive", name="개화기 조선 사진 아카이브", region="kr",
        nationality="KR", birth_year=None, death_year=None, portrait_url=None,
        # Hand-picked PD glass-plate/print era views of Joseon and the Korean
        # Empire (verified PD + resolution on Commons, 2026-06).
        sources=[SourceQuery(source="wikimedia", object_ids=[
            "File:광화문 앞 (1900s).jpg",
            "File:숭례문 (1900s).jpg",
            "File:평양칠성문 (1900s).jpg",
            "File:Korea-Portrait of Emperor Gojong-01.jpg",
            "File:Seoul-in-korean-empire-1900s-vintage-everyday-life.jpg",
            "File:Sungnyemun1904.jpg",
            "File:Korea-History-1910-1920-Korean.mother.child-Carpenter.Collection.jpg",
            "File:Pyeng-yang, looking down the Ta-dong River from the wall.jpg",
            "File:Courant - Souvenir de Séoul, Corée-10.jpg",
            "File:WestGate of Seoul 1900s.jpg",
        ])],
    ),
    # ── Japan ────────────────────────────────────────────────────────────
    MasterSeed(
        id="felice-beato", name="Felice Beato", region="jp", nationality="IT",
        birth_year=1832, death_year=1909, portrait_url=None,
        # 1871 신미양요(Korea) 종군 사진 2점을 명시적으로 앞세우고, 나머지는
        # Commons/Met/AIC 검색으로 채운다.
        sources=[SourceQuery(source="wikimedia", object_ids=[
                     "File:First known photo of Koreans 1871.jpg",
                     "File:1871sujagi.jpg",
                 ]),
                 SourceQuery(source="wikimedia", query="Felice Beato", artist="Beato"),
                 SourceQuery(source="the_met", query="Felice Beato"),
                 SourceQuery(source="aic", query="Felice Beato")],
    ),
    MasterSeed(
        id="kusakabe-kimbei", name="Kusakabe Kimbei (日下部金兵衛)", region="jp",
        nationality="JP", birth_year=1841, death_year=1934, portrait_url=None,
        sources=[SourceQuery(source="wikimedia", query="Kusakabe Kimbei",
                             artist="Kimbei")],  # Commons 40 PD
    ),
    MasterSeed(
        id="ogawa-kazumasa", name="Ogawa Kazumasa (小川一眞)", region="jp",
        nationality="JP", birth_year=1860, death_year=1929, portrait_url=None,
        sources=[SourceQuery(source="wikimedia", query="Ogawa Kazumasa",
                             artist="Ogawa")],  # Commons 25 PD
    ),
    MasterSeed(
        id="uchida-kuichi", name="Uchida Kuichi (内田九一)", region="jp",
        nationality="JP", birth_year=1844, death_year=1875, portrait_url=None,
        sources=[SourceQuery(source="wikimedia", query="Uchida Kuichi",
                             artist="Uchida")],  # Commons 34 PD
    ),
    MasterSeed(
        id="ueno-hikoma", name="Ueno Hikoma (上野彦馬)", region="jp",
        nationality="JP", birth_year=1838, death_year=1904, portrait_url=None,
        sources=[SourceQuery(source="wikimedia", query="Ueno Hikoma",
                             artist="Ueno")],  # Commons 33 PD
    ),
    MasterSeed(
        id="tamamura-kozaburo", name="Tamamura Kōzaburō (玉村康三郎)", region="jp",
        nationality="JP", birth_year=1856, death_year=1923, portrait_url=None,
        sources=[SourceQuery(source="wikimedia", query="Tamamura Kozaburo",
                             artist="Tamamura")],  # Commons 16 PD
    ),
    MasterSeed(
        id="shimooka-renjo", name="Shimooka Renjō (下岡蓮杖)", region="jp",
        nationality="JP", birth_year=1823, death_year=1914, portrait_url=None,
        sources=[SourceQuery(source="wikimedia", query="Shimooka Renjo",
                             artist="Shimooka")],  # Commons 8 PD
    ),
    # ── International ────────────────────────────────────────────────────
    MasterSeed(
        id="julia-margaret-cameron", name="Julia Margaret Cameron", region="foreign",
        nationality="GB", birth_year=1815, death_year=1879, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Julia Margaret Cameron")],  # AIC 39
    ),
    MasterSeed(
        id="alfred-stieglitz", name="Alfred Stieglitz", region="foreign", nationality="US",
        birth_year=1864, death_year=1946, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Alfred Stieglitz"),  # AIC 10+
                 SourceQuery(source="wikimedia", query="Alfred Stieglitz photograph",
                             artist="Stieglitz")],
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
        sources=[SourceQuery(source="aic", query="Roger Fenton"),  # AIC thin (3)
                 SourceQuery(source="wikimedia", query="Roger Fenton photograph",
                             artist="Fenton")],
    ),
    MasterSeed(
        id="william-henry-fox-talbot", name="William Henry Fox Talbot", region="foreign",
        nationality="GB", birth_year=1800, death_year=1877, portrait_url=None,
        sources=[SourceQuery(source="aic", query="William Henry Fox Talbot")],  # AIC 40
    ),
    MasterSeed(
        id="charles-marville", name="Charles Marville", region="foreign", nationality="FR",
        birth_year=1813, death_year=1879, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Charles Marville"),  # AIC thin (2)
                 SourceQuery(source="wikimedia", query="Charles Marville Paris",
                             artist="Marville")],
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
    MasterSeed(
        id="timothy-osullivan", name="Timothy H. O'Sullivan", region="foreign",
        nationality="US", birth_year=1840, death_year=1882, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Timothy O'Sullivan")],  # AIC 60
    ),
    MasterSeed(
        id="alexander-gardner", name="Alexander Gardner", region="foreign",
        nationality="US", birth_year=1821, death_year=1882, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Alexander Gardner")],  # AIC 22
    ),
    MasterSeed(
        id="david-octavius-hill", name="David Octavius Hill", region="foreign",
        nationality="GB", birth_year=1802, death_year=1870, portrait_url=None,
        sources=[SourceQuery(source="aic", query="David Octavius Hill")],  # AIC 30
    ),
    MasterSeed(
        id="john-thomson", name="John Thomson", region="foreign", nationality="GB",
        birth_year=1837, death_year=1921, portrait_url=None,
        sources=[SourceQuery(source="aic", query="John Thomson")],  # AIC 59 (아시아 기록)
    ),
    MasterSeed(
        id="francis-frith", name="Francis Frith", region="foreign", nationality="GB",
        birth_year=1822, death_year=1898, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Francis Frith")],  # AIC 60
    ),
    MasterSeed(
        id="frederick-h-evans", name="Frederick H. Evans", region="foreign",
        nationality="GB", birth_year=1853, death_year=1943, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Frederick H. Evans")],  # AIC 28
    ),
    MasterSeed(
        id="hippolyte-bayard", name="Hippolyte Bayard", region="foreign",
        nationality="FR", birth_year=1801, death_year=1887, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Hippolyte Bayard")],  # AIC 26
    ),
    MasterSeed(
        id="etienne-carjat", name="Étienne Carjat", region="foreign", nationality="FR",
        birth_year=1828, death_year=1906, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Étienne Carjat")],  # AIC 36
    ),
    MasterSeed(
        id="lewis-hine", name="Lewis Hine", region="foreign", nationality="US",
        birth_year=1874, death_year=1940, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Lewis Hine")],  # AIC 60
    ),
    MasterSeed(
        id="gertrude-kasebier", name="Gertrude Käsebier", region="foreign",
        nationality="US", birth_year=1852, death_year=1934, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Gertrude Käsebier"),  # AIC 5
                 SourceQuery(source="wikimedia", query="Gertrude Käsebier",
                             artist="Käsebier")],
    ),
]
