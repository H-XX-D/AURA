# Medicine Cabinet

A collection of tools for managing AI agent memory, including long-term, portable memory ("Tablets") and project-specific context ("Capsules").

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/hendrixx-cnc/medicine-cabinet.git
cd medicine_cabinet

# Install locally
pip install -e .
```

### CLI Usage

The easiest way to use Medicine Cabinet is through the command-line interface:

```bash
# Create a context capsule
medicine-cabinet capsule create "MyApp" "Adding user authentication" --author "Todd"

# Set task details
medicine-cabinet capsule set-task myapp.auractx "Implement password hashing"
medicine-cabinet capsule set-files myapp.auractx src/auth.py tests/test_auth.py

# Read a capsule
medicine-cabinet capsule read myapp.auractx

# Create a tablet
medicine-cabinet tablet create "Auth Bug Fix" "Fixed SQL injection" --tags security authentication

# Add an entry to a tablet
medicine-cabinet tablet add-entry auth_bug_fix.auratab src/auth.py --diff-file changes.diff --notes '{"summary": "Used parameterized queries"}'

# Inspect any file
medicine-cabinet inspect myapp.auractx
medicine-cabinet inspect auth_bug_fix.auratab
```

### Python API Usage

```python
from medicine_cabinet import ContextCapsule, CapsuleMetadata, Tablet, TabletMetadata, TabletEntry

# Create a Context Capsule (working memory for a project)
capsule = ContextCapsule(metadata=CapsuleMetadata(
    project="MyApp",
    summary="Adding user authentication"
))

capsule.set_task_objective("Implement password hashing")
capsule.set_relevant_files(["src/auth.py", "tests/test_auth.py"])
capsule.write("myapp.auractx")

# Create a Tablet (long-term memory)
tablet = Tablet(metadata=TabletMetadata(
    title="Auth Bug Fix",
    description="Fixed SQL injection vulnerability"
))

tablet.add_entry(TabletEntry(
    path="src/auth.py",
    diff="... your git diff ...",
    notes='{"summary": "Used parameterized queries"}'
))

tablet.write("auth_fix.auratab")
```

### Inspect Files

```bash
python -m medicine_cabinet.inspector myapp.auractx
python -m medicine_cabinet.inspector auth_fix.auratab
```

## What Is This?

This module is designed to be a self-contained package that can be easily copied into other projects.

### Related Projects

The Medicine Cabinet is a foundational component for enabling more advanced AI capabilities. It is designed to work in concert with other projects by Todd Hendricks:

*   **[Orkestra](https://github.com/hendrixx-cnc/Orkestra)**: A multi-AI task coordination platform that allows a "Conductor" to orchestrate complex, autonomous workflows across different AI models like Claude, Grok, ChatGPT, Gemini, and Copilot.
*   **[AURA](https://github.com/hendrixx-cnc/AURA)**: A hybrid AI-optimized compression library for chat and streaming applications. It uses a combination of template matching, multiple compression backends, and optional GPU acceleration to achieve high throughput and significant bandwidth savings, with a strong focus on enterprise-grade audit capabilities.
*   [***The Quantum Self***](https://github.com/hendrixx-cnc/The-Quantum-Self): A self-published book by Todd Hendricks that contains the proof-of-concept for the Orkestra system, demonstrating its ability to create a complete NodeJS and React web application from start to finish. The repository contains the manuscript and associated code.

### Future Vision: A Universal Memory Layer

The goal for the Medicine Cabinet is to become a universal, portable memory layer for AI assistants, accessible across all development tools. Future plans include:

*   **Free IDE Extensions:**
    *   **VS Code:** An extension that allows the AI assistant within VS Code to read and write Capsules and Tablets, maintaining context between sessions.
    *   **Other IDEs:** Similar extensions for JetBrains IDEs (PyCharm, WebStorm), Sublime Text, and others.
*   **Browser Extensions:**
    *   Extensions for Chrome, Safari, and Firefox that enable a browser-based AI to access project context from local Medicine Cabinet files, allowing for intelligent assistance on platforms like GitHub, Stack Overflow, and documentation sites.
*   **Native Helper Application:** A lightweight, secure background service that will act as the bridge between the browser/IDE extensions and the local file system, ensuring safe and efficient access to the memory files.

This ecosystem will allow an AI's "memory" to follow the developer wherever they work, creating a seamless and truly context-aware experience.

