# Outputs

This directory is empty on purpose. Runs write here on the coordinator's machine
and everything below it is ignored by Git.

A successful run produces:

| File | What it holds |
|---|---|
| `matches.csv` | The assignment, with each pair's score broken down by component |
| `review_queue.csv` | The same pairs, ranked by how much they merit a second look |
| `candidate_scores.csv` | Every eligible pair that was considered, not just the chosen ones |
| `declared_relationships.csv` | The relationships that were fixed in advance |
| `eligibility_exclusions.csv` | Pairs ruled out before scoring, and which rule ruled them out |
| `summary.json` | Counts and the two objective values |
| `effective_policy.yaml` | The policy as it was actually applied, defaults included |
| `run_manifest.json` | Input hashes, software versions, exact objectives, and the tie rule |
| `validation.json` | Whatever the validator found |

`coordinator_contacts.csv` is added only when `--include-contacts` is passed.

A run that finds no complete assignment writes `infeasibility.json` with a
minimum-cut certificate explaining which participants could not be covered, and
deliberately writes no `matches.csv`. A partial matching is not a result.
