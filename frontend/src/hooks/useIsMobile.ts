/**
 * useIsMobile — reactive hook for mobile breakpoint detection.
 *
 * Returns `true` when the viewport is below 768px (mobile layout).
 * Listens for matchMedia `change` events so the value updates on
 * resize and orientation change without a full re-render cycle.
 */

import { useEffect, useState } from "react";

const MOBILE_QUERY = "(max-width: 767px)";

export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
    const mql = window.matchMedia(MOBILE_QUERY);
    return mql ? mql.matches : false;
  });

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia(MOBILE_QUERY);
    if (!mql) return;
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mql.addEventListener("change", handler);
    setIsMobile(mql.matches);
    return () => mql.removeEventListener("change", handler);
  }, []);

  return isMobile;
}
