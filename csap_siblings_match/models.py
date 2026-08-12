"""Explicit data objects shared by the matching pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from fractions import Fraction


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    role: str | None = None
    participant_id: str | None = None
    field: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "role": self.role,
            "participant_id": self.participant_id,
            "field": self.field,
        }


@dataclass
class ValidationResult:
    issues: list[Issue] = field(default_factory=list)

    def add(
        self,
        severity: str,
        code: str,
        message: str,
        role: str | None = None,
        participant_id: str | None = None,
        field: str | None = None,
    ) -> None:
        self.issues.append(
            Issue(severity, code, message, role, participant_id, field)
        )

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class DeclaredMatch:
    little_id: str
    big_id: str
    reason: str


@dataclass(frozen=True)
class PairScore:
    little_id: str
    big_id: str
    total: Fraction
    priority_alignment: Fraction
    bachelor_degree: Fraction
    undergrad_university: Fraction
    home_location: Fraction
    purdue_college: Fraction
    advisor: Fraction

    def components(self) -> dict[str, Fraction]:
        return {
            "priority_alignment": self.priority_alignment,
            "bachelor_degree": self.bachelor_degree,
            "undergrad_university": self.undergrad_university,
            "home_location": self.home_location,
            "purdue_college": self.purdue_college,
            "advisor": self.advisor,
        }

    def with_total(self, total: Fraction) -> PairScore:
        return replace(self, total=total)


@dataclass(frozen=True)
class AssignedMatch:
    little_id: str
    big_id: str
    assignment_type: str
    pair_score: PairScore
    note: str = ""


@dataclass(frozen=True)
class FeasibilityDiagnostic:
    required_flow: int
    maximum_flow: int
    cut_little_ids: tuple[str, ...]
    cut_big_ids: tuple[str, ...]
    residual_capacities: dict[str, int]

    @property
    def deficit(self) -> int:
        return self.required_flow - self.maximum_flow

    def as_dict(self) -> dict[str, object]:
        return {
            "required_flow": self.required_flow,
            "maximum_flow": self.maximum_flow,
            "deficit": self.deficit,
            "cut_little_ids": list(self.cut_little_ids),
            "cut_big_ids": list(self.cut_big_ids),
            "residual_capacities": dict(sorted(self.residual_capacities.items())),
        }


@dataclass(frozen=True)
class OptimizationResult:
    matches: tuple[AssignedMatch, ...]
    declared_assignments: tuple[AssignedMatch, ...]
    candidate_counts: dict[str, int]
    bottleneck_score: Fraction | None
    ordinary_total_score: Fraction
    integer_cost_denominator: int | None
    diagnostic: FeasibilityDiagnostic | None = None
    # Bigs that hold no declared relationship and received at least one ordinary
    # assignment. Maximized before either score objective.
    big_coverage: int = 0

    @property
    def is_complete(self) -> bool:
        return self.diagnostic is None


@dataclass(frozen=True)
class ReviewCase:
    little_id: str
    big_id: str
    assignment_type: str
    total_score: Fraction
    candidate_count: int
    regret: Fraction
    sensitivity: Fraction
    exception_risk: Fraction
    combined_risk: Fraction
