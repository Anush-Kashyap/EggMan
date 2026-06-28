from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QSpinBox, QVBoxLayout

from core.settings import SettingsManager


class SettingsDialog(QDialog):
    def __init__(self, settings: SettingsManager, on_saved, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._on_saved = on_saved
        self.setWindowTitle("EggMan Settings")
        self.setMinimumWidth(280)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        form = QFormLayout()
        form.setSpacing(8)

        self._aot_cb = QCheckBox()
        self._aot_cb.setChecked(bool(self._settings.get("always_on_top")))
        form.addRow("Always on top:", self._aot_cb)

        self._w_spin = QSpinBox()
        self._w_spin.setRange(220, 600)
        self._w_spin.setValue(int(self._settings.get("win_w")))
        form.addRow("Window width:", self._w_spin)

        self._h_spin = QSpinBox()
        self._h_spin.setRange(300, 900)
        self._h_spin.setValue(int(self._settings.get("win_h")))
        form.addRow("Window height:", self._h_spin)

        layout.addLayout(form)

        note = QLabel("Window size applies on next launch.")
        note.setStyleSheet("color: #888; font-size: 9px;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self):
        self._settings.set("always_on_top", self._aot_cb.isChecked())
        self._settings.set("win_w", self._w_spin.value())
        self._settings.set("win_h", self._h_spin.value())
        self._settings.save()
        self._on_saved()
        self.accept()
