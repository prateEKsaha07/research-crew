from graph.state import ResearchState


def researcher(state: ResearchState) -> dict:
    """TODO(phase-3): migrate to list[dict] with {text, url}."""
    findings = [
        "Quantum computing threatens RSA-2048 encryption within a decade | https://example.com/quantum-rsa",
        "NIST standardized post-quantum cryptographic algorithms in 2024 | https://example.com/nist-pqc",
        "Shor's algorithm breaks public-key cryptography by factoring large integers | https://example.com/shor",
    ]
    return {"research_findings": findings}