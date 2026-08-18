# ai;dr

**AI; didn't read.** A macOS menu-bar app: copy any text anywhere and a small
card drops from the ai;dr icon with its point — a bold one-line headline plus a short detailed summary — distilled by a
small language model that runs **entirely on your machine, in-process**. No
server, no Ollama, no API keys, no network once the model is present. No
window, no typing, no buttons; it just watches your clipboard.

**Website:** https://ronreiter.github.io/aidr · **Download:** [latest release](https://github.com/ronreiter/aidr/releases/latest/download/aidr.zip) (macOS, Apple Silicon)

## Two ways to use it

### 1. The packaged app (for distribution — nothing to install)

Build a self-contained `.app` that bundles Python, llama.cpp, and the model:

```sh
./build.sh          # → dist/aidr.app  (~680 MB, model included)
```

Then move `dist/aidr.app` to `/Applications` and double-click. It runs with
**nothing else installed** — no Python, no Ollama, no downloads.

**Gatekeeper:** release builds are signed with a Developer ID but not
notarized, so on another Mac the first launch needs **right-click the app →
Open → Open** (only once). Local `./build.sh` output is ad-hoc signed; to sign
it yourself: `codesign --deep --force --options runtime -s "Developer ID
Application: …" dist/aidr.app`.

### 2. From source (for development)

```sh
poetry install
poetry run python aidr.py        # or ./aidr
```

The model is downloaded once from Hugging Face (`Qwen/Qwen3-0.6B-GGUF`,
~610 MB) and cached in `~/.cache/huggingface`.

## How it works

1. It lives in the menu bar (a document-with-sparkles icon).
2. Copy 100+ characters in any app.
3. A card drops from the icon: a bold **one-line headline** and, beneath it, a
   **2-3 sentence detailed summary** — from a local **Qwen3-0.6B** model run via
   `llama-cpp-python`. It stays 10 seconds or until you click it, and never
   steals focus. Your clipboard is never modified.

Click the icon for **Copy last summary** and **Quit**.

## Configuration

| Env var           | Default                    | Purpose                                |
|-------------------|----------------------------|----------------------------------------|
| `AIDR_MODEL_PATH` | (unset)                    | Use a specific local `.gguf` file      |
| `AIDR_MODEL_REPO` | `Qwen/Qwen3-0.6B-GGUF`     | Hugging Face repo to download from      |
| `AIDR_MODEL_FILE` | `Qwen3-0.6B-Q8_0.gguf`     | File within that repo                   |
| `AIDR_DEBUG`      | (unset)                    | `1` → log the pipeline to stderr        |

To ship a different/smaller model, drop its `.gguf` in `models/` before
`./build.sh`, or set the env vars above.

macOS only (menu-bar UI + Metal-accelerated llama.cpp).
