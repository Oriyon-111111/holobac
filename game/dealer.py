# dealer.py

from .player import Player
from .deck import draw_card

class Dealer(Player):
    def __init__(self):
        super().__init__("Dealer")

    def play(self, deck):
        """
        Dealer draws cards until the round score is at least 24.
        If a Joker is drawn, tries assigning the best value (closest to 30)
        without busting. If all possible values bust, assigns 1.
        """
        while self.round_score < 24 and not self.is_busted:
            card = draw_card(deck)
            if card is None:
                break  # deck is empty

            if card.is_joker:
                value = self.assign_joker_value()
                self.add_card(card, card_value=value)
            else:
                self.add_card(card)

        return self.round_score

    def assign_joker_value(self):
        """
        Determines the best Joker value (1,2,3,4,5,6,7,10,11,12)
        that won't cause the dealer to bust. If all values bust,
        returns 1 as a fallback.
        """
        possible_values = [12, 11, 10, 7, 6, 5, 4, 3, 2, 1]
        
        for val in possible_values:
            if self.round_score + val <= 30:
                return val
        return 1  # fallback if everything busts

    def reveal_hand(self):
        """Returns a list representation of the dealer's hand with the first card hidden."""
        if len(self.hand) > 1:
            return [("Hidden", "?")] + self.hand[1:]
        else:
            return self.hand


