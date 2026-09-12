const search = document.querySelector('#search');
search?.addEventListener('input', () => {
  const query = search.value.trim().toLocaleLowerCase('vi');
  document.querySelectorAll('#rows tr').forEach((row) => {
    row.hidden = query && !row.dataset.search.includes(query);
  });
});
