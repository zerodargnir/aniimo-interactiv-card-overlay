"""About tab: version, credits, disclaimer, logs and detection debug."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from aniimo_overlay import APP_NAME, __version__, paths
from aniimo_overlay.gui.tab_display import section

if TYPE_CHECKING:
    from aniimo_overlay.app import App


class AboutTab(QWidget):
    def __init__(self, app: App) -> None:
        super().__init__()
        self.app = app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 14, 4, 4)
        layout.setSpacing(10)

        title = QLabel(f"<b>{APP_NAME}</b> — version {__version__}")
        layout.addWidget(title)
        credits = QLabel(
            self.tr(
                'Carte fournie par <a href="https://aniimotools.dev" style="color:#4c8dff">aniimotools.dev</a>, '
                "site de fans non officiel.<br>"
                "Outil non affilié à Pawprint Studio / FunPlus."
            )
        )
        credits.setOpenExternalLinks(True)
        credits.setWordWrap(True)
        layout.addWidget(credits)

        layout.addSpacing(4)
        layout.addWidget(section(self.tr("Utilisation")))
        usage = QLabel(
            self.tr(
                "• Le jeu doit être en <b>plein écran fenêtré</b> (borderless) : un overlay ne peut pas "
                "s'afficher par-dessus un plein écran exclusif.<br>"
                "• Ouvre la carte en jeu puis appuie sur le raccourci « Détecter le plan ».<br>"
                "• Si le jeu tourne en administrateur, lance aussi l'overlay en administrateur, "
                "sinon les raccourcis ne marchent pas."
            )
        )
        usage.setObjectName("muted")
        usage.setWordWrap(True)
        layout.addWidget(usage)

        layout.addSpacing(4)
        layout.addWidget(section(self.tr("Diagnostic")))
        self.debug = QCheckBox(
            self.tr("Mode debug détection (enregistre captures et masques dans les logs)")
        )
        self.debug.toggled.connect(app.set_debug_detection)
        layout.addWidget(self.debug)
        row = QHBoxLayout()
        logs = QPushButton(self.tr("Ouvrir le dossier des logs"))
        logs.clicked.connect(app.open_log_dir)
        row.addWidget(logs)
        row.addStretch(1)
        layout.addLayout(row)
        where = QLabel(self.tr("Réglages : %s") % paths.config_file())
        where.setObjectName("muted")
        where.setWordWrap(True)
        layout.addWidget(where)
        layout.addStretch(1)

    def refresh(self) -> None:
        self.debug.blockSignals(True)
        self.debug.setChecked(self.app.cfg.detection.debug)
        self.debug.blockSignals(False)
