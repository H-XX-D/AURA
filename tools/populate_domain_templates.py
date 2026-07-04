#!/usr/bin/env python3
"""
Populate domain-specific template ranges with 500 entries each
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.templates import TemplateLibrary


def populate_ai_to_ai_templates(library: TemplateLibrary, count: int = 500):
    """Populate AI-to-AI range (128-2127) with 500 templates"""
    print(f"\n{'='*80}")
    print("POPULATING AI-TO-AI TEMPLATES (128-2,127)")
    print(f"{'='*80}\n")

    templates = [
        # OpenAI GPT-4 response patterns
        '{{"id": "chatcmpl-{0}", "object": "chat.completion", "model": "gpt-4", "choices": [{{"message": {{"role": "assistant", "content": "{1}"}}, "finish_reason": "stop"}}], "usage": {{"prompt_tokens": {2}, "completion_tokens": {3}, "total_tokens": {4}}}}}',
        '{{"id": "chatcmpl-{0}", "object": "chat.completion", "model": "gpt-3.5-turbo", "choices": [{{"message": {{"role": "assistant", "content": "{1}"}}, "finish_reason": "stop"}}]}}',
        '{{"id": "chatcmpl-{0}", "created": {1}, "model": "{2}", "choices": [{{"message": {{"content": "{3}"}}}}]}}',
        # Claude API response patterns
        '{{"id": "msg-{0}", "type": "message", "role": "assistant", "content": "{1}", "model": "claude-3-opus", "stop_reason": "end_turn", "usage": {{"input_tokens": {2}, "output_tokens": {3}}}}}',
        '{{"id": "msg-{0}", "type": "message", "role": "assistant", "content": "{1}", "model": "claude-3-sonnet", "stop_reason": "{2}"}}',
        '{{"id": "msg-{0}", "content": "{1}", "model": "{2}", "usage": {{"input_tokens": {3}, "output_tokens": {4}}}}}',
        # Generic LLM patterns
        '{{"status": "{0}", "message": "{1}", "timestamp": {2}, "request_id": "req-{3}"}}',
        '{{"response": {{"text": "{0}", "model": "{1}", "tokens": {2}}}}}',
        '{{"error": {{"message": "{0}", "type": "{1}", "code": "{2}"}}, "request_id": "req-{3}"}}',
        '{{"result": "{0}", "confidence": {1}, "model": "{2}", "latency_ms": {3}}}',
        # Model metadata patterns
        '{{"model": "{0}", "version": "{1}", "parameters": {{"temperature": {2}, "max_tokens": {3}}}}}',
        '{{"request": {{"prompt": "{0}", "model": "{1}", "stream": {2}}}}}',
        '{{"completion": {{"text": "{0}", "finish_reason": "{1}", "index": {2}}}}}',
        # Batch processing patterns
        '{{"batch_id": "{0}", "status": "{1}", "completed": {2}, "total": {3}}}',
        '{{"job_id": "{0}", "type": "{1}", "progress": {2}, "eta_seconds": {3}}}',
        # Rate limiting patterns
        '{{"rate_limit": {{"limit": {0}, "remaining": {1}, "reset_at": {2}}}}}',
        '{{"quota": {{"used": {0}, "limit": {1}, "period": "{2}"}}, "user_id": "{3}"}}',
    ]

    added = 0
    for i in range(count):
        try:
            template_id = library.allocate_ai_to_ai_id()
            pattern = templates[i % len(templates)]
            library.add(template_id, pattern)
            added += 1
            if (added % 100) == 0:
                print(f"  Added {added}/{count} AI-to-AI templates...")
        except Exception as e:
            print(f"  Error adding template {i}: {e}")
            break

    print(f"\n✅ Added {added} AI-to-AI templates (IDs: 128-{127+added})")
    return added


def populate_human_to_ai_templates(library: TemplateLibrary, count: int = 500):
    """Populate Human-to-AI range (2128-4999) with 500 templates"""
    print(f"\n{'='*80}")
    print("POPULATING HUMAN-TO-AI TEMPLATES (2,128-4,999)")
    print(f"{'='*80}\n")

    # First, update the range definition
    library.HUMAN_TO_AI_RANGE = range(2128, 5000)
    library._next_human_to_ai_id = 2128

    templates = [
        # Questions and requests
        "Can you help me with {0}?",
        "I need assistance with {0}.",
        "How do I {0}?",
        "What is {0}?",
        "Please explain {0} to me.",
        "Could you tell me about {0}?",
        "I'm trying to {0} but {1}.",
        "Can you provide information on {0}?",
        # Commands
        "Create a {0} for {1}.",
        "Generate {0} based on {1}.",
        "Summarize {0}.",
        "Translate {0} to {1}.",
        "Analyze {0} and provide {1}.",
        # Feedback and clarification
        "That's not quite what I meant. I need {0}.",
        "Can you elaborate on {0}?",
        "I don't understand {0}. Can you clarify?",
        "Thanks! Can you also {0}?",
        # Context and preferences
        "I prefer {0} instead of {1}.",
        "My goal is to {0}.",
        "The context is {0}.",
        "I'm working on {0} for {1}.",
        # Conversations
        "Hello! I need help with {0}.",
        "Thanks for your help with {0}.",
        "That worked! Now can you {0}?",
        "I have a question about {0}.",
    ]

    added = 0
    for i in range(count):
        try:
            # Manual allocation for human-to-ai range
            template_id = library._next_human_to_ai_id
            library._next_human_to_ai_id += 1

            pattern = templates[i % len(templates)]
            library.add(template_id, pattern)
            added += 1
            if (added % 100) == 0:
                print(f"  Added {added}/{count} Human-to-AI templates...")
        except Exception as e:
            print(f"  Error adding template {i}: {e}")
            break

    print(f"\n✅ Added {added} Human-to-AI templates (IDs: 2128-{2127+added})")
    return added


def populate_healthcare_templates(library: TemplateLibrary, count: int = 500):
    """Populate Healthcare range (5000-6999) with 500 templates"""
    print(f"\n{'='*80}")
    print("POPULATING HEALTHCARE TEMPLATES (5,000-6,999)")
    print(f"{'='*80}\n")

    templates = [
        # Patient information
        "Patient {0} reports {1} with severity {2}/10",
        "Patient ID: {0}, Age: {1}, Gender: {2}, Chief Complaint: {3}",
        "Presenting symptoms: {0}, Duration: {1}",
        "Medical history: {0}, Allergies: {1}",
        # Prescriptions
        "Prescription: {0} {1}mg, {2} times daily for {3} days",
        "Rx: {0}, Dosage: {1}, Route: {2}, Frequency: {3}",
        "Medication: {0}, Start date: {1}, Duration: {2}",
        # Lab results
        "Lab results for {0}: {1} = {2} {3} (normal range: {4})",
        "Test: {0}, Result: {1}, Status: {2}",
        "Blood work: {0} - {1}, Date: {2}",
        # Appointments
        "Appointment scheduled for {0} on {1} at {2}",
        "Follow-up visit: {0}, Date: {1}, Provider: {2}",
        "Next appointment: {0} with Dr. {1}",
        # Vitals
        "Vitals: BP {0}/{1}, HR {2}, Temp {3}°F, O2 sat {4}%",
        "Blood pressure: {0}/{1} mmHg, Heart rate: {2} bpm",
        "Temperature: {0}°F, Respiratory rate: {1}/min",
        # Diagnoses
        "Diagnosis: {0}, ICD-10: {1}, Severity: {2}",
        "Primary diagnosis: {0}, Secondary: {1}",
        "Condition: {0}, Status: {1}, Onset: {2}",
        # Treatment plans
        "Treatment plan: {0}, Expected duration: {1}",
        "Recommended: {0}, Follow-up in {1} weeks",
        "Plan: {0}, Monitor for {1}",
        # Procedures
        "Procedure: {0}, Date: {1}, Provider: {2}, Status: {3}",
        "Surgery scheduled: {0}, Date: {1}, Pre-op: {2}",
        # Notes
        "Clinical notes: {0}, Observation: {1}",
        "Progress note: {0}, Assessment: {1}, Plan: {2}",
    ]

    added = 0
    for i in range(count):
        try:
            template_id = library.allocate_healthcare_id()
            pattern = templates[i % len(templates)]
            library.add(template_id, pattern)
            added += 1
            if (added % 100) == 0:
                print(f"  Added {added}/{count} Healthcare templates...")
        except Exception as e:
            print(f"  Error adding template {i}: {e}")
            break

    print(f"\n✅ Added {added} Healthcare templates (IDs: 5000-{4999+added})")
    return added


def populate_financial_templates(library: TemplateLibrary, count: int = 500):
    """Populate Financial range (7000-9999) with 500 templates"""
    print(f"\n{'='*80}")
    print("POPULATING FINANCIAL TEMPLATES (7,000-9,999)")
    print(f"{'='*80}\n")

    templates = [
        # Transactions
        "Transaction {0}: {1} ${2} to account {3} on {4}",
        "Transfer: ${0} from {1} to {2}, Date: {3}, Status: {4}",
        "Payment of ${0} processed, Reference: {1}",
        "Debit: ${0}, Balance: ${1}, Date: {2}",
        "Credit: ${0}, Source: {1}, Posted: {2}",
        # Account statements
        "Account {0} balance: ${1} (available: ${2})",
        "Statement for account {0}: Opening ${1}, Closing ${2}",
        "Balance inquiry: Account {0}, Available: ${1}, Pending: ${2}",
        # Payments
        "Payment of ${0} received from {1} - Invoice #{2}",
        "Bill payment: ${0} to {1}, Due: {2}, Paid: {3}",
        "Auto-payment scheduled: ${0} on {1} to {2}",
        # Trading
        "Trade executed: {0} shares of {1} at ${2}/share",
        "Order {0}: {1} {2} shares at ${3}, Status: {4}",
        "Position: {0} shares {1}, Cost basis: ${2}, Current: ${3}",
        # Investments
        "Portfolio value: ${0}, Change: {1}%, Date: {2}",
        "Investment: {0}, Amount: ${1}, Return: {2}%",
        "Dividend received: ${0} from {1} on {2}",
        # Credit/Debit cards
        "Card transaction: ${0} at {1}, Card ending {2}",
        "Card authorization: ${0}, Merchant: {1}, Status: {2}",
        "ATM withdrawal: ${0} at {1}, Fee: ${2}",
        # Loans
        "Loan {0}: Balance ${1}, Payment ${2}, Due {3}",
        "Mortgage payment: ${0}, Principal: ${1}, Interest: ${2}",
        "Auto loan: Account {0}, Monthly ${1}, Remaining {2} payments",
        # Invoices
        "Invoice #{0}: Amount ${1}, Due {2}, Status: {3}",
        "Bill: {0}, Amount: ${1}, Due date: {2}",
        # Alerts
        "Account alert: {0}, Balance: ${1}, Threshold: ${2}",
        "Low balance warning: Account {0}, Balance: ${1}",
        "Suspicious activity detected: {0}, Amount: ${1}",
        # Wire transfers
        "Wire transfer: ${0} to {1}, Reference: {2}, Status: {3}",
        "Incoming wire: ${0} from {1}, Date: {2}",
    ]

    added = 0
    for i in range(count):
        try:
            template_id = library.allocate_financial_id()
            pattern = templates[i % len(templates)]
            library.add(template_id, pattern)
            added += 1
            if (added % 100) == 0:
                print(f"  Added {added}/{count} Financial templates...")
        except Exception as e:
            print(f"  Error adding template {i}: {e}")
            break

    print(f"\n✅ Added {added} Financial templates (IDs: 7000-{6999+added})")
    return added


def populate_legal_templates(library: TemplateLibrary, count: int = 500):
    """Populate Legal range (10000-11999) with 500 templates"""
    print(f"\n{'='*80}")
    print("POPULATING LEGAL TEMPLATES (10,000-11,999)")
    print(f"{'='*80}\n")

    templates = [
        # Contracts
        "Party {0} hereby agrees to {1} under terms {2}",
        "This agreement dated {0} between {1} and {2}",
        "Contract {0}: Parties {1} and {2}, Effective {3}",
        # Legal notices
        "Notice to {0} regarding {1}, dated {2}",
        "Legal notice: {0}, Reference: {1}, Date: {2}",
        "Formal notification: {0}, Recipient: {1}",
        # Compliance
        "Pursuant to {0}, {1} shall {2} within {3} days",
        "Compliance status: {0} - Last audit: {1}",
        "Regulatory requirement: {0}, Deadline: {1}, Status: {2}",
        # Terms and conditions
        "By {0}, you agree to {1}",
        "Terms: {0}, Effective date: {1}, Version: {2}",
        "User agrees to: {0}, Subject to: {1}",
        # Privacy and data
        "Personal data: {0}, Purpose: {1}, Retention: {2}",
        "Privacy notice: We collect {0} for {1}",
        "Data processing: {0}, Legal basis: {1}, Controller: {2}",
        # Intellectual property
        "Copyright {0} by {1}. All rights reserved.",
        "Trademark: {0}, Owner: {1}, Registration: {2}",
        "Patent {0}: {1}, Filed: {2}, Status: {3}",
        # Liability
        "Limitation of liability: {0}, Maximum: ${1}",
        "{0} shall not be liable for {1}",
        "Indemnification: {0} indemnifies {1} against {2}",
        # Dispute resolution
        "Dispute regarding {0} to be resolved by {1}",
        "Arbitration: {0}, Venue: {1}, Rules: {2}",
        "Jurisdiction: {0}, Governing law: {1}",
        # Termination
        "Termination effective {0}, Reason: {1}",
        "Agreement terminated: {0}, Notice given: {1}",
        "Right to terminate: {0}, Conditions: {1}",
        # Warranties
        "Warranty: {0}, Duration: {1}, Exclusions: {2}",
        "{0} warrants that {1}",
        "No warranty for: {0}, As-is basis",
    ]

    added = 0
    for i in range(count):
        try:
            template_id = library.allocate_legal_id()
            pattern = templates[i % len(templates)]
            library.add(template_id, pattern)
            added += 1
            if (added % 100) == 0:
                print(f"  Added {added}/{count} Legal templates...")
        except Exception as e:
            print(f"  Error adding template {i}: {e}")
            break

    print(f"\n✅ Added {added} Legal templates (IDs: 10000-{9999+added})")
    return added


def populate_small_sentences_templates(library: TemplateLibrary, count: int = 500):
    """Populate Small Sentences range (12000-13999) with 500 templates"""
    print(f"\n{'='*80}")
    print("POPULATING SMALL SENTENCES TEMPLATES (12,000-13,999)")
    print(f"{'='*80}\n")

    templates = [
        # Greetings
        "Hello {0}!",
        "Hi {0}, welcome back!",
        "Good {0}, {1}!",
        "Hey {0}!",
        "Welcome, {0}!",
        # Farewells
        "Goodbye {0}!",
        "See you later, {0}!",
        "Have a great {0}!",
        "Take care, {0}!",
        # Status messages
        "Your {0} is ready",
        "{0} completed successfully",
        "{0} in progress...",
        "{0} failed: {1}",
        "Status: {0}",
        # Notifications
        "{0} sent you a message",
        "New {0} from {1}",
        "{0} mentioned you in {1}",
        "Reminder: {0}",
        "Alert: {0}",
        # Confirmations
        "Are you sure you want to {0}?",
        "Confirm {0}",
        "{0} confirmed",
        "Please verify {0}",
        # Errors
        "Error: {0}",
        "{0} not found",
        "Invalid {0}",
        "Cannot {0}: {1}",
        "Failed to {0}",
        # Success messages
        "Success! {0}",
        "{0} saved",
        "{0} updated",
        "{0} deleted",
        "Done!",
        # Questions
        "What is {0}?",
        "How to {0}?",
        "Why {0}?",
        "When {0}?",
        "Where is {0}?",
        # Commands
        "Click {0}",
        "Open {0}",
        "Close {0}",
        "Save {0}",
        "Delete {0}",
        "Edit {0}",
        # Info messages
        "Loading {0}...",
        "Processing {0}...",
        "Waiting for {0}...",
        "{0} ready",
        "{0} available",
    ]

    added = 0
    for i in range(count):
        try:
            template_id = library.allocate_small_sentences_id()
            pattern = templates[i % len(templates)]
            library.add(template_id, pattern)
            added += 1
            if (added % 100) == 0:
                print(f"  Added {added}/{count} Small Sentences templates...")
        except Exception as e:
            print(f"  Error adding template {i}: {e}")
            break

    print(f"\n✅ Added {added} Small Sentences templates (IDs: 12000-{11999+added})")
    return added


def populate_quotes_templates(library: TemplateLibrary, count: int = 1000):
    """Populate Quotes range (14000-14999) with 1000 templates"""
    print(f"\n{'='*80}")
    print("POPULATING QUOTES TEMPLATES (14,000-14,999)")
    print(f"{'='*80}\n")

    quotes = [
        "The only way to do great work is to love what you do. - {0}",
        "Life is what happens when you're busy making other plans. - {0}",
        "In the middle of difficulty lies opportunity. - {0}",
        "The future belongs to those who believe in the beauty of their dreams. - {0}",
        "It does not matter how slowly you go as long as you do not stop. - {0}",
        "Everything you've ever wanted is on the other side of fear. - {0}",
        "Success is not final, failure is not fatal: it is the courage to continue that counts. - {0}",
        "Believe you can and you're halfway there. - {0}",
        "The only impossible journey is the one you never begin. - {0}",
        "In the end, we only regret the chances we didn't take. - {0}",
        "The best time to plant a tree was 20 years ago. The second best time is now. - {0}",
        "Your time is limited, don't waste it living someone else's life. - {0}",
        "The way to get started is to quit talking and begin doing. - {0}",
        "Don't let yesterday take up too much of today. - {0}",
        "You learn more from failure than from success. Don't let it stop you. - {0}",
        "It's not whether you get knocked down, it's whether you get up. - {0}",
        "People who are crazy enough to think they can change the world, are the ones who do. - {0}",
        "Failure will never overtake me if my determination to succeed is strong enough. - {0}",
        "We may encounter many defeats but we must not be defeated. - {0}",
        "Knowing is not enough; we must apply. Wishing is not enough; we must do. - {0}",
        "{0} said: {1}",
        "Quote of the day: {0}",
        "Wisdom from {0}: {1}",
        "{0} once said: {1}",
        "Remember: {0}",
    ]

    added = 0
    for i in range(count):
        try:
            # Manual allocation for quotes range (14000-14999)
            template_id = 14000 + i
            pattern = quotes[i % len(quotes)]
            library.add(template_id, pattern)
            added += 1
            if (added % 200) == 0:
                print(f"  Added {added}/{count} Quotes templates...")
        except Exception as e:
            print(f"  Error adding template {i}: {e}")
            break

    print(f"\n✅ Added {added} Quotes templates (IDs: 14000-{13999+added})")
    return added


def save_templates_to_file(
    library: TemplateLibrary, filepath: str = ".aura_cache/domain_templates.json"
):
    """Save populated templates to a JSON file for persistence"""
    # Create .aura_cache directory if it doesn't exist
    cache_dir = Path(filepath).parent
    cache_dir.mkdir(exist_ok=True)

    # Build template data structure
    data = {
        "version": "1.0",
        "created_at": datetime.now().isoformat(),
        "total_templates": len(library.templates),
        "platform_templates": {},
        "domains": {},
    }

    # Group templates by domain
    for template_id, pattern in library.templates.items():
        domain = None
        if 128 <= template_id < 2128:
            domain = "ai_to_ai"
        elif 2128 <= template_id < 5000:
            domain = "human_to_ai"
        elif 5000 <= template_id < 7000:
            domain = "healthcare"
        elif 7000 <= template_id < 10000:
            domain = "financial"
        elif 10000 <= template_id < 12000:
            domain = "legal"
        elif 12000 <= template_id < 14000:
            domain = "small_sentences"
        elif 14000 <= template_id < 15000:
            domain = "quotes"
        else:
            domain = "default"

        if domain not in data["domains"]:
            data["domains"][domain] = {}

        data["domains"][domain][str(template_id)] = {
            "pattern": pattern,
            "template_id": template_id,
            "created_at": datetime.now().isoformat(),
        }

        # Also add to platform_templates for compatibility
        data["platform_templates"][str(template_id)] = {
            "pattern": pattern,
            "template_id": template_id,
            "domain": domain,
        }

    # Atomic write
    temp_path = Path(filepath).with_suffix(".tmp")
    with open(temp_path, "w") as f:
        json.dump(data, f, indent=2)
    temp_path.replace(filepath)

    print(f"\n✅ Templates saved to {filepath}")
    print(f"   Total: {data['total_templates']} templates")
    for domain, templates in data["domains"].items():
        print(f"   {domain}: {len(templates)} templates")


def main():
    print("=" * 80)
    print("DOMAIN TEMPLATE POPULATION SCRIPT")
    print("=" * 80)
    print("\nThis script will populate each domain with 500 templates:")
    print("  - AI-to-AI: 500 templates (128-627)")
    print("  - Human-to-AI: 500 templates (2128-2627)")
    print("  - Healthcare: 500 templates (5000-5499)")
    print("  - Financial: 500 templates (7000-7499)")
    print("  - Legal: 500 templates (10000-10499)")
    print("  - Small Sentences: 500 templates (12000-12499)")
    print("  - Quotes: 1000 templates (14000-14999)")
    print()

    # Create template library
    library = TemplateLibrary()

    # Populate each domain
    results = {}
    results["ai_to_ai"] = populate_ai_to_ai_templates(library, 500)
    results["human_to_ai"] = populate_human_to_ai_templates(library, 500)
    results["healthcare"] = populate_healthcare_templates(library, 500)
    results["financial"] = populate_financial_templates(library, 500)
    results["legal"] = populate_legal_templates(library, 500)
    results["small_sentences"] = populate_small_sentences_templates(library, 500)
    results["quotes"] = populate_quotes_templates(library, 1000)

    # Summary
    print(f"\n{'='*80}")
    print("POPULATION COMPLETE")
    print(f"{'='*80}\n")

    total = sum(results.values())
    print("Templates added by domain:")
    print(f"  AI-to-AI:         {results['ai_to_ai']:>4} templates")
    print(f"  Human-to-AI:      {results['human_to_ai']:>4} templates")
    print(f"  Healthcare:       {results['healthcare']:>4} templates")
    print(f"  Financial:        {results['financial']:>4} templates")
    print(f"  Legal:            {results['legal']:>4} templates")
    print(f"  Small Sentences:  {results['small_sentences']:>4} templates")
    print(f"  Quotes:           {results['quotes']:>4} templates")
    print(f"  {'-'*40}")
    print(f"  Total:            {total:>4} templates")

    print(f"\nTemplate library now contains {len(library.templates)} templates")
    print(f"\n✅ All domains populated successfully!")

    # Save templates to file for persistence
    save_templates_to_file(library)


if __name__ == "__main__":
    main()
