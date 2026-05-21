import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KoapArticle(Base):
    __tablename__ = "koap_articles"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    factor_group: Mapped[str] = mapped_column(String(32), nullable=False)


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    license_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    experience_years: Mapped[int] = mapped_column(Integer, nullable=False)
    city: Mapped[str] = mapped_column(String(64), nullable=False)
    mileage_km: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    violations: Mapped[list["Violation"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["ScoreSnapshot"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )


class Violation(Base):
    __tablename__ = "violations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    driver_id: Mapped[str] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    article_code: Mapped[str] = mapped_column(
        ForeignKey("koap_articles.code"), nullable=False, index=True
    )
    occurred_at: Mapped[date] = mapped_column(Date, nullable=False)
    fine_kzt: Mapped[int | None] = mapped_column(Integer)
    at_fault: Mapped[bool | None] = mapped_column(Boolean)
    recurrence_idx: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    driver: Mapped["Driver"] = relationship(back_populates="violations")
    article: Mapped["KoapArticle"] = relationship()


class ScoreSnapshot(Base):
    __tablename__ = "score_snapshots"
    __table_args__ = ()

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    driver_id: Mapped[str] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    risk_score: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    safety_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    premium_coef: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)

    driver: Mapped["Driver"] = relationship(back_populates="snapshots")
