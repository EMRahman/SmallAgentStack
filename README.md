# The Small Agent Stack

A plain-language, static guide to replacing a bundled OpenClaw setup with independent tools:

- [Pi](https://pi.dev/docs/latest) for the agent and saved sessions
- [Pi Livecraft](https://github.com/sebastienservouze/pi-livecraft) for an optional browser interface and session cost analysis
- system cron for explicit scheduled tasks
- [TelePi](https://github.com/benedict2310/TelePi) for optional Telegram access
- an optional macOS Apple Notes runner pattern for editable job briefs, living output notes, and shared-note notifications

The page also includes a conservative prompt that an installed Pi agent can use to audit and migrate useful OpenClaw instructions, memory, skills, and schedules without copying secrets, enabling jobs, deleting data, or shutting OpenClaw down.

## Preview locally

No build step is required. Open `index.html` directly, or run a small local server:

```sh
python3 -m http.server 8000
```

Then open <http://127.0.0.1:8000>.

## Publish with GitHub Pages

In the repository on GitHub, open **Settings → Pages**, choose **Deploy from a branch**, select the repository's default branch and `/ (root)`, then save.

## Files

- `index.html` — page content and accessible structure
- `styles.css` — responsive visual system
- `script.js` — mobile navigation, copy buttons, prompt expansion, and subtle reveal animation

This is an independent community guide. Package names and requirements can change, so installation links point to each project's upstream documentation.
