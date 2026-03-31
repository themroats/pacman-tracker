/**
 * Root application component with React Router.
 */

import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppLayout from "@/components/Layout/AppLayout";
import ToastContainer from "@/components/common/ToastContainer";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import HomePage from "@/pages/HomePage";
import MapPage from "@/pages/MapPage";
import CoveragePage from "@/pages/CoveragePage";
import RoutePage from "@/pages/RoutePage";
import ProfilePage from "@/pages/ProfilePage";
import ActivityDetailPage from "@/pages/ActivityDetailPage";
import AuthCallbackPage from "@/pages/AuthCallbackPage";

function App() {
  return (
    <>
      <ErrorBoundary>
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
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/profile/activity/:id" element={<ActivityDetailPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ErrorBoundary>
      <ToastContainer />
    </>
  );
}
export default App;
