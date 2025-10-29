#!/usr/bin/env python3
"""
Medicine Cabinet CLI - Command-line interface for managing AI memory.

Usage:
    medicine-cabinet capsule create <project> <summary> [options]
    medicine-cabinet capsule read <file>
    medicine-cabinet capsule set-task <file> <objective>
    medicine-cabinet capsule set-files <file> <file1> [<file2> ...]
    medicine-cabinet tablet create <title> <description> [options]
    medicine-cabinet tablet read <file>
    medicine-cabinet tablet add-entry <file> <path> [options]
    medicine-cabinet inspect <file>
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List

from context_capsule import (
    ContextCapsule,
    CapsuleMetadata,
    CapsuleSection,
    load_capsule,
)
from tablet import Tablet, TabletMetadata, TabletEntry, load_tablet


def cmd_capsule_create(args):
    """Create a new context capsule."""
    metadata = CapsuleMetadata(
        project=args.project,
        summary=args.summary,
        author=args.author,
        branch=args.branch,
    )
    capsule = ContextCapsule(metadata=metadata)
    
    output_path = Path(args.output or f"{args.project.lower().replace(' ', '_')}.auractx")
    capsule.write(output_path)
    print(f"✓ Created capsule: {output_path}")


def cmd_capsule_read(args):
    """Read and display a context capsule."""
    capsule = load_capsule(args.file)
    
    print("=" * 80)
    print(f"Context Capsule: {args.file}")
    print("=" * 80)
    print(f"Project: {capsule.metadata.project}")
    print(f"Summary: {capsule.metadata.summary}")
    print(f"Author: {capsule.metadata.author or 'N/A'}")
    print(f"Created: {capsule.metadata.created_at.isoformat()}")
    print(f"Branch: {capsule.metadata.branch or 'N/A'}")
    print("-" * 80)
    
    if capsule.get_task_objective():
        print(f"\nTask Objective:\n  {capsule.get_task_objective()}")
    
    if capsule.get_relevant_files():
        print(f"\nRelevant Files:")
        for f in capsule.get_relevant_files():
            print(f"  - {f}")
    
    if capsule.get_working_plan():
        print(f"\nWorking Plan:")
        plan = capsule.get_working_plan()
        if isinstance(plan, list):
            for i, step in enumerate(plan, 1):
                print(f"  {i}. {step}")
        else:
            print(f"  {plan}")
    
    if capsule.get_error_state():
        print(f"\nLast Error:\n  {capsule.get_error_state()}")
    
    print("\n" + "=" * 80)


def cmd_capsule_set_task(args):
    """Set the task objective in a capsule."""
    capsule = load_capsule(args.file)
    capsule.set_task_objective(args.objective)
    capsule.write(args.file)
    print(f"✓ Updated task objective in {args.file}")


def cmd_capsule_set_files(args):
    """Set the relevant files in a capsule."""
    capsule = load_capsule(args.file)
    capsule.set_relevant_files(args.files)
    capsule.write(args.file)
    print(f"✓ Updated relevant files in {args.file} ({len(args.files)} files)")


def cmd_tablet_create(args):
    """Create a new tablet."""
    metadata = TabletMetadata(
        title=args.title,
        description=args.description,
        author=args.author,
        tags=args.tags or [],
    )
    tablet = Tablet(metadata=metadata, version=1)
    
    output_path = Path(args.output or f"{args.title.lower().replace(' ', '_')}.auratab")
    tablet.write(output_path)
    print(f"✓ Created tablet: {output_path}")


def cmd_tablet_read(args):
    """Read and display a tablet."""
    tablet = load_tablet(args.file)
    
    print("=" * 80)
    print(f"Tablet: {args.file}")
    print("=" * 80)
    print(f"Title: {tablet.metadata.title}")
    print(f"Description: {tablet.metadata.description}")
    print(f"Author: {tablet.metadata.author or 'N/A'}")
    print(f"Created: {tablet.created_at.isoformat()}")
    print(f"Tags: {', '.join(tablet.metadata.tags) if tablet.metadata.tags else 'None'}")
    print(f"Entries: {len(tablet.entries)}")
    print("-" * 80)
    
    for i, entry in enumerate(tablet.entries, 1):
        print(f"\n[Entry {i}]")
        print(f"  Path: {entry.path}")
        if entry.notes:
            print(f"  Notes: {entry.notes[:100]}{'...' if len(entry.notes) > 100 else ''}")
        if entry.diff:
            print(f"  Diff: {len(entry.diff)} characters")
    
    print("\n" + "=" * 80)


def cmd_tablet_add_entry(args):
    """Add an entry to an existing tablet."""
    tablet = load_tablet(args.file)
    
    diff = ""
    if args.diff_file:
        diff = Path(args.diff_file).read_text()
    elif args.diff:
        diff = args.diff
    
    entry = TabletEntry(
        path=args.path,
        diff=diff,
        notes=args.notes or "",
    )
    
    tablet.add_entry(entry)
    tablet.write(args.file)
    print(f"✓ Added entry to {args.file}: {args.path}")


def cmd_inspect(args):
    """Inspect any Medicine Cabinet file."""
    from inspector import main as inspector_main
    sys.argv = ["inspector", str(args.file)]
    inspector_main()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Medicine Cabinet - AI Agent Memory Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Capsule commands
    capsule_parser = subparsers.add_parser("capsule", help="Manage context capsules")
    capsule_subparsers = capsule_parser.add_subparsers(dest="capsule_command")
    
    # capsule create
    capsule_create = capsule_subparsers.add_parser("create", help="Create a new capsule")
    capsule_create.add_argument("project", help="Project name")
    capsule_create.add_argument("summary", help="Brief summary")
    capsule_create.add_argument("--author", help="Author name")
    capsule_create.add_argument("--branch", help="Git branch")
    capsule_create.add_argument("-o", "--output", help="Output file path")
    capsule_create.set_defaults(func=cmd_capsule_create)
    
    # capsule read
    capsule_read = capsule_subparsers.add_parser("read", help="Read a capsule")
    capsule_read.add_argument("file", help="Capsule file path")
    capsule_read.set_defaults(func=cmd_capsule_read)
    
    # capsule set-task
    capsule_task = capsule_subparsers.add_parser("set-task", help="Set task objective")
    capsule_task.add_argument("file", help="Capsule file path")
    capsule_task.add_argument("objective", help="Task objective")
    capsule_task.set_defaults(func=cmd_capsule_set_task)
    
    # capsule set-files
    capsule_files = capsule_subparsers.add_parser("set-files", help="Set relevant files")
    capsule_files.add_argument("file", help="Capsule file path")
    capsule_files.add_argument("files", nargs="+", help="File paths")
    capsule_files.set_defaults(func=cmd_capsule_set_files)
    
    # Tablet commands
    tablet_parser = subparsers.add_parser("tablet", help="Manage tablets")
    tablet_subparsers = tablet_parser.add_subparsers(dest="tablet_command")
    
    # tablet create
    tablet_create = tablet_subparsers.add_parser("create", help="Create a new tablet")
    tablet_create.add_argument("title", help="Tablet title")
    tablet_create.add_argument("description", help="Tablet description")
    tablet_create.add_argument("--author", help="Author name")
    tablet_create.add_argument("--tags", nargs="+", help="Tags")
    tablet_create.add_argument("-o", "--output", help="Output file path")
    tablet_create.set_defaults(func=cmd_tablet_create)
    
    # tablet read
    tablet_read = tablet_subparsers.add_parser("read", help="Read a tablet")
    tablet_read.add_argument("file", help="Tablet file path")
    tablet_read.set_defaults(func=cmd_tablet_read)
    
    # tablet add-entry
    tablet_entry = tablet_subparsers.add_parser("add-entry", help="Add entry to tablet")
    tablet_entry.add_argument("file", help="Tablet file path")
    tablet_entry.add_argument("path", help="File path for the entry")
    tablet_entry.add_argument("--diff", help="Diff content")
    tablet_entry.add_argument("--diff-file", help="Path to diff file")
    tablet_entry.add_argument("--notes", help="Notes (can be JSON)")
    tablet_entry.set_defaults(func=cmd_tablet_add_entry)
    
    # Inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Inspect any file")
    inspect_parser.add_argument("file", help="File to inspect")
    inspect_parser.set_defaults(func=cmd_inspect)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if hasattr(args, "func"):
        try:
            args.func(args)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if args.command == "capsule":
            capsule_parser.print_help()
        elif args.command == "tablet":
            tablet_parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
