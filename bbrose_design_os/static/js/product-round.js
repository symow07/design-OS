/* Forms submit normally; JavaScript adds rows and mirrors the chosen copy treatment. */
(() => {
  document.querySelectorAll('[data-content-role-for]').forEach(badge => {
    const choice = document.getElementsByName(`${badge.dataset.contentRoleFor}_role`)[0];
    if (!choice) return;
    const refresh = () => { badge.textContent = choice.value; };
    choice.addEventListener('change', refresh);
    refresh();
  });
  document.querySelectorAll('[data-add-round-row]').forEach(button => button.addEventListener('click', () => {
    const prefix = button.dataset.addRoundRow;
    const total = document.getElementById(`id_${prefix}-TOTAL_FORMS`);
    const limit = prefix === 'panels' ? 32 : 20;
    if (Number(total.value) >= limit) return;
    const template = document.getElementById(`${prefix}-empty`);
    const holder = document.getElementById(prefix === 'panels' ? 'panel-rows' : 'shade-rows');
    holder.insertAdjacentHTML('beforeend', template.innerHTML.replaceAll('__prefix__', total.value));
    total.value = Number(total.value) + 1;
  }));
  const section = document.getElementById('stand-type');
  if (section) {
    const form = section.closest('form');
    const hidden = document.getElementById('id_stand_type');
    const cards = section.querySelectorAll('[data-stand-type]');
    const show = data => {
      const type = hidden.value || data.suggested;
      cards.forEach(card => {
        const on = card.dataset.standType === type;
        card.classList.toggle('chosen', on);
        card.setAttribute('aria-pressed', on);
        card.querySelector('.stand-suggested').hidden = card.dataset.standType !== data.suggested;
      });
      document.getElementById('stand-why').textContent = `The engine suggests ${data.suggested_label}: ${data.why}.`;
      const box = document.getElementById('stand-solved');
      if (!data.ok) { box.textContent = data.words; return; }
      const size = data.closed;
      box.textContent = '';
      const line = document.createElement('p');
      line.textContent = `It will build: ${data.count} products, ${data.rows} rows × ${data.columns}, closed ${size.width} × ${size.depth} × ${size.height} mm (width × depth × height). Every product's top ${data.bar_mm} mm and the whole header's safe area are seen from both eyes.`;
      box.append(line);
      if (data.changes.length) {
        const list = document.createElement('ul');
        list.className = 'small';
        data.changes.forEach(row => {
          const item = document.createElement('li');
          item.textContent = `${row.dimension} ${row.from_mm ? row.from_mm + ' → ' : ''}${row.to_mm}: ${row.reason}`;
          list.append(item);
        });
        box.append(list);
      }
    };
    let timer;
    const ask = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const data = new URLSearchParams();
        new FormData(form).forEach((value, key) => { if (/^(stand_|width$|depth$|height$|cap_height$|diameter$)/.test(key)) data.set(key, value); });
        fetch(`${section.dataset.previewUrl}?${data}`, {headers: {Accept: 'application/json'}}).then(reply => reply.ok ? reply.json() : null).then(answer => { if (answer) show(answer); });
      }, 300);
    };
    cards.forEach(card => card.addEventListener('click', () => { hidden.value = card.dataset.standType; ask(); }));
    form.querySelectorAll('input').forEach(input => { if (/^(stand_|width$|depth$|height$|cap_height$|diameter$)/.test(input.name)) input.addEventListener('input', ask); });
  }
})();
