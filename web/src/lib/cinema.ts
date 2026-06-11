import type { Locale } from "@/lib/i18n";

// "영화, 한 프레임" — learn composition, light and color from cinema.
//
// Two kinds, split by copyright:
//  - CINEMA_PD: public-domain films (early cinema + 1940s noir whose copyright
//    lapsed). We host the real frame (hotlinked from Wikimedia Commons).
//  - CINEMA_MODERN: in-copyright modern masterpieces, included as a 인용
//    (quotation for criticism/education, 저작권법 §28/§35-5): a single low-res
//    still with full attribution (director + studio) and the educational note
//    that is the whole point. The `studio` credit is mandatory; `image` is
//    filled from a sourced low-res still (left undefined until sourced — the
//    UI hides any modern entry without one rather than render a broken card).
export interface CinemaScene {
  id: string;
  title: Record<Locale, string>;
  credit: Record<Locale, string>; // director (· cinematographer) · year
  lesson: Record<Locale, string>; // what to learn — composition / light / colour
  url: string; // link out (Wikipedia)
  image?: string; // hosted still — PD Commons frame, or sourced 인용 still
  studio?: string; // attribution for in-copyright modern stills (required there)
}

export const CINEMA_PD: CinemaScene[] = [
  {
    id: "trip-to-the-moon",
    title: { ko: "달세계 여행", en: "A Trip to the Moon", ja: "月世界旅行" },
    credit: { ko: "조르주 멜리에스 · 1902", en: "Georges Méliès · 1902", ja: "ジョルジュ・メリエス · 1902" },
    lesson: {
      ko: "영화 특수효과의 시대를 연 멜리에스는 무대를 정면으로 바라보는 회화적 구성으로 환상을 빚었습니다. 깊이 없는 평면 무대와 좌우 대칭이 오히려 동화 같은 비현실감을 만듭니다.",
      en: "Méliès, who opened the age of movie special effects, built fantasy with painterly, head-on staging. The flat, frontal set and symmetry are exactly what make it feel like a fairy tale.",
      ja: "映画特殊効果の時代を開いたメリエスは、舞台を正面から捉える絵画的な構図で幻想を作りました。奥行きのない平面的な舞台と左右対称が、むしろ童話のような非現実感を生みます。",
    },
    url: "https://en.wikipedia.org/wiki/A_Trip_to_the_Moon",
    image: "https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Trip_to_the_Moon_Workshop.png/960px-Trip_to_the_Moon_Workshop.png",
  },
  {
    id: "caligari",
    title: { ko: "칼리가리 박사의 밀실", en: "The Cabinet of Dr. Caligari", ja: "カリガリ博士" },
    credit: { ko: "로베르트 비네 · 1920", en: "Robert Wiene · 1920", ja: "ローベルト・ヴィーネ · 1920" },
    lesson: {
      ko: "독일 표현주의의 출발점. 직선이 사라진 사선과 뾰족한 세트, 붓으로 칠한 그림자가 인물의 불안한 내면을 공간 그 자체로 번역합니다.",
      en: "The starting point of German Expressionism. Jagged diagonals, pointed sets and shadows literally painted on the walls translate a disturbed mind into space itself.",
      ja: "ドイツ表現主義の出発点。直線を失った斜線と尖ったセット、筆で描かれた影が、不安な内面を空間そのものに翻訳します。",
    },
    url: "https://en.wikipedia.org/wiki/The_Cabinet_of_Dr._Caligari",
    image: "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Publicity_still_for_The_Cabinet_of_Dr._Caligari_%281920%29_04.jpg/960px-Publicity_still_for_The_Cabinet_of_Dr._Caligari_%281920%29_04.jpg",
  },
  {
    id: "potemkin",
    title: { ko: "전함 포템킨 (오데사 계단)", en: "Battleship Potemkin (Odessa Steps)", ja: "戦艦ポチョムキン" },
    credit: { ko: "세르게이 에이젠슈테인 · 1925", en: "Sergei Eisenstein · 1925", ja: "セルゲイ・エイゼンシュテイン · 1925" },
    lesson: {
      ko: "몽타주의 정수. 계단을 굴러 내려가는 유모차라는 단 하나의 디테일에 학살의 공포를 응축해, 편집의 리듬이 곧 감정임을 보여줍니다.",
      en: "The essence of montage. The single detail of a pram rolling down the steps concentrates the horror of a massacre — proving that the rhythm of editing is itself emotion.",
      ja: "モンタージュの真髄。階段を転がり落ちる乳母車という一つのディテールに虐殺の恐怖を凝縮し、編集のリズムこそが感情であることを示します。",
    },
    url: "https://en.wikipedia.org/wiki/Battleship_Potemkin",
    image: "https://upload.wikimedia.org/wikipedia/commons/0/0b/Odessastepsbaby.jpg",
  },
  {
    id: "phantom-of-the-opera",
    title: { ko: "오페라의 유령", en: "The Phantom of the Opera", ja: "オペラの怪人" },
    credit: { ko: "루퍼트 줄리안 · 1925", en: "Rupert Julian · 1925", ja: "ルパート・ジュリアン · 1925" },
    lesson: {
      ko: "가면이 벗겨지는 순간을 연극적 조명과 실루엣으로 구성합니다. 빛과 어둠의 대비만으로 공포의 절정을 만드는 무성영화 조명의 교본입니다.",
      en: "The unmasking is built from theatrical light and silhouette. A textbook of silent-era lighting that reaches the peak of horror through contrast of light and dark alone.",
      ja: "仮面が剥がれる瞬間を、演劇的な照明とシルエットで構成します。光と闇の対比だけで恐怖の頂点を作る、無声映画照明の教本です。",
    },
    url: "https://en.wikipedia.org/wiki/The_Phantom_of_the_Opera_(1925_film)",
    image: "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9a/Phantomunmasking.jpg/960px-Phantomunmasking.jpg",
  },
  {
    id: "the-general",
    title: { ko: "제너럴", en: "The General", ja: "キートンの大列車追跡" },
    credit: { ko: "버스터 키튼 · 1926", en: "Buster Keaton · 1926", ja: "バスター・キートン · 1926" },
    lesson: {
      ko: "키튼은 기차와 인물, 풍경을 한 프레임 깊숙이 배치(딥 스테이징)해, 컷 없이도 액션의 지리와 인과를 또렷이 읽히게 합니다.",
      en: "Keaton stacks train, figure and landscape deep within one frame (deep staging), so the geography and cause-and-effect of the action read clearly without a single cut.",
      ja: "キートンは列車・人物・風景を一つのフレームの奥深くに配置（ディープ・ステージング）し、カットなしでアクションの地理と因果をはっきり読ませます。",
    },
    url: "https://en.wikipedia.org/wiki/The_General_(1926_film)",
    image: "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/The_General_17.jpg/960px-The_General_17.jpg",
  },
  {
    id: "metropolis",
    title: { ko: "메트로폴리스", en: "Metropolis", ja: "メトロポリス" },
    credit: { ko: "프리츠 랑 · 1927", en: "Fritz Lang · 1927", ja: "フリッツ・ラング · 1927" },
    lesson: {
      ko: "프리츠 랑은 좌우 대칭과 기하학적 군중 배치로 거대 도시의 위압을 시각화합니다. 인간을 하나의 패턴으로 환원하는 구도가 곧 주제가 됩니다.",
      en: "Fritz Lang visualises the menace of the mega-city through symmetry and geometric crowds. The composition that reduces humans to a pattern is itself the theme.",
      ja: "フリッツ・ラングは左右対称と幾何学的な群衆配置で巨大都市の威圧を視覚化します。人間を一つのパターンに還元する構図こそがテーマです。",
    },
    url: "https://en.wikipedia.org/wiki/Metropolis_(1927_film)",
    image: "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Metropolis_%281927%29_-_Hel.jpg/960px-Metropolis_%281927%29_-_Hel.jpg",
  },
  {
    id: "man-with-a-movie-camera",
    title: { ko: "카메라를 든 사나이", en: "Man with a Movie Camera", ja: "カメラを持った男" },
    credit: { ko: "지가 베르토프 · 1929", en: "Dziga Vertov · 1929", ja: "ジガ・ヴェルトフ · 1929" },
    lesson: {
      ko: "베르토프는 이중노출과 '카메라를 찍는 카메라'로 영화가 스스로를 드러내게 합니다. 구도 자체가 보는 행위에 대한 질문이 됩니다.",
      en: "Vertov makes cinema reveal itself through double exposure and a camera filming the camera. The composition itself becomes a question about the act of seeing.",
      ja: "ヴェルトフは二重露光と「カメラを撮るカメラ」で、映画自身を露わにします。構図そのものが「見る」という行為への問いになります。",
    },
    url: "https://en.wikipedia.org/wiki/Man_with_a_Movie_Camera",
    image: "https://upload.wikimedia.org/wikipedia/commons/8/8b/Man_with_a_Movie_Camera_by_Dziga_Vertov.jpg",
  },
  {
    id: "detour",
    title: { ko: "디투어", en: "Detour", ja: "恐怖のまわり道" },
    credit: { ko: "에드거 G. 울머 · 1945", en: "Edgar G. Ulmer · 1945", ja: "エドガー・G・ウルマー · 1945" },
    lesson: {
      ko: "저예산 누아르의 전설. 최소한의 저조도 조명과 좁은 프레임이 인물을 운명에 가두는 폐소감을 만듭니다.",
      en: "A legend of low-budget noir. Minimal low-key lighting and a tight frame create the claustrophobia of a man trapped by fate.",
      ja: "低予算ノワールの伝説。最小限のローキー照明と狭いフレームが、運命に囚われた人物の閉塞感を生みます。",
    },
    url: "https://en.wikipedia.org/wiki/Detour_(1945_film)",
    image: "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/Ann_Savage_and_Tom_Neal_in_Detour.jpg/960px-Ann_Savage_and_Tom_Neal_in_Detour.jpg",
  },
  {
    id: "scarlet-street",
    title: { ko: "스칼렛 스트리트", en: "Scarlet Street", ja: "スカーレット・ストリート" },
    credit: { ko: "프리츠 랑 · 1945", en: "Fritz Lang · 1945", ja: "フリッツ・ラング · 1945" },
    lesson: {
      ko: "프리츠 랑이 누아르로 옮긴 그림자. 인물을 어둠 속에 고립시키는 조명이 욕망과 파멸의 심리를 공간으로 그립니다.",
      en: "The shadow Fritz Lang carried into noir. Lighting that isolates a figure in darkness draws the psychology of desire and ruin as space.",
      ja: "フリッツ・ラングがノワールに持ち込んだ影。人物を闇の中に孤立させる照明が、欲望と破滅の心理を空間として描きます。",
    },
    url: "https://en.wikipedia.org/wiki/Scarlet_Street",
    image: "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Joan_Bennett_in_Scarlet_Street_%282%29.jpg/960px-Joan_Bennett_in_Scarlet_Street_%282%29.jpg",
  },
  {
    id: "the-stranger",
    title: { ko: "이방인", en: "The Stranger", ja: "上海から来た女… (The Stranger)" },
    credit: { ko: "오슨 웰스 · 1946", en: "Orson Welles · 1946", ja: "オーソン・ウェルズ · 1946" },
    lesson: {
      ko: "오슨 웰스 특유의 깊은 공간과 강한 명암 대비. 전경과 후경을 동시에 또렷이 살리는 구성이 긴장을 끌어올립니다.",
      en: "Orson Welles's signature deep space and hard chiaroscuro. Keeping foreground and background both in sharp focus ratchets up the tension.",
      ja: "オーソン・ウェルズ特有の深い空間と強い明暗対比。前景と後景を同時にくっきり捉える構図が緊張を高めます。",
    },
    url: "https://en.wikipedia.org/wiki/The_Stranger_(1946_film)",
    image: "https://upload.wikimedia.org/wikipedia/commons/f/fb/The_Stranger_1946_%283%29.jpg",
  },
];

export const CINEMA_MODERN: CinemaScene[] = [
  {
    id: "2001",
    title: { ko: "2001 스페이스 오디세이", en: "2001: A Space Odyssey", ja: "2001年宇宙の旅" },
    credit: { ko: "스탠리 큐브릭 · 1968", en: "Stanley Kubrick · 1968", ja: "スタンリー・キューブリック · 1968" },
    lesson: {
      ko: "큐브릭은 완벽한 좌우 대칭과 일점 투시로 우주의 냉정함을 구도에 새깁니다. 흰색과 검정의 절제 위에 놓인 HAL의 붉은 점 하나가 모든 시선을 잡아끕니다.",
      en: "Kubrick carves the cold of space into the frame with perfect symmetry and one-point perspective. A single red dot — HAL — pulls every eye against the restraint of white and black.",
      ja: "キューブリックは完璧な左右対称と一点透視で宇宙の冷たさを構図に刻みます。白と黒の抑制の上に置かれたHALの赤い点一つが、すべての視線を引きつけます。",
    },
    url: "https://en.wikipedia.org/wiki/2001:_A_Space_Odyssey",
    studio: "Metro-Goldwyn-Mayer",
  },
  {
    id: "days-of-heaven",
    title: { ko: "천국의 나날들", en: "Days of Heaven", ja: "天国の日々" },
    credit: { ko: "테런스 맬릭 · 촬영 네스토르 알멘드로스 · 1978", en: "Terrence Malick · dop Néstor Almendros · 1978", ja: "テレンス・マリック · 撮影ネストール・アルメンドロス · 1978" },
    lesson: {
      ko: "촬영감독 알멘드로스는 해 질 녘 '매직 아워'의 자연광만으로 황금빛 들판을 담았습니다. 인공조명을 버린 빛이 곧 감정의 온도가 됩니다.",
      en: "Cinematographer Almendros shot the golden fields with nothing but the natural light of the 'magic hour' at dusk. Light, freed of artificial sources, becomes the temperature of feeling.",
      ja: "撮影監督アルメンドロスは、夕暮れの「マジックアワー」の自然光だけで黄金の野を捉えました。人工照明を捨てた光が、そのまま感情の温度になります。",
    },
    url: "https://en.wikipedia.org/wiki/Days_of_Heaven",
    studio: "Paramount Pictures",
  },
  {
    id: "in-the-mood-for-love",
    title: { ko: "화양연화", en: "In the Mood for Love", ja: "花様年華" },
    credit: { ko: "왕가위 · 촬영 크리스토퍼 도일 · 2000", en: "Wong Kar-wai · dop Christopher Doyle · 2000", ja: "ウォン・カーウァイ · 撮影クリストファー・ドイル · 2000" },
    lesson: {
      ko: "왕가위와 도일은 포화된 붉은색과 초록의 대비, 좁은 프레임으로 억눌린 그리움을 칠합니다. 색이 곧 인물이 말하지 못한 감정이 됩니다.",
      en: "Wong Kar-wai and Doyle paint suppressed longing with saturated red-against-green and cramped framing. Colour becomes the emotion the characters never speak.",
      ja: "ウォン・カーウァイとドイルは、飽和した赤と緑の対比、狭いフレームで抑えられた想いを塗ります。色がそのまま、人物が言えなかった感情になります。",
    },
    url: "https://en.wikipedia.org/wiki/In_the_Mood_for_Love",
    studio: "Block 2 Pictures · Jet Tone",
  },
  {
    id: "amelie",
    title: { ko: "아멜리에", en: "Amélie", ja: "アメリ" },
    credit: { ko: "장피에르 죄네 · 촬영 브뤼노 델보넬 · 2001", en: "Jean-Pierre Jeunet · dop Bruno Delbonnel · 2001", ja: "ジャン＝ピエール・ジュネ · 撮影ブリュノ・デルボネル · 2001" },
    lesson: {
      ko: "죄네는 초록과 붉은빛, 황금빛을 과장해 파리를 동화로 바꿉니다. 색의 채도를 끌어올리는 것만으로 일상이 환상이 됩니다.",
      en: "Jeunet turns Paris into a fairy tale by exaggerating green, red and gold. Simply pushing up saturation makes the everyday fantastical.",
      ja: "ジュネは緑と赤、金色を誇張してパリを童話に変えます。色の彩度を上げるだけで、日常が幻想になります。",
    },
    url: "https://en.wikipedia.org/wiki/Am%C3%A9lie",
    studio: "UGC-Fox Distribution",
  },
  {
    id: "hero",
    title: { ko: "영웅", en: "Hero", ja: "HERO" },
    credit: { ko: "장이머우 · 촬영 크리스토퍼 도일 · 2002", en: "Zhang Yimou · dop Christopher Doyle · 2002", ja: "チャン・イーモウ · 撮影クリストファー・ドイル · 2002" },
    lesson: {
      ko: "장이머우는 장(章)마다 하나의 색을 부여해 같은 이야기를 색으로 다시 들려줍니다. 색이 곧 서사이자 감정의 장르가 됩니다.",
      en: "Zhang Yimou gives each chapter a single dominant colour, retelling the same story through colour. Colour becomes both narrative and the genre of feeling.",
      ja: "チャン・イーモウは章ごとに一つの色を与え、同じ物語を色で語り直します。色がそのまま物語であり、感情のジャンルになります。",
    },
    url: "https://en.wikipedia.org/wiki/Hero_(2002_film)",
    studio: "Beijing New Picture Film",
  },
  {
    id: "grand-budapest-hotel",
    title: { ko: "그랜드 부다페스트 호텔", en: "The Grand Budapest Hotel", ja: "グランド・ブダペスト・ホテル" },
    credit: { ko: "웨스 앤더슨 · 촬영 로버트 예먼 · 2014", en: "Wes Anderson · dop Robert Yeoman · 2014", ja: "ウェス・アンダーソン · 撮影ロバート・イェーオマン · 2014" },
    lesson: {
      ko: "웨스 앤더슨은 정중앙 대칭과 파스텔 팔레트로 동화적 질서를 세웁니다. 분홍과 보라의 균형이 향수와 유머를 동시에 빚습니다.",
      en: "Wes Anderson builds a storybook order from dead-centre symmetry and a pastel palette. The balance of pink and purple conjures nostalgia and humour at once.",
      ja: "ウェス・アンダーソンは中央対称とパステルのパレットで童話的な秩序を築きます。ピンクと紫の均衡が、郷愁とユーモアを同時に生みます。",
    },
    url: "https://en.wikipedia.org/wiki/The_Grand_Budapest_Hotel",
    studio: "Fox Searchlight Pictures",
  },
  {
    id: "moonlight",
    title: { ko: "문라이트", en: "Moonlight", ja: "ムーンライト" },
    credit: { ko: "배리 젱킨스 · 촬영 제임스 랙스턴 · 2016", en: "Barry Jenkins · dop James Laxton · 2016", ja: "バリー・ジェンキンス · 撮影ジェームズ・ラクストン · 2016" },
    lesson: {
      ko: "촬영감독 랙스턴은 푸른빛과 보랏빛으로 흑인의 피부 결을 새롭게 비춥니다. 색온도가 인물의 정체성과 고독을 함께 말합니다.",
      en: "Cinematographer Laxton lights Black skin anew in blues and purples. Colour temperature speaks the character's identity and solitude at the same time.",
      ja: "撮影監督ラクストンは青と紫で黒人の肌の質感を新たに照らします。色温度が人物のアイデンティティと孤独を同時に語ります。",
    },
    url: "https://en.wikipedia.org/wiki/Moonlight_(2016_film)",
    studio: "A24 · Plan B Entertainment",
  },
  {
    id: "blade-runner-2049",
    title: { ko: "블레이드 러너 2049", en: "Blade Runner 2049", ja: "ブレードランナー 2049" },
    credit: { ko: "드니 빌뇌브 · 촬영 로저 디킨스 · 2017", en: "Denis Villeneuve · dop Roger Deakins · 2017", ja: "ドゥニ・ヴィルヌーヴ · 撮影ロジャー・ディーキンス · 2017" },
    lesson: {
      ko: "촬영감독 로저 디킨스는 구역마다 하나의 색을 지배색으로 깔아 감정의 지도를 그립니다. 주황과 청록의 대비가 디스토피아의 고독을 색으로 번역합니다.",
      en: "Cinematographer Roger Deakins lays one dominant colour over each zone, drawing a map of emotion. The clash of orange and teal translates dystopian solitude into colour.",
      ja: "撮影監督ロジャー・ディーキンスは地区ごとに一つの色を支配色として敷き、感情の地図を描きます。オレンジと青緑の対比が、ディストピアの孤独を色に翻訳します。",
    },
    url: "https://en.wikipedia.org/wiki/Blade_Runner_2049",
    studio: "Warner Bros. · Alcon Entertainment",
  },
];
