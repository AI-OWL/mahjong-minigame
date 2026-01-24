import pygame
import random
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional

# Initialize Pygame
pygame.init()

# Constants
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
TILE_WIDTH = 80
TILE_HEIGHT = 100
TILE_DEPTH = 8  # 3D effect depth
FPS = 60

# Colors - Modern mobile game palette
BG_GRADIENT_TOP = (20, 30, 60)
BG_GRADIENT_BOTTOM = (60, 40, 80)
TILE_FACE = (245, 240, 235)
TILE_SIDE = (200, 195, 190)
TILE_TOP = (220, 215, 210)
TILE_BORDER = (180, 175, 170)
TILE_SELECTED = (255, 220, 100)
TILE_HINT = (100, 255, 150)
BUTTON_PRIMARY = (76, 175, 80)
BUTTON_PRIMARY_HOVER = (100, 200, 105)
BUTTON_SECONDARY = (33, 150, 243)
BUTTON_DANGER = (244, 67, 54)
TEXT_WHITE = (255, 255, 255)
TEXT_DARK = (50, 50, 50)
SHADOW = (0, 0, 0, 100)
OVERLAY = (0, 0, 0, 180)

# Game States
HOME_SCREEN = 0
LEVEL_SELECT = 1
PLAYING = 2
LEVEL_COMPLETE = 3
GAME_OVER = 4

@dataclass
class TilePosition:
    x: int  # Grid X
    y: int  # Grid Y
    z: int  # Layer (height)
    
    def __hash__(self):
        return hash((self.x, self.y, self.z))
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y and self.z == other.z

class Tile:
    def __init__(self, pos: TilePosition, character_id: int, image: pygame.Surface):
        self.pos = pos
        self.character_id = character_id
        self.image = image
        self.is_selected = False
        self.is_hint = False
        self.render_x = 0
        self.render_y = 0
        self.animation_offset = 0
        
    def get_screen_pos(self, offset_x: int, offset_y: int) -> Tuple[int, int]:
        """Calculate screen position with 3D offset"""
        base_x = offset_x + self.pos.x * (TILE_WIDTH // 2)
        base_y = offset_y + self.pos.y * (TILE_HEIGHT // 2)
        
        # Add 3D depth effect
        depth_offset = self.pos.z * TILE_DEPTH
        
        self.render_x = base_x - depth_offset
        self.render_y = base_y - depth_offset
        
        return self.render_x, self.render_y
    
    def is_blocked_left(self, tiles_dict: dict) -> bool:
        """Check if tile is blocked on the left - adjacent tile on same layer"""
        # A tile at this layer directly to the left
        for dy in [-1, 0, 1]:
            left_pos = TilePosition(self.pos.x - 2, self.pos.y + dy, self.pos.z)
            if left_pos in tiles_dict:
                return True
        return False
    
    def is_blocked_right(self, tiles_dict: dict) -> bool:
        """Check if tile is blocked on the right - adjacent tile on same layer"""
        # A tile at this layer directly to the right
        for dy in [-1, 0, 1]:
            right_pos = TilePosition(self.pos.x + 2, self.pos.y + dy, self.pos.z)
            if right_pos in tiles_dict:
                return True
        return False
    
    def is_blocked_top(self, tiles_dict: dict) -> bool:
        """Check if tile has another tile on top covering it"""
        # Check if any tile one layer above overlaps with this tile's area
        # A tile above must overlap to cover - check a 3x3 grid around our position
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                top_pos = TilePosition(self.pos.x + dx, self.pos.y + dy, self.pos.z + 1)
                if top_pos in tiles_dict:
                    return True
        return False
    
    def is_free(self, tiles_dict: dict) -> bool:
        """Check if tile can be selected - must not be covered AND must be free on at least one side"""
        # Rule 1: Cannot be covered by another tile
        if self.is_blocked_top(tiles_dict):
            return False
        
        # Rule 2: Must be free on at least one side (left OR right, not both blocked)
        left_blocked = self.is_blocked_left(tiles_dict)
        right_blocked = self.is_blocked_right(tiles_dict)
        
        # Free if at least one side is open
        if left_blocked and right_blocked:
            return False
        
        return True
    
    def draw(self, screen: pygame.Surface, tiles_dict: dict = None, is_hovered: bool = False):
        """Draw the domino tile with hover effects"""
        x, y = self.render_x, self.render_y
        y += self.animation_offset
        
        # Check if tile is free (clickable)
        is_free = tiles_dict is None or self.is_free(tiles_dict)
        
        # Draw green glow for hovered usable tiles - very tight to fit domino
        if is_hovered and is_free:
            glow_surf = pygame.Surface((TILE_WIDTH + 6, TILE_HEIGHT + 6), pygame.SRCALPHA)
            for i in range(3, 0, -1):
                alpha = int(100 * (i / 3))
                glow_color = (50, 255, 100, alpha)
                pygame.draw.rect(glow_surf, glow_color, (3-i, 3-i, TILE_WIDTH + i*2, TILE_HEIGHT + i*2), border_radius=4)
            screen.blit(glow_surf, (x - 3, y - 3))
        
        # Draw shadow for depth
        shadow_surf = pygame.Surface((TILE_WIDTH + 6, TILE_HEIGHT + 6), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 80), (0, 0, TILE_WIDTH + 6, TILE_HEIGHT + 6), border_radius=4)
        screen.blit(shadow_surf, (x + 4, y + 4))
        
        # Draw the domino image directly
        if self.image:
            # Calculate darkness based on whether tile is usable
            if is_free or self.is_selected or self.is_hint:
                greyed_out = False
            else:
                # Tile is blocked - apply grey effect
                greyed_out = True
            
            image_rect = self.image.get_rect(topleft=(x, y))
            
            # Apply greyscale to blocked tiles - keep solid, not transparent
            if greyed_out and not self.is_selected and not self.is_hint:
                # Create greyed out version of the image - fully opaque
                greyed_image = self.image.copy()
                
                # Convert to greyscale using a more subtle approach
                # Create a greyscale overlay that desaturates
                pixel_array = pygame.surfarray.pixels3d(greyed_image)
                # Convert to greyscale but keep it visible
                grey_values = (pixel_array[:, :, 0] * 0.3 + 
                              pixel_array[:, :, 1] * 0.59 + 
                              pixel_array[:, :, 2] * 0.11).astype('uint8')
                pixel_array[:, :, 0] = grey_values
                pixel_array[:, :, 1] = grey_values
                pixel_array[:, :, 2] = grey_values
                del pixel_array  # Unlock the surface
                
                # Darken slightly but keep opaque
                dark_overlay = pygame.Surface((greyed_image.get_width(), greyed_image.get_height()), pygame.SRCALPHA)
                dark_overlay.fill((0, 0, 0, 60))  # Subtle darkening, not heavy
                greyed_image.blit(dark_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
                
                screen.blit(greyed_image, image_rect)
            else:
                screen.blit(self.image, image_rect)
            
            # Draw selection/hint border over the domino - slightly inset to fit
            if self.is_selected:
                border_rect = pygame.Rect(x + 2, y + 2, TILE_WIDTH - 4, TILE_HEIGHT - 4)
                pygame.draw.rect(screen, (255, 180, 0), border_rect, 3, border_radius=4)
            elif self.is_hint:
                border_rect = pygame.Rect(x + 2, y + 2, TILE_WIDTH - 4, TILE_HEIGHT - 4)
                pygame.draw.rect(screen, (50, 200, 100), border_rect, 3, border_radius=4)
    
    def contains_point(self, px: int, py: int) -> bool:
        """Check if point is inside tile"""
        return (self.render_x <= px <= self.render_x + TILE_WIDTH and
                self.render_y <= py <= self.render_y + TILE_HEIGHT)

class Button:
    def __init__(self, x: int, y: int, width: int, height: int, text: str, 
                 color: Tuple[int, int, int], hover_color: Tuple[int, int, int], game=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.is_hovered = False
        self.scale = 1.0
        self.game = game
        
    def draw(self, screen: pygame.Surface, font: pygame.font.Font, number_font: pygame.font.Font = None):
        # Smooth scaling animation
        target_scale = 1.05 if self.is_hovered else 1.0
        self.scale += (target_scale - self.scale) * 0.3
        
        # Calculate scaled rect - make it larger to accommodate background
        scaled_width = int(self.rect.width * self.scale)
        scaled_height = int(self.rect.height * self.scale)
        scaled_rect = pygame.Rect(
            self.rect.centerx - scaled_width // 2,
            self.rect.centery - scaled_height // 2,
            scaled_width,
            scaled_height
        )
        
        # Draw button background - fill the entire button with extra padding
        if self.game and self.game.button_background_original:
            # Add extra padding to background for better fit
            bg_width = scaled_width + 40
            bg_height = scaled_height + 20
            button_bg = pygame.transform.smoothscale(self.game.button_background_original, (bg_width, bg_height))
            
            # Apply slight brightness boost if hovered - subtle, not flashbang
            if self.is_hovered:
                button_bg = button_bg.copy()
                bright_overlay = pygame.Surface((bg_width, bg_height), pygame.SRCALPHA)
                bright_overlay.fill((255, 220, 150, 30))  # Warm glow instead of white
                button_bg.blit(bright_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            
            # Center the larger background
            bg_rect = pygame.Rect(
                scaled_rect.centerx - bg_width // 2,
                scaled_rect.centery - bg_height // 2,
                bg_width,
                bg_height
            )
            screen.blit(button_bg, bg_rect)
        else:
            # Fallback to solid color with shadow
            shadow_surf = pygame.Surface((scaled_width + 10, scaled_height + 10), pygame.SRCALPHA)
            pygame.draw.rect(shadow_surf, (0, 0, 0, 120), shadow_surf.get_rect(), border_radius=15)
            screen.blit(shadow_surf, (scaled_rect.x - 5, scaled_rect.y + 5))
            
            color = self.hover_color if self.is_hovered else self.color
            pygame.draw.rect(screen, color, scaled_rect, border_radius=12)
        
        # Draw text with shadow for depth
        if self.text:
            # Text shadow - more prominent
            text_shadow = font.render(self.text, True, (0, 0, 0))
            text_shadow.set_alpha(220)
            text_shadow_rect = text_shadow.get_rect(center=(scaled_rect.centerx + 2, scaled_rect.centery + 2))
            screen.blit(text_shadow, text_shadow_rect)
            
            # Second shadow for extra depth
            text_shadow2 = font.render(self.text, True, (0, 0, 0))
            text_shadow2.set_alpha(120)
            text_shadow2_rect = text_shadow2.get_rect(center=(scaled_rect.centerx + 3, scaled_rect.centery + 3))
            screen.blit(text_shadow2, text_shadow2_rect)
            
            # Main text
            text_surface = font.render(self.text, True, TEXT_WHITE)
            text_rect = text_surface.get_rect(center=scaled_rect.center)
            screen.blit(text_surface, text_rect)
        
    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_hovered:
                return True
        return False

class Level:
    def __init__(self, name: str, layout_function, difficulty: str):
        self.name = name
        self.layout_function = layout_function
        self.difficulty = difficulty

class MahjongGame:
    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Mahjong Solitaire - Match & Clear")
        self.clock = pygame.time.Clock()
        self.running = True
        self.game_state = HOME_SCREEN
        self.hovered_tile = None  # Track which tile is being hovered
        
        # Load fonts
        self.load_fonts()
        
        # Load resources
        self.load_dominos()
        self.load_backgrounds()
        
        # Levels with updated names
        self.levels = [
            Level("Turtle", self.create_pyramid_layout, "Easy"),
            Level("Tri-Peaks", self.create_temple_layout, "Medium"),
            Level("Butterfly", self.create_dragon_layout, "Hard")
        ]
        self.current_level_index = 0
        
        # Game state
        self.tiles: List[Tile] = []
        self.tiles_dict: dict = {}
        self.selected_tile: Optional[Tile] = None
        self.start_time = 0
        self.elapsed_time = 0
        self.matches_made = 0
        self.hint_tiles: List[Tile] = []
        self.moves_left = 0
        
        # Power-up limits
        self.hints_left = 3
        self.undos_left = 3
        self.mixes_left = 3
        
        # Move history for undo
        self.move_history: List[Tuple[Tile, Tile]] = []
        
        # Buttons
        self.create_buttons()
        
    def create_buttons(self):
        """Create all UI buttons"""
        center_x = WINDOW_WIDTH // 2
        
        # Home screen buttons - even larger play button
        self.play_button = Button(center_x - 200, 400, 400, 110, "PLAY", BUTTON_PRIMARY, BUTTON_PRIMARY_HOVER, self)
        
        # Level select buttons - much larger
        self.level_buttons = []
        for i in range(3):
            btn = Button(150 + i * 380, 350, 340, 180, "", BUTTON_SECONDARY, BUTTON_PRIMARY_HOVER, self)
            self.level_buttons.append(btn)
        
        self.back_button = Button(40, 20, 180, 60, "BACK", BUTTON_SECONDARY, BUTTON_PRIMARY_HOVER, self)
        
        # In-game buttons - positioned on right side with spacing, larger size
        self.hint_button = Button(WINDOW_WIDTH - 240, 120, 220, 65, "HINT", BUTTON_SECONDARY, BUTTON_PRIMARY_HOVER, self)
        self.undo_button = Button(WINDOW_WIDTH - 240, 200, 220, 65, "UNDO", BUTTON_SECONDARY, BUTTON_PRIMARY_HOVER, self)
        self.mix_button = Button(WINDOW_WIDTH - 240, 280, 220, 65, "MIX", BUTTON_SECONDARY, BUTTON_PRIMARY_HOVER, self)
        self.restart_button = Button(WINDOW_WIDTH - 240, 360, 220, 65, "RESTART", BUTTON_SECONDARY, BUTTON_PRIMARY_HOVER, self)
        
        # End screen buttons
        self.next_level_button = Button(center_x - 250, 500, 220, 70, "NEXT LEVEL", BUTTON_PRIMARY, BUTTON_PRIMARY_HOVER, self)
        self.retry_button = Button(center_x + 30, 500, 220, 70, "RETRY", BUTTON_SECONDARY, BUTTON_PRIMARY_HOVER, self)
        self.menu_button = Button(center_x - 110, 600, 220, 60, "MENU", BUTTON_SECONDARY, BUTTON_PRIMARY_HOVER, self)
        
    def load_fonts(self):
        """Load custom fonts"""
        try:
            # Load Yusei Magic font for game UI
            yusei_path = "src/yusei-magic/YuseiMagic-Regular.ttf"
            self.button_font = pygame.font.Font(yusei_path, 45)
            self.small_font = pygame.font.Font(yusei_path, 32)
            self.tiny_font = pygame.font.Font(yusei_path, 24)
            self.game_font = pygame.font.Font(yusei_path, 40)  # For in-game text
            print("Loaded Yusei Magic font")
        except Exception as e:
            print(f"Error loading Yusei Magic font: {e}")
            self.button_font = pygame.font.Font(None, 45)
            self.small_font = pygame.font.Font(None, 32)
            self.tiny_font = pygame.font.Font(None, 24)
            self.game_font = pygame.font.Font(None, 40)
        
        # Use same font for numbers
        self.number_font_large = self.button_font
        self.number_font_small = self.small_font
        self.number_font_tiny = self.tiny_font
        
        try:
            # Load decorative fonts for home screen only
            runewood_path = "src/Runewood.ttf"
            self.title_font = pygame.font.Font(runewood_path, 90)
            print("Loaded Runewood font for title")
        except Exception as e:
            print(f"Error loading Runewood font: {e}")
            self.title_font = pygame.font.Font(None, 90)
        
        try:
            # Load Derbyshire for subtitle on home screen
            derbyshire_path = "src/derbyshire/Derbyshire Bold.otf"
            self.subtitle_font = pygame.font.Font(derbyshire_path, 40)
            print("Loaded Derbyshire font for subtitle")
        except Exception as e:
            print(f"Error loading Derbyshire font: {e}")
            self.subtitle_font = pygame.font.Font(None, 40)
    
    def load_backgrounds(self):
        """Load background images"""
        try:
            # Load main background
            main_bg = pygame.image.load("src/Backgrounds/mainBG.png")
            self.main_background = pygame.transform.scale(main_bg, (WINDOW_WIDTH, WINDOW_HEIGHT))
            print("Loaded main background")
        except Exception as e:
            print(f"Error loading mainBG.png: {e}")
            # Fallback to gradient
            self.main_background = self.create_gradient_background()
        
        try:
            # Load button background
            button_bg = pygame.image.load("src/Backgrounds/buttonBG.png")
            # Keep original for tiling/scaling as needed
            self.button_background_original = button_bg
            print("Loaded button background")
        except Exception as e:
            print(f"Error loading buttonBG.png: {e}")
            self.button_background_original = None
        
        try:
            # Load text background for title/subtitle
            text_bg = pygame.image.load("src/Backgrounds/textBG.png")
            self.text_background_original = text_bg
            print("Loaded text background")
        except Exception as e:
            print(f"Error loading textBG.png: {e}")
            self.text_background_original = None
    
    def create_gradient_background(self):
        """Create gradient background as fallback"""
        background = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        for y in range(WINDOW_HEIGHT):
            ratio = y / WINDOW_HEIGHT
            color = (
                int(BG_GRADIENT_TOP[0] + (BG_GRADIENT_BOTTOM[0] - BG_GRADIENT_TOP[0]) * ratio),
                int(BG_GRADIENT_TOP[1] + (BG_GRADIENT_BOTTOM[1] - BG_GRADIENT_TOP[1]) * ratio),
                int(BG_GRADIENT_TOP[2] + (BG_GRADIENT_BOTTOM[2] - BG_GRADIENT_TOP[2]) * ratio)
            )
            pygame.draw.line(background, color, (0, y), (WINDOW_WIDTH, y))
        return background
    
    def load_dominos(self):
        """Load all domino images from dominos folder"""
        self.domino_images = []
        dominos_path = Path("src/dominos")
        
        # Load dominos in sorted order to maintain consistency
        domino_files = sorted(dominos_path.glob("*.png"))
        
        for domino_file in domino_files:
            try:
                image = pygame.image.load(str(domino_file))
                # Scale domino to exact tile size - the images ARE the tiles
                image = pygame.transform.smoothscale(image, (TILE_WIDTH, TILE_HEIGHT))
                self.domino_images.append(image)
                print(f"Loaded {domino_file.name}")
            except Exception as e:
                print(f"Error loading {domino_file}: {e}")
        
        print(f"Loaded {len(self.domino_images)} domino images")
        
    def create_pyramid_layout(self) -> List[TilePosition]:
        """Create simple symmetrical pyramid - Easy level"""
        positions = []
        
        # Simple pyramid - 5 layers, symmetrical
        # Layer 0 (base) - 7x7
        for y in range(0, 14, 2):
            for x in range(0, 14, 2):
                positions.append(TilePosition(x, y, 0))
        
        # Layer 1 - 5x5
        for y in range(2, 12, 2):
            for x in range(2, 12, 2):
                positions.append(TilePosition(x, y, 1))
        
        # Layer 2 - 3x3
        for y in range(4, 10, 2):
            for x in range(4, 10, 2):
                positions.append(TilePosition(x, y, 2))
        
        # Layer 3 - 2x2
        for y in range(5, 9, 2):
            for x in range(5, 9, 2):
                positions.append(TilePosition(x, y, 3))
        
        # Layer 4 (top) - 1 tile
        positions.append(TilePosition(6, 6, 4))
        
        return positions
    
    def create_temple_layout(self) -> List[TilePosition]:
        """Create three symmetrical pyramids (Tri-Peaks) - Medium level"""
        positions = []
        
        # Left pyramid - 4 layers
        # Layer 0 - 3x3 base
        for y in range(8, 14, 2):
            for x in range(2, 8, 2):
                positions.append(TilePosition(x, y, 0))
        # Layer 1 - 2x2
        for y in range(9, 13, 2):
            for x in range(3, 7, 2):
                positions.append(TilePosition(x, y, 1))
        # Layer 2 - 1x1
        positions.append(TilePosition(4, 10, 2))
        # Peak
        positions.append(TilePosition(4, 10, 3))
        
        # Middle pyramid - 4 layers
        # Layer 0 - 3x3 base
        for y in range(8, 14, 2):
            for x in range(11, 17, 2):
                positions.append(TilePosition(x, y, 0))
        # Layer 1 - 2x2
        for y in range(9, 13, 2):
            for x in range(12, 16, 2):
                positions.append(TilePosition(x, y, 1))
        # Layer 2 - 1x1
        positions.append(TilePosition(13, 10, 2))
        # Peak
        positions.append(TilePosition(13, 10, 3))
        
        # Right pyramid - 4 layers
        # Layer 0 - 3x3 base
        for y in range(8, 14, 2):
            for x in range(20, 26, 2):
                positions.append(TilePosition(x, y, 0))
        # Layer 1 - 2x2
        for y in range(9, 13, 2):
            for x in range(21, 25, 2):
                positions.append(TilePosition(x, y, 1))
        # Layer 2 - 1x1
        positions.append(TilePosition(22, 10, 2))
        # Peak
        positions.append(TilePosition(22, 10, 3))
        
        return positions
    
    def create_dragon_layout(self) -> List[TilePosition]:
        """Create Butterfly layout - Hard level"""
        positions = []
        
        # Center vertical row: 2 wide at bottom, 1 wide for 2 stacks above
        # Bottom - 2 wide
        positions.append(TilePosition(13, 10, 0))
        positions.append(TilePosition(15, 10, 0))
        # Middle - 1 wide (centered on bottom 2)
        positions.append(TilePosition(14, 9, 1))
        # Top - 1 wide
        positions.append(TilePosition(14, 8, 2))
        
        # LEFT WING
        # Top circle (smaller) - 3 stacks high total
        # Layer 0 - outer ring
        left_top_outer = [(6, 6), (8, 6), (10, 6), (6, 8), (10, 8), (6, 10), (8, 10), (10, 10)]
        for x, y in left_top_outer:
            positions.append(TilePosition(x, y, 0))
        
        # Layer 1 - closer to center
        left_top_mid = [(7, 7), (9, 7), (7, 9), (9, 9)]
        for x, y in left_top_mid:
            positions.append(TilePosition(x, y, 1))
        
        # Layer 2 - center with 1 domino stack
        positions.append(TilePosition(8, 8, 2))
        
        # Bottom circle (larger) - 3 stacks high total
        # Layer 0 - outer ring (larger)
        left_bottom_outer = [(4, 12), (6, 12), (8, 12), (10, 12), (4, 14), (10, 14), (4, 16), (6, 16), (8, 16), (10, 16)]
        for x, y in left_bottom_outer:
            positions.append(TilePosition(x, y, 0))
        
        # Layer 1 - closer to center
        left_bottom_mid = [(5, 13), (7, 13), (9, 13), (5, 15), (9, 15), (7, 15)]
        for x, y in left_bottom_mid:
            positions.append(TilePosition(x, y, 1))
        
        # Layer 2 - center with 5 domino stack (1 in middle, 1 on each side)
        # Middle
        positions.append(TilePosition(7, 14, 2))
        # Left of middle
        positions.append(TilePosition(6, 14, 2))
        # Right of middle
        positions.append(TilePosition(8, 14, 2))
        # Add 2 more for 5 total
        positions.append(TilePosition(7, 13, 2))
        positions.append(TilePosition(7, 15, 2))
        
        # Connecting pieces - 3 stacks high next to center row
        positions.append(TilePosition(12, 9, 0))
        positions.append(TilePosition(12, 9, 1))
        positions.append(TilePosition(12, 9, 2))
        
        # RIGHT WING (mirror of left)
        # Top circle (smaller) - 3 stacks high total
        # Layer 0 - outer ring
        right_top_outer = [(18, 6), (20, 6), (22, 6), (18, 8), (22, 8), (18, 10), (20, 10), (22, 10)]
        for x, y in right_top_outer:
            positions.append(TilePosition(x, y, 0))
        
        # Layer 1 - closer to center
        right_top_mid = [(19, 7), (21, 7), (19, 9), (21, 9)]
        for x, y in right_top_mid:
            positions.append(TilePosition(x, y, 1))
        
        # Layer 2 - center with 1 domino stack
        positions.append(TilePosition(20, 8, 2))
        
        # Bottom circle (larger) - 3 stacks high total
        # Layer 0 - outer ring (larger)
        right_bottom_outer = [(18, 12), (20, 12), (22, 12), (24, 12), (18, 14), (24, 14), (18, 16), (20, 16), (22, 16), (24, 16)]
        for x, y in right_bottom_outer:
            positions.append(TilePosition(x, y, 0))
        
        # Layer 1 - closer to center
        right_bottom_mid = [(19, 13), (21, 13), (23, 13), (19, 15), (23, 15), (21, 15)]
        for x, y in right_bottom_mid:
            positions.append(TilePosition(x, y, 1))
        
        # Layer 2 - center with 5 domino stack (1 in middle, 1 on each side)
        # Middle
        positions.append(TilePosition(21, 14, 2))
        # Left of middle
        positions.append(TilePosition(20, 14, 2))
        # Right of middle
        positions.append(TilePosition(22, 14, 2))
        # Add 2 more for 5 total
        positions.append(TilePosition(21, 13, 2))
        positions.append(TilePosition(21, 15, 2))
        
        # Connecting pieces - 3 stacks high next to center row
        positions.append(TilePosition(16, 9, 0))
        positions.append(TilePosition(16, 9, 1))
        positions.append(TilePosition(16, 9, 2))
        
        return positions
    
    def create_tiles_from_layout(self, positions: List[TilePosition]):
        """Create tiles from position layout with guaranteed even distribution for winnability"""
        self.tiles = []
        self.tiles_dict = {}
        self.selected_tile = None
        self.hint_tiles = []
        self.matches_made = 0
        
        # Reset power-up limits
        self.hints_left = 3
        self.undos_left = 3
        self.mixes_left = 3
        self.move_history = []
        
        # We need pairs, so ensure even number of positions
        if len(positions) % 2 != 0:
            positions = positions[:-1]
        
        # CRITICAL: Create EVEN distribution - every character appears EXACTLY the same number of times
        num_pairs = len(positions) // 2
        num_dominos = len(self.domino_images)
        character_ids = []
        
        # Calculate how many times each character should appear
        pairs_per_character = num_pairs // num_dominos
        remainder = num_pairs % num_dominos
        
        # Add equal pairs for each character
        for char_id in range(num_dominos):
            for _ in range(pairs_per_character):
                character_ids.append(char_id)
        
        # Distribute remainder evenly
        for i in range(remainder):
            character_ids.append(i)
        
        # Now we have exactly num_pairs character IDs
        # Duplicate for pairs (each character appears twice)
        character_ids = character_ids * 2
        
        # Shuffle to randomize positions
        random.shuffle(character_ids)
        
        # Verify we have the right number
        assert len(character_ids) == len(positions), f"Mismatch: {len(character_ids)} ids for {len(positions)} positions"
        
        # Create tiles
        for i, pos in enumerate(positions):
            char_id = character_ids[i]
            image = self.domino_images[char_id]
            tile = Tile(pos, char_id, image)
            self.tiles.append(tile)
            self.tiles_dict[pos] = tile
        
        self.update_moves_count()
        
    def start_level(self, level_index: int):
        """Start a specific level"""
        self.current_level_index = level_index
        level = self.levels[level_index]
        positions = level.layout_function()
        self.create_tiles_from_layout(positions)
        self.start_time = pygame.time.get_ticks()
        self.game_state = PLAYING
        
    def update_moves_count(self):
        """Count available matching pairs"""
        self.moves_left = 0
        free_tiles = [t for t in self.tiles if t.is_free(self.tiles_dict)]
        
        for i, tile1 in enumerate(free_tiles):
            for tile2 in free_tiles[i + 1:]:
                if tile1.character_id == tile2.character_id:
                    self.moves_left += 1
        
    def show_hint(self):
        """Highlight a matching pair"""
        if self.hints_left <= 0:
            return
        
        # Clear previous hints
        for tile in self.tiles:
            tile.is_hint = False
        self.hint_tiles = []
        
        free_tiles = [t for t in self.tiles if t.is_free(self.tiles_dict)]
        
        for i, tile1 in enumerate(free_tiles):
            for tile2 in free_tiles[i + 1:]:
                if tile1.character_id == tile2.character_id:
                    tile1.is_hint = True
                    tile2.is_hint = True
                    self.hint_tiles = [tile1, tile2]
                    self.hints_left -= 1
                    return
    
    def undo_move(self):
        """Undo the last move"""
        if self.undos_left <= 0 or len(self.move_history) == 0:
            return
        
        # Get the last matched pair
        tile1, tile2 = self.move_history.pop()
        
        # Add tiles back to the game
        self.tiles.append(tile1)
        self.tiles.append(tile2)
        self.tiles_dict[tile1.pos] = tile1
        self.tiles_dict[tile2.pos] = tile2
        
        # Reset selection states
        tile1.is_selected = False
        tile2.is_selected = False
        tile1.is_hint = False
        tile2.is_hint = False
        
        self.selected_tile = None
        self.matches_made -= 1
        self.undos_left -= 1
        self.update_moves_count()
    
    def mix_tiles(self):
        """Reshuffle remaining tiles"""
        if self.mixes_left <= 0:
            return
        
        # Get all character IDs from remaining tiles
        character_ids = [tile.character_id for tile in self.tiles]
        random.shuffle(character_ids)
        
        # Reassign character IDs and images to tiles
        for i, tile in enumerate(self.tiles):
            tile.character_id = character_ids[i]
            tile.image = self.domino_images[character_ids[i]]
            tile.is_selected = False
            tile.is_hint = False
        
        self.selected_tile = None
        self.mixes_left -= 1
        self.update_moves_count()
        
    def handle_tile_click(self, tile: Tile):
        """Handle clicking on a tile"""
        if not tile.is_free(self.tiles_dict):
            return
        
        # Clear hints
        for t in self.tiles:
            t.is_hint = False
        
        if self.selected_tile is None:
            # Select first tile
            tile.is_selected = True
            self.selected_tile = tile
        elif self.selected_tile == tile:
            # Deselect
            tile.is_selected = False
            self.selected_tile = None
        else:
            # Try to match
            if self.selected_tile.character_id == tile.character_id:
                # Match found! Store in history for undo
                self.move_history.append((self.selected_tile, tile))
                
                # Remove both tiles
                self.tiles.remove(self.selected_tile)
                self.tiles.remove(tile)
                del self.tiles_dict[self.selected_tile.pos]
                del self.tiles_dict[tile.pos]
                self.selected_tile = None
                self.matches_made += 1
                
                # Check win condition
                if len(self.tiles) == 0:
                    self.game_state = LEVEL_COMPLETE
                else:
                    self.update_moves_count()
                    # Check if no more moves (and no mix available)
                    if self.moves_left == 0 and self.mixes_left == 0:
                        self.game_state = GAME_OVER
            else:
                # No match, switch selection
                self.selected_tile.is_selected = False
                tile.is_selected = True
                self.selected_tile = tile
    
    def draw_gradient_rect(self, surface: pygame.Surface, rect: pygame.Rect, 
                          color1: Tuple[int, int, int], color2: Tuple[int, int, int]):
        """Draw a rectangle with vertical gradient"""
        for y in range(rect.height):
            ratio = y / rect.height
            color = (
                int(color1[0] + (color2[0] - color1[0]) * ratio),
                int(color1[1] + (color2[1] - color1[1]) * ratio),
                int(color1[2] + (color2[2] - color1[2]) * ratio)
            )
            pygame.draw.line(surface, color, 
                           (rect.x, rect.y + y), 
                           (rect.x + rect.width, rect.y + y))
    
    def draw_home_screen(self):
        """Draw modern home screen"""
        self.screen.blit(self.main_background, (0, 0))
        
        # Draw text background for title and subtitle
        if self.text_background_original:
            # Calculate size needed for title + subtitle
            title_text = self.title_font.render("MAHJONG", True, TEXT_WHITE)
            subtitle = self.subtitle_font.render("SOLITAIRE", True, (255, 215, 100))
            
            # Size the text background to fit both title and subtitle with padding
            text_bg_width = max(title_text.get_width(), subtitle.get_width()) + 120
            text_bg_height = title_text.get_height() + subtitle.get_height() + 60
            
            text_bg = pygame.transform.smoothscale(self.text_background_original, (text_bg_width, text_bg_height))
            text_bg_x = WINDOW_WIDTH // 2 - text_bg_width // 2
            text_bg_y = 100
            self.screen.blit(text_bg, (text_bg_x, text_bg_y))
            
            # Draw title with shadow on top of background
            title_shadow = self.title_font.render("MAHJONG", True, (0, 0, 0))
            self.screen.blit(title_shadow, (WINDOW_WIDTH // 2 - title_text.get_width() // 2 + 3, text_bg_y + 23))
            self.screen.blit(title_text, (WINDOW_WIDTH // 2 - title_text.get_width() // 2, text_bg_y + 20))
            
            # Draw subtitle on background
            self.screen.blit(subtitle, (WINDOW_WIDTH // 2 - subtitle.get_width() // 2, text_bg_y + title_text.get_height() + 30))
        else:
            # Fallback without background
            title_shadow = self.title_font.render("MAHJONG", True, (0, 0, 0))
            title_text = self.title_font.render("MAHJONG", True, TEXT_WHITE)
            self.screen.blit(title_shadow, (WINDOW_WIDTH // 2 - title_text.get_width() // 2 + 3, 153))
            self.screen.blit(title_text, (WINDOW_WIDTH // 2 - title_text.get_width() // 2, 150))
            
            subtitle = self.subtitle_font.render("SOLITAIRE", True, (255, 215, 100))
            self.screen.blit(subtitle, (WINDOW_WIDTH // 2 - subtitle.get_width() // 2, 240))
        
        # Instructions with text background - more spacing
        instructions = [
            "Match tiles on top of the pile",
            "Clear all tiles to win",
            "3 unique levels to master"
        ]
        y = 540
        for text in instructions:
            surf = self.small_font.render(text, True, TEXT_WHITE)
            
            # Draw text background for each instruction - much larger
            if self.text_background_original:
                instr_bg_width = surf.get_width() + 120  # More padding
                instr_bg_height = surf.get_height() + 30  # More padding
                instr_bg = pygame.transform.smoothscale(self.text_background_original, (instr_bg_width, instr_bg_height))
                instr_bg_x = WINDOW_WIDTH // 2 - instr_bg_width // 2
                self.screen.blit(instr_bg, (instr_bg_x, y - 10))
            
            self.screen.blit(surf, (WINDOW_WIDTH // 2 - surf.get_width() // 2, y))
            y += 70  # More spacing between instructions
        
        # Draw play button with smaller text
        self.play_button.draw(self.screen, self.small_font, self.small_font)
        
    def draw_level_select(self):
        """Draw level selection screen"""
        self.screen.blit(self.main_background, (0, 0))
        
        # Title with larger background and shadow
        title = self.button_font.render("SELECT LEVEL", True, TEXT_WHITE)
        title_shadow = self.button_font.render("SELECT LEVEL", True, (0, 0, 0))
        title_shadow.set_alpha(200)
        
        if self.text_background_original:
            title_bg_width = title.get_width() + 180  # Larger background
            title_bg_height = title.get_height() + 50
            title_bg = pygame.transform.smoothscale(self.text_background_original, (title_bg_width, title_bg_height))
            title_bg_x = WINDOW_WIDTH // 2 - title_bg_width // 2
            self.screen.blit(title_bg, (title_bg_x, 60))
            title_x = WINDOW_WIDTH // 2 - title.get_width() // 2
            self.screen.blit(title_shadow, (title_x + 2, 77))
            self.screen.blit(title, (title_x, 75))
        else:
            title_x = WINDOW_WIDTH // 2 - title.get_width() // 2
            self.screen.blit(title_shadow, (title_x + 2, 82))
            self.screen.blit(title, (title_x, 80))
        
        # Level buttons - use textBG for larger backgrounds
        for i, (btn, level) in enumerate(zip(self.level_buttons, self.levels)):
            # Draw text background (textBG) instead of buttonBG
            if self.text_background_original:
                level_bg_width = btn.rect.width + 60
                level_bg_height = btn.rect.height + 40
                level_bg = pygame.transform.smoothscale(self.text_background_original, (level_bg_width, level_bg_height))
                level_bg_x = btn.rect.centerx - level_bg_width // 2
                level_bg_y = btn.rect.centery - level_bg_height // 2
                
                # Apply brightness if hovered - subtle warm glow
                if btn.is_hovered:
                    level_bg = level_bg.copy()
                    bright_overlay = pygame.Surface((level_bg_width, level_bg_height), pygame.SRCALPHA)
                    bright_overlay.fill((255, 220, 150, 30))
                    level_bg.blit(bright_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
                
                self.screen.blit(level_bg, (level_bg_x, level_bg_y))
            
            # Level info on button - use Yusei font with shadows
            level_num_label = self.button_font.render("LEVEL ", True, TEXT_WHITE)
            level_num_label_shadow = self.button_font.render("LEVEL ", True, (0, 0, 0))
            level_num_value = self.button_font.render(f"{i + 1}", True, TEXT_WHITE)
            level_num_value_shadow = self.button_font.render(f"{i + 1}", True, (0, 0, 0))
            name_text = self.small_font.render(level.name, True, TEXT_WHITE)
            name_text_shadow = self.small_font.render(level.name, True, (0, 0, 0))
            diff_text = self.tiny_font.render(level.difficulty, True, (200, 255, 200))
            diff_text_shadow = self.tiny_font.render(level.difficulty, True, (0, 0, 0))
            
            btn_center_x = btn.rect.centerx
            
            # Draw "LEVEL" and number together with shadows
            level_combined_width = level_num_label.get_width() + level_num_value.get_width()
            level_start_x = btn_center_x - level_combined_width // 2
            
            # Shadows
            level_num_label_shadow.set_alpha(200)
            level_num_value_shadow.set_alpha(200)
            self.screen.blit(level_num_label_shadow, (level_start_x + 2, btn.rect.y + 32))
            self.screen.blit(level_num_value_shadow, (level_start_x + level_num_label.get_width() + 2, btn.rect.y + 32))
            # Text
            self.screen.blit(level_num_label, (level_start_x, btn.rect.y + 30))
            self.screen.blit(level_num_value, (level_start_x + level_num_label.get_width(), btn.rect.y + 30))
            
            # Name with shadow
            name_text_shadow.set_alpha(200)
            self.screen.blit(name_text_shadow, (btn_center_x - name_text.get_width() // 2 + 2, btn.rect.y + 87))
            self.screen.blit(name_text, (btn_center_x - name_text.get_width() // 2, btn.rect.y + 85))
            
            # Difficulty with shadow
            diff_text_shadow.set_alpha(200)
            self.screen.blit(diff_text_shadow, (btn_center_x - diff_text.get_width() // 2 + 2, btn.rect.y + 132))
            self.screen.blit(diff_text, (btn_center_x - diff_text.get_width() // 2, btn.rect.y + 130))
        
        # Back button with larger background - smaller text with shadow
        if self.text_background_original:
            back_text = self.tiny_font.render("BACK", True, TEXT_WHITE)
            back_text_shadow = self.tiny_font.render("BACK", True, (0, 0, 0))
            back_text_shadow.set_alpha(200)
            back_bg_width = back_text.get_width() + 100
            back_bg_height = back_text.get_height() + 40
            back_bg = pygame.transform.smoothscale(self.text_background_original, (back_bg_width, back_bg_height))
            back_bg_x = self.back_button.rect.centerx - back_bg_width // 2
            back_bg_y = self.back_button.rect.centery - back_bg_height // 2
            
            if self.back_button.is_hovered:
                back_bg = back_bg.copy()
                bright_overlay = pygame.Surface((back_bg_width, back_bg_height), pygame.SRCALPHA)
                bright_overlay.fill((255, 220, 150, 30))
                back_bg.blit(bright_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            
            self.screen.blit(back_bg, (back_bg_x, back_bg_y))
            text_x = self.back_button.rect.centerx - back_text.get_width() // 2
            text_y = self.back_button.rect.centery - back_text.get_height() // 2
            self.screen.blit(back_text_shadow, (text_x + 2, text_y + 2))
            self.screen.blit(back_text, (text_x, text_y))
        else:
            self.back_button.draw(self.screen, self.tiny_font, self.tiny_font)
        
    def draw_game_screen(self):
        """Draw the main game"""
        self.screen.blit(self.main_background, (0, 0))
        
        # Update timer
        if len(self.tiles) > 0:
            self.elapsed_time = (pygame.time.get_ticks() - self.start_time) // 1000
        
        # Draw Level info at top with background - use Yusei font with shadow
        level = self.levels[self.current_level_index]
        level_text = self.game_font.render(f"Level {self.current_level_index + 1}: {level.name}", True, TEXT_WHITE)
        level_shadow = self.game_font.render(f"Level {self.current_level_index + 1}: {level.name}", True, (0, 0, 0))
        level_shadow.set_alpha(200)
        
        if self.text_background_original:
            level_bg_width = level_text.get_width() + 100
            level_bg_height = level_text.get_height() + 30
            level_bg = pygame.transform.smoothscale(self.text_background_original, (level_bg_width, level_bg_height))
            level_bg_x = WINDOW_WIDTH // 2 - level_bg_width // 2
            self.screen.blit(level_bg, (level_bg_x, 20))
            text_x = WINDOW_WIDTH // 2 - level_text.get_width() // 2
            self.screen.blit(level_shadow, (text_x + 2, 32))
            self.screen.blit(level_text, (text_x, 30))
        else:
            self.screen.blit(level_shadow, (32, 22))
            self.screen.blit(level_text, (30, 20))
        
        # Draw stats on the left side with proper spacing and backgrounds - use Yusei for all
        stats_data = [
            ("Time", f"{self.elapsed_time}s", 30),
            ("Tiles", f"{len(self.tiles)}", 30),
            ("Moves", f"{self.moves_left}", 30)
        ]
        
        y_pos = 120
        for label, value, x_pos in stats_data:
            # Render label and value with Yusei font and shadows
            label_text = self.small_font.render(label, True, TEXT_WHITE)
            label_shadow = self.small_font.render(label, True, (0, 0, 0))
            label_shadow.set_alpha(200)
            value_text = self.small_font.render(value, True, TEXT_WHITE)
            value_shadow = self.small_font.render(value, True, (0, 0, 0))
            value_shadow.set_alpha(200)
            
            # Calculate combined width for background
            combined_width = label_text.get_width() + value_text.get_width() + 20
            combined_height = max(label_text.get_height(), value_text.get_height())
            
            # Draw background
            if self.text_background_original:
                stat_bg_width = combined_width + 60
                stat_bg_height = combined_height + 20
                stat_bg = pygame.transform.smoothscale(self.text_background_original, (stat_bg_width, stat_bg_height))
                self.screen.blit(stat_bg, (x_pos - 20, y_pos - 5))
            
            # Draw text with shadows
            self.screen.blit(label_shadow, (x_pos + 2, y_pos + 2))
            self.screen.blit(label_text, (x_pos, y_pos))
            self.screen.blit(value_shadow, (x_pos + label_text.get_width() + 12, y_pos + 2))
            self.screen.blit(value_text, (x_pos + label_text.get_width() + 10, y_pos))
            
            y_pos += 60
        
        # Draw buttons on the right side with counters - smaller text with shadows
        # Hint button with counter
        hint_counter = self.tiny_font.render(f"({self.hints_left})", True, TEXT_WHITE)
        hint_counter_shadow = self.tiny_font.render(f"({self.hints_left})", True, (0, 0, 0))
        hint_counter_shadow.set_alpha(200)
        self.hint_button.draw(self.screen, self.tiny_font, self.tiny_font)
        
        # Draw counter next to button with shadow
        counter_x = self.hint_button.rect.x + self.hint_button.rect.width + 15
        counter_y = self.hint_button.rect.centery - hint_counter.get_height() // 2
        self.screen.blit(hint_counter_shadow, (counter_x + 2, counter_y + 2))
        self.screen.blit(hint_counter, (counter_x, counter_y))
        
        # Undo button with counter
        undo_counter = self.tiny_font.render(f"({self.undos_left})", True, TEXT_WHITE)
        undo_counter_shadow = self.tiny_font.render(f"({self.undos_left})", True, (0, 0, 0))
        undo_counter_shadow.set_alpha(200)
        self.undo_button.draw(self.screen, self.tiny_font, self.tiny_font)
        counter_y = self.undo_button.rect.centery - undo_counter.get_height() // 2
        self.screen.blit(undo_counter_shadow, (counter_x + 2, counter_y + 2))
        self.screen.blit(undo_counter, (counter_x, counter_y))
        
        # Mix button with counter
        mix_counter = self.tiny_font.render(f"({self.mixes_left})", True, TEXT_WHITE)
        mix_counter_shadow = self.tiny_font.render(f"({self.mixes_left})", True, (0, 0, 0))
        mix_counter_shadow.set_alpha(200)
        self.mix_button.draw(self.screen, self.tiny_font, self.tiny_font)
        counter_y = self.mix_button.rect.centery - mix_counter.get_height() // 2
        self.screen.blit(mix_counter_shadow, (counter_x + 2, counter_y + 2))
        self.screen.blit(mix_counter, (counter_x, counter_y))
        
        # Restart button
        self.restart_button.draw(self.screen, self.tiny_font, self.tiny_font)
        
        # Back button at top right - smaller text
        self.back_button.draw(self.screen, self.tiny_font, self.tiny_font)
        
        # Calculate tile positions - dynamically center based on actual pixel bounds
        if self.tiles:
            # Find grid coordinate bounds
            min_x = min(tile.pos.x for tile in self.tiles)
            max_x = max(tile.pos.x for tile in self.tiles)
            min_y = min(tile.pos.y for tile in self.tiles)
            max_y = max(tile.pos.y for tile in self.tiles)
            max_z = max(tile.pos.z for tile in self.tiles)
            
            # Calculate pixel bounds considering isometric projection
            # Each grid unit in X adds TILE_WIDTH // 2, in Y adds TILE_HEIGHT // 2
            pixel_width = (max_x - min_x) * (TILE_WIDTH // 2) + TILE_WIDTH
            pixel_height = (max_y - min_y) * (TILE_HEIGHT // 2) + TILE_HEIGHT
            
            # Add extra space for 3D depth effect
            depth_offset = max_z * TILE_DEPTH
            pixel_width += depth_offset
            pixel_height += depth_offset
            
            # Calculate offsets to center the layout
            # Account for min coordinates to position correctly
            offset_x = (WINDOW_WIDTH - pixel_width) // 2 - min_x * (TILE_WIDTH // 2) + depth_offset
            offset_y = (WINDOW_HEIGHT - pixel_height) // 2 - min_y * (TILE_HEIGHT // 2) + 80  # Extra space for top UI
        else:
            offset_x = WINDOW_WIDTH // 2
            offset_y = WINDOW_HEIGHT // 2
        
        for tile in self.tiles:
            tile.get_screen_pos(offset_x, offset_y)
        
        # Sort tiles for proper rendering (back to front, bottom to top)
        sorted_tiles = sorted(self.tiles, key=lambda t: (t.pos.z, t.render_y, t.render_x))
        
        # Get current mouse position to detect hover
        mouse_pos = pygame.mouse.get_pos()
        self.hovered_tile = None
        
        # Find which tile is being hovered (check top tiles first)
        sorted_tiles_top_first = sorted(self.tiles, key=lambda t: (-t.pos.z, -t.render_y, -t.render_x))
        for tile in sorted_tiles_top_first:
            if tile.contains_point(mouse_pos[0], mouse_pos[1]):
                if tile.is_free(self.tiles_dict):
                    self.hovered_tile = tile
                break
        
        # Draw tiles with depth information and hover state
        for tile in sorted_tiles:
            is_hovered = (tile == self.hovered_tile)
            tile.draw(self.screen, self.tiles_dict, is_hovered)
        
    def draw_level_complete(self):
        """Draw level complete screen"""
        self.screen.blit(self.main_background, (0, 0))
        
        # Overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(overlay, OVERLAY, overlay.get_rect())
        self.screen.blit(overlay, (0, 0))
        
        # Congratulations with background
        congrats = self.title_font.render("LEVEL COMPLETE!", True, (255, 215, 0))
        congrats_shadow = self.title_font.render("LEVEL COMPLETE!", True, (0, 0, 0))
        
        if self.text_background_original:
            congrats_bg_width = congrats.get_width() + 120
            congrats_bg_height = congrats.get_height() + 40
            congrats_bg = pygame.transform.smoothscale(self.text_background_original, (congrats_bg_width, congrats_bg_height))
            congrats_bg_x = WINDOW_WIDTH // 2 - congrats_bg_width // 2
            self.screen.blit(congrats_bg, (congrats_bg_x, 130))
            self.screen.blit(congrats_shadow, (WINDOW_WIDTH // 2 - congrats.get_width() // 2 + 3, 153))
            self.screen.blit(congrats, (WINDOW_WIDTH // 2 - congrats.get_width() // 2, 150))
        else:
            self.screen.blit(congrats_shadow, (WINDOW_WIDTH // 2 - congrats.get_width() // 2 + 3, 153))
            self.screen.blit(congrats, (WINDOW_WIDTH // 2 - congrats.get_width() // 2, 150))
        
        # Stats with backgrounds - use Yusei font for all with shadows
        stats_data = [
            ("Time: ", f"{self.elapsed_time} seconds"),
            ("Matches: ", f"{self.matches_made}"),
            ("Level: ", self.levels[self.current_level_index].name)
        ]
        y = 300
        for label, value in stats_data:
            label_text = self.game_font.render(label, True, TEXT_WHITE)
            label_shadow = self.game_font.render(label, True, (0, 0, 0))
            label_shadow.set_alpha(200)
            value_text = self.game_font.render(value, True, TEXT_WHITE)
            value_shadow = self.game_font.render(value, True, (0, 0, 0))
            value_shadow.set_alpha(200)
            
            combined_width = label_text.get_width() + value_text.get_width()
            
            # Draw background
            if self.text_background_original:
                stat_bg_width = combined_width + 100
                stat_bg_height = max(label_text.get_height(), value_text.get_height()) + 30
                stat_bg = pygame.transform.smoothscale(self.text_background_original, (stat_bg_width, stat_bg_height))
                stat_bg_x = WINDOW_WIDTH // 2 - stat_bg_width // 2
                self.screen.blit(stat_bg, (stat_bg_x, y - 10))
            
            # Draw text with shadows
            start_x = WINDOW_WIDTH // 2 - combined_width // 2
            self.screen.blit(label_shadow, (start_x + 2, y + 2))
            self.screen.blit(label_text, (start_x, y))
            self.screen.blit(value_shadow, (start_x + label_text.get_width() + 2, y + 2))
            self.screen.blit(value_text, (start_x + label_text.get_width(), y))
            y += 70
        
        # Buttons
        if self.current_level_index < len(self.levels) - 1:
            self.next_level_button.draw(self.screen, self.button_font, self.button_font)
        self.retry_button.draw(self.screen, self.button_font, self.button_font)
        self.menu_button.draw(self.screen, self.small_font, self.small_font)
        
    def draw_game_over(self):
        """Draw game over screen"""
        self.screen.blit(self.main_background, (0, 0))
        
        # Overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(overlay, OVERLAY, overlay.get_rect())
        self.screen.blit(overlay, (0, 0))
        
        # Game Over with background
        title = self.title_font.render("NO MORE MOVES!", True, (255, 100, 100))
        title_shadow = self.title_font.render("NO MORE MOVES!", True, (0, 0, 0))
        
        if self.text_background_original:
            title_bg_width = title.get_width() + 120
            title_bg_height = title.get_height() + 40
            title_bg = pygame.transform.smoothscale(self.text_background_original, (title_bg_width, title_bg_height))
            title_bg_x = WINDOW_WIDTH // 2 - title_bg_width // 2
            self.screen.blit(title_bg, (title_bg_x, 180))
            self.screen.blit(title_shadow, (WINDOW_WIDTH // 2 - title.get_width() // 2 + 3, 203))
            self.screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 200))
        else:
            self.screen.blit(title_shadow, (WINDOW_WIDTH // 2 - title.get_width() // 2 + 3, 203))
            self.screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 200))
        
        # Message with background and shadow
        message = self.game_font.render("Try again or choose a different level", True, TEXT_WHITE)
        message_shadow = self.game_font.render("Try again or choose a different level", True, (0, 0, 0))
        message_shadow.set_alpha(200)
        
        if self.text_background_original:
            msg_bg_width = message.get_width() + 100
            msg_bg_height = message.get_height() + 30
            msg_bg = pygame.transform.smoothscale(self.text_background_original, (msg_bg_width, msg_bg_height))
            msg_bg_x = WINDOW_WIDTH // 2 - msg_bg_width // 2
            self.screen.blit(msg_bg, (msg_bg_x, 310))
        
        msg_x = WINDOW_WIDTH // 2 - message.get_width() // 2
        self.screen.blit(message_shadow, (msg_x + 2, 322))
        self.screen.blit(message, (msg_x, 320))
        
        # Buttons
        self.retry_button.draw(self.screen, self.button_font, self.button_font)
        self.menu_button.draw(self.screen, self.small_font, self.small_font)
        
    def run(self):
        """Main game loop"""
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    
                # Handle events based on game state
                if self.game_state == HOME_SCREEN:
                    if self.play_button.handle_event(event):
                        self.game_state = LEVEL_SELECT
                        
                elif self.game_state == LEVEL_SELECT:
                    if self.back_button.handle_event(event):
                        self.game_state = HOME_SCREEN
                    for i, btn in enumerate(self.level_buttons):
                        if btn.handle_event(event):
                            self.start_level(i)
                            
                elif self.game_state == PLAYING:
                    if self.back_button.handle_event(event):
                        self.game_state = LEVEL_SELECT
                    elif self.hint_button.handle_event(event):
                        self.show_hint()
                    elif self.undo_button.handle_event(event):
                        self.undo_move()
                    elif self.mix_button.handle_event(event):
                        self.mix_tiles()
                    elif self.restart_button.handle_event(event):
                        self.start_level(self.current_level_index)
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        # Check tile clicks (reverse order for top tiles first)
                        sorted_tiles = sorted(self.tiles, key=lambda t: (-t.pos.z, -t.render_y, -t.render_x))
                        for tile in sorted_tiles:
                            if tile.contains_point(event.pos[0], event.pos[1]):
                                self.handle_tile_click(tile)
                                break
                                
                elif self.game_state == LEVEL_COMPLETE:
                    if self.current_level_index < len(self.levels) - 1:
                        if self.next_level_button.handle_event(event):
                            self.start_level(self.current_level_index + 1)
                    if self.retry_button.handle_event(event):
                        self.start_level(self.current_level_index)
                    if self.menu_button.handle_event(event):
                        self.game_state = LEVEL_SELECT
                        
                elif self.game_state == GAME_OVER:
                    if self.retry_button.handle_event(event):
                        self.start_level(self.current_level_index)
                    if self.menu_button.handle_event(event):
                        self.game_state = LEVEL_SELECT
            
            # Draw current screen
            if self.game_state == HOME_SCREEN:
                self.draw_home_screen()
            elif self.game_state == LEVEL_SELECT:
                self.draw_level_select()
            elif self.game_state == PLAYING:
                self.draw_game_screen()
            elif self.game_state == LEVEL_COMPLETE:
                self.draw_level_complete()
            elif self.game_state == GAME_OVER:
                self.draw_game_over()
                
            pygame.display.flip()
            self.clock.tick(FPS)
            
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    game = MahjongGame()
    game.run()
