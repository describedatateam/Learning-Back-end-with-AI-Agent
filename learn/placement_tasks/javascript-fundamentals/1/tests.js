const ITEMS = [
  { title: 'Pen', price: 2.5 },
  { title: 'Lamp', price: 30 },
  { title: 'Notebook', price: 10 },
];

test('filters', () => {
  expect(cheapTitles(ITEMS, 10)).toEqual(['Pen', 'Notebook']);
});

test('empty', () => {
  expect(cheapTitles(ITEMS, 1)).toEqual([]);
  expect(cheapTitles([], 50)).toEqual([]);
});

test('unchanged', () => {
  const copy = JSON.stringify(ITEMS);
  cheapTitles(ITEMS, 100);
  expect(JSON.stringify(ITEMS)).toBe(copy);
});
