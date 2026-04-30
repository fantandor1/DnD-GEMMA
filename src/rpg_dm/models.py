from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .db import Base
from .utils import utcnow


class TimestampMixin:
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class Campaign(TimestampMixin, Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    setting_name: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(String(200), default="")
    system_prompt: Mapped[str] = mapped_column(Text)
    model_id: Mapped[str] = mapped_column(String(200))

    hero: Mapped["Hero"] = relationship(
        back_populates="campaign",
        uselist=False,
        cascade="all, delete-orphan",
    )
    turns: Mapped[list["Turn"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="Turn.id",
    )
    locations: Mapped[list["Location"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="Location.updated_at.desc()",
    )
    characters: Mapped[list["Character"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="Character.updated_at.desc()",
    )
    quests: Mapped[list["Quest"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="Quest.updated_at.desc()",
    )
    notes: Mapped[list["Note"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="Note.updated_at.desc()",
    )
    recap: Mapped["CampaignRecap | None"] = relationship(
        back_populates="campaign",
        uselist=False,
        cascade="all, delete-orphan",
    )
    memory_updates: Mapped[list["MemoryUpdate"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="MemoryUpdate.id.desc()",
    )


class Location(TimestampMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("campaign_id", "slug", name="uq_campaign_location_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(220), index=True)
    name: Mapped[str] = mapped_column(String(220))
    summary: Mapped[str] = mapped_column(Text, default="")
    atmosphere: Mapped[str] = mapped_column(Text, default="")
    danger_level: Mapped[str] = mapped_column(String(60), default="unknown")
    notable_features: Mapped[list[str]] = mapped_column(JSON, default=list)
    exits: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    first_seen_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)

    campaign: Mapped["Campaign"] = relationship(back_populates="locations")
    residents: Mapped[list["Character"]] = relationship(back_populates="location")


class Hero(TimestampMixin, Base):
    __tablename__ = "heroes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    current_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    archetype: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status_text: Mapped[str] = mapped_column(Text, default="")
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    inventory: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    campaign: Mapped["Campaign"] = relationship(back_populates="hero")
    current_location: Mapped[Location | None] = relationship(foreign_keys=[current_location_id])


class Character(TimestampMixin, Base):
    __tablename__ = "characters"
    __table_args__ = (UniqueConstraint("campaign_id", "slug", name="uq_campaign_character_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    slug: Mapped[str] = mapped_column(String(220), index=True)
    name: Mapped[str] = mapped_column(String(220))
    role: Mapped[str] = mapped_column(String(60), default="npc")
    summary: Mapped[str] = mapped_column(Text, default="")
    personality: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(120), default="active")
    attitude: Mapped[str] = mapped_column(String(120), default="neutral")
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    inventory: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    first_seen_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)

    campaign: Mapped["Campaign"] = relationship(back_populates="characters")
    location: Mapped[Location | None] = relationship(back_populates="residents")


class Quest(TimestampMixin, Base):
    __tablename__ = "quests"
    __table_args__ = (UniqueConstraint("campaign_id", "slug", name="uq_campaign_quest_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(220), index=True)
    title: Mapped[str] = mapped_column(String(220))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(80), default="active")
    progress_note: Mapped[str] = mapped_column(Text, default="")

    campaign: Mapped["Campaign"] = relationship(back_populates="quests")


class Turn(TimestampMixin, Base):
    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    dice_result: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    campaign: Mapped["Campaign"] = relationship(back_populates="turns")


class Note(TimestampMixin, Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[int | None] = mapped_column(ForeignKey("turns.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(220))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80), default="gm_note")
    importance: Mapped[str] = mapped_column(String(40), default="medium")
    source: Mapped[str] = mapped_column(String(40), default="model")
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)

    campaign: Mapped["Campaign"] = relationship(back_populates="notes")


class CampaignRecap(TimestampMixin, Base):
    __tablename__ = "campaign_recaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    body: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(40), default="model")

    campaign: Mapped["Campaign"] = relationship(back_populates="recap")


class MemoryUpdate(TimestampMixin, Base):
    __tablename__ = "memory_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    assistant_turn_id: Mapped[int | None] = mapped_column(ForeignKey("turns.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    raw_payload: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, default="")

    campaign: Mapped["Campaign"] = relationship(back_populates="memory_updates")
