import os
import io
import discord
import asyncio
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from PIL import Image

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

#############################
# Global Settings
#############################
CARD_WIDTH = 60
CARD_HEIGHT = 96
SCALE_FACTOR = 1.25  # 125% scale
SPACING = 10         # pixels between cards
SCALED_WIDTH = int(CARD_WIDTH * SCALE_FACTOR)
SCALED_HEIGHT = int(CARD_HEIGHT * SCALE_FACTOR)

CARD_DECK_PATH = "card_deck"  # top-level folder
THUMBNAIL_URL = "https://Oriyon-111111.github.io/holobac/Thumbnail.png"  # static external URL

#############################
# Utility: Load and Scale Card Images
#############################
def get_card_image_path(suit, rank, is_joker=False):
    """
    Returns the full path to the image file for a given suit/rank or joker.
    We force everything to lowercase to avoid case-sensitivity issues in Docker.
    """
    if is_joker:
        # If your joker images are in 'comodine' folder, e.g. 'comodines1.png'
        return os.path.join(CARD_DECK_PATH, "comodine", "comodines1.png")
    else:
        # Force suit to lowercase
        suit = suit.lower()
        # Convert rank to string
        rank_str = str(rank).lower()  # typically just str(rank) is fine
        # Example path: card_deck/copa/copa6.png
        return os.path.join(CARD_DECK_PATH, suit, f"{suit}{rank_str}.png")

def load_and_scale_card_image(card_obj):
    """
    Opens the image file for card_obj (which might be a tuple or a custom class),
    converts it to RGBA, and scales it to SCALED_WIDTH x SCALED_HEIGHT.
    """
    # We assume card_obj[0].suit or card_obj.suit is stored in .suit
    # If your structure is different, adjust accordingly
    if card_obj.is_joker:
        path = get_card_image_path("", "", is_joker=True)
    else:
        path = get_card_image_path(card_obj.suit, card_obj.rank, is_joker=False)

    img = Image.open(path).convert("RGBA")
    scaled = img.resize((SCALED_WIDTH, SCALED_HEIGHT), Image.Resampling.LANCZOS)
    return scaled

def create_player_row_image(player_cards):
    """
    Given a list of card objects (or tuples) for the player,
    returns a single PIL image with all cards laid out horizontally.
    """
    from PIL import Image

    if not player_cards:
        return Image.new("RGBA", (SCALED_WIDTH, SCALED_HEIGHT), (0,0,0,0))

    # Load each card image
    imgs = [load_and_scale_card_image(c[0]) for c in player_cards]  # or c if c is the card object
    count = len(imgs)
    total_width = (SCALED_WIDTH * count) + (count - 1) * SPACING

    row_img = Image.new("RGBA", (total_width, SCALED_HEIGHT), (0,0,0,0))
    x_offset = 0
    for im in imgs:
        row_img.paste(im, (x_offset, 0), im)
        x_offset += SCALED_WIDTH + SPACING

    return row_img

#############################
# Dealer's Hand -> Text
#############################
def dealer_hand_to_text(dealer_cards):
    """
    Convert the dealer's hand (list of (CardObject, assigned_val)) into a string.
    E.g.: "6 of copa • Joker(as 10)"
    """
    if not dealer_cards:
        return "No cards."

    parts = []
    for card_obj, assigned_val in dealer_cards:
        if card_obj.is_joker:
            parts.append(f"Joker(as {assigned_val})")
        else:
            # suit and rank are presumably stored in card_obj
            parts.append(f"{card_obj.rank} of {card_obj.suit.lower()}")
    return " • ".join(parts)

#############################
# Scoreboard
#############################
def graceful_scoreboard(player_scores, dealer_scores):
    """
    Returns two lines of text showing each round's score plus total,
    using a bracket style, e.g. "[ 6 ] [ 22 ] [ 10 ] (Total: 38)"
    """
    def safe(x): return x if x else 0
    p1, p2, p3 = map(safe, player_scores)
    d1, d2, d3 = map(safe, dealer_scores)
    p_total = p1 + p2 + p3
    d_total = d1 + d2 + d3

    dealer_line = f"[ {d1} ] [ {d2} ] [ {d3} ] (Total: {d_total})"
    player_line = f"[ {p1} ] [ {p2} ] [ {p3} ] (Total: {p_total})"
    return dealer_line, player_line

#############################
# Build Single Embed
#############################
def build_embed_with_player_image(state, final_color=None, final_title=None):
    """
    Builds a Discord Embed reflecting the current game state,
    sets a static thumbnail, and includes a row of card images for the player.
    """
    import discord
    from discord import Embed, Color, File

    player_cards = state["player"].hand  # list of (CardObject, assigned_value)
    row_img = create_player_row_image(player_cards)

    # Convert PIL image to bytes
    img_bytes = io.BytesIO()
    row_img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    player_file = File(img_bytes, filename="player_hand.png")

    embed_title = final_title if final_title else "Let's Play Holobac - Good Luck!"
    color = final_color if final_color else Color.blue()
    embed = Embed(title=embed_title, color=color)

    # Table field
    embed.add_field(name="Table", value=f"Medium (Bet: {state['bet']} Credits)", inline=False)

    # Dealer's Hand
    d_text = dealer_hand_to_text(state["dealer"].hand)
    embed.add_field(name="Dealer's Hand", value=d_text, inline=False)

    # Round Scores
    d_line, p_line = graceful_scoreboard(state["player_round_scores"], state["dealer_round_scores"])
    embed.add_field(name="Round Scores", value=f"Dealer: {d_line}\nPlayer: {p_line}", inline=False)

    # Player's row image
    embed.set_image(url="attachment://player_hand.png")

    # Round info
    round_num = min(state["round"], 3)
    round_str = f"(Round {round_num} of 3)"
    commentary = state["commentary"] if state["commentary"] else ""
    embed.add_field(name="Player's Hand", value=f"{commentary}\n{round_str}", inline=False)

    # Static thumbnail
    embed.set_thumbnail(url=THUMBNAIL_URL)

    files = [player_file]
    return embed, files

#############################
# Main Bot Logic
#############################
game_sessions = {}

def start_game(user_id, bet=0):
    """
    Creates a new game state, deals initial cards, checks two-joker rule.
    """
    from game.deck import create_combined_deck, shuffle_deck, draw_card
    from game.player import Player
    from game.dealer import Dealer

    deck = create_combined_deck(num_decks=3)
    shuffle_deck(deck)
    player = Player("Player")
    dealer = Dealer()

    # Deal two cards to player
    for _ in range(2):
        card = draw_card(deck)
        if card:
            if card.is_joker:
                player.add_card(card, card_value=10)
            else:
                player.add_card(card)

    # Deal two cards to dealer
    for _ in range(2):
        card = draw_card(deck)
        if card:
            if card.is_joker:
                dealer.add_card(card, card_value=10)
            else:
                dealer.add_card(card)

    state = {
        "deck": deck,
        "player": player,
        "dealer": dealer,
        "round": 1,  # game ends when round == 4
        "bet": bet,
        "player_round_scores": [None, None, None],
        "dealer_round_scores": [None, None, None],
        "commentary": f"Your score is {player.round_score}.",
        "username": "",
        "player_done": False
    }

    # Two-joker rule check
    if len(player.hand) == 2 and all(c[0].is_joker for c in player.hand):
        player.round_score = 30
        state["player_done"] = True
        state["commentary"] = "Two jokers! HOLOBAC! Your score is automatically 30."

    return state

def start_new_round(state):
    """
    Resets player/dealer for a new round, deals 2 cards each, checks 2-joker rule.
    """
    from game.deck import draw_card
    state["player"].reset_round()
    state["dealer"].reset_round()
    state["player_done"] = False

    for _ in range(2):
        card = draw_card(state["deck"])
        if card:
            if card.is_joker:
                state["player"].add_card(card, card_value=10)
            else:
                state["player"].add_card(card)

    for _ in range(2):
        card = draw_card(state["deck"])
        if card:
            if card.is_joker:
                state["dealer"].add_card(card, card_value=10)
            else:
                state["dealer"].add_card(card)

    state["commentary"] = f"Your score is {state['player'].round_score}."
    # Two-joker rule check
    if len(state["player"].hand) == 2 and all(c[0].is_joker for c in state["player"].hand):
        state["player"].round_score = 30
        state["player_done"] = True
        state["commentary"] = "Two jokers! HOLOBAC! Your score is automatically 30."
    return state

#############################
# Discord UI
#############################
class EndGameView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="PLAY AGAIN", style=discord.ButtonStyle.primary, custom_id="holobac_playagain")
    async def play_again_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = start_game(interaction.user.id)
        state["username"] = interaction.user.name
        game_sessions[interaction.user.id] = state
        embed, files = build_embed_with_player_image(state)
        await interaction.response.edit_message(embed=embed, attachments=files, view=HolobacView(interaction.user.id))

    @discord.ui.button(label="CHANGE BET", style=discord.ButtonStyle.primary, custom_id="holobac_changebet")
    async def change_bet_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Change bet not implemented yet!", ephemeral=True)

class HolobacView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="DRAW", style=discord.ButtonStyle.primary, custom_id="holobac_draw")
    async def draw_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Called when user clicks 'DRAW'.
        """
        try:
            await interaction.response.defer()
            await asyncio.sleep(0.5)

            from game.deck import draw_card
            state = game_sessions.get(interaction.user.id)
            if state is None:
                state = start_game(interaction.user.id)
                state["username"] = interaction.user.name
                game_sessions[interaction.user.id] = state

            # If two-joker rule already triggered
            if state.get("player_done", False):
                await self.auto_stand(state, interaction, busted=False)
                return

            card = draw_card(state["deck"])
            if card:
                if card.is_joker:
                    state["player"].add_card(card, card_value=10)
                    state["commentary"] = f"You drew a Joker (as 10). Your score is {state['player'].round_score}."
                else:
                    state["player"].add_card(card)
                    state["commentary"] = f"You drew a {card}. Your score is {state['player'].round_score}."
            else:
                state["commentary"] = "No more cards in the deck!"

            if state["player"].round_score > 30:
                state["player"].is_busted = True
                state["commentary"] = f"Your score is {state['player'].round_score}. You busted!"
                embed, files = build_embed_with_player_image(state)
                await interaction.message.edit(embed=embed, attachments=files, view=self)
                await asyncio.sleep(1)
                await self.auto_stand(state, interaction, busted=True)
                return

            if state["player"].round_score == 30:
                state["commentary"] = "HOLOBAC! You have 30 exactly!"
                embed, files = build_embed_with_player_image(state)
                await interaction.message.edit(embed=embed, attachments=files, view=self)
                await asyncio.sleep(1)
                await self.auto_stand(state, interaction, busted=False)
                return

            embed, files = build_embed_with_player_image(state)
            await interaction.message.edit(embed=embed, attachments=files, view=self)

        except Exception as e:
            print("ERROR in draw_button:", e)
            try:
                await interaction.followup.send("Error in DRAW", ephemeral=True)
            except:
                pass

    async def auto_stand(self, state, interaction: discord.Interaction, busted=False):
        """
        If user busts or hits exactly 30 (two-joker auto),
        finalize the player's round and let the dealer draw.
        """
        from game.deck import draw_card
        while state["dealer"].round_score < 24 and not state["dealer"].is_busted:
            c = draw_card(state["deck"])
            if c:
                if c.is_joker:
                    state["dealer"].add_card(c, card_value=10)
                else:
                    state["dealer"].add_card(c)
            embed, files = build_embed_with_player_image(state)
            await interaction.message.edit(embed=embed, attachments=files, view=self)
            await asyncio.sleep(1)

        player_score = 0 if busted else state["player"].round_score
        dealer_score = 0 if state["dealer"].is_busted else state["dealer"].round_score
        r_idx = state["round"] - 1
        state["player_round_scores"][r_idx] = player_score
        state["dealer_round_scores"][r_idx] = dealer_score

        if busted:
            state["commentary"] += f" Dealer ends with {dealer_score}."
        else:
            state["commentary"] += f" Dealer ends with {dealer_score}."

        state["round"] += 1
        # If round == 4, game ends
        if state["round"] == 4:
            await self.check_game_end(state, interaction)
        else:
            await self.check_game_end(state, interaction)

    async def check_game_end(self, state, interaction: discord.Interaction):
        """
        If round == 4, finalize the entire game. Otherwise, start new round.
        """
        if state["round"] == 4:
            total_dealer = sum(s if s else 0 for s in state["dealer_round_scores"])
            total_player = sum(s if s else 0 for s in state["player_round_scores"])
            if total_player > total_dealer:
                final_color = discord.Color.green()
                final_title = "Well Played!"
                state["commentary"] += f" You won! Final: Dealer {total_dealer}, Player {total_player}"
            elif total_player < total_dealer:
                final_color = discord.Color.red()
                final_title = "Better Luck Next Time!"
                state["commentary"] += f" You lost. Final: Dealer {total_dealer}, Player {total_player}"
            else:
                final_color = discord.Color.greyple()
                final_title = "It's a Tie!"
                state["commentary"] += f" It's a tie! Final: Dealer {total_dealer}, Player {total_player}"

            embed, files = build_embed_with_player_image(state, final_color=final_color, final_title=final_title)
            # Force final embed to say Round 3 of 3
            embed.set_field_at(3, name="Player's Hand", value=f"{state['commentary']}\n(Round 3 of 3)", inline=False)
            await interaction.message.edit(embed=embed, view=EndGameView(interaction.user.id))
            game_sessions.pop(interaction.user.id, None)
        else:
            # Not final round yet
            state = start_new_round(state)
            embed, files = build_embed_with_player_image(state)
            await interaction.message.edit(embed=embed, attachments=files, view=self)

    @discord.ui.button(label="STAND", style=discord.ButtonStyle.primary, custom_id="holobac_stand")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Called when user clicks 'STAND'.
        """
        try:
            await interaction.response.defer()
            await asyncio.sleep(0.5)
            from game.deck import draw_card
            state = game_sessions.get(interaction.user.id)
            if state is None:
                state = start_game(interaction.user.id)
                state["username"] = interaction.user.name
                game_sessions[interaction.user.id] = state

            while state["dealer"].round_score < 24 and not state["dealer"].is_busted:
                c = draw_card(state["deck"])
                if c:
                    if c.is_joker:
                        state["dealer"].add_card(c, card_value=10)
                    else:
                        state["dealer"].add_card(c)
                embed, files = build_embed_with_player_image(state)
                await interaction.message.edit(embed=embed, attachments=files, view=self)
                await asyncio.sleep(1)

            player_score = 0 if state["player"].is_busted else state["player"].round_score
            dealer_score = 0 if state["dealer"].is_busted else state["dealer"].round_score
            r_idx = state["round"] - 1
            state["player_round_scores"][r_idx] = player_score
            state["dealer_round_scores"][r_idx] = dealer_score

            if state["player"].is_busted:
                state["commentary"] = f"You busted! Dealer ends with {dealer_score}."
            else:
                state["commentary"] = f"You stand at {player_score}. Dealer ends with {dealer_score}."

            state["round"] += 1
            await self.check_game_end(state, interaction)

        except Exception as e:
            print("ERROR in stand_button:", e)
            try:
                await interaction.followup.send("Error in STAND.", ephemeral=True)
            except:
                pass

@bot.tree.command(name="holobac", description="Start the Holobac game!")
async def holobac_command(interaction: discord.Interaction):
    """
    /holobac slash command entry point.
    """
    state = start_game(interaction.user.id)
    state["username"] = interaction.user.name
    game_sessions[interaction.user.id] = state

    embed, files = build_embed_with_player_image(state)
    view = HolobacView(interaction.user.id)
    await interaction.response.send_message(embed=embed, files=files, view=view)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN is not set. Make sure it's in .env or passed as an env variable.")
    bot.run(TOKEN)



