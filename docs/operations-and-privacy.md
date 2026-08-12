# Running the matcher

## Where preparation ends

Raw form exports and the one-off scripts that convert them live outside this
repository. A preparer turns them into canonical CSV and a reviewed policy
catalog; from there the matcher validates, but never edits, what it is given.

Keeping cohort data out of Git matters more than it might seem: an ignored
directory is a convenience, not a boundary. Anything published should be built
from a clean checkout rather than from a working copy that happens to have
private files sitting in it.

## Run procedure

1. Preserve original exports in approved private storage.
2. Prepare canonical Big and Little CSV files using the data contract.
3. Resolve each declared known-Little name to an ID and create the private
   declared-relationship CSV. Stop on ambiguity. A Big that declared several Littles
   contributes one row per relationship, up to its declared capacity. When two
   Bigs declare the same Little, the coordinator decides which relationship
   stands and records the decision in the `reason` column.
4. Review the private catalog for every degree, university, location, Purdue
   college, and advisor value.
5. Run `validate`. Resolve every error; do not infer missing values.
6. Run `match` into a private output path that does not already exist. A lock,
   staging directory, and final rename publish the report set transactionally.
7. If exit code is `3`, inspect `infeasibility.json`, add capacity or make an
   explicit policy correction, then rerun the complete process.
8. Review `review_queue.csv`, eligibility exclusions, objectives, and the run
   manifest before releasing assignments.

No automation may exceed capacity, use an unavailable Big, silently relax an
ordinary rule, or publish a partial matching as final.

An interrupted process can leave a hidden lock or staging directory. Do not
delete it blindly: an authorized operator first verifies that no run is active,
reviews whether the staging data requires incident handling, and then removes
the stale artifact before retrying.

## What the tool does with sensitive fields

Names and emails stay in the canonical CSV because coordinators asked for a
single operational file rather than two. Tests enforce that editing them cannot
change a score or an assignment, and contact details are only written to the
reports when explicitly requested.

Gender identity and Colombian status are used only for explicit hard rules.
They never contribute soft-score points. Home location contributes only through
the published city-region-country policy; it is not treated as nationality.

CSV outputs are written atomically with private file permissions. Cells that
could be interpreted as spreadsheet formulas are escaped.

## Reproducibility

`run_manifest.json` records:

- timestamp and operator;
- schema and policy versions;
- SHA-256 hashes of protected inputs and effective policy;
- package version, package-code hash, Python, NetworkX, and PyYAML versions;
- exact bottleneck and total-score fractions;
- max-flow, min-cost-flow, and ID tie rules; and
- assignment digest, declared-relationship evidence, output options, exclusion
  counts, and infeasibility evidence including residual capacities.

The effective policy used by the run is written beside the manifest. These
records allow an authorized reviewer with the same private inputs to reproduce
the result without exposing raw data in public logs.

## CLI

```bash
csap-siblings-match validate \
  --big inputs/canonical/fall_2026/bigs.csv \
  --little inputs/canonical/fall_2026/littles.csv \
  --declared inputs/overrides/fall_2026/declared_relationships.csv \
  --config config/fall_2026.private.yaml \
  --report outputs/fall_2026-validation.json

csap-siblings-match match \
  --big inputs/canonical/fall_2026/bigs.csv \
  --little inputs/canonical/fall_2026/littles.csv \
  --declared inputs/overrides/fall_2026/declared_relationships.csv \
  --config config/fall_2026.private.yaml \
  --operator coordinator-id \
  --output-dir outputs/fall_2026
```

Exit codes are `0` for success, `2` for invalid input/configuration, and `3`
for a valid but infeasible hard-policy graph.
