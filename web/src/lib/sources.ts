// Human-readable label for each crawler source id (the `source` enum the
// backend stores on every exhibition). Used to tell the reader where a listing
// was pulled from.
const SOURCE_LABELS: Record<string, string> = {
  artmap: "ARTMAP",
  naver: "네이버 블로그",
  photo_sema: "서울시립 사진미술관",
  museum_hanmi: "뮤지엄한미",
  koba: "KOBA",
  goeun: "고은사진미술관",
  gallery_lux: "갤러리 룩스",
  gallery_kong: "공근혜갤러리",
  ryugaheon: "류가헌",
  ilwoo_space: "일우스페이스",
  sangsangmadang: "KT&G 상상마당",
  canon_gallery: "캐논 갤러리",
  tokyo_photographic_art_museum: "東京都写真美術館",
  tokyo_art_beat: "Tokyo Art Beat",
  fujifilm_square: "FUJIFILM SQUARE",
  gallery_bresson: "갤러리 브레송",
  pgi: "PGI",
  zen_foto: "ZEN FOTO GALLERY",
};

// Fallback for snapshots exported before the `source` field existed: map the
// source_url host back to a source id. Safe to keep — once every row carries
// `source`, this branch is simply never reached.
const HOST_TO_SOURCE: Record<string, string> = {
  "art-map.co.kr": "artmap",
  "sema.seoul.go.kr": "photo_sema",
  "museumhanmi.or.kr": "museum_hanmi",
  "conference.kobashow.com": "koba",
  "www.goeunmuseum.kr": "goeun",
  "gallerylux.net": "gallery_lux",
  "www.konggallery.com": "gallery_kong",
  "blog.naver.com": "ryugaheon",
  "www.ilwoo.org": "ilwoo_space",
  "www.sangsangmadang.com": "sangsangmadang",
  "kr.canon": "canon_gallery",
  "topmuseum.jp": "tokyo_photographic_art_museum",
  "www.tokyoartbeat.com": "tokyo_art_beat",
  "fujifilmsquare.jp": "fujifilm_square",
  "gallerybresson.com": "gallery_bresson",
  "www.pgi.ac": "pgi",
  "zen-foto.jp": "zen_foto",
};

function hostOf(url: string | null): string | null {
  if (!url) return null;
  try {
    return new URL(url).hostname;
  } catch {
    return null;
  }
}

// Resolve the display label for an exhibition's source. Prefers the stored
// `source` id, falls back to the URL host, and finally to the bare hostname so
// something sensible always shows. Returns null only when both are absent.
export function sourceLabel(
  source: string | null | undefined,
  sourceUrl: string | null | undefined,
): string | null {
  let key = source ?? null;
  if (!key) key = HOST_TO_SOURCE[hostOf(sourceUrl ?? null) ?? ""] ?? null;
  if (key && SOURCE_LABELS[key]) return SOURCE_LABELS[key];
  const host = hostOf(sourceUrl ?? null);
  return host ? host.replace(/^www\./, "") : null;
}
