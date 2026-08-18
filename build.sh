#!/bin/bash
# Build the self-contained ai;dr.app (bundles Python, llama.cpp, and the model).
set -e
cd "$(dirname "$0")"
if [ ! -f models/Qwen3-0.6B-Q8_0.gguf ]; then
  echo "Fetching model from Hugging Face…"
  GGUF=$(poetry run python -c "from huggingface_hub import hf_hub_download; print(hf_hub_download('Qwen/Qwen3-0.6B-GGUF','Qwen3-0.6B-Q8_0.gguf'))")
  mkdir -p models && cp "$GGUF" models/
fi
poetry run pyinstaller --noconfirm --clean aidr.spec
echo "Built dist/aidr.app  ($(du -sh dist/aidr.app | cut -f1))"
