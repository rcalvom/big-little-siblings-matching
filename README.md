# CSAP Big-Little Siblings Matching

A capacity-aware bipartite matching tool for the Big-Little Siblings Program of
the Colombian Student Association at Purdue (CSAP). It pairs incoming visiting
scholars with mentors under explicit, reviewable rules, and documents every
decision it makes.

The problem is modelled as a capacitated bipartite matching. Given a set of
mentors with integer capacities and a set of participants, the solver first
establishes whether a complete assignment exists. When one does, it spreads the
assignment across as many mentors as possible, then maximizes the score of the
weakest ordinary pair, then maximizes total compatibility without reducing
either, and finally resolves remaining ties by canonical identifier. The result
does not depend on the order of the input rows.

Feasibility is decided by a maximum-flow computation, the remaining objectives
by integer minimum-cost flow over scores scaled by their least common denominator,
and all arithmetic is rational. Nothing is rounded before it is optimized.

## Scope and limitations

The compatibility score is a weighted combination of six declared attributes. It
reflects what the program decided to value, not evidence about what makes
mentoring work, and it has not been validated against outcomes. What it does
offer is a record of why any given pair was chosen, which a coordinator can read
and disagree with.

Every run ranks its own assignments by how much they merit a second look, on the
assumption that some of them will.

## Method

Eligibility is decided before scoring. A pair is admissible only when three
conditions hold: the mentor has declared availability; if either participant
requested a mentor of the same gender identity, both disclosed values are equal;
and if the mentor asked to be paired with a Colombian participant, the
participant self-reported as such. Gender identity and national status act
solely as filters and never contribute to the score.

Admissible pairs are scored on six components, each normalized to `[0, 1]` and
combined under explicit policy weights: alignment of the five ranked mentoring
priorities, undergraduate field of study over an ISCED-F hierarchy,
undergraduate institution, home location, current Purdue college, and academic
advisor. Partial credit within the hierarchies is configurable.

Relationships a mentor already declared are supplied separately and treated as
mandatory. A mentor may hold several, bounded by declared capacity; each
participant holds at most one. They consume capacity and remain outside the
score objectives, since the solver cannot alter them.

A volunteer who offered to mentor and received nobody is treated as a worse
outcome than a pair being slightly less well matched, which is why coverage
outranks both score objectives. A mentor who offered more than one slot fills
the second only once no other mentor can take that Little instead.

When no complete assignment exists, the run stops with exit code `3` and emits a
minimum-cut certificate identifying the capacitated Hall deficiency, rather than
publishing a partial matching.

See `docs/methodology.md` for the formal model.

## Where the data lives

Participant records, cohort policy catalogs, and generated reports stay on the
coordinator's machine, not here. `inputs/`, `outputs/`, and `config/` ship as
empty directories with a README explaining what belongs in each one locally, and
the rest is handled by `.gitignore`. The fixtures used by the tests and by the
example below are synthetic.

## Input boundary

The command-line interface accepts canonical CSV conforming exactly to
`docs/data-contract.md`, and validates without repairing. It deliberately
provides no spreadsheet importer, forms adapter, fuzzy matcher, or semantic
model. Every value a score catalog consumes must appear literally in the
effective policy; case, punctuation, and diacritic variants are explicit
aliases, and an unmapped value stops the run rather than being inferred.

Converting a cohort's raw responses into canonical CSV is therefore a separate,
private preparation step, performed and reviewed by an authorized operator.
Keeping it outside this boundary is what allows the matcher's behaviour to be
audited.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Python 3.11 or newer is required.

## Reproducible example

The paths below refer to a repository checkout; the fixtures are not embedded in
the installed distribution.

```bash
RUN_DIR="$(mktemp -d)"

csap-siblings-match validate \
  --big examples/bigs.csv \
  --little examples/littles.csv \
  --declared examples/declared_relationships.csv \
  --config examples/policy.yaml \
  --report "$RUN_DIR/validation.json"

csap-siblings-match match \
  --big examples/bigs.csv \
  --little examples/littles.csv \
  --declared examples/declared_relationships.csv \
  --config examples/policy.yaml \
  --operator synthetic-example \
  --output-dir "$RUN_DIR/output"
```

The output directory must not already exist; reports are published
transactionally through a lock, a staging directory, and a final rename.

A successful run writes the assignment, the review queue, per-pair score
evidence, the effective policy, and a manifest recording input hashes, software
versions, exact objective fractions, and the tie rule. Together these let a
reviewer holding the same private inputs reproduce the result without exposing
raw data.

Exit codes are `0` for success, `2` for invalid input or configuration, and `3`
for a valid but infeasible instance.

## Documentation

- `docs/methodology.md` — model, score, objectives, and proof strategy.
- `docs/data-contract.md` — canonical CSV schemas and the policy contract.
- `docs/operations-and-privacy.md` — controlled run procedure and audit record.
- `docs/synthetic-example.md` — a worked example of the bottleneck objective.
- `config/cohort.example.yaml` — an annotated policy override to copy from.
- `examples/` — the executable fixtures used above.

## Development

```bash
python -m pip install -e ".[test]"
pytest
```

The suite checks the optimizer against an independent brute-force oracle on
small graphs, enumerates all 120 permutations of the five priority ranks,
asserts invariance to input order, exercises the hard eligibility rules and the
capacity bounds on declared relationships, and runs the command-line interface
end to end.
