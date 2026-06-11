"""Curated roster of public-domain photography masters.

Foreign 19th–early-20th-c masters form the backbone (verified PD coverage at
the Art Institute of Chicago). Japan and Korea ride on Wikimedia Commons: the
Met flags most photography images as not-open-access, so Commons is the only
free source with real coverage there. Korean photographers of the modern era
(임응식 등) are still in copyright (death + 70y), so the Korea section is
honest about what IS public domain: foreign masters who documented Joseon,
plus a hand-picked open-era (개화기) archive. The modern (20th-c) section
rides on U.S. government-commissioned work (FSA/OWI, NPS Mural Project) and
gifted-to-LOC archives, which are PD regardless of the photographer's death
year. A master with zero usable PD works is dropped at build time."""

from __future__ import annotations

from dataclasses import replace

from crawler.masters.models import MasterSeed, SourceQuery

# Work-ids the searches keep returning that are NOT works by the master —
# portraits of them, book covers, text scans, paintings, duplicate variants.
# Sourced from the 2026-06-11 image audit; applied to ROSTER below.
_EXCLUDED_WORK_IDS: dict[str, list[str]] = {
    "lewis-hine": [
        "wikimedia-170878494",  # verso of photo: NYPL catalog stamps and 
        "wikimedia-13284824",  # portrait OF elderly Hine, title just his
        "wikimedia-37213074",  # modern snapshot of Hine print at 2014 Ve
        "wikimedia-29715257",  # duplicate Powerhouse Mechanic file
    ],
    "frederick-h-evans": [
        "wikimedia-60418172",  # portrait OF Frederick Evans seated, sign
        "wikimedia-60418282",  # portrait OF Evans examining object, Kase
        "wikimedia-60416688",  # portrait OF Evans kneeling at print cabi
        "wikimedia-60416665",  # portrait OF Evans in velvet jacket, Kase
    ],
    "alexander-gardner": [
        "aic-27501",  # engraved decorative book title-page cove
    ],
    "arthur-rothstein": [
        "wikimedia-188464135",  # Rothstein himself operating view camera 
        "wikimedia-67129037",  # Rothstein in suit holding camera lens, s
        "wikimedia-107021338",  # Close head-and-shoulders portrait of Rot
        "wikimedia-67121456",  # Indoor portrait of Rothstein seated agai
        "wikimedia-2741201",  # Rothstein holding camera, black retouch 
        "wikimedia-67121376",  # Rothstein at tripod camera overlooking i
        "wikimedia-67127361",  # Rothstein in suit holding camera lens
    ],
    "dorothea-lange": [
        "wikimedia-53038",  # Lange sitting on car roof holding camera
        "wikimedia-3948901",  # Lange atop automobile with large camera
        "wikimedia-9968330",  # close portrait of Lange holding camera o
        "wikimedia-92311414",  # Lange seated on car roof with camera
        "wikimedia-86946563",  # duplicate variant
    ],
    "esther-bubley": [
        "wikimedia-97932378",  # duplicate variant
        "wikimedia-98205973",  # duplicate variant
    ],
    "etienne-carjat": [
        "aic-105473",  # Pencil drawing of Daumier in profile
    ],
    "francis-frith": [
        "aic-157944",  # open book spread with small mounted phot
    ],
    "gertrude-kasebier": [
        "wikimedia-57853278",  # near-duplicate
        "wikimedia-67391458",  # near-duplicate
        "wikimedia-68028110",  # near-duplicate
        "wikimedia-27338525",  # near-duplicate
        "wikimedia-80953125",  # Blessed Art Thou variant (AIC print kept
        "wikimedia-67604988",  # Blessed Art Thou variant
        "wikimedia-66214823",  # Blessed Art Thou variant
        "wikimedia-57253978",  # Portrait of Kasebier in plumed hat by de
        "wikimedia-5151754",  # Standing portrait of Kasebier in light c
        "wikimedia-100781892",  # Kasebier in hat holding portfolio, c.190
        "wikimedia-101353271",  # Kasebier in cape and hat, 1890s street p
        "wikimedia-101578996",  # Postcard photo of Kasebier holding small
        "wikimedia-101355656",  # Kasebier and de Meyer chatting at doorwa
        "wikimedia-101354266",  # Cabinet-card family group of four women
    ],
    "gordon-parks": [
        "wikimedia-165856229",  # near-duplicate
        "wikimedia-165828652",  # near-duplicate
        "wikimedia-165828566",  # near-duplicate Johnson sitting
        "wikimedia-5999774",  # portrait of Gordon Parks in crowd
        "wikimedia-85758000",  # portrait of Gordon Parks in crowd
        "wikimedia-16633380",  # Gordon Parks photographed at March on Wa
        "wikimedia-620001",  # close portrait of Gordon Parks
        "wikimedia-115649325",  # newsprint halftone portrait of Parks wit
        "wikimedia-166394524",  # duplicate variant
    ],
    "gustave-le-gray": [
        "aic-126478",  # framed color oil painting of waves on ro
    ],
    "hippolyte-bayard": [
        "wikimedia-29945646",  # near-duplicate
        "wikimedia-128860787",  # nearly blank faded wash, figure indistin
        "wikimedia-128860743",  # heavily degraded speckled blue wash, bar
        "wikimedia-128860847",  # near-duplicate
        "wikimedia-3464635",  # 1863 carte-de-visite studio portrait OF 
        "aic-23756",  # printed theater play text page (Suzette 
        "aic-23784",  # book half-title page 'LE R. P. D'ALZON'
    ],
    "jack-delano": [
        "wikimedia-33761718",  # head portrait of balding man in suit
        "wikimedia-2721689",  # formal studio portrait of man in pinstri
        "wikimedia-12748180",  # Delano holding camera in front of locomo
    ],
    "joseon-photo-archive": [
        "wikimedia-2901805",  # painted royal portrait of Gojong in red 
    ],
    "kusakabe-kimbei": [
        "wikimedia-10490073",  # printed text advertisement page for Kimb
        "wikimedia-53383059",  # photographic portrait of elderly Kusakab
        "wikimedia-33838096",  # printed text advertisement page for Kimb
    ],
    "nadar": [
        "aic-144578",  # ink caricature drawing labeled Champfleu
    ],
    "ogawa-kazumasa": [
        "wikimedia-47620448",  # studio bust portrait of older man with g
    ],
    "percival-lowell": [
        "wikimedia-4029856",  # dark cloth book cover, embossed emblem
        "wikimedia-2814687",  # decorated book cover 'Choson Land of Mor
        "wikimedia-4028496",  # maroon book cover 'The Solar System by P
        "wikimedia-4029444",  # plain red book cover, no image
    ],
    "peter-henry-emerson": [
        "aic-145668",  # plain dark blue book cover, no image
    ],
    "russell-lee": [
        "wikimedia-149972245",  # studio portrait of man with camera strap
        "wikimedia-149972022",  # same studio portrait of man, uncropped n
        "wikimedia-160236791",  # cropped studio portrait of same man
        "wikimedia-149972149",  # studio portrait of man with camera
        "wikimedia-114997197",  # duplicate variant
        "wikimedia-150056360",  # studio portrait of seated man in glasses
    ],
    "shimooka-renjo": [
        "wikimedia-13315734",  # color painting of Western family with de
        "wikimedia-110197354",  # man posing beside camera on tripod
        "wikimedia-183985494",  # seated man with swords, bakumatsu portra
    ],
    "tamamura-kozaburo": [
        "wikimedia-156529006",  # head portrait of elderly Japanese man
        "wikimedia-82415252",  # duplicate variant
    ],
    "timothy-osullivan": [
        "aic-210783",  # Printed text back of stereo card, no ima
        "aic-210767",  # Printed text back of stereo card, no ima
    ],
    "toni-frissell": [
        "wikimedia-5963176",  # passport-style head portrait of woman
        "wikimedia-29613345",  # Frissell in uniform showing camera to ch
        "wikimedia-29613723",  # Frissell with camera and children, film 
        "wikimedia-5946502",  # Frissell in uniform with camera, childre
        "wikimedia-88492650",  # woman in sunglasses posing, Matterhorn b
        "wikimedia-3705470",  # woman in turban holding camera, grass
    ],
    "ueno-hikoma": [
        "wikimedia-430882",  # bust portrait of Japanese man, arms cros
        "wikimedia-2264204",  # modern color photo of stone bust statue
        "wikimedia-2264218",  # modern B&W photo of same stone bust stat
    ],
    "walker-evans": [
        "wikimedia-2245656",  # candid portrait of Walker Evans himself 
        "wikimedia-147062335",  # closeup crop of Walker Evans portrait
    ],
}

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
    # NOTE: deliberately excluded as too controversial for the app's tone:
    # Felice Beato (staged corpses in war photos; embedded with the US force
    # in the 1871 invasion of Joseon), Edward S. Curtis (staged/romanticized
    # "vanishing race" framing), Eadweard Muybridge (killed his wife's lover).
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
    # ── Modern (20th century) ────────────────────────────────────────────
    # Living-memory masters are still in copyright, but U.S. government
    # commissions (FSA/OWI documentary program, NPS Mural Project) and
    # gifted-to-LOC archives are public domain — that's what these draw on.
    MasterSeed(
        id="dorothea-lange", name="Dorothea Lange", region="modern", nationality="US",
        birth_year=1895, death_year=1965, portrait_url=None,
        sources=[SourceQuery(source="wikimedia", query="Dorothea Lange",
                             artist="Lange")],  # Commons 36 PD (FSA)
    ),
    MasterSeed(
        id="walker-evans", name="Walker Evans", region="modern", nationality="US",
        birth_year=1903, death_year=1975, portrait_url=None,
        sources=[SourceQuery(source="wikimedia", query="Walker Evans FSA",
                             artist="Evans")],  # Commons 38 PD (FSA)
    ),
    MasterSeed(
        id="gordon-parks", name="Gordon Parks", region="modern", nationality="US",
        birth_year=1912, death_year=2006, portrait_url=None,
        sources=[SourceQuery(source="wikimedia", query="Gordon Parks",
                             artist="Parks"),  # Commons 7 PD (FSA/OWI)
                 SourceQuery(source="wikimedia", query="Gordon Parks FSA photograph",
                             artist="Parks")],
        title_overrides={
            "wikimedia-2740688":  # Commons filename is just "GordonParksFSA"
                "Ella Watson and Her Grandchildren, Washington, D.C.",
        },
    ),
    MasterSeed(
        id="ansel-adams", name="Ansel Adams", region="modern", nationality="US",
        birth_year=1902, death_year=1984, portrait_url=None,
        # NPS Mural Project (1941-42) — U.S. government work, PD.
        sources=[SourceQuery(source="wikimedia", query="Ansel Adams National Archives",
                             artist="Adams")],  # Commons 40 PD
    ),
    MasterSeed(
        id="arthur-rothstein", name="Arthur Rothstein", region="modern", nationality="US",
        birth_year=1915, death_year=1985, portrait_url=None,
        sources=[SourceQuery(source="wikimedia", query="Arthur Rothstein",
                             artist="Rothstein")],  # Commons 38 PD (FSA)
    ),
    MasterSeed(
        id="jack-delano", name="Jack Delano", region="modern", nationality="US",
        birth_year=1914, death_year=1997, portrait_url=None,
        sources=[SourceQuery(source="wikimedia", query="Jack Delano",
                             artist="Delano")],  # Commons 37 PD (FSA Kodachrome)
    ),
    MasterSeed(
        id="russell-lee", name="Russell Lee", region="modern", nationality="US",
        birth_year=1903, death_year=1986, portrait_url=None,
        sources=[SourceQuery(source="wikimedia", query="Russell Lee FSA",
                             artist="Lee")],  # Commons 38 PD (FSA)
        # Iconic anti-segregation document, but the period caption's language
        # is jarring as a casual gallery title.
        exclude_titles=['drinking at "colored" water cooler'],
    ),
    MasterSeed(
        id="toni-frissell", name="Toni Frissell", region="modern", nationality="US",
        birth_year=1907, death_year=1988, portrait_url=None,
        # Her archive was gifted to the Library of Congress, public domain.
        sources=[SourceQuery(source="wikimedia", query="Toni Frissell",
                             artist="Frissell")],  # Commons 38 PD
    ),
    MasterSeed(
        id="esther-bubley", name="Esther Bubley", region="modern", nationality="US",
        birth_year=1921, death_year=1998, portrait_url=None,
        sources=[SourceQuery(source="wikimedia", query="Esther Bubley",
                             artist="Bubley")],  # Commons 39 PD (OWI/SONJ-era PD set)
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
        id="peter-henry-emerson", name="Peter Henry Emerson", region="foreign",
        nationality="GB", birth_year=1856, death_year=1936, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Peter Henry Emerson")],  # AIC 40
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
        sources=[SourceQuery(source="aic", query="Frederick H. Evans"),  # AIC 28
                 SourceQuery(source="wikimedia", query="Frederick H. Evans photograph",
                             artist="Frederick H. Evans")],
    ),
    MasterSeed(
        id="hippolyte-bayard", name="Hippolyte Bayard", region="foreign",
        nationality="FR", birth_year=1801, death_year=1887, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Hippolyte Bayard"),  # AIC 26
                 SourceQuery(source="wikimedia", query="Hippolyte Bayard photograph",
                             artist="Hippolyte Bayard")],
    ),
    MasterSeed(
        id="etienne-carjat", name="Étienne Carjat", region="foreign", nationality="FR",
        birth_year=1828, death_year=1906, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Étienne Carjat")],  # AIC 36
    ),
    MasterSeed(
        id="lewis-hine", name="Lewis Hine", region="foreign", nationality="US",
        birth_year=1874, death_year=1940, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Lewis Hine"),  # AIC 60
                 SourceQuery(source="wikimedia", query="Lewis Hine", artist="Hine")],
    ),
    MasterSeed(
        id="gertrude-kasebier", name="Gertrude Käsebier", region="foreign",
        nationality="US", birth_year=1852, death_year=1934, portrait_url=None,
        sources=[SourceQuery(source="aic", query="Gertrude Käsebier"),  # AIC 5
                 SourceQuery(source="wikimedia", query="Gertrude Käsebier",
                             artist="Käsebier")],
    ),
]

ROSTER = [
    replace(seed, exclude_ids=_EXCLUDED_WORK_IDS.get(seed.id, []))
    for seed in ROSTER
]
