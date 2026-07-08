import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import TraceListPage from "./pages/TraceListPage";
import TraceDetailPage from "./pages/TraceDetailPage";
import ThreadDetailPage from "./pages/ThreadDetailPage";
import StatsPage from "./pages/StatsPage";

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0">
        <Routes>
          <Route path="/" element={<TraceListPage />} />
          <Route path="/traces/:traceId" element={<TraceDetailPage />} />
          <Route path="/threads/:threadId" element={<ThreadDetailPage />} />
          <Route path="/stats" element={<StatsPage />} />
        </Routes>
      </main>
    </div>
  );
}
