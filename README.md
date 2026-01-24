# 🀄 Mahjong Solitaire - Character Edition

A stunning 3D Mahjong Solitaire game with custom character tiles and multiple levels!

## ✨ Features

- 🎮 **Classic Mahjong Solitaire gameplay** - Match tiles on top of the pile
- 🏗️ **3D layered tiles** - Beautiful depth effect with proper stacking
- 🎯 **3 Unique Levels** - Pyramid, Temple, and Dragon layouts
- ⏱️ **Timer & Stats** - Track your performance
- 💡 **Hint System** - Get help when stuck
- 🎨 **Modern Mobile UI** - Gorgeous gradients, shadows, and animations
- 🌟 **12 Custom Characters** - All your favorite characters as tiles
- 🔄 **Restart Anytime** - Try again to beat your time

## 🎮 How to Play

### Installation

1. Make sure you have Python 3.7+ installed
2. Install pygame-ce (works with Python 3.14):

```bash
pip install pygame-ce
```

Or use the requirements file:

```bash
pip install -r requirements.txt
```

### Running the Game

```bash
python mahjong_game.py
```

## 🕹️ Game Rules

1. **Select two matching tiles** that are **free** (not blocked)
2. A tile is **free** if:
   - No tile is on top of it
   - At least one side (left or right) is open
3. Match all tiles to clear the level
4. Use hints if you get stuck
5. Complete all 3 levels!

## 🎯 Levels

### Level 1: Pyramid (Easy)
Classic pyramid shape - perfect for learning the mechanics

### Level 2: Temple (Medium)
Complex temple structure with columns and courtyards

### Level 3: Dragon (Hard)
Challenging serpentine dragon pattern with multiple layers

## 🎨 Game Features

### Main Menu
- Beautiful gradient backgrounds
- Smooth button animations
- Clear instructions

### Level Selection
- Choose any of the 3 levels
- See difficulty ratings
- Return to menu anytime

### Gameplay
- 3D tile rendering with shadows
- Highlight selected tiles
- Show available moves
- Timer and statistics
- Hint button reveals a matching pair
- Restart button to try again

### Win Screen
- Celebration message
- Time and match statistics
- Progress to next level
- Retry current level

## 🎲 Characters

The game features 12 unique characters:
- 🧑 Cas
- 👩 Cherie  
- 🧔 Giuseppe
- 🧑‍🦱 Jack
- 👩‍🦱 Jackie
- 🧑‍🦰 Jason
- 👨 Joe
- 👩‍🦰 Mina
- 🤴 Prince
- 👨‍🏫 Prof J
- 🧑‍🎓 Spencer
- 🧑‍💼 Trace

## 🎮 Controls

- **Mouse Click**: Select tiles, navigate menus
- **💡 Hint Button**: Show a matching pair
- **🔄 Restart Button**: Start level over
- **← Back Button**: Return to previous screen

## 🛠️ Technical Details

- **Engine**: Pygame CE (Community Edition)
- **Resolution**: 1400x900
- **3D Effect**: Layered rendering with depth offsets
- **Tile Logic**: Advanced blocking detection algorithm
- **UI**: Modern gradient-based design with smooth animations
- **Layout System**: Procedural level generation

## 📁 Project Structure

```
mahjong-minigame/
├── src/
│   └── characters/          # Character tile images (12 PNG files)
├── mahjong_game.py          # Main game file
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## 🎯 Tips & Strategy

1. **Look for pairs at the edges first** - They're usually easier to free
2. **Work from top to bottom** - Clear upper layers to access lower ones
3. **Use hints wisely** - They help you learn patterns
4. **Plan ahead** - Try not to trap matching tiles
5. **Take your time** - It's about completing, not speed!

## 🐛 Troubleshooting

### "No module named 'pygame'"
If using Python 3.12+, install pygame-ce instead:
```bash
pip install pygame-ce
```

### Game won't start
Make sure all character images are in `src/characters/` folder

Enjoy matching! 🀄✨
