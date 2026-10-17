/* Runs the Python cleaning engine (Pyodide) off the main thread.
   Messages in:  {id, type: "load"|"run"|"export", ...}
   Messages out: {id, ok, result|error}, plus {type: "status"} while the engine boots. */

// Module worker: if this import fails (offline, blocked CDN), the page's worker.onerror reports it.
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";

let web = null;

const ready = (async () => {
  const status = (text) => postMessage({ type: "status", text });
  status("Downloading the Python runtime");
  const pyodide = await loadPyodide({ indexURL: PYODIDE });
  status("Installing the cleaning engine");
  await pyodide.loadPackage("micropip");
  const manifest = await fetch(new URL("data/engine.json", self.location)).then((r) => r.json());
  const urls = manifest.wheels.map((w) => new URL("wheels/" + w, self.location).href);
  await pyodide.pyimport("micropip").install(urls);
  web = pyodide.pyimport("data_cleaner.web");
  status("ready");
})();

function lastLine(err) {
  const text = String(err && err.message || err);
  const lines = text.trim().split("\n");
  return lines[lines.length - 1].replace(/^\w+(Error|Exception): /, "");
}

self.onmessage = async (event) => {
  const { id, type } = event.data;
  try {
    await ready;
    let result;
    if (type === "load") {
      result = JSON.parse(web.load(event.data.bytes, event.data.name, event.data.sheet || null));
    } else if (type === "run") {
      result = JSON.parse(web.run(JSON.stringify(event.data.options)));
    } else if (type === "export") {
      const proxy = web.export(event.data.kind);
      result = proxy.toJs();
      proxy.destroy();
    }
    postMessage({ id, ok: true, result });
  } catch (err) {
    postMessage({ id, ok: false, error: lastLine(err) });
  }
};

ready.catch((err) => postMessage({ type: "status", text: "error", error: lastLine(err) }));
