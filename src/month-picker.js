(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const input = $('start'), dialog = $('month-picker'), trigger = $('start-trigger');
  const data = JSON.parse($('research-data').textContent);
  const minimum = input.min;
  const maximum = data.assets.flatMap(asset => asset.monthly)
    .filter(month => month.complete).map(month => month.month).sort().at(-1);
  input.max = maximum;
  const firstYear = Number(minimum.slice(0, 4)), lastYear = Number(maximum.slice(0, 4));
  const format = value => `${Number(value.slice(0, 4))}年${Number(value.slice(5))}月`;
  const key = (year, month) => `${year}-${String(month).padStart(2, '0')}`;
  const clamp = value => value < minimum ? minimum : value > maximum ? maximum : value;
  let draft = input.value, previousOverflow = '';
  const sync = () => { $('start-label').textContent = format(input.value); };

  for (let year = firstYear; year <= lastYear; year++) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = year;
    button.dataset.year = year;
    button.setAttribute('aria-label', `${year}年`);
    button.onclick = () => selectYear(year);
    $('year-list').append(button);
  }
  for (let month = 1; month <= 12; month++) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = `${month}月`;
    button.dataset.pickerMonth = month;
    button.onclick = () => { draft = key(Number(draft.slice(0, 4)), month); render(); };
    $('month-grid').append(button);
  }
  const latestDate = data.assets.map(asset => asset.summary.data_end).sort().at(-1);
  const recentStart = clamp(key(Number(latestDate.slice(0, 4)) - 10, Number(latestDate.slice(5, 7))));
  for (const [label, value] of [['最早月份', minimum], ['近十年起点', recentStart], ['最新完整月', maximum]]) {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.startShortcut = value;
    button.append(document.createTextNode(label));
    const date = document.createElement('span');
    date.textContent = value.replace('-', '.');
    button.append(date);
    button.onclick = () => { draft = value; render(); scrollYear(); };
    $('month-shortcuts').append(button);
  }

  function render() {
    const year = Number(draft.slice(0, 4)), month = Number(draft.slice(5));
    $('picker-year').textContent = `${year}年`;
    $('month-selection').textContent = format(draft);
    $('year-prev').disabled = year === firstYear;
    $('year-next').disabled = year === lastYear;
    $('year-list').querySelectorAll('button').forEach(button => {
      const selected = Number(button.dataset.year) === year;
      button.setAttribute('aria-pressed', selected);
      button.tabIndex = selected ? 0 : -1;
    });
    $('month-grid').querySelectorAll('button').forEach(button => {
      const number = Number(button.dataset.pickerMonth), value = key(year, number);
      const selected = number === month;
      button.disabled = value < minimum || value > maximum;
      button.setAttribute('aria-pressed', selected);
      button.setAttribute('aria-label', format(value));
      button.tabIndex = selected ? 0 : -1;
    });
  }
  function scrollYear() {
    // Scroll only the year list; keep the dialog and underlying research page stationary.
    const list = $('year-list'), button = list.querySelector('[aria-pressed="true"]');
    const top = button.getBoundingClientRect().top - list.getBoundingClientRect().top + list.scrollTop;
    list.scrollTop = top - (list.clientHeight - button.offsetHeight) / 2;
  }
  function selectYear(year) {
    draft = clamp(key(year, Number(draft.slice(5))));
    render();
    scrollYear();
  }
  $('year-prev').onclick = () => selectYear(Number(draft.slice(0, 4)) - 1);
  $('year-next').onclick = () => selectYear(Number(draft.slice(0, 4)) + 1);
  $('year-list').onkeydown = event => {
    const columns = getComputedStyle($('year-list')).gridTemplateColumns.split(' ').length;
    const step = {ArrowLeft: -1, ArrowRight: 1, ArrowUp: -columns, ArrowDown: columns}[event.key];
    if (step == null) return;
    event.preventDefault();
    const year = Math.min(lastYear, Math.max(firstYear, Number(draft.slice(0, 4)) + step));
    selectYear(year);
    $('year-list').querySelector('[aria-pressed="true"]').focus({preventScroll: true});
  };
  $('month-grid').onkeydown = event => {
    const step = {ArrowLeft: -1, ArrowRight: 1, ArrowUp: -3, ArrowDown: 3}[event.key];
    if (step == null) return;
    event.preventDefault();
    const month = Math.min(12, Math.max(1, Number(draft.slice(5)) + step));
    draft = clamp(key(Number(draft.slice(0, 4)), month));
    render();
    $('month-grid').querySelector('[aria-pressed="true"]').focus();
  };
  trigger.onclick = () => {
    draft = clamp(input.value || minimum);
    render();
    previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.showModal();
    trigger.setAttribute('aria-expanded', 'true');
    scrollYear();
    $('year-list').querySelector('[aria-pressed="true"]').focus({preventScroll: true});
  };
  $('month-apply').onclick = () => {
    input.value = draft;
    input.dispatchEvent(new Event('change', {bubbles: true}));
    dialog.close();
  };
  for (const id of ['month-close', 'month-cancel']) $(id).onclick = () => dialog.close();
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
  dialog.addEventListener('close', () => {
    document.body.style.overflow = previousOverflow;
    trigger.setAttribute('aria-expanded', 'false');
    trigger.focus({preventScroll: true});
  });
  input.addEventListener('change', sync);
  $('reset').addEventListener('click', sync);
  sync();
})();
