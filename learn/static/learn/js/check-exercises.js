/* Checks a generated path's new HTML, CSS and JavaScript exercises in the owner's browser.
 *
 * Each pending exercise runs twice with the browser runner: its reference solution
 * must pass every test and its starter must fail at least one. The server keeps the
 * ones that do and hides the rest, then the page reloads to show the result.
 */
(async () => {
  const box = document.querySelector('[data-check-exercises]');
  if (!box || !window.WebRunner) return;
  const url = box.dataset.checkExercises;
  const csrf = box.querySelector('[name=csrfmiddlewaretoken]').value;
  const status = box.querySelector('[data-status]');
  try {
    const { exercises } = await (await fetch(url, { credentials: 'same-origin' })).json();
    let done = 0;
    for (const ex of exercises) {
      status.textContent = box.dataset.progress.replace('{done}', done).replace('{total}', exercises.length);
      const solution = await WebRunner.run({ files: ex.solution, tests: ex.tests, libs: ex.libs });
      const starter = await WebRunner.run({ files: ex.starter, tests: ex.tests, libs: ex.libs });
      await fetch(url, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ chapter: ex.chapter, solution: solution.tests, starter: starter.tests }),
      });
      done += 1;
    }
    location.reload();
  } catch (e) {
    box.classList.replace('info', 'warning');
    status.textContent = box.dataset.failed;
  }
})();
