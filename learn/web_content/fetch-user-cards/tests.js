const USERS = __learn.api['/api/users'].body;

test('fetches', async () => {
  await waitFor(() => __learn.calls.length);
  expect(__learn.calls.some((call) => call.path === '/api/users')).toBe(true);
});

test('loading', async () => {
  await waitFor(() => $$('#users .card').length === USERS.length);
  $('#users').innerHTML = '';
  const done = loadUsers();
  expect($('#status').textContent.trim().toLowerCase()).toContain('loading');
  await done;
});

test('cards', async () => {
  await waitFor(() => $$('#users .card').length >= USERS.length);
  expect($$('#users .card').length).toBe(USERS.length);
  expect($$('#users article.card').length).toBe(USERS.length);
});

test('content', async () => {
  await waitFor(() => $$('#users .card').length === USERS.length);
  expect($$('#users .card h3').map((h) => h.textContent.trim())).toEqual(USERS.map((u) => u.name));
  expect($$('#users .card p').map((p) => p.textContent.trim())).toEqual(USERS.map((u) => u.email));
});

test('cleared', async () => {
  await waitFor(() => $$('#users .card').length === USERS.length);
  expect(await waitFor(() => $('#status').textContent.trim() === '')).toBe(true);
});

test('error', async () => {
  const route = __learn.api['/api/users'];
  __learn.api['/api/users'] = { status: 500, body: { error: 'Server error' } };
  $('#users').innerHTML = '';
  try {
    await loadUsers();
    expect($('#status').textContent).toContain('Could not load users');
    expect($$('#users .card').length).toBe(0);
  } finally {
    __learn.api['/api/users'] = route;
  }
});
