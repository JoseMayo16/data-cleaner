(function () {
  "use strict";

  var KINDS = [
    ["email", "Email"], ["phone", "Phone"], ["date", "Date"], ["number", "Number"],
    ["name", "Person name"], ["category", "Category"], ["id", "ID (trim only)"], ["text", "Text (trim only)"],
  ];
  var RULES = {
    whitespace: "Extra spaces removed",
    empty_value: "Placeholders emptied (N/A, -, null)",
    email_format: "Emails lowercased and trimmed",
    email_domain_typo: "Email domain typos fixed",
    phone_format: "Phones in international format",
    date_format: "Dates as YYYY-MM-DD",
    number_format: "Numbers without symbols or separators",
    name_case: "Names capitalized",
    category_variant: "Spelling variants merged",
    duplicate_row: "Duplicate rows removed",
  };
  var LIST_LIMIT = 500;
  var SAMPLE_OPTIONS = {
    "sales-orders.xlsx": { country: "US", people: false },
    "crm-contacts.csv": { country: "CO", people: true },
  };

  var file = null;      // {bytes, name}
  var loaded = null;    // profile from the engine
  var result = null;    // cleaning report

  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    for (var k in attrs || {}) {
      if (k === "text") n.textContent = attrs[k];
      else if (k === "class") n.className = attrs[k];
      else n.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c != null) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function fmt(n) { return n.toLocaleString("en-US"); }

  // --- engine (Pyodide in a worker) ------------------------------------------------------

  var worker = new Worker("worker.js", { type: "module" });
  var pending = {}, nextId = 1;

  worker.onerror = function (e) {
    e.preventDefault();
    engineStatus({ text: "error", error: "could not download Pyodide from cdn.jsdelivr.net. Check the connection or any content blocker." });
  };

  worker.onmessage = function (e) {
    var m = e.data;
    if (m.type === "status") return engineStatus(m);
    var p = pending[m.id];
    delete pending[m.id];
    if (m.ok) p.resolve(m.result); else p.reject(new Error(m.error));
  };

  function call(msg, transfer) {
    return new Promise(function (resolve, reject) {
      msg.id = nextId++;
      pending[msg.id] = { resolve: resolve, reject: reject };
      worker.postMessage(msg, transfer || []);
    });
  }

  function engineStatus(m) {
    var pill = $("engine"), label = pill.querySelector("span");
    pill.classList.remove("ready", "failed");
    if (m.text === "ready") { pill.classList.add("ready"); label.textContent = "Engine ready, runs in your browser"; }
    else if (m.text === "error") { pill.classList.add("failed"); label.textContent = "Engine failed to load"; showLoadError("The Python engine could not load: " + m.error); }
    else label.textContent = m.text + "…";
  }

  // --- progress in the toolbar ----------------------------------------------------------

  function setStep(n) {
    [1, 2, 3].forEach(function (i) {
      var li = $("step-" + i);
      li.classList.toggle("is-current", i === n);
      li.classList.toggle("is-done", i < n);
    });
  }

  // --- step 1: load ----------------------------------------------------------------------

  function showLoadError(text) { $("load-error").textContent = text; $("load-error").hidden = !text; }

  function loadBytes(bytes, name, sheet) {
    showLoadError("");
    file = { bytes: bytes, name: name };
    $("drop").classList.add("busy");
    return call({ type: "load", bytes: bytes.slice(), name: name, sheet: sheet || null })
      .then(function (profile) { loaded = profile; renderReview(sheet); })
      .catch(function (err) { showLoadError(err.message); })
      .then(function () { $("drop").classList.remove("busy"); });
  }

  function readFile(f) {
    f.arrayBuffer().then(function (buf) {
      setOptions({ country: "CO", people: true });
      loadBytes(new Uint8Array(buf), f.name);
    });
  }

  function setOptions(o) {
    $("opt-country").value = o.country;
    $("opt-people").checked = o.people;
  }

  $("pick").addEventListener("click", function () { $("file").click(); });
  $("file").addEventListener("change", function () { if (this.files[0]) readFile(this.files[0]); this.value = ""; });
  var drop = $("drop");
  ["dragenter", "dragover"].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add("over"); }); });
  ["dragleave", "drop"].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.remove("over"); }); });
  drop.addEventListener("drop", function (e) { if (e.dataTransfer.files[0]) readFile(e.dataTransfer.files[0]); });

  function openSample(name) {
    return fetch("samples/" + name).then(function (r) { return r.arrayBuffer(); }).then(function (buf) {
      setOptions(SAMPLE_OPTIONS[name]);
      return loadBytes(new Uint8Array(buf), name);
    });
  }

  document.querySelectorAll("[data-sample]").forEach(function (b) {
    b.addEventListener("click", function () { openSample(b.dataset.sample); });
  });

  // --- step 2: review ----------------------------------------------------------------------

  function renderReview(sheet) {
    $("review").hidden = false;
    $("results").hidden = true;
    $("review-title").textContent = fmt(loaded.columns.length) + " columns, " + fmt(loaded.rows) + " rows";
    $("file-name").textContent = file.name;
    $("file-name").hidden = false;
    setStep(2);

    var wrap = $("sheet-wrap"), select = $("sheet");
    wrap.hidden = loaded.sheets.length < 2;
    select.replaceChildren.apply(select, loaded.sheets.map(function (s) { return el("option", { value: s, text: s }); }));
    if (sheet) select.value = sheet;

    var head = el("thead", {}, [el("tr", {}, ["Column", "Type", "Filled", "Examples"].map(function (h) { return el("th", { text: h }); }))]);
    var body = el("tbody", {}, loaded.columns.map(function (c) {
      var sel = el("select", { "data-column": c.name, "aria-label": "Type of " + c.name });
      KINDS.forEach(function (k) { sel.appendChild(el("option", { value: k[0], text: k[1] })); });
      sel.value = c.kind;
      return el("tr", {}, [
        el("td", { text: c.name }), el("td", {}, [sel]),
        el("td", { class: "num", text: Math.round(100 * c.filled / Math.max(1, loaded.rows)) + "%" }),
        el("td", { class: "ex", text: c.examples.join("  ·  ") }),
      ]);
    }));
    $("columns").replaceChildren(head, body);
    $("review").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  $("sheet").addEventListener("change", function () { loadBytes(file.bytes, file.name, this.value); });
  $("reset").addEventListener("click", function () {
    $("review").hidden = true; $("results").hidden = true;
    $("file-name").hidden = true;
    setStep(1);
    $("start").scrollIntoView({ behavior: "smooth" });
  });

  function options() {
    var kinds = {};
    document.querySelectorAll("#columns select[data-column]").forEach(function (s) { kinds[s.dataset.column] = s.value; });
    return {
      country: $("opt-country").value, date_order: $("opt-dates").value, duplicates: $("opt-dups").value,
      flag_shared_contacts: $("opt-people").checked, fix_names: $("opt-names").checked,
      merge_categories: $("opt-cats").checked, fix_email_typos: $("opt-typos").checked, kinds: kinds,
    };
  }

  $("run").addEventListener("click", function () {
    var btn = this;
    btn.disabled = true;
    btn.textContent = "Cleaning…";
    call({ type: "run", options: options() })
      .then(function (r) { result = r; renderResults(); })
      .catch(function (err) { alert("Cleaning failed: " + err.message); })
      .then(function () { btn.disabled = false; btn.textContent = "Clean data"; });
  });

  // --- step 3: results ---------------------------------------------------------------------

  function tile(label, value, sub) {
    return el("div", { class: "stat" }, [el("div", { class: "stat-value", text: value }),
      el("div", { class: "stat-label", text: label }), el("div", { class: "stat-sub", text: sub })]);
  }

  function cleanShare(r) {
    // Never round a file with open issues up to 100%.
    if (!r.issues.length) return "100%";
    var share = 100 * (1 - r.issues.length / Math.max(1, r.rows_out * r.columns.length));
    return (Math.floor(share * 10) / 10).toFixed(1) + "%";
  }

  function renderResults() {
    var r = result;
    $("results").hidden = false;
    setStep(3);
    var touched = r.columns.filter(function (c) { return c.changed; }).length;
    $("kpis").replaceChildren(
      tile("Rows", fmt(r.rows_in) + " → " + fmt(r.rows_out), r.duplicates.length + " duplicates " + ($("opt-dups").value === "remove" ? "removed" : "found")),
      tile("Cells fixed", fmt(r.changes.length), "in " + touched + " of " + r.columns.length + " columns"),
      tile("Need review", fmt(r.issues.length), "values that could not be fixed safely"),
      tile("Clean cells", cleanShare(r), "of the output has no open issue")
    );

    var counts = r.rule_counts, keys = Object.keys(counts);
    var max = Math.max.apply(null, keys.map(function (k) { return counts[k]; }).concat([1]));
    $("rules").replaceChildren.apply($("rules"), keys.length ? keys.map(function (k) {
      var bar = el("span");
      bar.style.width = "calc((100% - 56px) * " + (counts[k] / max).toFixed(3) + ")";
      return el("div", { class: "rule" }, [el("span", { text: RULES[k] || k }), el("div", { class: "rule-bar" }, [bar, el("b", { text: fmt(counts[k]) })])]);
    }) : [el("p", { class: "muted", text: "Nothing needed fixing." })]);

    $("n-changes").textContent = fmt(r.changes.length);
    $("n-issues").textContent = fmt(r.issues.length);
    renderData();
    renderChanges("");
    renderIssues();
    selectTab("data");
    $("results").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderData() {
    var r = result, changed = {}, flagged = {};
    r.changes.forEach(function (c) { changed[c.row + "|" + c.column] = c; });
    r.issues.forEach(function (i) { flagged[i.row + "|" + i.column] = i; });

    var head = el("thead", {}, [el("tr", {}, [el("th", { text: "Row" })].concat(r.header.map(function (h) { return el("th", { text: h }); })))]);
    var body = el("tbody", {}, r.preview.map(function (row, i) {
      var src = r.source_rows[i];
      return el("tr", {}, [el("td", { class: "row", text: String(src) })].concat(row.map(function (v, c) {
        var key = src + "|" + r.header[c], td = el("td", { text: v });
        var notes = [];
        if (changed[key]) { td.classList.add("changed"); notes.push("Was: " + (changed[key].before || "(empty)")); }
        if (flagged[key]) { td.classList.add("flagged"); notes.push(flagged[key].problem); }
        if (notes.length) td.title = notes.join("\n");
        return td;
      })));
    }));
    var legend = el("div", { class: "legend" }, [
      el("span", {}, [el("i", { class: "l-changed" }), "Changed (hover to see the original)"]),
      el("span", {}, [el("i", { class: "l-flagged" }), "Needs review"]),
    ]);
    var note = r.rows_out > r.preview.length ? el("p", { class: "note", text: "Showing the first " + r.preview.length + " of " + fmt(r.rows_out) + " rows. The download has all of them." }) : null;
    $("tab-data").replaceChildren(legend, el("div", { class: "table-wrap" }, [el("table", { class: "grid" }, [head, body])]), note || "");
  }

  function renderChanges(rule) {
    var list = result.changes.filter(function (c) { return !rule || c.rules.indexOf(rule) >= 0; });
    var select = el("select", { "aria-label": "Filter changes by rule" }, [el("option", { value: "", text: "All rules" })]
      .concat(Object.keys(result.rule_counts).filter(function (k) { return k !== "duplicate_row"; }).map(function (k) { return el("option", { value: k, text: RULES[k] || k }); })));
    select.value = rule;
    select.addEventListener("change", function () { renderChanges(select.value); });
    var rows = list.slice(0, LIST_LIMIT).map(function (c) {
      return el("tr", {}, [el("td", { class: "num", text: String(c.row) }), el("td", { text: c.column }),
        el("td", {}, [el("span", { class: "before", text: c.before || "(empty)" })]),
        el("td", {}, [el("span", { class: "after", text: c.after || "(empty)" })]),
        el("td", {}, c.rules.map(function (k) { return el("span", { class: "tag", text: k }); }))]);
    });
    var dups = rule ? [] : result.duplicates.slice(0, LIST_LIMIT).map(function (d) {
      return el("tr", {}, [el("td", { class: "num", text: String(d.row) }), el("td", { text: "(whole row)" }),
        el("td", {}, [el("span", { class: "before", text: "duplicate of row " + d.duplicate_of })]),
        el("td", { text: $("opt-dups").value === "remove" ? "removed" : "kept" }), el("td", {}, [el("span", { class: "tag", text: "duplicate_row" })])]);
    });
    $("tab-changes").replaceChildren(
      el("label", { class: "filter" }, ["Show", select]),
      el("div", { class: "table-wrap" }, [el("table", {}, [
        el("thead", {}, [el("tr", {}, ["Row", "Column", "Before", "After", "Rule"].map(function (h) { return el("th", { text: h }); }))]),
        el("tbody", {}, rows.concat(dups)),
      ])]),
      list.length > LIST_LIMIT ? el("p", { class: "note", text: "Showing " + LIST_LIMIT + " of " + fmt(list.length) + ". The Excel download lists every change." }) : ""
    );
  }

  function renderIssues() {
    var list = result.issues;
    if (!list.length) { $("tab-issues").replaceChildren(el("p", { class: "muted", text: "Nothing needs review." })); return; }
    $("tab-issues").replaceChildren(
      el("div", { class: "table-wrap" }, [el("table", {}, [
        el("thead", {}, [el("tr", {}, ["Row", "Column", "Value", "Problem"].map(function (h) { return el("th", { text: h }); }))]),
        el("tbody", {}, list.slice(0, LIST_LIMIT).map(function (i) {
          return el("tr", {}, [el("td", { class: "num", text: String(i.row) }), el("td", { text: i.column || "(whole row)" }),
            el("td", {}, [el("span", { class: "after", text: i.value || "" })]), el("td", { text: i.problem })]);
        })),
      ])]),
      list.length > LIST_LIMIT ? el("p", { class: "note", text: "Showing " + LIST_LIMIT + " of " + fmt(list.length) + "." }) : ""
    );
  }

  function selectTab(name) {
    document.querySelectorAll("[data-tab]").forEach(function (b) { b.setAttribute("aria-selected", String(b.dataset.tab === name)); });
    ["data", "changes", "issues"].forEach(function (t) { $("tab-" + t).hidden = t !== name; });
  }
  document.querySelectorAll("[data-tab]").forEach(function (b) { b.addEventListener("click", function () { selectTab(b.dataset.tab); }); });

  // --- downloads -----------------------------------------------------------------------------

  var EXPORTS = {
    xlsx: ["-clean.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    csv: ["-clean.csv", "text/csv"],
    report: ["-audit.json", "application/json"],
  };
  document.querySelectorAll("[data-export]").forEach(function (b) {
    b.addEventListener("click", function () {
      var kind = b.dataset.export, spec = EXPORTS[kind];
      call({ type: "export", kind: kind }).then(function (bytes) {
        var url = URL.createObjectURL(new Blob([bytes], { type: spec[1] }));
        var a = el("a", { href: url, download: file.name.replace(/\.[^.]+$/, "") + spec[0] });
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      }).catch(function (err) { alert("Export failed: " + err.message); });
    });
  });

  // Shareable demo links: ?sample=crm-contacts.csv opens a sample, &run=1 also cleans it.
  var params = new URLSearchParams(location.search);
  if (SAMPLE_OPTIONS[params.get("sample")]) {
    openSample(params.get("sample")).then(function () {
      if (params.get("run") === "1" && loaded) $("run").click();
    });
  }

  $("theme").addEventListener("click", function () {
    var root = document.documentElement;
    var cur = root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    root.dataset.theme = cur === "dark" ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch (e) {}
  });
})();
