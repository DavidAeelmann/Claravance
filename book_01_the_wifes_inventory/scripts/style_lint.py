#!/usr/bin/env python3
import re
import sys
from pathlib import Path

BANNED_PHRASES = [
    r"\btestament\b", r"\btapestry\b", r"\bmosaic\b", r"\bsymphony\b",
    r"\bcacophony\b", r"\bkaleidoscope\b", r"\bbeacon\b", r"\blabyrinth\b",
    r"\babyss\b", r"\bchasm\b", r"\bmaelstrom\b", r"\bfacade\b",
    r"\borchestration\b", r"\benigma\b", r"\bparadox\b", r"\bozone\b",
    r"\bpalpable\b", r"\bshiver down\b", r"\bchill down\b",
    r"\bice in (?:my|her|his|their) veins\b", r"\bblood ran cold\b",
    r"\bbreath hitched\b", r"\blet out a breath\b", r"\bknuckles turned white\b",
    r"\bsilence stretched\b", r"\beyes narrowed\b", r"\bthroat tightened\b",
    r"\bstomach dropped\b", r"\bwave of (?:dread|relief|panic|fear)\b",
    r"\bflicker of\b", r"\bchuckle[ds]?\b", r"\bsmirk(?:ed|s|ing)?\b",
    r"\bsteely gaze\b", r"\blittle did (?:i|she|he) know\b",
    r"\bin that moment\b", r"\bnothing would ever be the same\b",
    r"\bbefore (?:i|she|he) knew it\b", r"\ba reminder that\b",
    r"\bit wasn['’]t [^.?!]{1,40}[—;-]\s*it was\b",
    r"\bi felt (?:a |an )?(?:surge|pang|wave|sense|rush|spike) of\b",
]

DIALOGUE_ADVERB_RE = re.compile(
    r"\b(?:said|asked|replied|whispered|muttered|snapped)\s+[a-z]+ly\b",
    re.IGNORECASE,
)

MEASUREMENT_RE = re.compile(
    r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty|thirty|forty|fifty|sixty|eighty|ninety|half(?:-|\s+an?)?)\s+(?:inch(?:es)?|foot|feet|yard|yards|degrees?|pounds?|lbs?|millimeters?|centimeters?|miles?|paces?|percent)\b",
    re.IGNORECASE,
)

def split_sentences(text: str) -> list[str]:
    clean = re.sub(r"\n+", " ", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[\"“A-Z])", clean.strip())
    return [p.strip() for p in parts if p.strip()]

def lint_chapter(path: Path) -> int:
    raw = path.read_text(encoding="utf-8")
    # Strip markdown H1/H2 headers and horizontal rules for prose metrics
    prose_lines = [
        ln for ln in raw.splitlines()
        if not ln.strip().startswith("#") and ln.strip() != "---"
    ]
    prose = "\n".join(prose_lines)
    words = re.findall(r"\b[\w'’-]+\b", prose)
    word_count = len(words)

    issues = []

    if word_count < 1750 or word_count > 2500:
        issues.append(f"WORD_COUNT: {word_count} words (target 1750-2500)")

    for pat in BANNED_PHRASES:
        for m in re.finditer(pat, prose, flags=re.IGNORECASE):
            issues.append(f"BANNED_LEXICON: '{m.group(0)}' at char {m.start()}")

    for m in DIALOGUE_ADVERB_RE.finditer(prose):
        issues.append(f"DIALOGUE_ADVERB: '{m.group(0)}'")

    measurements = [m.group(0) for m in MEASUREMENT_RE.finditer(prose)]
    if len(measurements) > 4:
        issues.append(
            f"TAPE_MEASURE_OVERLOAD: {len(measurements)} physical measurements found (max 4): {measurements}"
        )

    sentences = split_sentences(prose)
    ing_openers = []
    med_streak = 0
    med_streaks_found = []

    for idx, sent in enumerate(sentences, 1):
        s_words = re.findall(r"\b[\w'’-]+\b", sent)
        wc = len(s_words)
        first_word = s_words[0].lower() if s_words else ""
        if first_word.endswith("ing") and first_word not in {"bring", "ring", "sing", "king", "thing", "spring", "string", "morning", "evening", "ceiling", "nothing", "something", "everything", "anything"}:
            ing_openers.append((idx, sent[:60]))

        if 12 <= wc <= 16:
            med_streak += 1
            if med_streak == 3:
                med_streaks_found.append((idx - 2, idx))
        else:
            med_streak = 0

    max_ing = max(1, round(word_count / 500))
    if len(ing_openers) > max_ing:
        issues.append(
            f"PARTICIPIAL_OPENERS: {len(ing_openers)} found (max {max_ing} for {word_count} words): {ing_openers[:5]}"
        )

    if med_streaks_found:
        issues.append(
            f"CADENCE_STREAK: 3+ consecutive 12-16 word sentences at indices {med_streaks_found}"
        )

    print(f"=== STYLE LINT REPORT: {path.name} ===")
    print(f"Words: {word_count} | Sentences: {len(sentences)} | -ing openers: {len(ing_openers)}/{max_ing} | Measurements: {len(measurements)}/4")
    if issues:
        print(f"STATUS: FAIL ({len(issues)} issue(s))")
        for item in issues:
            print(f"  - {item}")
        return 1
    print("STATUS: PASS (0 violations)")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: style_lint.py <chapter_file.md>")
        sys.exit(2)
    sys.exit(lint_chapter(Path(sys.argv[1])))
