# player.py

class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []         # list of (card, assigned_value)
        self.round_score = 0   # current round score
        self.total_score = 0   # cumulative score over multiple rounds
        self.is_busted = False
        self.bet = 0           # if currency is involved

    def reset_round(self):
        """Resets round-specific attributes."""
        self.hand = []
        self.round_score = 0
        self.is_busted = False

    def add_card(self, card, card_value=None):
        """
        Adds a card to the player's hand.
        If the card is a Joker, card_value must be provided.
        Otherwise, the card's rank is used.
        """
        if card.is_joker:
            if card_value is None:
                raise ValueError("Joker drawn but no value assigned.")
            value = card_value
        else:
            value = card.rank

        self.hand.append((card, value))
        self.round_score += value

        if self.round_score > 30:
            self.is_busted = True

        return self.round_score

    def __repr__(self):
        return f"{self.name}: Hand={self.hand}, RoundScore={self.round_score}, TotalScore={self.total_score}"

