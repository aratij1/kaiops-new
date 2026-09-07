import { useEffect, useState } from "react";

export function entryScript(document: Document): string | null {
  return document.querySelector<HTMLScriptElement>('script[type="module"][src]')?.getAttribute("src") || null;
}

export default function UiUpdateNotice() {
  const [available, setAvailable] = useState(false);
  useEffect(() => {
    const loadedEntry = entryScript(document);
    if (!loadedEntry || import.meta.env.DEV) return;
    const controller = new AbortController();
    let checking = false;
    const check = async () => {
      if (checking || controller.signal.aborted) return;
      checking = true;
      try {
        const response = await fetch("/index.html", { cache: "no-store", signal: controller.signal });
        if (!response.ok) return;
        const latestEntry = entryScript(new DOMParser().parseFromString(await response.text(), "text/html"));
        if (latestEntry && latestEntry !== loadedEntry && !controller.signal.aborted) setAvailable(true);
      } catch { /* Keep the current workspace usable while offline. */ }
      finally { checking = false; }
    };
    void check();
    const timer = window.setInterval(() => void check(), 60000);
    const onFocus = () => void check();
    window.addEventListener("focus", onFocus);
    return () => { controller.abort(); window.clearInterval(timer); window.removeEventListener("focus", onFocus); };
  }, []);
  return available ? <div role="status" className="ui-update-notice"><span>An updated KaiMS page is available. Save any draft before reloading.</span><button type="button" onClick={() => window.location.reload()}>Load updated page</button></div> : null;
}
