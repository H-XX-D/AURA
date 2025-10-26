#!/usr/bin/env python3
"""
A command-line tool to inspect and print the contents of AURA Tablet
(.auratab) and Context Capsule (.auractx) files.

This provides a human-readable view of the binary formats for debugging,
safety checks, and general curiosity.
"""

import argparse
import json
from pathlib import Path

from .context_capsule import (
    CAPSULE_MAGIC,
    ContextCapsule,
    SectionKind,
    load_capsule,
)
from .tablet import TABLET_MAGIC, Tablet, load_tablet


def print_tablet(tablet: Tablet):
    """Prints the contents of a Tablet object in a readable format."""
    print("=" * 80)
    print(f"  AURA Tablet (.auratab)")
    print("=" * 80)
    print(f"  Format Version: {tablet.version}")
    print(f"  Created At:     {tablet.created_at.isoformat()}")
    print("-" * 80)
    print("  Metadata:")
    print(json.dumps(tablet.metadata.to_dict(), indent=4))
    print("-" * 80)
    print(f"  Entries ({len(tablet.entries)}):")

    if not tablet.entries:
        print("  <No entries>")
        return

    for i, entry in enumerate(tablet.entries):
        print(f"\n  --- Entry {i + 1} ---")
        print(f"  Path: {entry.path}")
        print("  Notes:")
        # Try to pretty-print if notes are JSON, otherwise print as text
        try:
            notes_data = json.loads(entry.notes)
            print(json.dumps(notes_data, indent=4))
        except (json.JSONDecodeError, TypeError):
            print(entry.notes or "<No notes>")
        
        print("  Diff:")
        print(entry.diff or "<No diff>")


def print_capsule(capsule: ContextCapsule):
    """Prints the contents of a ContextCapsule object in a readable format."""
    print("=" * 80)
    print(f"  AURA Context Capsule (.auractx)")
    print("=" * 80)
    print(f"  Format Version: {capsule.version}")
    print(f"  Created At:     {capsule.created_at.isoformat()}")
    print("-" * 80)
    print("  Metadata:")
    print(json.dumps(capsule.metadata.to_dict(), indent=4))
    print("-" * 80)
    print(f"  Sections ({len(capsule.sections)}):")

    if not capsule.sections:
        print("  <No sections>")
        return

    for i, section in enumerate(capsule.sections):
        print(f"\n  --- Section {i + 1} ---")
        print(f"  Name: {section.name}")
        print(f"  Kind: {section.kind.name}")
        print("  Payload:")

        if section.kind == SectionKind.JSON:
            try:
                payload_data = json.loads(section.payload)
                print(json.dumps(payload_data, indent=4))
            except json.JSONDecodeError:
                print(f"<Invalid JSON: {section.payload.decode('utf-8', 'replace')}>")
        elif section.kind == SectionKind.TEXT:
            print(section.payload.decode("utf-8", "replace"))
        elif section.kind == SectionKind.BINARY:
            print(f"<Binary data, {len(section.payload)} bytes>")
            # Optionally, print a hex dump for small binary payloads
            if len(section.payload) <= 256:
                import binascii
                print(binascii.hexlify(section.payload).decode('ascii'))
        else:
            print("<Unknown kind>")


def main():
    """Main entry point for the inspector tool."""
    parser = argparse.ArgumentParser(
        description="Inspect AURA Tablet (.auratab) or Context Capsule (.auractx) files."
    )
    parser.add_argument(
        "file_path",
        type=Path,
        help="The path to the .auratab or .auractx file to inspect.",
    )
    args = parser.parse_args()

    file_path: Path = args.file_path

    if not file_path.is_file():
        print(f"Error: File not found at '{file_path}'")
        exit(1)

    try:
        with file_path.open("rb") as f:
            magic = f.read(8)

            if magic == TABLET_MAGIC:
                tablet = load_tablet(f)
                print_tablet(tablet)
            elif magic == CAPSULE_MAGIC:
                capsule = load_capsule(f)
                print_capsule(capsule)
            else:
                print(f"Error: Unrecognized file format. Magic bytes: {magic!r}")
                exit(1)

    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        exit(1)


if __name__ == "__main__":
    main()
