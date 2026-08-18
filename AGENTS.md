# AGENTS.md — aidr

`ai;dr` (AI; didn't read): a **macOS menu-bar app** that distills whatever the
user copies into its shortest point, using a small language model that runs
**in-process** (no server). Single-file app (`aidr.py`), packaged into a
self-contained `.app` with PyInstaller. macOS only.

## Stack & constraints

- Python 3 (3.10–3.15), managed by **Poetry** (in-project `.venv`,
  `package-mode = false`). Runtime deps: **rumps** (status item + run loop +
  timers), **pyobjc/AppKit** (NSPanel dropdown, SF Symbol icon),
  **llama-cpp-python** (in-process inference), **huggingface-hub** (model
  download when run from source). Dev: **pyinstaller**. Add deps with
  `poetry add`, never by hand-editing pyproject.
- **No Ollama, no cloud, no server.** Inference is `llama_cpp.Llama` loaded
  once in a background thread at startup. Model: `Qwen/Qwen3-0.6B-GGUF` (`Qwen3-0.6B-Q8_0.gguf`), `/no_think` appended
  to skip Qwen3 reasoning, `<think>` stripped. `n_ctx=8192`, input truncated at
  16k chars. `summarize()` makes TWO calls — a one-line headline (HEADLINE_PROMPT,
  48 tok) and a 2-3 sentence detail (DETAIL_PROMPT, 200 tok) — rendered in the
  card as one NSAttributedString (bold labelColor headline + smaller
  secondaryLabelColor detail).
- **Model resolution** (`resolve_model_path`): explicit `AIDR_MODEL_PATH` →
  `RESOURCEPATH`/`sys._MEIPASS`/script-dir `models/<file>` (bundled app) →
  Hugging Face download (cached). So the packaged app uses its bundled model;
  from source it downloads once.
- Input is the **clipboard**: a rumps.Timer polls `NSPasteboard.changeCount()`;
  a new value ≥ `MIN_CHARS` (100) triggers a summary. Never writes the
  clipboard except the "Copy last summary" menu item; guards against
  re-summarizing its own last result.

## Hard-won gotchas (do not regress)

- **rumps.Timer fires its callback IMMEDIATELY on `.start()`** (fire date =
  now), then repeats. Never use it for a one-shot delay. The card's 10s
  auto-close uses `_CardController.performSelector:withObject:afterDelay:`
  (a real one-shot). An earlier rumps.Timer close made the card flash and
  vanish instantly.
- The dropdown is a floating **NSPanel** (borderless, non-activating,
  `hidesOnDeactivate=False`, level 25), NOT an NSPopover. A status-item
  NSPopover gets dismissed instantly because rumps assigns a menu to the
  status item. The panel never steals focus and dismisses on click (a
  gesture recognizer) or after 10s.
- Menu-bar **icon** is the SF Symbol `sparkles.rectangle.stack` (fallbacks:
  doc.text.magnifyingglass, wand.and.sparkles, sparkles), set as a template
  image on the status button once it exists (in `_ensure_icon`, from the
  first clip-timer tick). Placeholder title `✨` until then.
- Threading: worker thread does model load + inference and hands results to a
  `queue.Queue`; a main-thread drain timer updates the UI. Only the main
  thread touches AppKit.
- `AIDR_DEBUG=1` logs the pipeline (started / loading model / model ready /
  new copy / result / card visible). macOS reports `panel.isVisible()` /
  `popover.isShown()` true when displayed — the reliable way to verify without
  a screenshot (screenshots are unreliable while the user is active or on a
  multi-monitor setup).

## Build / run / test

- Run from source: `poetry install` then `./aidr` (or `poetry run python aidr.py`).
- Build the app: `./build.sh` → `dist/aidr.app` (stages the model into
  `models/`, runs `pyinstaller aidr.spec`). The spec bundles the model as a
  data file, `collect_all('llama_cpp')` for the native libs + Metal, and sets
  `LSUIElement` so there's no dock icon.
- Verify the packaged app self-contained: run
  `AIDR_DEBUG=1 dist/aidr.app/Contents/MacOS/aidr`, copy 100+ chars, confirm
  the log shows it loaded the **bundled** model path and produced a result.
- The app is ad-hoc signed only. Distribution to other Macs needs a Developer
  ID sign + notarize, or the recipient right-click → Open.
- `.gitignore` excludes `models/`, `dist/`, `build/`, `.venv/`, and the local
  `.claude/settings*.json` (which set `worktree.bgIsolation=none` so background
  Claude jobs can edit this fresh repo in place).
- Git: never commit unless the user asks; feature branches + PRs, never main.
