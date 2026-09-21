/*
 * Resdex form recorder — paste into DevTools console on resdex.naukri.com
 * (advanced search page), then fill the form BY HAND, normally.
 *
 * Records a structured trace of what a human does and what the page shows:
 *   - every click / focus / input / change / Enter / Tab / Escape, with a CSS path,
 *     element attributes (name, placeholder, role, aria-*), and current value
 *   - every dropdown/listbox that appears (role=listbox|option, aria-owns targets,
 *     class~=dropdown|suggest|option|menu), with its option texts and outerHTML
 *   - a form-state snapshot (all visible inputs/selects + chips) after each action
 *
 * Finish with:  __snyRec.download()   -> saves resdex_trace_<time>.json
 * Other:        __snyRec.stop()  __snyRec.events (live array)  __snyRec.summary()
 *
 * Then give that JSON (or `__snyRec.summary()` output) to Claude to write the
 * fill logic from what the page actually does, instead of guessing selectors.
 */
(() => {
  if (window.__snyRec) { window.__snyRec.stop(); }

  const t0 = Date.now();
  const events = [];
  const MAX_HTML = 1500;
  const seenListboxes = new WeakSet();

  const cssPath = (el) => {
    if (!el || el.nodeType !== 1) return null;
    const parts = [];
    while (el && el.nodeType === 1 && parts.length < 6) {
      let p = el.tagName.toLowerCase();
      if (el.id) { p += `#${CSS.escape(el.id)}`; parts.unshift(p); break; }
      const cls = (el.className && el.className.toString().trim().split(/\s+/).slice(0, 2)) || [];
      if (cls.length && cls[0]) p += "." + cls.map((c) => CSS.escape(c)).join(".");
      parts.unshift(p);
      el = el.parentElement;
    }
    return parts.join(" > ");
  };

  const describe = (el) => {
    if (!el || el.nodeType !== 1) return null;
    const a = (n) => el.getAttribute(n);
    return {
      path: cssPath(el),
      tag: el.tagName.toLowerCase(),
      id: el.id || null,
      name: a("name"),
      type: a("type"),
      placeholder: a("placeholder"),
      role: a("role"),
      ariaLabel: a("aria-label"),
      ariaOwns: a("aria-owns") || a("aria-controls"),
      ariaExpanded: a("aria-expanded"),
      cls: el.className && el.className.toString().slice(0, 120),
      text: (el.textContent || "").trim().slice(0, 100),
      value: "value" in el ? el.value : undefined,
    };
  };

  const formSnapshot = () => {
    const fields = Array.from(document.querySelectorAll("input, select, textarea"))
      .filter((e) => e.offsetParent !== null && e.type !== "hidden")
      .map((e) => ({
        name: e.name || null, id: e.id || null, placeholder: e.placeholder || null,
        type: e.type, value: e.value, checked: e.checked,
      }));
    const chips = Array.from(document.querySelectorAll(
      "[class*='chip'], [class*='pill'], [class*='tag']"
    )).filter((e) => e.offsetParent !== null)
      .map((e) => (e.textContent || "").trim())
      .filter((t) => t && t.length < 60);
    return { fields, chips: [...new Set(chips)] };
  };

  const push = (type, data) => {
    events.push({ t: Date.now() - t0, type, ...data });
  };

  const isListboxLike = (el) => {
    if (!el || el.nodeType !== 1) return false;
    const role = el.getAttribute("role");
    if (role === "listbox" || role === "option" || role === "menu") return true;
    const cls = (el.className && el.className.toString()) || "";
    return /dropdown|suggest|option|sug-|menu|listbox|autocomplete/i.test(cls);
  };

  const captureListbox = (el, reason) => {
    if (seenListboxes.has(el)) return;
    const optionEls = el.matches("[role='option'], li")
      ? [el]
      : Array.from(el.querySelectorAll("[role='option'], li"));
    const options = optionEls.map((o) => (o.textContent || "").trim()).filter(Boolean);
    if (options.length === 0 && (el.textContent || "").trim().length === 0) return;
    seenListboxes.add(el);
    push("dropdown_appeared", {
      reason,
      container: describe(el),
      optionCount: options.length,
      options: options.slice(0, 40),
      html: el.outerHTML.slice(0, MAX_HTML),
    });
  };

  const mo = new MutationObserver((muts) => {
    for (const m of muts) {
      for (const n of m.addedNodes) {
        if (n.nodeType !== 1) continue;
        if (isListboxLike(n)) captureListbox(n, "added-node");
        n.querySelectorAll && n.querySelectorAll("[role='listbox'], [role='option']").forEach(
          (c) => captureListbox(c.closest("[role='listbox']") || c, "added-descendant")
        );
      }
      if (m.type === "attributes" && m.attributeName === "aria-expanded" &&
          m.target.getAttribute("aria-expanded") === "true") {
        const id = m.target.getAttribute("aria-owns") || m.target.getAttribute("aria-controls");
        const lb = id && document.getElementById(id);
        push("combobox_expanded", { input: describe(m.target), listboxFound: !!lb });
        if (lb) setTimeout(() => captureListbox(lb, "aria-owns-after-expand"), 250);
      }
    }
  });
  mo.observe(document.documentElement, {
    childList: true, subtree: true, attributes: true, attributeFilter: ["aria-expanded"],
  });

  const snapSoon = (() => {
    let timer = null;
    return () => {
      clearTimeout(timer);
      timer = setTimeout(() => push("form_state", formSnapshot()), 500);
    };
  })();

  const onClick = (e) => { push("click", { target: describe(e.target) }); snapSoon(); };
  const onFocus = (e) => { push("focus", { target: describe(e.target) }); };
  const onInput = (e) => { push("input", { target: describe(e.target) }); };
  const onChange = (e) => { push("change", { target: describe(e.target) }); snapSoon(); };
  const onKey = (e) => {
    if (["Enter", "Tab", "Escape", "ArrowDown", "ArrowUp", ","].includes(e.key)) {
      push("key", { key: e.key, target: describe(e.target) });
      snapSoon();
    }
  };
  const onNav = () => push("navigation", { url: location.href });

  document.addEventListener("click", onClick, true);
  document.addEventListener("focusin", onFocus, true);
  document.addEventListener("input", onInput, true);
  document.addEventListener("change", onChange, true);
  document.addEventListener("keydown", onKey, true);
  window.addEventListener("beforeunload", onNav);

  push("start", { url: location.href, ua: navigator.userAgent });
  push("form_state", formSnapshot());

  const summary = () => {
    const lines = [];
    for (const ev of events) {
      const sec = (ev.t / 1000).toFixed(1).padStart(6);
      if (ev.type === "click") lines.push(`${sec}s CLICK   ${ev.target?.tag} "${ev.target?.text}" ${ev.target?.path}`);
      else if (ev.type === "input") lines.push(`${sec}s INPUT   ${ev.target?.name || ev.target?.placeholder || ev.target?.path} = "${ev.target?.value}"`);
      else if (ev.type === "key") lines.push(`${sec}s KEY     ${ev.key} in ${ev.target?.name || ev.target?.placeholder || ev.target?.path}`);
      else if (ev.type === "combobox_expanded") lines.push(`${sec}s OPEN    combobox ${ev.input?.name || ev.input?.placeholder} aria-owns=${ev.input?.ariaOwns} found=${ev.listboxFound}`);
      else if (ev.type === "dropdown_appeared") lines.push(`${sec}s OPTIONS (${ev.optionCount}) ${JSON.stringify(ev.options.slice(0, 12))}  in ${ev.container?.path}`);
      else if (ev.type === "form_state") lines.push(`${sec}s STATE   chips=${JSON.stringify(ev.chips)} filled=${JSON.stringify(ev.fields.filter((f) => f.value || f.checked).map((f) => `${f.name || f.placeholder}=${f.value || f.checked}`))}`);
      else if (ev.type === "navigation") lines.push(`${sec}s NAV     ${ev.url}`);
    }
    const out = lines.join("\n");
    console.log(out);
    return out;
  };

  const download = () => {
    const blob = new Blob([JSON.stringify({ events, summary: summary() }, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `resdex_trace_${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
    a.click();
  };

  const stop = () => {
    mo.disconnect();
    document.removeEventListener("click", onClick, true);
    document.removeEventListener("focusin", onFocus, true);
    document.removeEventListener("input", onInput, true);
    document.removeEventListener("change", onChange, true);
    document.removeEventListener("keydown", onKey, true);
    window.removeEventListener("beforeunload", onNav);
    push("stop", {});
  };

  window.__snyRec = { events, summary, download, stop };
  console.log("[SnyRec] recording. Fill the form by hand, then run __snyRec.download()");
})();
