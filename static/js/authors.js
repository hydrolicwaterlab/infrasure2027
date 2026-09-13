(() => {
  const list = document.getElementById('authors-list');
  const template = document.getElementById('author-row-template');
  const addBtn = document.getElementById('author-add');
  if (!list || !template || !addBtn) return;

  const rows = () => list.querySelectorAll('.author-row');

  const syncRemove = () => {
    const all = rows();
    all.forEach((row) => {
      const btn = row.querySelector('.author-remove');
      if (btn) btn.disabled = all.length <= 1;
    });
  };

  addBtn.addEventListener('click', () => {
    const node = template.content.firstElementChild.cloneNode(true);
    list.appendChild(node);
    syncRemove();
    const first = node.querySelector('input');
    if (first) first.focus();
  });

  list.addEventListener('click', (e) => {
    const btn = e.target.closest('.author-remove');
    if (!btn || rows().length <= 1) return;
    btn.closest('.author-row').remove();
    syncRemove();
  });

  syncRemove();
})();
