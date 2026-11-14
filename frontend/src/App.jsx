import { useEffect, useState } from "react";
import { AppProvider } from "./store";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import Overview from "./pages/Overview";
import Recommendations from "./pages/Recommendations";
import InventoryInsights from "./pages/InventoryInsights";
import BudgetPlanner from "./pages/BudgetPlanner";
import PurchasePlan from "./pages/PurchasePlan";
import Assistant from "./pages/Assistant";

const NAV = [
  { id: "overview", label: "Overview" },
  { id: "recommendations", label: "Recommendations" },
  { id: "insights", label: "Inventory Insights" },
  { id: "budget", label: "Budget Planner" },
  { id: "plan", label: "Purchase Plan" },
  { id: "assistant", label: "Ask DukaanPulse" },
];

const TITLES = Object.fromEntries(NAV.map((n) => [n.id, n.label]));
const IDS = new Set(NAV.map((n) => n.id));

function initialPage() {
  const h = (typeof window !== "undefined" ? window.location.hash : "").replace("#", "");
  return IDS.has(h) ? h : "overview";
}

function Shell() {
  const [page, setPage] = useState(initialPage);
  const [navParam, setNavParam] = useState(null);
  const [drawer, setDrawer] = useState(false);

  useEffect(() => {
    const onHash = () => {
      const h = window.location.hash.replace("#", "");
      if (IDS.has(h)) setPage(h);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function navigate(next, param) {
    setPage(next);
    setNavParam(param || null);
    if (window.location.hash.replace("#", "") !== next) window.location.hash = next;
    window.scrollTo({ top: 0 });
  }

  const Page =
    {
      overview: Overview,
      recommendations: Recommendations,
      insights: InventoryInsights,
      budget: BudgetPlanner,
      plan: PurchasePlan,
      assistant: Assistant,
    }[page] || Overview;

  return (
    <div className="app">
      <Sidebar
        items={NAV}
        active={page}
        onNavigate={navigate}
        open={drawer}
        onClose={() => setDrawer(false)}
      />
      <div className="main">
        <Header title={TITLES[page]} onMenu={() => setDrawer(true)} />
        <main className="content">
          <Page onNavigate={navigate} navParam={navParam} />
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
