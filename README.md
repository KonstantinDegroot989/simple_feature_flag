# simple_feature_flag

Evaluate feature flags with percentage rollout and per-subject overrides.

```python
from simple_feature_flag import Flag, FlagSet

flags = FlagSet([
    Flag(name="new-checkout", percentage=10.0, default=False),
    Flag(name="new-checkout", percentage=10.0, default=False,
         overrides={"qa-bot": True}),
])

flags.evaluate("new-checkout", "user-42")  # True for ~10% of subjects
flags.evaluate("new-checkout", "qa-bot")   # True, override wins
```

## Why this exists

Percentage rollouts are easy to get wrong when the bucket is recomputed per
request: a subject can land on either side of the cut on consecutive calls. This
library hashes `(flag name, subject key)` once and compares the resulting bucket
to the configured percentage, so a subject's result is stable for as long as the
flag's percentage is unchanged.

The trade-off is that changing a flag's percentage reshuffles the bucket
assignment for every subject, not just the newly included ones. That is
acceptable here because flags are short-lived and a clean re-roll is easier to
reason about than a consistent-hashing scheme.

## Awkward edge

`FlagSet.evaluate` raises `EvaluationError` for an unknown flag name instead of
returning a default. A typo in a flag name is almost always a bug, and a silent
`False` would hide it until someone noticed the feature never turned on.

## API

- `Flag(name, percentage=0.0, default=False, overrides=None)`
  - `name`: non-empty string.
  - `percentage`: float in `[0, 100]`.
  - `default`: returned when the subject is not bucketed into the rollout.
  - `overrides`: mapping of subject key to forced boolean result.
  - `.bucket(subject) -> float`: stable bucket in `[0, 100)`.
  - `.evaluate(subject) -> bool`.
- `FlagSet(flags=())`
  - `.add(flag)`: add or replace by name.
  - `.get(name) -> Flag | None`.
  - `.evaluate(name, subject) -> bool`: raises `EvaluationError` if `name` is unknown.
  - `len(flagset)` and `name in flagset`.
- `EvaluationError`: raised on invalid flag configuration or unknown flag names.

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

