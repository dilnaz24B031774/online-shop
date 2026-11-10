(() => {
  const refresh = document.getElementById('refresh-challenge');
  const prompt = document.getElementById('challenge-prompt');
  const challengeId = document.querySelector('input[name=challenge_id]');
  const answer = document.getElementById('id_challenge_answer');
  const feedback = document.getElementById('challenge-feedback');
  if (refresh && prompt && challengeId && answer) {
    refresh.addEventListener('click', async () => {
      refresh.disabled = true;
      if (feedback) feedback.textContent = 'Загружаем проверку…';
      try {
        const response = await fetch('/api/auth/challenge/', { cache: 'no-store', credentials: 'same-origin' });
        if (!response.ok) throw new Error('challenge unavailable');
        const challenge = await response.json();
        prompt.textContent = challenge.prompt;
        challengeId.value = challenge.id;
        answer.value = '';
        answer.focus();
        if (feedback) feedback.textContent = 'Новый пример готов.';
      } catch {
        if (feedback) feedback.textContent = 'Не удалось обновить проверку. Повторите через минуту.';
      } finally {
        refresh.disabled = false;
      }
    });
  }
  const cooldown = document.querySelector('[data-login-cooldown]');
  const form = document.getElementById('login-form');
  const submit = document.getElementById('login-submit');
  if (!cooldown || !submit || !form) return;
  const duration = Number(cooldown.dataset.loginCooldown);
  if (!Number.isFinite(duration) || duration <= 0) return;
  const deadline = Date.now() + duration * 1000;
  const countdown = document.getElementById('login-countdown');
  const tick = () => {
    const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
    if (countdown) countdown.textContent = String(remaining);
    if (remaining === 0) {
      clearInterval(timer);
      cooldown.textContent = 'Время ожидания истекло. Можно повторить вход.';
      submit.disabled = false;
    }
  };
  const timer = setInterval(tick, 1000);
  tick();
  window.addEventListener('pagehide', () => clearInterval(timer), { once: true });
})();
