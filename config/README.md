# Policy configuration

The package ships a structural policy in
`csap_siblings_match/policies/default.yaml`: the score components, the gender
domain, and the default weights. What it cannot ship is the part that changes
every semester, namely the catalogs that turn each cohort's free-text answers
into codes the matcher can compare.

That part goes in a file passed with `--config`. Start from
`cohort.example.yaml`, which documents every section, and save your version as
`<season>.private.yaml`. Files matching `*.private.yaml` are ignored by Git,
which is where real cohort catalogs belong.

An override only needs to state what it changes; everything else falls back to
the default policy.

One setting worth knowing about: by default each run computes twelve additional
matchings with slightly perturbed weights, so the review queue can flag
assignments that were close calls. On a large cohort this is the slowest part of
a run. Setting `review.sensitivity_enabled: false` turns it off, and the run
manifest records that it was off.
