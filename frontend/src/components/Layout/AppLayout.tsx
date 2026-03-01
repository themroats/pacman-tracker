/**
 * T074 — AppLayout
 *
 * Responsive layout shell with NavBar. Wraps page content.
 */

import React from "react";
import { Outlet } from "react-router-dom";
import NavBar from "./NavBar";

export default function AppLayout() {
  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <NavBar />
      <main style={{ flex: 1, position: "relative" }}>
        <Outlet />
      </main>
    </div>
  );
}
