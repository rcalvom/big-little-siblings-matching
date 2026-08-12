# Canonical data contract

This document defines the CSV files the matcher reads. It is the boundary
between private cohort preparation and the tool itself: preparation turns raw
form exports into these files, and the matcher validates them without repairing
anything.

The matcher does not read spreadsheets, normalize Microsoft Forms exports, infer
categories, or fuzzy-match text. If a value does not conform, the run stops and
says so.

## Rules that apply to every file

- UTF-8 CSV, with the exact column order given below and no extra columns.
- Every field is required; there are no optional columns.
- Text is trimmed, NFC-normalized, and free of control characters.
- Boolean fields hold the literal lowercase strings `yes` or `no`.
- Identifiers are `B-<source number>` for Bigs and `L-<source number>` for
  Littles, where the source number is the response number in the original form.
- Names and emails are contact data only. They never affect eligibility, score,
  optimization, or tie-breaking, and a test enforces this.
- Any value a score catalog consumes must appear literally in the effective
  policy. Case, punctuation, and accent variants are written out as explicit
  aliases; nothing is matched implicitly, and an unmapped value stops the run.

## Big CSV

| # | Column | Meaning |
|---|---|---|
| 1 | `big_id` | `B-<source number>`, unique |
| 2 | `first_name` | Contact data |
| 3 | `last_name` | Contact data |
| 4 | `email` | Contact data |
| 5 | `gender_identity` | Must be a value in the policy's gender domain |
| 6 | `same_gender_mentorship` | `yes` or `no` |
| 7 | `bachelor_degree` | Scored against the ISCED-F catalog |
| 8 | `undergrad_university` | Scored against the university catalog |
| 9 | `home_location` | Scored against the location catalog |
| 10 | `purdue_college` | Scored by exact code equality |
| 11 | `advisor` | Scored by exact person identity |
| 12 | `priority_academic_mentoring_rank` | 1–5, see below |
| 13 | `priority_emotional_support_rank` | 1–5 |
| 14 | `priority_local_integration_rank` | 1–5 |
| 15 | `priority_graduate_research_rank` | 1–5 |
| 16 | `priority_social_activities_rank` | 1–5 |
| 17 | `accepts_non_colombian_little` | `no` restricts this Big to Colombian Littles |
| 18 | `can_commit_4_6_hours` | `no` removes the Big from the run entirely |
| 19 | `capacity` | Positive integer; the most Littles this Big will take |

A Big who answers `no` to `can_commit_4_6_hours` is excluded from ordinary and
declared assignments alike. A Big who requests same-gender mentorship must
declare a disclosed gender value: a non-disclosed value cannot satisfy the rule,
since the rule compares two declared values.

## Little CSV

| # | Column | Meaning |
|---|---|---|
| 1 | `little_id` | `L-<source number>`, unique |
| 2 | `first_name` | Contact data |
| 3 | `last_name` | Contact data |
| 4 | `email` | Contact data |
| 5 | `gender_identity` | Must be a value in the policy's gender domain |
| 6 | `same_gender_mentorship` | `yes` or `no` |
| 7 | `is_colombian` | `yes` or `no`; see the note below |
| 8 | `bachelor_degree` | Scored against the ISCED-F catalog |
| 9 | `undergrad_university` | Scored against the university catalog |
| 10 | `home_location` | Scored against the location catalog |
| 11 | `purdue_college` | Scored by exact code equality |
| 12 | `advisor` | Scored by exact person identity |
| 13 | `priority_academic_mentoring_rank` | 1–5, see below |
| 14 | `priority_emotional_support_rank` | 1–5 |
| 15 | `priority_local_integration_rank` | 1–5 |
| 16 | `priority_graduate_research_rank` | 1–5 |
| 17 | `priority_social_activities_rank` | 1–5 |

The matcher never derives `is_colombian`. When a cohort's form does not ask the
question, an authorized preparer may fill it using one documented rule, recorded
in the preparation audit and reviewed before the run. For Fall 2026 the rule was
the declared country of the undergraduate institution. Names, birthplace, and
home location are not used for this.

## Priority ranks

Both roles rank the same five aspects of the relationship, where `1` is most
important:

1. Academic guidance and mentorship.
2. Emotional support and approachability.
3. Integration into Purdue and the Lafayette community.
4. Graduate school or research-career information.
5. Social or leisure activities.

The five values must form a permutation of 1 through 5. Ties and gaps are
rejected, because the score compares rank orders.

## Declared relationships

| # | Column | Meaning |
|---|---|---|
| 1 | `little_id` | The Little in the relationship |
| 2 | `big_id` | The Big in the relationship |
| 3 | `reason` | Why it stands, in the coordinator's words |

Bigs may name a Little they already know. Preparation resolves each name to an
unambiguous ID before this file exists; a name that is missing, ambiguous, or
not found is settled by hand rather than guessed.

Each Little appears at most once. A Big may appear several times, up to its
declared capacity. These relationships consume capacity and may bypass the
ordinary gender and Colombian-status rules, but never availability or capacity,
and the optimizer treats them as fixed.

## Policy catalogs

The cohort's private YAML resolves the free text above into codes the matcher
can compare:

| Catalog | Resolves to |
|---|---|
| `bachelor_degree` | ISCED-F broad, narrow, and detailed field |
| `undergrad_university` | University system and campus |
| `home_location` | Country, region, and city |
| `purdue_college` | One canonical college code |
| `advisor` | One canonical person code |

Hierarchies are checked for consistency: a detailed field cannot sit under two
different narrow fields, and a city cannot belong to two different regions.
