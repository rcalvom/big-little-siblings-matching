# Inputs

This directory is empty on purpose. Cohort data lives here on the coordinator's
machine and is ignored by Git:

```text
inputs/
  source/<season>/       original exports, kept exactly as downloaded
  canonical/<season>/    the Big and Little CSV the matcher reads
  overrides/<season>/    relationships a Big already declared
```

Turning the first into the second is a manual, reviewed step, and deliberately
not something this tool does. The matcher reads only the schemas in
`docs/data-contract.md` and refuses anything else rather than guessing.

Participants are identified by `B-<n>` and `L-<n>`, derived from their response
number in the original form. Names and emails travel with the records for the
coordinator's convenience but are never used to identify or match anyone.
