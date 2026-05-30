"use client";
import Link from "next/link";
import { Compass, Search, Map, Heart, User } from "lucide-react";
import { LoginButton } from "@/components/LoginButton";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useLang } from "@/components/LanguageProvider";

const ITEMS = [
  { href: "/", key: "nav.discover", icon: Compass },
  { href: "/search", key: "nav.search", icon: Search },
  { href: "/map", key: "nav.map", icon: Map },
  { href: "/scrap", key: "nav.scrap", icon: Heart },
  { href: "/me", key: "nav.me", icon: User },
] as const;

export function Nav() {
  const { t } = useLang();
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
                {t(it.key)}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <LanguageSwitcher />
            <LoginButton />
          </div>
        </div>
      </header>

      {/* mobile top bar — keeps the language switcher reachable on phones */}
      <header className="sticky top-0 z-20 flex h-12 items-center justify-between border-b border-line bg-black px-5 md:hidden">
        <Link href="/" className="text-base font-extrabold tracking-tight">FRAME</Link>
        <LanguageSwitcher />
      </header>

      {/* mobile bottom tab */}
      <nav className="fixed inset-x-0 bottom-0 z-20 flex border-t border-line bg-black pb-5 pt-2 md:hidden">
        {ITEMS.map((it) => {
          const Icon = it.icon;
          return (
            <Link key={it.href} href={it.href}
              className="flex flex-1 flex-col items-center gap-0.5 text-[10px] text-tx3">
              <Icon size={18} />
              {t(it.key)}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
