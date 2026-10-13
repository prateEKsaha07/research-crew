"""Throwaway smoke script for prompts/templates.py. Do not commit."""
from prompts.templates import (
    researcher_query_gen,
    researcher_summarize,
    writer_draft,
    writer_revise,
)

FINDINGS = [
    "Shor's algorithm could break RSA-2048 within a decade. | https://example.com/quantum-computing-rsa-threat",
    "Error-corrected qubits remain the main scaling bottleneck. | https://example.com/quantum-error-correction",
    "Post-quantum cryptography standards are being finalized. | https://example.com/post-quantum-standards",
]

outputs = {
    "researcher_query_gen": researcher_query_gen("quantum computing"),
    "researcher_summarize": researcher_summarize("quantum computing RSA threat"),
    "writer_draft": writer_draft("quantum computing", FINDINGS),
    "writer_revise": writer_revise(
        "## Executive Summary\n...\n## Background\n...",
        "Add more citations in Key Findings.",
    ),
}

for name, text in outputs.items():
    print("=" * 60)
    print(name)
    print("=" * 60)
    print(text)
    print()

# Placeholder check: every {name} must be filled
bad = [n for n, t in outputs.items() if "{" in t or "}" in t]
print("PLACEHOLDER CHECK:", "FAIL " + str(bad) if bad else "OK (no unfilled placeholders)")