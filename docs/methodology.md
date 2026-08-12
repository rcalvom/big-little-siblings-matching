# Methodology

## Scope

The system computes a complete capacitated bipartite matching when one exists.
For ordinary assignments it first spreads across as many mentors as possible,
then maximizes the weakest pair score, then total score. Every input field, hard
rule, score component, objective, and tie rule is explicit.

The score is a transparent policy proxy for compatibility. It is not an
empirically validated prediction of mentoring success.

## Sets and fixed relationships

Let $B$ be the valid, available Bigs and $L$ the valid Littles. Big $b$
has integer capacity $c_b>0$. A private set $F\subseteq B\times L$ contains
known relationships declared in the Big form and resolved to canonical IDs
during private data preparation.

Each Little may occur in at most one relationship in $F$. A Big may occur in
several, bounded by its declared capacity. A declared relationship:

- is mandatory;
- consumes one unit of Big capacity;
- may bypass ordinary gender and Colombian-status rules;
- may not use an unavailable Big; and
- may never exceed declared capacity.

Conflicts stop the run. They are never resolved by score.

Let $f_b\in\{0,\dots,c_b\}$ be the declared load of Big $b$,
$\bar c_b=c_b-f_b$, and $L'=L\setminus L_F$ the ordinary Littles.

## Ordinary eligibility

An ordinary edge $(b,\ell)$ exists only when all hard rules pass:

1. The Big answered `yes` to `can_commit_4_6_hours`.
2. If either participant answered `yes` to `same_gender_mentorship`, their
   disclosed canonical `gender_identity` values are equal.
3. If the Big answered `no` to `accepts_non_colombian_little`, the Little must
   have `is_colombian=yes`.

Gender and Colombian status never add or subtract score. No missing value,
unknown category, or unmapped canonical text is inferred.

## Exact pair score

Every eligible pair has six components in $[0,1]$:

$$
z_{b\ell}=(P,D,U,H,C,A).
$$

The initial weights are equal, but all are explicit policy constants:

$$
q_{b\ell}=
\frac{\alpha_P P+\alpha_D D+\alpha_U U+\alpha_H H+\alpha_C C+\alpha_A A}
{\alpha_P+\alpha_D+\alpha_U+\alpha_H+\alpha_C+\alpha_A},
\qquad \alpha_i=1.
$$

The implementation uses rational arithmetic. It does not optimize rounded
floating-point scores.

### Priority alignment

Both roles assign distinct ranks 1 through 5 to the same categories. For rank
difference $d_k=r_{bk}-r_{\ell k}$, normalized Spearman similarity is:

$$
P_{b\ell}=1-\frac{\sum_{k=1}^{5}d_k^2}{40}.
$$

### Bachelor degree

Reviewed canonical labels map to an ISCED-F hierarchy. Defaults are:

$$
D_{b\ell}=\begin{cases}
1 & \text{same detailed field},\\
2/3 & \text{same narrow field},\\
1/3 & \text{same broad field},\\
0 & \text{otherwise}.
\end{cases}
$$

### Undergraduate university

Reviewed labels map to campus and university system:

$$
U_{b\ell}=\begin{cases}
1 & \text{same campus},\\
1/2 & \text{same system, different campus},\\
0 & \text{otherwise}.
\end{cases}
$$

### Home location

Reviewed labels map to city, region, and country:

$$
H_{b\ell}=\begin{cases}
1 & \text{same city},\\
2/3 & \text{same region},\\
1/3 & \text{same country},\\
0 & \text{otherwise}.
\end{cases}
$$

### Purdue college and advisor

`purdue_college` uses exact resolved-code equality after approved literal alias
resolution. `advisor` uses exact person identity after approved literal name
resolution. Different advisors never receive semantic or fuzzy similarity.

## Complete feasibility

For every ordinary edge, let $x_{b\ell}\in\{0,1\}$. A final result must satisfy:

$$
\sum_{b:(b,\ell)\in E}x_{b\ell}=1 \qquad \forall \ell\in L',
$$

$$
\sum_{\ell:(b,\ell)\in E}x_{b\ell}\leq \bar c_b
\qquad \forall b\in B.
$$

A maximum-flow computation checks these constraints before optimization. Full
coverage exists exactly when the maximum flow equals $|L'|$. If it does not,
the run produces a minimum-cut diagnostic and no `matches.csv`. The cut is a
capacitated Hall-deficiency witness.

## Lexicographic objectives

For an assigned ordinary Little, define:

$$
u_\ell=\sum_b q_{b\ell}x_{b\ell}.
$$

### Mentor coverage

The program values every volunteer receiving someone over any individual pair
being slightly better matched, so the first objective spreads assignments across
as many mentors as possible. Let $B_0$ be the Bigs holding no declared
relationship. The first objective is:

$$
K^*=\max_x\left|\left\{b\in B_0:\sum_{\ell}x_{b\ell}\geq 1\right\}\right|.
$$

The implementation routes each $b\in B_0$ to the sink through a dedicated first
slot of capacity one carrying weight $-M$, where
$M>|L'|\cdot\mathrm{lcm}$ exceeds any achievable total score. Minimum-cost flow
therefore fills distinct mentors before it spends anything on quality, which
makes the objectives lexicographic rather than a weighted compromise.

This objective can lower both score objectives, and it is meant to. A Big whose
capacity exceeds one receives a second Little only once no uncovered Big can
take that Little instead.

### Pair quality

After $K^*$ is fixed, the second objective is bottleneck quality:

$$
t^*=\max_x\min_{\ell\in L'}u_\ell.
$$

The implementation searches the finite set of distinct pair scores. For each
threshold $t$, it tests whether a complete assignment retaining coverage $K^*$
exists using only edges with $q_{b\ell}\geq t$.

After fixing $t^*$, the third objective is:

$$
Q^*=\max_x\sum_{(b,\ell)\in E}q_{b\ell}x_{b\ell}
\quad\text{subject to }q_{b\ell}\geq t^*\text{ and coverage }K^*.
$$

This is solved as integer min-cost flow after multiplying rational scores by
their least common denominator. Declared relationships are reported but are
excluded from $t^*$ and $Q^*$ because the optimizer cannot change them.

If several matchings preserve all three objectives, Littles and candidate Bigs
are ordered by canonical numeric IDs. Each assignment is fixed only when the
remaining problem can still attain both $K^*$ and $Q^*$. This yields one
input-order-independent result without hash collisions.

## Review and audit

Every completed assignment receives a review risk based on five configured
signals: low score, candidate count, regret relative to the best individual
candidate, assignment changes under weight perturbations, and declared-pair
exceptions. Sensitivity is enabled by default and runs twelve exact perturbed-
weight matchings; policy may disable it for an operational run, in which case
that signal is removed from the risk denominator. This ranking supports human
review; it does not modify the match.

Each run records hashes of the exact parsed input bytes, effective policy,
installed package code, and canonical assignment, plus software versions,
exact objective fractions, algorithm names, tie rule, counts, operator, and
feasibility status in `run_manifest.json`.
