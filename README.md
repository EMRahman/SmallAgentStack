# The Small Agent Stack

A plain-language, static guide to replacing a bundled OpenClaw setup with independent tools:

- [Pi](https://pi.dev/docs/latest) for the agent and saved sessions
- [Pi Livecraft](https://github.com/sebastienservouze/pi-livecraft) for an optional browser interface and session cost analysis
- system cron for explicit scheduled tasks
- [TelePi](https://github.com/benedict2310/TelePi) for optional Telegram access
- an optional macOS Apple Notes runner pattern for editable job briefs, living output notes, and shared-note notifications

The page also includes a conservative prompt that an installed Pi agent can use to audit and migrate useful OpenClaw instructions, memory, skills, and schedules without copying secrets, enabling jobs, deleting data, or shutting OpenClaw down.

The design essay explains agency through agent-assisted research and customization, with expandable steelman arguments for and against the modular approach. It distinguishes runtime coordination from vendor control, and includes OpenClaw's own architectural counterargument. Audience history links to [Star History](https://www.star-history.com/?repos=earendil-works%2Fpi%2Copenclaw%2Fopenclaw&type=date&legend=top-left); stars and issue reports are not treated as reliability measurements.

The research section separates personal reliability, explicit model-call triggers and narrow custom extensions from security guarantees. It examines OpenClaw's documented struggles and possible recovery, traces its early use of Pi through Armin Ronacher's January and Mario Zechner's April accounts, and distinguishes that history from current runtime documentation. The assessment connects discovering those layers to practical agency, the Raspberry Pi educational ideal, and the possibilities of agent-assisted bespoke software.

## Read the guide

Visit the published site: [SmallAgentStack](https://emrahman.github.io/SmallAgentStack/).

## Files

- `index.html` — page content and accessible structure
- `styles.css` — responsive visual system
- `script.js` — mobile navigation, copy buttons, prompt expansion, and subtle reveal animation
- `drafts/evidence.html` — supplementary age-aligned chart preview; see `drafts/README.md` for sources and reproduction
- `scripts/evidence.py` — standard-library chart generator and read-only GitHub collector
- `tests/` — data-methodology and page-structure tests

## Preview and checks

Serve the guide locally, then open `http://127.0.0.1:8000/#research`:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Run the data-methodology, source-qualification and page-structure tests without network access:

```sh
python3 -B -m unittest discover -s tests -v
```

This is an independent community guide. Package names and requirements can change, so installation links point to each project's upstream documentation.
