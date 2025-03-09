# game_manager.py

from .deck import create_combined_deck, shuffle_deck, draw_card
from .player import Player
from .dealer import Dealer

# DEBUG: This prints as soon as game_manager.py is loaded
print("DEBUG: game_manager.py is loaded.")

def simulate_round():
    # DEBUG: This prints as soon as simulate_round() is called
    print("DEBUG: simulate_round() called.")

    """
    Simulates a single round of Holobac:
    - Creates and shuffles a combined deck (3 decks)
    - Deals two cards each to the player and the dealer
    - Simulates the dealer's turn (drawing until reaching at least 24)
    - Displays the player's hand and score
    - Displays the dealer's hand (with the first card hidden initially)
      and then reveals the final hand after playing
    """
    deck = create_combined_deck(num_decks=3)
    shuffle_deck(deck)

    # Create player and dealer objects
    player = Player("Player")
    dealer = Dealer()

    # --- Initial Dealing: Two Cards Each ---
    for _ in range(2):
        card = draw_card(deck)
        if card is None:
            break
        # For simulation, if the card is a Joker, assign a default value (e.g., 10)
        if card.is_joker:
            player.add_card(card, card_value=10)
        else:
            player.add_card(card)

    for _ in range(2):
        card = draw_card(deck)
        if card is None:
            break
        if card.is_joker:
            dealer.add_card(card, card_value=10)
        else:
            dealer.add_card(card)

    print("DEBUG: Finished dealing initial hands.")

    # --- Display Initial Hands ---
    print("Player's hand:", player.hand)
    print("Player's round score:", player.round_score)

    # For dealer, we show the first card as hidden
    print("Dealer's hand (initially):", dealer.reveal_hand())
    print("Dealer's round score is hidden for suspense.")

    # --- Dealer's Turn ---
    dealer.play(deck)

    # --- Reveal Dealer's Final Hand ---
    print("\nDealer's final hand:", dealer.hand)
    print("Dealer's final round score:", dealer.round_score)

    print("DEBUG: End of simulate_round().")

def run_multiple_simulations(num_simulations=100):
    """
    Runs multiple simulations to compare player and dealer wins.
    This is a very basic simulation where the player never draws additional cards.
    """
    dealer_wins = 0
    player_wins = 0

    for _ in range(num_simulations):
        deck = create_combined_deck(num_decks=3)
        shuffle_deck(deck)
        player = Player("Player")
        dealer = Dealer()

        # Deal 2 cards each for the simulation
        for _ in range(2):
            card = draw_card(deck)
            if card:
                if card.is_joker:
                    player.add_card(card, card_value=10)
                else:
                    player.add_card(card)

        for _ in range(2):
            card = draw_card(deck)
            if card:
                if card.is_joker:
                    dealer.add_card(card, card_value=10)
                else:
                    dealer.add_card(card)

        # Dealer plays out its turn
        dealer.play(deck)

        # Compare scores
        if not player.is_busted and not dealer.is_busted:
            if player.round_score > dealer.round_score:
                player_wins += 1
            elif dealer.round_score > player.round_score:
                dealer_wins += 1
        elif player.is_busted and not dealer.is_busted:
            dealer_wins += 1
        elif dealer.is_busted and not player.is_busted:
            player_wins += 1

    print(f"\nOut of {num_simulations} simulations:")
    print(f"Player wins: {player_wins}")
    print(f"Dealer wins: {dealer_wins}")
    print(f"Ties/others: {num_simulations - (player_wins + dealer_wins)}")

if __name__ == "__main__":
    # To run a single round simulation, leave this as is:
    simulate_round()
    
    # To run multiple simulations, uncomment the next line and comment out simulate_round() above:
    # run_multiple_simulations(100)

if __name__ == "__main__":
    # simulate_round()
    run_multiple_simulations(100)


