import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/app.css";

import App from "./App";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Unable to find the root DOM element.");
}

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
