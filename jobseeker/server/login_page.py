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
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='8' fill='%235E6AD2'/><path d='M9 20l4-9 3 6 2-3 5 6' stroke='white' stroke-width='2.4' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>" />
<style>
  /* The same self hosted face the dashboard uses, so signing in and using the
     app do not feel like two different products. One family only: the display
     face this page used to load was dropped from the design system, and a
     stylesheet that keeps asking for it ships a 404 on the first screen. */
  @font-face {
    font-family: "Inter var";
    src: url("/fonts/Inter.woff2") format("woff2");
    font-weight: 100 900;
    font-display: swap;
  }
  /* Dark is the primary theme, so it is the default here and light is the
     override. These values are the dashboard's own tokens; see DESIGN.md. */
  :root {
    --canvas: #010102; --surface: #0f1011; --surface-2: #141516; --surface-3: #18191a;
    --line: #23252a; --line-strong: #34343a;
    --ink: #f7f8f8; --ink-2: #d0d6e0; --muted: #8a8f98;
    --accent: #5e6ad2; --accent-hover: #828fff; --accent-focus: #5e69d1; --accent-ink: #ffffff;
    --danger: #eb5757;
    --edge: inset 0 1px 0 rgb(255 255 255 / .04);
    --shadow: 0 6px 12px -6px rgb(0 0 0 / .5), 0 24px 48px -24px rgb(0 0 0 / .8);
  }
  @media (prefers-color-scheme: light) {
    :root {
      --canvas: #f1f2f4; --surface: #ffffff; --surface-2: #f7f8f9; --surface-3: #edeef1;
      --line: #dcdee3; --line-strong: #c8cbd2;
      --ink: #131416; --ink-2: #3b3f45; --muted: #64696e;
      --accent: #5e6ad2; --accent-hover: #4d59c4; --accent-focus: #5e69d1; --accent-ink: #ffffff;
      --danger: #bf2a2a;
      --edge: inset 0 1px 0 rgb(255 255 255 / .7);
      --shadow: 0 6px 12px -6px rgb(16 20 25 / .14), 0 18px 36px -18px rgb(16 20 25 / .22);
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    padding: 24px; background: var(--canvas); color: var(--ink);
    font-family: "Inter var", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    font-size: 14px; line-height: 1.5; letter-spacing: -0.006em;
    -webkit-font-smoothing: antialiased;
  }
  ::selection { background: color-mix(in oklab, var(--accent) 34%, transparent); color: var(--ink); }
  * { caret-color: var(--accent); }
  /* Depth is the surface ladder and a hairline, the way it is everywhere else
     in this product. No accent wash: the accent is spent on the one action. */
  main {
    position: relative; width: 100%; max-width: 360px;
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 12px; box-shadow: var(--shadow), var(--edge); padding: 24px 22px 20px;
  }
  .brand { display: flex; align-items: center; gap: 10px; margin-bottom: 22px; }
  .brand h1 { font-size: 14px; font-weight: 600; letter-spacing: -0.018em; margin: 0; }
  .brand p { margin: 1px 0 0; font-size: 11px; color: var(--muted); }
  h2 { font-size: 22px; font-weight: 620; letter-spacing: -0.021em; margin: 0 0 6px; }
  .lede { margin: 0 0 20px; font-size: 13px; line-height: 1.55; color: var(--muted); }
  label { display: block; font-size: 12px; font-weight: 500; color: var(--muted); margin-bottom: 6px; }
  .field { position: relative; display: flex; align-items: center; }
  .reveal {
    position: absolute; right: 4px; width: 28px; height: 28px; padding: 0;
    display: grid; place-items: center; margin: 0;
    background: transparent; border: 0; border-radius: 8px;
    color: var(--muted); cursor: pointer;
  }
  .reveal:hover { color: var(--ink); background: var(--surface-3); }
  input {
    width: 100%; height: 36px; padding: 0 38px 0 10px; font-size: 14px; color: var(--ink);
    background: var(--surface-2); border: 1px solid var(--line);
    border-radius: 8px; outline: none; transition: border-color .14s;
  }
  input::placeholder { color: var(--muted); }
  input:hover { border-color: var(--line-strong); }
  /* The one focus treatment this product uses: a 2px accent ring at half
     strength, following the element's own corners. */
  input:focus, button:focus-visible, .reveal:focus-visible {
    outline: 2px solid color-mix(in oklab, var(--accent-focus) 55%, transparent);
    outline-offset: 1px; border-color: var(--line-strong);
  }
  button[type="submit"] {
    width: 100%; min-height: 32px; margin-top: 14px; border: 1px solid transparent;
    border-radius: 8px; background: var(--accent); color: var(--accent-ink);
    font-family: inherit; font-size: 13px; font-weight: 510; cursor: pointer;
    transition: background-color .14s;
  }
  button[type="submit"]:hover:not(:disabled) { background: var(--accent-hover); }
  button[type="submit"]:active:not(:disabled) { background: var(--accent-focus); }
  /* Desaturate rather than fade: a faded label falls below readable contrast. */
  button[type="submit"]:disabled {
    background: var(--surface-3); color: var(--muted); cursor: not-allowed;
  }
  /* A hairline in the danger hue, not a filled block: the same alert grammar
     the dashboard uses. */
  .error {
    display: none; margin-top: 14px; padding: 8px 10px; border-radius: 8px;
    background: var(--surface-2);
    border: 1px solid color-mix(in oklab, var(--danger) 40%, var(--line));
    color: var(--ink-2); font-size: 13px; line-height: 1.45;
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
    <svg class="logo" width="26" height="26" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="var(--accent)" />
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
