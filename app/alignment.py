"""Pure alignment-check logic — no I/O, no HTTP, fully unit-testable.

Constraints are **typed** before checking, because the two types have
opposite satisfaction semantics:

* A *prohibition* ("never contact the customer directly") is satisfied by
  **absence** — a compliant plan never mentions it. It is violated when the
  plan's text overlaps the prohibited action.
* An *obligation* ("must log every refund decision") is satisfied by
  **presence** — it is flagged when the plan never engages its subject
  matter at all.

Without this split, a compliant plan that correctly avoids a prohibited
action would be flagged as "unaddressed" — the exact false positive this
module exists to prevent.

Known limitations (documented, not hidden): checks are keyword-overlap
heuristics, not semantic comprehension. Paraphrased violations can be
missed; prohibitions phrased without a negation prefix ("keep the customer
out of the loop") are misclassified as obligations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity  # pyright: ignore[reportUnknownVariableType]

PROHIBITION_PREFIXES: tuple[str, ...] = ("never ", "do not ", "don't ", "must not ", "no ")
"""A constraint starting with one of these is treated as a prohibition."""

PROHIBITION_OVERLAP_THRESHOLD = 0.6
"""A plan overlapping a prohibition/out-of-scope phrase above this ratio is a violation."""

OBLIGATION_COVERAGE_FLOOR = 0.4
"""A plan must cover at least this fraction of an obligation's content tokens
to count as addressing it. Set above incidental-vocabulary level: a plan in
the same domain shares stray nouns with every obligation (e.g. 'refund'),
and 0.15 let one shared noun out of four tokens count as engagement."""

STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "else",
        "when",
        "at",
        "by",
        "for",
        "with",
        "about",
        "against",
        "between",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "to",
        "from",
        "up",
        "down",
        "in",
        "out",
        "on",
        "off",
        "over",
        "under",
        "again",
        "further",
        "once",
        "here",
        "there",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "can",
        "will",
        "just",
        "should",
        "now",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "doing",
        "of",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "we",
        "they",
        "them",
        "their",
        "your",
        "my",
        "our",
        "must",
        "never",
        "dont",
    }
)
"""Common words carrying no signal for overlap checks. Includes the negation
words themselves ('not', 'never', 'must', 'dont') so a prohibition's
*subject matter* — not its negation framing — is what gets matched."""


@dataclass(frozen=True)
class AlignmentResult:
    """Outcome of checking a proposed plan against a package."""

    aligned: bool
    flags: list[str]
    goal_similarity: float


def tokenize(text: str) -> set[str]:
    """Lowercase, strip punctuation, split, and drop stopwords.

    Example::

        assert tokenize("Never contact the customer!") == {"contact", "customer"}
    """
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in STOPWORDS}


def keyword_overlap_ratio(phrase: str, text: str) -> float:
    """Fraction of ``phrase``'s content tokens that appear in ``text``.

    Raises ``ValueError`` if ``phrase`` has no content tokens — a ratio
    against nothing is undefined and silently returning 0.0 would hide a
    malformed constraint.

    Example::

        ratio = keyword_overlap_ratio("log every refund decision", plan_text)
    """
    phrase_tokens = tokenize(phrase)
    if not phrase_tokens:
        msg = f"phrase {phrase!r} has no content tokens after stopword removal"
        raise ValueError(msg)
    text_tokens = tokenize(text)
    return len(phrase_tokens & text_tokens) / len(phrase_tokens)


def split_constraints(constraints: list[str]) -> tuple[list[str], list[str]]:
    """Split constraints into (prohibitions, obligations) by negation prefix.

    Example::

        prohibitions, obligations = split_constraints(
            ["never contact the customer", "must log every decision"]
        )
        assert prohibitions == ["never contact the customer"]
    """
    prohibitions: list[str] = []
    obligations: list[str] = []
    for constraint in constraints:
        stripped = constraint.strip().lower()
        if stripped.startswith(PROHIBITION_PREFIXES):
            prohibitions.append(constraint)
        else:
            obligations.append(constraint)
    return prohibitions, obligations


def find_prohibition_violations(plan_text: str, prohibitions: list[str]) -> list[str]:
    """Return prohibitions whose subject matter the plan engages (= violations).

    Empty ``prohibitions`` is a legitimate boundary case, not an error.

    Example::

        violations = find_prohibition_violations(plan, ["never contact the customer"])
    """
    return [
        phrase
        for phrase in prohibitions
        if keyword_overlap_ratio(phrase, plan_text) >= PROHIBITION_OVERLAP_THRESHOLD
    ]


def find_unmet_obligations(plan_text: str, obligations: list[str]) -> list[str]:
    """Return obligations the plan never engages at all.

    Example::

        unmet = find_unmet_obligations(plan, ["must log every refund decision"])
    """
    return [
        phrase
        for phrase in obligations
        if keyword_overlap_ratio(phrase, plan_text) < OBLIGATION_COVERAGE_FLOOR
    ]


def goal_similarity_score(plan_text: str, original_goal: str) -> float:
    """TF-IDF cosine similarity between plan and goal. Advisory only.

    Never gates the aligned verdict — lexical similarity on short free
    text is too noisy to hard-fail a legitimate plan on.

    Example::

        score = goal_similarity_score(plan, "process the refund backlog")
    """
    # sklearn ships no type information, so its return values are opaque to
    # the checker; suppressions are scoped to exactly these two calls.
    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform([original_goal, plan_text])  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    similarity = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType, reportUnknownMemberType, reportIndexIssue]
    return float(similarity)  # pyright: ignore[reportUnknownArgumentType]


def normalize_proposed_plan(proposed_plan: str | list[str]) -> str:
    """Flatten a plan (string or list of steps) into one text block.

    Raises ``ValueError`` on an empty plan — validating nothing is a
    caller error, not a legitimate green result.

    Example::

        text = normalize_proposed_plan(["fetch records", "log each decision"])
    """
    text = proposed_plan if isinstance(proposed_plan, str) else ". ".join(proposed_plan)
    if not text.strip():
        msg = "proposed_plan is empty"
        raise ValueError(msg)
    return text


def evaluate_alignment(
    original_goal: str,
    constraints: list[str],
    out_of_scope: list[str],
    plan_text: str,
) -> AlignmentResult:
    """Run all checks and combine into a single verdict.

    ``aligned`` is true iff there are no prohibition/out-of-scope violations
    and no unmet obligations. ``goal_similarity`` is reported but never
    gates the verdict.

    Example::

        result = evaluate_alignment(goal, constraints, out_of_scope, plan_text)
        assert result.aligned
    """
    prohibitions, obligations = split_constraints(constraints)

    flags: list[str] = []
    for phrase in find_prohibition_violations(plan_text, prohibitions):
        flags.append(f"prohibition violated: plan engages '{phrase}'")
    for phrase in find_prohibition_violations(plan_text, out_of_scope):
        flags.append(f"out-of-scope: plan engages '{phrase}'")
    for phrase in find_unmet_obligations(plan_text, obligations):
        flags.append(f"obligation unmet: plan never addresses '{phrase}'")

    return AlignmentResult(
        aligned=not flags,
        flags=flags,
        goal_similarity=goal_similarity_score(plan_text, original_goal),
    )
