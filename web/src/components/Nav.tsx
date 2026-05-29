import Link from "next/link";
import { Compass, Search, Map, Heart, User } from "lucide-react";

const ITEMS = [
  { href: "/", label: "둘러보기", icon: Compass },
  { href: "/search", label: "검색", icon: Search },
  { href: "/map", label: "지도", icon: Map },
  { href: "/scrap", label: "스크랩", icon: Heart },
  { href: "/me", label: "마이", icon: User },
];

export function Nav() {
  return (
    <>
      {/* desktop top nav */}
      <header className="sticky top-0 z-20 hidden border-b border-line bg-black md:block">
        <div className="mx-auto flex h-14 max-w-[1180px] items-center gap-7 px-7">
          <Link href="/" className="text-lg font-extrabold tracking-tight">FRAME</Link>
          <nav className="flex gap-1">
            {ITEMS.slice(0, 4).map((it) => (
              <Link key={it.href} href={it.href}
                className="rounded-md px-3 py-1.5 text-sm font-medium text-tx3 hover:text-tx">
                {it.label}
              </Link>
            ))}
          </nav>
          <button className="ml-auto rounded-md bg-white px-4 py-2 text-sm font-semibold text-black">
            로그인
          </button>
        </div>
      </header>

      {/* mobile bottom tab */}
      <nav className="fixed inset-x-0 bottom-0 z-20 flex border-t border-line bg-black pb-5 pt-2 md:hidden">
        {ITEMS.map((it) => {
          const Icon = it.icon;
          return (
            <Link key={it.href} href={it.href}
              className="flex flex-1 flex-col items-center gap-0.5 text-[10px] text-tx3">
              <Icon size={18} />
              {it.label}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
