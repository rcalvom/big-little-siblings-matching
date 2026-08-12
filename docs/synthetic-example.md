# A worked example

This example is independently invented and contains no participant data.

Two Bigs have capacity one, and two Littles must both be assigned. Suppose the
eligible aggregate scores are:

| | `B-1` | `B-2` |
|---|---:|---:|
| `L-1` | 0.9 | 0.6 |
| `L-2` | 0.6 | 0.4 |

A maximum-total-only policy would choose `L-1` to `B-1` and `L-2` to `B-2`:

$$
\min(0.9,0.4)=0.4, \qquad 0.9+0.4=1.3.
$$

The CSAP policy protects the weakest ordinary match first. It chooses `L-1` to
`B-2` and `L-2` to `B-1`:

$$
\min(0.6,0.6)=0.6, \qquad 0.6+0.6=1.2.
$$

The lower total is intentional: the primary objective improves the weakest
pair from 0.4 to 0.6. Total score is maximized only after this bottleneck value
is fixed.

If both assignments also tied on bottleneck and total score, the canonical
Little IDs would be considered in order and each would receive the lowest Big
ID that preserves both global objectives.

The executable example in `examples/` calculates scores from all six
documented components rather than supplying this illustrative matrix directly.
