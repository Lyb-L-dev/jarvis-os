"use client";

import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { AppHeader } from "@/components/app-header";
import { DesktopActivationBridge } from "@/components/desktop-activation-bridge";
import { Sidebar } from "@/components/sidebar";

const SIDEBAR_STORAGE_KEY = "jarvis:sidebar-hidden:v1";
const SIDEBAR_CHANGE_EVENT = "jarvis:sidebar-change";
let sidebarMemoryPreference = false;

const SidebarControlContext = createContext<
  ((active: boolean) => void) | null
>(null);

function subscribeToSidebarPreference(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(SIDEBAR_CHANGE_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(SIDEBAR_CHANGE_EVENT, callback);
  };
}

function getSidebarPreference() {
  try {
    const storedPreference = window.localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (storedPreference !== null) {
      sidebarMemoryPreference = storedPreference === "true";
    }
    return sidebarMemoryPreference;
  } catch {
    return sidebarMemoryPreference;
  }
}

function getServerSidebarPreference() {
  return false;
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [sidebarControlActive, setSidebarControlActive] = useState(false);
  const sidebarHidden = useSyncExternalStore(
    subscribeToSidebarPreference,
    getSidebarPreference,
    getServerSidebarPreference,
  );
  const isTabletRoute = pathname.startsWith("/tablet");
  const effectiveSidebarHidden = sidebarControlActive && sidebarHidden;

  const toggleSidebar = useCallback(() => {
    const next = !getSidebarPreference();
    sidebarMemoryPreference = next;
    try {
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(next));
    } catch {
      // The in-memory preference still supports the current browser session.
    }
    window.dispatchEvent(new Event(SIDEBAR_CHANGE_EVENT));
  }, []);

  return (
    <SidebarControlContext.Provider value={setSidebarControlActive}>
      <div
        className="app-shell"
        data-sidebar-state={effectiveSidebarHidden ? "hidden" : "visible"}
      >
        <Sidebar hidden={effectiveSidebarHidden || isTabletRoute} />
        <AppHeader
          onToggleSidebar={toggleSidebar}
          showSidebarToggle={sidebarControlActive && !isTabletRoute}
          sidebarHidden={effectiveSidebarHidden}
        />
        <DesktopActivationBridge />
        {children}
      </div>
    </SidebarControlContext.Provider>
  );
}

export function useSidebarControlRegistration() {
  const setSidebarControlActive = useContext(SidebarControlContext);

  useEffect(() => {
    if (!setSidebarControlActive) return;
    setSidebarControlActive(true);
    return () => setSidebarControlActive(false);
  }, [setSidebarControlActive]);
}
