import { useEffect, useState } from "react";
import {
  Activity,
  Bell,
  ChevronDown,
  RefreshCw,
} from "lucide-react";

import Sidebar, { MenuButton } from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Home from "./pages/Home";
import type { ModuleKey } from "./types";
import { loadBackendData, dataReady } from "./services/data";

export default function App() {
  const [active, setActive] = useState<ModuleKey>("overview");
  const [showHome, setShowHome] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const [ready, setReady] = useState(dataReady);
  const [reload, setReload] = useState(0);

  // Update the clock every second.
  useEffect(() => {
    const id = window.setInterval(() => {
      setNow(new Date());
    }, 1000);

    return () => window.clearInterval(id);
  }, []);

  // Load backend data and refresh it when requested.
  useEffect(() => {
    let mounted = true;

    loadBackendData().finally(() => {
      if (mounted) {
        setReady(dataReady);
      }
    });

    return () => {
      mounted = false;
    };
  }, [reload]);

  // Show the homepage before the dashboard.
  if (showHome) {
    return <Home onEnterDashboard={() => setShowHome(false)} />;
  }

  // Existing dashboard.
  return (
    <div className="app-shell">
      <Sidebar
        active={active}
        onSelect={setActive}
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        live={ready}
      />

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <MenuButton onClick={() => setMenuOpen(true)} />

            <span className="breadcrumb">
              SYS <b>/</b> WAREHOUSE CORE <b>/</b>{" "}
              <strong>{active.toUpperCase()}</strong>
            </span>
          </div>

          <div className="topbar-right">
            <span className="clock">
              <Activity size={14} />
              {now.toLocaleTimeString("en-GB")}
            </span>

            <span className="top-status">
              <i />
              {ready ? "LIVE PIPELINE" : "DEMO / OFFLINE"}
            </span>

            <button
              className="icon-button"
              title="Refresh pipeline data"
              onClick={() => setReload((x) => x + 1)}
            >
              <RefreshCw size={16} />
            </button>

            <button className="icon-button" title="Notifications">
              <Bell size={16} />
            </button>

            <button className="user-chip">
              <span>SC</span> OPERATOR <ChevronDown size={13} />
            </button>
          </div>
        </header>

        <div className="page-content">
          <Dashboard active={active} />
        </div>
      </main>
    </div>
  );
}
