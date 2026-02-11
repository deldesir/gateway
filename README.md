# Gateway

A personal agentic backend designed to fulfill specific communication needs, featuring **B2B Multi-Tenancy** and **Dynamic Personas**.

## Features

### 🏢 B2B Multi-Tenancy
-   **Channel Routing**: Routes incoming messages (WhatsApp/SMS) to specific business personas based on the phone number.
-   **Dynamic Configuration**: Map phone numbers to Personas dynamically via chat commands.

### 🎭 Dynamic Personas & Tools
-   **Scoped Capabilities**: Personas have distinct tools (e.g., *Hardware Store* checks stock, *Clinic* books appointments).
-   **Security**: Tools are bound strictly to the active persona, preventing unauthorized access.

### 🧠 Hybrid Knowledge System
-   **Core Context**: File-based injection for critical policies (100% recall).
-   **Extended Memory**: RAG (Vector Database) for scalable knowledge retrieval.
-   **Dynamic Updates**: Add knowledge in real-time via the `#knowledge` command.

## Attribution
This project is an upcycled and evolved implementation inspired by the **[Scranton Agents](https://github.com/ayushtiwari134/scranton-agents)** architecture.
