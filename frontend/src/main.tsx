import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth";
import { ToastProvider } from "./ui";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><HashRouter><ToastProvider><AuthProvider><App /></AuthProvider></ToastProvider></HashRouter></React.StrictMode>);
if ("serviceWorker" in navigator && import.meta.env.PROD) window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
