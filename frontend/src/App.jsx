import React, { useEffect, useState } from 'react';
import { api } from './api.js';
import { Caps } from './components.jsx';
import Dashboard from './pages/Dashboard.jsx';
import FoodScan from './pages/FoodScan.jsx';
import Freshness from './pages/Freshness.jsx';
import Hygiene from './pages/Hygiene.jsx';
import Cooking from './pages/Cooking.jsx';
import Planner from './pages/Planner.jsx';

const TABS = [
  ['dashboard', 'Dashboard', Dashboard],
  ['food', 'Food Scan', FoodScan],
  ['freshness', 'Freshness', Freshness],
  ['hygiene', 'Kitchen Hygiene', Hygiene],
  ['cooking', 'Smart Cooking', Cooking],
  ['planner', 'Meal Planner', Planner],
];

export default function App() {
  const [tab, setTab] = useState(() => {
    const h = typeof location !== 'undefined' ? location.hash.slice(1) : '';
    return TABS.some((t) => t[0] === h) ? h : 'dashboard';
  });
  const [caps, setCaps] = useState({ ai_configured: true, server_audio: false, offline: false });

  useEffect(() => {
    api.health().then(setCaps).catch(() => setCaps({ ai_configured: false, server_audio: false, offline: true }));
  }, []);

  const go = (t) => {
    setTab(t);
    if (typeof window !== 'undefined') {
      history.replaceState(null, '', `#${t}`);
      window.scrollTo(0, 0);
    }
  };
  const Page = TABS.find((t) => t[0] === tab)[2];

  return (
    <Caps.Provider value={caps}>
      <div className="shell">
        <aside className="side">
          <div className="brand">
            Food<span>Verse</span> AI
          </div>
          <nav role="tablist" aria-label="Modules">
            {TABS.map(([k, label]) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => go(k)}>
                {label}
              </button>
            ))}
          </nav>
        </aside>
        <main className="main">
          {caps.offline && (
            <p className="banner bad">The backend is not reachable. Start it with: uvicorn app.main:app --port 8000</p>
          )}
          {!caps.offline && !caps.ai_configured && (
            <p className="banner warn">
              ANTHROPIC_API_KEY is not set on the server. Add it to backend/.env and restart to enable analysis.
            </p>
          )}
          <Page go={go} />
        </main>
      </div>
    </Caps.Provider>
  );
}
