# Fetch users and show them as cards

Most pages get their data from an API. In JavaScript you ask for it with **`fetch`**, and wait for the answer with **`async` / `await`**.

## The pattern

```js
async function loadPosts() {
  const response = await fetch('/api/posts');   // 1. ask the server
  if (!response.ok) {                            // 2. 404, 500... still arrive here
    showError('Could not load posts');
    return;
  }
  const posts = await response.json();           // 3. read the JSON body
  posts.forEach(renderPost);                     // 4. put it on the page
}
```

Two things trip people up:

- `fetch` gives you a **Response**, not the data. Call `await response.json()` to read it.
- `fetch` does **not** throw on a 500. Check `response.ok` yourself.

Use `textContent` to put API data on the page. `innerHTML` would run any HTML hidden in the data.

## Your task

In `script.js`, finish `loadUsers()`:

1. Show `Loading...` in `#status`.
2. `await fetch('/api/users')`.
3. If the response is not ok, show `Could not load users` in `#status` and stop.
4. Read the JSON and add one `<article class="card">` per user to `#users`, with the name in an `<h3>` and the email in a `<p>`.
5. Clear `#status` when the cards are on the page.

There is no real server here: `/api/users` is a practice API that answers inside your browser. Keep the English messages exactly as written, because the tests look for them.
