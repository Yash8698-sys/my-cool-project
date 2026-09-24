"""
Database models and session management using SQLAlchemy and SQLite.
"""

import json
import os
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, Index
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

Base = declarative_base()

DEFAULT_CATEGORIES: Dict[str, float] = {
    "Food": 15.0,
    "Rent": 30.0,
    "Transport": 6.0,
    "Shopping": 10.0,
    "Entertainment": 4.0,
    "Utilities": 6.0,
    "Health": 4.0,
    "Miscellaneous": 5.0,
}

DEFAULT_SAVINGS_GOAL = 20.0
DEFAULT_CURRENCY = "₹"


class Settings(Base):
    """Stores user configuration including currency, savings goal, and category limits."""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    currency = Column(String(10), default=DEFAULT_CURRENCY, nullable=False)
    savings_goal_percent = Column(Float, default=DEFAULT_SAVINGS_GOAL, nullable=False)
    category_budgets_json = Column(Text, nullable=False)

    @property
    def category_budgets(self) -> Dict[str, float]:
        """Returns the dictionary of category budgets as percentages."""
        try:
            return json.loads(self.category_budgets_json)
        except Exception:
            return dict(DEFAULT_CATEGORIES)

    @category_budgets.setter
    def category_budgets(self, budgets: Dict[str, float]) -> None:
        """Stores the dictionary of category budgets as JSON."""
        self.category_budgets_json = json.dumps(budgets)


class MonthlySalary(Base):
    """Stores monthly income and salary details."""
    __tablename__ = "monthly_salaries"

    id = Column(Integer, primary_key=True)
    month = Column(String(7), unique=True, nullable=False, index=True)  # YYYY-MM
    salary = Column(Float, nullable=False)
    other_income = Column(Float, default=0.0, nullable=False)
    change_type = Column(String(20), nullable=True)  # hike, bonus, deduction, or None
    notes = Column(Text, nullable=True)


class Expense(Base):
    """Stores individual expense line items."""
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    month = Column(String(7), nullable=False, index=True)  # YYYY-MM
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    category = Column(String(50), nullable=False)
    description = Column(String(200), default="", nullable=False)
    amount = Column(Float, nullable=False)


def get_engine(db_path: Optional[str] = None):
    """Creates a SQLite engine."""
    if db_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, "expense_agent.db")
    return create_engine(f"sqlite:///{db_path}", echo=False, connect_args={"check_same_thread": False})


def get_session_factory(engine):
    """Returns a thread-safe scoped session factory."""
    return scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def init_db(engine) -> None:
    """Initializes tables and seeds default settings if not present."""
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        settings = session.query(Settings).first()
        if not settings:
            settings = Settings(
                currency=DEFAULT_CURRENCY,
                savings_goal_percent=DEFAULT_SAVINGS_GOAL,
                category_budgets_json=json.dumps(DEFAULT_CATEGORIES),
            )
            session.add(settings)
            session.commit()
    finally:
        session.close()


def get_settings(session) -> Settings:
    """Retrieves the application settings or creates default settings if missing."""
    settings = session.query(Settings).first()
    if not settings:
        settings = Settings(
            currency=DEFAULT_CURRENCY,
            savings_goal_percent=DEFAULT_SAVINGS_GOAL,
            category_budgets_json=json.dumps(DEFAULT_CATEGORIES),
        )
        session.add(settings)
        session.commit()
    return settings
