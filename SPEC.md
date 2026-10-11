# AI Classroom --- Technical Specification

**Document:** `SPEC.md`\
**Version:** 1.0\
**Status:** Requirements specification\
**Target runtime:** Python 3.11+\
**GUI framework:** pygame\
**Testing:** pytest

## 1. Overview

### 1.1 Purpose

AI Classroom is a modest 2D desktop simulation in which six AI
assistants act as students in a classroom. The user acts as the teacher:
they enter a question, wait while all assistants generate answers
concurrently, select a student who has raised a hand, review the answer
in a speech bubble, and grade it as **GOOD** or **BAD**.

The application demonstrates concurrent answer generation, explicit
state transitions, provider substitution, simple animation,
scorekeeping, and persistent round history. It is not intended to
imitate the official appearance of any AI product. Student characters
are drawn from simple shapes and use distinct colors and text labels
only.

### 1.2 Goals

-   Present a clear, approachable classroom interface.
-   Request answers from all six students concurrently without blocking
    the GUI.
-   Make agent states visible and enforce state-machine rules centrally.
-   Support an offline deterministic mock provider and an optional
    Gemini-backed provider.
-   Track per-student scores and persist round history.
-   Keep domain logic independent of pygame so it can be tested with
    pytest.

### 1.3 Non-goals

-   No official logos, external character images, or branded visual
    assets.
-   No multi-user networking, accounts, authentication, or cloud
    synchronization.
-   No promise that AI-generated answers are factually correct.
-   No execution of generated answers as code.
-   No requirement for audio, 3D graphics, or a physics engine.
-   No implementation code is specified in this document.

### 1.4 User stories

1.  **As a teacher**, I can type a non-empty question and start a round
    so all six students begin thinking.
2.  **As a teacher**, I can see which students are thinking, ready,
    answered, or in error.
3.  **As a teacher**, I can tell that a student is ready because the
    character raises a hand and the desk becomes selectable.
4.  **As a teacher**, I can select a ready student and watch the teacher
    character move to that desk.
5.  **As a teacher**, I can read the student's answer in a wrapped,
    scrollable speech bubble.
6.  **As a teacher**, I can grade the selected answer GOOD or BAD,
    changing the student's score by +1 or -1.
7.  **As a teacher**, I cannot grade a student who is not selected, is
    not READY, or has already been graded this round.
8.  **As a teacher**, I can see a scoreboard and ranking that update
    immediately after grading.
9.  **As a teacher**, I can start another round; all students return to
    THINKING and prior round grades remain in the scoreboard and
    history.
10. **As a developer**, I can test core behavior without creating a
    pygame window.
11. **As a developer/operator**, I can run the app offline with mock
    answers if the Gemini key is absent or the service fails.

## 2. Technical requirements and constraints

-   Python 3.11 or newer.
-   pygame for rendering, input, and the main event loop.
-   pytest for automated tests.
-   python-dotenv for optional `.env` configuration.
-   Window size: 1280 × 720 logical pixels.
-   Target frame rate: 60 FPS.
-   User-facing interface labels and messages: Romanian, including
    Romanian diacritics.
-   Use a system font with Romanian character support, for example
    Arial, with a fallback font if unavailable.
-   Six students arranged as two rows of three desks: ChatGPT, Gemini,
    Copilot, Grok, Claude, and DeepSeek.
-   `core/` must not import pygame, directly or indirectly.
-   All provider calls run away from the GUI thread. Results are
    transferred through `queue.Queue` and consumed during the frame
    loop.
-   Per-agent answer deadline: 30 seconds. Expired requests transition
    that agent to `ERROR`.
-   Gemini integration is optional. Missing credentials or provider
    errors must not prevent the application from running.
-   Store history in `results/history.json`. The application must handle
    a missing or malformed history file safely.

## 3. Project structure

``` text
ai-classroom/
├── main.py
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── core/
│   ├── __init__.py
│   ├── models.py
│   ├── scoreboard.py
│   ├── classroom.py
│   └── history.py
├── providers/
│   ├── __init__.py
│   ├── base.py
│   ├── mock.py
│   └── gemini.py
├── gui/
│   ├── __init__.py
│   ├── scene.py
│   ├── sprites.py
│   ├── widgets.py
│   └── animations.py
├── results/
│   └── .gitkeep
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_scoreboard.py
    ├── test_classroom.py
    ├── test_history.py
    └── test_mock_provider.py
```

`results/history.json` is created at runtime and should normally be
ignored by version control. `results/.gitkeep` may be committed to
preserve the directory. `.env.example` contains placeholder values only;
the real `.env` must never be committed.

## 4. Domain model and module specifications

The signatures below define the required public contracts. Internal
helper methods may be added as needed, provided they preserve the
separation of concerns.

### 4.1 `core/models.py`

**Responsibility:** Define framework-independent data structures and
enums. This module must not import pygame or provider SDKs.

#### `AgentState`

Enum values:

-   `IDLE`: no active answer request.
-   `THINKING`: a request is running.
-   `READY`: an answer has been received and may be selected.
-   `ANSWERED`: the teacher has graded the answer for the current round.
-   `ERROR`: the request failed or exceeded its deadline.

#### `Grade`

Enum values:

-   `GOOD`
-   `BAD`

#### `Answer`

Immutable or effectively immutable record containing:

-   `agent_id: str`
-   `question: str`
-   `text: str`
-   `created_at: str` --- ISO 8601 timestamp
-   `provider: str` --- provider identifier, such as `mock` or `gemini`
-   `round_id: str`

The answer text must be a string. Empty or whitespace-only provider
responses are treated as provider failures.

#### `Agent`

Record representing a student:

-   `id: str` --- stable unique identifier, e.g. `chatgpt`
-   `name: str` --- visible display name
-   `color: tuple[int, int, int]` --- RGB color
-   `state: AgentState`
-   `answer: Answer | None`
-   `error_message: str | None`
-   `score: int`
-   `graded_round_id: str | None`

The model must not contain pygame surfaces, rectangles, fonts, or other
GUI objects.

Recommended signatures:

-   `def reset_for_round(self) -> None`
-   `def set_thinking(self) -> None`
-   `def set_ready(self, answer: Answer) -> None`
-   `def set_error(self, message: str) -> None`

These operations should validate legal transitions or be called only
through a validated controller. Invalid transitions must not silently
corrupt state.

### 4.2 `core/scoreboard.py`

**Responsibility:** Maintain score totals and produce stable rankings.
It must not depend on rendering or provider details.

#### `Scoreboard`

Required signatures:

-   `def add_grade(self, agent_id: str, grade: Grade) -> int`
-   `def get_score(self, agent_id: str) -> int`
-   `def ranking(self) -> list[tuple[str, int]]`
-   `def reset(self) -> None`

Rules:

-   `GOOD` adds exactly one point.
-   `BAD` subtracts exactly one point.
-   Unknown agent IDs must raise a documented exception such as
    `KeyError`; they must not silently create scoreboard entries.
-   Ranking is ordered by score descending. Ties are resolved
    deterministically by the configured student order, then by stable
    agent ID if needed.
-   `reset()` sets every registered student's score to zero without
    changing the registered student set.
-   The controller is responsible for ensuring a grade can be applied
    only once per agent per round.

### 4.3 `core/classroom.py`

**Responsibility:** Coordinate rounds, agent states, provider work,
timeouts, selection, grading, and result delivery. It must not import
pygame.

#### `Classroom`

Recommended constructor:

`def __init__(self, agents: list[Agent], provider: AnswerProvider, scoreboard: Scoreboard, history: HistoryStore, timeout_seconds: float = 30.0, max_workers: int = 6) -> None`

Required public methods:

-   `def ask(self, question: str) -> str`
    -   Rejects an empty or whitespace-only question with `ValueError`.
    -   Starts a new round, returns its `round_id`, resets all students'
        per-round answer/error/grading fields, and puts all six students
        into `THINKING`.
    -   Submits one independent answer task per student to a
        `ThreadPoolExecutor`.
    -   A new round invalidates late results from earlier rounds; late
        results must not overwrite current state.
-   `def poll_results(self) -> list[AnswerResult]`
    -   Non-blockingly drains the internal `queue.Queue`.
    -   Applies only results that match the active round and an agent
        currently in `THINKING`.
    -   Transitions successful results to `READY`; failed results to
        `ERROR`.
    -   Evaluates request deadlines without waiting for provider calls
        to return.
-   `def select(self, agent_id: str) -> Agent`
    -   Allows selection only if the target agent is `READY`.
    -   Sets the selected agent and returns it.
    -   Raises a documented exception for unknown or non-ready agents.
    -   Selection does not grade the agent or change its score.
-   `def grade(self, agent_id: str, grade: Grade) -> int`
    -   Permitted only for the currently selected agent, which must be
        `READY`.
    -   Permitted once per agent per round.
    -   Applies the score delta, transitions the agent to `ANSWERED`,
        records the grade, and persists the round update.
    -   Returns the resulting score.
-   `def get_selected_agent(self) -> Agent | None`
-   `def get_agents(self) -> list[Agent]`
-   `def get_scoreboard(self) -> Scoreboard`
-   `def get_round_id(self) -> str | None`
-   `def close(self) -> None`
    -   Shuts down executor resources cleanly. GUI shutdown must call
        this method.
    -   Shutdown must not block indefinitely on an unresponsive
        provider. Provider network calls should also have finite
        transport-level timeouts.

#### Result record

`AnswerResult` is a framework-independent record containing:

-   `round_id: str`
-   `agent_id: str`
-   `answer: Answer | None`
-   `error_message: str | None`
-   `completed_at: float` --- monotonic time used for deadline
    accounting

Exactly one of `answer` and `error_message` should be populated.

#### Concurrency and timeout rules

-   Each agent task is submitted independently to a
    `ThreadPoolExecutor`, with up to six workers by default.
-   Worker threads must never mutate `Agent`, `Scoreboard`, GUI objects,
    or any other shared domain state. They return an `AnswerResult` to a
    thread-safe queue; the controller applies it when `poll_results()`
    runs on the main thread.
-   Each request has an individual deadline of 30 seconds measured using
    a monotonic clock.
-   A request that reaches its deadline while still `THINKING`
    transitions to `ERROR` with a user-readable timeout message.
-   A late result after timeout is ignored.
-   Provider exceptions are converted to result errors rather than
    escaping worker threads.
-   A completed future must not be processed twice.
-   A new round starts a new round ID. Results with an older ID are
    discarded.
-   Empty questions are rejected before any state changes or task
    submission.
-   GUI frame processing must never call a blocking `Future.result()` on
    unfinished tasks.

### 4.4 `core/history.py`

**Responsibility:** Persist round and grading data to JSON without
importing pygame or provider SDKs.

#### `HistoryStore`

Recommended signatures:

-   `def __init__(self, path: str = "results/history.json") -> None`
-   `def save_round(self, round_record: RoundRecord) -> None`
-   `def update_grade(self, round_id: str, agent_id: str, grade: Grade, score_after: int) -> None`
-   `def load_rounds(self) -> list[RoundRecord]`
-   `def export_json(self) -> dict[str, object]`

`RoundRecord` contains at minimum:

-   `round_id: str`
-   `question: str`
-   `started_at: str`
-   `agents: list[AgentRoundRecord]`

Each `AgentRoundRecord` contains:

-   `agent_id: str`
-   `state: str`
-   `answer_text: str | None`
-   `provider: str | None`
-   `error_message: str | None`
-   `grade: str | None`
-   `score_after: int | None`

Persistence rules:

-   Use UTF-8 and preserve Romanian diacritics.
-   Create the parent directory when necessary.
-   Write JSON with a version field, for example `schema_version: 1`.
-   Avoid corrupting an existing history file during normal writes:
    serialize to a temporary sibling file, flush/close it, then replace
    the target.
-   A missing file returns an empty history.
-   Invalid JSON, unsupported schema versions, or unreadable files
    produce a logged/user-visible warning and a safe empty history; the
    app remains usable.
-   History write failures must be surfaced non-fatally to the
    GUI/logging layer. They must not undo an already applied score or
    freeze the event loop.
-   Do not store API keys, environment variables, or unnecessary secrets
    in history.
-   Define whether answers are persisted in full. Version 1 stores
    answer text for local review; the UI should not claim the file is
    encrypted.

### 4.5 `providers/base.py`

**Responsibility:** Define the provider abstraction and shared
provider-level errors.

#### `AnswerProvider`

Abstract base class:

-   `@abstractmethod`
-   `def get_answer(self, question: str, agent: Agent) -> str`

The `agent` argument provides identity/personality context. The public
concept remains "answer a question"; providers must return answer text
only. Provider implementations must document their timeout behavior and
must not access pygame.

Recommended exceptions:

-   `ProviderError`
-   `ProviderTimeoutError`

All provider exceptions must be caught by the classroom worker boundary
and represented as `AnswerResult` errors.

### 4.6 `providers/mock.py`

**Responsibility:** Provide offline answers for demos, automated tests,
and fallback operation.

#### `MockProvider`

Recommended constructor:

`def __init__(self, seed: int | None = None, min_delay: float = 1.0, max_delay: float = 4.0, wrong_answer_probability: float = 0.15) -> None`

Required signature:

-   `def get_answer(self, question: str, agent: Agent) -> str`

Requirements:

-   Works without network access or API keys.
-   Supports deterministic-capable output and delay selection when a
    seed is provided. Tests should be able to disable delay or inject a
    zero-delay configuration.
-   Normal interactive configuration simulates a delay between 1 and 4
    seconds.
-   Uses varied answer styles/personality profiles per student;
    personality changes tone/format, not the agent's identity or the
    requested language.
-   Sometimes intentionally returns an incorrect or misleading mock
    answer so grading can be demonstrated. This behavior must be
    configurable and deterministic in tests.
-   Does not use unseeded global random state. Each instance owns its
    random generator.
-   Mock content must be clearly considered demonstration content, not
    real model output.
-   Should not use `time.sleep()` in a way that prevents the timeout
    mechanism from being tested; the provider may simulate delay in a
    worker thread, and tests must be able to configure delay to zero.

### 4.7 `providers/gemini.py`

**Responsibility:** Optional Gemini integration, isolated behind the
provider interface.

#### `GeminiProvider`

Recommended constructor:

`def __init__(self, api_key: str, fallback: AnswerProvider, timeout_seconds: float = 20.0) -> None`

Required signature:

-   `def get_answer(self, question: str, agent: Agent) -> str`

Requirements:

-   Reads `GEMINI_API_KEY` from environment configuration loaded by
    `python-dotenv` at the application entry point.
-   Does not read `.env` directly from core logic.
-   If the key is missing, the application chooses `MockProvider`; it
    must not instantiate a nonfunctional Gemini client.
-   Applies a finite network/request timeout shorter than the
    classroom's 30-second per-agent deadline where supported by the SDK.
-   Includes the student name and a short personality instruction in the
    prompt, while treating the user's question as untrusted input. The
    user question must not be allowed to override application-level
    output constraints.
-   Returns plain answer text, not raw SDK response objects.
-   On any SDK exception, invalid/empty response, rate limit,
    authentication failure, or timeout, invokes the configured
    `fallback` provider and returns the fallback answer if it succeeds.
-   If both Gemini and fallback fail, raises a `ProviderError` with a
    safe, concise message. Do not include API keys or sensitive request
    headers in errors.
-   Do not log credentials or full environment contents.
-   Provider selection and fallback must be testable with fake
    provider/client objects so tests do not require a real API key or
    network.
-   The provider SDK dependency and its supported version must be
    documented in `requirements.txt`/README. The rest of the app must
    remain runnable if Gemini is not configured.

### 4.8 `gui/sprites.py`

**Responsibility:** Draw student and teacher characters using pygame
primitives. This module may import pygame; core modules may not.

#### `StudentSprite`

Recommended signatures:

-   `def __init__(self, agent: Agent, desk_rect: pygame.Rect) -> None`
-   `def update(self, dt: float) -> None`
-   `def draw(self, surface: pygame.Surface) -> None`
-   `def hit_test(self, position: tuple[int, int]) -> bool`

Visual requirements:

-   Circle head, rectangle body, simple arms/legs, distinct solid color
    per student, and a readable name tag.
-   No official logos, downloaded images, or externally sourced
    textures.
-   `THINKING`: animated ellipsis above the head.
-   `READY`: one raised arm and a small vertical bounce.
-   `ANSWERED`: neutral seated pose with a subtle completed indicator.
-   `ERROR`: visible error marker and/or `ERR` status text.
-   `IDLE`: neutral seated pose.

#### `TeacherSprite`

Recommended signatures:

-   `def __init__(self, start_position: tuple[float, float]) -> None`
-   `def walk_to(self, target: tuple[float, float]) -> None`
-   `def update(self, dt: float) -> None`
-   `def draw(self, surface: pygame.Surface) -> None`
-   `def is_moving(self) -> bool`

Requirements:

-   Teacher movement is visual only; it must not control domain state.
-   Movement uses time-based linear interpolation or an easing function
    so speed does not depend on frame rate.
-   Reaching a desk should stop movement without oscillation.
-   The answer bubble appears only after the teacher has reached the
    selected desk, unless the design explicitly defines an accessible
    interim state.

### 4.9 `gui/animations.py`

**Responsibility:** Reusable, time-based visual animation helpers.

Recommended interfaces:

-   `class BounceAnimation`
    -   `def start(self) -> None`
    -   `def update(self, dt: float) -> None`
    -   `def get_offset(self) -> float`
-   `class WalkAnimation`
    -   `def start(self, start: tuple[float, float], end: tuple[float, float], duration: float) -> None`
    -   `def update(self, dt: float) -> tuple[float, float]`
    -   `def is_complete(self) -> bool`
-   `class FloatingText`
    -   Fields: text, position, lifetime, elapsed time, and score-delta
        sign.
    -   `def update(self, dt: float) -> None`
    -   `def draw(self, surface: pygame.Surface) -> None`
    -   `def is_complete(self) -> bool`

All animation progress must use elapsed time (`dt`), not frame counts.
Animation helpers must not modify scores or agent states.

### 4.10 `gui/widgets.py`

**Responsibility:** Render and handle isolated UI widgets. Widgets may
report user intent to `Scene`, but must not directly mutate core models.

#### `QuestionInput`

-   `def handle_event(self, event: pygame.event.Event) -> None`
-   `def draw(self, surface: pygame.Surface) -> None`
-   `def get_text(self) -> str`
-   `def clear(self) -> None`

A single-line input is sufficient for version 1. Enter starts a round;
Shift+Enter may be reserved for future multiline support. Empty input
must display a Romanian validation message and must not start a round.

#### `ScoreboardWidget`

-   `def set_rows(self, rows: list[tuple[str, int]]) -> None`
-   `def draw(self, surface: pygame.Surface) -> None`

Displays all six students, current scores, and ranking order. Negative
scores must be shown correctly.

#### `SpeechBubble`

-   `def set_text(self, text: str) -> None`
-   `def scroll(self, delta: int) -> None`
-   `def draw(self, surface: pygame.Surface) -> None`

Requirements:

-   Wrap words to fit the bubble width.
-   Clip text to the bubble viewport.
-   Support mouse wheel and/or keyboard scrolling for long answers.
-   Keep the text readable and do not let it overlap grade buttons.
-   Handle long unbroken strings without crashing; character-level
    wrapping may be used as a fallback.

#### `StatusMessage`

-   `def show(self, message: str, duration: float = 3.0) -> None`
-   `def update(self, dt: float) -> None`
-   `def draw(self, surface: pygame.Surface) -> None`

Displays short Romanian validation, timeout, provider, and history
warnings. A warning must not be the only indication of a student's
`ERROR` state.

### 4.11 `gui/scene.py`

**Responsibility:** Own the pygame scene, translate user events into
controller calls, poll result queues, update visual objects, and draw
the application. It is the only layer that coordinates GUI components.

#### `ClassroomScene`

Recommended constructor:

`def __init__(self, classroom: Classroom, screen: pygame.Surface, clock: pygame.time.Clock) -> None`

Required methods:

-   `def handle_event(self, event: pygame.event.Event) -> None`
-   `def update(self, dt: float) -> None`
-   `def draw(self) -> None`
-   `def run(self) -> None`
-   `def request_new_round(self) -> None`
-   `def shutdown(self) -> None`

Rules:

-   Poll `Classroom.poll_results()` on every frame.
-   Never wait synchronously for provider completion.
-   Handle input and mouse events on the pygame/main thread.
-   Only READY student sprites are clickable.
-   Clicking a READY student calls `Classroom.select()` and begins
    teacher movement.
-   Grade buttons are enabled only when a selected student is READY and
    the teacher has arrived.
-   After grading, update the scoreboard and spawn a floating
    score-delta animation.
-   Catch expected domain validation errors and display Romanian status
    messages.
-   On close/quit, call `Classroom.close()` and shut down pygame
    resources.
-   Keep rendering separate from domain decisions; do not duplicate
    state-machine rules in sprites/widgets.

### 4.12 `main.py`

**Responsibility:** Configure and start the application.

Required responsibilities:

-   Load `.env` using `python-dotenv`.
-   Initialize logging and pygame.
-   Configure the system font/fallback font.
-   Create six `Agent` instances in a fixed, documented order.
-   Initialize `Scoreboard`, `HistoryStore`, and provider strategy.
-   Choose `GeminiProvider` only when `GEMINI_API_KEY` is present and
    valid; otherwise choose `MockProvider`.
-   Construct `Classroom`, the display surface, clock, and
    `ClassroomScene`.
-   Run the main loop and guarantee cleanup on normal exit or
    startup/runtime failure.
-   Never print or log the API key.

## 5. State machine

### 5.1 Text diagram

``` text
                    ask(question)
       ┌──────────────────────────────────┐
       │                                  ▼
    ┌──────┐                         ┌──────────┐
    │ IDLE │ ──────────────────────> │ THINKING │
    └──────┘                         └────┬─────┘
                                          │
                         ┌────────────────┴──────────────┐
                         │                               │
                  answer received                  timeout/failure
                         │                               │
                         ▼                               ▼
                    ┌─────────┐                     ┌─────────┐
                    │  READY  │                     │  ERROR  │
                    └────┬────┘                     └─────────┘
                         │
                 teacher grades once
                         │
                         ▼
                    ┌──────────┐
                    │ ANSWERED │
                    └──────────┘

New valid question: every agent is reset for the new round and enters THINKING.
```

### 5.2 Transition rules

  -------------------------------------------------------------------------
  Current state     Event               Next state        Required behavior
  ----------------- ------------------- ----------------- -----------------
  `IDLE`            Valid question      `THINKING`        Clear per-round
                    submitted                             fields and submit
                                                          provider work

  Any state         New valid question  `THINKING`        Start a new round
                    submitted                             ID; invalidate
                                                          previous
                                                          asynchronous
                                                          results

  `THINKING`        Non-empty answer    `READY`           Store answer and
                    received for active                   enable selection
                    round                                 

  `THINKING`        Timeout or          `ERROR`           Store safe error
                    unrecoverable                         message; disable
                    provider/fallback                     selection
                    failure                               

  `READY`           Teacher selects     `READY`           Record selected
                    student                               agent; begin
                                                          visual walk

  `READY`           Selected answer     `ANSWERED`        Apply one score
                    graded                                delta and persist
                                                          grade

  `ANSWERED`        Grade attempted     `ANSWERED`        Reject operation;
                    again in same round                   no score change

  `ERROR`           Late answer arrives `ERROR`           Ignore result

  Any state         Result from an      Unchanged         Discard stale
                    older round arrives                   result
  -------------------------------------------------------------------------

### 5.3 State invariants

-   Only `READY` agents can be selected.
-   Only the currently selected `READY` agent can be graded.
-   Each agent can receive at most one grade per round.
-   `ANSWERED` agents cannot be graded again during the same round.
-   `ERROR` and `THINKING` agents cannot be selected or graded.
-   An answer is available only for a successful current-round response.
-   Invalid or empty questions do not start a round and do not reset
    existing state.
-   Only the controller mutates domain state in response to worker
    results.
-   A stale result cannot replace current-round state.

## 6. UI layout

### 6.1 Window and coordinate system

-   Logical window: **1280 × 720**.
-   Target: 60 FPS, with a fixed logical layout and time-based
    animations.
-   Background: light, muted classroom color; use simple rectangles and
    lines for floor, wall, and board.
-   Use a consistent margin of approximately 20--28 px.
-   UI text is Romanian. Student proper names remain as specified.
-   Use readable contrast, minimum practical body text size around 16
    px, and larger section headings.
-   If the requested system font is unavailable, select a fallback font
    that supports `ă â î ș ț` and `Ă Â Î Ș Ț`.

### 6.2 Approximate layout map

``` text
1280 × 720
┌──────────────────────────────────────────────────────────────────────────────┐
│ AI CLASSROOM — Întrebarea profesorului                                       │ y=0..70
├──────────────────────────────────────────────────────────────────────────────┤
│ [ Introdu întrebarea.............................. ] [ÎNTREABĂ]              │ y=80..135
├───────────────────────────────────────────────────────┬──────────────────────┤
│                                                       │ CLASAMENT            │
│  Rând 1:   [ChatGPT]   [Gemini]   [Copilot]           │ 1. ChatGPT       0   │
│             desks + student sprites                   │ 2. Gemini        0   │
│                                                       │ 3. Copilot       0   │
│  Rând 2:   [Grok]      [Claude]   [DeepSeek]          │ 4. Grok          0   │
│             desks + student sprites                   │ 5. Claude        0   │
│                                                       │ 6. DeepSeek      0   │
│                                                       │                      │
│  Teacher sprite moves between desk positions          │                      │
├───────────────────────────────────────────────────────┴──────────────────────┤
│ Status: „Elevii se gândesc...” / „Alege un elev care a ridicat mâna.”        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Coordinate guidance

Coordinates are approximate and may be adjusted for legibility while
preserving the layout:

-   Header: `x=20, y=12, w=1240, h=50`.
-   Question input: `x=24, y=84, w=980, h=42`.
-   Ask button: `x=1020, y=84, w=236, h=42`.
-   Classroom play area: `x=20, y=145, w=900, h=520`.
-   Scoreboard: `x=940, y=150, w=316, h=430`.
-   Status line: `x=24, y=675, w=1232, h=28`.
-   Desk columns centered approximately at `x=170`, `x=455`, and
    `x=740`.
-   Desk rows centered approximately at `y=285` and `y=495`.
-   Teacher's initial position: near the front of the classroom,
    approximately `(455, 600)`.
-   Speech bubble: positioned in an unobstructed area of the classroom,
    initially around `x=80, y=155, w=800, h=170`; its position may adapt
    to the selected desk and available space.
-   GOOD/BAD buttons: placed inside or immediately below the
    speech-bubble panel, with sufficient separation to prevent
    accidental clicks.

The scene must prevent the bubble from covering the question input or
scoreboard. If a bubble overlays desks, clicking the bubble must not
accidentally select an obscured student.

### 6.4 Visual design

-   Students: circle head, rectangle torso, simple arms/legs, unique
    color, and name tag.
-   Desks: simple filled rectangles with outlines; no textures required.
-   Thinking: ellipsis cycles visually above the head.
-   Ready: raised hand, gentle bounce, and visible readiness cue.
-   Answered: neutral pose and a discreet completion marker.
-   Error: visible `EROARE`/`ERR` indicator plus a short status
    explanation.
-   Teacher: simple distinct character; movement speed should be
    consistent across frame rates.
-   Speech bubble: rounded rectangle, readable text, and scroll
    affordance when text overflows.
-   Floating score: `+1` or `-1`, shown briefly near the graded student.
-   Scoreboard: score and ranking update immediately after a grade is
    accepted.
-   No flashing effects that could be uncomfortable; animation should
    remain subtle.

### 6.5 Interaction behavior

1.  The teacher enters a question and presses **ÎNTREABĂ** or Enter.
2.  If empty, show `Introduceți o întrebare înainte de a începe.` and
    preserve the current round.
3.  On a valid question, clear the prior answer bubble/selection and
    start a new round.
4.  All six students enter `THINKING`; the GUI remains responsive.
5.  Each student independently changes to `READY` or `ERROR` as a result
    arrives or times out.
6.  Clicking a READY student selects that student and animates the
    teacher toward the desk.
7.  After arrival, show the student's answer in a speech bubble and
    enable **BUN** and **GREȘIT** (labels may alternatively be **GOOD**
    and **BAD** if required for the demonstration; one convention must
    be used consistently).
8.  Clicking a grade applies +1 for GOOD or -1 for BAD exactly once,
    transitions the agent to `ANSWERED`, updates ranking, and displays
    the floating delta.
9.  The teacher may select another READY student. The current bubble is
    replaced when another student is selected.
10. A new question begins a new round and clears per-round answer/grade
    states while retaining cumulative scores.
11. Closing the window triggers clean shutdown.

## 7. Configuration, secrets, and error handling

### 7.1 Environment configuration

Supported settings:

  ------------------------------------------------------------------------------------------------
  Variable                                      Required Default                  Meaning
  -------------------------------- --------------------- ------------------------ ----------------
  `GEMINI_API_KEY`                                    No unset                    Credential for
                                                                                  optional Gemini
                                                                                  integration

  `AI_CLASSROOM_PROVIDER`                             No `mock` when no key;      Provider
                                                         otherwise configured     preference,
                                                         choice                   e.g. `mock` or
                                                                                  `gemini`

  `AI_CLASSROOM_TIMEOUT_SECONDS`                      No `30`                     Per-agent
                                                                                  controller
                                                                                  deadline

  `AI_CLASSROOM_MOCK_SEED`                            No unset                    Optional
                                                                                  deterministic
                                                                                  seed for
                                                                                  reproducible
                                                                                  demos

  `AI_CLASSROOM_HISTORY_PATH`                         No `results/history.json`   Local history
                                                                                  file path

  `AI_CLASSROOM_LOG_LEVEL`                            No `INFO`                   Logging
                                                                                  verbosity
  ------------------------------------------------------------------------------------------------

If `AI_CLASSROOM_PROVIDER=gemini` but the key is absent, log a warning
and use mock mode. If the provider name is invalid, fail configuration
validation with a clear message or safely fall back to mock mode; choose
one policy and test it. Mock mode must work without any `.env` file.

`.env.example` should document the variable names with placeholder
values only, for example `GEMINI_API_KEY=replace_me`. Never include a
real key in source control.

### 7.2 `.gitignore` requirements

At minimum, ignore:

``` gitignore
.env
.venv/
venv/
__pycache__/
.pytest_cache/
*.py[cod]
results/history.json
*.log
```

Do not ignore `.env.example`. Do not commit API keys, request headers,
local virtual environments, logs containing sensitive data, or generated
personal history.

### 7.3 Error handling policy

-   **Empty question:** reject before changing state; show a Romanian
    validation message.
-   **Provider exception:** capture it in the worker boundary; convert
    it to an error result.
-   **Gemini error:** attempt mock fallback; use the fallback result if
    available.
-   **Timeout:** mark the affected agent `ERROR` after 30 seconds, even
    if the worker is still blocked. Use finite network timeouts and
    ignore late results.
-   **Invalid/empty answer:** treat as provider failure; try fallback
    where configured.
-   **Stale result:** discard silently or log at debug level; never
    apply it to the current round.
-   **Unknown student ID:** raise a clear domain exception; do not
    mutate scores.
-   **Illegal selection/grading:** reject without changing score/state;
    display a concise Romanian message where user initiated.
-   **History read failure:** continue with empty history and show/log a
    warning.
-   **History write failure:** keep the accepted grade in memory, report
    that it could not be saved, and continue running.
-   **Unexpected GUI exception:** log traceback to a local log file
    without exposing credentials; show a generic user-friendly error
    where safe.
-   **Shutdown:** stop accepting new rounds, cancel queued work where
    possible, and release pygame resources. Running Python threads
    cannot be forcibly killed; all provider calls therefore need finite
    timeouts and shutdown must have a defined bounded-wait policy.

### 7.4 Logging

-   Use Python's `logging` module.
-   Log application startup, selected provider name, round IDs, state
    transitions, provider failure categories, timeout events, and
    persistence failures.
-   Never log `GEMINI_API_KEY`, environment dumps, authorization
    headers, or unnecessary full prompt contents.
-   Avoid recording more personal data than necessary. Since questions
    and answers may be saved to history, make that behavior clear in the
    README.

## 8. Testing strategy

### 8.1 General requirements

-   Use pytest.
-   Unit tests for `core/` must run without pygame initialization,
    network access, a Gemini key, or a display.
-   Provider tests use seeded mock instances and zero-delay
    configurations where possible.
-   Gemini tests use fake clients/providers; no live API call is
    required.
-   Tests should avoid arbitrary long sleeps. Inject clocks or deadlines
    where practical; otherwise use short configurable timeout values in
    isolated tests.
-   Each test should assert both the returned result and relevant
    state/score side effects.

### 8.2 Concrete unit test cases

#### Models and state validation

1.  `test_agent_initial_state_is_idle`
    -   A new agent starts in `IDLE`, has no answer/error, and no grade
        for a round.
2.  `test_agent_reset_for_round_clears_round_fields`
    -   Reset clears answer, error, and per-round grade metadata.
3.  `test_agent_ready_requires_answer`
    -   A successful transition stores the supplied answer and sets
        `READY`.
4.  `test_agent_error_stores_message`
    -   An error transition sets `ERROR` and stores a safe message.
5.  `test_invalid_state_transition_is_rejected`
    -   A transition disallowed by the model/controller contract raises
        a documented exception or is rejected without mutation.

#### Scoreboard

6.  `test_good_grade_adds_one_point`
    -   Score changes from 0 to 1.
7.  `test_bad_grade_subtracts_one_point`
    -   Score changes from 0 to -1.
8.  `test_multiple_grades_accumulate`
    -   GOOD, GOOD, BAD yields a score of 1.
9.  `test_unknown_agent_score_raises_key_error`
    -   Unknown IDs are rejected.
10. `test_ranking_is_descending`
    -   Higher scores appear before lower scores.
11. `test_ranking_ties_are_deterministic`
    -   Equal scores follow the documented stable order.
12. `test_reset_zeros_all_registered_scores`
    -   All registered scores become zero and registered IDs remain
        unchanged.

#### Classroom controller and state machine

13. `test_empty_question_is_rejected_without_starting_round`
    -   `""` and whitespace-only input raise `ValueError`; no tasks are
        submitted and state remains unchanged.
14. `test_ask_sets_all_agents_to_thinking`
    -   A valid question creates a round ID and moves all six agents to
        `THINKING`.
15. `test_answers_are_requested_for_all_agents`
    -   A fake provider records one request per agent.
16. `test_successful_result_moves_agent_to_ready`
    -   A valid current-round result changes only the matching agent to
        `READY`.
17. `test_failed_result_moves_agent_to_error`
    -   A provider failure sets `ERROR` with a message.
18. `test_only_ready_agent_can_be_selected`
    -   Selecting an `IDLE`, `THINKING`, `ANSWERED`, or `ERROR` agent is
        rejected.
19. `test_select_ready_agent_sets_selection`
    -   Selecting a READY agent makes it the selected agent without
        changing score.
20. `test_only_selected_agent_can_be_graded`
    -   Grading a different READY agent is rejected and no score
        changes.
21. `test_good_grade_changes_state_and_score_once`
    -   The selected READY agent becomes `ANSWERED`, and score increases
        by one.
22. `test_bad_grade_changes_state_and_score_once`
    -   The selected READY agent becomes `ANSWERED`, and score decreases
        by one.
23. `test_second_grade_in_same_round_is_rejected`
    -   A repeated grade has no score side effect.
24. `test_new_round_resets_agent_states_but_preserves_scores`
    -   Agents return to THINKING and cumulative scores remain
        unchanged.
25. `test_stale_result_from_previous_round_is_ignored`
    -   A late result from an older round cannot alter the new round.
26. `test_late_result_after_timeout_is_ignored`
    -   An agent remains in ERROR after a delayed result arrives.
27. `test_per_agent_timeout_does_not_block_polling`
    -   Polling remains prompt while another provider call is still
        running.
28. `test_completed_future_is_not_processed_twice`
    -   One result produces one state transition only.
29. `test_close_shuts_down_executor`
    -   The controller rejects or safely handles new work after closure
        and releases executor resources.

#### History

30. `test_missing_history_file_returns_empty_list`
    -   Loading a nonexistent file returns an empty list.
31. `test_save_and_load_round_round_trips`
    -   A saved round can be loaded with equivalent IDs, question,
        states, answers, and timestamps.
32. `test_history_preserves_romanian_diacritics`
    -   Text such as `întrebare`, `școală`, and `răspuns` round-trips
        correctly.
33. `test_corrupt_json_is_handled_safely`
    -   Invalid JSON does not crash startup and results in a
        warning/empty history.
34. `test_unsupported_schema_version_is_handled`
    -   A schema version not supported by the app is rejected safely.
35. `test_grade_update_changes_correct_agent_only`
    -   A grade update changes the requested agent's record and leaves
        others unchanged.
36. `test_write_failure_does_not_undo_score`
    -   Simulated disk failure is reported, while the in-memory score
        remains applied.

#### Mock provider

37. `test_mock_provider_returns_nonempty_string`
    -   The provider returns non-empty answer text.
38. `test_mock_provider_is_reproducible_with_seed`
    -   Equivalent seeded instances produce the same configured
        output/delay sequence for the same call order.
39. `test_mock_provider_supports_zero_delay`
    -   A zero-delay test configuration completes without deliberate
        waiting.
40. `test_mock_provider_personality_varies_by_agent`
    -   At least two agent profiles produce distinguishable styles under
        controlled fixtures.
41. `test_mock_wrong_answer_probability_is_configurable`
    -   Probability zero never deliberately selects the wrong-answer
        path; probability one always does under deterministic fixtures.
42. `test_mock_provider_does_not_use_global_random_state`
    -   Calls do not alter the global random generator state.

#### Gemini provider (with fakes)

43. `test_gemini_success_returns_plain_text`
    -   A successful fake response becomes a plain string.
44. `test_gemini_error_uses_mock_fallback`
    -   A simulated SDK error returns fallback text.
45. `test_gemini_empty_response_uses_fallback`
    -   Empty output triggers fallback.
46. `test_gemini_and_fallback_failure_raises_provider_error`
    -   Dual failure is represented as a safe provider error.
47. `test_gemini_errors_do_not_leak_api_key`
    -   Error strings/logs do not include the test key.
48. `test_missing_key_selects_mock_provider`
    -   Startup configuration uses mock mode when the key is absent.

#### GUI smoke/manual tests

These tests may be separate from headless unit tests:

49. Window opens at 1280 × 720 and runs at a target of 60 FPS on a
    typical desktop.
50. All six students are visible in two rows of three with distinct
    colors and readable labels.
51. The GUI remains responsive while all six mock answers are being
    generated.
52. Thinking ellipses animate and READY students raise their hands and
    bounce subtly.
53. Clicking a non-READY student does not select or grade them.
54. Clicking a READY student moves the teacher to the corresponding
    desk.
55. Long answers wrap and can be scrolled without overlapping grade
    controls.
56. GOOD/BAD actions update the scoreboard and show `+1`/`-1`.
57. Starting a new round invalidates late results and preserves
    cumulative scores.
58. The app starts without `.env` or network access.
59. Closing the window does not leave the app's own executor or pygame
    resources unmanaged.

## 9. Acceptance criteria

The release is accepted when all applicable items below pass.

-   [ ] Application starts with Python 3.11+ using the documented setup.
-   [ ] Main window is 1280 × 720 and targets 60 FPS.
-   [ ] All interface labels and system messages are in Romanian and
    Romanian diacritics render correctly.
-   [ ] Six named students appear in two rows of three, each with a
    distinct color and simple shape-based character.
-   [ ] No official AI logos or external images are used.
-   [ ] The question input rejects empty/whitespace-only questions
    without resetting the current round.
-   [ ] A valid question moves all six agents to THINKING and requests
    answers concurrently.
-   [ ] The GUI never waits synchronously for unfinished provider calls.
-   [ ] Results reach the main thread through `queue.Queue` and are
    polled every frame.
-   [ ] Each agent independently reaches READY or ERROR.
-   [ ] A per-agent 30-second deadline is enforced, and late results are
    ignored.
-   [ ] Only READY students are selectable.
-   [ ] The teacher walks to the selected desk using time-based
    interpolation/easing.
-   [ ] The selected answer appears in a readable, word-wrapped,
    scrollable speech bubble after the teacher arrives.
-   [ ] Grade controls are enabled only for the selected READY agent
    after arrival.
-   [ ] GOOD adds exactly one point; BAD subtracts exactly one point.
-   [ ] Each agent can be graded at most once per round.
-   [ ] The scoreboard displays all six students and a deterministic
    descending ranking.
-   [ ] A floating `+1` or `-1` animation appears after successful
    grading.
-   [ ] A new round resets per-round states but preserves cumulative
    scores.
-   [ ] Core logic imports no pygame and is fully testable without
    opening a window.
-   [ ] Mock mode works offline, supports a seed, configurable delay,
    varied personalities, and configurable intentionally wrong answers.
-   [ ] Gemini mode is optional, reads credentials from environment
    configuration, has finite timeouts, and falls back to mock on
    provider errors.
-   [ ] No API key is committed, displayed, or written to logs/history.
-   [ ] History is stored in versioned JSON under
    `results/history.json`, preserves Romanian characters, and fails
    safely.
-   [ ] pytest unit tests cover core state rules, scoring, history,
    concurrency edge cases, and mock-provider behavior.
-   [ ] PEP 8, type hints, and docstrings are applied consistently.
-   [ ] Shutdown closes pygame and the controller executor using a
    documented bounded-wait strategy.

## 10. Coding standards and maintainability

### 10.1 Style

-   Follow PEP 8 for naming, whitespace, imports, and line length.
-   Use `snake_case` for modules, functions, and variables; `PascalCase`
    for classes; and `UPPER_SNAKE_CASE` for constants.
-   Use type hints for public functions, method parameters, return
    values, and important data structures.
-   Add docstrings to modules, classes, and public methods describing
    purpose, inputs, outputs, and relevant exceptions.
-   Prefer small functions with one responsibility.
-   Avoid duplicated state-machine rules across the controller and GUI.
-   Use explicit exceptions for invalid operations instead of silent
    failure.
-   Keep magic numbers in named constants or configuration.
-   Use `pathlib.Path` for filesystem paths where practical.
-   Use `logging`, not scattered `print()` calls, for operational
    diagnostics.

### 10.2 Dependency boundaries

-   `core/` may import Python standard-library modules and other `core/`
    modules only. It must never import pygame, provider SDKs, or GUI
    modules.
-   `providers/` may import the provider interface, domain models,
    standard library modules, and the optional provider SDK. It must
    never import GUI modules.
-   `gui/` may import pygame, domain models, and the public classroom
    controller interface. It must not implement scoring or state-machine
    transitions itself.
-   `main.py` is the composition root and may wire core, providers, and
    GUI together.
-   Tests for core must not require pygame initialization.
-   Worker threads communicate results via immutable/result records and
    a thread-safe queue. Only the controller's polling path applies
    changes to domain state.

### 10.3 Quality and documentation

-   Pin or constrain dependencies to versions verified with Python
    3.11+.
-   Document virtual-environment setup, installation, test execution,
    mock mode, Gemini configuration, history location, and
    troubleshooting.
-   Keep the mock provider as the default development/test path.
-   Add regression tests whenever a state transition, timeout, fallback,
    or persistence bug is fixed.
-   Do not add dependencies without a clear need.
-   Do not put implementation code in this specification; implementation
    details should follow these contracts.

## 11. Definition of done

The specification is fulfilled by an implementation that passes the
acceptance checklist, keeps the GUI responsive during concurrent work,
preserves strict separation between domain logic and rendering, and can
run and be tested offline without Gemini credentials. Any deviation from
the public interfaces or state rules above must be documented and
covered by tests.
