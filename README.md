# PFAST_AI

> **Production-oriented AI Telegram Assistant built with Python.**

PFAST_AI is a modular AI-powered Telegram assistant designed with a focus on **reliability, extensibility, memory, provider abstraction, security, and production readiness**.

The project is built as more than a simple chatbot: it includes an AI processing pipeline, persistent memory, user management, usage controls, subscriptions, referrals, background tasks, logging, validation, and automated testing.

---

## ✨ Features

* 🤖 AI-powered conversational assistant
* 🧠 Short-term and long-term memory
* 🔀 Modular AI provider architecture
* 🎯 Intent detection and AI request routing
* 🧩 Context building and conversation management
* 🛡️ Rate limiting and usage control
* 👤 User management
* 💳 Plans, subscriptions, usage and payment infrastructure
* 🎁 Referral system
* ⚙️ Background task worker
* 📝 Structured logging
* 🔍 Startup / pre-flight validation
* 🧪 Automated test suite
* 🔐 Environment-based configuration
* 🗄️ Database-backed persistence
* 🧱 Modular and extensible architecture

---

## 🏗️ Architecture

PFAST_AI follows a layered architecture designed to keep Telegram-specific logic separated from the AI and business logic.

```text
Telegram Update
      │
      ▼
Message / Handler Layer
      │
      ▼
AI Engine
      │
      ├── Intent Detection
      ├── Context Builder
      ├── Memory
      ├── Provider Manager
      └── Response Processing
      │
      ▼
AI Provider
      │
      ▼
Response
      │
      ▼
Telegram
```

Supporting systems operate alongside the main pipeline:

```text
                 ┌──────────────┐
                 │   Telegram   │
                 └──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │   Handlers   │
                 └──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │   AI Engine  │
                 └──────┬───────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
      Memory         Context       Providers
          │             │             │
          └─────────────┼─────────────┘
                        │
                        ▼
                   AI Response

       ┌──────────┐  ┌──────────┐  ┌──────────┐
       │ Database │  │ Security │  │  Tasks   │
       └──────────┘  └──────────┘  └──────────┘
```

---

## 🧠 AI Pipeline

The AI layer is separated into dedicated components responsible for processing requests.

Key responsibilities include:

* Request classification
* Intent detection
* Context construction
* Conversation handling
* Memory extraction
* Provider selection
* AI generation
* Response processing
* Error and fallback handling

This separation allows individual parts of the pipeline to evolve without coupling the entire application to a single provider or implementation.

---

## 🧠 Memory System

PFAST_AI includes a persistent memory layer capable of maintaining relevant user information across conversations.

The memory architecture distinguishes between:

* Short-term conversational context
* Long-term user memory
* Memory extraction
* Memory retrieval

Memory extraction is optimized so that unnecessary extraction requests are avoided for intents where memory processing is not required.

---

## 🔀 AI Provider Architecture

AI providers are abstracted behind a provider-management layer.

This allows the application to:

* Switch between providers
* Configure models through environment variables
* Implement provider fallback strategies
* Keep provider-specific implementation isolated
* Extend the system with additional providers

The core application therefore does not need to be tightly coupled to a single AI API.

---

## 🗄️ Data Layer

The application uses a database-backed architecture for persistent application state.

The data layer covers areas including:

* Users
* Messages
* Memory
* User state
* Plans
* Plan pricing
* Usage
* Subscriptions
* Payment requests
* Referrals
* Rate limiting
* Banned users
* AI cache

The project is structured to support further database evolution and migration toward production infrastructure.

---

## 🛡️ Security & Reliability

Security and operational reliability are considered throughout the application.

Implemented mechanisms include:

* Environment-based secret management
* Rate limiting
* Usage limits
* User access control
* Banned-user handling
* Startup validation
* Structured logging
* Provider error handling
* Application lifecycle management

Sensitive credentials and configuration values should be provided through environment variables rather than committed to the repository.

---

## 💳 Plans & Subscriptions

PFAST_AI includes infrastructure for monetization and usage management.

The system contains components for:

* Subscription plans
* Plan pricing
* Usage tracking
* Payment requests
* Subscription state
* Referral rewards

Plans are centralized to provide a single source of truth for plan-related limits and configuration.

---

## 🎁 Referral System

A referral subsystem is included for user acquisition and reward management.

It provides the foundation for:

* Referral tracking
* Referral configuration
* User attribution
* Referral-based rewards

---

## ⚙️ Background Tasks

The project includes a worker component for handling background operations independently from the primary Telegram update flow.

This architecture allows long-running or scheduled operations to be separated from user-facing request processing.

---

## 📁 Project Structure

```text
My-AI-/
│
├── backend/
│
├── bots/
│   └── telegram_bot/
│       ├── admin/
│       ├── database/
│       ├── features/
│       ├── services/
│       │   └── ai/
│       ├── tests/
│       ├── main.py
│       ├── worker.py
│       ├── logger.py
│       └── requirements.txt
│
├── tests/
│
└── ...
```

The exact structure may evolve as the project continues to be developed.

---

## 🛠️ Tech Stack

### Core

* Python
* Telegram Bot API
* `python-telegram-bot`

### AI

* LLM APIs
* OpenAI-compatible APIs
* Modular provider architecture
* AI model routing

### Backend

* Python backend services
* SQLite / PostgreSQL-compatible database architecture
* Background workers

### Infrastructure

* Linux
* Nginx
* Gunicorn
* Environment-based configuration

### Testing

* pytest
* Automated unit and integration tests

### Development

* Git
* GitHub
* Python virtual environments

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Arman-Cgh/My-AI-.git
cd My-AI-
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it:

**Windows**

```powershell
venv\Scripts\activate
```

**Linux / macOS**

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r bots/telegram_bot/requirements.txt
```

### 4. Configure environment variables

Create an environment configuration based on the variables required by the project.

```env
BOT_TOKEN=your_telegram_bot_token

AI_PROVIDER=your_provider
AI_MODEL=your_model
AI_API_KEY=your_api_key

DATABASE_URL=your_database_url
```

Never commit real credentials or API keys to GitHub.

### 5. Run the application

```bash
python bots/telegram_bot/main.py
```

---

## 🧪 Testing

Run the test suite with:

```bash
pytest
```

For verbose output:

```bash
pytest -v
```

The repository contains dedicated tests for core application components and AI functionality.

---

## 📊 Production Readiness

The project is being developed with production operation in mind.

Current architecture focuses on:

* Modular services
* Provider abstraction
* Persistent state
* Error handling
* Logging
* Rate limiting
* Usage management
* Startup validation
* Automated testing
* Background processing
* Environment-based configuration

The architecture is continuously evolving toward a more scalable and maintainable deployment model.

---

## 🗺️ Roadmap

* [ ] Complete production database migration
* [ ] Expand automated test coverage
* [ ] CI/CD pipeline
* [ ] Improved monitoring and observability
* [ ] Advanced AI routing
* [ ] Expanded provider ecosystem
* [ ] Improved task scheduling
* [ ] Enhanced administration tools
* [ ] Public API layer
* [ ] Production deployment automation

---

## 👨‍💻 Author

**Younes**

Python Developer focused on **Artificial Intelligence, automation, and production-oriented software development**.

---

## 📄 License

License information will be added as the project is finalized.
