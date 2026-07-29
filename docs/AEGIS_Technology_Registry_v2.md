# AEGIS Technology Registry v2

*Технологическая конституция персональной AI-операционной системы*

Версия: 2.0  
Дата среза: 29 июля 2026 года  
Целевая инфраструктура: Windows Workstation ↔ Ubuntu AI Server

> **Статус документа.** Технологии со статусом `ACTIVE` уже приняты. `LOCKED_PLANNED` зафиксированы для будущей реализации. `CANDIDATE` и `EXPERIMENTAL` требуют изолированного теста, сравнения, RFC и явного одобрения владельца.

## 1. Резюме решений

Этот документ обновляет технологический реестр AEGIS с учётом фактической архитектуры проекта, внешнего GreenBoost и актуальных моделей Hugging Face. Главная цель — максимально использовать зрелые внешние компоненты и не разрабатывать с нуля то, что уже качественно решено upstream-проектами.

Главное решение: используется именно `gitlab.com/IsolatedOctopi/greenboost`. GreenBoost выбирается как внешний NVIDIA/CUDA-слой для расширения памяти, квантизации, кластерного исполнения, модели-сервера и телеметрии. AEGIS не копирует его внутренности и общается с ним через GB-Synapse, MCP, CLI и наблюдаемую телеметрию. Заявленные возможности считаются утверждениями upstream до собственного benchmark.

Ключевые изменения:

- внутренние AEGIS `probes`, `ledger`, `policy` и `admission` сохраняются, но относятся к **Resource Governance**, а не к внешнему GreenBoost;
- текущий Qwen3-Coder остаётся рабочей базой до измерений;
- Qwen3-Coder-30B-A3B и Qwen3-Coder-Next добавляются как кандидаты coding-agent режима через GreenBoost;
- Qwen3-VL-4B остаётся основным 8 ГБ vision/UI-профилем;
- Qwen3-ASR и Qwen3-TTS становятся приоритетными кандидатами Voice Runtime;
- BGE-M3 сохраняется как активный embedding baseline;
- Docling, MarkItDown, OmniParser, Playwright, pywinauto, Tree-sitter, SCIP, OpenTelemetry и Qdrant рассматриваются как готовые строительные блоки;
- production-зависимости должны фиксироваться по версии, revision, commit SHA или Docker digest.

## 2. Статусы

| Статус | Значение |
|---|---|
| `ACTIVE` | Уже используется и принято владельцем. |
| `LOCKED_PLANNED` | Выбрано для будущего этапа, но ещё не принято в production. |
| `CANDIDATE` | Допущено к сравнению и benchmark. |
| `EXPERIMENTAL` | Высокий риск, низкоуровневая интеграция или недостаточно подтверждённая зрелость. |
| `OPTIONAL` | Не является обязательной частью AEGIS Core. |

## 3. Архитектурные принципы

### 3.1 Provider-first

Бизнес-логика AEGIS зависит от интерфейсов, а не от конкретной модели или runtime. Любая модель должна быть заменяема конфигурацией.

### 3.2 External service boundary

GPL, kernel-level и быстро меняющиеся проекты запускаются отдельно и интегрируются через API, CLI или MCP. Исходники таких систем не копируются внутрь AEGIS Core без отдельного решения.

### 3.3 No silent fallback

При выбранном remote/GreenBoost режиме ошибка должна быть явной. Автоматический переход на другой provider разрешён только политикой с записью в аудит.

### 3.4 Benchmark before replacement

Новая модель не становится основной только потому, что она новее или выше в публичном leaderboard. Она должна пройти тесты на русском языке, latency, VRAM/RAM, tool use, устойчивость и качество на реальных задачах владельца.

### 3.5 One Active Vertical

Одновременно реализуется один вертикальный этап. Исследование кандидатов допустимо, но production-разработка не распараллеливается между roadmap-этапами.

### 3.6 Security by default

Действия над файлами, UI, почтой и системой остаются под политиками AEGIS, даже если внешний агент или runtime умеет выполнять инструменты самостоятельно.

### 3.7 Pinned production

В production запрещены необязанные `latest`, `main`, `master` и плавающие model revisions. После acceptance фиксируются:

- Git commit SHA;
- Docker image digest;
- Python/package version;
- Hugging Face model revision;
- CUDA/driver compatibility;
- checksum и rollback-процедура, где применимо.

## 4. Целевое железо

| Профиль | GPU/VRAM | RAM | Назначение | Ограничение |
|---|---:|---:|---|---|
| Ubuntu AI Server | RTX 3050 8 ГБ | 32 ГБ DDR4 | LLM, OCR, embeddings, ComfyUI, voice | Один тяжёлый GPU workload одновременно. |
| Windows Workstation | RTX 3050 8 ГБ | 32 ГБ DDR5 | UI, файлы, desktop automation, возможный feeder node | Не должен терять отзывчивость рабочего стола. |
| Две текущие машины | 2× RTX 3050 8 ГБ по LAN | 64 ГБ суммарно | GreenBoost cluster experiments | LAN не эквивалентен локальной VRAM; необходим benchmark. |
| Будущий NVIDIA-профиль | RTX 3090 24 ГБ | 32–64 ГБ | 30B/32B, VLM, длинный контекст | Проверить питание, охлаждение и состояние карты. |
| Возможный AMD workstation | Radeon RX 9070 XT | 32 ГБ DDR5 | Игры и локальный UI | GreenBoost ориентирован на NVIDIA; AI server должен оставаться NVIDIA. |

## 5. GreenBoost

### 5.1 Выбранный upstream

- Репозиторий: `gitlab.com/IsolatedOctopi/greenboost`
- Статус: `SELECTED / EXPERIMENTAL`
- Роль: внешний вычислительный слой AEGIS.

На дату среза upstream заявляет следующие подсистемы:

- GB-Tiering;
- GB-Quant;
- GB-Cluster;
- GB-Synapse;
- GB-Dataflux;
- GB-CLI;
- MCP-серверы;
- режимы с kernel module и без него;
- совместимость с CUDA 12/13 и несколькими inference runtime.

Ни одна из этих возможностей не считается подтверждённой на нашем железе до воспроизводимого теста.

### 5.2 Граница ответственности

| AEGIS сохраняет | GreenBoost предоставляет | AEGIS не пишет заново |
|---|---|---|
| `ExecutionOrchestratorRuntime` | GB-Tiering | CUDA memory paging/virtualization |
| Resource Governance policy | GB-Quant | квантизацию весов и KV-cache |
| Service compatibility rules | GB-Cluster | сетевое объединение NVIDIA GPU |
| Dangerous-action confirmation | GB-Synapse | дублирующий model proxy |
| Provider selection/fallback | GB-Dataflux | низкоуровневую GPU telemetry |
| Project/job state | MCP/CLI control surfaces | kernel module и cluster fabric |

### 5.3 Рекомендуемая архитектура

```text
ExecutionOrchestratorRuntime
├── ResourceGovernance
│   ├── ProbeService
│   ├── ResourceLedger
│   ├── PolicyEngine
│   └── AdmissionController
└── RuntimeProviderRegistry
    ├── OllamaProvider
    └── GreenBoostProvider
        ├── GBSynapseClient
        ├── GBDatafluxClient
        ├── GBCapabilityDiscovery
        └── GBMcpAdapter
```

### 5.4 Что сохраняем из текущих наработок

- `probes.py` — сбор фактов о GPU, RAM, CPU, дисках, контейнерах и сервисах;
- `ledger.py` — состояние ресурсов и активных workload AEGIS;
- `policy.py` — режимы Performance, Balanced, Eco и Emergency;
- `admission.py` — решение `ALLOW`, `WAIT`, `DENY` или `DEGRADE` до запуска job;
- `ExecutionOrchestratorRuntime` — единственный верхнеуровневый оркестратор;
- существующие provider contracts, CLI, конфигурацию, logging и тестовую инфраструктуру.

### 5.5 Что откладываем или отменяем

- универсальный Reservation Engine;
- собственный GPU scheduler;
- собственный VRAM virtualizer;
- собственную сетевую GPU fabric;
- model proxy, дублирующий GB-Synapse;
- копирование GreenBoost-кода внутрь AEGIS.

### 5.6 Acceptance-план

1. Зафиксировать Ubuntu kernel, NVIDIA driver, CUDA, Docker и текущую конфигурацию.
2. Сделать backup/rollback-план.
3. Проверить GreenBoost сначала в isolated/no-kmod или Light-профиле.
4. Снять Ollama baseline на одинаковом prompt-наборе.
5. Проверить GB-Synapse API, streaming, health и ошибки.
6. Проверить GB-Dataflux и возможность связать метрики с `job_id`/`trace_id` AEGIS.
7. Проверить single-node tiering.
8. Проверить dual-node cluster только после стабильного single-node режима.
9. Измерить tokens/s, time-to-first-token, p50/p95 latency, RAM, VRAM, NVMe I/O и recovery после OOM/сбоя.
10. Убедиться, что отключение GreenBoost возвращает систему к принятому Ollama пути.
11. Зафиксировать commit SHA и конфигурацию только после owner approval.

## 6. LLM и coding models

### 6.1 Текущий provider

| Компонент | Статус | Решение |
|---|---|---|
| Ollama | `ACTIVE` | Сохранить как baseline и fallback runtime. |
| `qwen3-coder:latest` | `ACTIVE`, dev only | Продолжать использовать; перед production закрепить точный tag/digest. |
| Qwen3-Coder family | `LOCKED_PLANNED` | Основное направление coding/repository intelligence. |

### 6.2 Кандидаты

| Модель | Статус | Целевой профиль | Решение |
|---|---|---|---|
| Qwen3-Coder-30B-A3B-Instruct | `CANDIDATE` | 2×8 ГБ через GreenBoost или 24 ГБ NVIDIA | Главный реалистичный сильный coding benchmark. |
| Qwen3-Coder-Next | `EXPERIMENTAL` | GreenBoost + RAM/NVMe или 24 ГБ+ | High-end coding-agent benchmark; total weights остаются тяжёлыми даже при малом числе active parameters. |
| Qwen3.5 9B-class | `CANDIDATE` | 8 ГБ quant | Универсальный reasoning/tool-use кандидат. |

### 6.3 Benchmark coding-моделей

Проверять:

- редактирование существующего AEGIS-кода;
- генерацию patch/diff вместо полного переписывания файлов;
- способность удерживать архитектурные ограничения;
- tool calling и структурированный JSON;
- Python, PowerShell, Bash, Docker Compose и Windows automation;
- исправление failing tests;
- работу с длинным repository context;
- склонность выдумывать файлы, символы и API;
- скорость и потребление памяти.

До завершения benchmark текущая модель не заменяется.

## 7. Vision и UI Understanding

### 7.1 Основная модель

| Модель | Статус | Назначение |
|---|---|---|
| Qwen3-VL-4B-Instruct | `LOCKED_PLANNED` | Основной vision/UI профиль для RTX 3050 8 ГБ. |
| Qwen3-VL-8B-Instruct | `CANDIDATE` | Более качественный профиль при приемлемой latency. |
| Qwen3-VL-30B-A3B / 32B-class | `EXPERIMENTAL` | GreenBoost или будущая RTX 3090; complex UI/video benchmark. |

### 7.2 UI pipeline

```text
Screenshot
├── OmniParser → UI elements and bounding boxes
├── OCR Runtime → visible text
└── Qwen3-VL → semantic understanding and planning
                    ↓
                  UI Graph
```

Qwen3-VL не должен в одиночку отвечать за детекцию всех интерактивных элементов. OmniParser рассматривается как отдельный `UIElementDetectionProvider`, OCR — как отдельный источник текста, а VLM — как reasoning layer.

### 7.3 Обязательные ограничения

- multi-monitor awareness;
- visual verification после действия;
- запрет клика только по предположению модели;
- OCR/VLM prompt-injection protection;
- taint tracking для текста с экрана;
- подтверждение опасных действий.

## 8. OCR

| Компонент | Статус | Решение |
|---|---|---|
| PaddleOCR provider | `ACTIVE` | Сохранить как специализированный OCR baseline. |
| Unlimited OCR provider | `ACTIVE` | Сохранить существующий принятый путь. |
| Qwen3-VL OCR | Дополнительный | Использовать для смыслового разбора, но не заменять специализированный OCR без benchmark. |

Специализированный OCR остаётся предпочтительным для скорости, стабильности и массовой обработки документов.

## 9. Embeddings, reranking и memory

### 9.1 Embeddings

| Модель | Статус | Решение |
|---|---|---|
| BAAI/bge-m3 | `ACTIVE` | Основной multilingual baseline для документов, кода, RAG и project memory. |
| Qwen3-Embedding-0.6B | `CANDIDATE` | Быстрый универсальный кандидат. |
| Qwen3-Embedding larger profiles | `CANDIDATE` | Проверить качество retrieval против latency/RAM. |
| Qwen3-VL-Embedding | `EXPERIMENTAL` | Кандидат для мультимодальной памяти скриншотов, UI и изображений. |

### 9.2 Reranker

`BAAI/bge-reranker-v2-m3` получает статус `LOCKED_PLANNED` как лёгкий multilingual reranker. Он должен включаться после первичного retrieval, а не заменять embedding index.

### 9.3 Vector storage

| Компонент | Статус | Решение |
|---|---|---|
| SQLite/local index | `ACTIVE/FOUNDATION` | Допустим для ранней версии и небольшого корпуса. |
| Qdrant | `CANDIDATE` | Локальный service после corpus benchmark, особенно для payload filtering и нескольких коллекций. |

Не следует вводить Qdrant только ради моды. Переход оправдан, если локальный индекс перестанет удовлетворять требованиям по фильтрации, объёму, скорости или обслуживанию нескольких типов памяти.

## 10. Voice Runtime

### 10.1 Speech-to-text

| Компонент | Статус | Решение |
|---|---|---|
| faster-whisper + whisper-large-v3-turbo | `LOCKED_PLANNED` | Надёжный baseline и fallback. |
| Qwen3-ASR-0.6B | `CANDIDATE` | Realtime/low-latency benchmark. |
| Qwen3-ASR-1.7B | `CANDIDATE` | Quality benchmark на русском и английском. |
| Silero VAD | `LOCKED_PLANNED` | Основной VAD provider. |

### 10.2 Text-to-speech

| Компонент | Статус | Решение |
|---|---|---|
| Qwen3-TTS-0.6B | `CANDIDATE` | Streaming/low-latency профиль. |
| Qwen3-TTS-1.7B | `CANDIDATE` | Quality/voice benchmark. |
| CPU TTS fallback | `MANDATORY` | Должен работать, когда GPU занят OCR, Vision или ComfyUI. |
| AIRI unspeech | `CANDIDATE` | Возможный unified ASR/TTS proxy или adapter. |

### 10.3 Voice benchmark

Проверять:

- русский и английский;
- задержку до первого аудиофрагмента;
- streaming;
- шум, микрофон и перебивания;
- потребление VRAM;
- одновременную работу с LLM;
- естественность и стабильность голоса;
- приватность reference audio;
- корректное прекращение генерации.

## 11. Document Intelligence

### 11.1 Основной стек

| Компонент | Статус | Назначение |
|---|---|---|
| Docling | `LOCKED_PLANNED` | Основной parser для PDF, DOCX, PPTX, XLSX, layout, reading order, таблиц и структурированного document model. |
| MarkItDown | `LOCKED_PLANNED` | Быстрый и лёгкий fallback для преобразования файлов в Markdown. |
| MinerU | `CANDIDATE` | Benchmark на сложных PDF, формулах и многостолбцовых документах. |
| Existing OCR Runtime | `ACTIVE` | Сканированные и OCR-heavy документы. |

### 11.2 Архитектура

```text
DocumentRuntime
├── DoclingProvider
├── MarkItDownProvider
├── MinerUProvider (optional candidate)
└── OCRRuntimeAdapter
```

AEGIS не должен писать собственные универсальные PDF/DOCX/PPTX/XLSX-парсеры с нуля. Его зона ответственности:

- provider abstraction;
- provenance;
- безопасный доступ к файлам;
- chunking и indexing;
- project links;
- error normalization;
- artifact lifecycle.

## 12. Desktop и browser automation

### 12.1 Windows UI

`pywinauto` получает статус `LOCKED_PLANNED` как основной низкоуровневый provider для Win32 и Microsoft UI Automation.

```text
WindowsUIRuntime
└── PywinautoProvider
```

Над ним остаются политики AEGIS:

- разрешения;
- confirmation gates;
- visual verification;
- safe typing;
- rollback, где возможен;
- audit log;
- запрет необратимых действий без подтверждения.

### 12.2 Browser Runtime

Playwright получает статус `LOCKED_PLANNED`.

```text
BrowserRuntime
└── PlaywrightProvider
```

Не следует писать собственный Selenium-подобный движок. AEGIS добавляет поверх Playwright:

- allowlist доменов;
- browser profile isolation;
- download policy;
- credential handling;
- prompt-injection isolation;
- screenshot/DOM verification;
- подтверждение отправки форм, покупок и сообщений.

## 13. Repository Intelligence

### 13.1 Tree-sitter

Статус: `LOCKED_PLANNED`.

Используется для:

- AST/CST;
- classes, functions, imports;
- устойчивого разбора незавершённого кода;
- symbol extraction;
- incremental parsing;
- построения repository graph.

### 13.2 SCIP

Статус: `LOCKED_PLANNED`.

Используется как стандартный code-intelligence формат для:

- definitions;
- references;
- implementations;
- cross-file symbol links;
- language-independent index.

### 13.3 Итоговая схема

```text
Repository
├── Tree-sitter → local syntax/AST graph
├── SCIP index → semantic symbol graph
├── BGE-M3/Qwen embeddings → semantic retrieval
└── Git → history, commits and diffs
                       ↓
          Repository Intelligence Runtime
```

AEGIS не должен писать собственные парсеры языков программирования.

## 14. Distributed Windows ↔ Ubuntu Runtime

### 14.1 Базовый кандидат

Dramatiq + Redis получает статус `CANDIDATE` для первой production-версии распределённых задач.

Преимущества:

- Python-first;
- простая эксплуатация;
- retries;
- очереди;
- меньше инфраструктурной тяжести, чем Temporal;
- подходит для двух домашних машин.

### 14.2 Experimental candidate

Temporal получает статус `EXPERIMENTAL`.

Он полезен для durable workflows, signals, queries и long-running recovery, но может оказаться избыточным и дублировать `ExecutionOrchestratorRuntime`. Рассматривать только после отдельного architecture benchmark.

### 14.3 Неосновной кандидат

Celery не выбирается как базовая схема Windows ↔ Ubuntu из-за сложности эксплуатации и официально слабой поддержки Windows.

## 15. Observability и Security

### 15.1 OpenTelemetry

Статус: `LOCKED_PLANNED`.

Используется для:

- traces;
- metrics;
- context propagation;
- связывания remote jobs;
- provider latency;
- runtime health;
- экспортёров и dashboard integration.

OpenTelemetry не заменяет:

- structured application logs;
- отдельный неизменяемый audit log;
- security events;
- пользовательские confirmations.

### 15.2 Safety classifier

Qwen3Guard-0.6B может рассматриваться как `CANDIDATE` лёгкого дополнительного classifier. Он не является единственным защитным механизмом и не может самостоятельно разрешать опасные действия.

Главная защита остаётся policy-based:

- least privilege;
- allowed directories;
- recoverable deletion;
- action confirmation;
- tainted external content;
- prompt-injection isolation;
- secrets outside Git;
- network isolation;
- rollback и audit.

## 16. Companion и Game Companion

### 16.1 AIRI

`moeru-ai/airi` сохраняется как `LOCKED_PLANNED` companion/presentation layer.

Допустимые направления интеграции:

- companion UI;
- Live2D/VRM;
- realtime voice;
- unspeech;
- game integrations;
- memory hooks;
- desktop overlay.

AIRI не заменяет AEGIS Core и интегрируется через API, adapter, plugin или отдельный frontend/runtime.

### 16.2 Game Companion

Разрешённые функции:

- понимание HUD и экрана;
- голосовые реакции;
- советы;
- session memory;
- overlay;
- безопасные официальные integrations.

Запрещается использовать AEGIS для читов, обхода anti-cheat или запрещённой автоматизации онлайн-игр.

## 17. Office и File Co-worker

Reading и parsing делегируются Docling, MarkItDown и OCR Runtime. Создание и изменение документов остаётся за provider-neutral Artifact Runtime AEGIS.

File Runtime обязан обеспечивать:

- allowed directories;
- safe path resolution;
- recoverable deletion;
- versioning/rollback;
- file locking;
- audit;
- confirmation для destructive actions;
- защиту от инструкций, найденных внутри недоверенных документов.

Внешние document parsers не получают право самостоятельно удалять, перемещать или перезаписывать пользовательские файлы.

## 18. Gmail, Calendar и n8n

- Gmail, Google Calendar и Contacts относятся к Stage 17.
- Отправка писем и изменение календаря требуют явной политики или подтверждения.
- n8n остаётся `OPTIONAL` и не становится обязательной частью AEGIS Core.
- Для основных действий предпочтительны typed provider contracts, а n8n используется для пользовательских recurring workflows и внешней интеграции.

## 19. Decision Register

| ID | Область | Статус | Решение |
|---|---|---|---|
| D-001 | External compute | SELECTED | Использовать `IsolatedOctopi/greenboost` через service boundary. |
| D-002 | Internal resource code | KEEP/RENAME | Сохранить и обозначить как Resource Governance. |
| D-003 | CUDA tiering/cluster | DELEGATE | Не писать заново; делегировать GreenBoost. |
| D-004 | Baseline coding LLM | ACTIVE | Сохранить текущий Qwen3-Coder до benchmark. |
| D-005 | Strong coding candidate | CANDIDATE | Qwen3-Coder-30B-A3B. |
| D-006 | High-end coding | EXPERIMENTAL | Qwen3-Coder-Next. |
| D-007 | Vision 8 ГБ | LOCKED | Qwen3-VL-4B. |
| D-008 | Embeddings | ACTIVE | BGE-M3. |
| D-009 | Voice | CANDIDATE | Qwen3-ASR/TTS против faster-whisper baseline. |
| D-010 | Documents | LOCKED | Docling primary, MarkItDown fallback. |
| D-011 | UI detection | CANDIDATE | OmniParser provider. |
| D-012 | Vector DB | CANDIDATE | Qdrant после corpus benchmark. |
| D-013 | Code intelligence | LOCKED | Tree-sitter + SCIP. |
| D-014 | Browser | LOCKED | Playwright. |
| D-015 | Windows UI | LOCKED | pywinauto + native UI Automation. |
| D-016 | Observability | LOCKED | OpenTelemetry + structured logs + audit. |

## 20. Обновлённый Stage 7

```text
Stage 7 — Resource Governance and GreenBoost Integration

7.1 Resource contracts                         completed
7.2 Resource probes                            completed
7.3 Resource ledger                            completed
7.4 Resource policy engine                     completed
7.5 Admission controller                       completed
7.6 External GreenBoost audit                  current
7.7 Isolated GreenBoost installation
7.8 GB-Synapse runtime adapter
7.9 GB-Dataflux telemetry adapter
7.10 Capability discovery
7.11 Ollama ↔ GB-Synapse fallback policy
7.12 Resource Governance integration
7.13 Single-node benchmark
7.14 Dual-node benchmark
7.15 Security and rollback validation
7.16 Production acceptance
```

Нельзя удалять существующие реализации до завершения migration tests. Старые import paths при переименовании должны иметь временные compatibility aliases и documented deprecation period.

## 21. Следующий активный RFC

# RFC-055 — GreenBoost External Integration Boundary

Это должен быть следующий и единственный активный vertical. RFC не устанавливает GreenBoost автоматически и не меняет production-сервер до ручного шага владельца.

### Обязательные разделы

- цель и non-goals;
- выбранная версия/commit GreenBoost;
- лицензия и service boundary;
- deployment topology;
- backup и rollback;
- GB-Synapse API contract;
- GB-Dataflux/MCP read-only integration;
- capability discovery и health states;
- Resource Governance mapping;
- fallback rules без silent local execution;
- threat model kernel module, MCP и cluster;
- single-node и dual-node benchmark;
- automated integration tests;
- manual acceptance checklist.

### Предлагаемые CLI-команды

```text
aegis greenboost doctor
aegis greenboost capabilities
aegis greenboost status
aegis greenboost models
aegis greenboost benchmark --profile single-node
aegis greenboost benchmark --profile dual-node
aegis greenboost rollback-check
```

### Критерии завершения

- AEGIS выполняет chat request через GB-Synapse и получает streaming response;
- health/doctor показывает понятные причины отказа;
- Dataflux metrics связаны с AEGIS `job_id`/`trace_id`;
- отключение GreenBoost возвращает систему к принятому Ollama пути;
- accepted CLI/config contracts не сломаны;
- fallback не выполняется скрытно;
- владелец вручную подтверждает benchmark и rollback.

## 22. Матрица совместимости моделей

| Модель | Железо | Runtime | Статус | Примечание |
|---|---|---|---|---|
| Current Qwen3-Coder | RTX 3050 8 ГБ | Ollama/GGUF | ACTIVE | Точную модель и quant закрепить. |
| Qwen3-Coder-30B-A3B | 2×8 ГБ / 24 ГБ | GB-Synapse/GGUF | CANDIDATE | Проверить реальную скорость weight movement. |
| Qwen3-Coder-Next | GreenBoost + DDR/NVMe | GB-Synapse/vLLM/SGLang | EXPERIMENTAL | Quant обязателен; acceptance зависит от latency. |
| Qwen3.5 9B-class | 8 ГБ quant | Transformers/GGUF | CANDIDATE | Проверить tool calling и русский язык. |
| Qwen3-VL-4B | 8 ГБ | Transformers/GGUF | LOCKED | Основной UI profile. |
| Qwen3-VL-8B | 8–16 ГБ | Transformers/GGUF | CANDIDATE | Может потребовать tiering. |
| Qwen3-VL-30B-A3B/32B | 2×8/24 ГБ + tiering | GB-Synapse | EXPERIMENTAL | Только complex UI/video benchmark. |
| BGE-M3 | CPU/GPU | FlagEmbedding | ACTIVE | Уже принят. |
| Qwen3-Embedding-0.6B | CPU/малый GPU | SentenceTransformers | CANDIDATE | Сравнить индекс и latency. |
| Qwen3-ASR-0.6B | малый GPU | Transformers | CANDIDATE | Realtime target. |
| Qwen3-ASR-1.7B | 8 ГБ | Transformers | CANDIDATE | Quality target. |
| Qwen3-TTS-0.6B | 8 ГБ/shared | Qwen TTS runtime | CANDIDATE | Streaming test required. |
| Qwen3-TTS-1.7B | 8 ГБ/exclusive | Qwen TTS runtime | CANDIDATE | Quality profile. |

## 23. Риски

| ID | Риск | Уровень | Митигирование |
|---|---|---|---|
| R1 | Kernel/CUDA regression GreenBoost | Высокий | Изолированная установка, backup, pinned commit, rollback test. |
| R2 | Слишком низкая скорость tiering | Высокий | Baseline и p95 benchmark на реальных prompts. |
| R3 | Модель помещается, но latency непригодна | Высокий | Отдельный acceptance threshold по quality/latency. |
| R4 | GPL/licensing coupling | Средний | Отдельный service process; не копировать код в AEGIS. |
| R5 | MCP получает слишком широкие права | Высокий | Read-only по умолчанию, allowlist, confirmation gate. |
| R6 | Model churn | Средний | Квартальный review; production revisions pinned. |
| R7 | AMD upgrade ломает GreenBoost plan | Средний | Сохранить NVIDIA Ubuntu server как AI node. |
| R8 | Voice cloning/privacy | Средний | Только разрешённые голоса и локальные reference clips. |
| R9 | Prompt injection через документы/UI | Высокий | Taint tracking, action policy, external-content isolation. |

## 24. Upstream registry

### AI и runtime

- `github.com/ollama/ollama`
- `github.com/QwenLM/Qwen3-Coder`
- `github.com/QwenLM/Qwen3-VL`
- `github.com/FlagOpen/FlagEmbedding`
- `github.com/PaddlePaddle/PaddleOCR`
- `github.com/ComfyUI/ComfyUI`
- `github.com/SYSTRAN/faster-whisper`
- `github.com/snakers4/silero-vad`

### GreenBoost

- `gitlab.com/IsolatedOctopi/greenboost`

### Documents и UI

- `github.com/docling-project/docling`
- `github.com/microsoft/markitdown`
- `github.com/opendatalab/MinerU`
- `github.com/microsoft/OmniParser`

### Desktop, browser и code intelligence

- `github.com/microsoft/playwright-python`
- `github.com/pywinauto/pywinauto`
- `github.com/tree-sitter/tree-sitter`
- `github.com/sourcegraph/scip`

### Memory, observability и distributed runtime

- `github.com/qdrant/qdrant`
- `github.com/open-telemetry/opentelemetry-python`
- `github.com/Bogdanp/dramatiq`
- `github.com/temporalio/sdk-python`

### Companion и automation

- `github.com/moeru-ai/airi`
- `github.com/n8n-io/n8n`

## 25. Правила обновления реестра

- плановый пересмотр — раз в квартал;
- внеплановый пересмотр — новый major release, критическая CVE, смена GPU или несовместимость accepted runtime;
- новый кандидат получает статус `CANDIDATE`, но не `ACTIVE` до benchmark и owner approval;
- удаление `ACTIVE` технологии требует migration plan и rollback;
- сравнение выполняется на одинаковом наборе задач и железе;
- production-версии фиксируются по revision, digest или SHA;
- изменение Roadmap требует явного решения владельца.

> **Финальная рекомендация.** Не начинать массовую замену моделей. Сначала завершить RFC-055 и получить стабильный `GreenBoostProvider` с проверенным rollback. Затем провести единый benchmark-пакет: coding, vision, embeddings, ASR и TTS. По результатам обновить статусы без переписывания provider contracts.
