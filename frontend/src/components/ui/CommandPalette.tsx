"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/api-client";
import { STAGE_LABELS, SEGMENT_LABELS, NAV_ITEMS } from "@/lib/constants";
import { toPersianNum } from "@/lib/utils";

interface SearchResultItem {
  id: string;
  type: "contact" | "invoice" | "campaign" | "product" | "page";
  title: string;
  subtitle?: string | null;
  url: string;
  meta?: Record<string, unknown>;
}

interface SearchResponse {
  query: string;
  total: number;
  results: SearchResultItem[];
}

const TYPE_CONFIG: Record<string, { icon: string; label: string; color: string }> = {
  page: { icon: "📄", label: "صفحه", color: "bg-gray-100 text-gray-600" },
  contact: { icon: "👤", label: "مخاطب", color: "bg-blue-50 text-blue-700" },
  invoice: { icon: "🧾", label: "فاکتور", color: "bg-green-50 text-green-700" },
  campaign: { icon: "📣", label: "کمپین", color: "bg-purple-50 text-purple-700" },
  product: { icon: "📦", label: "محصول", color: "bg-amber-50 text-amber-700" },
};

export default function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // ⌘+K / Ctrl+K to toggle
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      }
      if (e.key === "Escape") setIsOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Focus input on open
  useEffect(() => {
    if (isOpen) {
      requestAnimationFrame(() => inputRef.current?.focus());
      setQuery("");
      setResults([]);
      setActiveIndex(0);
    }
  }, [isOpen]);

  // Page results filtered from NAV_ITEMS
  const getPageResults = useCallback((q: string): SearchResultItem[] => {
    const items = q
      ? NAV_ITEMS.filter(
          (item) =>
            item.label.includes(q) ||
            item.href.toLowerCase().includes(q.toLowerCase())
        )
      : NAV_ITEMS;
    return items.map((item) => ({
      id: "page-" + item.href,
      type: "page" as const,
      title: item.icon + " " + item.label,
      subtitle: null,
      url: item.href,
    }));
  }, []);

  // Search API with debounce
  useEffect(() => {
    if (!isOpen) return;
    const pageResults = getPageResults(query);

    if (!query || query.length < 2) {
      setResults(pageResults);
      setActiveIndex(0);
      return;
    }

    setIsSearching(true);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await apiGet<SearchResponse>(
          "/search?q=" + encodeURIComponent(query) + "&limit=20"
        );
        if (res.ok && res.data) {
          setResults([...pageResults, ...(res.data.results || [])]);
        } else {
          setResults(pageResults);
        }
      } catch {
        setResults(pageResults);
      } finally {
        setIsSearching(false);
        setActiveIndex(0);
      }
    }, 250);
    return () => clearTimeout(debounceRef.current);
  }, [query, isOpen, getPageResults]);

  // Navigate to selected result
  const navigateTo = useCallback(
    (item: SearchResultItem) => {
      setIsOpen(false);
      router.push(item.url);
    },
    [router]
  );

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((prev) => Math.min(prev + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter" && results[activeIndex]) {
      e.preventDefault();
      navigateTo(results[activeIndex]);
    }
  };

  // Scroll active item into view
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const el = list.querySelector("[data-active=true]") as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  if (!isOpen) return null;

  // Group results by type for display
  const grouped: Record<string, SearchResultItem[]> = {};
  for (const r of results) {
    if (!grouped[r.type]) grouped[r.type] = [];
    grouped[r.type].push(r);
  }
  const typeOrder = ["page", "contact", "invoice", "campaign", "product"];
  let globalIdx = 0;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50"
        onClick={() => setIsOpen(false)}
      />

      {/* Dialog */}
      <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4 pointer-events-none">
        <div
          className="w-full max-w-lg bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden pointer-events-auto"
          role="dialog"
          aria-label="جستجوی سریع"
        >
          {/* Search input */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
            <svg
              className="w-5 h-5 text-gray-400 shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="جستجو در مخاطبین، فاکتورها، کمپین‌ها..."
              className="flex-1 text-sm outline-none placeholder-gray-400 bg-transparent"
              dir="rtl"
            />
            {isSearching && (
              <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
            )}
            <kbd className="hidden sm:inline-flex px-2 py-0.5 text-[10px] text-gray-400 bg-gray-50 border border-gray-200 rounded font-mono">
              ESC
            </kbd>
          </div>

          {/* Results list */}
          <div ref={listRef} className="max-h-[50vh] overflow-y-auto py-2">
            {results.length === 0 && query.length >= 2 && !isSearching && (
              <div className="px-4 py-8 text-center text-sm text-gray-400">
                نتیجه‌ای یافت نشد
              </div>
            )}

            {typeOrder.map((type) => {
              const items = grouped[type];
              if (!items || items.length === 0) return null;
              const cfg = TYPE_CONFIG[type] || TYPE_CONFIG.page;

              return (
                <div key={type}>
                  <div className="px-4 py-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                    {cfg.label}
                  </div>
                  {items.map((item) => {
                    const idx = globalIdx++;
                    const isItemActive = idx === activeIndex;
                    return (
                      <button
                        key={item.id}
                        data-active={isItemActive}
                        onClick={() => navigateTo(item)}
                        onMouseEnter={() => setActiveIndex(idx)}
                        className={
                          "w-full flex items-center gap-3 px-4 py-2.5 text-right transition-colors " +
                          (isItemActive ? "bg-blue-50" : "hover:bg-gray-50")
                        }
                      >
                        <span
                          className={
                            "shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-xs " +
                            cfg.color
                          }
                        >
                          {cfg.icon}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-800 truncate">
                            {item.title}
                          </div>
                          {item.subtitle && (
                            <div className="text-xs text-gray-400 truncate" dir="ltr">
                              {item.subtitle}
                            </div>
                          )}
                        </div>
                        {typeof item.meta?.stage === "string" && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 shrink-0">
                            {STAGE_LABELS[item.meta.stage] || item.meta.stage}
                          </span>
                        )}
                        {typeof item.meta?.segment === "string" && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 shrink-0">
                            {SEGMENT_LABELS[item.meta.segment] || item.meta.segment}
                          </span>
                        )}
                        {isItemActive && (
                          <span className="text-[10px] text-gray-300 shrink-0">↵</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>

          {/* Footer with keyboard hints */}
          <div className="flex items-center justify-between px-4 py-2 border-t border-gray-100 bg-gray-50/50 text-[10px] text-gray-400">
            <div className="flex items-center gap-3">
              <span>
                <kbd className="px-1 py-0.5 bg-white border border-gray-200 rounded text-[10px] font-mono">
                  ↑↓
                </kbd>{" "}
                ناوبری
              </span>
              <span>
                <kbd className="px-1 py-0.5 bg-white border border-gray-200 rounded text-[10px] font-mono">
                  ↵
                </kbd>{" "}
                انتخاب
              </span>
              <span>
                <kbd className="px-1 py-0.5 bg-white border border-gray-200 rounded text-[10px] font-mono">
                  Esc
                </kbd>{" "}
                بستن
              </span>
            </div>
            {results.length > 0 && (
              <span>{toPersianNum(results.length)} نتیجه</span>
            )}
          </div>
        </div>
      </div>
    </>
  );
}




