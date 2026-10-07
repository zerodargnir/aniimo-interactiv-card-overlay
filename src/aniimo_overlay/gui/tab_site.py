"""Site tab: page URL / language, reload, open in the browser."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from aniimo_overlay.bridge.site import LANGUAGES, build_url, language_of
from aniimo_overlay.gui.tab_display import section

if TYPE_CHECKING:
    from aniimo_overlay.app import App


class SiteTab(QWidget):
    def __init__(self, app: App) -> None:
        super().__init__()
        self.app = app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 14, 4, 4)
        layout.setSpacing(10)
        layout.addWidget(section(self.tr("Page affichée")))

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        self.language = QComboBox()
        for code, label in LANGUAGES.items():
            self.language.addItem(label, code)
        self.language.addItem(self.tr("Personnalisée"), "")
        self.language.activated.connect(self._on_language)
        self.url = QLineEdit()
        self.url.editingFinished.connect(lambda: app.set_url(self.url.text()))
        form.addRow(self.tr("Langue"), self.language)
        form.addRow(self.tr("Adresse"), self.url)
        layout.addLayout(form)

        row = QHBoxLayout()
        reload_button = QPushButton(self.tr("Recharger la page"))
        reload_button.clicked.connect(app.reload_page)
        browser = QPushButton(self.tr("Ouvrir dans le navigateur"))
        browser.clicked.connect(app.open_in_browser)
        row.addWidget(reload_button)
        row.addWidget(browser)
        row.addStretch(1)
        layout.addLayout(row)

        layout.addSpacing(4)
        layout.addWidget(section(self.tr("Bon à savoir")))
        tips = QLabel(
            self.tr(
                "• Choisis la difficulté une fois sur la page (en mode interactif) : le site s'en souvient.\n"
                "• La page est chargée une seule fois ; le bouton « Recharger » ne sert qu'en cas de problème.\n"
                "• Tes préférences et ta connexion au site sont conservées entre deux lancements."
            )
        )
        tips.setObjectName("muted")
        tips.setWordWrap(True)
        layout.addWidget(tips)
        layout.addStretch(1)

    def _on_language(self, _index: int) -> None:
        code = self.language.currentData()
        if code:
            url = build_url(code)
            self.url.setText(url)
            self.app.set_url(url)
        else:
            self.url.setFocus()

    def refresh(self) -> None:
        url = self.app.cfg.site.url
        if not self.url.hasFocus():
            self.url.setText(url)
        code = language_of(url) or ""
        index = self.language.findData(code)
        self.language.setCurrentIndex(index if index >= 0 else self.language.count() - 1)
