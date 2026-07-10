# 🥚 EggMan v0.7

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Framework: PySide6](https://img.shields.io/badge/framework-PySide6-green.svg?style=for-the-badge&logo=qt&logoColor=white)](https://wiki.qt.io/Qt_for_Python)
[![Backend: Local Ollama](https://img.shields.io/badge/backend-Ollama-orange.svg?style=for-the-badge&logo=ollama&logoColor=white)](https://ollama.com/)
[![Tests: Pytest](https://img.shields.io/badge/tests-Pytest-yellow.svg?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)

> **The Ultimate Local, Emotional AI Desktop Companion**  
> EggMan is a premium, fully offline AI assistant that lives directly on your desktop. Combining real-time streaming, local vector storage, an advanced persistent memory system, wake-word activation, screen vision, and dynamic persona overlays, EggMan delivers a desktop assistant experience that is private, highly reactive, and responsive.

---

## 📖 Table of Contents
1. [🚀 Core Modules in Version 0.7](#-core-modules-in-version-0.7)
2. [🧠 Memory System v2](#-memory-system-v2)
3. [🧩 Prompt Builder v2](#-prompt-builder-v2)
4. [⚡ Event Bus Infrastructure](#-event-bus-infrastructure)
5. [🗃️ Capability & Tool Registry V2](#-capability--tool-registry-v2)
6. [📁 Repository Structure](#-repository-structure)
7. [💻 Developer Quick Start](#-developer-quick-start)
8. [📦 PyInstaller Bundling](#-pyinstaller-bundling)

---

## 🚀 Core Modules in Version 0.7

### ⚡ Fluid Token Streaming & Micro-Animations
- **Zero-Latency Rendering:** Tokens are written directly to the screen as soon as they are received from the local Ollama stream, bypassing all buffer lag.
- **Micro-Animations:** Custom-rendered words feature a smooth, lightweight fade-in combined with a vertical slide glide (150ms) to enhance readability.
- **Smart Sizing Policies:** Message bubbles scale up to **72% of the active window width** for paragraphs and technical code, while shrinking to fit short one-liners.

### 🎭 Floating Persona Selector
- **Title Bar Integration:** Triggered via a `🎭` icon on the right side of the Title Bar.
- **Smooth Popup Transition:** Cards cascade with a staggered 60ms slide-in spring animation from right-to-left.
- **Click-to-Dismiss:** Closes automatically on select or when clicking outside.

### 📦 Ollama Model Auto-Pulling
- **Eager Background Pulling:** If `nomic-embed-text` is missing during startup or indexing, EggMan automatically triggers a background API pull from Ollama to download it on-demand without blocking GUI operations.

---

## 🧠 Memory System v2

EggMan v0.6 features an intelligent long-term memory system that stores, classifies, retrieves, and maintains memories naturally:
- **8 Memory Categories:** Auto-classifies user statements into `Preferences`, `Goals`, `Habits`, `Skills`, `Projects`, `Personal Facts`, `Temporary`, and `Permanent`.
- **0-100 Importance Scoring:** Evaluates relevance using dynamic heuristics (explicitness, category weights, user keywords).
- **Conflict Resolution:** Automatically detects overlapping preferences (e.g. changing IDEs, OS, languages) and deactivates/supersedes old records, preserving a historical chain.
- **Lazy Expiration:** Automatically sweeps and deactivates temporary memories (e.g., "I'm travelling this week") after a 48-hour duration.
- **Multi-Factor Ranking:** Sorts retrieval using relevance (40%), importance (30%), recency (15%), confidence (10%), and category boosts (5%).

---

## 🧩 Prompt Builder v2

To avoid system prompt bloat and improve response speed, EggMan utilizes a registry-driven prompt builder:
- **Modular LEGO Structure:** Dynamically selects only applicable prompt blocks (e.g., Vision rules are omitted unless an image is attached; Memory rules are omitted if no memories are retrieved).
- **Static Caching:** Static modules (Core Identity, Communication Style) are cached at compile time.
- **Qualifying Inferences:** Low-confidence inferences are prefixed with `(Possible)` inside the prompt so the LLM does not state them as absolute facts.

---

## ⚡ Event Bus Infrastructure

EggMan v0.7 introduces a custom, production-ready **Event Bus System** that serves as the decoupled communication backbone of the companion:
- **Strongly-Typed Event Objects:** Communication uses BaseEvent subclasses (e.g. `StartupTaskStartedEvent`, `StartupTaskCompletedEvent`) instead of raw strings.
- **Concurrently Thread-Safe:** Employs reentrant locking (`threading.RLock`) to safely register callbacks and dispatch events across parallel background threads.
- **Exception Isolation:** Guarantees that callback failures in one subscriber do not block the publication flow to other modules.
- **Proof-of-Concept Integration:** Migrated the **Startup System** to decoupled Event Bus notifications to coordinate thread-safe UI state updates.

---

## 🗃️ Capability & Tool Registry (v0.7)

EggMan v0.7 implements a highly extensible **Registry Subsystem** designed to eliminate hardcoded feature lists and modularize the runtime environment:
- **BaseRegistry Backbone:** Standardizes operations (`register`, `unregister`, `get`, `exists`, `clear`, iteration, ID lookup) with reentrant locking (`threading.RLock`) for full thread safety.
- **Capabilities (Descriptive):** Profiles representing what EggMan is capable of (`Voice`, `Vision`, `Desktop Automation`, `Knowledge`, `Developer`).
- **Tools (Executable V2):** Connects to parents and wraps executable objects (`Calculator`, `Clipboard`, `Screenshot`, `Launch Application`, `Knowledge Search`) with strict metadata schemas.
- **Dynamic Help Dialog:** Rewrites the `/help` window layout to dynamically read and build UI cards representing active capabilities and their health status on the fly.
- **Event Bus Integration:** Dispatches state change events (`CapabilityRegisteredEvent`, `ToolRegisteredEvent`, `CapabilityEnabledEvent`, etc.) directly via the Event Bus for out-of-band updates.

---

## 📊 Egg Inspector Diagnostics

Accessible via the `/dev` slash command, Egg Inspector hosts multiple diagnostic dashboards:
- **Performance tab:** Tracks latency, tokens/sec, response timeline stages, and request average comparison.
- **Startup tab:** Benchmarks concurrent service boot times (DB init, warmups, audio pre-checks).
- **Knowledge tab:** Details document status, vector counts, database size, search times, and similarity scores.
- **Prompt tab:** Breaks down prompt composition, cache performance, per-module token counts, and reduction percentages.
- **Memory tab:** Evaluates memory database sizes, average confidence, category distribution, and active/expired ratios.

---

## 🎭 Persona System (v1)

EggMan's active persona dynamically alters its tone, vocabulary, formatting constraints, and synchronizes its mascot avatar, keeping backend capabilities identical.

| Persona | Key | Emoji | Avatar | Vibe / Style |
| :--- | :--- | :---: | :---: | :--- |
| **Normal** | `normal` | 🥚 | Classic Mascot | Calm, practical, Curiously honest. Uses classic `thinking.png` state. |
| **Coding Guy** | `coding` | 💻 | Senior Dev Avatar | Passionate engineer. Makes occasional dry programming jokes/analogies. |
| **Party Boi** | `party` | 🍺 | Party Hat Avatar | Playful, chaotic, carefree. Stretches vowels (`helloooo`) and uses slang. |

---

## ⚡ Startup System v2

The startup process initializes independent services concurrently:

```mermaid
graph TD
    A[Launch App] --> B{Concurrent Phase 1}
    B --> B1[SessionContext Init]
    B --> B2[Scheduler Init]
    B --> B3[Voice Pre-Verification]
    B --> B4[Configuration Loader]
    B --> B5[Ollama Handshake]
    B1 & B2 & B3 & B4 & B5 --> C[Phase 2: Model Warm-up]
    C --> D[Phase 3: Reminder Audit]
    D --> E[Mascot State: READY]
```

---

## 🛠️ Architectural Workflow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Main as main.py (UI)
    participant CE as ConversationEngine
    participant PB as PromptBuilder v2
    participant AI as AIEngine
    participant OLL as Ollama Engine

    User->>Main: Enter Message (Text/Speech)
    Main->>CE: stream_reply(user_message)
    CE->>PB: build_system_prompt()
    PB-->>CE: Dynamically Assembled System Prompt
    CE->>AI: generate(AIRequest)
    AI->>OLL: Dynamic Inference
    OLL-->>Main: Real-time Chunks
    Main->>User: Animated Fade-In Rendering
```

---

## 🎙️ Wake-Word & Voice Interface

- **Wake-Word Engine:** Uses `openWakeWord` configured with an `"Alexa"` acoustic footprint.
- **Speech-to-Text (STT):** Powered by `faster-whisper` using CPU `int8` quantization for responsive local voice transcription.
- **Speech Bubble Indicator:** Shows an Instagram-style bouncing three-dots typing animation over the companion during processing.

---

## 📁 Repository Structure

```text
Eggman/
├── app/                  # Application containers and initializers
├── assets/               # Images, icons, and theme files
├── backend/              # Core background engines
│   ├── ai/               # Provider routing, models, and StreamingResponse
│   ├── context/          # RAG Context & Knowledge Builders
│   ├── database/         # SQLite schema & SQL execution layers
│   ├── embeddings/       # Vector storage & chromadb integrations
│   ├── emotion/          # Emotion mapping engines
│   ├── knowledge/        # PDF loaders & document management
│   ├── memory/           # Classifiers, scorers, conflict resolvers (v2)
│   ├── personas/         # Persona subclasses & PersonaManager (v1)
│   ├── profiler/         # Diagnostics & Telemetry (v2)
│   ├── prompt/           # Modular PromptBuilder, registries, caches (v2)
│   ├── startup/          # StartupService & profile logger (v2)
│   ├── tools/            # Native OS execution tools (Calc, Clipboard)
│   ├── vision/           # Screen captures and VisionManager
│   └── voice/            # Speech-to-text & openWakeWord services
├── core/                 # Configurations, slash command routing, and themes
├── ui/                   # PySide6 widgets, custom Dialogs, and Switchers
├── tests/                # Pytest suites (60+ unit tests)
├── main.py               # Application entry point
├── EggMan.spec           # PyInstaller spec file
└── requirements.txt      # Main project dependencies
```

---

## 💻 Developer Quick Start

### 1. Set Up Environment
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Pull Ollama Models
Ensure Ollama is running locally, then fetch the required models:
```bash
ollama pull qwen3:8b
ollama pull qwen2.5vl:7b
ollama pull nomic-embed-text
```

### 3. Launch Application
```bash
python main.py
```

### 4. Run Tests
```bash
pytest
```

---

## 📦 PyInstaller Bundling

To compile a standalone, zero-dependency executable distribution of EggMan, run:

```bash
pyinstaller -y EggMan.spec
```

The completed build is written to **`dist/EggMan/EggMan.exe`**. The build system bundles Whisper models, wake-word parameters, and avatar assets automatically.
