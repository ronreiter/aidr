#!/usr/bin/env python3
"""ai;dr — AI; didn't read (macOS menu-bar edition).

Lives in the menu bar. Copy any text (100+ characters) anywhere and a small
floating card drops from the ai;dr icon with a one-line headline plus a couple
of sentences of detail, distilled by a small language model that runs
**in-process** — no server, no Ollama, no network once the model is present.
The card stays for 10 seconds, or until you click it. No window, no typing,
no buttons, and it never steals focus.

The model (Qwen3-0.6B GGUF) is loaded from the app bundle when packaged, or
downloaded once from Hugging Face and cached when run from source. macOS only.
"""

import os
import queue
import re
import sys
import threading
import webbrowser

import objc
import rumps
from AppKit import (
    NSAttributedString,
    NSClickGestureRecognizer,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSImage,
    NSMutableAttributedString,
    NSMutableParagraphStyle,
    NSPanel,
    NSParagraphStyleAttributeName,
    NSPasteboard,
    NSPasteboardTypeString,
    NSScreen,
    NSTextField,
    NSVisualEffectView,
)
from Foundation import NSMakePoint, NSMakeRect, NSMakeSize, NSObject

# AppKit enum values (stable) — declared as literals to avoid import churn.
NS_BORDERLESS = 0
NS_NONACTIVATING_PANEL = 1 << 7  # NSWindowStyleMaskNonactivatingPanel
NS_BACKING_BUFFERED = 2
NS_STATUS_WINDOW_LEVEL = 25  # float above ordinary windows
NS_COLLECTION = 1 | 16 | 256  # CanJoinAllSpaces | Stationary | FullScreenAuxiliary
NS_VE_MATERIAL_POPOVER = 6
NS_VE_STATE_ACTIVE = 1
NS_VE_BLEND_BEHIND = 0
NS_WORD_WRAP = 0  # NSLineBreakByWordWrapping

# Menu-bar icon: an SF Symbol (document + sparkles = "summarize"). Tried in order.
ICON_SYMBOLS = [
    "sparkles.rectangle.stack",  # a page/stack with sparkles
    "doc.text.magnifyingglass",
    "wand.and.sparkles",
    "sparkles",
]
ICON_HEIGHT = 17.0

# Model: a small Qwen3 GGUF, run in-process via llama.cpp.
MODEL_REPO = os.environ.get("AIDR_MODEL_REPO", "Qwen/Qwen3-0.6B-GGUF")
MODEL_FILE = os.environ.get("AIDR_MODEL_FILE", "Qwen3-0.6B-Q8_0.gguf")
MODEL_PATH = os.environ.get("AIDR_MODEL_PATH")  # explicit override

MIN_CHARS = 100
MAX_INPUT_CHARS = 16_000  # keep well under the context window
N_CTX = 8192
POLL_SECONDS = 0.4  # clipboard check interval
POPUP_SECONDS = 10.0  # how long the card stays before auto-hiding
CARD_WIDTH = 400
PAD = 16

WEBSITE = os.environ.get("AIDR_WEBSITE", "https://ronreiter.github.io/aidr/")

HEADLINE_PROMPT = (
    "You are ai;dr (AI; didn't read). Distill the text into its single "
    "essential point on ONE short line, in the fewest words possible - aim "
    "for under 12 words. Be blunt. No preamble, no quotes, no explanation. "
    "If the text has no discernible point, say so in 5 words or fewer."
)
DETAIL_PROMPT = (
    "You are ai;dr. Summarize the text in 2-3 short, factual sentences that "
    "capture the key points someone would need. No preamble, no headings, no "
    "bullet symbols, no quotes - just the sentences."
)


def _dbg(msg):
    if os.environ.get("AIDR_DEBUG"):
        print(f"[aidr] {msg}", file=sys.stderr, flush=True)


class SummarizeError(Exception):
    pass


def resolve_model_path():
    """Bundled model (packaged app) first, else download from Hugging Face (cached)."""
    if MODEL_PATH and os.path.exists(MODEL_PATH):
        return MODEL_PATH
    # py2app sets RESOURCEPATH; PyInstaller sets sys._MEIPASS.
    for base in (os.environ.get("RESOURCEPATH"), getattr(sys, "_MEIPASS", None),
                 os.path.dirname(os.path.abspath(__file__))):
        if base:
            cand = os.path.join(base, "models", MODEL_FILE)
            if os.path.exists(cand):
                return cand
    from huggingface_hub import hf_hub_download
    _dbg(f"downloading {MODEL_REPO}/{MODEL_FILE} from Hugging Face…")
    return hf_hub_download(MODEL_REPO, MODEL_FILE)


def load_model():
    from llama_cpp import Llama

    path = resolve_model_path()
    _dbg(f"loading model {path}")
    return Llama(model_path=path, n_ctx=N_CTX, n_gpu_layers=-1, verbose=False)


def _complete(llm, system, text, max_tokens):
    out = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": text + " /no_think"},  # skip Qwen3 reasoning
        ],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    answer = out["choices"][0]["message"]["content"]
    answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL)
    # Collapse whitespace per line but keep the model's line breaks (lists).
    lines = (" ".join(line.split()) for line in answer.splitlines())
    return "\n".join(line for line in lines if line)


def summarize(llm, text):
    """Return (headline, detail): a one-liner and a 2-3 sentence summary."""
    text = text.strip()
    if len(text) < MIN_CHARS:
        raise SummarizeError(
            f"Only {len(text)} characters - ai;dr needs at least {MIN_CHARS}."
        )
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]
    headline = " ".join(_complete(llm, HEADLINE_PROMPT, text, 48).split())
    detail = _break_numbered_items(_complete(llm, DETAIL_PROMPT, text, 200))
    return headline, detail


def _break_numbered_items(text):
    """Put inline '1. ... 2. ... 3. ...' enumerations on lines of their own."""
    if len(re.findall(r"(?:^|\s)\d{1,2}\.\s+[A-Z\d]", text)) < 2:
        return text
    return re.sub(r"[ \t]+(?=\d{1,2}\.\s+[A-Z\d])", "\n", text)


def make_menu_icon():
    """A monochrome template image from the first SF Symbol that resolves."""
    for name in ICON_SYMBOLS:
        img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, "ai;dr")
        if img is not None:
            size = img.size()
            if size.height:
                scale = ICON_HEIGHT / size.height
                img.setSize_(NSMakeSize(size.width * scale, ICON_HEIGHT))
            img.setTemplate_(True)
            _dbg(f"icon symbol: {name}")
            return img
    return None


class _CardController(NSObject):
    """ObjC target (rumps.App isn't an NSObject) for click-to-dismiss and the
    one-shot auto-close. Uses performSelector:afterDelay: — a real one-shot on
    the main run loop, unlike rumps.Timer which fires immediately on start."""

    def initWithPanel_(self, panel):
        self = objc.super(_CardController, self).init()
        if self is None:
            return None
        self._panel = panel
        return self

    def arm_(self, seconds):
        NSObject.cancelPreviousPerformRequestsWithTarget_(self)
        self.performSelector_withObject_afterDelay_("hide:", None, float(seconds))

    def hide_(self, _sender):
        if self._panel is not None:
            self._panel.orderOut_(None)
        _dbg("card hidden")


class AidrApp(rumps.App):
    def __init__(self):
        super().__init__("ai;dr", title="✨", quit_button="Quit ai;dr")
        self.menu = ["About ai;dr…", None, "Show clipboard summary", "Copy last summary"]
        self.busy = False
        self.last_result = ""  # full headline + detail, for "Copy last summary" + dedup
        self.last_headline = ""  # kept separately so the card can be re-shown
        self.last_detail = None
        self.queue = queue.Queue()
        self._llm = None
        self._llm_lock = threading.Lock()
        self._icon_set = False
        self._panel = None
        self._label = None
        self._card = None
        self._last_change = NSPasteboard.generalPasteboard().changeCount()

        self._clip_timer = rumps.Timer(self._poll_clipboard, POLL_SECONDS)
        self._clip_timer.start()
        self._drain_timer = rumps.Timer(self._drain, 0.1)
        self._drain_timer.start()
        threading.Thread(target=self._ensure_llm, daemon=True).start()
        _dbg("started")

    def _ensure_llm(self):
        with self._llm_lock:
            if self._llm is None:
                self._llm = load_model()
                _dbg("model ready")
        return self._llm

    def _ensure_icon(self):
        if self._icon_set:
            return
        try:
            button = self._nsapp.nsstatusitem.button()
        except Exception:
            return
        if button is None:
            return
        img = make_menu_icon()
        if img is not None:
            button.setImage_(img)
            button.setTitle_("")
        self._icon_set = True

    @rumps.clicked("Show clipboard summary")
    def _show_last(self, _sender):
        if self.last_headline:
            self._show_card(self.last_headline, self.last_detail)
        else:
            self._show_card("Nothing summarized yet.", None)

    @rumps.clicked("About ai;dr…")
    def _about(self, _sender):
        webbrowser.open(WEBSITE)

    @rumps.clicked("Copy last summary")
    def _copy_last(self, _sender):
        if self.last_result:
            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setString_forType_(self.last_result, NSPasteboardTypeString)
            self._last_change = pb.changeCount()  # don't summarize our own copy

    # --- clipboard watch ---

    def _poll_clipboard(self, _timer):
        self._ensure_icon()
        pb = NSPasteboard.generalPasteboard()
        count = pb.changeCount()
        if count == self._last_change:
            return
        self._last_change = count
        text = (pb.stringForType_(NSPasteboardTypeString) or "").strip()
        if len(text) < MIN_CHARS or text == self.last_result or self.busy:
            _dbg(f"ignored copy (len={len(text)}, busy={self.busy})")
            return
        _dbg(f"new copy len={len(text)} -> summarizing")
        self.busy = True
        self._show_card("ai;dr…", None)
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()

    def _worker(self, text):
        """Off the main thread — model load + inference, then hand back via the queue."""
        try:
            llm = self._ensure_llm()
            headline, detail = summarize(llm, text)
        except SummarizeError as e:
            self.queue.put(("err", str(e)))
        except Exception as e:  # model load / inference failure
            self.queue.put(("err", f"Model error: {e}"))
        else:
            self.queue.put(("ok", headline, detail))

    def _drain(self, _timer):
        try:
            item = self.queue.get_nowait()
        except queue.Empty:
            return
        self.busy = False
        if item[0] == "err":
            self._show_card(item[1], None)
        else:
            _, headline, detail = item
            self.last_result = f"{headline}\n\n{detail}".strip()
            self.last_headline, self.last_detail = headline, detail
            _dbg(f"result: {headline!r} / {detail!r}")
            self._show_card(headline, detail)

    # --- the dropdown (a floating panel under the menu-bar item) ---

    def _ensure_card(self):
        if self._panel is not None:
            return
        rect = NSMakeRect(0, 0, CARD_WIDTH, 100)
        style = NS_BORDERLESS | NS_NONACTIVATING_PANEL
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, style, NS_BACKING_BUFFERED, False
        )
        panel.setLevel_(NS_STATUS_WINDOW_LEVEL)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        panel.setHasShadow_(True)
        panel.setHidesOnDeactivate_(False)  # don't vanish when we're not the active app
        panel.setReleasedWhenClosed_(False)
        panel.setFloatingPanel_(True)
        panel.setBecomesKeyOnlyIfNeeded_(True)
        panel.setCollectionBehavior_(NS_COLLECTION)

        effect = NSVisualEffectView.alloc().initWithFrame_(rect)
        effect.setMaterial_(NS_VE_MATERIAL_POPOVER)
        effect.setState_(NS_VE_STATE_ACTIVE)
        effect.setBlendingMode_(NS_VE_BLEND_BEHIND)
        effect.setWantsLayer_(True)
        effect.layer().setCornerRadius_(12.0)
        effect.layer().setMasksToBounds_(True)

        label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(PAD, PAD, CARD_WIDTH - 2 * PAD, 40)
        )
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(True)
        label.cell().setWraps_(True)
        label.cell().setLineBreakMode_(NS_WORD_WRAP)
        effect.addSubview_(label)

        panel.setContentView_(effect)
        self._card = _CardController.alloc().initWithPanel_(panel)
        gesture = NSClickGestureRecognizer.alloc().initWithTarget_action_(
            self._card, "hide:"
        )
        effect.addGestureRecognizer_(gesture)
        self._panel, self._label = panel, label

    def _card_text(self, headline, detail):
        """Bold headline + a smaller, dimmer detail paragraph as one attributed string."""
        s = NSMutableAttributedString.alloc().init()
        s.appendAttributedString_(
            NSAttributedString.alloc().initWithString_attributes_(
                headline,
                {
                    NSFontAttributeName: NSFont.boldSystemFontOfSize_(15),
                    NSForegroundColorAttributeName: NSColor.labelColor(),
                },
            )
        )
        if detail:
            detail_attrs = {
                NSFontAttributeName: NSFont.systemFontOfSize_(12),
                NSForegroundColorAttributeName: NSColor.secondaryLabelColor(),
            }
            list_style = NSMutableParagraphStyle.alloc().init()
            list_style.setHeadIndent_(18.0)  # wrapped lines align past the "1. "
            for i, line in enumerate(detail.split("\n")):
                attrs = dict(detail_attrs)
                if re.match(r"\d{1,2}\.\s", line):
                    attrs[NSParagraphStyleAttributeName] = list_style
                prefix = "\n\n" if i == 0 else "\n"
                s.appendAttributedString_(
                    NSAttributedString.alloc().initWithString_attributes_(
                        prefix + line, attrs
                    )
                )
        return s

    def _show_card(self, headline, detail):
        self._ensure_card()
        inner = CARD_WIDTH - 2 * PAD
        self._label.setAttributedStringValue_(self._card_text(headline, detail))
        fit = self._label.cell().cellSizeForBounds_(NSMakeRect(0, 0, inner, 10_000))
        h = max(22, min(int(fit.height) + 2, 460))
        total = h + 2 * PAD
        self._label.setFrame_(NSMakeRect(PAD, PAD, inner, h))
        self._panel.setContentSize_(NSMakeSize(CARD_WIDTH, total))

        x, y = self._anchor(total)
        self._panel.setFrameOrigin_(NSMakePoint(x, y))
        self._panel.orderFrontRegardless()
        self._card.arm_(POPUP_SECONDS)  # one-shot auto-close, resets on each show
        _dbg(f"card visible={self._panel.isVisible()} at ({int(x)},{int(y)})")

    def _anchor(self, total):
        """Top-right, just under the menu bar, aligned to the status item if we can find it."""
        try:
            frame = self._nsapp.nsstatusitem.button().window().frame()
            x = frame.origin.x + frame.size.width - CARD_WIDTH
            y = frame.origin.y - total - 6
            return x, y
        except Exception:
            scr = NSScreen.mainScreen().frame()
            return scr.size.width - CARD_WIDTH - 16, scr.size.height - total - 40


if __name__ == "__main__":
    AidrApp().run()
