# Example

A small, runnable cohort. Every person, university, and organization in these
files is invented.

The four files are a complete set of inputs in canonical form: two participant
CSV files, an empty declared-relationship file, and a policy catalog covering
exactly the values the records use.

```bash
RUN_DIR="$(mktemp -d)"
csap-siblings-match match \
  --big examples/bigs.csv \
  --little examples/littles.csv \
  --declared examples/declared_relationships.csv \
  --config examples/policy.yaml \
  --operator synthetic-example \
  --output-dir "$RUN_DIR/output"
```

It assigns `L-1` to `B-1` and `L-2` to `B-2`.

Useful things to try from here: delete a row from `policy.yaml` and watch the
run stop on an unmapped value instead of guessing; lower a `capacity` until no
complete assignment exists and read the minimum-cut certificate it writes
instead of a partial result.
