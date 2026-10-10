test('string', () => {
  expect(typeof bumpVersion('{"name":"app","version":1}')).toBe('string');
});

test('bumped', () => {
  expect(JSON.parse(bumpVersion('{"name":"app","version":1}'))).toEqual({ name: 'app', version: 2 });
  expect(JSON.parse(bumpVersion('{"version":41}')).version).toBe(42);
});

test('kept', () => {
  const out = JSON.parse(bumpVersion('{"name":"api","version":3,"tags":["web","v3"],"private":true}'));
  expect(out).toEqual({ name: 'api', version: 4, tags: ['web', 'v3'], private: true });
});
