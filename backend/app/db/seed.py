"""Idempotent development seed data. Run with: python -m app.db.seed"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CampusLocation, Category
from app.db.session import SessionLocal

CATEGORIES: list[tuple[str, str]] = [
    ("Electronics", "Phones, laptops, tablets, chargers, headphones"),
    ("ID and Cards", "Student IDs, access cards, bank cards"),
    ("Keys", "Keys and key fobs"),
    ("Bags", "Backpacks, handbags, laptop sleeves"),
    ("Clothing", "Jackets, hoodies, scarves, hats"),
    ("Books and Stationery", "Textbooks, notebooks, calculators"),
    ("Bottles and Containers", "Water bottles, lunch boxes, mugs"),
    ("Accessories", "Glasses, watches, jewellery, umbrellas"),
    ("Sports Equipment", "Balls, rackets, gym gear"),
    ("Other", "Anything that does not fit another category"),
]

LOCATIONS: list[tuple[str, str]] = [
    ("Main Library", "All floors and study rooms"),
    ("Student Union", "Lounges, food court and event spaces"),
    ("Science Building", "Labs and lecture rooms"),
    ("Engineering Building", "Workshops, labs and lecture rooms"),
    ("Dining Hall", "Main campus dining hall"),
    ("Sports Centre", "Gym, courts and changing rooms"),
    ("Lecture Theatre Complex", "Large lecture theatres"),
    ("Residence Halls", "On-campus housing common areas"),
    ("Parking and Transit", "Car parks and campus bus stops"),
]


def seed(db: Session) -> tuple[int, int]:
    """Insert missing reference rows. Returns (categories_added, locations_added)."""
    existing_categories = set(db.scalars(select(Category.name)))
    existing_locations = set(db.scalars(select(CampusLocation.name)))

    new_categories = [Category(name=n, description=d) for n, d in CATEGORIES if n not in existing_categories]
    new_locations = [CampusLocation(name=n, description=d) for n, d in LOCATIONS if n not in existing_locations]
    db.add_all([*new_categories, *new_locations])
    db.commit()
    return len(new_categories), len(new_locations)


if __name__ == "__main__":
    with SessionLocal() as session:
        added_categories, added_locations = seed(session)
    print(f"Seed complete: {added_categories} categories and {added_locations} locations added.")
