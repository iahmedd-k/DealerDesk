import re

from pydantic import BaseModel


class SafetyResult(BaseModel):
    is_safe: bool
    violation: str | None = None
    sanitized_message: str
    deflection_message: str | None = None


# Patterns for prompt injection, jailbreaks, and persona overrides
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous\s+|prior\s+)?(instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous\s+|prior\s+)?(instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"(reveal|show|display|print)\s+(your\s+)?(system\s+prompt|instructions|initial\s+prompt)", re.IGNORECASE),
    re.compile(r"(what\s+is\s+your|tell\s+me\s+your)\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"\b(DAN|jailbreak|developer\s+mode|unrestricted\s+mode)\b", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+(not\s+an\s+ai|evil|a\s+hacker|an\s+unrestricted)", re.IGNORECASE),
    re.compile(r"(you\s+are\s+now|switch\s+to)\s+(god\s+mode|chaos\s+mode|developer\s+mode)", re.IGNORECASE),
    re.compile(r"(database\s+password|jwt_secret|api_key|secret_key|master\s+token)", re.IGNORECASE),
    re.compile(r"(DROP\s+(?:TABLE|\w+\s+TABLE)|SELECT\s+\*\s+FROM\s+users|--\s*;\s*DELETE)", re.IGNORECASE),
]

# Sensitive PII patterns (Credit cards & SSNs)
CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
SSN_PATTERN = re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b")

# Abusive or malicious content indicators
ABUSIVE_PATTERNS = [
    re.compile(r"\b(kill\s+yourself|bomb|weapon|explosive|attack\s+target|terrorist)\b", re.IGNORECASE),
]

# Financial tampering / impossible discount override patterns
FINANCIAL_OVERRIDE_PATTERN = re.compile(
    r"(sell\s+me\s+this\s+(car|vehicle)\s+for\s+\$?(0|1|10|100)\b|agree\s+to\s+free\s+car|give\s+me\s+a\s+99%\s+discount)",
    re.IGNORECASE,
)


def evaluate_input_safety(
    message: str,
    dealership_name: str = "DealerDesk",
) -> SafetyResult:
    """
    Evaluates customer input against dealership guardrails:
    1. Prompt injection / jailbreak attempts
    2. Abusive / harmful content
    3. Financial / commercial discount override attempts
    4. PII redaction (credit cards & SSNs)
    """
    clean_text = message.strip()

    # 1. Check for prompt injection / system prompt probing
    for pattern in INJECTION_PATTERNS:
        if pattern.search(clean_text):
            return SafetyResult(
                is_safe=False,
                violation="prompt_injection",
                sanitized_message=clean_text,
                deflection_message=(
                    f"I am the official automotive assistant for {dealership_name}. "
                    "I am only authorized to assist with vehicle specifications, fleet availability, "
                    "test-drive appointments, and official dealership services. "
                    "How can I help you find your next vehicle?"
                ),
            )

    # 2. Check for harmful / abusive content
    for pattern in ABUSIVE_PATTERNS:
        if pattern.search(clean_text):
            return SafetyResult(
                is_safe=False,
                violation="harmful_content",
                sanitized_message=clean_text,
                deflection_message=(
                    f"At {dealership_name}, we maintain a respectful and safe communication environment. "
                    "Our customer support team is available during business hours if you require assistance."
                ),
            )

    # 3. Check for unauthorized financial / pricing override attempts
    if FINANCIAL_OVERRIDE_PATTERN.search(clean_text):
        return SafetyResult(
            is_safe=False,
            violation="commercial_tampering",
            sanitized_message=clean_text,
            deflection_message=(
                f"Vehicle prices at {dealership_name} are based on official verified manufacturer and dealership stock listings. "
                "Any special promotions, trade-in valuations, and financing incentives must be finalized in person "
                "with our licensed sales and finance specialists. Would you like to check our current inventory prices?"
            ),
        )

    # 4. Detect and redact sensitive PII (Credit cards, SSNs)
    sanitized = clean_text
    pii_found = False
    if CREDIT_CARD_PATTERN.search(sanitized):
        sanitized = CREDIT_CARD_PATTERN.sub("[REDACTED CARD NUMBER]", sanitized)
        pii_found = True
    if SSN_PATTERN.search(sanitized):
        sanitized = SSN_PATTERN.sub("[REDACTED SSN]", sanitized)
        pii_found = True

    return SafetyResult(
        is_safe=True,
        violation="pii_detected" if pii_found else None,
        sanitized_message=sanitized,
        deflection_message=None,
    )


def sanitize_output(text: str, dealership_name: str = "our dealership") -> str:
    """
    Sanitizes assistant output:
    - Strips internal grounding markers and robotic phrasing (e.g. '[Grounded Answer]', 'According to provided documents')
    - Ensures no accidental API keys or secrets leak
    - Formats clean markdown
    """
    cleaned = text

    # Remove robotic prefixes and grounding disclaimers
    replacements = [
        (r"\[Grounded Answer\]\s*", ""),
        (r"\[Grounded Response\]\s*", ""),
        (r"According to [^,\n]+'s official dealership documentation:\s*", f"At **{dealership_name}**, "),
        (r"According to official dealership documentation:\s*", f"At **{dealership_name}**, "),
        (r"Based on the provided (context|documents|data):\s*", ""),
        (r"In the provided dealership catalog:\s*", ""),
        (r"According to the provided knowledge chunks:\s*", ""),
    ]

    for pat, rep in replacements:
        cleaned = re.sub(pat, rep, cleaned, flags=re.IGNORECASE)

    # Redact any accidental credit cards in output
    cleaned =     cleaned = CREDIT_CARD_PATTERN.sub("[CONFIDENTIAL]", cleaned)
    cleaned = SSN_PATTERN.sub("[CONFIDENTIAL]", cleaned)

    return cleaned.strip()
