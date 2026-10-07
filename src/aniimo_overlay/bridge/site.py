"""Everything that knows about aniimotools.dev: URL, how to pick a direction, scrolling.

The page is driven like a user would: scroll to the "Quel plan ?" selector, press the
numpad key, and (only if the key did not register) click the matching direction button.
Nothing is read from the page except whether the navigation elements exist / are pressed.
"""

from __future__ import annotations

import json
import logging

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication

log = logging.getLogger(__name__)

SITE_ROOT = "https://aniimotools.dev"
PAGE_PATH = "/map/lost-sanctum/"
DEFAULT_LANG = "fr"
# Language code -> label. English is served without a language prefix.
LANGUAGES: dict[str, str] = {
    "fr": "Français",
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "pt-br": "Português (Brasil)",
    "ru": "Русский",
    "th": "ไทย",
    "vi": "Tiếng Việt",
    "zh-cn": "简体中文",
}

# CSS selectors of the page (found with the DevTools, October 2026).
# MAY BREAK IF THE SITE CHANGES: update them here only.
SELECTORS = {
    "finder": ".ls-find",  # the "Quel plan ?" block
    "overview": "[data-overview]",  # overview section the numpad shortcut listens on
    "active_pad": "[data-pad]:not([hidden])",  # direction pad of the selected difficulty
    "direction_button": '[data-dir="{sector}"]',  # one button per compass direction
    "back_button": "[data-back]",  # "back" button of an opened plan (returns to overview)
}

KEY_SETTLE_MS = 350  # wait after scrolling / key press before checking the result

_KEYPAD_KEYS = {
    1: Qt.Key.Key_1,
    2: Qt.Key.Key_2,
    3: Qt.Key.Key_3,
    4: Qt.Key.Key_4,
    6: Qt.Key.Key_6,
    7: Qt.Key.Key_7,
    8: Qt.Key.Key_8,
    9: Qt.Key.Key_9,
}


def build_url(lang: str) -> str:
    lang = lang if lang in LANGUAGES else DEFAULT_LANG
    return SITE_ROOT + ("" if lang == "en" else f"/{lang}") + PAGE_PATH


def language_of(url: str) -> str | None:
    """Language of a site URL, None if the URL is not a known page of the site."""
    for lang in LANGUAGES:
        if url.rstrip("/") == build_url(lang).rstrip("/"):
            return lang
    return None


# Returns the state of the direction button (as JSON), without reading any page content.
_STATE_JS = """
JSON.stringify((() => {
  const S = %(selectors)s;
  const finder = document.querySelector(S.finder);
  const overview = document.querySelector(S.overview);
  if (!finder || !overview) return {ok: false, reason: "missing"};
  if (overview.getClientRects().length === 0) return {ok: false, reason: "hidden"};
  const pad = document.querySelector(S.active_pad);
  const btn = pad && pad.querySelector(S.direction_button.replace("{sector}", %(sector)s));
  if (!btn) return {ok: false, reason: "no-button"};
  return {ok: true, disabled: btn.disabled, pressed: btn.getAttribute("aria-pressed") === "true"};
})())
"""

_SCROLL_JS = """
(() => {
  const el = document.querySelector(%(selector)s);
  if (!el) return false;
  el.scrollIntoView({block: "center", behavior: "instant"});
  return true;
})()
"""

_CLICK_JS = """
(() => {
  const pad = document.querySelector(%(pad)s);
  const btn = pad && pad.querySelector(%(button)s);
  if (!btn || btn.disabled) return false;
  btn.click();
  return true;
})()
"""

_BACK_JS = """
(() => {
  const btn = [...document.querySelectorAll(%(selector)s)].find(b => b.getClientRects().length);
  if (!btn) return false;
  btn.click();
  return true;
})()
"""

MAX_KEY_ATTEMPTS = 2


def _parse_state(raw) -> dict:
    try:
        state = json.loads(raw) if isinstance(raw, str) and raw else None
    except ValueError:
        state = None
    return state if isinstance(state, dict) else {"ok": False, "reason": "error"}


class SiteBridge(QObject):
    """Drives the page inside the overlay's web view."""

    status = Signal(str)  # user-facing French message

    def __init__(self, view: QWebEngineView, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._view = view
        self._loaded = False
        self._pending: tuple[str, int | None] | None = None
        view.loadFinished.connect(self._on_load_finished)

    # --- loading ------------------------------------------------------------------

    def load(self, url: str) -> None:
        """Load the page once. Called at start-up and when the user changes URL / reloads."""
        self._loaded = False
        log.info("Loading %s", url)
        self._view.setUrl(QUrl(url))

    def reload(self) -> None:
        self._loaded = False
        self._view.reload()

    def _on_load_finished(self, ok: bool) -> None:
        self._loaded = ok
        if not ok:
            self.status.emit(self.tr("Page aniimotools.dev non chargée (connexion ?)"))
            return
        self.scroll_to_selector()
        if self._pending:
            (sector, numpad), self._pending = self._pending, None
            self.select_direction(sector, numpad)

    # --- navigation ---------------------------------------------------------------

    def scroll_to_selector(self) -> None:
        js = _SCROLL_JS % {"selector": json.dumps(SELECTORS["finder"])}
        self._view.page().runJavaScript(js, 0, self._on_scrolled)

    def _on_scrolled(self, ok) -> None:
        if not ok:
            log.warning("Selector %r not found on the page", SELECTORS["finder"])

    def select_direction(self, sector: str, numpad: int | None = None) -> None:
        """Ask the site to show the plan(s) for this blue-door direction."""
        if not self._loaded:
            self._pending = (sector, numpad)
            self.status.emit(self.tr("Page en cours de chargement…"))
            return
        self._query_state(sector, lambda st: self._after_state(sector, numpad, st, False))

    def _query_state(self, sector: str, callback) -> None:
        js = _STATE_JS % {"selectors": json.dumps(SELECTORS), "sector": json.dumps(sector)}
        self._view.page().runJavaScript(js, 0, lambda raw: callback(_parse_state(raw)))

    def _after_state(self, sector: str, numpad: int | None, state: dict, went_back: bool) -> None:
        if not state.get("ok"):
            reason = state.get("reason")
            if reason == "hidden" and not went_back:
                # A plan is open: press its "back" button like a user, then retry.
                js = _BACK_JS % {"selector": json.dumps(SELECTORS["back_button"])}
                self._view.page().runJavaScript(
                    js,
                    0,
                    lambda _ok: QTimer.singleShot(
                        KEY_SETTLE_MS,
                        lambda: self._query_state(
                            sector, lambda st: self._after_state(sector, numpad, st, True)
                        ),
                    ),
                )
                return
            log.warning("Direction selector unavailable (%s)", reason)
            if reason == "hidden":
                self.status.emit(self.tr("Reviens à la vue d'ensemble des plans sur la page"))
            else:
                self.status.emit(
                    self.tr("Sélecteur « Quel plan ? » introuvable (le site a peut-être changé)")
                )
            return
        self.scroll_to_selector()
        if state.get("disabled"):
            self.status.emit(self.tr("Aucun plan dans cette direction pour cette difficulté"))
            return
        QTimer.singleShot(KEY_SETTLE_MS, lambda: self._press_key(sector, numpad, 1))

    def _press_key(self, sector: str, numpad: int | None, attempt: int) -> None:
        if numpad not in _KEYPAD_KEYS:
            self._click_button(sector)
            return
        target = self._view.focusProxy() or self._view
        for event_type in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            event = QKeyEvent(
                event_type, _KEYPAD_KEYS[numpad], Qt.KeyboardModifier.KeypadModifier, str(numpad)
            )
            QApplication.sendEvent(target, event)
        QTimer.singleShot(
            KEY_SETTLE_MS,
            lambda: self._query_state(
                sector, lambda st: self._after_key(sector, numpad, attempt, st)
            ),
        )

    def _after_key(self, sector: str, numpad: int, attempt: int, state: dict) -> None:
        # Done when the direction is selected, or when the site opened the only matching
        # plan (the overview is then hidden).
        if state.get("pressed") or state.get("reason") == "hidden":
            return
        if attempt < MAX_KEY_ATTEMPTS:
            # The key may have toggled an already selected direction off: press again.
            self._press_key(sector, numpad, attempt + 1)
            return
        log.info("Numpad key not taken into account, clicking the %s button instead", sector)
        self._click_button(sector)

    def _click_button(self, sector: str) -> None:
        js = _CLICK_JS % {
            "pad": json.dumps(SELECTORS["active_pad"]),
            "button": json.dumps(SELECTORS["direction_button"].replace("{sector}", sector)),
        }
        self._view.page().runJavaScript(js, 0, self._after_click)

    def _after_click(self, ok) -> None:
        if not ok:
            self.status.emit(self.tr("Impossible de sélectionner la direction sur la page"))
