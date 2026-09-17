(() => {
  const rows = document.querySelectorAll("tr.reg-row[data-reg-target]");
  const modals = document.querySelectorAll(".reg-modal");
  if (!rows.length || !modals.length) return;

  const open = (modal, trigger) => {
    modal.classList.add("is-open");
    modal._trigger = trigger;
    document.body.classList.add("reg-modal-open");
    const close = modal.querySelector(".reg-modal-close");
    if (close) close.focus();
  };

  const close = (modal) => {
    modal.classList.remove("is-open");
    if (!document.querySelector(".reg-modal.is-open")) {
      document.body.classList.remove("reg-modal-open");
    }
    const trigger = modal._trigger;
    if (trigger) trigger.focus();
  };

  rows.forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target.closest("a, button, input, select, textarea, form, label")) return;
      const modal = document.getElementById(row.dataset.regTarget);
      if (modal) open(modal, row);
    });
    row.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      if (event.target.closest("a, button, input, select, textarea")) return;
      event.preventDefault();
      const modal = document.getElementById(row.dataset.regTarget);
      if (modal) open(modal, row);
    });
  });

  modals.forEach((modal) => {
    modal.addEventListener("click", (event) => {
      if (event.target === modal) close(modal);
    });
    const closeBtn = modal.querySelector(".reg-modal-close");
    if (closeBtn) closeBtn.addEventListener("click", () => close(modal));
    modal.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close(modal);
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const modal = document.querySelector(".reg-modal.is-open");
    if (modal) close(modal);
  });
})();