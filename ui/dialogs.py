from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from backend.ai.ollama_provider import OllamaProvider
from core.config import ConfigManager
from core.settings import SettingsManager


class SettingsDialog(QDialog):
    def __init__(self, settings: SettingsManager, config: ConfigManager, on_saved, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._config = config
        self._on_saved = on_saved
        self.setWindowTitle("EggMan Settings")
        self.setMinimumWidth(320)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        ai_heading = QLabel("Ollama")
        ai_heading.setStyleSheet("font-weight: bold;")
        layout.addWidget(ai_heading)

        ai_form = QFormLayout()
        ai_form.setSpacing(8)

        self._ollama_url = QLineEdit()
        self._ollama_url.setText(str(self._config.get("ollama_base_url")))
        self._ollama_url.setPlaceholderText("http://localhost:11434")
        ai_form.addRow("Base URL:", self._ollama_url)

        self._ollama_model = QLineEdit()
        self._ollama_model.setText(str(self._config.get("ollama_model")))
        self._ollama_model.setPlaceholderText("qwen3:8b")
        ai_form.addRow("Model:", self._ollama_model)

        layout.addLayout(ai_form)

        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._test_btn.clicked.connect(self._test_connection)
        test_row.addWidget(self._test_btn)
        test_row.addStretch()
        layout.addLayout(test_row)

        self._test_status = QLabel("")
        self._test_status.setWordWrap(True)
        self._test_status.setStyleSheet("color: #666; font-size: 9px;")
        layout.addWidget(self._test_status)

        window_heading = QLabel("Window")
        window_heading.setStyleSheet("font-weight: bold;")
        layout.addWidget(window_heading)

        form = QFormLayout()
        form.setSpacing(8)

        self._aot_cb = QCheckBox()
        self._aot_cb.setChecked(bool(self._settings.get("always_on_top")))
        form.addRow("Always on top:", self._aot_cb)

        self._wake_word_cb = QCheckBox()
        self._wake_word_cb.setChecked(bool(self._config.get("wake_word_enabled", True)))
        form.addRow("Enable wake word:", self._wake_word_cb)

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

    def _test_connection(self):
        self._test_btn.setEnabled(False)
        self._test_status.setText("Testing connection...")
        try:
            provider = OllamaProvider(
                base_url=self._ollama_url.text().strip(),
                model_name=self._ollama_model.text().strip(),
            )
            result = provider.test_connection()
            if result.get("ok"):
                models = result.get("available_models") or []
                model_count = len(models)
                self._test_status.setText(
                    f"Connected — using {result.get('model')} ({result.get('elapsed_ms')} ms, {model_count} models available)."
                )
                self._test_status.setStyleSheet("color: #2a6; font-size: 9px;")
            else:
                self._test_status.setText(f"Failed — {result.get('error', 'Unknown error')}")
                self._test_status.setStyleSheet("color: #a33; font-size: 9px;")
        except Exception as exc:
            self._test_status.setText(f"Failed — {exc}")
            self._test_status.setStyleSheet("color: #a33; font-size: 9px;")
        finally:
            self._test_btn.setEnabled(True)

    def _save(self):
        self._config.set("provider", "ollama")
        self._config.set("ollama_base_url", self._ollama_url.text().strip() or OllamaProvider.DEFAULT_BASE_URL)
        self._config.set("ollama_model", self._ollama_model.text().strip() or OllamaProvider.DEFAULT_MODEL)
        self._config.set("wake_word_enabled", self._wake_word_cb.isChecked())
        self._config.save()

        self._settings.set("always_on_top", self._aot_cb.isChecked())
        self._settings.set("win_w", self._w_spin.value())
        self._settings.set("win_h", self._h_spin.value())
        self._settings.save()
        self._on_saved()
        self.accept()
