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
THUMBNAIL_URL = "https://oriyon111111.github.io/holobac/Thumbnail.png"  # static external URL

#############################
# Utility: Load and Scale Card Images
#############################
def get_card_image_path(suit, rank, is_joker=False):
    """
    Returns the full path to the image file for a given suit/rank or joker.
    We force everything to lowercase to avoid case-sensitivity issues in Docker.
    """
    if is_joker:
        return os.path.join(CARD_DECK_PATH, "comodine", "comodines1.png")
    else:
        suit = suit.lower()
        rank_str = str(rank).lower()
        return os.path.join(CARD_DECK_PATH, suit, f"{suit}{rank_str}.png")

def load_and_scale_card_image(card_obj):
    """
    Opens the image file for card_obj, converts it to RGBA, and scales it.
    """
    if card_obj.is_joker:
        path = get_card_image_path("", "", is_joker=True)
    else:
        path = get_card_image_path(card_obj.suit, card_obj.rank, is_joker=False)
    img = Image.open(path).convert("RGBA")
    scaled = img.resize((SCALED_WIDTH, SCALED_HEIGHT), Image.Resampling.LANCZOS)
    return scaled

def create_player_row_image(player_cards):
    """
    Given a list of card objects (or tuples) for the player, returns a single PIL image
    with all cards laid out horizontally.
    """
    from PIL import Image
    if not player_cards:
        return Image.new("RGBA", (SCALED_WIDTH, SCALED_HEIGHT), (0,0,0,0))
    imgs = [load_and_scale_card_image(c[0]) for c in player_cards]
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
    Converts the dealer's hand (list of (CardObject, assigned_value)) into a string.
    """
    if not dealer_cards:
        return "No cards."
    parts = []
    for card_obj, assigned_val in dealer_cards:
        if card_obj.is_joker:
            parts.append(f"Joker(as {assigned_val})")
        else:
            parts.append(f"{card_obj.rank} of {card_obj.suit.lower()}")
    return " • ".join(parts)

#############################
# Scoreboard
#############################
def graceful_scoreboard(player_scores, dealer_scores):
    """
    Returns two lines of text showing round scores and total using a bracket style.
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
# Build Single Embed with Player's Hand Image
#############################
def build_embed_with_player_image(state, final_color=None, final_title=None):
    """
    Builds a Discord Embed reflecting the current game state.
    """
    from discord import Embed, Color, File
    player_cards = state["player"].hand  # list of (CardObject, assigned_value)
    row_img = create_player_row_image(player_cards)
    img_bytes = io.BytesIO()
    row_img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    player_file = File(img_bytes, filename="player_hand.png")
    embed_title = final_title if final_title else "Let's Play Holobac - Good Luck!"
    color = final_color if final_color else Color.blue()
    embed = Embed(title=embed_title, color=color)
    embed.add_field(name="Table", value=f"Medium (Bet: {state['bet']} Credits)", inline=False)
    d_text = dealer_hand_to_text(state["dealer"].hand)
    embed.add_field(name="Dealer's Hand", value=d_text, inline=False)
    d_line, p_line = graceful_scoreboard(state["player_round_scores"], state["dealer_round_scores"])
    embed.add_field(name="Round Scores", value=f"Dealer: {d_line}\nPlayer: {p_line}", inline=False)
    embed.set_image(url="attachment://player_hand.png")
    round_num = min(state["round"], 3)
    round_str = f"(Round {round_num} of 3)"
    commentary = state["commentary"] if state["commentary"] else ""
    embed.add_field(name="Player's Hand", value=f"{commentary}\n{round_str}", inline=False)
    embed.set_thumbnail(url=THUMBNAIL_URL)
    files = [player_file]
    return embed, files

#############################
# Joker Select View
#############################
class JokerSelectView(discord.ui.View):
    def __init__(self, user_id, state, original_interaction):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.state = state
        self.original_interaction = original_interaction

    @discord.ui.select(
        placeholder="Select a value for the Joker",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="2", value="2"),
            discord.SelectOption(label="3", value="3"),
            discord.SelectOption(label="4", value="4"),
            discord.SelectOption(label="5", value="5"),
            discord.SelectOption(label="6", value="6"),
            discord.SelectOption(label="7", value="7"),
            discord.SelectOption(label="10", value="10"),
            discord.SelectOption(label="11", value="11"),
            discord.SelectOption(label="12", value="12"),
        ]
    )
    async def select_callback(self, select: discord.ui.Select, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This selection isn't for you.", ephemeral=True)
            return
        chosen_value = int(select.values[0])
        # Update the last card (assumed to be the Joker) in the player's hand with the selected value.
        card_obj, _ = self.state["player"].hand[-1]
        self.state["player"].hand[-1] = (card_obj, chosen_value)
        self.state["commentary"] = f"You selected {chosen_value} for the Joker. Your score is now {self.state['player'].round_score}."
        new_embed, files = build_embed_with_player_image(self.state)
        await interaction.response.edit_message(embed=new_embed, attachments=files, view=None)

#############################
# Main Bot Logic and Game State
#############################
game_sessions = {}

def start_game(user_id, bet=0):
    from game.deck import create_combined_deck, shuffle_deck, draw_card
    from game.player import Player
    from game.dealer import Dealer
    deck = create_combined_deck(num_decks=3)
    shuffle_deck(deck)
    player = Player("Player")
    dealer = Dealer()
    # Deal 2 cards to player
    for _ in range(2):
        card = draw_card(deck)
        if card:
            if card.is_joker:
                # Temporarily assign value 0; we'll ask the user to select later.
                player.add_card(card, card_value=0)
            else:
                player.add_card(card)
    # Deal 2 cards to dealer
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
        "round": 1,
        "bet": bet,
        "player_round_scores": [None, None, None],
        "dealer_round_scores": [None, None, None],
        "commentary": f"Your score is {player.round_score}.",
        "username": "",
        "player_done": False
    }
    # Two-joker rule: if first two cards are jokers, auto-assign 30.
    if len(player.hand) == 2 and all(c[0].is_joker for c in player.hand):
        player.round_score = 30
        state["player_done"] = True
        state["commentary"] = "Two jokers! HOLOBAC! Your score is automatically 30."
    return state

def start_new_round(state):
    from game.deck import draw_card
    state["player"].reset_round()
    state["dealer"].reset_round()
    state["player_done"] = False
    for _ in range(2):
        card = draw_card(state["deck"])
        if card:
            if card.is_joker:
                state["player"].add_card(card, card_value=0)  # Joker value to be selected
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
    if len(state["player"].hand) == 2 and all(c[0].is_joker for c in state["player"].hand):
        state["player"].round_score = 30
        state["player_done"] = True
        state["commentary"] = "Two jokers! HOLOBAC! Your score is automatically 30."
    return state

#############################
# Discord UI: Views and Commands
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
        try:
            await interaction.response.defer()
            await asyncio.sleep(0.5)
            from game.deck import draw_card
            state = game_sessions.get(interaction.user.id)
            if state is None:
                state = start_game(interaction.user.id)
                state["username"] = interaction.user.name
                game_sessions[interaction.user.id] = state
            # Draw a card
            card = draw_card(state["deck"])
            if card:
                if card.is_joker:
                    # Add Joker with temporary value 0, then prompt for selection.
                    state["player"].add_card(card, card_value=0)
                    state["commentary"] = "You drew a Joker! Please select a value: 2, 3, 4, 5, 6, 7, 10, 11, or 12."
                    new_embed, files = build_embed_with_player_image(state)
                    # Present the Joker selection dropdown.
                    view = JokerSelectView(interaction.user.id, state, interaction)
                    await interaction.message.edit(embed=new_embed, attachments=files, view=view)
                    return
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
            except Exception as exc:
                print("Followup error:", exc)

    async def auto_stand(self, state, interaction: discord.Interaction, busted=False):
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
        if state["round"] == 4:
            await self.check_game_end(state, interaction)
        else:
            await self.check_game_end(state, interaction)

    async def check_game_end(self, state, interaction: discord.Interaction):
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
            embed.set_field_at(3, name="Player's Hand", value=f"{state['commentary']}\n(Round 3 of 3)", inline=False)
            await interaction.message.edit(embed=embed, view=EndGameView(interaction.user.id))
            game_sessions.pop(interaction.user.id, None)
        else:
            state = start_new_round(state)
            embed, files = build_embed_with_player_image(state)
            await interaction.message.edit(embed=embed, attachments=files, view=self)

    @discord.ui.button(label="STAND", style=discord.ButtonStyle.primary, custom_id="holobac_stand")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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


