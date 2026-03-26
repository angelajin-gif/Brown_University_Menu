from __future__ import annotations

from enum import Enum


class MealSlot(str, Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"


class HallId(str, Enum):
    hall1 = "hall1"
    hall2 = "hall2"


class DietaryTag(str, Enum):
    vegan = "vegan"
    vegetarian = "vegetarian"
    spicy = "spicy"
    high_protein = "high-protein"
    low_calorie = "low-calorie"
    kosher = "kosher"
    halal = "halal"
    shared_oil = "shared-oil"


class AllergenTag(str, Enum):
    gluten_free = "gluten-free"
    dairy = "dairy"
    alcohol = "alcohol"
    soy = "soy"
    egg = "egg"
    coconut = "coconut"
    tree_nuts = "tree-nuts"
    sesame = "sesame"
    fish = "fish"
    shellfish = "shellfish"


class SourceType(str, Enum):
    menu = "menu"
    nutrition = "nutrition"
