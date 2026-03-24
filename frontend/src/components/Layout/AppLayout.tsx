/**
 * T074 — AppLayout
 *
 * Responsive layout shell with NavBar. Wraps page content.
 */

import { Outlet } from "react-router-dom";
import NavBar from "./NavBar";

export default function AppLayout() {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      <NavBar />
      <main style={{ flex: 1, position: "relative", overflow: "auto" }}>
        <Outlet />
      </main>
    </div>
  );
}
