import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { setApiErrorHandler } from "./api/client";
import { useAppStore } from "./store";

// Wire global API errors to toast notifications
setApiErrorHandler((error) => {
  useAppStore.getState().addToast(error.message, "error");
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
