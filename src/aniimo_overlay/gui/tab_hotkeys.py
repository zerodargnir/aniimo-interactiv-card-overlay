"""Hotkeys tab: one recorder per action, conflict check, reset to defaults."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from aniimo_overlay.config import HotkeysConfig
from aniimo_overlay.gui.tab_display import section
from aniimo_overlay.gui.widgets import HotkeyEdit
from aniimo_overlay.hotkeys import ACTIONS, find_conflicts

if TYPE_CHECKING:
    from aniimo_overlay.app import App

ACTION_LABELS = {
    "toggle_visible": "Afficher / masquer l'overlay",
    "toggle_interactive": "Mode passif / interactif",
    "detect": "Détecter le plan",
    "opacity_up": "Opacité +",
    "opacity_down": "Opacité −",
    "zoom_in": "Zoom de la page +",
    "zoom_out": "Zoom de la page −",
}


class HotkeysTab(QWidget):
    def __init__(self, app: App) -> None:
        super().__init__()
        self.app = app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 14, 4, 4)
        layout.setSpacing(10)
        layout.addWidget(section(self.tr("Raccourcis globaux")))

        hint = QLabel(self.tr("Clique sur un raccourci puis appuie sur la nouvelle combinaison."))
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self.edits: dict[str, HotkeyEdit] = {}
        for row, action in enumerate(ACTIONS):
            grid.addWidget(QLabel(self.tr(ACTION_LABELS[action])), row, 0)
            edit = HotkeyEdit()
            edit.changed.connect(self._on_changed)
            edit.recording_changed.connect(app.set_hotkeys_recording)
            grid.addWidget(edit, row, 1)
            clear = QPushButton(self.tr("Effacer"))
            clear.clicked.connect(lambda _=False, e=edit: self._clear(e))
            grid.addWidget(clear, row, 2)
            self.edits[action] = edit
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self.conflict = QLabel()
        self.conflict.setObjectName("conflict")
        self.conflict.setWordWrap(True)
        self.conflict.hide()
        layout.addWidget(self.conflict)

        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        row = QHBoxLayout()
        reset = QPushButton(self.tr("Rétablir les raccourcis par défaut"))
        reset.clicked.connect(self._reset)
        row.addWidget(reset)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)

    def _current(self) -> dict[str, str]:
        return {action: edit.value() for action, edit in self.edits.items()}

    def _clear(self, edit: HotkeyEdit) -> None:
        edit.set_value("")
        self._on_changed()

    def _reset(self) -> None:
        defaults = HotkeysConfig().as_dict()
        for action, edit in self.edits.items():
            edit.set_value(defaults[action])
        self._on_changed()

    def _on_changed(self, _spec: str = "") -> None:
        mapping = self._current()
        conflicts = find_conflicts(mapping)
        if conflicts:
            lines = [
                " et ".join(f"« {self.tr(ACTION_LABELS[a])} »" for a in actions)
                for actions in conflicts.values()
            ]
            self.conflict.setText(
                self.tr("Conflit : même raccourci pour ")
                + " ; ".join(lines)
                + self.tr(". Non enregistré.")
            )
            self.conflict.show()
            return
        self.conflict.hide()
        self.app.set_hotkeys(mapping)

    def refresh(self) -> None:
        if self.conflict.isVisible():
            return  # keep the user's pending (conflicting) edits on screen
        current = self.app.cfg.hotkeys.as_dict()
        for action, edit in self.edits.items():
            if edit.value() != current[action]:
                edit.set_value(current[action])
        if not self.app.hotkeys.available and self.app.hotkeys.error:
            self.status.setText(self.app.hotkeys.error)
        else:
            self.status.setText("")
