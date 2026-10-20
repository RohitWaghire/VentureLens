"""Shared data models for the VentureLens grilling pipeline.

Pipeline: user prompt -> dynamic grilling questions with shortlisted options ->
answers (the transcript) -> the model writes a report -> presented to the user.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class BusinessProfile(BaseModel):
    """Details stated in the opening prompt.

    Dynamic grilling further rounds out the picture; each answer is captured in
    the transcript rather than forced into a fixed set of fields.
    """

    idea: str = ""
    budget: str = ""
    region: str = ""


class GrillOption(BaseModel):
    """A suggested answer shown as a selectable chip."""

    label: str
    value: str = ""


class GrillQuestion(BaseModel):
    """One dynamically generated question with suggested answer options."""

    id: str
    text: str
    options: List[GrillOption] = Field(default_factory=list)
    free_text_hint: str = ""


class GrillTurn(BaseModel):
    """One question/answer exchange in the grilling transcript."""

    question_id: str
    question: str
    answer: str


class ReportSection(BaseModel):
    heading: str
    body: str


class Report(BaseModel):
    """The report the model writes from the collected answers."""

    title: str = ""
    summary: str = ""
    sections: List[ReportSection] = Field(default_factory=list)
    caveat: str = ""