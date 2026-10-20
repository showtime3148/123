document.getElementById("loginForm").addEventListener("submit", async event => {
  event.preventDefault();
  const button = document.getElementById("loginButton");
  const error = document.getElementById("loginError");
  button.disabled = true; error.textContent = "";
  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({password: document.getElementById("password").value}),
      signal: AbortSignal.timeout(15000)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "로그인 정보를 확인해 주세요.");
    document.getElementById("password").value = "";
    location.replace("/");
  } catch (failure) {
    error.textContent = failure.name === "TimeoutError" ? "연결 시간이 초과되었습니다. 다시 시도해 주세요." : failure.message;
  } finally { button.disabled = false; }
});
