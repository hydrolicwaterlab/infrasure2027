(() => {
  const header = document.getElementById("site-header");
  const toggle = document.getElementById("nav-toggle");
  const menu = document.getElementById("mobile-nav");

  // Sticky header: compact state on scroll (with hysteresis to avoid flicker)
  if (header) {
    let compact = false;
    const setCompact = (active) => {
      if (active !== compact) {
        compact = active;
        header.classList.toggle("is-scrolled", compact);
      }
    };
    const onScroll = () => {
      if (window.scrollY > 30) setCompact(true);
      else if (window.scrollY < 2) setCompact(false);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  // Mobile menu
  if (toggle && menu) {
    const close = () => {
      menu.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    };
    toggle.addEventListener("click", () => {
      const open = menu.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    menu.addEventListener("click", (e) => {
      if (e.target.closest("a")) close();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });
    window.addEventListener("resize", () => {
      if (window.innerWidth > 980) close();
    });
  }

  // Brochure dropdowns (hover handled in CSS; click/keyboard here)
  const dropdowns = document.querySelectorAll(".nav-dropdown, .mobile-dropdown");
  if (dropdowns.length) {
    const closeDropdown = (wrap) => {
      wrap.classList.remove("is-open");
      const btn = wrap.querySelector(".nav-dropdown-toggle, .mobile-dropdown-toggle");
      if (btn) btn.setAttribute("aria-expanded", "false");
    };
    const closeAll = (except) => {
      dropdowns.forEach((wrap) => {
        if (wrap !== except) closeDropdown(wrap);
      });
    };
    dropdowns.forEach((wrap) => {
      const btn = wrap.querySelector(".nav-dropdown-toggle, .mobile-dropdown-toggle");
      if (!btn) return;
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const open = !wrap.classList.contains("is-open");
        closeAll(wrap);
        wrap.classList.toggle("is-open", open);
        btn.setAttribute("aria-expanded", String(open));
        if (!open) {
          const focused = wrap.querySelector(":focus");
          if (focused) focused.blur();
        }
      });
    });
    document.addEventListener("click", () => closeAll(null));
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      closeAll(null);
      const active = document.activeElement;
      if (active && active.closest(".nav-dropdown, .mobile-dropdown")) active.blur();
    });
  }

  // Policies page — highlight currently visible section in the "On this page" list
  const toc = document.querySelector(".policy-toc");
  if (toc) {
    const links = [...toc.querySelectorAll("a[href^='#']")];
    const titles = document.querySelectorAll(".policy-block[id]");
    if (links.length && titles.length) {
      const onScroll = () => {
        let current = titles[0].id;
        const probe = window.scrollY + 110;
        titles.forEach((el) => {
          if (el.offsetTop <= probe) current = el.id;
        });
        links.forEach((a) => {
          const active = a.getAttribute("href") === `#${current}`;
          a.classList.toggle("is-active", active);
          if (active) a.setAttribute("aria-current", "true");
          else a.removeAttribute("aria-current");
        });
      };
      onScroll();
      window.addEventListener("scroll", onScroll, { passive: true });
    }
  }
})();
