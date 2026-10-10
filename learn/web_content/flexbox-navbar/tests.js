test('nav-flex', () => {
  expect(css($('.site-nav'), 'display')).toBe('flex');
});

test('nav-ends', () => {
  expect(css($('.site-nav'), 'justify-content')).toBe('space-between');
  const nav = $('.site-nav').getBoundingClientRect();
  const links = $('.links').getBoundingClientRect();
  expect(nav.right - links.right < 40).toBe(true);
});

test('nav-center', () => {
  expect(css($('.site-nav'), 'align-items')).toBe('center');
});

test('nav-wrap', () => {
  expect(css($('.site-nav'), 'flex-wrap')).toBe('wrap');
});

test('no-bullets', () => {
  expect(css($('.links'), 'list-style-type')).toBe('none');
});

test('links-row', () => {
  expect(css($('.links'), 'display')).toBe('flex');
  const items = $$('.links li').map((li) => li.getBoundingClientRect());
  expect(items.every((box) => Math.abs(box.top - items[0].top) < 2)).toBe(true);
  expect(css($('.links'), 'column-gap')).toBe('16px');
});
