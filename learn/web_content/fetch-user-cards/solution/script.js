// GET /api/users returns a JSON list: [{ "id": 1, "name": "...", "email": "..." }, ...]
const statusBox = document.querySelector('#status');
const usersBox = document.querySelector('#users');

async function loadUsers() {
  statusBox.textContent = 'Loading...';
  statusBox.classList.remove('error');
  const response = await fetch('/api/users');
  if (!response.ok) {
    statusBox.textContent = 'Could not load users';
    statusBox.classList.add('error');
    return;
  }
  const users = await response.json();
  for (const user of users) {
    const card = document.createElement('article');
    card.className = 'card';
    const name = document.createElement('h3');
    name.textContent = user.name;
    const email = document.createElement('p');
    email.textContent = user.email;
    card.append(name, email);
    usersBox.append(card);
  }
  statusBox.textContent = '';
}

loadUsers();
