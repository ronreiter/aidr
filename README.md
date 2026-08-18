# ai;dr

**AI wrote it. You shouldn't have to read it.**

Something is generating an enormous amount of text lately, and it isn't people.
The six-paragraph email that was one sentence. The pull request description that
restates the diff back to you. Release notes written to sound thorough. A recipe
with a childhood memoir attached. Somebody else's AI does the padding, and the
padding lands on you.

ai;dr is a macOS menu-bar app that reads it so you don't. Copy the wall of text
and a card drops out of the menu bar with the one line it was hiding — plus two
sentences of detail if you want them.

It takes a small AI to clean up after a big one. The small one runs entirely on
your Mac.

**[Download for macOS](https://github.com/ronreiter/aidr/releases/latest/download/aidr.dmg)**
· [Website](https://ronreiter.github.io/aidr/)

---

## How it works

1. It sits in the menu bar. No window, no typing, no buttons.
2. Copy 100+ characters, exactly the way you already copy things.
3. A card drops from the icon with the point. It stays ten seconds, or until you
   click it. It never steals focus from what you were doing.

Anything under 100 characters is ignored, so copying a file path, a variable
name or a URL never sets it off. It wakes up for the things you'd otherwise
skim. Your clipboard is never modified.

The menu has **Show clipboard summary** if you missed a card, and **Copy last
summary** to paste it somewhere.

## Why it runs on your machine

Paying a cloud AI to compress what another cloud AI inflated is a strange way to
live. So the model ships inside the app:

- **No server, no daemon, no API key.** `llama.cpp` runs Qwen3-0.6B in-process.
- **Nothing is uploaded**, because there is nowhere for it to go — the app makes
  no network requests at all. It works on a plane.
- **Nothing is stored.** No history, no telemetry, no summaries on disk.

That is also why the download is ~680 MB: almost all of it is the model, not the
app.

## Install

Download **[aidr.dmg](https://github.com/ronreiter/aidr/releases/latest/download/aidr.dmg)**,
open it, and drag ai;dr into the Applications folder shown beside it.

Apple Silicon only. It's signed with a Developer ID and notarized by Apple, so
it opens on first launch — no right-click dance, no "unidentified developer".

To keep it running, add it under **System Settings → General → Login Items**.

## Run from source

```sh
git clone https://github.com/ronreiter/aidr
cd aidr
poetry install
./aidr
```

The model is fetched once from Hugging Face (~610 MB) and cached in
`~/.cache/huggingface`. Needs Python 3.10–3.15.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `AIDR_MODEL_PATH` | (unset) | Use a specific local `.gguf` instead |
| `AIDR_MODEL_REPO` | `Qwen/Qwen3-0.6B-GGUF` | Hugging Face repo to download from |
| `AIDR_MODEL_FILE` | `Qwen3-0.6B-Q8_0.gguf` | File within that repo |
| `AIDR_WEBSITE` | the project site | Where "About ai;dr…" points |
| `AIDR_DEBUG` | (unset) | `1` logs the pipeline to stderr |

Any GGUF llama.cpp can load will work — drop one in `models/` before building,
or point `AIDR_MODEL_PATH` at it.

## Building and releasing

```sh
./build.sh        # → dist/aidr.app and dist/aidr.dmg, model bundled
```

Releases are automatic: bump `version` in `pyproject.toml` and push to `main`.
CI builds the app, signs it with the Developer ID, notarizes it with Apple,
staples the ticket, and publishes the zip. Pushes that don't change the version
don't rebuild.

## How it's put together

A single Python file. `rumps` for the menu-bar item, AppKit for the floating
card, `llama-cpp-python` for inference, and PyInstaller to fold Python, the
native libraries and the model into one `.app`.

## Credits

Model: [Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B) (Apache-2.0) ·
Inference: [llama.cpp](https://github.com/ggerganov/llama.cpp) ·
Icon: [Tabler Icons](https://tabler.io/icons) (MIT) ·
ai;dr is MIT licensed.
