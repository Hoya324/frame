import type { Locale } from "@/lib/i18n";

// Contemporary / modern masters whose works are still in copyright, so we
// can't host a single image — instead we list them and link out (official
// foundation, gallery, museum or encyclopedia page; every URL verified 200).
export interface ContemporaryMaster {
  id: string;
  name: Record<Locale, string>;
  years: string;
  line: Record<Locale, string>; // one-line "why they matter"
  url: string;
}

export const CONTEMPORARY: ContemporaryMaster[] = [
  {
    id: "koo-bohnchang",
    name: { ko: "구본창", en: "Koo Bohnchang", ja: "ク・ボンチャン" },
    years: "1953–",
    line: {
      ko: "백자와 탈 — 한국의 사물을 응시하는 시선",
      en: "Quiet gazes at Korean white porcelain and masks",
      ja: "白磁と仮面 — 韓国の物を見つめる視線",
    },
    url: "https://www.kukjegallery.com/artists/koo-bohnchang",
  },
  {
    id: "bae-bien-u",
    name: { ko: "배병우", en: "Bae Bien-U", ja: "ペ・ビョンウ" },
    years: "1950–",
    line: {
      ko: "안개 속 소나무 숲의 사진가",
      en: "Photographer of pine forests in the mist",
      ja: "霧の松林の写真家",
    },
    url: "https://ko.wikipedia.org/wiki/%EB%B0%B0%EB%B3%91%EC%9A%B0",
  },
  {
    id: "han-youngsoo",
    name: { ko: "한영수", en: "Han Youngsoo", ja: "ハン・ヨンス" },
    years: "1933–1999",
    line: {
      ko: "전후 1950–60년대 서울의 세련된 일상",
      en: "Elegant everyday Seoul of the 1950s–60s",
      ja: "戦後ソウルの洗練された日常",
    },
    url: "https://en.wikipedia.org/wiki/Han_Youngsoo",
  },
  {
    id: "daido-moriyama",
    name: { ko: "모리야마 다이도", en: "Daido Moriyama", ja: "森山大道" },
    years: "1938–",
    line: {
      ko: "거칠고 흔들리는 도쿄 거리의 눈",
      en: "Grainy, blurry eyes on the Tokyo street",
      ja: "アレ・ブレ・ボケの東京の眼",
    },
    url: "https://www.moriyamadaido.com/",
  },
  {
    id: "hiroshi-sugimoto",
    name: { ko: "스기모토 히로시", en: "Hiroshi Sugimoto", ja: "杉本博司" },
    years: "1948–",
    line: {
      ko: "바다와 극장 — 시간을 찍는 개념 사진",
      en: "Seascapes and theaters — photographing time itself",
      ja: "海景と劇場 — 時間を写す概念写真",
    },
    url: "https://www.sugimotohiroshi.com/",
  },
  {
    id: "rinko-kawauchi",
    name: { ko: "가와우치 린코", en: "Rinko Kawauchi", ja: "川内倫子" },
    years: "1972–",
    line: {
      ko: "일상의 빛을 건져 올리는 서정",
      en: "Lyric attention to the light of ordinary days",
      ja: "日常の光をすくいあげる叙情",
    },
    url: "https://rinkokawauchi.com/",
  },
  {
    id: "shoji-ueda",
    name: { ko: "우에다 쇼지", en: "Shoji Ueda", ja: "植田正治" },
    years: "1913–2000",
    line: {
      ko: "돗토리 모래언덕 위의 초현실 연출",
      en: "Surreal staging on the Tottori sand dunes",
      ja: "鳥取砂丘の演出写真",
    },
    url: "https://www.houki-town.jp/ueda/",
  },
  {
    id: "henri-cartier-bresson",
    name: { ko: "앙리 카르티에-브레송", en: "Henri Cartier-Bresson", ja: "アンリ・カルティエ＝ブレッソン" },
    years: "1908–2004",
    line: {
      ko: "'결정적 순간'의 창시자",
      en: "Father of the decisive moment",
      ja: "「決定的瞬間」の創始者",
    },
    url: "https://www.henricartierbresson.org/",
  },
  {
    id: "vivian-maier",
    name: { ko: "비비안 마이어", en: "Vivian Maier", ja: "ヴィヴィアン・マイヤー" },
    years: "1926–2009",
    line: {
      ko: "사후에 발견된 거리 사진의 전설",
      en: "The street-photography legend found after her death",
      ja: "死後に発見された伝説のストリート写真家",
    },
    url: "https://www.vivianmaier.com/",
  },
  {
    id: "saul-leiter",
    name: { ko: "솔 라이터", en: "Saul Leiter", ja: "ソール・ライター" },
    years: "1923–2013",
    line: {
      ko: "비 오는 뉴욕, 유리창 너머의 색",
      en: "Color through rainy New York windows",
      ja: "雨のニューヨーク、窓越しの色彩",
    },
    url: "https://www.saulleiterfoundation.org/",
  },
  {
    id: "william-eggleston",
    name: { ko: "윌리엄 이글스턴", en: "William Eggleston", ja: "ウィリアム・エグルストン" },
    years: "1939–",
    line: {
      ko: "컬러 사진을 예술로 끌어올린 선구자",
      en: "The pioneer who made color photography art",
      ja: "カラー写真を芸術にした先駆者",
    },
    url: "https://egglestonartfoundation.org/",
  },
  {
    id: "irving-penn",
    name: { ko: "어빙 펜", en: "Irving Penn", ja: "アーヴィング・ペン" },
    years: "1917–2009",
    line: {
      ko: "극도로 정제된 스튜디오 초상과 정물",
      en: "Severely refined studio portraits and still lifes",
      ja: "極度に洗練されたスタジオ写真",
    },
    url: "https://irvingpenn.org/",
  },
  {
    id: "robert-doisneau",
    name: { ko: "로베르 두아노", en: "Robert Doisneau", ja: "ロベール・ドアノー" },
    years: "1912–1994",
    line: {
      ko: "파리의 유머와 낭만을 포착한 눈",
      en: "Humor and romance on the streets of Paris",
      ja: "パリのユーモアとロマンを捉えた眼",
    },
    url: "https://www.robert-doisneau.com/",
  },
  {
    id: "michael-kenna",
    name: { ko: "마이클 케나", en: "Michael Kenna", ja: "マイケル・ケンナ" },
    years: "1953–",
    line: {
      ko: "고요한 흑백 풍경 — 솔섬의 그 사진가",
      en: "Stillness in black and white — of Solseom fame",
      ja: "静謐なモノクロ風景の写真家",
    },
    url: "https://www.michaelkenna.com/",
  },
];
