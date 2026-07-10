# EggMan — Architecture & Concepts Reference

**Version:** 0.7  
**Language:** Python 3.11  
**UI Framework:** PySide6 (Qt6)  
**LLM Backend:** Ollama (local)  
**License:** Proprietary

---

## 1. Overview

EggMan is a fully offline AI desktop companion. It runs entirely on the local machine — no cloud calls, no data leakage. The mascot sits on the desktop as a draggable, frameless window with hover-reveal input controls. A separate chat window provides full conversation history. The backend runs on Ollama for LLM inference and embeddings, faster-whisper for speech-to-text, and openWakeWord for hands-free wake-word detection.

---

## 2. Directory Structure

| Path | Purpose |
|------|---------|
| `main.py` | Application entry point — creates QApplication, AppContainer, ChatWindow, DesktopCompanion |
| `app/container.py` | **Dependency Injection container** — wires all backend services together |
| `core/` | Shared primitives: config, settings, themes, logging, path resolution, slash commands, provider ABC |
| `backend/` | 20 subpackages forming the engine room |
| `ui/` | PySide6 widgets: dialogs, companion window, persona switcher, custom widgets |
| `data/` | Runtime data: `config.json`, `knowledge.db`, `exports/`, `screenshots/`, `logs/` |
| `assets/` | Icons, mascot images (`inactive.png`, `active.png`, `thinking.png`) |
| `tests/` | pytest suite |
| `EggMan.spec` | PyInstaller build config |

---

## 3. Core Concepts

### 3.1 AppContainer (Dependency Injection)

**File:** `app/container.py`

The AppContainer is a single class that constructs and wires every service in the application. It is created once in `main()` and passed to the ChatWindow. This pattern:

- **Centralizes construction** — no service creates its own dependencies
- **Enables swapping** — providers, databases, and retrievers can be swapped without touching UI code
- **Exposes startup diagnostics** — `ollama_startup_error` is checked at construction time

Key wiring in order:
1. `ConfigManager` → loads `data/config.json`
2. `AppLogger` → writes to `data/logs/eggman.log`
3. `SettingsManager` → reads/writes `eggman_settings.json`
4. `EventBus` → decoupled pub-sub backbone
5. `CommandHandler` → slash command router
6. `DatabaseManager` → SQLite wrapper for `database/eggman.sqlite3`
7. Repositories (`ConversationRepository`, `TaskRepository`, `KBRepository`)
8. Knowledge system: `VectorStore` → `EmbeddingService` → `DocumentParser` → `Chunker` → `DocumentIndex` → `KnowledgeManager`
9. Memory system: `MemoryRepository` → `MemoryExtractor` → `MemoryClassifier` → `ImportanceScorer` → `ConflictResolver` → `ExpirationManager` → `MemoryRanker` → `MemoryRetriever` → `MemoryManager`
10. `RetrievalService` (delegates to MemoryManager)
11. `ContextBuilder` (injects memories + knowledge into prompts)
12. `PromptBuilder` (module-based system prompt compiler)
13. Registries (`CapabilityRegistry`, `ToolRegistryV2`)
14. `AIEngine` → `ProviderRegistry` → `ConversationEngine`
15. Voice: `SpeechToTextService` → `VoiceManager` → `WakeWordService`
16. `VisionManager`, `Scheduler`, `EmotionEngine`, `ToolRouter`

### 3.2 Dual-Config System

Two JSON files manage persistent state:

**`data/config.json`** — Managed by `ConfigManager` (`core/config.py`)
- Provider settings: `ollama_base_url`, `ollama_model`, `embedding_model`
- Feature toggles: `wake_word_enabled`, `always_on_top`, `typing_delay`, `theme`
- Has `_DEFAULTS` for safe missing-key fallback

**`eggman_settings.json`** — Managed by `SettingsManager` (`core/settings.py`)
- Window geometry: `win_x`, `win_y`, `win_w`, `win_h`
- UI state: `active_persona`, `theme`

The split exists so that `config.json` can be bundled with the EXE as a resource, while `eggman_settings.json` lives in writable user data.

### 3.3 Path Resolution System

**File:** `core/paths.py`

Handles the difference between development and frozen (PyInstaller) environments:

- `IS_FROZEN` — True when running from EXE
- `PROJECT_ROOT` — Source tree root (dev) or `sys._MEIPASS` (frozen)
- `USER_DATA_ROOT` — `%APPDATA%/EggMan` (frozen) or `PROJECT_ROOT` (dev)
- `_path(...)` → resolves relative to `USER_DATA_ROOT`
- `resource_path(...)` → resolves relative to `RESOURCE_ROOT` (frozen bundle or project root)
- `external_path(...)` → resolves relative to `APP_ROOT` (EXE directory or project root)

---

## 4. AI & Conversation System

### 4.1 Architecture

```
User Message
    │
    ├── /command? → CommandHandler → CommandResult (action + response)
    │
    └── ConversationEngine.stream_reply()
            │
            ├── SessionManager → SessionContext (emotion, voice mode, dev mode)
            ├── PersonaManager → active persona prompt
            ├── PromptBuilder.build_system_prompt()
            │       └── PromptRegistry → PromptModule list
            │       └── PromptCache (caches static modules)
            │
            ├── AIEngine.generate() or .stream()
            │       ├── _route_tool_request() → ToolRouter short-circuit?
            │       ├── _build_request_with_context() → ContextBuilder
            │       │       ├── RetrievalService → MemoryManager
            │       │       └── KnowledgeManager.search()
            │       └── ProviderRegistry → OllamaProvider.generate()/stream()
            │
            └── StreamingResponse (iterable of StreamChunk)
```

### 4.2 AI Models (backend/ai/models.py)

- `AIRequest` — Contains `system_prompt`, `user_message`, `conversation_history` (list of `MessageEntry`), `memories`, `images`, `tool_results`, `metadata`
- `AIResponse` — Contains `response_text`, `model_name`, `finish_reason`, `token_usage`, `tool_requests`, `error`
- `StreamChunk` — One incremental token with `text` and `done` flag
- `TokenUsage` — `prompt_tokens`, `completion_tokens`, `total_tokens`

### 4.3 Provider Pattern (core/providers.py + backend/ai/provider_registry.py)

**`BaseProvider`** (ABC):
- `generate(request: AIRequest) -> AIResponse`
- `stream(request: AIRequest) -> StreamingResponse`

**`LocalProvider`**: Fallback with random egg-themed replies. Used when Ollama is down.

**`OllamaProvider`**: Communicates with Ollama HTTP API at `/api/generate`. Supports:
- Streaming via `POST /api/generate` with `"stream": true`, yields JSON lines
- Vision model (auto-switches to `qwen2.5vl:7b` when images present)
- Connection test via `GET /api/tags`
- Model auto-resolution (prefers `qwen3:8b`, falls back to configured model)
- Profiling integration (first-token latency, tokens/sec, stage timing)

**`ProviderRegistry`**: Maps string keys to factory callables. Default: `"ollama"`.

### 4.4 Streaming System (backend/ai/streaming.py)

- `StreamingResponse` wraps an `Iterable[str]` and yields `StreamChunk` objects
- Used by `_fetch_reply` in ChatWindow: background thread iterates chunks, emits `_reply_chunk` signals to the main thread
- `StreamingPipeline` is a simpler provider-agnostic coordinator (splits text by spaces)

### 4.5 PromptBuilder v2 (backend/prompt/prompt_builder.py)

A registry-driven modular prompt compiler:

1. **PromptContext** — captures current state: `mode`, `is_voice`, `has_image`, `has_tools`, `has_scheduler`, `developer_mode`, `retrieved_memories`, `retrieved_knowledge`
2. **PromptRegistry** — global registry of `PromptModule` subclasses
3. **PromptModule** — each module has `name()`, `is_applicable(context)`, `is_static()`, `generate(context)`
4. **PromptCache** — caches static modules (identity, communication) keyed by `{module_name}:{voice}:{mode}`

**Modules** (in `backend/prompt/modules/`):

| Module | Static? | Condition |
|--------|---------|-----------|
| `identity` | Yes | Always |
| `communication` | Yes | Always |
| `persona` | No | If persona_prompt exists |
| `memory` | No | If memories retrieved |
| `knowledge` | No | If knowledge found |
| `vision` | No | If image attached |
| `tools` | No | If tool intent detected |
| `scheduler` | No | If scheduling intent |
| `developer` | No | If developer_mode enabled |

After modules, the builder appends:
- Mode-specific instruction (`casual` / `teaching` / `programming`)
- Length constraints (greetings → 1 sentence, small talk → 1-2 sentences)

### 4.6 ContextBuilder (backend/context/context_builder.py)

Builds the `ContextPayload` object that enriches the AI request:

1. Trims conversation history to last 6 turns
2. Generates a lightweight summary of older turns (first 60 chars each)
3. Retrieves memories via `RetrievalService`
4. Searches knowledge base via `KnowledgeManager`
5. Injects both into the system prompt with labeled sections
6. Developer mode logs all injection stats

---

## 5. Memory System v2

### 5.1 Architecture

```
User Message → MemoryExtractor → MemoryClassifier → ImportanceScorer
    → ConflictResolver → MemoryRepository (SQLite) → MemoryRetriever
        → ExpirationManager (lazy sweep) → MemoryRanker
```

### 5.2 Key Types (backend/memory/models.py)

**`MemoryCategory`** (enum):
- `PREFERENCE`, `GOAL`, `HABIT`, `SKILL`, `PROJECT`, `PERSONAL_FACT`, `TEMPORARY`, `PERMANENT`, `SEMANTIC`, `WORKING`

**`MemoryRecord`**:
- `id`, `key`, `value`, `category`, `importance` (0-100), `confidence` (0.0-1.0), `source`, `created_at`, `last_accessed`, `access_count`, `expires_at`, `supersedes`, `embedding_id`, `active`

### 5.3 Pipeline Stages

**`MemoryExtractor`** — Pattern-matches user sentences for factual extractions (e.g., "I use...", "My name is...", "I work at..."). Returns `MemoryRecord` or `None`.

**`MemoryClassifier`** — Assigns an 8-category classification using keyword maps.

**`ImportanceScorer`** — Scores 0-100 based on category multiplier + keyword boost (e.g., "never", "always" → +30).

**`ConflictResolver`** — Groups memories by topic (Language, Editor, OS, Theme). If a newer memory conflicts with an older one, deactivates the old (`active=0`) and sets `supersedes` on the new.

**`ExpirationManager`** — TEMPORARY memories expire after 48 hours. Lazy-swept during retrieval.

**`MemoryRanker`** — Scores candidates for retrieval:
```
Score = Relevance × 0.40 + Importance × 0.30 + Recency × 0.15 + Confidence × 0.10 + CategoryBoost × 0.05
```

**`MemoryRetriever`** — Orchestrates expiration sweep → keyword search → ranking → top-k selection.

**`MemoryManager`** — Public facade coordinating the full pipeline.

### 5.4 Database Schema (backend/database/schema.py)

```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    importance TEXT NOT NULL,      -- migrated from 'low'/'medium'/'high' to integers
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_accessed TEXT NOT NULL,
    access_count INTEGER NOT NULL,
    metadata TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'explicit',
    expires_at TEXT,               -- nullable ISO datetime
    supersedes INTEGER,           -- FK to old memory id
    embedding_id TEXT,
    active INTEGER NOT NULL DEFAULT 1
);
```

---

## 6. Knowledge System v1

### 6.1 Architecture

```
File Upload → KnowledgeManager.upload_document()
    │
    ├── KBRepository.save_document() → eggman.db (metadata)
    │
    └── Background Thread:
        DocumentIndex.index_document_sync()
            ├── DocumentParser.parse() → ParsedDocument (pages with text)
            ├── Chunker.chunk() → List<TextChunk>
            ├── EmbeddingService.embed_batch() → List<List<float>>
            └── VectorStore.store_chunks() → knowledge.db

Query → KnowledgeManager.search()
    ├── Retriever.retrieve() → semantic cosine similarity
    └── Fallback: KBRepository.search_documents() → keyword
```

### 6.2 Two-Database Separation

| Database | Location | Contents |
|----------|----------|----------|
| `eggman.sqlite3` | `database/` | Document metadata (filename, status, chunk_count), conversations, memories, tasks |
| `knowledge.db` | `data/` | Chunk text + embeddings (BLOBs), vector metadata |

This separation means the knowledge index can be rebuilt independently without affecting conversation/memory data.

### 6.3 Key Components

**`DocumentParser`** — Uses loaders (`.txt` via `base_loader.py`, `.pdf` via `pdf_loader.py`) to extract text with page numbers.

**`Chunker`** — Configurable chunk size (default 512 chars) and overlap (default 64 chars). Preserves paragraph boundaries and avoids mid-sentence splits.

**`TextChunk`** — Dataclass with `document_id`, `chunk_index`, `page_number`, `text`, `chunk_id`.

**`EmbeddingProvider` (ABC)** — Abstract. Implemented by `OllamaEmbeddingProvider` which calls `POST /api/embed` on Ollama. Auto-pulls the model if missing.

**`EmbeddingService`** — Wraps the provider, provides `embed(text)` and `embed_batch(texts)`.

**`VectorStore` (ABC)** — Abstract. Implemented by `SQLiteVectorStore`:
- Stores embeddings as numpy `float32` BLOBs
- Search loads all vectors into memory and computes cosine similarity with `np.dot / (norm1 × norm2)`
- Supports dimension mismatch detection (model change)
- Thread-safe with `threading.Lock`

**`Retriever`** — Embeds the query, searches vector store, returns `RetrievalStats` with ranked results and timing.

**`DocumentIndex`** — Orchestrates the 4-stage indexing pipeline: Parse → Chunk → Embed → Store. Produces an `IndexingReport` with per-stage timing.

**`KnowledgeManager`** — Public interface. `search()` does semantic retrieval then formats results for prompt injection. Falls back to keyword search. Tracks `last_report` for status polling.

### 6.4 Database Schema (in knowledge.db)

```sql
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER,
    text TEXT NOT NULL,
    embedding BLOB,              -- numpy float32 array
    model_name TEXT,
    dimensions INTEGER,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(doc_id, chunk_index)
);

CREATE TABLE store_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

---

## 7. UI Layer

### 7.1 Component Hierarchy

```
QApplication
├── DesktopCompanion (frameless, always-on-top mascot window)
│   ├── QLabel (avatar pixmap)
│   ├── InputBar (QLineEdit + mic, send, screenshot buttons)
│   ├── SpeechBubble (floating bubble with TypingIndicator)
│   └── Chat/Close buttons
│
└── ChatWindow (frameless chat panel)
    ├── TitleBar (drag handle, persona switcher, min/close)
    ├── ChatDisplay (QScrollArea with MessageBubble list)
    ├── InputBar (bottom, shared reference from companion)
    └── BottomBar (calendar, bug buttons)
```

### 7.2 Window Architecture

**ChatWindow** (`main.py:36-848`):
- Frameless, translucent, fixed-size
- `QGraphicsOpacityEffect` for fade-in/out animations
- Owns `AppContainer` reference → all services
- Thread-safe signal bridge: `_reply_chunk`, `_reply_ready`, `_voice_text_ready`, `_schedule_triggered`
- Slash commands: `/help`, `/clear`, `/export`, `/settings`, `/schedule`, `/file`, `/dev`, `/theme`

**DesktopCompanion** (`ui/companion.py:186-451`):
- 275×275 frameless window, always-on-top, skips taskbar
- Hover-reveal input controls with opacity animation (200ms)
- Three visual states: `inactive`, `active`, `thinking` (different PNGs)
- Speech bubble with 3-dot typing indicator and 30-second auto-dismiss
- Draggable via mouse events
- Chat window position sync

### 7.3 Custom Widgets

**`TitleBar`** (`ui/widgets.py:258-332`):
- 42px tall, displays "EGGMAN" label
- Custom min/close buttons with hover colors
- `inject_right_button()` for persona switcher insertion
- Mouse drag moves the window

**`ChatDisplay`** (`ui/widgets.py:394-508`):
- Auto-scrolling QScrollArea with message limit (MAX_MESSAGES=100)
- Empty state label when no messages
- `MessageBubble` with sender label, animated text container, timestamp

**`MessageBubble`** (`ui/widgets.py:334-391`):
- User messages right-aligned, egg messages left-aligned
- `MessageTextContainer` for token-level streaming animation

**`MessageTextContainer`** + `AnimatedWordLabel` (`ui/widgets.py:147-254`):
- Splits text into tokens, renders each as an `AnimatedWordLabel`
- Uses `FlowLayout` for word-wrap within a 72% width limit
- Each word has a 150ms parallel animation: opacity 0→1 + offset_y 6→0

**`FlowLayout`** (`ui/widgets.py:19-136`):
- Custom QLayout that arranges widgets horizontally and wraps
- Supports `NewlineWidget` for forced line breaks
- `heightForWidth()` enables proper size hints

**`InputBar`** (`ui/widgets.py:511-607`):
- 54px bar with QLineEdit + 3 icon buttons (mic, send, screenshot)
- Voice listening state: red mic button, "Listening..." placeholder
- Voice processing state: "Transcribing..." placeholder

**`SpeechBubble`** (`ui/companion.py:52-184`):
- Floating window with rounded rect + pointing triangle
- `TypingIndicator` (3 bouncing dots, 150ms per frame)
- 30-second auto-fade timer

### 7.4 Dialogs (ui/dialogs.py)

| Dialog | Trigger | Purpose |
|--------|---------|---------|
| `SettingsDialog` | `/settings` | Ollama URL/model, always-on-top, wake word, window size |
| `HelpWindow` | `/help` | System commands, capability grid, about info |
| `ScheduleWindow` | Calendar button | View/manage scheduled tasks |
| `KnowledgeBaseWindow` | `/file` | Drag-drop file upload, view indexed docs, delete docs |
| `EggInspectorWindow` | `/dev` (bug button) | 6-tab diagnostics: Perf, Boot, Knowledge, Prompt, Memory, Audio |
| `ToastLabel` | Internal | Non-modal toast notification |
| `SettingsDialog` | Internal | Theme-tinted settings panel |

---

## 8. Voice & Audio System

### 8.1 Architecture

```
Microphone
    │
    ├── openWakeWord (continuous, lightweight)
    │   └── "alexa" detected → WakeWordService → VoiceManager.start_listening()
    │
    └── VoiceManager (on demand or wake-triggered)
        └── Records audio → SpeechToTextService (faster-whisper)
            └── Transcription → ChatWindow._on_voice_text()
```

### 8.2 Components

**`SpeechToTextService`** (`backend/voice/speech_to_text.py`):
- Wraps `faster-whisper.WhisperModel`
- Configurable model size (`base` / `small` / `medium` / `large-v3`)
- Converts numpy audio to text on a background thread
- Handles silence detection and VadOptions

**`VoiceManager`** (`backend/voice/voice_manager.py`):
- State machine: `IDLE → LISTENING → PROCESSING → IDLE`
- Records audio with `sounddevice` in a background thread
- Saves recordings to `data/audio/` for debugging
- Fires callbacks for state changes, transcription, and errors

**`WakeWordService`** (`backend/voice/wake_word.py`):
- Runs `openWakeWord` in a continuous background thread
- Configured with Alexa model, adjustable threshold
- On detection: triggers `VoiceManager.start_listening()`
- Starts after startup completes (not during initialization)

---

## 9. Event Bus System

**File:** `backend/event_bus/event_bus.py`

A simple, thread-safe pub-sub system:

- `BaseEvent` — frozen dataclass with `event_id` (UUID), `timestamp`, `source`, `metadata`
- `EventBus.subscribe(event_type, callback)` — register for a specific event class
- `EventBus.publish(event)` — dispatches to all matching subscribers outside the lock
- Exception isolation — one failing callback doesn't block others

**Event types** (`backend/event_bus/event_types.py`):
- `StartupTaskStartedEvent`, `StartupTaskCompletedEvent`, `StartupCompletedEvent`

**Usage**: ChatWindow subscribes to startup events for logging. Registry system uses events for capability/tool state changes.

---

## 10. Registry System

### 10.1 BaseRegistry (Generic, Thread-Safe)

**File:** `backend/registry/common/base_registry.py`

Generic `BaseRegistry[T]` with:
- `register(item)`, `unregister(id)`, `get(id)`, `get_all()`, `exists(id)`, `clear()`
- Thread safety via `threading.RLock()`
- Validation hooks: `validate(item)`, `on_registered(item)`, `on_unregistered(item)`
- Custom exceptions: `DuplicateRegistrationError`, `ItemNotFoundError`, `ValidationError`

### 10.2 CapabilityRegistry

**File:** `backend/registry/capability/`

- Registers `Capability` objects (descriptive metadata: `id`, `name`, `description`, `category`, `version`, `enabled`)
- Auto-registration via `@capability(...)` decorator — decorates classes like `KnowledgeManager`, `PerformanceProfiler`
- Publishes events: `CapabilityRegisteredEvent`, `CapabilityEnabledEvent`, etc.
- Used by `HelpWindow` to dynamically build the help UI

### 10.3 ToolRegistry (v2)

**File:** `backend/registry/tool/`

- Registers `Tool` objects (executable: `id`, `capability_id`, `name`, `description`, `execute()`)
- Auto-registration via `@tool(...)` decorator — decorates `CalculatorTool`, `ClipboardTool`, `AppLauncherTool`, etc.
- `ToolExecutor` provides safe execution wrapper
- Used by the dynamic help system

### 10.4 Decorator Pattern

`@capability(...)` and `@tool(...)` store registration data in a `__pending_registration__` list on the class, which is flushed during AppContainer init via:
```python
register_pending_capabilities(capability_registry)
register_pending_tools(tool_registry, container=self)
```

This means simply importing a module is enough to register it — no manual bootstrapping needed.

---

## 11. Startup System v2

**File:** `backend/startup/startup_service.py`

Three-phase initialization:

**Phase 1 (Concurrent):** 5 stages run in parallel threads:
- `SessionContext` — initialize session state, developer mode
- `Scheduler` — verify scheduler exists (thread started on construction)
- `Voice Initialization` — validate audio subsystem
- `Configuration` — verify config keys are present
- `Ollama Connection` — test Ollama connectivity

**Phase 2 (Sequential):** Model warm-up — sends a "READY" prompt to Ollama to pre-load the model into VRAM. Skipped if Ollama is unavailable.

**Phase 3 (Sequential):** Reminder check — queries task repository for overdue items.

**Chat interaction during startup:**
- Welcome message displayed immediately
- Input disabled with "Waiting for EggMan..." placeholder
- Slash commands `/help`, `/schedule`, `/file`, `/dev`, `/clear`, `/export`, `/settings`, `/theme` always allowed
- Other messages blocked with "still getting ready" response
- On ready: input enabled, wake word started, ready message shown (with Ollama error if any)

---

## 12. Tools System

### 12.1 ToolRouter (backend/tools/router.py)

Short-circuits AI generation for direct tool execution:

1. `copy <text>` → ClipboardTool
2. `open <app>` / `launch <app>` → AppLauncherTool
3. `calculate <expr>` / `what is <expr>` → CalculatorTool

Returns `ToolRouteResult(handled=True, response_text, tool_name, result)`. AIEngine checks this before calling the LLM.

### 12.2 Built-in Tools (backend/tools/builtins.py)

**`CalculatorTool`** — Safe AST-based arithmetic evaluator. Walks Python AST nodes to evaluate `+`, `-`, `*`, `/`, `%`, `**`. Prevents large values (>1e9) and excessive exponents (>12).

**`ClipboardTool`** — Uses `tkinter` clipboard (or injected Qt clipboard) for copy/paste. Works in frozen EXE via `tkinter` hidden import.

**`AppLauncherTool`** — Launches registered applications (Chrome, VS Code, Spotify, Notepad) via `subprocess.Popen`. Uses `ApplicationRegistry` with path candidates. No arbitrary shell execution.

---

## 13. Scheduler

**File:** `backend/scheduler/scheduler.py`

- Stores tasks in `scheduled_tasks` SQLite table
- Parses natural language schedules via `parse_and_schedule()` (keyword matching: "tomorrow 3pm", "in 30 minutes", "every day at 9am")
- Runs a daemon thread that checks every 30 seconds for due tasks
- Fires triggers via callback → signal bridge → ChatWindow UI
- Checks for overdue tasks on startup

---

## 14. Vision System

**File:** `backend/vision/vision_manager.py`

- Captures screenshots of the primary monitor
- Stores pending attachments (base64-encoded images)
- Shows preview window for review before sending
- Vision provider (`qwen2.5vl:7b`) auto-selected when images present in `OllamaProvider`

---

## 15. Profiler & Diagnostics

**File:** `backend/profiler/performance_profiler.py`

- Singleton with thread-local `RequestProfile` storage
- Only active when Developer Mode is ON
- Records: request timing, per-stage breakdown, model name, token counts, GPU info
- Stores last 50 requests in memory history
- EggInspectorWindow displays 6 tabs of diagnostics

**`RequestProfile`** (`backend/profiler/request_profile.py`):
- `start_time`, `stages` dict, `total_time`
- Tracks: `memory_used`, `knowledge_used`, `vision_used`, `tools_executed`
- Token breakdown: `prompt_tokens`, `output_tokens`, `system_prompt_tokens`, `user_prompt_tokens`, `history_tokens`
- Ollama timing: `load_duration`, `prompt_eval_duration`, `eval_duration`

---

## 16. Persona System

**File:** `backend/personas/`

**`BasePersona`** — ABC with `key`, `display_name`, `description`, `avatar_path`, `build_prompt()`

Three built-in personas:

| Persona | Key | Style |
|---------|-----|-------|
| Normal | `normal` | Calm, practical, curious |
| Coding Guy | `coding` | Passionate engineer, dry programming jokes |
| Party Boi | `party` | Playful, chaotic, stretches vowels |

**`PersonaManager`** — Singleton. Manages active persona, persists selection to settings. Provides `get_active_persona_prompt()` for prompt injection.

**Visual sync:** When persona changes:
- Mascot avatar switches (Custom PNGs for coding/party)
- Chat announcement posted
- Selection persisted to `eggman_settings.json`

---

## 17. Emotion Engine

**File:** `backend/emotion/`

Simple keyword-based sentiment:
- `Mood.HAPPY` → "hello", "hi"
- `Mood.SAD` → "error", "fail"
- `Mood.CURIOUS` → contains "?"
- `Mood.NEUTRAL` → default

Separate emotion detection also happens in `ConversationEngine._detect_mode()` for response mode classification (casual / teaching / programming).

---

## 18. Theme System

**File:** `core/themes.py`

**`Theme`** — Static class with color/font constants. Mutated by `ThemeManager` at runtime.

**`ThemeManager`** — Maps theme names to palettes. `apply(name)` sets all `Theme` attributes. Supports `light` and `dark` palettes via `/theme light|dark` command.

Light: warm cream/brown palette (#F5F0E8, #C8BFA8)
Dark: catppuccin-inspired (#1E1E2E, #313244)

---

## 19. Slash Commands

**File:** `core/commands.py`

| Command | Action | Handler |
|---------|--------|---------|
| `/help` | `"help"` | Opens HelpWindow |
| `/schedule <text>` | `"schedule"` | Scheduler.parse_and_schedule() |
| `/file` | `"file"` | Opens KnowledgeBaseWindow |
| `/dev` | `"dev"` | Toggles Developer Mode |
| `/clear` | `"clear"` | Clears chat display |
| `/export` | `"export"` | Saves chat to text file |
| `/settings` | `"settings"` | Opens SettingsDialog |
| `/theme light|dark` | `"theme_..."` | Applies theme |

Returns `CommandResult(handled, response, action)`.

---

## 20. Database Layer

### 20.1 Tables in eggman.sqlite3

**`conversations`**: `id`, `sender`, `message`, `created_at`

**`memories`**: `id`, `category`, `key`, `value`, `importance`, `confidence`, `created_at`, `updated_at`, `last_accessed`, `access_count`, `metadata`, `source`, `expires_at`, `supersedes`, `embedding_id`, `active`

**`scheduled_tasks`**: `id`, `title`, `scheduled_time`, `repeat_status`, `created_at`

**`kb_documents`**: `id`, `filename`, `file_type`, `file_size`, `content`, `source_path`, `created_at`, `status`, `chunk_count`, `metadata`

### 20.2 Repository Pattern

Each table has a corresponding repository class:

| Repository | File | Operations |
|------------|------|------------|
| `ConversationRepository` | `repositories/conversation_repository.py` | save, get_history |
| `MemoryRepository` | `memory/memory_repository.py` | save, update, get, search, mark_accessed |
| `TaskRepository` | `repositories/task_repository.py` | save, get_all, get_due, mark_completed |
| `KBRepository` | `repositories/kb_repository.py` | save, update, get, search, delete |

### 20.3 DatabaseManager

WAL-mode SQLite wrapper. Creates `eggman.sqlite3` on init. Provides `get_connection()` with `row_factory = sqlite3.Row`.

---

## 21. PyInstaller Build

**File:** `EggMan.spec`

- Collects all backend, core, ui submodules automatically
- Bundles: `assets/`, `data/config.json`, `faster_whisper` assets, `openWakeWord` resources
- Excludes `chromadb` (not used directly)
- Hidden imports for: `tkinter`, `openwakeword`, `onnxruntime`, `scipy`, `sklearn`, `numpy`
- Build: `python -m PyInstaller EggMan.spec --noconfirm`
- Output: `dist/EggMan/EggMan.exe`

---

## 22. Testing

- Framework: pytest (60+ tests)
- Tests in `tests/` directory
- Run: `pytest`

---

## 23. Data Flow: Full Request Lifecycle

```
1. User types/speaks message
2. ChatWindow._on_send() or _on_voice_text()
3. CommandHandler.handle() — slash command?
   ├── Yes → execute action, return
   └── No → continue
4. VisionManager — check pending screenshot
5. _start_typing() → show "..." bubble, disable input
6. Background thread: _fetch_reply()
   a. ConversationEngine.stream_reply()
   b. SessionContext update (emotion, voice mode)
   c. Mode detection (casual/teaching/programming)
   d. PersonaManager → active persona prompt
   e. PromptBuilder.build_system_prompt()
      - Create PromptContext
      - Select applicable PromptModules
      - Compile + cache sections
   f. AIEngine.stream()
      - ToolRouter short-circuit?
      - ContextBuilder.build_context()
          - Memory retrieval via RetrievalService
          - Knowledge search via KnowledgeManager
      - ProviderRegistry → OllamaProvider
          - POST /api/generate stream=True
          - Yield chunks
   g. Yield StreamChunks
7. _reply_chunk signal → _on_reply_chunk()
   - Remove "..." bubble
   - Append text to MessageTextContainer with animation
8. _reply_ready signal → _finish_typing()
   - Replace streaming bubble with final
   - Re-enable input
   - Show speech bubble on companion
9. Memory capture (background): _capture_memory()
   - MemoryExtractor → MemoryManager.save_memory()
```

---

## 24. Key Design Patterns Used

| Pattern | Where |
|---------|-------|
| **Dependency Injection** | `AppContainer` constructs and wires all services |
| **Singleton** | `SessionManager`, `PersonaManager`, `PerformanceProfiler` |
| **ABC / Interface** | `BaseProvider`, `EmbeddingProvider`, `VectorStore`, `BasePersona`, `PromptModule` |
| **Factory** | `ProviderRegistry` maps keys to factory callables |
| **Strategy** | Pluggable providers, vector stores, embedding providers |
| **Observer / Pub-Sub** | `EventBus` for decoupled communication |
| **Registry** | `PromptRegistry`, `CapabilityRegistry`, `ToolRegistry` |
| **Decorator** | `@capability()`, `@tool()` for auto-registration |
| **Facade** | `KnowledgeManager`, `MemoryManager` coordinate complex subsystems |
| **Repository** | Data access objects for each SQLite table |
| **Command** | `CommandHandler` routes slash commands |
| **Template Method** | `DocumentIndex.index_document_sync()` defines indexing pipeline |
| **Proxy / Signal Bridge** | Qt signals cross thread boundaries safely |
| **MVC** | UI (widgets) ↔ Backend (services) ↔ Data (SQLite) |

---

## 25. Async / Threading Model

| Thread | Purpose |
|--------|---------|
| **Main (Qt) thread** | All UI rendering, signal handling, user input |
| **AI worker** | Per-message thread for LLM streaming (`_fetch_reply`) |
| **StartupService** | Background initialization pipeline |
| **DocumentIndex** | Background indexing per uploaded file |
| **Scheduler** | Every 30s task check loop |
| **Voice capture** | `sounddevice` audio recording stream |
| **WakeWord** | Continuous `openWakeWord` inference |
| **Model pull** | Background `ensure_model_available()` for embedding model |

Thread safety: Qt signals for cross-thread communication, `threading.Lock` for shared resources (vector store, event bus, registries).
