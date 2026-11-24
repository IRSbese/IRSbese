// ЧАСТЬ 7. Небольшие интерактивные элементы интерфейса.
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-dismiss-flash]').forEach(function (button) {
    button.addEventListener('click', function () {
      const message = button.closest('.flash');
      if (message) message.remove();
    });
  });

  const toggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('.main-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      const opened = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(opened));
    });
  }
  document.querySelectorAll('input[type="file"]').forEach(function (input) {
    input.addEventListener('change', function () {
      if (input.files && input.files[0] && input.files[0].size > 5 * 1024 * 1024) {
        alert('Файл больше 5 МБ. Выберите изображение меньшего размера.');
        input.value = '';
      }
    });
  });
});
