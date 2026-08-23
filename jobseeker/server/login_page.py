"""The login screen.

Served by the API itself for any unauthenticated page request, so there is no
route in the dashboard that can be reached without signing in. It is a single
self contained document with no build step and no external requests, and it
follows the same palette as the dashboard in both light and dark.
"""

from __future__ import annotations

LOGIN_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="color-scheme" content="light dark" />
<meta name="robots" content="noindex, nofollow" />
<title>Sign in · JobSeeker</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='8' fill='%230E7C86'/><path d='M9 20l4-9 3 6 2-3 5 6' stroke='white' stroke-width='2.4' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>" />
<style>
  /* The same self hosted faces the dashboard uses, so signing in and using the
     app do not feel like two different products. */
  @font-face {
    font-family: "Ysabeau";
    src: url("/fonts/Ysabeau.woff2") format("woff2");
    font-weight: 100 1000;
    font-display: swap;
  }
  @font-face {
    font-family: "Inter var";
    src: url("/fonts/Inter.woff2") format("woff2");
    font-weight: 100 900;
    font-display: swap;
  }
  :root {
    --canvas: #f2f1ed; --surface: #ffffff; --surface-3: #f0efea;
    --line: #e4e2db; --ink: #14171a; --muted: #6f7378;
    --accent: #0e7c86; --accent-ink: #ffffff; --accent-soft: #e3f2f3;
    --danger: #b91c1c; --danger-soft: #fdeaea;
    --shadow: 0 1px 2px rgb(16 20 25 / .04), 0 24px 48px -24px rgb(16 20 25 / .22);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --canvas: #0c0d0f; --surface: #16181b; --surface-3: #212529;
      --line: #292d32; --ink: #f0efe9; --muted: #85888c;
      --accent: #2dd4bf; --accent-ink: #04211f; --accent-soft: #10312f;
      --danger: #f87171; --danger-soft: #2c1516;
      --shadow: 0 1px 2px rgb(0 0 0 / .5), 0 24px 48px -24px rgb(0 0 0 / .85);
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    padding: 24px; background: var(--canvas); color: var(--ink);
    font-family: "Inter var", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  /* A single quiet accent wash, so the page is not a bare form on a flat field. */
  body::before {
    content: ""; position: fixed; inset: 0; pointer-events: none;
    background: radial-gradient(60rem 30rem at 50% -12rem,
      color-mix(in oklab, var(--accent) 12%, transparent), transparent 70%);
  }
  main {
    position: relative; width: 100%; max-width: 380px;
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 18px; box-shadow: var(--shadow); padding: 28px 26px 24px;
  }
  .brand { display: flex; align-items: center; gap: 10px; margin-bottom: 22px; }
  .brand h1 {
    font-family: "Ysabeau", ui-sans-serif, system-ui, sans-serif;
    font-size: 17px; font-weight: 650; letter-spacing: -0.006em; margin: 0;
  }
  .brand p { margin: 2px 0 0; font-size: 11px; color: var(--muted); }
  h2 {
    font-family: "Ysabeau", ui-sans-serif, system-ui, sans-serif;
    font-size: 23px; font-weight: 650; letter-spacing: -0.006em; margin: 0 0 6px;
  }
  .lede { margin: 0 0 20px; font-size: 12.5px; line-height: 1.55; color: var(--muted); }
  label { display: block; font-size: 11px; font-weight: 600; letter-spacing: .05em;
          text-transform: uppercase; color: var(--muted); margin-bottom: 7px; }
  .field { position: relative; display: flex; align-items: center; }
  .reveal {
    position: absolute; right: 6px; width: 32px; height: 32px; padding: 0;
    display: grid; place-items: center; margin: 0;
    background: transparent; border: 0; border-radius: 8px;
    color: var(--muted); cursor: pointer;
  }
  .reveal:hover { color: var(--ink); background: var(--surface-3); }
  input {
    width: 100%; height: 44px; padding: 0 42px 0 12px; font-size: 15px; color: var(--ink);
    background: var(--surface-3); border: 1px solid var(--line);
    border-radius: 11px; outline: none; transition: border-color .12s, box-shadow .12s;
  }
  input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--accent) 22%, transparent);
  }
  button {
    font-family: "Ysabeau", ui-sans-serif, system-ui, sans-serif;
    font-weight: 650;
    width: 100%; height: 42px; margin-top: 14px; border: 0; border-radius: 11px;
    background: var(--accent); color: var(--accent-ink);
    font-size: 14px; font-weight: 600; cursor: pointer; transition: filter .12s;
  }
  button:hover:not(:disabled) { filter: brightness(1.07); }
  button:disabled { opacity: .55; cursor: not-allowed; }
  .error {
    display: none; margin-top: 14px; padding: 9px 11px; border-radius: 10px;
    background: var(--danger-soft); color: var(--danger);
    font-size: 12.5px; line-height: 1.45;
  }
  .error.show { display: block; }
  .foot { margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--line);
          font-size: 11px; line-height: 1.5; color: var(--muted); }
  svg.logo { flex: none; }
</style>
</head>
<body>
<main>
  <div class="brand">
    <svg class="logo" width="30" height="30" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="var(--accent)" />
      <path d="M8.5 20.5 12.5 11l3.2 6.2 2.1-3.1 5.7 6.4" stroke="var(--accent-ink)"
            stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
    <div>
      <h1>JobSeeker</h1>
      <p>__BRAND__</p>
    </div>
  </div>

  <h2>Sign in</h2>
  <p class="lede">
    This dashboard can send email on your behalf, so it is not open to the internet.
  </p>

  <form id="form" autocomplete="on">
    <label for="password">Password</label>
    <div class="field">
      <input id="password" name="password" type="password" autocomplete="current-password"
             autofocus required />
      <button type="button" class="reveal" id="reveal" aria-label="Show password"
              aria-pressed="false" tabindex="-1">
        <svg id="eye" width="17" height="17" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="1.6" stroke-linecap="round"
             stroke-linejoin="round" aria-hidden="true">
          <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
          <circle cx="12" cy="12" r="3.2" />
        </svg>
      </button>
    </div>
    <button id="submit" type="submit">Sign in</button>
  </form>

  <div class="error" id="error" role="alert"></div>

  <p class="foot">
    Forgotten it? Reset it from the machine with <code>./run set-password</code>.
    There is no reset by email, by design. Once you are in, you can change it
    under Profile.
  </p>
</main>

<script>
  const reveal = document.getElementById("reveal");
  const eye = document.getElementById("eye");
  const EYE_OPEN =
    '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />' +
    '<circle cx="12" cy="12" r="3.2" />';
  const EYE_OFF =
    '<path d="M9.9 5.8A9.5 9.5 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-3.2 3.9M6.3 7.9A17 17 0 0 0 2.5 12S6 18.5 12 18.5c1 0 1.9-.2 2.7-.5" />' +
    '<path d="M10 10a3.2 3.2 0 0 0 4.2 4.4M3.5 3.5l17 17" />';

  const form = document.getElementById("form");
  const input = document.getElementById("password");
  const button = document.getElementById("submit");
  const error = document.getElementById("error");

  function fail(message) {
    error.textContent = message;
    error.classList.add("show");
    button.disabled = false;
    button.textContent = "Sign in";
    input.select();
  }

  let revealTimer = null;
  reveal.addEventListener("click", () => {
    const showing = input.type === "text";
    input.type = showing ? "password" : "text";
    eye.innerHTML = showing ? EYE_OPEN : EYE_OFF;
    reveal.setAttribute("aria-pressed", String(!showing));
    reveal.setAttribute("aria-label", showing ? "Show password" : "Hide password");
    // Never leave a password on screen indefinitely.
    window.clearTimeout(revealTimer);
    if (!showing) {
      revealTimer = window.setTimeout(() => {
        input.type = "password";
        eye.innerHTML = EYE_OPEN;
        reveal.setAttribute("aria-pressed", "false");
        reveal.setAttribute("aria-label", "Show password");
      }, 15000);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.classList.remove("show");
    button.disabled = true;
    button.textContent = "Checking";

    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: input.value }),
      });
      const payload = await response.json().catch(() => ({}));
      if (response.ok) {
        window.location.replace("/");
        return;
      }
      fail(payload.error || "That did not work.");
    } catch (problem) {
      fail("Could not reach the server. Is it still running?");
    }
  });
</script>
</body>
</html>
"""


def render(brand: str = "application engine") -> bytes:
    return LOGIN_HTML.replace("__BRAND__", brand).encode("utf-8")
