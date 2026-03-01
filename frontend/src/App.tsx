/**
 * Root application component with React Router.
 */

import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppLayout from "@/components/Layout/AppLayout";
import HomePage from "@/pages/HomePage";
import MapPage from "@/pages/MapPage";
import CoveragePage from "@/pages/CoveragePage";
import RoutePage from "@/pages/RoutePage";
import ProgressPage from "@/pages/ProgressPage";
import AuthCallbackPage from "@/pages/AuthCallbackPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Auth callback — no layout */}
        <Route path="/auth/callback" element={<AuthCallbackPage />} />

        {/* All other pages share the NavBar layout */}
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/coverage" element={<CoveragePage />} />
          <Route path="/route" element={<RoutePage />} />
          <Route path="/progress" element={<ProgressPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
