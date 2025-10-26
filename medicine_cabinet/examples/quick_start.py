#!/usr/bin/env python3
"""Quick start example for Medicine Cabinet."""

from datetime import datetime, timezone
from pathlib import Path
from context_capsule import ContextCapsule, CapsuleMetadata, CapsuleSection
from tablet import Tablet, TabletMetadata, TabletEntry

# Example 1: Create a Context Capsule (project working memory)
print("Creating a Context Capsule...")
capsule_metadata = CapsuleMetadata(
    project="MyAwesomeApp",
    summary="Working on user authentication feature",
    author="Todd",
)

capsule = ContextCapsule(metadata=capsule_metadata)

# Use semantic helpers to add structured data
capsule.set_task_objective("Implement password hashing for user login")
capsule.set_relevant_files(["src/auth.py", "tests/test_auth.py"])
capsule.set_working_plan([
    "Add bcrypt dependency",
    "Create hash_password function",
    "Update login endpoint",
    "Write unit tests"
])

# Save the capsule
capsule_path = Path("my_project.auractx")
capsule.write(capsule_path)
print(f"✓ Capsule saved to {capsule_path}")

# Read it back
loaded_capsule = ContextCapsule.read(capsule_path)
print(f"✓ Task objective: {loaded_capsule.get_task_objective()}")
print(f"✓ Relevant files: {loaded_capsule.get_relevant_files()}")

print("\n" + "="*60 + "\n")

# Example 2: Create a Tablet (long-term memory)
print("Creating a Tablet...")
tablet_metadata = TabletMetadata(
    title="Authentication Bug Fix",
    description="Fixed SQL injection vulnerability in login endpoint",
    author="Todd",
    tags=["security", "authentication", "bug-fix"]
)

tablet = Tablet(metadata=tablet_metadata, version=1)

# Add an entry with structured notes
entry = TabletEntry(
    path="src/auth.py",
    diff="""--- a/src/auth.py
+++ b/src/auth.py
@@ -10,7 +10,7 @@
 def authenticate(username, password):
-    query = f"SELECT * FROM users WHERE username='{username}'"
+    query = "SELECT * FROM users WHERE username=?"
+    cursor.execute(query, (username,))
""",
    notes='{"summary": "Fixed SQL injection by using parameterized query", "problem_signature": "String concatenation in SQL query", "solution_pattern": "Use parameterized queries with ? placeholders"}'
)

tablet.add_entry(entry)

# Save the tablet
tablet_path = Path("auth_fix.auratab")
tablet.write(tablet_path)
print(f"✓ Tablet saved to {tablet_path}")

# Read it back
loaded_tablet = Tablet.read(tablet_path)
print(f"✓ Tablet title: {loaded_tablet.metadata.title}")
print(f"✓ Entries: {len(loaded_tablet.entries)}")

print("\n✓ Quick start complete! Check the generated files.")
