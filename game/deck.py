# deck.py

import random

class Card:
    """
    Represents a single card in the Spanish deck.
    For standard cards, suit and rank are defined.
    For Jokers, is_joker is True and suit/rank remain None.
    """
    def __init__(self, suit=None, rank=None, is_joker=False):
        self.suit = suit
        self.rank = rank
        self.is_joker = is_joker

    def __repr__(self):
        if self.is_joker:
            return "Joker"
        return f"{self.rank} of {self.suit}"

def create_single_spanish_deck(include_jokers=True):
    """
    Generates a single Spanish deck.
    Ranks: 1, 2, 3, 4, 5, 6, 7, 10, 11, 12
    Suits: basto, copa, espada, oro
    Optionally includes 5 Jokers.
    """
    suits = ["basto", "copa", "espada", "oro"]
    ranks = [1, 2, 3, 4, 5, 6, 7, 10, 11, 12]

    deck = []
    for suit in suits:
        for rank in ranks:
            deck.append(Card(suit=suit, rank=rank))

    if include_jokers:
        # Include 5 Jokers
        for _ in range(5):
            deck.append(Card(is_joker=True))

    return deck

def create_combined_deck(num_decks=3):
    """
    Creates a combined deck from the specified number of Spanish decks.
    For Holobac, we use 3 decks (making 135 cards if each deck has 45).
    """
    combined = []
    for _ in range(num_decks):
        combined.extend(create_single_spanish_deck(include_jokers=True))
    return combined

def shuffle_deck(deck):
    """
    Shuffles the provided deck in place.
    """
    random.shuffle(deck)

def draw_card(deck):
    """
    Draws (removes and returns) the top card from the deck.
    Returns None if the deck is empty.
    """
    if len(deck) == 0:
        return None
    return deck.pop(0)

