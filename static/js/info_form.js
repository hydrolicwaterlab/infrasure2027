(() => {
  const form = document.getElementById('info-form');
  if (!form) return;
  const acctEmail = form.dataset.acctEmail || "";
  const acctIsPersonal = form.dataset.isPersonal === "true";
  const getVal = (name) => {
    const els = form.querySelectorAll(`[name="${name}"]`);
    if (!els.length) return "";
    const checked = form.querySelector(`[name="${name}"]:checked`);
    if (checked) return checked.value || "";
    const el = els[0];
    return el.value || "";
  };
  const update = () => {
    const cat = getVal('participant_category');
    form.querySelectorAll('[data-branch]').forEach(p => {
      const show = p.getAttribute('data-branch') === cat;
      p.hidden = !show;
      p.querySelectorAll('input, select, textarea').forEach(inp => {
        if (!show) {
          inp.required = false;
          inp.disabled = true;
        } else {
          inp.disabled = false;
        }
      });
    });

    const lvl = getVal('student_level');
    form.querySelectorAll('[data-show-if="student_level==UG"]').forEach(p => {
      const show = cat === "Student" && lvl === "UG";
      p.hidden = !show;
      p.querySelectorAll('input, select, textarea').forEach(inp => {
        inp.disabled = !show;
        if (!show) inp.required = false;
      });
    });
    form.querySelectorAll('[data-show-if="student_level==PhD"]').forEach(p => {
      const show = cat === "Student" && lvl === "PhD";
      p.hidden = !show;
      p.querySelectorAll('input, select').forEach(inp => {
        inp.disabled = !show;
        inp.required = show;
      });
    });

    const arole = form.querySelector('[name="academic_role"]')?.value || "";
    form.querySelectorAll('[data-show-if="academic_role==Professor"]').forEach(p => {
      const show = cat === "Academic" && arole === "Professor";
      p.hidden = !show;
      p.querySelectorAll('select, input').forEach(inp => {
        inp.disabled = !show;
        inp.required = show;
      });
    });

    if (cat === "Student") {
      const sl = form.querySelector('#student_level');
      if (sl && !sl.disabled) sl.required = true;
      const instEmailOptional = lvl === "UG" || lvl === "PG";
      const instEmailReq = document.getElementById('institute_email_req');
      if (instEmailReq) instEmailReq.style.display = instEmailOptional ? "none" : "";
      form.querySelectorAll('[data-branch="Student"] input, [data-branch="Student"] select, [data-branch="Student"] textarea').forEach(inp => {
        if (inp.disabled) return;
        if (inp.name === "institute_email") {
          if (!instEmailOptional) {
            inp.required = !(form.querySelector('#institute_email_same_student')?.checked && !acctIsPersonal);
          } else {
            inp.required = false;
          }
          return;
        }
        if (["degree_name","department","institute_name","institute_address","institute_country","institute_zipcode"].includes(inp.name)) inp.required = true;
        if (inp.name === "ug_program" && lvl === "UG") inp.required = true;
        if (inp.name === "supervisor_name" && lvl === "PhD") inp.required = true;
      });
    } else if (cat === "Academic") {
      const sel = form.querySelector('#academic_role');
      if (sel && !sel.disabled) sel.required = true;
      form.querySelectorAll('[data-branch="Academic"] input, [data-branch="Academic"] textarea, [data-branch="Academic"] select').forEach(inp => {
        if (inp.disabled) return;
        if (inp.name === "institute_email" && form.querySelector('#institute_email_same_academic')?.checked && !acctIsPersonal) return;
        if (["department","institute_name","institute_address","institute_country","institute_zipcode","institute_email"].includes(inp.name)) inp.required = true;
      });
    } else if (cat === "Industry") {
      ["company_name","position","company_email","company_address","company_country","company_zipcode"].forEach(n => {
        if (n === "company_email" && form.querySelector('#company_email_same')?.checked && !acctIsPersonal) return;
        const inp = form.querySelector(`[name="${n}"]`);
        if (inp && !inp.disabled) inp.required = true;
      });
    }

    form.querySelectorAll('input[name="institute_email_same"]').forEach(cb => {
      const branch = cb.closest('[data-branch]');
      const isVisible = branch && !branch.hidden;
      if (acctIsPersonal && isVisible) {
        if (cb.checked) cb.checked = false;
        cb.disabled = true;
        cb.closest('label').style.opacity = "0.6";
        cb.closest('label').title = "Your registration email is personal — cannot use same";
      } else if (isVisible) {
        cb.disabled = false;
        cb.closest('label').style.opacity = "";
        cb.closest('label').title = "";
      } else {
        cb.disabled = true;
      }
      const emailInput = branch ? branch.querySelector('input[name="institute_email"]') : null;
      if (emailInput && isVisible) {
        if (cb.checked && !acctIsPersonal) {
          emailInput.value = acctEmail;
          emailInput.readOnly = true;
          emailInput.style.opacity = "0.6";
          emailInput.required = false;
        } else {
          emailInput.readOnly = false;
          emailInput.style.opacity = "";
        }
      }
    });
    const compCb = form.querySelector('input[name="company_email_same"]');
    if (compCb) {
      const branch = compCb.closest('[data-branch]');
      const isVisible = branch && !branch.hidden;
      const compEmail = form.querySelector('#company_email');
      if (acctIsPersonal && isVisible) {
        if (compCb.checked) compCb.checked = false;
        compCb.disabled = true;
        compCb.closest('label').style.opacity = "0.6";
        compCb.closest('label').title = "Your registration email is personal — cannot use same";
        if (compEmail) { compEmail.readOnly = false; compEmail.style.opacity=""; }
      } else if (isVisible) {
        compCb.disabled = false;
        compCb.closest('label').style.opacity = "";
        compCb.closest('label').title = "";
        if (compCb.checked) {
          compEmail.value = acctEmail;
          compEmail.readOnly = true;
          compEmail.style.opacity="0.6";
          compEmail.required = false;
        } else if (compEmail) {
          compEmail.readOnly = false;
          compEmail.style.opacity="";
        }
      } else {
        compCb.disabled = true;
      }
    }

    form.querySelectorAll('.choice input[type="radio"]').forEach(r => {
      const lab = r.closest('.choice');
      if (lab) lab.classList.toggle('is-on', r.checked);
    });
  };

  form.addEventListener('change', update);
  form.addEventListener('input', update);
  update();
})();