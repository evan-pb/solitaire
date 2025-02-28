import pygame
import os
import random
import copy

pygame.init()

# Window
WIDTH, HEIGHT = 1000, 650
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Solitaire")
clock = pygame.time.Clock()

# ===== LAYOUT / DIMENSIONS =====
TABLEAU_SPACING = 20
STOCK_X, STOCK_Y = 50, 50
WASTE_X, WASTE_Y = 50, 200
TABLEAU_START_X, TABLEAU_START_Y = 160, 50 
UNDO_BTN_WIDTH, UNDO_BTN_HEIGHT = 80, 30
RESHUFFLE_BTN_WIDTH, RESHUFFLE_BTN_HEIGHT = 100, 30

# ==== Choose a moderate card size (slightly larger but not screen-filling) ====
CARD_WIDTH, CARD_HEIGHT = 90, 130

# Deck ranks in ascending order
DECK_ORDER = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']

# Fonts
font = pygame.font.SysFont(None, 24)
big_font = pygame.font.SysFont(None, 28)

def create_full_deck():
    """Create a full 52-card deck, shuffled."""
    suits = ['H','D','C','S']
    values = ['A'] + [str(i) for i in range(2,11)] + ['J','Q','K']
    deck = [f"{val}{suit}" for suit in suits for val in values]
    random.shuffle(deck)
    return deck

def load_card_images():
    """
    Load images at their native resolution, then scale them to (CARD_WIDTH, CARD_HEIGHT).
    """
    images = {}
    suits = ['H','D','C','S']
    values = ['A'] + [str(i) for i in range(2,11)] + ['J','Q','K']

    for suit in suits:
        for val in values:
            path = os.path.join("assets", f"{val}{suit}.png")
            img = pygame.image.load(path)
            # Smooth-scale to avoid blockiness
            scaled = pygame.transform.smoothscale(img, (CARD_WIDTH, CARD_HEIGHT))
            images[f"{val}{suit}"] = scaled

    # Card back
    back_path = os.path.join("assets", "red_back.png")
    back_img = pygame.image.load(back_path)
    back_scaled = pygame.transform.smoothscale(back_img, (CARD_WIDTH, CARD_HEIGHT))
    images["BACK"] = back_scaled

    return images

card_images = load_card_images()

def get_rank(card):
    return card[:-1]

def get_suit(card):
    return card[-1]

def rank_index(r):
    return DECK_ORDER.index(r)

def is_opposite_color(c1, c2):
    red_suits = ['H','D']
    black_suits = ['C','S']
    return ((get_suit(c1) in red_suits and get_suit(c2) in black_suits) or
            (get_suit(c1) in black_suits and get_suit(c2) in red_suits))

def is_valid_tableau_move(target_up, top_card):
    """
    - If the tableau pile is empty, only a King can move there.
    - Otherwise, top_card must be exactly one rank lower + opposite color.
    """
    if not target_up:
        return get_rank(top_card) == 'K'
    target_top = target_up[-1]
    return (
        rank_index(get_rank(top_card)) + 1 == rank_index(get_rank(target_top))
        and is_opposite_color(top_card, target_top)
    )

def is_valid_foundation_move(foundation_cards, card, suit):
    """
    - Foundation is suit-specific.
    - If empty, must place Ace of that suit.
    - Otherwise must place next higher rank in ascending order.
    """
    if get_suit(card) != suit:
        return False
    if not foundation_cards:
        return get_rank(card) == 'A'
    top = foundation_cards[-1]
    return rank_index(get_rank(card)) == rank_index(get_rank(top)) + 1

class Solitaire:
    def __init__(self):
        self.deck = create_full_deck()

        # Tableau: each with 'down' (face-down) and 'up' (face-up) lists
        self.tableau = [{"down": [], "up": []} for _ in range(7)]
        self.setup_tableau()  # 28 cards dealt

        # Remainder (24 cards) is our stock
        self.stock = self.deck[:]
        self.waste = []
        self.spent = []  # older waste cards that aren’t currently displayed

        # Foundations, labeled suits in order
        self.foundation_suits = ['H','D','C','S']
        self.foundations = [[] for _ in range(4)]
        self.foundation_rects = []
        for i in range(4):
            fx = WIDTH - (CARD_WIDTH + 20)
            fy = 20 + i*(CARD_HEIGHT + 15)
            self.foundation_rects.append(pygame.Rect(fx, fy, CARD_WIDTH, CARD_HEIGHT))

        # Drag state: (source, subpile, origin_index, dx, dy)
        self.dragging = None

        # Moves and timer
        self.move_count = 0
        self.start_time = pygame.time.get_ticks()

        # History (for undo)
        self.history = []

        # Buttons
        self.undo_rect = pygame.Rect(10, HEIGHT - 40, UNDO_BTN_WIDTH, UNDO_BTN_HEIGHT)
        self.reshuffle_rect = pygame.Rect(
            WIDTH - RESHUFFLE_BTN_WIDTH - 10,
            HEIGHT - 40,
            RESHUFFLE_BTN_WIDTH,
            RESHUFFLE_BTN_HEIGHT
        )

        # Game over
        self.game_over = False
        self.play_again_rect = pygame.Rect(WIDTH // 2 - 60, HEIGHT // 2 + 50, 120, 40)

    def setup_tableau(self):
        """
        Deal i+1 cards onto each of the 7 piles, i facedown + 1 faceup.
        Removes exactly 28 cards from self.deck.
        """
        used = 0
        for i in range(7):
            for j in range(i + 1):
                if j < i:
                    self.tableau[i]["down"].append(self.deck[used])
                else:
                    self.tableau[i]["up"].append(self.deck[used])
                used += 1
        self.deck = self.deck[28:]  # remove those 28 from the deck

    def save_state(self):
        """Save a deep copy of the current state for undo."""
        return {
            "tableau": copy.deepcopy(self.tableau),
            "stock": copy.deepcopy(self.stock),
            "waste": copy.deepcopy(self.waste),
            "spent": copy.deepcopy(self.spent),
            "foundations": copy.deepcopy(self.foundations),
            "move_count": self.move_count,
            "game_over": self.game_over
        }

    def load_state(self, state):
        """Load previously saved state."""
        self.tableau = copy.deepcopy(state["tableau"])
        self.stock = copy.deepcopy(state["stock"])
        self.waste = copy.deepcopy(state["waste"])
        self.spent = copy.deepcopy(state["spent"])
        self.foundations = copy.deepcopy(state["foundations"])
        self.move_count = state["move_count"]
        self.game_over = state["game_over"]

    def handle_mouse_down(self, pos):
        # If the game is won, only check for Play Again
        if self.game_over:
            if self.play_again_rect.collidepoint(pos):
                self.__init__()  # start a new game
            return

        # Undo
        if self.undo_rect.collidepoint(pos):
            self.handle_undo()
            return

        # Reshuffle
        if self.reshuffle_rect.collidepoint(pos):
            self.__init__()  # brand-new game
            return

        # Check stock
        stock_rect = pygame.Rect(STOCK_X, STOCK_Y, CARD_WIDTH, CARD_HEIGHT)
        if stock_rect.collidepoint(pos):
            self.history.append(self.save_state())  # for undo
            self.click_stock()
            self.move_count += 1
            self.check_for_win()
            return

        # Check top of waste
        if self.waste:
            wx = WASTE_X
            wy = WASTE_Y + (len(self.waste) - 1)*TABLEAU_SPACING
            if pygame.Rect(wx, wy, CARD_WIDTH, CARD_HEIGHT).collidepoint(pos):
                self.history.append(self.save_state())
                card = self.waste.pop()
                subpile = [card]
                dx = pos[0] - wx
                dy = pos[1] - wy
                self.dragging = ('waste', subpile, None, dx, dy)
                return

        # Check tableau
        for i, pile in enumerate(self.tableau):
            x = TABLEAU_START_X + i*(CARD_WIDTH+10)
            y = TABLEAU_START_Y + len(pile["down"])*TABLEAU_SPACING

            for cindex in range(len(pile["up"]) - 1, -1, -1):
                card_rect = pygame.Rect(x, y + cindex*TABLEAU_SPACING, CARD_WIDTH, CARD_HEIGHT)
                if card_rect.collidepoint(pos):
                    self.history.append(self.save_state())
                    subpile = pile["up"][cindex:]
                    del pile["up"][cindex:]
                    dx = pos[0] - card_rect.x
                    dy = pos[1] - card_rect.y
                    self.dragging = ('tableau', subpile, i, dx, dy)
                    return

    def click_stock(self):
        # If stock empty, recycle everything from waste + spent
        if not self.stock:
            if self.waste or self.spent:
                self.stock = list(reversed(self.spent + self.waste))
                self.waste.clear()
                self.spent.clear()
            return

        card = self.stock.pop()
        # If waste is at capacity 3, move oldest to spent
        if len(self.waste) == 3:
            oldest = self.waste.pop(0)
            self.spent.append(oldest)
        self.waste.append(card)

    def handle_mouse_up(self, pos):
        if not self.dragging:
            return

        source, subpile, origin_index, dx, dy = self.dragging
        top_card = subpile[0]

        # Attempt foundation drop if single card
        if len(subpile) == 1:
            for i, rect in enumerate(self.foundation_rects):
                if rect.collidepoint(pos):
                    if is_valid_foundation_move(self.foundations[i], top_card, self.foundation_suits[i]):
                        self.foundations[i].append(top_card)
                        self.dragging = None
                        self.on_drop_success(source, subpile, origin_index)
                        return

        # Attempt tableau drop
        placed = False
        for i, pile in enumerate(self.tableau):
            x = TABLEAU_START_X + i*(CARD_WIDTH+10)
            y = TABLEAU_START_Y + (len(pile["down"]) + len(pile["up"]))*TABLEAU_SPACING
            drop_rect = pygame.Rect(x, y, CARD_WIDTH, CARD_HEIGHT)
            if drop_rect.collidepoint(pos):
                if is_valid_tableau_move(pile["up"], top_card):
                    pile["up"].extend(subpile)
                    placed = True
                break

        if placed:
            self.on_drop_success(source, subpile, origin_index)
        else:
            self.on_drop_fail(source, subpile, origin_index)

        self.dragging = None

    def on_drop_success(self, source, subpile, origin_index):
        # If from tableau, check flipping next face-down if needed
        if source == 'tableau':
            up_cards = self.tableau[origin_index]["up"]
            down_cards = self.tableau[origin_index]["down"]
            if not up_cards and down_cards:
                up_cards.append(down_cards.pop())

        self.move_count += 1
        self.check_for_win()

    def on_drop_fail(self, source, subpile, origin_index):
        if source == 'waste':
            self.waste.extend(subpile)
        else:  # 'tableau'
            self.tableau[origin_index]["up"].extend(subpile)

    def handle_mouse_motion(self, pos):
        if self.dragging:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)

    def handle_undo(self):
        if self.history:
            prev_state = self.history.pop()
            self.load_state(prev_state)
            self.move_count = max(0, self.move_count - 1)

    def check_for_win(self):
        # If all 52 cards are in the foundations, we win
        total_in_foundations = sum(len(f) for f in self.foundations)
        if total_in_foundations == 52:
            self.game_over = True

    def draw(self, screen):
        if self.game_over:
            self.draw_win_screen(screen)
            return

        screen.fill((0,128,0))

        # Stock
        if self.stock:
            screen.blit(card_images["BACK"], (STOCK_X, STOCK_Y))

        # Waste
        for i, card in enumerate(self.waste):
            wx = WASTE_X
            wy = WASTE_Y + i*TABLEAU_SPACING
            screen.blit(card_images[card], (wx, wy))

        # Foundations
        for i, rect in enumerate(self.foundation_rects):
            pygame.draw.rect(screen, (255,255,255), rect, 2)
            suit_label = font.render(self.foundation_suits[i], True, (255,255,255))
            label_rect = suit_label.get_rect(center=rect.center)
            screen.blit(suit_label, label_rect)

            if self.foundations[i]:
                top_card = self.foundations[i][-1]
                screen.blit(card_images[top_card], (rect.x, rect.y))

        # Tableau
        for i, pile in enumerate(self.tableau):
            x = TABLEAU_START_X + i*(CARD_WIDTH+10)
            y = TABLEAU_START_Y

            # facedown
            for _ in pile["down"]:
                screen.blit(card_images["BACK"], (x, y))
                y += TABLEAU_SPACING

            # faceup
            for c in pile["up"]:
                screen.blit(card_images[c], (x, y))
                y += TABLEAU_SPACING

        # Dragging subpile
        if self.dragging:
            _, subpile, _, dx, dy = self.dragging
            mx, my = pygame.mouse.get_pos()
            draw_x = mx - dx
            draw_y = my - dy
            for c in subpile:
                screen.blit(card_images[c], (draw_x, draw_y))
                draw_y += TABLEAU_SPACING

        # Timer & moves at bottom center
        elapsed_ms = pygame.time.get_ticks() - self.start_time
        elapsed_sec = elapsed_ms // 1000
        minutes = elapsed_sec // 60
        seconds = elapsed_sec % 60
        time_text = f"{minutes}:{seconds:02d}"
        moves_text = f"Moves: {self.move_count}"
        display_text = f"{time_text}   |   {moves_text}"

        rendered_bottom = big_font.render(display_text, True, (255,255,255))
        bottom_rect = rendered_bottom.get_rect(midbottom=(WIDTH//2, HEIGHT-5))
        screen.blit(rendered_bottom, bottom_rect)

        # Undo button
        pygame.draw.rect(screen, (200,50,50), self.undo_rect)
        undo_label = font.render("Undo", True, (255,255,255))
        label_rect = undo_label.get_rect(center=self.undo_rect.center)
        screen.blit(undo_label, label_rect)

        # Reshuffle button
        pygame.draw.rect(screen, (50,50,200), self.reshuffle_rect)
        reshuffle_label = font.render("Reshuffle", True, (255,255,255))
        label_rect2 = reshuffle_label.get_rect(center=self.reshuffle_rect.center)
        screen.blit(reshuffle_label, label_rect2)

        pygame.display.flip()

    def draw_win_screen(self, screen):
        screen.fill((0,100,0))

        # Win text
        win_text = big_font.render("YOU WIN!", True, (255,255,0))
        win_rect = win_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 20))
        screen.blit(win_text, win_rect)

        # Play again
        pygame.draw.rect(screen, (0,150,0), self.play_again_rect)
        pa_label = font.render("Play Again", True, (255,255,255))
        pa_rect = pa_label.get_rect(center=self.play_again_rect.center)
        screen.blit(pa_label, pa_rect)

        pygame.display.flip()

def main():
    game = Solitaire()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                game.handle_mouse_down(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP:
                game.handle_mouse_up(event.pos)
            elif event.type == pygame.MOUSEMOTION:
                game.handle_mouse_motion(event.pos)

        game.draw(screen)
        clock.tick(60)
    pygame.quit()

if __name__ == '__main__':
    main()