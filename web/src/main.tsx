import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import ChatApp from "./ChatApp";
import "./index.css";

// Run 14: the chat is the product. The classic single-question view is kept at
// ?view=classic because the smoke suite and the print/passport flows still use it.
const classic = new URLSearchParams(window.location.search).get("view") === "classic";

createRoot(document.getElementById("root")!).render(
  <StrictMode>{classic ? <App /> : <ChatApp />}</StrictMode>,
);
