"""Fault classification and workflow error hierarchies."""

from __future__ import annotations


class WorkflowError(Exception):
    """Base exception for workflow execution failures."""


class InfrastructureFault(WorkflowError):
    """Transient infrastructure failure (network partitions, DB disconnects, lock contention).

    Eligible for exponential backoff retries.
    """


class DeterministicSourceFault(WorkflowError):
    """Deterministic failure caused by input data (schema invalidity, corrupt payload).

    Not retryable; routes immediately to REVIEW_REQUIRED or FAILED without retry storms.
    """
