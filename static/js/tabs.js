(() => {
  const roots = document.querySelectorAll("[data-tabs]");
  if (!roots.length) return;

  const activate = (tabs, panelByKey, key, moveFocus) => {
    tabs.forEach((tab) => {
      const on = tab.dataset.tab === key;
      tab.classList.toggle("is-active", on);
      tab.setAttribute("aria-selected", String(on));
      tab.tabIndex = on ? 0 : -1;
      if (on && moveFocus) tab.focus();
    });
    Object.entries(panelByKey).forEach(([k, panel]) => {
      panel.hidden = k !== key;
    });
    const url = new URL(window.location.href);
    url.searchParams.set("tab", key);
    history.replaceState(null, "", url);
  };

  roots.forEach((root) => {
    const tabs = [...root.querySelectorAll("[role='tab']")];
    if (!tabs.length) return;
    const panelByKey = {};
    tabs.forEach((tab) => {
      const panel = document.getElementById(tab.getAttribute("aria-controls"));
      if (panel) panelByKey[tab.dataset.tab] = panel;
    });

    const current = tabs.find((tab) => tab.classList.contains("is-active")) || tabs[0];

    root.addEventListener("click", (e) => {
      const tab = e.target.closest("[role='tab']");
      if (tab && root.contains(tab)) activate(tabs, panelByKey, tab.dataset.tab, false);
    });

    root.addEventListener("keydown", (e) => {
      const i = tabs.indexOf(document.activeElement);
      if (i === -1) return;
      let next = null;
      if (e.key === "ArrowRight") next = tabs[(i + 1) % tabs.length];
      else if (e.key === "ArrowLeft") next = tabs[(i - 1 + tabs.length) % tabs.length];
      else if (e.key === "Home") next = tabs[0];
      else if (e.key === "End") next = tabs[tabs.length - 1];
      if (!next) return;
      e.preventDefault();
      activate(tabs, panelByKey, next.dataset.tab, true);
    });

    activate(tabs, panelByKey, current.dataset.tab, false);
  });
})();
