// GET /api/users returns a JSON list: [{ "id": 1, "name": "...", "email": "..." }, ...]
const statusBox = document.querySelector('#status');
const usersBox = document.querySelector('#users');

async function loadUsers() {
  // 1. Show "Loading..." in #status.
  // 2. await fetch('/api/users').
  // 3. If the response is not ok, show "Could not load users" in #status and stop.
  // 4. await response.json(), then add one <article class="card"> per user to #users,
  //    with the name in an <h3> and the email in a <p>.
  // 5. Clear #status when the cards are on the page.
}

loadUsers();
