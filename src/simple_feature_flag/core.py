"""Core evaluation logic for simple_feature_flag.

A flag is deterministic: the same (flag name, subject key) pair always yields the
same bucket, so a percentage rollout does not flap between requests. Overrides
are checked before the percentage, which is what you want when an operator needs
to force a subject on or off during an incident.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional


class EvaluationError(ValueError):
    """Raised when a flag is misconfigured or an unknown flag is evaluated."""


@dataclass(frozen=True)
class Flag:
    """A single feature flag.

    ``percentage`` is a float in [0, 100]. ``overrides`` maps a subject key to a
    forced boolean result. ``default`` is returned when the subject is not
    bucketed into the rollout.
    """

    name: str
    percentage: float = 0.0
    default: bool = False
    overrides: Dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise EvaluationError("flag name must be non-empty")
        if not (0.0 <= self.percentage <= 100.0):
            raise EvaluationError(
                f"percentage for {self.name!r} must be in [0, 100], got {self.percentage!r}"
            )
        for key, value in self.overrides.items():
            if not isinstance(key, str):
                raise EvaluationError("override keys must be strings")
            if not isinstance(value, bool):
                raise EvaluationError("override values must be booleans")

    def bucket(self, subject: str) -> float:
        """Return a stable bucket in [0, 100) for this subject.

        MD5 is used because it is fast and available in the standard library.
        This is not a security boundary; it only needs to be well distributed.
        """
        digest = hashlib.md5(f"{self.name}:{subject}".encode("utf-8")).digest()
        # Take the first 8 bytes as a big-endian integer and scale to [0, 100).
        value = int.from_bytes(digest[:8], "big")
        return (value / float(1 << 64)) * 100.0

    def evaluate(self, subject: str) -> bool:
        """Evaluate the flag for a subject.

        Overrides win. Otherwise the subject is bucketed and compared against
        ``percentage``. If not bucketed, ``default`` is returned.
        """
        if subject in self.overrides:
            return self.overrides[subject]
        if self.bucket(subject) < self.percentage:
            return True
        return self.default


class FlagSet:
    """A collection of flags that can be evaluated by name."""

    def __init__(self, flags: Iterable[Flag] = ()) -> None:
        self._flags: Dict[str, Flag] = {}
        for flag in flags:
            self.add(flag)

    def add(self, flag: Flag) -> None:
        """Add or replace a flag by name."""
        if not isinstance(flag, Flag):
            raise EvaluationError("can only add Flag instances")
        self._flags[flag.name] = flag

    def get(self, name: str) -> Optional[Flag]:
        """Return the flag with ``name``, or ``None``."""
        return self._flags.get(name)

    def evaluate(self, name: str, subject: str) -> bool:
        """Evaluate the named flag for ``subject``.

        Raises ``EvaluationError`` if the flag is unknown. Failing loudly is
        preferable to silently returning a default, because a typo in a flag
        name would otherwise be invisible.
        """
        flag = self._flags.get(name)
        if flag is None:
            raise EvaluationError(f"unknown flag: {name!r}")
        return flag.evaluate(subject)

    def __len__(self) -> int:
        return len(self._flags)

    def __contains__(self, name: object) -> bool:
        return name in self._flags
