import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/layout/Layout";
import ConditionsPage from "./pages/ConditionsPage";
import SimulatorPage from "./pages/SimulatorPage";
import CorrelationPage from "./pages/CorrelationPage";
import SahmPage from "./pages/SahmPage";
import LineagePage from "./pages/LineagePage";
import OverviewPage from "./pages/OverviewPage";
import RecessionPage from "./pages/RecessionPage";
import RegimesPage from "./pages/RegimesPage";
import SeriesPage from "./pages/SeriesPage";
import TaylorPage from "./pages/TaylorPage";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: 1 } },
});

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<OverviewPage />} />
            <Route path="series/:id" element={<SeriesPage />} />
            <Route path="lineage" element={<LineagePage />} />
            <Route path="recession" element={<RecessionPage />} />
            <Route path="correlation" element={<CorrelationPage />} />
            <Route path="regimes" element={<RegimesPage />} />
            <Route path="taylor" element={<TaylorPage />} />
            <Route path="sahm" element={<SahmPage />} />
            <Route path="conditions" element={<ConditionsPage />} />
            <Route path="simulator" element={<SimulatorPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
