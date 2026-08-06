import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import AppShell from "@/app-shell";
import "@/app/globals.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppShell />
  </StrictMode>,
);
