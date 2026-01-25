import pygame
import random
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional
try:
    from PIL import Image
except Exception:
    Image = None

# Initialize Pygame
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
try:
    pygame.mixer.init()
except Exception as e:
    print(f"Audio init failed: {e}")

# Constants
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
TILE_WIDTH = 80
TILE_HEIGHT = 100
DOMINO_INSET_X = 0
DOMINO_INSET_Y = 0
DOMINO_WIDTH = TILE_WIDTH - (DOMINO_INSET_X * 2)
DOMINO_HEIGHT = TILE_HEIGHT - (DOMINO_INSET_Y * 2)
DOMINO_SPACING_PAD_X = -35  # tighten horizontal gap
DOMINO_SPACING_PAD_Y = -20  # vertical spacing (already good)
GRID_STEP_X = DOMINO_WIDTH + DOMINO_SPACING_PAD_X
GRID_STEP_Y = DOMINO_HEIGHT + DOMINO_SPACING_PAD_Y
CAST_SHADOW_ALPHA = 110
CAST_SHADOW_OFFSET_X = 4
CAST_SHADOW_OFFSET_Y = 4
LAYER_OFFSET_X = 6
LAYER_OFFSET_Y = 5
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
        self.mask = None
        self.mask_surface = None
        self.mask_outline = []
        self.is_selected = False
        self.is_hint = False
        self.render_x = 0
        self.render_y = 0
        self.animation_offset = 0
        self.shake_offset_x = 0
        self.shake_time = 0
        self.refresh_mask()

    def refresh_mask(self):
        """Rebuild mask data after image changes."""
        if not self.image:
            self.mask = None
            self.mask_surface = None
            self.mask_outline = []
            return
        self.mask = pygame.mask.from_surface(self.image)
        self.mask_surface = self.mask.to_surface(
            setcolor=(255, 255, 255, 255),
            unsetcolor=(0, 0, 0, 0)
        )
        self.mask_outline = self.mask.outline()

    def has_adjacent_stack(self, tiles_dict: dict) -> bool:
        """Check if any neighboring tile is on a higher layer."""
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                pos = TilePosition(self.pos.x + dx, self.pos.y + dy, self.pos.z + 1)
                if pos in tiles_dict:
                    return True
        return False
        
    def get_screen_pos(self, offset_x: int, offset_y: int) -> Tuple[int, int]:
        """Calculate screen position with 3D offset"""
        # Space based on the actual visible domino so tiles touch cleanly
        spacing_x = GRID_STEP_X
        spacing_y = GRID_STEP_Y
        
        base_x = int(offset_x + self.pos.x * spacing_x)
        base_y = int(offset_y + self.pos.y * spacing_y)
        
        # 3D depth effect - offset to the RIGHT and UP for stacked tiles
        depth_offset_x = self.pos.z * LAYER_OFFSET_X
        depth_offset_y = self.pos.z * LAYER_OFFSET_Y
        
        self.render_x = int(base_x - depth_offset_x)
        self.render_y = int(base_y - depth_offset_y)
        
        return self.render_x, self.render_y
    
    def is_blocked_left(self, tiles_dict: dict) -> bool:
        """Check if tile is blocked on the left - adjacent tile on same layer"""
        # A tile at this layer directly to the left
        left_pos = TilePosition(self.pos.x - 1, self.pos.y, self.pos.z)
        if left_pos in tiles_dict:
            return True
        return False
    
    def is_blocked_right(self, tiles_dict: dict) -> bool:
        """Check if tile is blocked on the right - adjacent tile on same layer"""
        # A tile at this layer directly to the right
        right_pos = TilePosition(self.pos.x + 1, self.pos.y, self.pos.z)
        if right_pos in tiles_dict:
            return True
        return False
    
    def is_blocked_top(self, tiles_dict: dict) -> bool:
        """Check if tile has another tile on top covering it"""
        # Check if any tile one layer above overlaps with this tile's area
        # A tile above must overlap to cover - check a 3x3 grid around our position
        top_pos = TilePosition(self.pos.x, self.pos.y, self.pos.z + 1)
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
    
    def shake(self):
        """Trigger a shake animation for unavailable tile"""
        self.shake_time = pygame.time.get_ticks()
    
    def update_shake(self):
        """Update shake animation"""
        if self.shake_time > 0:
            elapsed = pygame.time.get_ticks() - self.shake_time
            if elapsed < 300:  # Shake for 300ms
                # Create shake effect - oscillate back and forth
                progress = elapsed / 300.0
                self.shake_offset_x = int(10 * (1 - progress) * (1 if (elapsed // 50) % 2 == 0 else -1))
            else:
                self.shake_offset_x = 0
                self.shake_time = 0
    
    def draw(self, screen: pygame.Surface, tiles_dict: dict = None, is_hovered: bool = False, max_z: int = 0):
        """Draw the domino tile - just the image"""
        self.update_shake()
        
        x, y = self.render_x + self.shake_offset_x, self.render_y
        y += self.animation_offset
        
        # Check if tile is free (clickable)
        is_free = tiles_dict is None or self.is_free(tiles_dict)
        
        # Actual domino dimensions (accounting for transparent padding)
        domino_width = DOMINO_WIDTH
        domino_height = DOMINO_HEIGHT
        domino_x = x + DOMINO_INSET_X
        domino_y = y + DOMINO_INSET_Y
        
        # Draw green glow for hovered usable tiles - mask to domino shape
        if is_hovered and is_free and self.mask_outline:
            glow_surf = pygame.Surface(self.image.get_size(), pygame.SRCALPHA)
            for width, alpha in [(8, 40), (6, 70), (4, 110)]:
                pygame.draw.lines(glow_surf, (50, 255, 100, alpha), True, self.mask_outline, width)
            screen.blit(glow_surf, (x, y))
        
        # Draw the domino image directly - NO greyscale, always full color
        if self.image:
            # Shadows for depth readability (masked to the domino shape)
            if self.mask_surface:
                # Lower tiles get a bit more shadow to separate layers visually
                depth_factor = max(0, max_z - self.pos.z)
                base_alpha = 40
                extra_alpha = min(depth_factor * 12, 80)
                shadow_alpha = base_alpha + extra_alpha
                shadow = pygame.Surface(self.image.get_size(), pygame.SRCALPHA)
                shadow.fill((0, 0, 0, shadow_alpha))
                shadow.blit(self.mask_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                screen.blit(shadow, (x + 2, y + 2))

            image_rect = self.image.get_rect(topleft=(x, y))
            screen.blit(self.image, image_rect)
            
            # Grey shade for tiles that cannot be pressed (mask to shape)
            if tiles_dict is not None and not is_free and self.mask_surface:
                shade = pygame.Surface(self.image.get_size(), pygame.SRCALPHA)
                shade.fill((0, 0, 0, 70))
                shade.blit(self.mask_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                screen.blit(shade, (x, y))

            
            # Subtle top-edge highlight for stacked tiles
            if self.pos.z > 0 and self.mask_outline:
                highlight = pygame.Surface(self.image.get_size(), pygame.SRCALPHA)
                pygame.draw.lines(highlight, (255, 255, 255, 90), True, self.mask_outline, 2)
                screen.blit(highlight, (x, y - 1))

            # Draw gold border for selected tiles - masked to domino outline
            if self.is_selected and self.mask_outline:
                border_surf = pygame.Surface(self.image.get_size(), pygame.SRCALPHA)
                pygame.draw.lines(border_surf, (255, 215, 0, 220), True, self.mask_outline, 4)
                screen.blit(border_surf, (x, y))
            elif self.is_hint and self.mask_outline:
                border_surf = pygame.Surface(self.image.get_size(), pygame.SRCALPHA)
                pygame.draw.lines(border_surf, (50, 255, 100, 220), True, self.mask_outline, 4)
                screen.blit(border_surf, (x, y))
    
    def contains_point(self, px: int, py: int) -> bool:
        """Check if point is inside tile"""
        if not (self.render_x <= px <= self.render_x + TILE_WIDTH and
                self.render_y <= py <= self.render_y + TILE_HEIGHT):
            return False
        if not self.mask:
            return True
        local_x = int(px - self.render_x)
        local_y = int(py - self.render_y)
        if local_x < 0 or local_y < 0 or local_x >= TILE_WIDTH or local_y >= TILE_HEIGHT:
            return False
        return self.mask.get_at((local_x, local_y)) == 1

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
                if self.game and hasattr(self.game, "play_sound"):
                    self.game.play_sound(self.game.button_press_sound)
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
        self.load_sounds()
        
        # Levels with updated names
        self.levels = [
            Level("Turtle", self.create_pyramid_layout, "Easy"),
            Level("Temple", self.create_temple_layout, "Medium"),
            Level("Diamond Peaks", self.create_dragon_layout, "Hard")
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
        
        # End screen buttons - larger buttons with smaller text
        self.next_level_button = Button(center_x - 320, 500, 280, 80, "NEXT LEVEL", BUTTON_PRIMARY, BUTTON_PRIMARY_HOVER, self)
        self.retry_button = Button(center_x + 40, 500, 280, 80, "RETRY", BUTTON_SECONDARY, BUTTON_PRIMARY_HOVER, self)
        self.menu_button = Button(center_x - 140, 610, 280, 70, "MENU", BUTTON_SECONDARY, BUTTON_PRIMARY_HOVER, self)

        # Mute button (top-right, all screens)
        self.mute_button = Button(WINDOW_WIDTH - 180, 20, 140, 50, "MUTE", BUTTON_SECONDARY, BUTTON_PRIMARY_HOVER, self)
        
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

    def load_sounds(self):
        """Load sound effects"""
        self.audio_enabled = pygame.mixer.get_init() is not None
        self.is_muted = False
        self.music_volume = 0.3
        self.sound_volume = 0.7
        self.domino_click1_sound = None
        self.domino_click2_sound = None
        self.incorrect_domino_sound = None
        self.correct_domino_sound = None
        self.level_win_sound = None
        self.button_press_sound = None

        sounds_path = Path("src/sounds")
        if not self.audio_enabled:
            return

        def load_sound(*paths: Path):
            for path in paths:
                if path and path.exists():
                    try:
                        sfx = pygame.mixer.Sound(str(path))
                        sfx.set_volume(self.sound_volume)
                        return sfx
                    except Exception as e:
                        print(f"Error loading sound {path.name}: {e}")
            return None

        self.domino_click1_sound = load_sound(sounds_path / "domino_click1.wav")
        self.domino_click2_sound = load_sound(sounds_path / "domino_click2.wav")
        self.incorrect_domino_sound = load_sound(sounds_path / "incorrect_domino.wav")
        self.correct_domino_sound = load_sound(sounds_path / "correct_domino.wav")
        self.level_win_sound = load_sound(sounds_path / "level_win.wav", sounds_path / "level_win.ogg", sounds_path / "level_win.mp4")
        self.button_press_sound = load_sound(sounds_path / "button_press.wav", sounds_path / "button_press.ogg", sounds_path / "button_press.mp4")

        # Load background music with fallbacks
        for music_path in (
            sounds_path / "main_music.mp3",
            sounds_path / "main_music.ogg",
            sounds_path / "main_music.wav",
        ):
            if music_path.exists():
                try:
                    pygame.mixer.music.load(str(music_path))
                    pygame.mixer.music.set_volume(self.music_volume)
                    pygame.mixer.music.play(-1)
                except Exception as e:
                    print(f"Error loading music {music_path.name}: {e}")
                break

    def play_sound(self, sound):
        if sound and not self.is_muted:
            try:
                sound.play()
            except Exception:
                pass

    def toggle_mute(self):
        if not self.audio_enabled:
            return
        self.is_muted = not self.is_muted
        if self.is_muted:
            pygame.mixer.music.set_volume(0.0)
            for s in (self.domino_click1_sound, self.domino_click2_sound, self.incorrect_domino_sound, self.correct_domino_sound, self.level_win_sound, self.button_press_sound):
                if s:
                    s.set_volume(0.0)
        else:
            pygame.mixer.music.set_volume(self.music_volume)
            for s in (self.domino_click1_sound, self.domino_click2_sound, self.incorrect_domino_sound, self.correct_domino_sound, self.level_win_sound, self.button_press_sound):
                if s:
                    s.set_volume(self.sound_volume)

    def draw_mute_button(self):
        self.mute_button.text = "UNMUTE" if self.is_muted else "MUTE"
        self.mute_button.draw(self.screen, self.tiny_font, self.tiny_font)
    
    def load_dominos(self):
        """Load domino images from dominos folder"""
        self.domino_images = []
        dominos_path = Path("src/dominos")
        
        # Load the new domino images in a fixed order to keep IDs consistent
        ordered_names = [
            "bullyDomino.png",
            "casDomino.png",
            "cherieDomino.png",
            "cyborgDomino.png",
            "giuseppeDomino.png",
            "jackDomino.png",
            "jackieDomino.png",
            "jasonDomino.png",
            "minaDomino.png",
            "princeDomino.png",
            "spencerDomino.png",
            "traceDomino.png",
        ]
        domino_files = []
        for name in ordered_names:
            path = dominos_path / name
            if not path.exists():
                print(f"Missing domino image: {name}")
            else:
                domino_files.append(path)

        for domino_file in domino_files:
            try:
                image = self._prepare_domino_image(domino_file)

                self.domino_images.append(image)
                print(f"Loaded {domino_file.name}")
            except Exception as e:
                print(f"Error loading {domino_file}: {e}")
        
        print(f"Loaded {len(self.domino_images)} domino images")

    def _prepare_domino_image(self, domino_file: Path) -> pygame.Surface:
        """Resize to standard tile size without cropping."""
        if Image is not None:
            pil_image = Image.open(domino_file).convert("RGBA")
            pil_image = pil_image.resize((TILE_WIDTH, TILE_HEIGHT), Image.LANCZOS)
            mode = pil_image.mode
            size = pil_image.size
            data = pil_image.tobytes()
            return pygame.image.fromstring(data, size, mode).convert_alpha()
        else:
            image = pygame.image.load(str(domino_file)).convert_alpha()
            return pygame.transform.smoothscale(image, (TILE_WIDTH, TILE_HEIGHT))

    def create_pyramid_layout(self) -> List[TilePosition]:
        """Easy level - Turtle shape (~90 tiles, 3 layers)"""
        positions = []
        occupied = set()
        
        def add_tile(tx: int, ty: int, z: int):
            key = (tx, ty, z)
            if key not in occupied:
                occupied.add(key)
                positions.append(TilePosition(tx, ty, z))
        
        def add_rect(x0: int, y0: int, w: int, h: int, z: int):
            for ty in range(y0, y0 + h):
                for tx in range(x0, x0 + w):
                    add_tile(tx, ty, z)
        
        # Core turtle shell (84 tiles)
        # Layer 0: 9x6
        add_rect(0, 0, 9, 6, 0)
        # Layer 1: 6x4 centered
        add_rect(1, 1, 6, 4, 1)
        # Layer 2: 3x2 centered
        add_rect(3, 2, 3, 2, 2)
        
        # Add side legs to reach 90 tiles (3 per side)
        add_rect(-1, 2, 1, 3, 0)
        add_rect(9, 2, 1, 3, 0)
        
        return positions
    
    def create_temple_layout(self) -> List[TilePosition]:
        """Medium level - Temple layout (~88-90 tiles, 3 layers)"""
        layout = [
            # === LAYER 0 (Bottom) ===
            # Top row
            (0, 0, 0), (2, 0, 0), (4, 0, 0), (6, 0, 0), (8, 0, 0), (10, 0, 0), (12, 0, 0), (14, 0, 0),
            # Second row
            (1, 1, 0), (3, 1, 0), (5, 1, 0), (7, 1, 0), (9, 1, 0), (11, 1, 0), (13, 1, 0),
            # Third row (main body)
            (0, 2, 0), (1, 2, 0), (2, 2, 0), (3, 2, 0), (4, 2, 0), (5, 2, 0), (6, 2, 0),
            (7, 2, 0), (8, 2, 0), (9, 2, 0), (10, 2, 0), (11, 2, 0), (12, 2, 0), (13, 2, 0),
            (14, 2, 0),
            # Fourth row (main body)
            (1, 3, 0), (2, 3, 0), (3, 3, 0), (4, 3, 0), (5, 3, 0), (6, 3, 0), (7, 3, 0),
            (8, 3, 0), (9, 3, 0), (10, 3, 0), (11, 3, 0), (12, 3, 0), (13, 3, 0),
            # Fifth row (main body)
            (2, 4, 0), (3, 4, 0), (4, 4, 0), (5, 4, 0), (6, 4, 0), (7, 4, 0),
            (8, 4, 0), (9, 4, 0), (10, 4, 0), (11, 4, 0), (12, 4, 0),
            # Sixth row
            (3, 5, 0), (4, 5, 0), (5, 5, 0), (6, 5, 0), (7, 5, 0), (8, 5, 0),
            (9, 5, 0), (10, 5, 0), (11, 5, 0),
            # Bottom row
            (0, 6, 0), (2, 6, 0), (4, 6, 0), (6, 6, 0), (8, 6, 0), (10, 6, 0), (12, 6, 0),
            (14, 6, 0),

            # === LAYER 1 (Middle) ===
            (2, 1, 1), (3, 1, 1), (4, 1, 1), (5, 1, 1), (6, 1, 1), (7, 1, 1), (8, 1, 1),
            (9, 1, 1), (10, 1, 1), (11, 1, 1), (12, 1, 1),
            (2, 2, 1), (3, 2, 1), (4, 2, 1), (5, 2, 1), (6, 2, 1), (7, 2, 1), (8, 2, 1),
            (9, 2, 1), (10, 2, 1), (11, 2, 1), (12, 2, 1),
            (2, 3, 1), (3, 3, 1), (4, 3, 1), (5, 3, 1), (6, 3, 1), (7, 3, 1), (8, 3, 1),
            (9, 3, 1), (10, 3, 1), (11, 3, 1), (12, 3, 1),
            (2, 4, 1), (3, 4, 1), (4, 4, 1), (5, 4, 1), (6, 4, 1), (7, 4, 1), (8, 4, 1),
            (9, 4, 1), (10, 4, 1), (11, 4, 1), (12, 4, 1),
            (4, 5, 1), (5, 5, 1), (6, 5, 1), (7, 5, 1), (8, 5, 1), (9, 5, 1), (10, 5, 1),

            # === LAYER 2 (Top) ===
            (6, 2, 2), (7, 2, 2), (6, 3, 2), (7, 3, 2),
        ]

        return [TilePosition(x, y, z) for x, y, z in layout]
    
    def create_dragon_layout(self) -> List[TilePosition]:
        """Hard level - Double Pyramid/Diamond layout (~88-92 tiles, 5 layers)"""
        layout = [
            # === LAYER 0 (Bottom/Base) ===
            (6, 0, 0), (7, 0, 0), (8, 0, 0),
            (4, 1, 0), (5, 1, 0), (6, 1, 0), (7, 1, 0), (8, 1, 0), (9, 1, 0), (10, 1, 0),
            (2, 2, 0), (3, 2, 0), (4, 2, 0), (5, 2, 0), (6, 2, 0), (7, 2, 0), (8, 2, 0),
            (9, 2, 0), (10, 2, 0), (11, 2, 0), (12, 2, 0),
            (1, 3, 0), (2, 3, 0), (3, 3, 0), (4, 3, 0), (5, 3, 0), (6, 3, 0), (7, 3, 0),
            (8, 3, 0), (9, 3, 0), (10, 3, 0), (11, 3, 0), (12, 3, 0), (13, 3, 0),
            (0, 4, 0), (1, 4, 0), (2, 4, 0), (3, 4, 0), (4, 4, 0), (5, 4, 0), (6, 4, 0),
            (7, 4, 0), (8, 4, 0), (9, 4, 0), (10, 4, 0), (11, 4, 0), (12, 4, 0),
            (13, 4, 0), (14, 4, 0),
            (1, 5, 0), (2, 5, 0), (3, 5, 0), (4, 5, 0), (5, 5, 0), (6, 5, 0), (7, 5, 0),
            (8, 5, 0), (9, 5, 0), (10, 5, 0), (11, 5, 0), (12, 5, 0), (13, 5, 0),
            (2, 6, 0), (3, 6, 0), (4, 6, 0), (5, 6, 0), (6, 6, 0), (7, 6, 0), (8, 6, 0),
            (9, 6, 0), (10, 6, 0), (11, 6, 0), (12, 6, 0),
            (4, 7, 0), (5, 7, 0), (6, 7, 0), (7, 7, 0), (8, 7, 0), (9, 7, 0), (10, 7, 0),
            (6, 8, 0), (7, 8, 0), (8, 8, 0),

            # === LAYER 1 (First Inner Layer) ===
            (5, 1, 1), (6, 1, 1), (7, 1, 1), (8, 1, 1), (9, 1, 1),
            (3, 2, 1), (4, 2, 1), (5, 2, 1), (6, 2, 1), (7, 2, 1), (8, 2, 1), (9, 2, 1),
            (10, 2, 1), (11, 2, 1),
            (2, 3, 1), (3, 3, 1), (4, 3, 1), (5, 3, 1), (6, 3, 1), (7, 3, 1), (8, 3, 1),
            (9, 3, 1), (10, 3, 1), (11, 3, 1), (12, 3, 1),
            (2, 4, 1), (3, 4, 1), (4, 4, 1), (5, 4, 1), (6, 4, 1), (7, 4, 1), (8, 4, 1),
            (9, 4, 1), (10, 4, 1), (11, 4, 1), (12, 4, 1),
            (2, 5, 1), (3, 5, 1), (4, 5, 1), (5, 5, 1), (6, 5, 1), (7, 5, 1), (8, 5, 1),
            (9, 5, 1), (10, 5, 1), (11, 5, 1), (12, 5, 1),
            (3, 6, 1), (4, 6, 1), (5, 6, 1), (6, 6, 1), (7, 6, 1), (8, 6, 1), (9, 6, 1),
            (10, 6, 1), (11, 6, 1),
            (5, 7, 1), (6, 7, 1), (7, 7, 1), (8, 7, 1), (9, 7, 1),

            # === LAYER 2 (Second Inner Layer) ===
            (4, 2, 2), (5, 2, 2), (6, 2, 2), (7, 2, 2), (8, 2, 2), (9, 2, 2), (10, 2, 2),
            (4, 3, 2), (5, 3, 2), (6, 3, 2), (7, 3, 2), (8, 3, 2), (9, 3, 2), (10, 3, 2),
            (4, 4, 2), (5, 4, 2), (6, 4, 2), (7, 4, 2), (8, 4, 2), (9, 4, 2), (10, 4, 2),
            (4, 5, 2), (5, 5, 2), (6, 5, 2), (7, 5, 2), (8, 5, 2), (9, 5, 2), (10, 5, 2),
            (4, 6, 2), (5, 6, 2), (6, 6, 2), (7, 6, 2), (8, 6, 2), (9, 6, 2), (10, 6, 2),

            # === LAYER 3 (Pre-Peak Layer) ===
            (5, 3, 3), (6, 3, 3), (7, 3, 3), (8, 3, 3), (9, 3, 3),
            (5, 4, 3), (6, 4, 3), (7, 4, 3), (8, 4, 3), (9, 4, 3),
            (5, 5, 3), (6, 5, 3), (7, 5, 3), (8, 5, 3), (9, 5, 3),

            # === LAYER 4 (Twin Peaks) ===
            (5, 3, 4), (5, 4, 4),
            (9, 3, 4), (9, 4, 4),
        ]

        return [TilePosition(x, y, z) for x, y, z in layout]
    
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
            tile.refresh_mask()
            tile.is_selected = False
            tile.is_hint = False
        
        self.selected_tile = None
        self.mixes_left -= 1
        self.update_moves_count()
        
    def handle_tile_click(self, tile: Tile):
        """Handle clicking on a tile"""
        # Check if tile is free first
        if not tile.is_free(self.tiles_dict):
            # Tile is blocked - shake it and deselect any selected tile
            tile.shake()
            self.play_sound(self.incorrect_domino_sound)
            if self.selected_tile:
                self.selected_tile.is_selected = False
                self.selected_tile = None
            return
        
        # Clear hints
        for t in self.tiles:
            t.is_hint = False
        
        if self.selected_tile is None:
            # Select first tile
            tile.is_selected = True
            self.selected_tile = tile
            self.play_sound(self.domino_click1_sound)
        elif self.selected_tile == tile:
            # Deselect
            tile.is_selected = False
            self.selected_tile = None
        else:
            # Try to match
            self.play_sound(self.domino_click2_sound)
            if self.selected_tile.character_id == tile.character_id:
                self.play_sound(self.correct_domino_sound)
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
                    self.play_sound(self.level_win_sound)
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
            
            # Calculate pixel bounds based on actual spacing and layer offsets
            spacing_x = GRID_STEP_X
            spacing_y = GRID_STEP_Y
            min_render_x = float("inf")
            max_render_x = float("-inf")
            min_render_y = float("inf")
            max_render_y = float("-inf")
            for tile in self.tiles:
                render_x = tile.pos.x * spacing_x + (tile.pos.z * LAYER_OFFSET_X)
                render_y = tile.pos.y * spacing_y + (tile.pos.z * LAYER_OFFSET_Y)
                min_render_x = min(min_render_x, render_x)
                min_render_y = min(min_render_y, render_y)
                max_render_x = max(max_render_x, render_x + TILE_WIDTH)
                max_render_y = max(max_render_y, render_y + TILE_HEIGHT)
            
            pixel_width = max_render_x - min_render_x
            pixel_height = max_render_y - min_render_y
            
            # Calculate offsets to center the layout
            offset_x = int((WINDOW_WIDTH - pixel_width) // 2 - min_render_x)
            offset_y = int((WINDOW_HEIGHT - pixel_height) // 2 - min_render_y + 80)  # Extra space for top UI
        else:
            offset_x = WINDOW_WIDTH // 2
            offset_y = WINDOW_HEIGHT // 2
        
        for tile in self.tiles:
            tile.get_screen_pos(offset_x, offset_y)
        
        # Sort tiles for proper rendering (back to front, top-right to bottom-left)
        sorted_tiles = sorted(
            self.tiles,
            key=lambda t: (t.pos.z, t.pos.y + t.pos.x, t.pos.y, t.pos.x)
        )
        
        # Get current mouse position to detect hover
        mouse_pos = pygame.mouse.get_pos()
        self.hovered_tile = None
        
        # Find which tile is being hovered (check top tiles first)
        sorted_tiles_top_first = sorted(
            self.tiles,
            key=lambda t: (-t.pos.z, -(t.pos.y + t.pos.x), -t.pos.y, -t.pos.x)
        )
        for tile in sorted_tiles_top_first:
            if tile.contains_point(mouse_pos[0], mouse_pos[1]):
                if tile.is_free(self.tiles_dict):
                    self.hovered_tile = tile
                break
        
        # Draw tiles with depth information and hover state
        max_z = max(tile.pos.z for tile in self.tiles)
        for tile in sorted_tiles:
            is_hovered = (tile == self.hovered_tile)
            tile.draw(self.screen, self.tiles_dict, is_hovered, max_z)
        
    def draw_level_complete(self):
        """Draw level complete screen"""
        self.screen.blit(self.main_background, (0, 0))
        
        # Overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(overlay, OVERLAY, overlay.get_rect())
        self.screen.blit(overlay, (0, 0))
        
        # Congratulations with background
        congrats = self.subtitle_font.render("LEVEL COMPLETE!", True, TEXT_WHITE)
        congrats_shadow = self.subtitle_font.render("LEVEL COMPLETE!", True, (0, 0, 0))
        
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
            self.next_level_button.draw(self.screen, self.tiny_font, self.tiny_font)
        self.retry_button.draw(self.screen, self.tiny_font, self.tiny_font)
        self.menu_button.draw(self.screen, self.tiny_font, self.tiny_font)
        
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
                    back_clicked = self.back_button.handle_event(event)
                    if back_clicked:
                        self.game_state = HOME_SCREEN
                    else:
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
