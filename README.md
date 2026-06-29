# 🥚 EggMan

> **Your Premium Emotional AI Desktop Companion**

EggMan is an AI-powered desktop companion built with **Python** and **PySide6**. Instead of being just another chatbot, EggMan is designed to live on your desktop, interact naturally, express emotions, remember conversations, listen to voice commands, and see your workspace—growing alongside you over time.

---

## 🚀 Key Features

### 🎙️ Continuous Wake-Word & Voice Interaction
- **Wake Word Activation**: Say `"Alexa"` to trigger silent, continuous voice listening (sound confirmation removed for a natural flow).
- **Local Speech-to-Text**: Powered by **Whisper** (`faster-whisper` model `base` on CPU under `int8` quantization) for high-performance offline transcription.
- **Wake Word Settings**: Toggle voice activation on or off dynamically in the settings menu.
- **Thread Stability**: Wake-word background capture runs in a dedicated thread initialized after the Qt event loop becomes active to prevent device driver conflicts.

### 📸 Explicit Vision & Screenshot Attachment
- **Explicit Workflow**: Capture your screen explicitly using the GUI screenshot button or the `"Take Screenshot"` command (typed or spoken).
- **Interactive Floating Preview**: Immediately spawns a frameless, top-level preview panel at the top-right of your screen showing:
  - Captioned screenshot thumbnail.
  - Action buttons:
    - **`Ask About`**: Submits whatever custom question you typed in the input bar alongside the screenshot. If the text bar is empty, EggMan lets you know: *"There is no command given for the screenshot"*.
    - **`Remove`**: Discards the pending screenshot.
- **Automatic Model Switcher**: Uses local Ollama model **`qwen2.5vl:7b`** automatically for image-based queries while defaulting to **`qwen3:8b`** for standard text chats.
- **Auto-Cleanup**: The pending attachment is automatically consumed and cleared on the next message submission.

### 🧠 Persistent Long-Term Memory & Tool Integration
- Extracts facts and preferences from your chats dynamically to build a long-term semantic memory.
- Executes native operating system tools (e.g. launching Apps like Spotify, Notepad, Chrome) using a modular Tool Router.

---

## 📁 Project Structure

```text
Eggman/
│
├── app/               # Application containers and initializers
├── assets/            # Images, icons, and theme files
├── backend/           # Core background engines
│   ├── ai/            # Provider routing and model APIs (Gemini & Ollama)
│   ├── memory/        # Semantic memory systems
│   ├── tools/         # OS execution tools
│   ├── vision/        # Screenshot capturing and VisionManager
│   └── voice/         # Whisper SpeechToText and openWakeWord services
├── core/              # Theme managers, configurations, and core loops
├── ui/                # PySide6 desktop views, widgets, and dialogs
├── tests/             # PyTest regression suites
├── main.py            # Application entry point
├── EggMan.spec        # PyInstaller packaging configuration
└── requirements.txt   # Dependency requirements
```

---

## 🧰 Tech Stack

| Technology       | Purpose                                                    |
| ---------------- | ---------------------------------------------------------- |
| **Python 3.11**  | Main programming language                                  |
| **PySide6**      | Translucent desktop companion widgets and settings views   |
| **Ollama**       | Local inference engines (`qwen3:8b` & `qwen2.5vl:7b`)      |
| **faster-whisper**| Local speech transcription (VAD-enabled)                  |
| **openWakeWord** | Background continuous wake word recognition                |
| **SQLite**       | Fact retention & semantic memory database                  |
| **PyInstaller**  | Single-bundle standalone packaging                          |

---

## 💻 Quick Start (Development)

1. **Install Virtual Environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **Run Inference Servers**:
   Make sure Ollama is running locally:
   ```bash
   ollama pull qwen3:8b
   ollama pull qwen2.5vl:7b
   ```
3. **Launch EggMan**:
   ```bash
   python main.py
   ```
4. **Run Unit Tests**:
   ```bash
   python -m pytest
   ```

---

## 📦 Standalone Packaging

EggMan compiles into a standalone portable application directory using PyInstaller.

To compile:
```bash
pyinstaller -y EggMan.spec
```
The output directory will be created at **`dist/EggMan/`**. You can run **`EggMan.exe`** directly from there. The specification configuration handles embedding all Whisper ONNX dependencies and the pre-trained `openWakeWord` models inside the `_internal` package directories.
