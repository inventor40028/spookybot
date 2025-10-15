import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, PreCheckoutQueryHandler
import asyncio
import re
import requests
from io import BytesIO
import random
import pyttsx3
import os
from telegram.ext import CallbackQueryHandler
import tempfile
from datetime import datetime, timedelta, date
from gradio_client import Client, handle_file
from bytez import Bytez
import requests
from io import BytesIO
import json, os, threading, time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import telegram
from random import randint, choice
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.ext import JobQueue
import pytz
import telegram.error
from telegram.helpers import escape_markdown
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv  # Add this import

# Load .env at start
load_dotenv()

executor = ThreadPoolExecutor(max_workers=8)
# ===== CONFIG =====
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
BYTEZ_API_KEY = os.getenv('BYTEZ_API_KEY')

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

print("-> Using gemini-2.0-flash-lite - FAST and RELIABLE!")

# User data storage
user_data = {}
photo_requests = {}
TRANSFORM_COOLDOWN = {}
STORY_COOLDOWN = {} 
RPG_COOLDOWN = {} 
SPOOKY_COOLDOWN = {}
MONSTER_COOLDOWN = {}


# Add this with your other configurations
SCARE_TIERS = {
    0: {"title": "🎃 Spooky Newbie", "color": "🟡"},
    50: {"title": "👻 Ghostly Apprentice", "color": "🟢"},
    100: {"title": "🧛 Vampire Elite", "color": "🔵"},
    200: {"title": "😈 Demon Lord", "color": "🟣"},
    500: {"title": "👑 Horror Monarch", "color": "🟠"},
    1000: {"title": "💀 Ancient Horror", "color": "🔴"}
}
PREMIUM_ANNOUNCE_GROUP = -1003176015564 
GROUP_ACHIEVEMENTS = {
    "transformation_master": {
        "name": "🎭 Transformation Master",
        "description": "Post 10+ different transformations",
        "requirement": 10,
        "type": "transformations"
    },
    "challenge_champ": {
        "name": "⚡ Challenge Champion",
        "description": "Win 5 daily scare challenges",
        "requirement": 5,
        "type": "challenge_wins"
    },
    "community_ghost": {
        "name": "👥 Community Ghost",
        "description": "Help 10+ other members",
        "requirement": 10,
        "type": "members_helped"
    },
    "horror_legend": {
        "name": "🏆 Horror Legend",
        "description": "Reach top 3 on leaderboard",
        "requirement": 1,  # Just need to reach top 3 once
        "type": "leaderboard_top3"
    },
    "fear_conqueror": {
        "name": "🛡️ Fear Conqueror",
        "description": "Complete 50 RPG adventures",
        "requirement": 50,
        "type": "rpg_adventures"
    },
    "monster_creator": {
        "name": "🧌 Monster Creator",
        "description": "Design 5 custom monsters",
        "requirement": 5,
        "type": "monsters_created"
    }
}


def get_user_tier(total_points):
    """Calculate user's tier based on total scare points"""
    sorted_tiers = sorted(SCARE_TIERS.keys(), reverse=True)
    
    for points_threshold in sorted_tiers:
        if total_points >= points_threshold:
            return SCARE_TIERS[points_threshold]
    
    return SCARE_TIERS[0]  # Default to first tier

def track_achievement(user_id, achievement_type, amount=1):
    """Track progress toward achievements"""
    achievements = init_user_achievements(user_id)
    
    # Update progress
    if achievement_type in achievements['progress']:
        achievements['progress'][achievement_type] += amount
    
    # Check for new achievements
    new_achievements = []
    for achievement_id, achievement_data in GROUP_ACHIEVEMENTS.items():
        if (achievement_id not in achievements['unlocked'] and 
            achievement_data['type'] == achievement_type and
            achievements['progress'][achievement_type] >= achievement_data['requirement']):
            
            achievements['unlocked'].append(achievement_id)
            new_achievements.append(achievement_data)
    
    if new_achievements:
        save_user_data()  # Save when achievements are unlocked
    
    return new_achievements


# Update your user data initialization to include achievements
def init_user_achievements(user_id):
    """Initialize achievement tracking for user"""
    if user_id not in user_data:
        user_data[user_id] = {}
    
    if 'achievements' not in user_data[user_id]:
        user_data[user_id]['achievements'] = {
            'unlocked': [],
            'progress': {
                'transformations': 0,
                'stories': 0,
                'challenge_wins': 0,
                'members_helped': 0,
                'leaderboard_top3': 0,
                'rpg_adventures': 0,
                'monsters_created': 0
            }
        }
    
    return user_data[user_id]['achievements']



# Add this with your other configurations at the top
GROUP_LEADERBOARD = {}  # {group_id: {user_id: score}}
user_warnings = {} 

def init_group_leaderboard(group_id):
    """Initialize leaderboard for a group"""
    gid = str(group_id)  # ✅ ensure consistent key type
    if gid not in GROUP_LEADERBOARD:
        GROUP_LEADERBOARD[gid] = {}
    return GROUP_LEADERBOARD[gid]

def update_group_score(group_id, user_id, points, username):
    """Update user's score in group leaderboard"""
    gid = str(group_id)  # ✅ convert to string
    leaderboard = init_group_leaderboard(gid)

    if user_id not in leaderboard:
        leaderboard[user_id] = {'score': 0, 'username': username}

    leaderboard[user_id]['score'] += points
    leaderboard[user_id]['username'] = username  # Update username if changed

    save_group_leaderboard()
    return leaderboard[user_id]['score']

def save_group_leaderboard():
    """Save group leaderboard to file"""
    try:
        with open('group_leaderboard.json', 'w') as f:
            json.dump(GROUP_LEADERBOARD, f)
    except:
        pass

def load_group_leaderboard():
    """Load group leaderboard from file"""
    global GROUP_LEADERBOARD
    try:
        if os.path.exists('group_leaderboard.json'):
            with open('group_leaderboard.json', 'r') as f:
                GROUP_LEADERBOARD = json.load(f)
    except:
        GROUP_LEADERBOARD = {}










def save_cooldowns():
    """Save all cooldowns to file"""
    try:
        cooldown_data = {
            "tictactoe": TICTACTOE_COOLDOWN,
            "gwt": GWT_COOLDOWN,
            "rpg": RPG_COOLDOWN,
            "story": STORY_COOLDOWN,
            "transform": TRANSFORM_COOLDOWN,
            "monster": MONSTER_COOLDOWN,
            "faction": FACTION_COOLDOWN
        }
        # Convert datetime objects to strings
        for cooldown_type, cooldown_dict in cooldown_data.items():
            for user_id, cooldown_time in cooldown_dict.items():
                if hasattr(cooldown_time, 'isoformat'):
                    cooldown_dict[user_id] = cooldown_time.isoformat()
        
        with open(COOLDOWN_FILE, 'w') as f:
            json.dump(cooldown_data, f, indent=2)
        print("💾 Cooldowns saved successfully!")
    except Exception as e:
        print(f"❌ Error saving cooldowns: {e}")

def load_cooldowns():
    """Load all cooldowns from file"""
    global TICTACTOE_COOLDOWN, GWT_COOLDOWN, RPG_COOLDOWN, STORY_COOLDOWN, TRANSFORM_COOLDOWN, MONSTER_COOLDOWN, FACTION_COOLDOWN
    
    try:
        if os.path.exists(COOLDOWN_FILE):
            with open(COOLDOWN_FILE, 'r') as f:
                cooldown_data = json.load(f)
            
            # Convert string timestamps back to datetime objects
            for cooldown_type, cooldown_dict in cooldown_data.items():
                for user_id, cooldown_time_str in cooldown_dict.items():
                    try:
                        cooldown_dict[user_id] = datetime.fromisoformat(cooldown_time_str)
                    except (ValueError, TypeError):
                        # If conversion fails, keep as string or set to old date
                        cooldown_dict[user_id] = datetime.now() - timedelta(days=2)
            
            TICTACTOE_COOLDOWN = cooldown_data.get("tictactoe", {})
            GWT_COOLDOWN = cooldown_data.get("gwt", {})
            RPG_COOLDOWN = cooldown_data.get("rpg", {})
            STORY_COOLDOWN = cooldown_data.get("story", {})
            TRANSFORM_COOLDOWN = cooldown_data.get("transform", {})
            MONSTER_COOLDOWN = cooldown_data.get("monster", {})
            FACTION_COOLDOWN = cooldown_data.get("faction", {})
            
            print(f"📂 Loaded cooldowns: {len(TICTACTOE_COOLDOWN)} TicTacToe, {len(GWT_COOLDOWN)} GWT, {len(RPG_COOLDOWN)} RPG")
    except Exception as e:
        print(f"❌ Error loading cooldowns: {e}")
        # Initialize empty if load fails
        TICTACTOE_COOLDOWN = {}
        GWT_COOLDOWN = {}
        RPG_COOLDOWN = {}
        STORY_COOLDOWN = {}
        TRANSFORM_COOLDOWN = {}
        MONSTER_COOLDOWN = {}
        FACTION_COOLDOWN = {}

# Update your cooldown setting functions to save automatically:
def set_tictactoe_cooldown(user_id):
    """Set Tic-Tac-Toe cooldown and save"""
    TICTACTOE_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()

def set_gwt_cooldown(user_id):
    """Set GWT cooldown and save"""
    GWT_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()

def set_rpg_cooldown(user_id):
    """Set RPG cooldown and save"""
    RPG_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()

def set_story_cooldown(user_id):
    """Set story cooldown and save"""
    STORY_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()

def set_transform_cooldown(user_id):
    """Set transformation cooldown and save"""
    TRANSFORM_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()

def set_monster_cooldown(user_id):
    """Set monster creation cooldown and save"""
    MONSTER_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()

def set_faction_cooldown(user_id):
    """Set faction join cooldown and save"""
    FACTION_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()




















# ===== COOLDOWN PERSISTENCE =====
COOLDOWN_FILE = "cooldowns.json"

# Global cooldown dictionaries
TICTACTOE_COOLDOWN = {}
GWT_COOLDOWN = {}
RPG_COOLDOWN = {}
STORY_COOLDOWN = {}
TRANSFORM_COOLDOWN = {}
MONSTER_COOLDOWN = {}
FACTION_COOLDOWN = {}

def save_cooldowns():
    """Save all cooldowns to file"""
    try:
        cooldown_data = {
            "tictactoe": TICTACTOE_COOLDOWN,
            "gwt": GWT_COOLDOWN,
            "rpg": RPG_COOLDOWN,
            "story": STORY_COOLDOWN,
            "transform": TRANSFORM_COOLDOWN,
            "monster": MONSTER_COOLDOWN,
            "faction": FACTION_COOLDOWN
        }
        # Convert datetime objects to strings
        for cooldown_type, cooldown_dict in cooldown_data.items():
            for user_id, cooldown_time in cooldown_dict.items():
                if hasattr(cooldown_time, 'isoformat'):
                    cooldown_dict[user_id] = cooldown_time.isoformat()
        
        with open(COOLDOWN_FILE, 'w') as f:
            json.dump(cooldown_data, f, indent=2)
        print("💾 Cooldowns saved successfully!")
    except Exception as e:
        print(f"❌ Error saving cooldowns: {e}")

def load_cooldowns():
    """Load all cooldowns from file"""
    global TICTACTOE_COOLDOWN, GWT_COOLDOWN, RPG_COOLDOWN, STORY_COOLDOWN, TRANSFORM_COOLDOWN, MONSTER_COOLDOWN, FACTION_COOLDOWN
    
    try:
        if os.path.exists(COOLDOWN_FILE):
            with open(COOLDOWN_FILE, 'r') as f:
                cooldown_data = json.load(f)
            
            # Convert string timestamps back to datetime objects
            for cooldown_type, cooldown_dict in cooldown_data.items():
                cleaned_dict = {}
                for user_id, cooldown_time_str in cooldown_dict.items():
                    try:
                        # Try to convert string back to datetime
                        if isinstance(cooldown_time_str, str):
                            cleaned_dict[user_id] = datetime.fromisoformat(cooldown_time_str)
                        else:
                            # If it's already a datetime or invalid, use current time minus 2 days
                            cleaned_dict[user_id] = datetime.now() - timedelta(days=2)
                    except (ValueError, TypeError) as e:
                        # If conversion fails, set to old date
                        print(f"❌ Error converting cooldown time for {user_id}: {e}")
                        cleaned_dict[user_id] = datetime.now() - timedelta(days=2)
                
                # Assign the cleaned dictionary
                if cooldown_type == "tictactoe":
                    TICTACTOE_COOLDOWN = cleaned_dict
                elif cooldown_type == "gwt":
                    GWT_COOLDOWN = cleaned_dict
                elif cooldown_type == "rpg":
                    RPG_COOLDOWN = cleaned_dict
                elif cooldown_type == "story":
                    STORY_COOLDOWN = cleaned_dict
                elif cooldown_type == "transform":
                    TRANSFORM_COOLDOWN = cleaned_dict
                elif cooldown_type == "monster":
                    MONSTER_COOLDOWN = cleaned_dict
                elif cooldown_type == "faction":
                    FACTION_COOLDOWN = cleaned_dict
            
            print(f"📂 Loaded cooldowns: {len(TICTACTOE_COOLDOWN)} TicTacToe, {len(GWT_COOLDOWN)} GWT, {len(RPG_COOLDOWN)} RPG")
    except Exception as e:
        print(f"❌ Error loading cooldowns: {e}")
        # Initialize empty if load fails
        TICTACTOE_COOLDOWN = {}
        GWT_COOLDOWN = {}
        RPG_COOLDOWN = {}
        STORY_COOLDOWN = {}
        TRANSFORM_COOLDOWN = {}
        MONSTER_COOLDOWN = {}
        FACTION_COOLDOWN = {}

def get_cooldown_time(user_id, cooldown_dict):
    """Safely get cooldown time, handling both datetime and string types"""
    if user_id not in cooldown_dict:
        return None
    
    cooldown_time = cooldown_dict[user_id]
    
    # If it's a string, try to convert to datetime
    if isinstance(cooldown_time, str):
        try:
            return datetime.fromisoformat(cooldown_time)
        except (ValueError, TypeError):
            # If conversion fails, return old date
            return datetime.now() - timedelta(days=2)
    
    # If it's already datetime, return as is
    return cooldown_time

def is_on_cooldown(user_id, cooldown_dict):
    """Check if user is on cooldown (24 hours)"""
    cooldown_time = get_cooldown_time(user_id, cooldown_dict)
    if not cooldown_time:
        return False
    
    now = datetime.now()
    return (now - cooldown_time).days < 1

# Update your cooldown setting functions:
def set_tictactoe_cooldown(user_id):
    """Set Tic-Tac-Toe cooldown and save"""
    TICTACTOE_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()

def set_gwt_cooldown(user_id):
    """Set GWT cooldown and save"""
    GWT_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()

def set_rpg_cooldown(user_id):
    """Set RPG cooldown and save"""
    RPG_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()

def set_story_cooldown(user_id):
    """Set story cooldown and save"""
    STORY_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()

def set_transform_cooldown(user_id):
    """Set transformation cooldown and save"""
    TRANSFORM_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()

def set_monster_cooldown(user_id):
    """Set monster creation cooldown and save"""
    MONSTER_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()

def set_faction_cooldown(user_id):
    """Set faction join cooldown and save"""
    FACTION_COOLDOWN[user_id] = datetime.now()
    save_cooldowns()



































# ===== COMPLETE WEREWOLF GAME =====
# Globals
WEREWOLF_GAMES = {}
WEREWOLF_COOLDOWN = {}

WEREWOLF_ROLES = {
    "werewolf": {"name": "🐺 Werewolf", "team": "werewolves", "count": 2, "description": "Kill villagers at night"},
    "seer": {"name": "🔮 Seer", "team": "villagers", "count": 1, "description": "Check one player's role each night"},
    "hunter": {"name": "🏹 Hunter", "team": "villagers", "count": 1, "description": "Shoot someone when dying"},
    "doctor": {"name": "💊 Doctor", "team": "villagers", "count": 1, "description": "Save one person from death each night"},
    "villager": {"name": "👨‍🌾 Villager", "team": "villagers", "count": 0, "description": "Vote during the day to find werewolves"}
}
async def werewolf_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a Werewolf game: /werewolf"""
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    
    if int(chat_id) > 0:
        await update.message.reply_text("🐺 Werewolf requires 6+ players! Use in groups.")
        return
    
    # Check if game already active in this chat
    if chat_id in WEREWOLF_GAMES and WEREWOLF_GAMES[chat_id]["phase"] != "completed":
        game = WEREWOLF_GAMES[chat_id]
        phase = game["phase"]
        
        if phase == "waiting":
            player_count = len(game["players"])
            await update.message.reply_text(
                f"🎮 *GAME ALREADY WAITING!* 🐺\n\n"
                f"👥 **Players joined:** {player_count}/15\n"
                f"⏰ **Game starts when 6+ players join**\n\n"
                f"_Click the existing join message to participate!_",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                f"🎮 *GAME IN PROGRESS!* 🌕\n\n"
                f"Current phase: **{phase.upper()}**\n"
                f"Players alive: **{sum(1 for p in game['players'].values() if p['alive'])}**\n\n"
                f"_Wait for this game to finish or use /werewolf_end to force end._",
                parse_mode='HTML'
            )
        return
    
    # Cooldown check
    now = datetime.now(pytz.UTC)
    if not is_premium_user(user_id):
        if user_id in WEREWOLF_COOLDOWN and (now - WEREWOLF_COOLDOWN[user_id]).days < 1:
            await update.message.reply_text("🎃 You've already played Werewolf today! Come back tomorrow.")
            return
        WEREWOLF_COOLDOWN[user_id] = now
    
    # Initialize game with lifespan
    WEREWOLF_GAMES[chat_id] = {
        "phase": "waiting",
        "players": {},
        "day_number": 1,
        "message_id": None,
        "votes": {},
        "night_actions": {},
        "killed_tonight": [],
        "hunter_shot": None,
        "created_at": now,
        "max_wait_time": 300,  # 5 minutes max waiting time
        "game_timeout": 1800   # 30 minutes total game timeout
    }
    
    # Send join message
    keyboard = [
        [InlineKeyboardButton("✅ Join Game", callback_data="werewolf_join")],
        [InlineKeyboardButton("🚪 Start Game (6+ players)", callback_data="werewolf_start_game")],
        [InlineKeyboardButton("❌ Cancel Game", callback_data="werewolf_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    sent = await update.message.reply_text(
        "🐺 *SPOOKY WEREWOLF* 🌕\n\n"
        "A game of deception and survival!\n\n"
        "👥 **Players joined:** 0/15\n"
        "⏰ **Game starts when 6+ players join**\n"
        "🕐 **Auto-cancel in:** 5 minutes\n\n"
        "*Roles:* 🐺 Werewolves, 🔮 Seer, 💊 Doctor, 🏹 Hunter, 👨‍🌾 Villagers\n\n"
        "Click ✅ JOIN to play!",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    WEREWOLF_GAMES[chat_id]["message_id"] = sent.message_id

    # Schedule waiting timeout (5 minutes)
    if context.job_queue:
        context.job_queue.run_once(
            werewolf_waiting_timeout,
            300,  # 5 minutes
            data={"chat_id": chat_id},
            name=f"werewolf_waiting_{chat_id}"
        )
        
        # Schedule total game timeout (30 minutes)
        context.job_queue.run_once(
            werewolf_game_timeout,
            1800,  # 30 minutes
            data={"chat_id": chat_id},
            name=f"werewolf_total_{chat_id}"
        )

async def werewolf_waiting_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Auto-cancel game if not enough players join in 5 minutes"""
    chat_id = context.job.data["chat_id"]
    if chat_id not in WEREWOLF_GAMES:
        return

    game = WEREWOLF_GAMES[chat_id]
    
    if game["phase"] == "waiting":
        player_count = len(game["players"])
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=game["message_id"],
                text=f"🐺 *WEREWOLF GAME CANCELLED* ⏰\n\n"
                     f"Not enough players joined in time!\n"
                     f"👥 **Final count:** {player_count}/6 players\n\n"
                     f"_Use /werewolf to start a new game!_",
                parse_mode='HTML'
            )
        except:
            pass
        
        # Clean up game
        del WEREWOLF_GAMES[chat_id]
        print(f"-> Werewolf game cancelled in chat {chat_id} (timeout)")

async def werewolf_game_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Force end game after 30 minutes total"""
    chat_id = context.job.data["chat_id"]
    if chat_id not in WEREWOLF_GAMES:
        return

    game = WEREWOLF_GAMES[chat_id]
    
    if game["phase"] not in ["completed", "waiting"]:
        # Force end the game
        alive_players = [pid for pid, pdata in game["players"].items() if pdata["alive"]]
        
        # Determine winner based on remaining players
        alive_werewolves = sum(1 for pid in alive_players if game["players"][pid]["team"] == "werewolves")
        alive_villagers = sum(1 for pid in alive_players if game["players"][pid]["team"] == "villagers")
        
        if alive_werewolves >= alive_villagers:
            winner = "werewolves"
        else:
            winner = "villagers"
        
        await end_werewolf_game(chat_id, winner, context, reason="Game timeout - forced end")
        print(f"-> Werewolf game forced ended in chat {chat_id} (30min timeout)")

async def werewolf_cancel_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow game creator to cancel waiting game"""
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    
    if chat_id not in WEREWOLF_GAMES or WEREWOLF_GAMES[chat_id]["phase"] != "waiting":
        await update.message.reply_text("❌ No waiting game to cancel!")
        return
    
    game = WEREWOLF_GAMES[chat_id]
    
    # Check if user started the game (first player)
    if game["players"] and list(game["players"].keys())[0] != user_id:
        await update.message.reply_text("❌ Only the game creator can cancel the game!")
        return
    
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["message_id"],
            text=f"🐺 *WEREWOLF GAME CANCELLED* ❌\n\n"
                 f"Game was cancelled by the creator.\n"
                 f"👥 **Players joined:** {len(game['players'])}/15\n\n"
                 f"_Use /werewolf to start a new game!_",
            parse_mode='HTML'
        )
    except:
        pass
    
    # Clean up game
    del WEREWOLF_GAMES[chat_id]
    await update.message.reply_text("✅ Game cancelled!")

async def handle_werewolf_cancel(query, user_id, context: ContextTypes.DEFAULT_TYPE):
    """Handle cancel button in waiting phase"""
    chat_id = str(query.message.chat_id)
    
    if chat_id not in WEREWOLF_GAMES or WEREWOLF_GAMES[chat_id]["phase"] != "waiting":
        await query.answer("❌ No game to cancel!")
        return
    
    game = WEREWOLF_GAMES[chat_id]
    
    # Check if user started the game
    if not game["players"] or list(game["players"].keys())[0] != str(user_id):
        await query.answer("❌ Only the game creator can cancel!")
        return
    
    try:
        await query.message.edit_text(
            f"🐺 *WEREWOLF GAME CANCELLED* ❌\n\n"
            f"Game was cancelled by the creator.\n"
            f"👥 **Players joined:** {len(game['players'])}/15\n\n"
            f"_Use /werewolf to start a new game!_",
            parse_mode='HTML'
        )
    except:
        pass
    
    # Clean up game
    del WEREWOLF_GAMES[chat_id]
    await query.answer("✅ Game cancelled!")

# Add this to your callback query handler for "werewolf_cancel"


async def handle_werewolf_join(query, user_id, context: ContextTypes.DEFAULT_TYPE):
    """Handle player joining Werewolf game"""
    chat_id = str(query.message.chat_id)
    
    if chat_id not in WEREWOLF_GAMES or WEREWOLF_GAMES[chat_id]["phase"] != "waiting":
        await query.answer("❌ No game waiting for players!")
        return
    
    game = WEREWOLF_GAMES[chat_id]
    username = query.from_user.first_name
    
    if user_id in game["players"]:
        await query.answer("❌ You already joined!")
        return
    
    if len(game["players"]) >= 15:
        await query.answer("❌ Game full! Max 15 players.")
        return
    
    # Add player
    game["players"][user_id] = {
        "username": username,
        "alive": True,
        "role": None,
        "team": None
    }
    
    # Update join message
    player_count = len(game["players"])
    keyboard = [
        [InlineKeyboardButton("✅ Join Game", callback_data="werewolf_join")],
        [InlineKeyboardButton("🚪 Start Game (6+ players)", callback_data="werewolf_start_game")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.edit_text(
        f"🐺 *SPOOKY WEREWOLF* 🌕\n\n"
        f"A game of deception and survival!\n\n"
        f"👥 **Players joined:** {player_count}/15\n"
        f"⏰ **Game starts when 6+ players join**\n\n"
        f"*Roles:* 🐺 Werewolves, 🔮 Seer, 💊 Doctor, 🏹 Hunter, 👨‍🌾 Villagers\n\n"
        f"Click ✅ JOIN to play!",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    await query.answer(f"✅ {username} joined Werewolf!")

async def handle_werewolf_start(query, user_id, context: ContextTypes.DEFAULT_TYPE):
    """Start the Werewolf game"""
    chat_id = str(query.message.chat_id)
    
    if chat_id not in WEREWOLF_GAMES:
        await query.answer("❌ No game to start!")
        return
    
    game = WEREWOLF_GAMES[chat_id]
    player_count = len(game["players"])
    
    if player_count < 6:
        await query.answer("❌ Need at least 6 players to start!")
        return
    
    # Assign roles
    await assign_werewolf_roles(chat_id, context)
    
    # Start first night
    game["phase"] = "night"
    await start_night_phase(chat_id, context)
    
    await query.answer("🎮 Werewolf game starting!")

async def assign_werewolf_roles(chat_id, context: ContextTypes.DEFAULT_TYPE):
    """Assign roles to players"""
    game = WEREWOLF_GAMES[chat_id]
    players = list(game["players"].keys())
    random.shuffle(players)
    
    # Calculate role distribution based on player count
    player_count = len(players)
    werewolf_count = max(2, player_count // 4)  # 25% werewolves
    
    roles = ["werewolf"] * werewolf_count
    roles.extend(["seer", "doctor", "hunter"])
    roles.extend(["villager"] * (player_count - len(roles)))
    random.shuffle(roles)
    
    # Assign roles
    for i, player_id in enumerate(players):
        if i < len(roles):
            role = roles[i]
            game["players"][player_id]["role"] = role
            game["players"][player_id]["team"] = WEREWOLF_ROLES[role]["team"]
    
    # Send role DMs
    for player_id, player_data in game["players"].items():
        role_info = WEREWOLF_ROLES[player_data["role"]]
        try:
            await context.bot.send_message(
                chat_id=int(player_id),
                text=f"🐺 *YOUR WEREWOLF ROLE* 🌕\n\n"
                     f"**{role_info['name']}**\n"
                     f"{role_info['description']}\n\n"
                     f"Team: {role_info['team'].title()}\n\n"
                     f"_Keep this secret! The game begins..._",
                parse_mode='HTML'
            )
        except:
            pass  # User might have blocked bot

async def start_night_phase(chat_id, context: ContextTypes.DEFAULT_TYPE):
    """Start night phase"""
    game = WEREWOLF_GAMES[chat_id]
    game["phase"] = "night"
    game["night_actions"] = {}
    game["killed_tonight"] = []
    
    # Build alive players list with IDs
    alive_players = []
    for player_id, player_data in game["players"].items():
        if player_data["alive"]:
            alive_players.append(f"• {player_data['username']} (ID: {player_id})")
    
    # Send night message to group
    night_msg = await context.bot.send_message(
        chat_id=int(chat_id),
        text=f"🌑 *NIGHT {game['day_number']}* 🌑\n\n"
             f"The village sleeps... evil awakens!\n\n"
             f"👥 **Alive Players ({len(alive_players)}):**\n" + "\n".join(alive_players) + "\n\n"
             f"🐺 Werewolves, choose your victim!\n"
             f"🔮 Seer, investigate someone!\n"
             f"💊 Doctor, save someone!\n\n"
             f"⏰ _You have 2 minutes for night actions..._",
        parse_mode='HTML'
    )
    
    # Send role-specific actions via DM
    await send_night_actions(chat_id, context)
    
    # Schedule night timeout (2 minutes)
    if context.job_queue:
        context.job_queue.run_once(
            werewolf_night_timeout,
            120,  # 2 minutes
            data={"chat_id": chat_id},
            name=f"werewolf_night_{chat_id}"
        )

async def send_night_actions(chat_id, context: ContextTypes.DEFAULT_TYPE):
    """Send night action buttons to players"""
    game = WEREWOLF_GAMES[chat_id]
    
    for player_id, player_data in game["players"].items():
        if not player_data["alive"]:
            continue
            
        role = player_data["role"]
        alive_players = [pid for pid, pdata in game["players"].items() if pdata["alive"] and pid != player_id]
        
        if role == "werewolf":
            # Werewolves vote to kill
            keyboard = []
            for target_id in alive_players:
                target_name = game["players"][target_id]["username"]
                keyboard.append([InlineKeyboardButton(f"🐺 Kill {target_name} (ID: {target_id})", callback_data=f"werewolf_kill_{target_id}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await context.bot.send_message(
                    chat_id=int(player_id),
                    text="🐺 *WEREWOLF ACTION* 🌕\n\nChoose who to kill tonight:",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            except:
                pass
                
        elif role == "seer":
            # Seer investigates
            keyboard = []
            for target_id in alive_players:
                target_name = game["players"][target_id]["username"]
                keyboard.append([InlineKeyboardButton(f"🔮 Check {target_name} (ID: {target_id})", callback_data=f"werewolf_seer_{target_id}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await context.bot.send_message(
                    chat_id=int(player_id),
                    text="🔮 *SEER ACTION* 🌕\n\nChoose who to investigate:",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            except:
                pass
                
        elif role == "doctor":
            # Doctor saves
            keyboard = []
            for target_id in alive_players:
                target_name = game["players"][target_id]["username"]
                keyboard.append([InlineKeyboardButton(f"💊 Save {target_name} (ID: {target_id})", callback_data=f"werewolf_doctor_{target_id}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await context.bot.send_message(
                    chat_id=int(player_id),
                    text="💊 *DOCTOR ACTION* 🌕\n\nChoose who to save from death:",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            except:
                pass

async def handle_werewolf_kill(query, user_id, target_id, context: ContextTypes.DEFAULT_TYPE):
    """Handle werewolf kill vote"""
    chat_id = str(query.message.chat_id)
    game = WEREWOLF_GAMES.get(chat_id)
    
    if not game or game["phase"] != "night":
        await query.answer("❌ Not in night phase!")
        return
    
    # Record the vote
    game["night_actions"]["kill_vote"] = game["night_actions"].get("kill_vote", {})
    game["night_actions"]["kill_vote"][user_id] = target_id
    
    target_name = game["players"][target_id]["username"]
    await query.answer(f"✅ Voting to kill {target_name}!")
    
    # Check if all werewolves voted
    werewolf_count = sum(1 for p in game["players"].values() if p["role"] == "werewolf" and p["alive"])
    if len(game["night_actions"].get("kill_vote", {})) >= werewolf_count:
        await resolve_night_actions(chat_id, context)

async def handle_werewolf_seer(query, user_id, target_id, context: ContextTypes.DEFAULT_TYPE):
    """Handle seer investigation"""
    chat_id = str(query.message.chat_id)
    game = WEREWOLF_GAMES.get(chat_id)
    
    if not game or game["phase"] != "night":
        await query.answer("❌ Not in night phase!")
        return
    
    target_role = game["players"][target_id]["role"]
    role_name = WEREWOLF_ROLES[target_role]["name"]
    target_name = game["players"][target_id]["username"]
    
    game["night_actions"]["seer_target"] = target_id
    
    try:
        await context.bot.send_message(
            chat_id=int(user_id),
            text=f"🔮 *SEER VISION* 🌕\n\n{target_name} is: {role_name}",
            parse_mode='HTML'
        )
    except:
        pass
    
    await query.answer("✅ Investigation complete!")

async def handle_werewolf_doctor(query, user_id, target_id, context: ContextTypes.DEFAULT_TYPE):
    """Handle doctor save"""
    chat_id = str(query.message.chat_id)
    game = WEREWOLF_GAMES.get(chat_id)
    
    if not game or game["phase"] != "night":
        await query.answer("❌ Not in night phase!")
        return
    
    game["night_actions"]["doctor_save"] = target_id
    target_name = game["players"][target_id]["username"]
    await query.answer(f"✅ Saving {target_name}!")

async def resolve_night_actions(chat_id, context: ContextTypes.DEFAULT_TYPE):
    """Resolve all night actions and start day phase"""
    game = WEREWOLF_GAMES[chat_id]
    
    # Determine kill target (most votes)
    kill_votes = game["night_actions"].get("kill_vote", {})
    killed_player = None
    
    if kill_votes:
        vote_count = {}
        for target_id in kill_votes.values():
            vote_count[target_id] = vote_count.get(target_id, 0) + 1
        
        kill_target = max(vote_count, key=vote_count.get)
        
        # Check if doctor saved the target
        doctor_save = game["night_actions"].get("doctor_save")
        if kill_target != doctor_save:
            game["players"][kill_target]["alive"] = False
            game["killed_tonight"].append(kill_target)
            killed_player = kill_target
    
    # Start day phase
    await start_day_phase(chat_id, killed_player, context)

async def start_day_phase(chat_id, killed_player, context: ContextTypes.DEFAULT_TYPE):
    """Start day phase with voting"""
    game = WEREWOLF_GAMES[chat_id]
    game["phase"] = "day"
    game["votes"] = {}
    game["day_number"] += 1
    
    # Build message
    alive_players = []
    for player_id, player_data in game["players"].items():
        if player_data["alive"]:
            alive_players.append(f"• {player_data['username']} (ID: {player_id})")
    
    day_text = f"☀️ *DAY {game['day_number']-1}* ☀️\n\n"
    
    if killed_player:
        killed_name = game["players"][killed_player]["username"]
        day_text += f"💀 Last night, {killed_name} was killed by werewolves!\n\n"
    else:
        day_text += f"🌟 The doctor saved someone! No one died last night!\n\n"
    
    day_text += f"👥 **Alive Players ({len(alive_players)}):**\n" + "\n".join(alive_players) + "\n\n"
    day_text += f"🗳️ **VOTE TO ELIMINATE:**\nUse `/vote PLAYER_ID`\nExample: `/vote {list(game['players'].keys())[0]}`\n\n"
    day_text += f"⏰ _You have 2 minutes to vote..._"
    
    await context.bot.send_message(
        chat_id=int(chat_id),
        text=day_text,
        parse_mode='HTML'
    )
    
    # Check victory conditions
    victory = check_victory_conditions(chat_id)
    if victory:
        await end_werewolf_game(chat_id, victory, context)
        return
    
    # Schedule day timeout (2 minutes)
    if context.job_queue:
        context.job_queue.run_once(
            werewolf_day_timeout,
            120,  # 2 minutes
            data={"chat_id": chat_id},
            name=f"werewolf_day_{chat_id}"
        )

async def werewolf_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle player votes: /vote PLAYER_ID"""
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    
    if chat_id not in WEREWOLF_GAMES or WEREWOLF_GAMES[chat_id]["phase"] != "day":
        await update.message.reply_text("❌ No active voting phase!")
        return
    
    game = WEREWOLF_GAMES[chat_id]
    
    # Check if user is alive and in game
    if user_id not in game["players"] or not game["players"][user_id]["alive"]:
        await update.message.reply_text("❌ You're not in the game or dead!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: `/vote PLAYER_ID`\nCheck the player list for IDs.")
        return
    
    target_id = context.args[0]
    
    # Validate target
    if target_id not in game["players"] or not game["players"][target_id]["alive"]:
        await update.message.reply_text("❌ Invalid player ID or player is dead!")
        return
    
    if target_id == user_id:
        await update.message.reply_text("❌ You cannot vote for yourself!")
        return
    
    # Record vote
    game["votes"][user_id] = target_id
    target_name = game["players"][target_id]["username"]
    voter_name = game["players"][user_id]["username"]
    
    await update.message.reply_text(f"✅ {voter_name} voted to eliminate {target_name}!")
    
    # Check if all alive players voted
    alive_count = sum(1 for p in game["players"].values() if p["alive"])
    if len(game["votes"]) >= alive_count:
        await resolve_voting(chat_id, context)

async def resolve_voting(chat_id, context: ContextTypes.DEFAULT_TYPE):
    """Resolve voting and eliminate player"""
    game = WEREWOLF_GAMES[chat_id]
    
    if not game["votes"]:
        await context.bot.send_message(chat_id=int(chat_id), text="❌ No votes cast! Moving to next night...")
        await start_night_phase(chat_id, context)
        return
    
    # Count votes
    vote_count = {}
    for target_id in game["votes"].values():
        vote_count[target_id] = vote_count.get(target_id, 0) + 1
    
    # Find player with most votes
    max_votes = max(vote_count.values())
    candidates = [pid for pid, votes in vote_count.items() if votes == max_votes]
    
    if len(candidates) > 1:
        # Tie - no one dies
        tied_names = [game["players"][pid]["username"] for pid in candidates]
        await context.bot.send_message(
            chat_id=int(chat_id),
            text=f"🤝 **TIE!** No one eliminated.\nTied: {', '.join(tied_names)}\n\nMoving to next night...",
            parse_mode='HTML'
        )
        await start_night_phase(chat_id, context)
        return
    
    # Eliminate player
    eliminated_id = candidates[0]
    eliminated_player = game["players"][eliminated_id]
    eliminated_player["alive"] = False
    
    await context.bot.send_message(
        chat_id=int(chat_id),
        text=f"⚰️ **{eliminated_player['username']}** was eliminated!\nThey were: {WEREWOLF_ROLES[eliminated_player['role']]['name']}",
        parse_mode='HTML'
    )
    
    # Handle hunter ability
    if eliminated_player["role"] == "hunter":
        await handle_hunter_death(chat_id, eliminated_id, context)
        return
    
    # Check victory conditions
    victory = check_victory_conditions(chat_id)
    if victory:
        await end_werewolf_game(chat_id, victory, context)
    else:
        await start_night_phase(chat_id, context)

async def handle_hunter_death(chat_id, hunter_id, context: ContextTypes.DEFAULT_TYPE):
    """Hunter shoots someone when dying"""
    game = WEREWOLF_GAMES[chat_id]
    hunter_name = game["players"][hunter_id]["username"]
    
    await context.bot.send_message(
        chat_id=int(chat_id),
        text=f"🏹 **{hunter_name} the Hunter** shoots someone before dying!\nThey have 1 minute to choose...",
        parse_mode='HTML'
    )
    
    # Send hunter shooting options via DM
    alive_players = [pid for pid, pdata in game["players"].items() if pdata["alive"] and pid != hunter_id]
    keyboard = []
    for target_id in alive_players:
        target_name = game["players"][target_id]["username"]
        keyboard.append([InlineKeyboardButton(f"🏹 Shoot {target_name} (ID: {target_id})", callback_data=f"werewolf_hunter_{target_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await context.bot.send_message(
            chat_id=int(hunter_id),
            text="🏹 *HUNTER'S REVENGE* 🌕\n\nChoose who to shoot:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except:
        pass
    
    # Schedule hunter timeout (1 minute)
    if context.job_queue:
        context.job_queue.run_once(
            werewolf_hunter_timeout,
            60,  # 1 minute
            data={"chat_id": chat_id},
            name=f"werewolf_hunter_{chat_id}"
        )

async def handle_werewolf_hunter(query, user_id, target_id, context: ContextTypes.DEFAULT_TYPE):
    """Handle hunter shooting"""
    chat_id = str(query.message.chat_id)
    game = WEREWOLF_GAMES.get(chat_id)
    
    if not game:
        await query.answer("❌ Game not found!")
        return
    
    # Kill the target
    game["players"][target_id]["alive"] = False
    target_name = game["players"][target_id]["username"]
    hunter_name = game["players"][user_id]["username"]
    
    await context.bot.send_message(
        chat_id=int(chat_id),
        text=f"💥 **{hunter_name}** shoots **{target_name}** before dying!\nThey were: {WEREWOLF_ROLES[game['players'][target_id]['role']]['name']}",
        parse_mode='HTML'
    )
    
    await query.answer("✅ Shot fired!")
    
    # Check victory conditions
    victory = check_victory_conditions(chat_id)
    if victory:
        await end_werewolf_game(chat_id, victory, context)
    else:
        await start_night_phase(chat_id, context)

def check_victory_conditions(chat_id):
    """Check if werewolves or villagers won"""
    game = WEREWOLF_GAMES[chat_id]
    
    alive_werewolves = sum(1 for p in game["players"].values() if p["alive"] and p["team"] == "werewolves")
    alive_villagers = sum(1 for p in game["players"].values() if p["alive"] and p["team"] == "villagers")
    
    if alive_werewolves == 0:
        return "villagers"
    elif alive_werewolves >= alive_villagers:
        return "werewolves"
    
    return None

async def end_werewolf_game(chat_id, winning_team, context: ContextTypes.DEFAULT_TYPE):
    """End game and announce winner"""
    game = WEREWOLF_GAMES[chat_id]
    
    # Build results
    results = []
    for player_id, player_data in game["players"].items():
        role_name = WEREWOLF_ROLES[player_data["role"]]["name"]
        status = "✅ Alive" if player_data["alive"] else "💀 Dead"
        results.append(f"• {player_data['username']} - {role_name} ({status})")
    
    winner_text = "👨‍🌾 **VILLAGERS WIN!** 🌅" if winning_team == "villagers" else "🐺 **WEREWOLVES WIN!** 🌕"
    
    await context.bot.send_message(
        chat_id=int(chat_id),
        text=f"🎮 *GAME OVER* 🎮\n\n{winner_text}\n\n**Final Results:**\n" + "\n".join(results) + "\n\nThanks for playing! 🐺",
        parse_mode='HTML'
    )
    
    # Clean up game
    del WEREWOLF_GAMES[chat_id]

# Timeout handlers
async def werewolf_night_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Auto-advance if players don't act at night"""
    chat_id = context.job.data["chat_id"]
    if chat_id in WEREWOLF_GAMES and WEREWOLF_GAMES[chat_id]["phase"] == "night":
        await context.bot.send_message(chat_id=int(chat_id), text="⏰ Night time over! Resolving actions...")
        await resolve_night_actions(chat_id, context)

async def werewolf_day_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Auto-advance if players don't vote"""
    chat_id = context.job.data["chat_id"]
    if chat_id in WEREWOLF_GAMES and WEREWOLF_GAMES[chat_id]["phase"] == "day":
        await context.bot.send_message(chat_id=int(chat_id), text="⏰ Voting time over! Resolving votes...")
        await resolve_voting(chat_id, context)

async def werewolf_hunter_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Auto-advance if hunter doesn't shoot"""
    chat_id = context.job.data["chat_id"]
    if chat_id in WEREWOLF_GAMES:
        await context.bot.send_message(chat_id=int(chat_id), text="⏰ Hunter didn't shoot! Moving to night...")
        await start_night_phase(chat_id, context)


async def werewolf_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explain Werewolf game rules with auto-delete after 20 seconds"""
    chat_id = str(update.effective_chat.id)
    
    help_text = (
        "🐺 *WEREWOLF GAME* 🌕\n\n"
        "A game of deception, deduction, and survival!\n\n"
        "🎮 *How to Play:*\n"
        "1. Use /werewolf_start to start a game in a group (6-15 players)\n"
        "2. Players join by clicking ✅ Join Game\n"
        "3. Game starts when 6+ players join\n\n"
        "👥 *Roles:*\n"
        "🐺 **Werewolves** - Kill villagers at night\n"
        "🔮 **Seer** - Check one player's role each night\n"
        "💊 **Doctor** - Save one person from death each night\n"
        "🏹 **Hunter** - Shoot someone when dying\n"
        "👨‍🌾 **Villagers** - Vote during the day to find werewolves\n\n"
        "⏰ *Game Phases:*\n"
        "🌑 **Night** - Special roles perform actions (2 minutes)\n"
        "☀️ **Day** - Everyone votes to eliminate (2 minutes)\n\n"
        "🏆 *Victory Conditions:*\n"
        "• Werewolves win if they equal or outnumber villagers\n"
        "• Villagers win if all werewolves are eliminated\n\n"
        "⚡ *Commands:*\n"
        "/vote PLAYER_ID - Vote to eliminate during day\n"
        "/werewolf - Start new game\n\n"
        "🎃 *Free users:* 1 game per day\n"
        "💫 *Premium:* Unlimited games! 🔥\n\n"
        "🕐 _This message will vanish in 20 seconds..._ 👻"
    )
    
    # Send the help message
    help_message = await update.message.reply_text(help_text, parse_mode='HTML')
    
    # Schedule auto-delete after 20 seconds
    if context.job_queue:
        context.job_queue.run_once(
            delete_werewolf_help,
            20,  # 20 seconds
            data={
                "chat_id": chat_id,
                "message_id": help_message.message_id
            },
            name=f"delete_werewolf_help_{chat_id}"
        )
    else:
        print("❌ JobQueue not available for auto-delete!")

async def delete_werewolf_help(context: ContextTypes.DEFAULT_TYPE):
    """Auto-delete the werewolf help message after 20 seconds"""
    try:
        job_data = context.job.data
        chat_id = job_data["chat_id"]
        message_id = job_data["message_id"]
        
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id
        )
        print(f"✅ Auto-deleted werewolf help from chat {chat_id}")
    except Exception as e:
        print(f"❌ Failed to auto-delete werewolf help: {e}")









































import random
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update

# ===== GHOST STORY CHAIN =====
# Globals
GHOST_STORY_GAMES = {}  # {chat_id: {"lines": [], "authors": [], "msg_id": int}}
STORY_VOTES = {}  # {chat_id: {line_index: [user_ids]}}
GHOST_BUTTON_COOLDOWN = {}  # {chat_id: {user_id: datetime}}

GHOST_STARTERS = [
    "The old house creaked at midnight...",
    "A whisper came from the empty room...",
    "The mirror showed someone else's face...",
    "Footsteps echoed in the fog outside...",
    "A cold hand brushed against my neck...",
    "The candle flickered without a breeze...",
    "Shadows danced in the abandoned attic...",
    "A scream cut through the silent night...",
    "The clock stopped, but time kept moving...",
    "Something scratched beneath the floorboards..."
]

async def ghoststory_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Ghost Story Chain with /ghoststory"""
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    
    if int(chat_id) > 0:
        await update.message.reply_text("👻 Ghost stories are for groups only!")
        return
    
    # Cooldown check (shared with Tic-Tac-Toe/Werewolf)
    now = datetime.now(timezone.utc)
    if not is_premium_user(user_id):
        if is_on_cooldown(user_id, TICTACTOE_COOLDOWN):
            await update.message.reply_text("👻 You've played a game today! Come back tomorrow or go premium! 💫")
            return
        set_tictactoe_cooldown(user_id)
    
    # Check for existing game
    if chat_id in GHOST_STORY_GAMES:
        await update.message.reply_text("👻 A story is already in progress! Reply to add a line or wait for voting!")
        return
    
    # Initialize game
    starter = random.choice(GHOST_STARTERS)
    GHOST_STORY_GAMES[chat_id] = {
        "lines": [starter],
        "authors": [None],  # Starter has no author
        "msg_id": None
    }
    
    # Post story start
    msg = await update.message.reply_text(
        f"👻 *GHOST STORY CHAIN* 👻\n\n"
        f"**Line 1:** {starter}\n\n"
        f"Reply to this message with your creepy continuation!\n"
        f"⏰ *3 lines max, 2 min total*",
    )
    GHOST_STORY_GAMES[chat_id]["msg_id"] = msg.message_id
    
    # Schedule end
    if context.job_queue:
        context.job_queue.run_once(
            ghoststory_end,
            120,  # 2 minutes
            data={"chat_id": chat_id},
            name=f"ghoststory_end_{chat_id}"
        )

async def ghoststory_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle player adding a story line via reply"""
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    
    if chat_id not in GHOST_STORY_GAMES:
        return
    game = GHOST_STORY_GAMES[chat_id]
    if len(game["lines"]) >= 3:
        await update.message.reply_text("👻 Story full! Wait for voting!")
        return
    if not update.message.reply_to_message or update.message.reply_to_message.message_id != game["msg_id"]:
        await update.message.reply_text("👻 Reply to the story message to add a line!")
        return
    # Check if user already contributed
    if user_id in game["authors"]:
        await update.message.reply_text("👻 You've already added a line! Let others contribute!")
        return
    
    line = update.message.text.strip()[:100]  # Limit to 100 chars
    if not line:
        await update.message.reply_text("👻 Can't add an empty line!")
        return
    
    game["lines"].append(line)
    game["authors"].append(user_id)
    await update.message.reply_text(
        f"✅ Line {len(game['lines'])} added by {update.effective_user.first_name}!",
        parse_mode="HTML"
    )
    
    # End early if max lines reached
    if len(game["lines"]) >= 3:
        await ghoststory_end(context, {"chat_id": chat_id})

async def ghoststory_vote(query, user_id, line_index, context: ContextTypes.DEFAULT_TYPE):
    """Handle vote for scariest line"""
    chat_id = str(query.message.chat_id)
    if chat_id not in GHOST_STORY_GAMES:
        await query.answer("⏳ No story to vote on!")
        return
    
    # Initialize votes
    if chat_id not in STORY_VOTES:
        STORY_VOTES[chat_id] = {str(i): [] for i in range(len(GHOST_STORY_GAMES[chat_id]["lines"]))}
    
    # Prevent double voting
    for voters in STORY_VOTES[chat_id].values():
        if user_id in voters:
            await query.answer("⏳ You already voted!")
            return
    
    # Record vote
    STORY_VOTES[chat_id][line_index].append(user_id)
    await query.answer(f"✅ Voted for Line {int(line_index)+1}!")

async def ghoststory_end(context: ContextTypes.DEFAULT_TYPE, job_data: dict = None):
    """End story-building and start voting"""
    chat_id = job_data["chat_id"] if job_data else context.job.data["chat_id"]
    if chat_id not in GHOST_STORY_GAMES:
        return
    game = GHOST_STORY_GAMES[chat_id]
    
    # Build story
    full_story = "\n".join([f"{i+1}. {line}" for i, line in enumerate(game["lines"])])
    keyboard = [[InlineKeyboardButton(f"Vote Line {i+1}", callback_data=f"ghoststory_vote_{i}")]
                for i in range(len(game["lines"]))]
    
    try:
        await context.bot.edit_message_text(
            chat_id=int(chat_id),
            message_id=game["msg_id"],
            text=f"👻 *STORY COMPLETE!* 👻\n\n{full_story}\n\nVote for the scariest line (30s):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    except:
        await context.bot.send_message(
            chat_id=int(chat_id),
            text=f"👻 *STORY COMPLETE!* 👻\n\n{full_story}\n\nVote for the scariest line (30s):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    
    # Schedule voting end
    if context.job_queue:
        context.job_queue.run_once(
            ghoststory_tally,
            30,  # 30 seconds
            data={"chat_id": chat_id},
            name=f"ghoststory_tally_{chat_id}"
        )

async def ghoststory_tally(context: ContextTypes.DEFAULT_TYPE):
    """Tally votes and announce winner"""
    chat_id = context.job.data["chat_id"]
    if chat_id not in GHOST_STORY_GAMES:
        return
    game = GHOST_STORY_GAMES[chat_id]
    votes = STORY_VOTES.get(chat_id, {})
    
    # Find winner
    max_votes = 0
    winner_index = 0
    for i, voters in votes.items():
        if len(voters) > max_votes:
            max_votes = len(voters)
            winner_index = int(i)
    
    # Handle no votes or tie
    if max_votes == 0 or len(game["lines"]) == 1:
        await context.bot.send_message(
            chat_id=int(chat_id),
            text="👻 *NO VOTES OR STORY TOO SHORT!* 👻\nNo winner this time. Thanks for playing!",
            parse_mode="HTML"
        )
    else:
        winner_id = game["authors"][winner_index]
        try:
            winner_name = (await context.bot.get_chat_member(chat_id, winner_id)).user.first_name
        except:
            winner_name = "Mystery Storyteller"
        await context.bot.send_message(
            chat_id=int(chat_id),
            text=f"👻 *SCARIEST LINE!* 👻\n"
                 f"Winner: {winner_name} with \"{game['lines'][winner_index]}\" (+25 scare points!)\n"
                 f"Thanks for playing!",
            parse_mode="HTML"
        )
        update_group_score(chat_id, winner_id, 25, winner_name)
        save_group_leaderboard()
    
    # Cleanup
    del GHOST_STORY_GAMES[chat_id]
    STORY_VOTES.pop(chat_id, None)
    GHOST_BUTTON_COOLDOWN.pop(chat_id, None)

# Placeholder for existing SpookyBot functions (ensure these are in your code)
def is_premium_user(user_id: str) -> bool:
    return False  # Replace with your function

def is_on_cooldown(user_id: str, cooldown_dict: dict) -> bool:
    if user_id in cooldown_dict:
        last_played = cooldown_dict[user_id]
        return (datetime.now(timezone.utc) - last_played).days < 1
    return False

def set_tictactoe_cooldown(user_id: str):
    TICTACTOE_COOLDOWN[user_id] = datetime.now(timezone.utc)

def update_group_score(chat_id: str, user_id: str, points: int, username: str):
    pass  # Replace with your function

def save_group_leaderboard():
    pass  # Replace with your function

TICTACTOE_COOLDOWN = {}  # Your existing global






































# ===== TIC-TAC-TOE MINI-GAME =====
# Globals
TICTACTOE_COOLDOWN = {}  
TICTACTOE_BUTTON_COOLDOWN = {}  
ACTIVE_TICTACTOE_GAMES = {}  
GWT_COOLDOWN = {}
RPG_COOLDOWN = {}
STORY_COOLDOWN = {}
TRANSFORM_COOLDOWN = {}
MONSTER_COOLDOWN = {}
FACTION_COOLDOWN = {}

def check_tictactoe_winner(board):
    """Return '👻', '🎃', 'draw', or None for game state."""
    win_conditions = [(0, 1, 2), (3, 4, 5), (6, 7, 8), 
                      (0, 3, 6), (1, 4, 7), (2, 5, 8), 
                      (0, 4, 8), (2, 4, 6)]
    for a, b, c in win_conditions:
        if board[a] == board[b] == board[c] and board[a] is not None:
            return board[a]
    if None not in board:
        return "draw"
    return None

def get_tictactoe_board_markup(chat_id):
    """Generate inline keyboard for Tic-Tac-Toe board."""
    board = ACTIVE_TICTACTOE_GAMES[chat_id]["board"]
    keyboard = []
    for j in range(0, 9, 3):
        row = []
        for i in range(j, j + 3):
            button_text = board[i] if board[i] else str(i + 1)
            row.append(InlineKeyboardButton(button_text, callback_data=f"tictactoe_{i}"))
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

async def tictactoe_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a Tic-Tac-Toe challenge in a group: /tictactoe"""
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    username = update.effective_user.first_name

    if int(chat_id) > 0:
        await update.message.reply_text("⚔️ Tic-Tac-Toe can only be played in groups!")
        return

    # Cooldown check
    now = datetime.now(pytz.UTC)
    if not is_premium_user(user_id):
        if is_on_cooldown(user_id, TICTACTOE_COOLDOWN):
            await update.message.reply_text(
                f"🎃 {mention(update.effective_user)} has already played Tic-Tac-Toe today! Come back tomorrow MORTAL  \n\n ONLY /PREMIUM HAVE INFINITE USE 👻",
                parse_mode="HTML"
            )
            return
        set_tictactoe_cooldown(user_id)

    # Create challenge - NO USER ID RESOLUTION NEEDED!
    ACTIVE_TICTACTOE_GAMES[chat_id] = {
        "status": "waiting",  # waiting, active, completed
        "challenger": {"id": user_id, "username": username, "mark": "👻"},
        "opponent": None,  # Will be set when someone accepts
        "board": [None] * 9,
        "turn": None,  # Will be set when game starts
        "message_id": None,
        "started_at": now
    }

    # Send challenge message with Accept button
    keyboard = [
        [InlineKeyboardButton("✅ Accept Challenge", callback_data="tictactoe_accept")],
        [InlineKeyboardButton("❌ Decline", callback_data="tictactoe_decline")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sent = await update.message.reply_text(
        f"🎲 *SPOOKY TIC-TAC-TOE CHALLENGE* 🎲\n\n"
        f"👻 *Challenger:* @{username}\n\n"
        f"Who will face the horror? The first to click ACCEPT will battle!\n\n"
        f"🏆 *Prize:* 25 scare points for the winner!\n"
        f"⏰ *Expires in:* 2 minutes",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    ACTIVE_TICTACTOE_GAMES[chat_id]["message_id"] = sent.message_id

    # Schedule challenge expiration
    if context.job_queue:
        context.job_queue.run_once(
            tictactoe_challenge_timeout,
            120,  # 2 minutes
            data={"chat_id": chat_id},
            name=f"tictactoe_challenge_{chat_id}"
        )
        print(f"-> Tic-Tac-Toe challenge started in chat {chat_id} by {username}")

async def handle_tictactoe_accept(query, user_id, context: ContextTypes.DEFAULT_TYPE):
    """Handle when someone accepts the Tic-Tac-Toe challenge"""
    chat_id = str(query.message.chat_id)
    if chat_id not in ACTIVE_TICTACTOE_GAMES:
        await query.answer("❌ No active challenge!")
        return

    game = ACTIVE_TICTACTOE_GAMES[chat_id]
    
    # Check if challenge is still waiting
    if game["status"] != "waiting":
        await query.answer("❌ Challenge already accepted or expired!")
        return

    username = query.from_user.first_name
    user_id = str(user_id)

    # Check if user is trying to accept their own challenge
    if user_id == game["challenger"]["id"]:
        await query.answer("❌ You cannot accept your own challenge!")
        return

    # Set opponent and start the game!
    game["opponent"] = {"id": user_id, "username": username, "mark": "🎃"}
    game["status"] = "active"
    game["turn"] = game["challenger"]["id"]  # Challenger goes first

    # Update message to show game started
    challenger_name = game["challenger"]["username"]
    opponent_name = game["opponent"]["username"]

    text = (
        f"🎲 *SPOOKY TIC-TAC-TOE* 🎲\n\n"
        f"👻 @{challenger_name} vs 🎃 @{opponent_name}\n"
        f"Turn: @{challenger_name}\n"
        f"Make a move by clicking a number (30s per turn)!"
    )

    try:
        await query.message.edit_text(
            text,
            reply_markup=get_tictactoe_board_markup(chat_id),
            parse_mode="HTML"
        )
    except telegram.error.TimedOut:
        await query.message.reply_text(text, reply_markup=get_tictactoe_board_markup(chat_id), parse_mode="HTML")
    
    await query.answer("✅ Challenge accepted! Game starting...")

    # Schedule move timeout
    if context.job_queue:
        context.job_queue.run_once(
            tictactoe_timeout,
            30,
            data={"chat_id": chat_id},
            name=f"tictactoe_timeout_{chat_id}"
        )

async def handle_tictactoe_decline(query, user_id, context: ContextTypes.DEFAULT_TYPE):
    """Handle when someone declines the challenge"""
    chat_id = str(query.message.chat_id)
    if chat_id not in ACTIVE_TICTACTOE_GAMES:
        await query.answer("❌ No active challenge!")
        return

    game = ACTIVE_TICTACTOE_GAMES[chat_id]
    
    if game["status"] != "waiting":
        await query.answer("❌ Challenge already accepted!")
        return

    username = query.from_user.first_name
    
    # Update message to show someone declined
    challenger_name = game["challenger"]["username"]
    
    try:
        await query.message.edit_text(
            f"🎲 *SPOOKY TIC-TAC-TOE CHALLENGE* 🎲\n\n"
            f"👻 *Challenger:* @{challenger_name}\n\n"
            f"❌ @{username} declined the challenge!\n\n"
            f"_The horror continues... someone else can still accept!_",
            parse_mode="HTML"
        )
    except:
        pass
    
    await query.answer("❌ Challenge declined!")

async def tictactoe_challenge_timeout(context: ContextTypes.DEFAULT_TYPE):
    """Handle challenge expiration"""
    chat_id = context.job.data["chat_id"]
    if chat_id not in ACTIVE_TICTACTOE_GAMES:
        return

    game = ACTIVE_TICTACTOE_GAMES[chat_id]
    
    if game["status"] == "waiting":
        challenger_name = game["challenger"]["username"]
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=game["message_id"],
                text=f"🎲 *SPOOKY TIC-TAC-TOE CHALLENGE* 🎲\n\n"
                     f"👻 *Challenger:* @{challenger_name}\n\n"
                     f"⏰ *Challenge expired!* No one was brave enough to face the horror... 👻",
                parse_mode="HTML"
            )
        except:
            pass
        
        del ACTIVE_TICTACTOE_GAMES[chat_id]
        print(f"-> Tic-Tac-Toe challenge expired in chat {chat_id}")

async def handle_tictactoe_move(query, user_id, position, context: ContextTypes.DEFAULT_TYPE):
    """Handle Tic-Tac-Toe move via button - SIMPLIFIED VERSION"""
    chat_id = str(query.message.chat_id)
    if chat_id not in ACTIVE_TICTACTOE_GAMES:
        await query.answer("❌ No active Tic-Tac-Toe game!")
        return

    game = ACTIVE_TICTACTOE_GAMES[chat_id]
    user_id = str(user_id)

    # Check if game is active
    if game["status"] != "active":
        await query.answer("❌ Game not active!")
        return

    # Button click cooldown
    if chat_id not in TICTACTOE_BUTTON_COOLDOWN:
        TICTACTOE_BUTTON_COOLDOWN[chat_id] = {}
    last_click = TICTACTOE_BUTTON_COOLDOWN[chat_id].get(user_id)
    now = datetime.now(pytz.UTC)
    if last_click and (now - last_click).total_seconds() < 1:
        await query.answer("⏳ Please wait a moment before clicking again!")
        return
    TICTACTOE_BUTTON_COOLDOWN[chat_id][user_id] = now

    # Check if user is one of the players
    if user_id not in [game["challenger"]["id"], game["opponent"]["id"]]:
        await query.answer("❌ You're not in this game!")
        return
    
    # Check if it's user's turn
    if user_id != game["turn"]:
        # Show whose turn it is
        current_turn_id = game["turn"]
        if current_turn_id == game["challenger"]["id"]:
            turn_username = game["challenger"]["username"]
        else:
            turn_username = game["opponent"]["username"]
        await query.answer(f"❌ It's @{turn_username}'s turn!")
        return
        
    if game["board"][position] is not None:
        await query.answer("❌ That position is already taken!")
        return

    # Determine which player is making the move
    if user_id == game["challenger"]["id"]:
        current_player = game["challenger"]
        next_turn_id = game["opponent"]["id"]
    else:
        current_player = game["opponent"]
        next_turn_id = game["challenger"]["id"]

    # Make move
    game["board"][position] = current_player["mark"]
    game["turn"] = next_turn_id
    
    winner = check_tictactoe_winner(game["board"])

    # Update message
    if winner:
        text = f"🎲 *SPOOKY TIC-TAC-TOE* 🎲\n\n"
        if winner == "draw":
            text += "It's a draw! No points awarded. 😿"
        else:
            # Find winner
            if winner == game["challenger"]["mark"]:
                winner_username = game["challenger"]["username"]
            else:
                winner_username = game["opponent"]["username"]
            
            text += f"@{winner_username} ({winner}) wins! +25 scare points! 🎃"
            
            # Award points using addscare method
            leaderboard = init_group_leaderboard(chat_id)
            if winner_username not in leaderboard:
                leaderboard[winner_username] = {'score': 0, 'username': winner_username}
            leaderboard[winner_username]['score'] += 25
            save_group_leaderboard()
            
        try:
            await query.message.edit_text(text, parse_mode="HTML")
        except telegram.error.TimedOut:
            await query.message.reply_text(text, parse_mode="HTML")
        del ACTIVE_TICTACTOE_GAMES[chat_id]
        print(f"-> Tic-Tac-Toe in chat {chat_id} ended: {winner}")
        return

    # Next turn
    if game["turn"] == game["challenger"]["id"]:
        next_player_username = game["challenger"]["username"]
    else:
        next_player_username = game["opponent"]["username"]
    
    challenger_name = game["challenger"]["username"]
    opponent_name = game["opponent"]["username"]
    
    text = (
        f"🎲 *SPOOKY TIC-TAC-TOE* 🎲\n\n"
        f"👻 @{challenger_name} vs 🎃 @{opponent_name}\n"
        f"Turn: @{next_player_username}\n"
        f"Make a move by clicking a number (30s per turn)!"
    )
    try:
        await query.message.edit_text(
            text,
            reply_markup=get_tictactoe_board_markup(chat_id),
            parse_mode="HTML"
        )
    except telegram.error.TimedOut:
        await query.message.reply_text(text, reply_markup=get_tictactoe_board_markup(chat_id), parse_mode="HTML")
    await query.answer("Move made!")

    # Reset timeout
    if context.job_queue:
        context.job_queue.run_once(
            tictactoe_timeout,
            30,
            data={"chat_id": chat_id},
            name=f"tictactoe_timeout_{chat_id}"
        )

async def tictactoe_timeout(context: ContextTypes.DEFAULT_TYPE):
    """End game if no move is made in 30 seconds."""
    chat_id = context.job.data["chat_id"]
    if chat_id not in ACTIVE_TICTACTOE_GAMES:
        return

    game = ACTIVE_TICTACTOE_GAMES[chat_id]
    if game["status"] != "active":
        return

    current_turn_id = game["turn"]
    if current_turn_id == game["challenger"]["id"]:
        current_player_username = game["challenger"]["username"]
    else:
        current_player_username = game["opponent"]["username"]
        
    text = (
        f"🎲 *SPOOKY TIC-TAC-TOE* 🎲\n\n"
        f"@{current_player_username} took too long! Game over, no points awarded. 😿"
    )
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["message_id"],
            text=text,
            parse_mode="HTML"
        )
    except telegram.error.TimedOut:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML"
        )
    print(f"-> Tic-Tac-Toe in chat {chat_id} timed out")
    del ACTIVE_TICTACTOE_GAMES[chat_id]

async def tictactoe_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explain Tic-Tac-Toe rules"""
    await update.message.reply_text(
        "🎲 *SPOOKY TIC-TAC-TOE* 🎲\n\n"
        "Start a challenge with /tictactoe in a group!\n"
        "🟢 First person to click ACCEPT becomes your opponent\n"
        "🟢 Take turns placing 👻 or 🎃 on a 3x3 grid\n"
        "🟢 First to align 3 marks (row, column, diagonal) wins!\n"
        "🟢 30 seconds per through out, or the game ends\n"
        "🏆 Winner gets +25 scare points!\n"
        "<i>Free players:</i> <b>1 game/day</b>.\n\n <i>Premiums:</i> <b>unlimited!</b> 🔥",
        parse_mode="HTML"
    )   






# ===== GAMES PANEL COMMAND =====
# ===== GAMES PANEL COMMAND =====
# ===== GAMES PANEL COMMAND =====
async def games_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all available games in one panel (auto-deletes after 10s)"""
    chat_id = str(update.effective_chat.id)
    
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_back")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the games panel message
    games_message = await update.message.reply_text(
        "🎮 <b>SPOOKY GAMES PANEL</b> 🎪\n\n"
        
        "⚔️ *GHOSTS vs ZOMBIES BATTLE* 🧟‍♂️\n"
        "Epic team battles in groups!\n"
        "• `/start_battle` - Start battle (admin)\n"  
        "• `/join_ghosts` - Join Ghost team\n"
        "• `/join_zombies` - Join Zombie team\n"
        "• `/haunt` - Ghosts attack\n"
        "• `/infect` - Zombies attack\n"
        "• `/battle_status` - Check battle\n\n"
        
        "🎲 *GHOSTS • WIZARDS • TROLLS* 🧌\n"  
        "• `/gwt_start` - Start game in group\n"
        "• Choose: Ghost, Wizard, or Troll\n"
        "• 30-second rounds\n"

        "👻 *MAKE A LINE* \n"
        "Make a classsic line from a movie or anywhere\n"
        "• `/ghoststory` - Start challenge\n"
        "• let members vote for the best line\n"
        

        "👻 *SPOOKY TIC-TAC-TOE* 🎃\n"
        "Classic game with horror twist!\n"
        "• `/tictactoe` - Start challenge\n"
        "• First to accept becomes opponent\n"
        "• Ghosts (👻) vs Pumpkins (🎃)\n"
        "• Winner gets +25 points!\n\n"
        
        " *WERE-WOLF* \n"
        "WEREWOLF GAME(MAFIA)!\n"
        "• `/werewolf_start` - Start challenge\n"
        "• Game of deception and survival\n"

        "🏆 *All games award SCARE POINTS!*\n"
        "• Free users: Limited plays/day\n"
        "• Premium: Unlimited games! 🔥\n\n"
        
        "*Use the commands above to play!* 🎯\n\n"
        "🕐 _This message will vanish in 15 seconds..._ 👻",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    # Schedule auto-delete after 10 seconds
    if context.job_queue:
        context.job_queue.run_once(
            delete_games_panel,
            15,  # 10 seconds
            data={
                "chat_id": chat_id,
                "message_id": games_message.message_id
            },
            name=f"delete_games_{chat_id}"
        )
    else:
        print("❌ JobQueue not available for auto-delete!")

async def delete_games_panel(context: ContextTypes.DEFAULT_TYPE):
    """Auto-delete the games panel message"""
    try:
        job_data = context.job.data
        chat_id = job_data["chat_id"]
        message_id = job_data["message_id"]
        
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id
        )
        print(f"✅ Auto-deleted games panel from chat {chat_id}")
    except Exception as e:
        print(f"❌ Failed to auto-delete games panel: {e}")





# ===== GHOSTS vs ZOMBIES - Group Battle Mode =====

# Globals
BATTLES_FILE = "battles.json"
BATTLES = {}  # { chat_id_str: {status, teams:{ghosts:{members:[{"id": user_id, "name": first_name}],hp}, zombies:{members:[{"id": user_id, "name": first_name}],hp}}, cooldowns:{user_id: iso}, started_at: iso, end_at: iso_or_None } }
BATTLE_DEFAULT_HP = 1000
BATTLE_ACTION_COOLDOWN = 30  # seconds per action per user
FACTION_COOLDOWN = {}  # {user_id: datetime} for daily join limit

# ---------------- persistence ----------------
def save_battles():
    try:
        with open(BATTLES_FILE, "w", encoding="utf-8") as f:
            json.dump(BATTLES, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save battles: {e}")

def load_battles():
    global BATTLES
    try:
        if os.path.exists(BATTLES_FILE):
            with open(BATTLES_FILE, "r", encoding="utf-8") as f:
                BATTLES = json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load battles: {e}")
        BATTLES = {}

# Helpers
def init_battle_state(chat_id_str):
    if chat_id_str not in BATTLES:
        BATTLES[chat_id_str] = {
            "status": "inactive",  # inactive | active
            "teams": {
                "ghosts": {"members": [], "hp": BATTLE_DEFAULT_HP},
                "zombies": {"members": [], "hp": BATTLE_DEFAULT_HP}
            },
            "cooldowns": {},  # { user_id_str: iso_timestamp }
            "started_at": None,
            "end_at": None
        }
    return BATTLES[chat_id_str]

def user_in_team(battle, user_id_str):
    g = any(m["id"] == user_id_str for m in battle["teams"]["ghosts"]["members"])
    z = any(m["id"] == user_id_str for m in battle["teams"]["zombies"]["members"])
    if g: return "ghosts"
    if z: return "zombies"
    return None

def mention(user):
    # returns safe mention for messages: use tg user link
    return f"[{user.first_name}]({user.id})"

def is_admin_user(user_id):
    # adapt to your admin check; I used the is_admin function pattern you have
    try:
        return is_admin(user_id)
    except:
        return False

from datetime import datetime, timedelta
import pytz

def can_act(battle, uid_str):
    if uid_str not in battle["actions"] or "timestamp" not in battle["actions"][uid_str]:
        return True, 0
    last_action = battle["actions"][uid_str]["timestamp"]
    cooldown = 28 if get_member_role(battle, user_in_team(battle, uid_str), uid_str) == "Ghoul" else 35
    elapsed = (datetime.now(pytz.UTC) - last_action).total_seconds()
    return elapsed >= cooldown, max(0, cooldown - elapsed)

    if not cd:
        return True, None
    try:
        last = datetime.fromisoformat(cd)
        diff = datetime.now(pytz.UTC) - last
        remaining = BATTLE_ACTION_COOLDOWN - int(diff.total_seconds())
        if remaining > 0:
            return False, remaining
        return True, None
    except Exception:
        return True, None

def set_action_timestamp(battle, user_id_str):
    battle.setdefault("cooldowns", {})[user_id_str] = datetime.now(pytz.UTC).isoformat()

def check_end_conditions(chat_id_str):
    """Return 'winner' name or None. If winner found, marks battle inactive."""
    battle = BATTLES.get(chat_id_str)
    if not battle or battle["status"] != "active":
        return None
    ghosts_hp = battle["teams"]["ghosts"]["hp"]
    zombies_hp = battle["teams"]["zombies"]["hp"]
    if ghosts_hp <= 0 and zombies_hp <= 0:
        # tie -> no winner
        battle["status"] = "inactive"
        battle["end_at"] = datetime.now(pytz.UTC).isoformat()
        save_battles()
        return "tie"
    if ghosts_hp <= 0:
        battle["status"] = "inactive"
        battle["end_at"] = datetime.now(pytz.UTC).isoformat()
        save_battles()
        return "zombies"
    if zombies_hp <= 0:
        battle["status"] = "inactive"
        battle["end_at"] = datetime.now(pytz.UTC).isoformat()
        save_battles()
        return "ghosts"
    return None

# --------------- Commands ----------------
async def start_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin starts battle in a group. Usage: /start_battle [duration_minutes optional]"""
    chat = update.effective_chat
    user = update.effective_user

    # group-only
    if chat.type == "private":
        await update.message.reply_text("⚔️ Battle events only run in group chats.")
        return

    if not is_admin_user(user.id):
        await update.message.reply_text("❌ Access Denied. Only admin can start the battle.")
        return

    chat_id_str = str(chat.id)
    duration_minutes = None
    if context.args:
        try:
            duration_minutes = int(context.args[0])
            if duration_minutes <= 0:
                raise ValueError("Duration must be positive")
        except:
            await update.message.reply_text("⚠️ Invalid duration. Using default 3 minutes.")
            duration_minutes = None

    battle = init_battle_state(chat_id_str)
    battle["status"] = "active"
    battle["teams"]["ghosts"]["members"] = []
    battle["teams"]["zombies"]["members"] = []
    battle["teams"]["ghosts"]["hp"] = BATTLE_DEFAULT_HP
    battle["teams"]["zombies"]["hp"] = BATTLE_DEFAULT_HP
    battle["teams"]["ghosts"]["damage"] = 0
    battle["teams"]["zombies"]["damage"] = 0
    battle["cooldowns"] = {}
    battle["actions"] = {}  # Track per-user actions {user_id: {"ultimate_blast": bool, "steal_health": bool}}
    battle["started_at"] = datetime.now(pytz.UTC).isoformat()
    battle["end_at"] = (datetime.now(pytz.UTC) + timedelta(minutes=duration_minutes or 3)).isoformat()
    battle["events"] = DEFAULT_EVENT_STATE.copy()
    save_battles()

    # Calculate total duration in seconds
    total_seconds = (duration_minutes * 60) if duration_minutes else 300
    # Schedule auto-end
    try:
        context.job_queue.run_once(
            auto_end_battle_job,
            total_seconds,
            data={"chat_id": chat.id},
            name=f"battle_end_{chat_id_str}"
        )
        # Schedule reminders: 2 minutes (120s) and 30 seconds before end
        if total_seconds >= 150:  # Only schedule 2-min warning if duration allows
            context.job_queue.run_once(
                send_battle_alert,
                total_seconds - 120,
                data={"chat_id": chat.id, "msg": "⏳ 3 minutes remaining! The air grows colder..."},
                name=f"battle_alert_2min_{chat_id_str}"
            )
        if total_seconds >= 30:  # Always try to schedule 30-sec warning
            context.job_queue.run_once(
                send_battle_alert,
                total_seconds - 30,
                data={"chat_id": chat.id, "msg": "⚠️ 30 seconds left! Unleash your final power!"},
                name=f"battle_alert_30sec_{chat_id_str}"
            )
        # Schedule first random event
        schedule_next_event(context.job_queue, chat.id)
    except Exception as e:
        print(f"⚠️ Failed to schedule battle jobs for chat {chat_id_str}: {e}")
        await update.message.reply_text("⚠️ Battle started, but scheduling failed. Check logs.")

    msg = (
        f"🩸 *GHOSTS vs ZOMBIES* has begun!\n\n"
        "Join a side with /join_ghosts or /join_zombies\n"
        "When enough souls gather, battle will rage. Use /battle_status to check the field."
    )
    if duration_minutes:
        msg += f"\n\n⏳ This battle will end in {duration_minutes} minutes."
    else:
        msg += "\n\n⏳ This battle will end in 3 minutes."

    await update.message.reply_text(msg, parse_mode="HTML")



async def join_team_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generic join command; we route based on command name."""
    chat = update.effective_chat
    user = update.effective_user
    cmd = update.message.text.split()[0].lower()
    chat_id_str = str(chat.id)

    if chat.type == "private":
        await update.message.reply_text("Join the battle in the group chat, not private messages.")
        return

    battle = init_battle_state(chat_id_str)
    if battle["status"] != "active":
        await update.message.reply_text("No active battle right now. Admins can start one with /start_battle.")
        return

    # Cooldown check for non-premium users
    now = datetime.now(pytz.UTC)
    user_id_str = str(user.id)
    if not is_premium_user(user_id_str):
        if user_id_str in FACTION_COOLDOWN and (now - FACTION_COOLDOWN[user_id_str]).days < 1:
            await update.message.reply_text(
                f"🎃 {mention(user)} has already joined a faction today! Come back tomorrow MORTAL  \n\n ONLY /PREMIUM HAVE INFINITE USE 👻 👻",
                parse_mode="HTML"
            )
            return
        FACTION_COOLDOWN[user_id_str] = now

    team = None
    if cmd == "/join_ghosts":
        team = "ghosts"
    elif cmd == "/join_zombies":
        team = "zombies"
    else:
        await update.message.reply_text("Usage: /join_ghosts or /join_zombies")
        return

    # Remove from other team if present
    other = "ghosts" if team == "zombies" else "zombies"
    if user_id_str in [m["id"] for m in battle["teams"][other]["members"]]:
        battle["teams"][other]["members"] = [m for m in battle["teams"][other]["members"] if m["id"] != user_id_str]

    # Add if not already in team (including role assignment)
    if user_id_str not in [m["id"] for m in battle["teams"][team]["members"]]:
        role = assign_random_role()
        battle["teams"][team]["members"].append({"id": user_id_str, "name": user.first_name, "role": role})
        save_battles()
        await update.message.reply_text(
            f"{mention(user)} has joined <b>{team.upper()}</b> as <i>{role}</i>!",
            parse_mode="HTML"
        )
    else:
        # display their role if already in
        member = next((m for m in battle["teams"][team]["members"] if m["id"] == user_id_str), None)
        role = member.get("role") if member else "Unknown"
        await update.message.reply_text(
            f"{mention(user)} you are already in <b>{team.upper()}</b> as <i>{role}</i>.",
            parse_mode="HTML"
        )









async def spectral_rush_job(context: ContextTypes.DEFAULT_TYPE):
    """Handles delayed damage for /spectral_rush."""
    chat_id = context.job.data["chat_id"]
    chat_id_str = str(chat_id)
    user_id = context.job.data["user_id"]
    user_name = context.job.data["user_name"]
    user_team = context.job.data["user_team"]
    role = context.job.data["role"]
    battle = BATTLES.get(chat_id_str)
    if not battle or battle.get("status") != "active":
        return
    enemy_team = "zombies" if user_team == "ghosts" else "ghosts"
    base = random.randint(10, 25)
    base += role_damage_bonus(role)
    bm_until = battle["events"].get("blood_moon_until")
    if bm_until:
        try:
            if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                base += 5
        except Exception:
            pass
    soul_bind = battle["events"].get("soul_bind")
    damage_multiplier = 1.0
    if soul_bind and soul_bind["team"] == user_team:
        try:
            if datetime.fromisoformat(soul_bind["until"]) > datetime.now(pytz.UTC):
                damage_multiplier = 0.5
        except Exception:
            pass
    enemy_members = battle["teams"][enemy_team]["members"]
    if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
        msg = f"💨 {user_name}'s spectral rush fades, but an enemy dodged!"
        damage = 0
    else:
        damage = int(base * 1.1 * damage_multiplier)  # Premium multiplier
        battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
        battle["teams"][user_team]["damage"] += damage
        msg = f"💨 {user_name}'s spectral rush strikes — {damage} damage to {enemy_team.upper()}!"
    save_battles()
    winner = check_end_conditions(chat_id_str)
    if winner:
        if winner == "tie":
            msg += "\n☯️ Both teams have fallen into the abyss... It's a tie."
        else:
            text = "GHOSTS" if winner == "ghosts" else "ZOMBIES"
            msg += f"\n🏆 *{text} WIN THE BATTLE!* The other team is vanquished."
    else:
        ghosts_hp = battle["teams"]["ghosts"]["hp"]
        zombies_hp = battle["teams"]["zombies"]["hp"]
        msg += (
            f"\n\n📊 Current HP  \n 👻 GHOSTS: {ghosts_hp} | 🧟 ZOMBIES: {zombies_hp}\n"
            f"🩸 Damage — 👻 {battle['teams']['ghosts']['damage']} | 🧟 {battle['teams']['zombies']['damage']}\n \n use help_move to use cool moves"
            "Use /battle_status to view members and HP."
        )
    try:
        await context.bot.send_animation(chat_id=chat_id, animation=random.choice(COMMAND_GIFS["spectral_rush"]), caption=msg, parse_mode="HTML")
    except Exception:
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")

async def dread_echo_job(context: ContextTypes.DEFAULT_TYPE):
    """Handles delayed damage for /dread_echo."""
    chat_id = context.job.data["chat_id"]
    chat_id_str = str(chat_id)
    user_id = context.job.data["user_id"]
    user_name = context.job.data["user_name"]
    user_team = context.job.data["user_team"]
    role = context.job.data["role"]
    battle = BATTLES.get(chat_id_str)
    if not battle or battle.get("status") != "active":
        return
    enemy_team = "zombies" if user_team == "ghosts" else "ghosts"
    base = random.randint(7, 17)  # Half of initial 15–35
    base += role_damage_bonus(role)
    bm_until = battle["events"].get("blood_moon_until")
    if bm_until:
        try:
            if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                base += 5
        except Exception:
            pass
    soul_bind = battle["events"].get("soul_bind")
    damage_multiplier = 1.0
    if soul_bind and soul_bind["team"] == user_team:
        try:
            if datetime.fromisoformat(soul_bind["until"]) > datetime.now(pytz.UTC):
                damage_multiplier = 0.5
        except Exception:
            pass
    enemy_members = battle["teams"][enemy_team]["members"]
    if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
        msg = f"🌑 {user_name}'s dread echo fades, but an enemy dodged!"
        damage = 0
    else:
        damage = int(base * 1.1 * damage_multiplier)  # Premium multiplier
        battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
        battle["teams"][user_team]["damage"] += damage
        msg = f"🌑 {user_name}'s dread echo resonates — {damage} damage to {enemy_team.upper()}!"
    save_battles()
    winner = check_end_conditions(chat_id_str)
    if winner:
        if winner == "tie":
            msg += "\n☯️ Both teams have fallen into the abyss... It's a tie."
        else:
            text = "GHOSTS" if winner == "ghosts" else "ZOMBIES"
            msg += f"\n🏆 *{text} WIN THE BATTLE!* The other team is vanquished."
    else:
        ghosts_hp = battle["teams"]["ghosts"]["hp"]
        zombies_hp = battle["teams"]["zombies"]["hp"]
        msg += (
            f"\n\n📊 Current HP \n 👻 GHOSTS: {ghosts_hp} | 🧟 ZOMBIES: {zombies_hp}\n"
            f"🩸 Damage — 👻 {battle['teams']['ghosts']['damage']} | 🧟 {battle['teams']['zombies']['damage']}\n"
            "Use /battle_status to view members and HP. \n use help_move to use cool moves"
        )
    try:
        await context.bot.send_animation(chat_id=chat_id, animation=random.choice(COMMAND_GIFS["dread_echo"]), caption=msg, parse_mode="HTML")
    except Exception:
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")

async def reaper_call_job(context: ContextTypes.DEFAULT_TYPE):
    """Handles mini-reaper for /reaper_call."""
    chat_id = context.job.data["chat_id"]
    chat_id_str = str(chat_id)
    user_name = context.job.data["user_name"]
    battle = BATTLES.get(chat_id_str)
    if not battle or battle.get("status") != "active":
        return
    damage_ghosts = random.randint(5, 15)
    damage_zombies = random.randint(5, 15)
    battle["teams"]["ghosts"]["hp"] = max(0, battle["teams"]["ghosts"]["hp"] - damage_ghosts)
    battle["teams"]["zombies"]["hp"] = max(0, battle["teams"]["zombies"]["hp"] - damage_zombies)
    msg = f"💀 {user_name}'s mini-reaper strikes — {damage_ghosts} damage to GHOSTS, {damage_zombies} damage to ZOMBIES!"
    save_battles()
    winner = check_end_conditions(chat_id_str)
    if winner:
        if winner == "tie":
            msg += "\n☯️ Both teams have fallen into the abyss... It's a tie."
        else:
            text = "GHOSTS" if winner == "ghosts" else "ZOMBIES"
            msg += f"\n🏆 *{text} WIN THE BATTLE!* The other team is vanquished."
    else:
        ghosts_hp = battle["teams"]["ghosts"]["hp"]
        zombies_hp = battle["teams"]["zombies"]["hp"]
        msg += (
            f"\n\n📊 Current HP \n 👻 GHOSTS: {ghosts_hp} | 🧟 ZOMBIES: {zombies_hp}\n"
            f"🩸 Damage — 👻 {battle['teams']['ghosts']['damage']} | 🧟 {battle['teams']['zombies']['damage']}\n"
            "Use /battle_status to view members and HP. \n use help_move to use cool moves"
        )
    try:
        await context.bot.send_animation(chat_id=chat_id, animation=random.choice(COMMAND_GIFS["reaper_call"]), caption=msg, parse_mode="HTML")
    except Exception:
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")




COMMAND_GIFS = {
    "haunt": [
        "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExYTNka3o1dXBvZ3BpczRxZHhjemJkZDBkdTg0dTlndDdnZjc0eXJuayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/XGi7sQQZhEa0z9h99D/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExN3o5cTczMTNvaXJzcXlyY21iY2tjMWd4enljNDBscHpkYnpiaWk4bCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/dvZIMlh8kcXnBlS2bw/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExN3o5cTczMTNvaXJzcXlyY21iY2tjMWd4enljNDBscHpkYnpiaWk4bCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/O6kb3Pa3Kgbsc/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExN3o5cTczMTNvaXJzcXlyY21iY2tjMWd4enljNDBscHpkYnpiaWk4bCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/GPvPg9pb7SUx2/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3ZTcxNTllZ2s2YnlueTN5OTVpaHIxOTJjdnNpeGsxbDVpenppbTR1bSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/2Il8Q4wyvRCOLz9m71/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3ZTcxNTllZ2s2YnlueTN5OTVpaHIxOTJjdnNpeGsxbDVpenppbTR1bSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/kEods2IoKO8MVqjId6/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExN3o5cTczMTNvaXJzcXlyY21iY2tjMWd4enljNDBscHpkYnpiaWk4bCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/TmzGmX0c91JUQ/giphy.gif"
    ],
    "infect": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbjY1OGt3dGYwMjh3b2NtdWp3MG55bmp5dzBzcmw2cHl4cjhwa3VqdyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/GQbNswkIXzlvi/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbjY1OGt3dGYwMjh3b2NtdWp3MG55bmp5dzBzcmw2cHl4cjhwa3VqdyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/PmcbF6mbXY8c8Ltm6S/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3ZzhzcGMwd3lqOXlpNnljZmJ0a21sZWY2dzZyeXUzaXc1ejZsZ2FxMyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Tv2LBQ8509D96tme87/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3eWllcjQwbmdpdjNxeW9ucHQ3ajBsbWx2empxb2h6cGh6bWFscTM5ZSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/I1NdzwwKlkvra/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3eWllcjQwbmdpdjNxeW9ucHQ3ajBsbWx2empxb2h6cGh6bWFscTM5ZSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/cWDPy85VoEmIfSpUoy/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3N2Z3cTQ1ZXgyeHhjYXIyeTFhaWlkbHNlZWlhMmIzYTRrMXRiNmU4aSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/gYpCMsy6uPVBu/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbjY1OGt3dGYwMjh3b2NtdWp3MG55bmp5dzBzcmw2cHl4cjhwa3VqdyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/nhklNniaxTXoI/giphy.gif"
    ],
    "revive": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZnh0N2t0bW4xMDV5b3k0NWtpZ2c1djNqcjM1MG1yN20xaHF1djJwciZlcD12MV9naWZzX3NlYXJjaCZjdD1n/mYbDg1HtyU4IvS2AvB/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZnh0N2t0bW4xMDV5b3k0NWtpZ2c1djNqcjM1MG1yN20xaHF1djJwciZlcD12MV9naWZzX3NlYXJjaCZjdD1n/3o7TKSM3u36i6yG4CI/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZjN2eGMyMGF1ZGR4MnFsaWs5MHRsdnRjeWpvOXd5c3p2OXU2Z2dvbiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/tUv2FIiNLxUVZ0hbJV/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExdDUzdzJoOXh2aGdiOHJraXZwZGk0ZW9ldXN6anlkOHQzcHNwd2ZlZyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/3ohs7S2207OksGCMhO/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNjJudzlhNnNpejB1eTQyMzIxODhjMTZrbjl1Nm8wYmE4OXZoNGRnNSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/hAE1jOL4qDJBW3Qcit/giphy.gif"
    ],
    "shield": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcHFraXExbGtmNnp2dTlnaDljc3h4aWR2YmJoaDgxemc1N3Rub2phNCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/UQZBfXcPQSZOQYp0yv/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcHFraXExbGtmNnp2dTlnaDljc3h4aWR2YmJoaDgxemc1N3Rub2phNCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/icJJguU1dJMKHOYbAO/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcHFraXExbGtmNnp2dTlnaDljc3h4aWR2YmJoaDgxemc1N3Rub2phNCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/VxHixRra5rtEMMw7b0/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExdXE0ZzdvOHAzZnppY2t6N2tmcWtiamkzMzd6ZWczYm9pbm9jZTl4ZiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ZnqfvC8BNlAXInRwG1/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNW8wY2g0djZoOHFhd2NuZGVtZHFhbWd0bzY1aWlyN3Q5a2NpZWMyaCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/AWgaY9xpmNE3PBEBLl/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3NmgzbzcwMHB2d3h5dmc2YXZueWttZDI2ZXV6YTJlaTZ6cHIyeWpnYiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/i55Kxr7CSNZSXlGDEm/giphy.gif"
    ],
    "attack_reaper": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNW8zNnA5aWU3NmUzc3o4ZHBkejg2aXJnZ2Q4ZGxxeXk3dW5pMTczNSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/7DrqhPgHUwPz1C35WK/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3aWFndTgydjEyZmxzaGxqNmtldzV1Nndxa3R5cDJmbzNuNzUzYXVwNiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/3o6Zt3veD2LsPfRV2U/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3aWFndTgydjEyZmxzaGxqNmtldzV1Nndxa3R5cDJmbzNuNzUzYXVwNiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/L1D0vKMHiwHY4FXOvO/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3eXhzbzVvNjlseXN4Z2JnMWZmZWVrOXZ2YjBzeHF5ODVnMnB6ank4YiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Y7thXXB9FjeXX5JBSE/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3eTh0MWtuMnVidXVoMnRsb2luM3d1OXdpb2pyd3hqaXJrNGZiNGtkdCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/xT5LMTy630tIuG8rTy/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3eTh0MWtuMnVidXVoMnRsb2luM3d1OXdpb2pyd3hqaXJrNGZiNGtkdCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/hmsTeDsMx5NAX4EVML/giphy.gif"
    ],
    "chill_touch": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExMTNkZzNqeHE0bnk5aXc5dGtqYWIxcDRjMzFlcHh1NjFmM3ppdXFzYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Sck9nw0xmPdnmVn0M6/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExMTNkZzNqeHE0bnk5aXc5dGtqYWIxcDRjMzFlcHh1NjFmM3ppdXFzYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/mbwVnRLXDDGh9zEAsd/giphy.gif"
    ],
    "spirit_burst": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbW5hZG11bjg0Z3p6NzFhMm83eDlieWJkd3pjdXh6ZmJuc3UzeWtldSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/J3T9b6JFfxFT2/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcmNqYnloNTY5OTBhenFldDYxZTNqOXZwbndvcXE3Y3lpMTV6OXB6OCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/skVe8kyj61sqS0RlSZ/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcmNqYnloNTY5OTBhenFldDYxZTNqOXZwbndvcXE3Y3lpMTV6OXB6OCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/V4mGtJcOLEDa98LpzN/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3ZXQzd2p2ZjhmdGdjZnA5NTVyODF2ajQ0eWNwODA4NXkwcXJqZGV3MCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Pn0cUOp5yrnK2M0E1t/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3aWRtbnRrcGJ4cmV5dTVnNzE0NGdldHU3bnltbW5yZ2cwNnJicDhrYyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/8UHNksuROtmXEZemRQ/giphy.gif"
    ],
    "ultimate_blast": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExaWxoYWk1ZDBvNzBtdnlrb3p2a2Rmcjdzdnh3dmdoMzlxN2w4dDczYiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/j4ilcBmGFTlm63BA6w/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3ZHRwazNnb2Zpd3UwYmxwYTgxYXk5YnRqbWFiN3JnaHd3bjlsbTk5cCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Kt7YwOfNSLSDK/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbGR3ZzAwYmR1a3ZvbWx4dGVuYnFlbWttdzBoZ2d0dTJ0bzdqMnAzaCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/oZFDGzlBJg4Hm/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbGR3ZzAwYmR1a3ZvbWx4dGVuYnFlbWttdzBoZ2d0dTJ0bzdqMnAzaCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/iUDymlBqRw8v2xm1lU/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbGR3ZzAwYmR1a3ZvbWx4dGVuYnFlbWttdzBoZ2d0dTJ0bzdqMnAzaCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/j52bGrifXj6rIPEn3f/giphy.gif"
    ],
    "steal_health": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExc2NvdjJzc2QwYjB1bzZtcmt2dnM3YWI5MDF6Zm9sdTRxOWY5MTllYyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/LH0MVLM9uiuSL7lCRc/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExN3BvMGR2eHI1dXdveTJqYXE5NHZwZHJtNXpzZms4MDVoNTljOWw1diZlcD12MV9naWZzX3NlYXJjaCZjdD1n/l8vN5etR8DIoHA0qzV/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExczlqeXZ5c2Zpd2drYTlneTl2dXMwcXIzbWc5N3RvY2g5eGJhNXJ6OSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/rRje0j8001edBi14W3/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExczlqeXZ5c2Zpd2drYTlneTl2dXMwcXIzbWc5N3RvY2g5eGJhNXJ6OSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/3o6wNVzLRWUvBirQs0/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3d2d4aHl5NHppZWY3cWh6a3J3eXQwNWR2anBhaHVva3F4bnJxamd2YyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/0RNX9sXs2aXAkd1JH5/giphy.gif"
    ],
    "dark_pulse": [
        "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExY2llYnhwNHU4eWhjdjliaHdxOGR6cjZjZmo3eDlzOXV6a3Fiem1lYyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/MVixFpu4YigEneLPeW/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZXAxcWoyeGc3dXVvYTZndWNzZm9qbTh6OG1heW5tMGxvNmJ3bGc5NCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/VgBk8EZQILIaPIJymY/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeW8yY3Z3NHpkYm0xNDVoaHJuZ3phOXIxNW95dnJpYjd3aHFmdnBlaiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Sb7z05GQV4WR9q2mMW/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2R0cGc2bmtxejQ0ZHJpcmN5NXo4d3Bua205Nmh6YTQyeXdsaDB5ciZlcD12MV9naWZzX3NlYXJjaCZjdD1n/d3mlFUG5HtdNuH4s/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExOHUzNDh4dnNhOGdtNWVjcmVjcjQzYTFmYjZwNjN3dGMxb25sNWJ4ayZlcD12MV9naWZzX3NlYXJjaCZjdD1n/CbKXgiQvufJyla0dfP/giphy.gif"
    ],
    "hex_curse": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZjdidjhlbjBqOTVvb25nNWd0dm81NzRtZmtwOGtuM3Zzb2dkMzIxMiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ME4mUH5XYQd9u/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHB1a253NGlhZnFiejRsZ2lha2Q4ZHF4cnY3aDNxYmE4anZ4eXE2ayZlcD12MV9naWZzX3NlYXJjaCZjdD1n/2eKtsBB9d8mcI3uA80/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHB1a253NGlhZnFiejRsZ2lha2Q4ZHF4cnY3aDNxYmE4anZ4eXE2ayZlcD12MV9naWZzX3NlYXJjaCZjdD1n/8QEPXgFem3wS5g8El8/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZHN6dmg0dGEzY3hiNm83YXNuNjAwczJiMzdhMWhtN3JkZGZwemthcSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/m25IBu3naOxZJWTP4a/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZHN6dmg0dGEzY3hiNm83YXNuNjAwczJiMzdhMWhtN3JkZGZwemthcSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/d83fGBVVTNUKZTGFVH/giphy.gif"
    ],
    "spectral_rush": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbm5rNDF2cnI3NXFydDUzMWJ6YWYwM3F5c2M2MTNhdDdqODdnbzk3dCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/zwPRprvrP4Lm0/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbm5rNDF2cnI3NXFydDUzMWJ6YWYwM3F5c2M2MTNhdDdqODdnbzk3dCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/iRDkNp3c0FXem0lCCF/giphy.gif"
    ],
    "fear_aura": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeTRrcm84aW1hZzhmcGdtMzBwc3N6enB5NGppM3N3dWRrYmQ0eXFlZCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/zWxXlcFYJZ6BaoL2ce/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeTRrcm84aW1hZzhmcGdtMzBwc3N6enB5NGppM3N3dWRrYmQ0eXFlZCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Jk2V2yN2S4lA6cMlCd/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3ZDRmMXhxdTJmY2Rncm8zNHpwNWFndjdvbWx2eXFmZmY3M2dlZXNvcSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/1qWlkZHTQ9R34Taixl/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeTRrcm84aW1hZzhmcGdtMzBwc3N6enB5NGppM3N3dWRrYmQ0eXFlZCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ZgI5P6a3ZBKgSaqmwl/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExa3diNWJkNzJjaWJrZmt5N2N0emw4bjFzdzVjNXlzZDQwb3A2NXhybyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/zS4OS2WbLEOvDHM1yU/giphy.gif"
    ],
    "grave_pact": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbTR6ZzExOHkwMTUyMTh0cnIxcmZmdnF3N3pqdzJwcXVsbHljM2poeiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/l2JJJ0CP1ZaKairdu/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbTR6ZzExOHkwMTUyMTh0cnIxcmZmdnF3N3pqdzJwcXVsbHljM2poeiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/WIa7F0q7VJTArpBlCr/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbTR6ZzExOHkwMTUyMTh0cnIxcmZmdnF3N3pqdzJwcXVsbHljM2poeiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/QuK14QC8pT8120sTQM/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3NXU4bmFoZ3NsMTB2YjB0cW9sdGxteWJ1bHJubGc2cjBpYXF3Y29jYiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/vKOc8VbZkUS2oAtdQk/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeXl3OTl3YzRiOGJ0dWcxZjRyeWNyam5taGE2MWVtYXBkNmx5MmpvMyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/cmShQtDEjHeRxJQo1s/giphy.gif"
    ],
    "phantom_strike": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeHAxOWlpOTY5aGpibTdrZXI1djZrdmhwcjBweTVpNzg1MG1zN29tZCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/3o6ZsYwYJXYcSKA4ZG/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeHAxOWlpOTY5aGpibTdrZXI1djZrdmhwcjBweTVpNzg1MG1zN29tZCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/XrdEl9CE7VHfa/giphy.gif"
    ],
    "doom_shroud": [
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3Z2l2NThpMnBuM2hpam02cXVoejN1cGc5NHE3M2c5aWtiMXc5b293dSZlcD12MV9naWZzX3JlbGF0ZWQmY3Q9Zw/JszViJEtcmUwpO77v3/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNGtiZGE4Y294cGJiYnI3YXBtOWtoaWxmNGtqMGlvNmJqOHl4dW1ueiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/rJCinmkwVOfouzNJht/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNGtiZGE4Y294cGJiYnI3YXBtOWtoaWxmNGtqMGlvNmJqOHl4dW1ueiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Ryim7YTIm571NRGRth/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNGtiZGE4Y294cGJiYnI3YXBtOWtoaWxmNGtqMGlvNmJqOHl4dW1ueiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/GMM12PBOZ1BmMgJGFz/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNnhhMG1nZzI1bGZ4cjE5cTF2bjd4enl5OGs4ancyaWd2eHFyYmc2NCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/EBiho5DrxUQ75JMcq7/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNnhhMG1nZzI1bGZ4cjE5cTF2bjd4enl5OGs4ancyaWd2eHFyYmc2NCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/iw6aVa0PT5QQYDPVAx/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNnhhMG1nZzI1bGZ4cjE5cTF2bjd4enl5OGs4ancyaWd2eHFyYmc2NCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/SeazCAa6TZdJfd2Sl4/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExMm53ZzE1MDU1MG1xeHJ6NzNzcWpxbTl0Z202NnVvN2hyazIyNWRmMSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/R1m9PxNP0528oYa4W3/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExMm53ZzE1MDU1MG1xeHJ6NzNzcWpxbTl0Z202NnVvN2hyazIyNWRmMSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Yksqr6OJeCRR0VqcAh/giphy.gif"
    ],
    "blood_surge": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHl4Zmw0OGRvOHdidTRsZmJvYmE5N3I1d25waTJnaGE3cHhwcGtqbCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/c8VX61PaB36lI29Vj4/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHl4Zmw0OGRvOHdidTRsZmJvYmE5N3I1d25waTJnaGE3cHhwcGtqbCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/mLGbg0dsgghtsQQmDm/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNHl4Zmw0OGRvOHdidTRsZmJvYmE5N3I1d25waTJnaGE3cHhwcGtqbCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/bpHCkFBkFOmlrKLYYX/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbnFmdmNsNWJ2cDR1MTA5ZXFlZDhwano3cGg4cDhld25rNzdkaWV1ZCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/rPn0Aq49KVSazc3XZu/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3Z3pyNWFjdDQ1YjU3ZDFpNzJsM2cxNGdyMjNoNmczbDZqZzd3OGg4YyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/V9RupScWk3CMf1CXuo/giphy.gif"
        
    ],
    "ghostly_swap": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExenZlMjdjMXR3NWVkanMwZXE1emFkeW92YjBtdjhzd3VnMHkzYmVqNiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/m59zqS6G8jE9Ip4daQ/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExenZlMjdjMXR3NWVkanMwZXE1emFkeW92YjBtdjhzd3VnMHkzYmVqNiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/sAgTPZCbRb0CQ/giphy.gif"
    ],
    "reaper_call": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbmFlcGQ5Y2plM2NobHpoamV5d29jbzN5M2h6MWJ0NXJzNGttcmJpaSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/h5NLPVn3rg0Rq/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbmFlcGQ5Y2plM2NobHpoamV5d29jbzN5M2h6MWJ0NXJzNGttcmJpaSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/u7vcwx7WynnExSb2PS/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbmFlcGQ5Y2plM2NobHpoamV5d29jbzN5M2h6MWJ0NXJzNGttcmJpaSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/8qkD2LxKag836/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbmFlcGQ5Y2plM2NobHpoamV5d29jbzN5M2h6MWJ0NXJzNGttcmJpaSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/dtBOiIvWLct1vii4KF/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3bWtwc2thb2F4dTRza283MWEyNGYxamR1MzU2NWF2cTl4dHliMHZoMiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/3JzJQyMcn3LskjCCyA/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3ZDlmdTE3a2Nzd2hwYmJkdnphdmZ5azk1NmI3cWEzbDQzbDJkcWZrbCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/d8RxIHZVfxIesGVBUZ/giphy.gif"
    ],
    "shadow_bolt": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExa2wzaGd5dzA0Yzh0c2N4b2d2bW8xczZwdGFldWx5MGh2MHFmd3l6YiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/zCkrtY5MU03o3gInU4/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExa2wzaGd5dzA0Yzh0c2N4b2d2bW8xczZwdGFldWx5MGh2MHFmd3l6YiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/pcj2yxch4SyKCYhXtr/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcDY0YjMyYnI3Y2d2YmVmM2dhaGZyM2s3NXAzajJsczg0aGV3dGZnNSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/HHTnOsGp58f1LGc0YO/giphy.gif"
    ],
    "vile_mist": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcHZtbnJjZHN1aTA3aTg0N3BwZ2JuZXdkY3BtNzdvajZueHF0enZnbCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/jOZt5tdGYxzz0H6Nfi/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExeTRxeTVmZTZjMHl4MW8yaGNoMjY0M3NxaTRubWx2aTZ1OTRjNDVnZiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/dz6Nrk35xWP3q/giphy.gif"
    ],
    "spirit_siphon": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYW5uOGx1Z3l0ZXVqNjM2MDc4dW8xeWpsZXhyaWJwZHFucjN4c3duOSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/10IIs7CN98Skw0/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExbmU4MXMxNzI0cXl4aWk0Mnd0M3hkZXJoMWxydjFybzgwZ2owbWxtNCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/QCJlIDkOJDEIctfdzz/giphy.gif"
    ],
    "dread_echo": [
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3NGVtcjVqZ2MyZDd6bGZoYTNiNjU5aGo5anh2MXI2dXpyZmJtcTQxOSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/dyjrpqaUVqCELGuQVr/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExN3U4dzlldWRmcGtkeHV6OWV0dXJmY2VkcWtneHl2MzB1c2l1aWV2cSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/QCJlIDkOJDEIctfdzz/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3emk4cTB3cm4xaGE3cHhvNmJjbGtzZmQ5c2g3Z2xhNnVrcTVndmR6YSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/qb1eHxhUHLdsc/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3Y293cHV6NzVtY3h6bzd2amI3OG9hcWE4aThncGx5cDA0cDFhZzd3dyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/cpkQpkVFOOoNi/giphy.gif"
    ],
    "haunted_mark": [
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExdmYyd2JseTducGd3dmN6NDkwcWNwMXdwYXJncmFiMXVxMTF4cjFhMSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/2Pk9newN8fkbu/giphy.gif",
        "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcmd6M3BydTd5NWJ4NXlucGFlcWliYWMxNjM2bnk1azd2cXpvMnlodyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/4OV1bLOIWwIXRxpXlN/giphy.gif"
    ]
}













async def send_battle_alert(context: ContextTypes.DEFAULT_TYPE):
    """Helper for timed alerts."""
    chat_id = context.job.data["chat_id"]
    msg = context.job.data["msg"]
    try:
        await context.bot.send_message(chat_id=chat_id, text=msg)
    except Exception:
        pass

async def start_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin starts battle in a group. Usage: /start_battle [duration_minutes optional]"""
    chat = update.effective_chat
    user = update.effective_user

    # group-only
    if chat.type == "private":
        await update.message.reply_text("⚔️ Battle events only run in group chats.")
        return

    if not is_admin_user(user.id):
        await update.message.reply_text("❌ Access Denied. Only admin can start the battle.")
        return

    chat_id_str = str(chat.id)
    duration_minutes = None
    if context.args:
        try:
            duration_minutes = int(context.args[0])
            if duration_minutes <= 0:
                raise ValueError("Duration must be positive")
        except:
            await update.message.reply_text("⚠️ Invalid duration. Using default 3 minutes.")
            duration_minutes = None

    battle = init_battle_state(chat_id_str)
    battle["status"] = "active"
    battle["teams"]["ghosts"]["members"] = []
    battle["teams"]["zombies"]["members"] = []
    battle["teams"]["ghosts"]["hp"] = BATTLE_DEFAULT_HP
    battle["teams"]["zombies"]["hp"] = BATTLE_DEFAULT_HP
    battle["teams"]["ghosts"]["damage"] = 0
    battle["teams"]["zombies"]["damage"] = 0
    battle["cooldowns"] = {}
    battle["actions"] = {}  # Track per-user actions
    battle["started_at"] = datetime.now(pytz.UTC).isoformat()
    battle["end_at"] = (datetime.now(pytz.UTC) + timedelta(minutes=duration_minutes or 3)).isoformat()
    battle["events"] = DEFAULT_EVENT_STATE.copy()
    save_battles()

    # Calculate total duration in seconds
    total_seconds = (duration_minutes * 60) if duration_minutes else 300
    # Schedule auto-end
    try:
        context.job_queue.run_once(
            auto_end_battle_job,
            total_seconds,
            data={"chat_id": chat.id},
            name=f"battle_end_{chat_id_str}"
        )
        # Schedule reminders: 2 minutes (120s) and 30 seconds before end
        if total_seconds >= 150:
            context.job_queue.run_once(
                send_battle_alert,
                total_seconds - 120,
                data={"chat_id": chat.id, "msg": "⏳ 2 minutes remaining! The air grows colder..."},
                name=f"battle_alert_2min_{chat_id_str}"
            )
        if total_seconds >= 30:
            context.job_queue.run_once(
                send_battle_alert,
                total_seconds - 30,
                data={"chat_id": chat.id, "msg": "⚠️ 30 seconds left! Unleash your final power!"},
                name=f"battle_alert_30sec_{chat_id_str}"
            )
        # Schedule first random event
        schedule_next_event(context.job_queue, chat.id)
    except Exception as e:
        print(f"⚠️ Failed to schedule battle jobs for chat {chat_id_str}: {e}")
        await update.message.reply_text("⚠️ Battle started, but scheduling failed. Check logs.")

    msg = (
        f"🩸 *GHOSTS vs ZOMBIES* has begun!\n\n"
        "Join a side with /join_ghosts or /join_zombies\n"
        "When enough souls gather, battle will rage. Use /battle_status to check the field.\n"
        "Use /help_move to see all battle actions."
    )
    if duration_minutes:
        msg += f"\n\n⏳ This battle will end in {duration_minutes} minutes."
    else:
        msg += "\n\n⏳ This battle will end in 3 minutes."

    await update.message.reply_text(msg, parse_mode="HTML")

from telegram.ext import ContextTypes
from telegram import Update
import asyncio

async def help_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display all available battle moves with descriptions and auto-delete after 5 seconds."""
    help_text = (
        "<b>👻 SpookyBot Battle Commands 👻</b>\n\n"
        "<b>Free Commands (Available to All):</b>\n"
        "• <b>/haunt</b> (Ghosts only): Deal 8-20 dmg to Zombies.\n"
        "• <b>/infect</b> (Zombies only): Deal 8-20 dmg to Ghosts.\n"
        "• <b>/revive</b>: Heal your team for 10-25 HP.\n"
        "• <b>/shield</b>: Add 5-15 temporary HP to your team.\n"
        "• <b>/attack_reaper</b>: Deal 8-20 dmg to the Reaper when active.\n"
        "• <b>/chill_touch</b>: Deal 10-25 dmg; 50% chance to reduce enemy dmg by 25% for 10s.\n"
        "• <b>/spirit_burst</b>: Deal 15-30 dmg; +5 if your team has more members.\n\n"
        "<b>Premium Commands (Require /premium):</b>\n"
        "• <b>/ultimate_blast</b>: Deal 20-50 dmg. High impact, once per battle.\n"
        "• <b>/steal_health</b>: Deal 20-55 dmg, heal your team for same amount.\n"
        "• <b>/dark_pulse</b>: Deal 15-40 dmg with dark energy.\n"
        "• <b>/hex_curse</b>: Reduce enemy healing by 50% for 15s.\n"
        "• <b>/spectral_rush</b>: Deal 10-25 dmg; strikes again after 5s.\n"
        "• <b>/fear_aura</b>: Paralyze enemy team for 10s.\n"
        "• <b>/grave_pact</b>: Sacrifice 20 HP to deal 30-60 dmg.\n"
        "• <b>/phantom_strike</b>: Deal 25-45 dmg; 10% chance to ignore shields.\n"
        "• <b>/doom_shroud</b>: Enemy actions have 20% miss chance for 15s.\n"
        "• <b>/blood_surge</b>: Boost your team’s next dmg by 1.5x for 10s.\n"
        "• <b>/ghostly_swap</b>: Swap 10-30 HP between teams.\n"
        "• <b>/reaper_call</b>: Summon a Mini-Reaper to strike in 10s.\n"
        "• <b>/shadow_bolt</b>: Deal 20-40 dmg; +5 if your team’s HP is below 50%.\n"
        "• <b>/vile_mist</b>: Enemy actions have 15% fail chance for 10s.\n"
        "• <b>/spirit_siphon</b>: Deal 10-25 dmg, heal for 50% of dmg.\n"
        "• <b>/dread_echo</b>: Deal 15-35 dmg; echoes again after 5s.\n"
        "• <b>/haunted_mark</b>: Enemy’s next dmg action hurts them for 25% for 15s.\n\n"
        "<b>Notes:</b>\n"
        "- All dmg actions are boosted by roles and blood moon.\n"
        "- Premium commands have a 1.1x dmg multiplier.\n"
        "- Cooldown: 30s (24s for Ghoul role).\n"
        "- Use /battle_status to check HP and members.\n"
    )

    # Send the message
    message = await update.message.reply_text(help_text, parse_mode="HTML")

    # Schedule deletion after 5 seconds
    async def delete_message(context: ContextTypes.DEFAULT_TYPE):
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=message.message_id
            )
        except Exception as e:
            print(f"⚠️ Failed to delete /help_move message: {e}")

    try:
        context.job_queue.run_once(
            delete_message,
            15,  # Delay in seconds
            data={"chat_id": update.effective_chat.id, "message_id": message.message_id},
            name=f"delete_help_move_{update.effective_chat.id}_{message.message_id}"
        )
    except Exception as e:
        print(f"⚠️ Failed to schedule deletion for /help_move: {e}")
        await update.message.reply_text("Error scheduling message deletion, but commands displayed.")






async def action_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all battle actions."""
    chat = update.effective_chat
    user = update.effective_user
    cmd = update.message.text.split()[0].lower()
    chat_id_str = str(chat.id)

    if chat.type == "private":
        await update.message.reply_text("Actions must be used in the group battle chat.")
        return

    battle = BATTLES.get(chat_id_str)
    if not battle or battle.get("status") != "active":
        await update.message.reply_text("No active battle in this chat.")
        return

    uid_str = str(user.id)
    user_team = user_in_team(battle, uid_str)
    if not user_team:
        await update.message.reply_text("You are not part of the battle. Join using /join_ghosts or /join_zombies.")
        return

    # Cooldown check
    allowed, rem = can_act(battle, uid_str)
    if not allowed:
        role = get_member_role(battle, user_team, uid_str)
        cd_mult = role_cooldown_mult(role) if role else 1.0
        adjusted = int(rem * cd_mult) if cd_mult < 1.0 else rem
        await update.message.reply_text(f"⏳ Wait {adjusted}s before acting again{' (role cooldown)' if cd_mult < 1.0 else ''}.")
        return

    # Initialize user actions for all commands
    battle["actions"].setdefault(uid_str, {
        "ultimate_blast": False, "steal_health": False, "dark_pulse": False,
        "hex_curse": False, "spectral_rush": False, "fear_aura": False,
        "grave_pact": False, "phantom_strike": False, "doom_shroud": False,
        "blood_surge": False, "ghostly_swap": False, "reaper_call": False,
        "shadow_bolt": False, "vile_mist": False, "spirit_siphon": False,
        "dread_echo": False, "haunted_mark": False, "chill_touch": False,
        "spirit_burst": False
    })

    # Check once-per-battle limit for all actions
    if battle["actions"][uid_str].get(cmd[1:], False):
        await update.message.reply_text(
            f"⏳ {mention(user)} You've already used {cmd} in this battle!",
            parse_mode="HTML"
        )
        return

    # Check premium status for premium commands
    premium_commands = [
        "ultimate_blast", "steal_health", "dark_pulse", "hex_curse", "spectral_rush",
        "fear_aura", "grave_pact", "phantom_strike", "doom_shroud", "blood_surge",
        "ghostly_swap", "reaper_call", "shadow_bolt", "vile_mist", "spirit_siphon",
        "dread_echo", "haunted_mark"
    ]
    if cmd[1:] in premium_commands and not is_premium_user(user.id):
        await update.message.reply_text(
            f"🎃 {mention(user)} Only premium users can use {cmd}! Unlock with /premium.",
            parse_mode="HTML"
        )
        return

    enemy_team = "zombies" if user_team == "ghosts" else "ghosts"
    result_text = ""
    points = 0

    # Check debuffs/buffs
    soul_bind = battle["events"].get("soul_bind")
    damage_multiplier = 1.0
    if soul_bind and soul_bind["team"] == user_team:
        try:
            if datetime.fromisoformat(soul_bind["until"]) > datetime.now(pytz.UTC):
                damage_multiplier = 0.5
        except Exception:
            pass
    doom_shroud = battle["events"].get("doom_shroud")
    miss_chance = 0.2 if doom_shroud and doom_shroud["team"] == user_team and datetime.fromisoformat(doom_shroud["until"]) > datetime.now(pytz.UTC) else 0.0
    vile_mist = battle["events"].get("vile_mist")
    fail_chance = 0.15 if vile_mist and vile_mist["team"] == user_team and datetime.fromisoformat(vile_mist["until"]) > datetime.now(pytz.UTC) else 0.0
    fear_aura = battle["events"].get("fear_aura")
    if fear_aura and fear_aura["team"] == user_team:
        try:
            if datetime.fromisoformat(fear_aura["until"]) > datetime.now(pytz.UTC):
                await update.message.reply_text(f"😱 {mention(user)} is paralyzed by fear aura!")
                return
        except Exception:
            pass
    blood_surge = battle["events"].get("blood_surge")
    surge_multiplier = 1.5 if blood_surge and blood_surge["team"] == user_team and datetime.fromisoformat(blood_surge["until"]) > datetime.now(pytz.UTC) else 1.0
    hex_curse = battle["events"].get("hex_curse")
    heal_multiplier = 0.5 if hex_curse and hex_curse["team"] == user_team and datetime.fromisoformat(hex_curse["until"]) > datetime.now(pytz.UTC) else 1.0
    haunted_mark = battle["events"].get("haunted_mark")
    self_damage = 0.25 if haunted_mark and haunted_mark["team"] == user_team and datetime.fromisoformat(haunted_mark["until"]) > datetime.now(pytz.UTC) else 0.0
    chill_touch = battle["events"].get("chill_touch")
    chill_multiplier = 0.75 if chill_touch and chill_touch["team"] == user_team and datetime.fromisoformat(chill_touch["until"]) > datetime.now(pytz.UTC) else 1.0

    # Handle action failure
    if random.random() < fail_chance:
        set_action_timestamp(battle, uid_str)
        await update.message.reply_text(
            f"🌫️ {mention(user)}'s {cmd} failed due to vile mist!",
            parse_mode="HTML"
        )
        return

# Handle reaper attack
    if cmd == "/attack_reaper":
        reaper = battle["events"].get("reaper")
        if not reaper:
            await update.message.reply_text("There is no Reaper to attack right now.")
            return
        base = random.randint(8, 20)
        role = get_member_role(battle, user_team, uid_str)
        base += role_damage_bonus(role)
        bm_until = battle["events"].get("blood_moon_until")
        if bm_until:
            try:
                if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                    base += 5
            except Exception:
                pass
        reaper["hp"] = max(0, reaper["hp"] - base)
        reaper["last_hit_by"] = {"team": user_team, "user_id": uid_str}
        battle["events"]["reaper"] = reaper
        save_battles()
        result_text = f"⚔️ {mention(user)} strikes THE REAPER for {base} damage!"
        set_action_timestamp(battle, uid_str)
        try:
            gif = random.choice(COMMAND_GIFS["attack_reaper"])
            print(f"Sending GIF for /attack_reaper: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /attack_reaper: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")
        return

    # Regular actions
    role = get_member_role(battle, user_team, uid_str)
    dodge = role_dodge_chance(role) if role else 0.0

    if cmd == "/haunt" and user_team == "ghosts":
        if random.random() < miss_chance:
            result_text = f"👻 {mention(user)}'s haunt missed due to doom shroud!"
            damage = 0
        else:
            base = random.randint(8, 20)
            base += role_damage_bonus(role)
            bm_until = battle["events"].get("blood_moon_until")
            if bm_until:
                try:
                    if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                        base += 5
                except Exception:
                    pass
            enemy_members = battle["teams"][enemy_team]["members"]
            if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
                result_text = f"👻 {mention(user)} tried to haunt, but an enemy dodged!"
                damage = 0
            else:
                damage = int(base * (1.0 if not is_premium_user(user.id) else 1.1) * damage_multiplier * surge_multiplier * chill_multiplier)
                battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
                battle["teams"][user_team]["damage"] += damage
                if self_damage > 0:
                    self_dmg = int(damage * self_damage)
                    battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - self_dmg)
                    result_text = f"👻 {mention(user)} haunts — {damage} damage to ZOMBIES, but {self_dmg} back to GHOSTS due to haunted mark!"
                else:
                    result_text = f"👻 {mention(user)} haunts the dead — {damage} damage to ZOMBIES!"
        battle["actions"][uid_str]["haunt"] = True
        try:
            gif = random.choice(COMMAND_GIFS["haunt"])
            print(f"Sending GIF for /haunt: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /haunt: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/infect" and user_team == "zombies":
        if random.random() < miss_chance:
            result_text = f"🧟 {mention(user)}'s infect missed due to doom shroud!"
            damage = 0
        else:
            base = random.randint(8, 20)
            base += role_damage_bonus(role)
            bm_until = battle["events"].get("blood_moon_until")
            if bm_until:
                try:
                    if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                        base += 5
                except Exception:
                    pass
            enemy_members = battle["teams"][enemy_team]["members"]
            if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
                result_text = f"🧟 {mention(user)} bit — but an enemy dodged!"
                damage = 0
            else:
                damage = int(base * (1.0 if not is_premium_user(user.id) else 1.1) * damage_multiplier * surge_multiplier * chill_multiplier)
                battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
                battle["teams"][user_team]["damage"] += damage
                if self_damage > 0:
                    self_dmg = int(damage * self_damage)
                    battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - self_dmg)
                    result_text = f"🧟 {mention(user)} infects — {damage} damage to GHOSTS, but {self_dmg} back to ZOMBIES due to haunted mark!"
                else:
                    result_text = f"🧟 {mention(user)} bites the living — {damage} damage to GHOSTS!"
        battle["actions"][uid_str]["infect"] = True
        try:
            gif = random.choice(COMMAND_GIFS["infect"])
            print(f"Sending GIF for /infect: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /infect: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/revive":
        base = random.randint(10, 25)
        base += role_heal_bonus(role)
        heal = int(base * heal_multiplier)
        battle["teams"][user_team]["hp"] = min(BATTLE_DEFAULT_HP, battle["teams"][user_team]["hp"] + heal)
        result_text = f"🕯️ {mention(user)} performs a minor ritual — {heal} HP restored to {user_team.upper()}!"
        battle["actions"][uid_str]["revive"] = True
        try:
            gif = random.choice(COMMAND_GIFS["revive"])
            print(f"Sending GIF for /revive: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /revive: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/shield":
        shield = random.randint(5, 15)
        battle["teams"][user_team]["hp"] = min(BATTLE_DEFAULT_HP, battle["teams"][user_team]["hp"] + shield)
        result_text = f"🛡️ {mention(user)} strengthens defenses — {shield} temporary HP to {user_team.upper()}!"
        battle["actions"][uid_str]["shield"] = True
        try:
            gif = random.choice(COMMAND_GIFS["shield"])
            print(f"Sending GIF for /shield: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /shield: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/ultimate_blast" and user_team in ["ghosts", "zombies"]:
        if random.random() < miss_chance:
            result_text = f"💥 {mention(user)}'s ultimate blast missed due to doom shroud!"
            damage = 0
        else:
            base = random.randint(20, 50)
            base += role_damage_bonus(role)
            bm_until = battle["events"].get("blood_moon_until")
            if bm_until:
                try:
                    if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                        base += 5
                except Exception:
                    pass
            enemy_members = battle["teams"][enemy_team]["members"]
            if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
                result_text = f"💥 {mention(user)} unleashes an Ultimate Blast, but an enemy dodged!"
                damage = 0
            else:
                damage = int(base * 1.1 * damage_multiplier * surge_multiplier * chill_multiplier)
                battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
                battle["teams"][user_team]["damage"] += damage
                if self_damage > 0:
                    self_dmg = int(damage * self_damage)
                    battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - self_dmg)
                    result_text = f"💥 {mention(user)} unleashes an *Ultimate Blast* — {damage} damage to {enemy_team.upper()}, but {self_dmg} back to {user_team.upper()} due to haunted mark!"
                else:
                    result_text = f"💥 {mention(user)} unleashes an *Ultimate Blast* — {damage} damage to {enemy_team.upper()}!"
        battle["actions"][uid_str]["ultimate_blast"] = True
        try:
            gif = random.choice(COMMAND_GIFS["ultimate_blast"])
            print(f"Sending GIF for /ultimate_blast: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /ultimate_blast: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/steal_health" and user_team in ["ghosts", "zombies"]:
        if random.random() < miss_chance:
            result_text = f"🩸 {mention(user)}'s health steal missed due to doom shroud!"
            damage = 0
            heal = 0
        else:
            base = random.randint(20, 55)
            base += role_damage_bonus(role)
            bm_until = battle["events"].get("blood_moon_until")
            if bm_until:
                try:
                    if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                        base += 5
                except Exception:
                    pass
            enemy_members = battle["teams"][enemy_team]["members"]
            if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
                result_text = f"🩸 {mention(user)} tries to steal health, but an enemy dodged!"
                damage = 0
                heal = 0
            else:
                damage = int(base * 1.1 * damage_multiplier * surge_multiplier * chill_multiplier)
                heal = damage
                battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
                battle["teams"][user_team]["hp"] = min(BATTLE_DEFAULT_HP, battle["teams"][user_team]["hp"] + heal)
                battle["teams"][user_team]["damage"] += damage
                if self_damage > 0:
                    self_dmg = int(damage * self_damage)
                    battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - self_dmg)
                    result_text = f"🩸 {mention(user)} steals {heal} HP from {enemy_team.upper()} for {user_team.upper()}, but {self_dmg} back to {user_team.upper()} due to haunted mark!"
                else:
                    result_text = f"🩸 {mention(user)} steals {heal} HP from {enemy_team.upper()} for {user_team.upper()}!"
        battle["actions"][uid_str]["steal_health"] = True
        try:
            gif = random.choice(COMMAND_GIFS["steal_health"])
            print(f"Sending GIF for /steal_health: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /steal_health: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/dark_pulse" and user_team in ["ghosts", "zombies"]:
        if random.random() < miss_chance:
            result_text = f"🌑 {mention(user)}'s dark pulse missed due to doom shroud!"
            damage = 0
        else:
            base = random.randint(15, 40)
            base += role_damage_bonus(role)
            bm_until = battle["events"].get("blood_moon_until")
            if bm_until:
                try:
                    if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                        base += 5
                except Exception:
                    pass
            damage = int(base * 1.1 * damage_multiplier * surge_multiplier * chill_multiplier)
            battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
            battle["teams"][user_team]["damage"] += damage
            if self_damage > 0:
                self_dmg = int(damage * self_damage)
                battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - self_dmg)
                result_text = f"🌑 {mention(user)} unleashes a *Dark Pulse* — {damage} damage to {enemy_team.upper()}, but {self_dmg} back to {user_team.upper()} due to haunted mark!"
            else:
                result_text = f"🌑 {mention(user)} unleashes a *Dark Pulse* — {damage} damage to {enemy_team.upper()}!"
        battle["actions"][uid_str]["dark_pulse"] = True
        try:
            gif = random.choice(COMMAND_GIFS["dark_pulse"])
            print(f"Sending GIF for /dark_pulse: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /dark_pulse: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/hex_curse" and user_team in ["ghosts", "zombies"]:
        enemy_members = battle["teams"][enemy_team]["members"]
        if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
            result_text = f"🪄 {mention(user)} tries to cast a hex, but the enemy resisted!"
        else:
            until = datetime.now(pytz.UTC) + timedelta(seconds=20)
            battle["events"]["hex_curse"] = {"team": enemy_team, "until": until.isoformat()}
            result_text = f"🪄 {mention(user)} casts *Hex Curse* — {enemy_team.upper()}’s healing reduced by 50% for 20s!"
        battle["actions"][uid_str]["hex_curse"] = True
        try:
            gif = random.choice(COMMAND_GIFS["hex_curse"])
            print(f"Sending GIF for /hex_curse: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /hex_curse: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/spectral_rush" and user_team in ["ghosts", "zombies"]:
        if random.random() < miss_chance:
            result_text = f"💨 {mention(user)}'s spectral rush missed due to doom shroud!"
            damage = 0
        else:
            base = random.randint(10, 25)
            base += role_damage_bonus(role)
            bm_until = battle["events"].get("blood_moon_until")
            if bm_until:
                try:
                    if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                        base += 5
                except Exception:
                    pass
            enemy_members = battle["teams"][enemy_team]["members"]
            if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
                result_text = f"💨 {mention(user)} charges with *Spectral Rush*, but an enemy dodged!"
                damage = 0
            else:
                damage = int(base * 1.1 * damage_multiplier * surge_multiplier * chill_multiplier)
                battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
                battle["teams"][user_team]["damage"] += damage
                if self_damage > 0:
                    self_dmg = int(damage * self_damage)
                    battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - self_dmg)
                    result_text = f"💨 {mention(user)} charges with *Spectral Rush* — {damage} damage to {enemy_team.upper()}, but {self_dmg} back to {user_team.upper()} due to haunted mark!"
                else:
                    result_text = f"💨 {mention(user)} charges with *Spectral Rush* — {damage} damage to {enemy_team.upper()}!"
                try:
                    context.job_queue.run_once(
                        spectral_rush_job,
                        5,
                        data={
                            "chat_id": chat.id,
                            "user_id": uid_str,
                            "user_name": user.first_name,
                            "user_team": user_team,
                            "role": role
                        },
                        name=f"spectral_rush_{chat_id_str}_{uid_str}"
                    )
                    result_text += f" Second strike incoming in 5s!"
                except Exception as e:
                    print(f"⚠️ Failed to schedule spectral_rush for chat {chat_id_str}: {e}")
        battle["actions"][uid_str]["spectral_rush"] = True
        try:
            gif = random.choice(COMMAND_GIFS["spectral_rush"])
            print(f"Sending GIF for /spectral_rush: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /spectral_rush: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/fear_aura" and user_team in ["ghosts", "zombies"]:
        enemy_members = battle["teams"][enemy_team]["members"]
        if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
            result_text = f"😱 {mention(user)} tries to cast a fear aura, but the enemy resisted!"
        else:
            until = datetime.now(pytz.UTC) + timedelta(seconds=10)
            battle["events"]["fear_aura"] = {"team": enemy_team, "until": until.isoformat()}
            result_text = f"😱 {mention(user)} casts *Fear Aura* — {enemy_team.upper()} paralyzed for 10s!"
        battle["actions"][uid_str]["fear_aura"] = True
        try:
            gif = random.choice(COMMAND_GIFS["fear_aura"])
            print(f"Sending GIF for /fear_aura: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /fear_aura: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/grave_pact" and user_team in ["ghosts", "zombies"]:
        if random.random() < miss_chance:
            result_text = f"⚰️ {mention(user)}'s grave pact missed due to doom shroud!"
            damage = 0
        else:
            base = random.randint(30, 60)
            base += role_damage_bonus(role)
            bm_until = battle["events"].get("blood_moon_until")
            if bm_until:
                try:
                    if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                        base += 5
                except Exception:
                    pass
            enemy_members = battle["teams"][enemy_team]["members"]
            if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
                result_text = f"⚰️ {mention(user)} tries a *Grave Pact*, but an enemy dodged!"
                damage = 0
            else:
                damage = int(base * 1.1 * damage_multiplier * surge_multiplier * chill_multiplier)
                battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - 20)
                battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
                battle["teams"][user_team]["damage"] += damage
                if self_damage > 0:
                    self_dmg = int(damage * self_damage)
                    battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - self_dmg)
                    result_text = f"⚰️ {mention(user)} sacrifices 20 HP for *Grave Pact* — {damage} damage to {enemy_team.upper()}, but {self_dmg} back to {user_team.upper()} due to haunted mark!"
                else:
                    result_text = f"⚰️ {mention(user)} sacrifices 20 HP for *Grave Pact* — {damage} damage to {enemy_team.upper()}!"
        battle["actions"][uid_str]["grave_pact"] = True
        try:
            gif = random.choice(COMMAND_GIFS["grave_pact"])
            print(f"Sending GIF for /grave_pact: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /grave_pact: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/phantom_strike" and user_team in ["ghosts", "zombies"]:
        if random.random() < miss_chance:
            result_text = f"👻 {mention(user)}'s phantom strike missed due to doom shroud!"
            damage = 0
        else:
            base = random.randint(25, 45)
            base += role_damage_bonus(role)
            bm_until = battle["events"].get("blood_moon_until")
            if bm_until:
                try:
                    if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                        base += 5
                except Exception:
                    pass
            enemy_members = battle["teams"][enemy_team]["members"]
            ignore_shield = random.random() < 0.1
            if not ignore_shield and enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
                result_text = f"👻 {mention(user)} unleashes a *Phantom Strike*, but an enemy dodged!"
                damage = 0
            else:
                damage = int(base * 1.1 * damage_multiplier * surge_multiplier * chill_multiplier)
                battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
                battle["teams"][user_team]["damage"] += damage
                if self_damage > 0:
                    self_dmg = int(damage * self_damage)
                    battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - self_dmg)
                    result_text = f"👻 {mention(user)} unleashes a *Phantom Strike* — {damage} damage to {enemy_team.upper()}{' (shield ignored)' if ignore_shield else ''}, but {self_dmg} back to {user_team.upper()} due to haunted mark!"
                else:
                    result_text = f"👻 {mention(user)} unleashes a *Phantom Strike* — {damage} damage to {enemy_team.upper()}{' (shield ignored)' if ignore_shield else ''}!"
        battle["actions"][uid_str]["phantom_strike"] = True
        try:
            gif = random.choice(COMMAND_GIFS["phantom_strike"])
            print(f"Sending GIF for /phantom_strike: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /phantom_strike: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/doom_shroud" and user_team in ["ghosts", "zombies"]:
        enemy_members = battle["teams"][enemy_team]["members"]
        if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
            result_text = f"🌫️ {mention(user)} tries to cast a doom shroud, but the enemy resisted!"
        else:
            until = datetime.now(pytz.UTC) + timedelta(seconds=15)
            battle["events"]["doom_shroud"] = {"team": enemy_team, "until": until.isoformat()}
            result_text = f"🌫️ {mention(user)} casts *Doom Shroud* — {enemy_team.upper()}’s actions have 20% chance to miss for 15s!"
        battle["actions"][uid_str]["doom_shroud"] = True
        try:
            gif = random.choice(COMMAND_GIFS["doom_shroud"])
            print(f"Sending GIF for /doom_shroud: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /doom_shroud: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/blood_surge" and user_team in ["ghosts", "zombies"]:
        enemy_members = battle["teams"][enemy_team]["members"]
        if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
            result_text = f"🩸 {mention(user)} tries to invoke a blood surge, but the enemy resisted!"
        else:
            until = datetime.now(pytz.UTC) + timedelta(seconds=10)
            battle["events"]["blood_surge"] = {"team": user_team, "until": until.isoformat()}
            result_text = f"🩸 {mention(user)} invokes *Blood Surge* — {user_team.upper()}’s next damage action boosted 1.5x for 10s!"
        battle["actions"][uid_str]["blood_surge"] = True
        try:
            gif = random.choice(COMMAND_GIFS["blood_surge"])
            print(f"Sending GIF for /blood_surge: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /blood_surge: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/ghostly_swap" and user_team in ["ghosts", "zombies"]:
        enemy_members = battle["teams"][enemy_team]["members"]
        if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
            result_text = f"🔄 {mention(user)} tries to swap spirits, but the enemy resisted!"
        else:
            amount = random.randint(10, 30)
            battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - amount)
            battle["teams"][enemy_team]["hp"] = min(BATTLE_DEFAULT_HP, battle["teams"][enemy_team]["hp"] + amount)
            result_text = f"🔄 {mention(user)} performs *Ghostly Swap* — swaps {amount} HP between {user_team.upper()} and {enemy_team.upper()}!"
        battle["actions"][uid_str]["ghostly_swap"] = True
        try:
            gif = random.choice(COMMAND_GIFS["ghostly_swap"])
            print(f"Sending GIF for /ghostly_swap: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /ghostly_swap: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/reaper_call" and user_team in ["ghosts", "zombies"]:
        enemy_members = battle["teams"][enemy_team]["members"]
        if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
            result_text = f"💀 {mention(user)} tries to summon a mini-reaper, but the enemy disrupted it!"
        else:
            try:
                context.job_queue.run_once(
                    reaper_call_job,
                    10,
                    data={
                        "chat_id": chat.id,
                        "user_name": user.first_name
                    },
                    name=f"reaper_call_{chat_id_str}_{uid_str}"
                )
                result_text = f"💀 {mention(user)} summons a *Mini-Reaper* — it will strike both teams in 10s!"
            except Exception as e:
                print(f"⚠️ Failed to schedule reaper_call for chat {chat_id_str}: {e}")
                result_text = f"💀 {mention(user)} tried to summon a mini-reaper, but the ritual failed!"
        battle["actions"][uid_str]["reaper_call"] = True
        try:
            gif = random.choice(COMMAND_GIFS["reaper_call"])
            print(f"Sending GIF for /reaper_call: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /reaper_call: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/shadow_bolt" and user_team in ["ghosts", "zombies"]:
        if random.random() < miss_chance:
            result_text = f"⚡ {mention(user)}'s shadow bolt missed due to doom shroud!"
            damage = 0
        else:
            base = random.randint(20, 40)
            base += role_damage_bonus(role)
            if battle["teams"][user_team]["hp"] < BATTLE_DEFAULT_HP * 0.5:
                base += 5
            bm_until = battle["events"].get("blood_moon_until")
            if bm_until:
                try:
                    if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                        base += 5
                except Exception:
                    pass
            enemy_members = battle["teams"][enemy_team]["members"]
            if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
                result_text = f"⚡ {mention(user)} fires a *Shadow Bolt*, but an enemy dodged!"
                damage = 0
            else:
                damage = int(base * 1.1 * damage_multiplier * surge_multiplier * chill_multiplier)
                battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
                battle["teams"][user_team]["damage"] += damage
                if self_damage > 0:
                    self_dmg = int(damage * self_damage)
                    battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - self_dmg)
                    result_text = f"⚡ {mention(user)} fires a *Shadow Bolt* — {damage} damage to {enemy_team.upper()}, but {self_dmg} back to {user_team.upper()} due to haunted mark!"
                else:
                    result_text = f"⚡ {mention(user)} fires a *Shadow Bolt* — {damage} damage to {enemy_team.upper()}!"
        battle["actions"][uid_str]["shadow_bolt"] = True
        try:
            gif = random.choice(COMMAND_GIFS["shadow_bolt"])
            print(f"Sending GIF for /shadow_bolt: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /shadow_bolt: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/vile_mist" and user_team in ["ghosts", "zombies"]:
        enemy_members = battle["teams"][enemy_team]["members"]
        if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
            result_text = f"🌫️ {mention(user)} tries to cast *Vile Mist*, but the enemy resisted!"
        else:
            until = datetime.now(pytz.UTC) + timedelta(seconds=10)
            battle["events"]["vile_mist"] = {"team": enemy_team, "until": until.isoformat()}
            result_text = f"🌫️ {mention(user)} casts *Vile Mist* — {enemy_team.upper()}’s actions have 15% chance to fail for 10s!"
        battle["actions"][uid_str]["vile_mist"] = True
        try:
            gif = random.choice(COMMAND_GIFS["vile_mist"])
            print(f"Sending GIF for /vile_mist: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /vile_mist: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/spirit_siphon" and user_team in ["ghosts", "zombies"]:
        if random.random() < miss_chance:
            result_text = f"🩸 {mention(user)}'s spirit siphon missed due to doom shroud!"
            damage = 0
            heal = 0
        else:
            base = random.randint(10, 25)
            base += role_damage_bonus(role)
            bm_until = battle["events"].get("blood_moon_until")
            if bm_until:
                try:
                    if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                        base += 5
                except Exception:
                    pass
            enemy_members = battle["teams"][enemy_team]["members"]
            if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
                result_text = f"🩸 {mention(user)} tries to siphon spirits, but an enemy dodged!"
                damage = 0
                heal = 0
            else:
                damage = int(base * 1.1 * damage_multiplier * surge_multiplier * chill_multiplier)
                heal = int(damage * 0.5)
                battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
                battle["teams"][user_team]["hp"] = min(BATTLE_DEFAULT_HP, battle["teams"][user_team]["hp"] + heal)
                battle["teams"][user_team]["damage"] += damage
                if self_damage > 0:
                    self_dmg = int(damage * self_damage)
                    battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - self_dmg)
                    result_text = f"🩸 {mention(user)} siphons {damage} damage from {enemy_team.upper()}, heals {heal} HP for {user_team.upper()}, but {self_dmg} back to {user_team.upper()} due to haunted mark!"
                else:
                    result_text = f"🩸 {mention(user)} siphons {damage} damage from {enemy_team.upper()}, heals {heal} HP for {user_team.upper()}!"
        battle["actions"][uid_str]["spirit_siphon"] = True
        try:
            gif = random.choice(COMMAND_GIFS["spirit_siphon"])
            print(f"Sending GIF for /spirit_siphon: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /spirit_siphon: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/dread_echo" and user_team in ["ghosts", "zombies"]:
        if random.random() < miss_chance:
            result_text = f"🌑 {mention(user)}'s dread echo missed due to doom shroud!"
            damage = 0
        else:
            base = random.randint(15, 35)
            base += role_damage_bonus(role)
            bm_until = battle["events"].get("blood_moon_until")
            if bm_until:
                try:
                    if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                        base += 5
                except Exception:
                    pass
            enemy_members = battle["teams"][enemy_team]["members"]
            if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
                result_text = f"🌑 {mention(user)} unleashes a *Dread Echo*, but an enemy dodged!"
                damage = 0
            else:
                damage = int(base * 1.1 * damage_multiplier * surge_multiplier * chill_multiplier)
                battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
                battle["teams"][user_team]["damage"] += damage
                if self_damage > 0:
                    self_dmg = int(damage * self_damage)
                    battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - self_dmg)
                    result_text = f"🌑 {mention(user)} unleashes a *Dread Echo* — {damage} damage to {enemy_team.upper()}, but {self_dmg} back to {user_team.upper()} due to haunted mark!"
                else:
                    result_text = f"🌑 {mention(user)} unleashes a *Dread Echo* — {damage} damage to {enemy_team.upper()}!"
                try:
                    context.job_queue.run_once(
                        dread_echo_job,
                        5,
                        data={
                            "chat_id": chat.id,
                            "user_id": uid_str,
                            "user_name": user.first_name,
                            "user_team": user_team,
                            "role": role
                        },
                        name=f"dread_echo_{chat_id_str}_{uid_str}"
                    )
                    result_text += f" Second echo incoming in 5s!"
                except Exception as e:
                    print(f"⚠️ Failed to schedule dread_echo for chat {chat_id_str}: {e}")
        battle["actions"][uid_str]["dread_echo"] = True
        try:
            gif = random.choice(COMMAND_GIFS["dread_echo"])
            print(f"Sending GIF for /dread_echo: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /dread_echo: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/haunted_mark" and user_team in ["ghosts", "zombies"]:
        enemy_members = battle["teams"][enemy_team]["members"]
        if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
            result_text = f"🪬 {mention(user)} tries to place a haunted mark, but the enemy resisted!"
        else:
            until = datetime.now(pytz.UTC) + timedelta(seconds=15)
            battle["events"]["haunted_mark"] = {"team": enemy_team, "until": until.isoformat()}
            result_text = f"🪬 {mention(user)} places a *Haunted Mark* — {enemy_team.upper()}’s next damage action hurts them for 25% for 15s!"
        battle["actions"][uid_str]["haunted_mark"] = True
        try:
            gif = random.choice(COMMAND_GIFS["haunted_mark"])
            print(f"Sending GIF for /haunted_mark: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /haunted_mark: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/chill_touch" and user_team in ["ghosts", "zombies"]:
        if random.random() < miss_chance:
            result_text = f"❄️ {mention(user)}'s chill touch missed due to doom shroud!"
            damage = 0
        else:
            base = random.randint(10, 25)
            base += role_damage_bonus(role)
            bm_until = battle["events"].get("blood_moon_until")
            if bm_until:
                try:
                    if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                        base += 5
                except Exception:
                    pass
            enemy_members = battle["teams"][enemy_team]["members"]
            if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
                result_text = f"❄️ {mention(user)} casts *Chill Touch*, but an enemy dodged!"
                damage = 0
            else:
                damage = int(base * (1.0 if not is_premium_user(user.id) else 1.1) * damage_multiplier * surge_multiplier * chill_multiplier)
                battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
                battle["teams"][user_team]["damage"] += damage
                if random.random() < 0.5:
                    until = datetime.now(pytz.UTC) + timedelta(seconds=10)
                    battle["events"]["chill_touch"] = {"team": enemy_team, "until": until.isoformat()}
                    chill_text = f" {enemy_team.upper()}’s next actions deal 25% less damage for 10s!"
                else:
                    chill_text = ""
                if self_damage > 0:
                    self_dmg = int(damage * self_damage)
                    battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - self_dmg)
                    result_text = f"❄️ {mention(user)} casts *Chill Touch* — {damage} damage to {enemy_team.upper()}{chill_text}, but {self_dmg} back to {user_team.upper()} due to haunted mark!"
                else:
                    result_text = f"❄️ {mention(user)} casts *Chill Touch* — {damage} damage to {enemy_team.upper()}{chill_text}!"
        battle["actions"][uid_str]["chill_touch"] = True
        try:
            gif = random.choice(COMMAND_GIFS["chill_touch"])
            print(f"Sending GIF for /chill_touch: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /chill_touch: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    elif cmd == "/spirit_burst" and user_team in ["ghosts", "zombies"]:
        if random.random() < miss_chance:
            result_text = f"💥 {mention(user)}'s spirit burst missed due to doom shroud!"
            damage = 0
        else:
            base = random.randint(15, 30)
            base += role_damage_bonus(role)
            if len(battle["teams"][user_team]["members"]) > len(battle["teams"][enemy_team]["members"]):
                base += 5
            bm_until = battle["events"].get("blood_moon_until")
            if bm_until:
                try:
                    if datetime.fromisoformat(bm_until) > datetime.now(pytz.UTC):
                        base += 5
                except Exception:
                    pass
            enemy_members = battle["teams"][enemy_team]["members"]
            if enemy_members and random.random() < (role_dodge_chance(get_member_role(battle, enemy_team, random.choice(enemy_members)["id"]))):
                result_text = f"💥 {mention(user)} unleashes a *Spirit Burst*, but an enemy dodged!"
                damage = 0
            else:
                damage = int(base * (1.0 if not is_premium_user(user.id) else 1.1) * damage_multiplier * surge_multiplier * chill_multiplier)
                battle["teams"][enemy_team]["hp"] = max(0, battle["teams"][enemy_team]["hp"] - damage)
                battle["teams"][user_team]["damage"] += damage
                if self_damage > 0:
                    self_dmg = int(damage * self_damage)
                    battle["teams"][user_team]["hp"] = max(0, battle["teams"][user_team]["hp"] - self_dmg)
                    result_text = f"💥 {mention(user)} unleashes a *Spirit Burst* — {damage} damage to {enemy_team.upper()}, but {self_dmg} back to {user_team.upper()} due to haunted mark!"
                else:
                    result_text = f"💥 {mention(user)} unleashes a *Spirit Burst* — {damage} damage to {enemy_team.upper()}!"
        battle["actions"][uid_str]["spirit_burst"] = True
        try:
            gif = random.choice(COMMAND_GIFS["spirit_burst"])
            print(f"Sending GIF for /spirit_burst: {gif}")
            await update.message.reply_animation(
                animation=gif,
                caption=result_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send GIF for /spirit_burst: {e}")
            await update.message.reply_text(result_text, parse_mode="HTML")

    else:
        await update.message.reply_text("That action is not allowed for your team or is unknown.")
        return

    # Set action timestamp (respect role cooldowns)
    set_action_timestamp(battle, uid_str)
    save_battles()

    # Check reaper and end conditions
    winner = check_end_conditions(chat_id_str)
    if winner:
        if winner == "tie":
            await update.message.reply_text("☯️ Both teams have fallen into the abyss... It's a tie.")
        else:
            text = "GHOSTS" if winner == "ghosts" else "ZOMBIES"
            await update.message.reply_text(f"🏆 *{text} WIN THE BATTLE!* The other team is vanquished.", parse_mode="HTML")
        return

    # Announce result and HP/damage summary
    ghosts_hp = battle["teams"]["ghosts"]["hp"]
    zombies_hp = battle["teams"]["zombies"]["hp"]
    announce = (
        f"{result_text}\n\n"
        f"📊 Current HP \n 👻 GHOSTS: {ghosts_hp} | 🧟 ZOMBIES: {zombies_hp}\n"
        f"🩸 Damage — 👻 {battle['teams']['ghosts']['damage']} | 🧟 {battle['teams']['zombies']['damage']}\n"
        "Use /battle_status to view members and HP. \n use help_move to use cool moves"
    )
    await update.message.reply_text(announce, parse_mode="HTML")






async def battle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("Battle status is available in the group chat only.")
        return
    chat_id_str = str(chat.id)
    battle = BATTLES.get(chat_id_str)
    if not battle or battle.get("status") != "active":
        await update.message.reply_text("No active battle right now.")
        return

    ghosts = battle["teams"]["ghosts"]["members"]
    zombies = battle["teams"]["zombies"]["members"]
    ghosts_list = ", ".join([f"[{m['name']}]({m['id']})" for m in ghosts]) if ghosts else "—"
    zombies_list = ", ".join([f"[{m['name']}]({m['id']})" for m in zombies]) if zombies else "—"
    await update.message.reply_text(
        f"📜 *BATTLE STATUS*\n\n"
        f"👻 GHOSTS ({len(ghosts)}): {ghosts_list}\n"
        f"🧟 ZOMBIES ({len(zombies)}): {zombies_list}\n\n"
        f"💉 HP — 👻 {battle['teams']['ghosts']['hp']} | 🧟 {battle['teams']['zombies']['hp']}\n",
        parse_mode="HTML"
    )

async def end_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin ends the battle early"""
    chat = update.effective_chat
    user = update.effective_user
    if not is_admin_user(user.id):
        await update.message.reply_text("❌ Access Denied.")
        return
    chat_id_str = str(chat.id)
    battle = BATTLES.get(chat_id_str)
    if not battle or battle.get("status") != "active":
        await update.message.reply_text("No active battle to end.")
        return

    battle["status"] = "inactive"
    battle["end_at"] = datetime.now(pytz.UTC).isoformat()
    save_battles()

    winner = decide_winner_by_hp(chat_id_str)
    update_leaderboard_on_win(chat_id_str, winner)
    summary = build_battle_summary(chat_id_str, winner)
    append_battle_history(summary)

    if winner == "ghosts":
        text = "GHOSTS"
    elif winner == "zombies":
        text = "ZOMBIES"
    else:
        text = "DRAW"

    await update.message.reply_text(f"🛑 Battle ended by admin. Result: *{text}*", parse_mode="HTML")




def decide_winner_by_hp(chat_id_str):
    battle = BATTLES.get(chat_id_str)
    ghosts_hp = battle["teams"]["ghosts"]["hp"]
    zombies_hp = battle["teams"]["zombies"]["hp"]
    if ghosts_hp > zombies_hp:
        return "ghosts"
    elif zombies_hp > ghosts_hp:
        return "zombies"
    else:
        return "tie"


# --------- New persistence files for leaderboard and history ----------
LEADERBOARD_FILE = "leaderboard.json"
BATTLE_HISTORY_FILE = "battle_history.json"

def load_leaderboard():
    try:
        if os.path.exists(LEADERBOARD_FILE):
            with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load leaderboard: {e}")
    return {}

def save_leaderboard(lb):
    try:
        with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
            json.dump(lb, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save leaderboard: {e}")

def append_battle_history(record):
    try:
        history = []
        if os.path.exists(BATTLE_HISTORY_FILE):
            with open(BATTLE_HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        history.append(record)
        with open(BATTLE_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to append battle history: {e}")

# ---------- Roles and Random Events configuration ----------
ROLES = {
    "Specter": {"damage_bonus": 5, "heal_bonus": 0, "cooldown_mult": 1.0, "dodge_chance": 0.0},
    "Necromancer": {"damage_bonus": 0, "heal_bonus": 10, "cooldown_mult": 1.0, "dodge_chance": 0.0},
    "Ghoul": {"damage_bonus": 0, "heal_bonus": 0, "cooldown_mult": 0.8, "dodge_chance": 0.0},
    "Wraith": {"damage_bonus": 0, "heal_bonus": 0, "cooldown_mult": 1.0, "dodge_chance": 0.20},
}
EVENTS_POOL = [
    # event_id, description, function to apply (we will handle by id)
    "cursed_fog",     # both teams lose HP
    "spirit_blessing",# one team heals
    "blood_moon",     # attacks +bonus damage for a short period (we'll mark a temp flag)
    "artifact_rain",  # small random HP to random members
    "spawn_reaper"    # spawn mini-boss
]
# temporary buffs stored per-battle as flags (e.g. blood_moon_duration)
DEFAULT_EVENT_STATE = {
         "blood_moon_until": None,
         "reaper": None,
         "soul_bind": None,
         "hex_curse": None,
         "doom_shroud": None,
         "fear_aura": None,
         "blood_surge": None,
         "haunted_mark": None,
         "chill_touch": None
    }


def assign_random_role():
    return random.choice(list(ROLES.keys()))


# ---------- Apply role perks helpers ----------
def get_member_role(battle, team_name, user_id_str):
    members = battle["teams"][team_name]["members"]
    m = next((x for x in members if x["id"] == user_id_str), None)
    return m.get("role") if m else None

def role_damage_bonus(role):
    return ROLES.get(role, {}).get("damage_bonus", 0)

def role_heal_bonus(role):
    return ROLES.get(role, {}).get("heal_bonus", 0)

def role_cooldown_mult(role):
    return ROLES.get(role, {}).get("cooldown_mult", 1.0)

def role_dodge_chance(role):
    return ROLES.get(role, {}).get("dodge_chance", 0.0)

# ---------- Random event engine ----------

def schedule_next_event(job_queue, chat_id, min_delay=30, max_delay=60, allow_skip=True):
    """
    Schedule the next random event for chat_id.
    - min_delay, max_delay control the random range.
    - allow_skip: if True keeps the small chance to skip scheduling (useful to reduce spam).
    """
    delay = random.randint(min_delay, max_delay)
    try:
        print(f"[Events] Scheduling next event for chat {chat_id} in {delay}s")
        job_queue.run_once(battle_event_job, delay, data={"chat_id": chat_id})
    except Exception as e:
        print(f"⚠️ Failed to schedule event for chat {chat_id}: {e}")

async def force_event_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /force_event cursed_fog  (or spirit_blessing, blood_moon, artifact_rain, spawn_reaper)"""
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("Use this in a group chat.")
        return
    chat_id_str = str(chat.id)
    battle = BATTLES.get(chat_id_str)
    if not battle or battle.get("status") != "active":
        await update.message.reply_text("No active battle in this chat.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /force_event <event_name>")
        return
    event = context.args[0]
    # temporarily call battle_event_job logic in-sync: create a fake context with same shape
    class Dummy:
        data = {"chat_id": chat.id}
        job = type("J", (), {"data": {"chat_id": chat.id}})
        job_queue = context.job_queue
    # set EVENTS_POOL to only the requested event for immediate use
    prev_pool = EVENTS_POOL.copy()
    try:
        if event not in EVENTS_POOL:
            await update.message.reply_text("Unknown event. Options: " + ", ".join(EVENTS_POOL))
            return
        # run a single event immediately
        # we reuse battle_event_job but with event forced: directly apply logic here for simplicity
        if event == "cursed_fog":
            dmg = 10
            old_g = battle["teams"]["ghosts"]["hp"]
            old_z = battle["teams"]["zombies"]["hp"]
            battle["teams"]["ghosts"]["hp"] = max(0, old_g - dmg)
            battle["teams"]["zombies"]["hp"] = max(0, old_z - dmg)
            save_battles()
            await update.message.reply_text(f"💀 Forced: Cursed Fog applied — both teams lose {dmg} HP! (G {old_g}->{battle['teams']['ghosts']['hp']}, Z {old_z}->{battle['teams']['zombies']['hp']})", parse_mode="HTML")
            return
        # you can implement other forced events similarly if needed
        await update.message.reply_text("Forced event processed.", parse_mode="HTML")
    finally:
        EVENTS_POOL[:] = prev_pool

async def battle_event_job(context: ContextTypes.DEFAULT_TYPE):
    """Apply a random event during the battle and reschedule next event (verbose + robust)."""
    chat_id = context.job.data["chat_id"]
    chat_id_str = str(chat_id)
    print(f"[Events] battle_event_job fired for chat {chat_id_str} at {datetime.now(pytz.UTC).isoformat()}")

    try:
        battle = BATTLES.get(chat_id_str)
        if not battle or battle.get("status") != "active":
            print(f"[Events] No active battle for chat {chat_id_str}, cancelling event.")
            return

        # pick event
        event = random.choice(EVENTS_POOL)
        # optionally keep a small skip chance (set to 0 during testing)
        if False:  # set to False to disable skipping entirely; change to True if you want skipping back
            if random.random() < 0.08:
                print("[Events] Random skip triggered; scheduling next event.")
                schedule_next_event(context.job_queue, chat_id)
                return

        # apply event effects
        msg = ""
        if event == "cursed_fog":
            dmg = 10
            old_g = battle["teams"]["ghosts"]["hp"]
            old_z = battle["teams"]["zombies"]["hp"]
            battle["teams"]["ghosts"]["hp"] = max(0, old_g - dmg)
            battle["teams"]["zombies"]["hp"] = max(0, old_z - dmg)
            msg = f"💀 *Cursed Fog* sweeps the field — both teams lose {dmg} HP!"
            print(f"[Events] cursed_fog applied: ghosts {old_g}->{battle['teams']['ghosts']['hp']}, zombies {old_z}->{battle['teams']['zombies']['hp']}")
        elif event == "spirit_blessing":
            team = random.choice(["ghosts", "zombies"])
            heal = 15
            old = battle["teams"][team]["hp"]
            battle["teams"][team]["hp"] = min(BATTLE_DEFAULT_HP, battle["teams"][team]["hp"] + heal)
            msg = f"🕯️ *Spirit Blessing* — {team.upper()} gain {heal} HP!"
            print(f"[Events] spirit_blessing applied to {team}: {old}->{battle['teams'][team]['hp']}")
        elif event == "blood_moon":
            until = datetime.now(pytz.UTC) + timedelta(seconds=20)
            battle["events"]["blood_moon_until"] = until.isoformat()
            msg = "🌕 *Blood Moon* rises — all attacks deal +5 damage for 20s!"
            print(f"[Events] blood_moon active until {until.isoformat()}")
        elif event == "artifact_rain":
            heal = 8
            recipients = []
            for team in ["ghosts", "zombies"]:
                members = battle["teams"][team]["members"]
                if members:
                    member = random.choice(members)
                    recipients.append((team, member))
                    battle["teams"][team]["hp"] = min(BATTLE_DEFAULT_HP, battle["teams"][team]["hp"] + heal)
            if recipients:
                msg = "🎁 *Artifact Rain* — small blessings fall on the field!"
                print(f"[Events] artifact_rain applied to teams: {', '.join(set(t for t,_ in recipients))}")
            else:
                msg = "🎁 The winds tried to bring artifacts, but no one was there to catch them."
                print("[Events] artifact_rain found no recipients.")
        elif event == "spawn_reaper":
            if not battle["events"].get("reaper"):
                reaper = {"hp": 80, "spawned_at": datetime.now(pytz.UTC).isoformat(), "deadline": (datetime.now(pytz.UTC)+timedelta(seconds=30)).isoformat(), "last_hit_by": None}
                battle["events"]["reaper"] = reaper
                msg = "☠️ *THE REAPER* has appeared! Both teams must attack the Reaper within 30s or suffer punishment! \n <b>USE /attack_reaper TO STRIKE NOW!!</b>"
                print(f"[Events] Reaper spawned for chat {chat_id_str}: {reaper}")
                try:
                    context.job_queue.run_once(resolve_reaper_job, 30, data={"chat_id": chat_id})
                except Exception as e:
                    print(f"⚠️ Failed to schedule reaper resolution: {e}")
            else:
                msg = "☠️ The Reaper stirs... but it is already present."
                print("[Events] spawn_reaper attempted but reaper already present.")
        else:
            msg = "A strange wind blows... nothing significant."
            print(f"[Events] unknown event '{event}' chosen.")

        # persist and notify chat
        save_battles()
        try:
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
        except Exception as e:
            print(f"⚠️ Failed to send event message to chat {chat_id}: {e}")

        # schedule next event if battle still active
        schedule_next_event(context.job_queue, chat_id)

    except Exception as ex:
        print(f"⚠️ Exception inside battle_event_job for chat {chat_id}: {ex}")
        try:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ An event failed to run (see server logs).")
        except:
            pass


async def resolve_reaper_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    chat_id_str = str(chat_id)
    battle = BATTLES.get(chat_id_str)
    if not battle or battle.get("status") != "active":
        # clear reaper if any
        if battle:
            battle["events"]["reaper"] = None
            save_battles()
        return

    reaper = battle["events"].get("reaper")
    if not reaper:
        return

    # if reaper hp > 0 -> not defeated
    if reaper["hp"] > 0:
        # punishment: both teams lose 15 HP
        dmg = 15
        battle["teams"]["ghosts"]["hp"] = max(0, battle["teams"]["ghosts"]["hp"] - dmg)
        battle["teams"]["zombies"]["hp"] = max(0, battle["teams"]["zombies"]["hp"] - dmg)
        msg = f"💀 The Reaper was not defeated — both teams suffer {dmg} HP!"
    else:
        # defeated: last hitter gets team HP bonus
        last = reaper.get("last_hit_by")  # dict with {team, user_id}
        if last:
            team = last["team"]
            bonus = 20
            battle["teams"][team]["hp"] = min(BATTLE_DEFAULT_HP, battle["teams"][team]["hp"] + bonus)
            msg = f"🏆 The Reaper was slain! {team.upper()} gains {bonus} HP thanks to the final strike!"
        else:
            msg = "The Reaper fell by unknown hands, but no one claims credit."

    # clear reaper
    battle["events"]["reaper"] = None
    save_battles()
    try:
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
    except Exception:
        pass



def update_leaderboard_on_win(chat_id_str, winner_team):
    lb = load_leaderboard()
    battle = BATTLES.get(chat_id_str)
    if not battle:
        return
    if winner_team in ("ghosts", "zombies"):
        winners = battle["teams"][winner_team]["members"]
        for m in winners:
            uid = m["id"]
            lb[uid] = lb.get(uid, 0) + 1
    save_leaderboard(lb)

def build_battle_summary(chat_id_str, winner_team):
    battle = BATTLES.get(chat_id_str)
    if not battle:
        return {}
    summary = {
        "chat": chat_id_str,
        "started_at": battle.get("started_at"),
        "ended_at": battle.get("end_at"),
        "winner": winner_team,
        "ghosts_hp": battle["teams"]["ghosts"]["hp"],
        "zombies_hp": battle["teams"]["zombies"]["hp"],
        "ghosts_damage": battle["teams"]["ghosts"].get("damage", 0),
        "zombies_damage": battle["teams"]["zombies"].get("damage", 0),
        "ghosts_members": battle["teams"]["ghosts"]["members"],
        "zombies_members": battle["teams"]["zombies"]["members"],
        "events": battle.get("events")
    }
    return summary



async def auto_end_battle_job(context: ContextTypes.DEFAULT_TYPE):
    """Auto-end battle after scheduled time and decide winner by HP."""
    chat_id = context.job.data["chat_id"]
    chat_id_str = str(chat_id)
    battle = BATTLES.get(chat_id_str)

    if not battle or battle.get("status") != "active":
        print(f"[AutoEnd] Skipped for chat {chat_id_str}: No active battle")
        return

    # Mark battle as ended
    battle["status"] = "inactive"
    battle["end_at"] = datetime.now(pytz.UTC).isoformat()
    save_battles()

    winner = decide_winner_by_hp(chat_id_str)
    update_leaderboard_on_win(chat_id_str, winner)
    summary = build_battle_summary(chat_id_str, winner)
    append_battle_history(summary)

    ghosts_hp = battle["teams"]["ghosts"]["hp"]
    zombies_hp = battle["teams"]["zombies"]["hp"]
    if winner == "ghosts":
        msg = (
            f"⏰ Time’s up!\n\n"
            f"🏆 *GHOSTS* emerge victorious with {ghosts_hp} HP left!\n"
            f"💀 ZOMBIES crumble with {zombies_hp} HP remaining.\n\n"
            f"🧾 Summary \n Ghosts Damage: {battle['teams']['ghosts']['damage']} | Zombies Damage: {battle['teams']['zombies']['damage']} \n /leaderboard - check the winners \n /battle_history - To check las epic fight"
        )
    elif winner == "zombies":
        msg = (
            f"⏰ Time’s up!\n\n"
            f"🏆 *ZOMBIES* devoured the spirits with {zombies_hp} HP left!\n"
            f"👻 GHOSTS fade away with {ghosts_hp} HP remaining.\n\n"
            f"🧾 Summary \n Ghosts Damage: {battle['teams']['ghosts']['damage']} | Zombies Damage: {battle['teams']['zombies']['damage']} \n /leaderboard - check the winners \n /battle_history - To check las epic fight"
        )
    else:
        msg = (
            f"⏰ Time’s up!\n\n"
            f"☯️ Both sides are evenly matched — it’s a DRAW!\n"
            f"👻 {ghosts_hp} HP | 🧟 {zombies_hp} HP\n\n"
            f"🧾 Summary \n Ghosts Damage: {battle['teams']['ghosts']['damage']} | Zombies Damage: {battle['teams']['zombies']['damage']} \n /leaderboard - check the winners \n /battle_history - To check las epic fight"
        )

    try:
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
        print(f"[AutoEnd] Battle ended for chat {chat_id_str}: {winner}")
    except Exception as e:
        print(f"⚠️ Failed to send auto-end message to chat {chat_id_str}: {e}")
    try:
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
    except Exception:
        pass






















































# ===== GHOSTS • WIZARDS • TROLLS MINI-GAME =====
# ===== GHOSTS • WIZARDS • TROLLS MINI-GAME =====
GWT_COOLDOWN = {}  # {user_id: datetime of last play}
ACTIVE_GWT_GAMES = {}  # {chat_id: {"players": {user_id: choice}, "message_id": id, "started_at": datetime}}

async def gwt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a GWT match in a group"""
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    username = update.effective_user.first_name

    if int(chat_id) > 0:
        await update.message.reply_text("⚔️ This game can only be played in groups!")
        return

    # Cooldown check
    now = datetime.now()
    if not is_premium_user(user_id):
        if user_id in GWT_COOLDOWN and (now - GWT_COOLDOWN[user_id]).days < 1:
            await update.message.reply_text(
                "🎃 You’ve already played *Ghosts–Wizards–Trolls* today! Come back tomorrow MORTAL  \n\n ONLY /PREMIUM HAVE INFINITE USE 👻 👻",
                parse_mode="HTML"
            )
            return
        GWT_COOLDOWN[user_id] = now

    # Initialize game
    ACTIVE_GWT_GAMES[chat_id] = {
        "players": {},
        "message_id": None,
        "started_at": now
    }
    keyboard = [
        [
            InlineKeyboardButton("👻 Ghost", callback_data="gwt_ghost"),
            InlineKeyboardButton("🧙 Wizard", callback_data="gwt_wizard"),
            InlineKeyboardButton("🧌 Troll", callback_data="gwt_troll"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sent = await update.message.reply_text(
        "⚔️ *GHOSTS • WIZARDS • TROLLS* ⚔️\n\n"
        "Choose your creature and prepare for battle!\n"
        "👻 Ghosts scare Trolls\n"
        "🧙 Wizards outspell Ghosts\n"
        "🧌 Trolls crush Wizards\n\n"
        "_You have 30 seconds to choose!_",
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
    ACTIVE_GWT_GAMES[chat_id]["message_id"] = sent.message_id

    # Schedule automatic resolution after 30 seconds
    context.job_queue.run_once(
        resolve_gwt_round,
        30,
        data={"chat_id": chat_id},
        name=f"gwt_resolve_{chat_id}"
    )
    print(f"-> GWT game started in chat {chat_id}, scheduled resolution in 30s")

async def handle_gwt_choice(query, user_id, choice):
    """Handle button press"""
    chat_id = str(query.message.chat_id)
    if chat_id not in ACTIVE_GWT_GAMES:
        await query.answer("❌ No active game right now!")
        return

    ACTIVE_GWT_GAMES[chat_id]["players"][user_id] = choice
    await query.answer(f"You chose {choice.capitalize()}!")
    print(f"-> User {user_id} chose {choice} in chat {chat_id}")

async def resolve_gwt_round(context: ContextTypes.DEFAULT_TYPE, chat_id: str = None):
    """Resolve one round and announce results"""
    print("-> resolve_gwt_round called")  # Debug: Confirm if function is triggered (for both auto and manual)

    if chat_id is None:
        if context.job:
            chat_id = context.job.data.get("chat_id")
            print(f"-> Automatic GWT resolution triggered for chat {chat_id}")  # Debug: Auto trigger
        if not chat_id:
            print("❌ resolve_gwt_round: No chat_id provided")
            return

    if chat_id not in ACTIVE_GWT_GAMES:
        print(f"❌ No active GWT game in chat {chat_id}")
        return

    data = ACTIVE_GWT_GAMES[chat_id]["players"]
    if not data:
        try:
            await context.bot.send_message(
                chat_id=int(chat_id),
                text="🏆 *ROUND OVER!* 🕒\n\nNo players chose a creature in time! 👻",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Error sending no-players result: {e}")
        del ACTIVE_GWT_GAMES[chat_id]
        return

    winning_relation = {"ghost": "troll", "wizard": "ghost", "troll": "wizard"}
    winner_type = random.choice(list(winning_relation.keys()))

    text = f"🏆 *ROUND OVER!* 🕒\nThe spirits whisper... *{winner_type.upper()}S* prevail!\n\n"
    winners = []

    for uid, choice in data.items():
        if choice == winner_type:
            winners.append(uid)
            update_group_score(chat_id, str(uid), 25, f"User_{uid}")

    if winners:
        names = [f"<a href='{uid}'>Player</a>" for uid in winners]
        text += f"{' , '.join(names)} gained +25 scare points! 🎃"
    else:
        text += "No survivors this round! 👻"

    try:
        await context.bot.send_message(chat_id=int(chat_id), text=text, parse_mode="HTML")
        print(f"-> GWT round resolved in chat {chat_id}: {winner_type} wins")
    except Exception as e:
        print(f"Error sending result: {e}")

    # Clean up game state
    del ACTIVE_GWT_GAMES[chat_id]
    save_group_leaderboard()

async def gwt_resolve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually resolve a GWT round (admin only)"""
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)

    if not is_admin_user(user_id):
        await update.message.reply_text("❌ Only admins can manually resolve games!")
        return

    if chat_id not in ACTIVE_GWT_GAMES:
        await update.message.reply_text("❌ No active GWT game to resolve!")
        return

    print(f"-> Manual GWT resolution triggered for chat {chat_id} by user {user_id}")  # Debug: Manual trigger
    await resolve_gwt_round(context, chat_id=chat_id)
    await update.message.reply_text("✅ Game resolved manually!", parse_mode="HTML")

async def gwt_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explain Ghosts vs Wizards vs Trolls rules"""
    help_text = (
        "👻 *GHOSTS vs WIZARDS vs TROLLS* 💀\n\n"
        "A spooky twist on Rock–Paper–Scissors! 🎃\n\n"
        "🌀 *How to Play:*\n"
        "1. Use /gwt_start to begin in a group.\n"
        "2. Choose your fighter:\n"
        "   👻 Ghost – scares Troll\n"
        "   🧙 Wizard – outspells Ghost\n"
        "   🧌 Troll – crushes Wizard\n\n"
        "⚡ *Battle Rules:*\n"
        "• Ghosts defeat Trolls\n"
        "• Wizards defeat Ghosts\n"
        "• Trolls defeat Wizards\n\n"
        "🏆 *Winners get*: +25 Scare Points!\n"
        "Free players can play once a day 👀\n\n"
        "💎 Premiums? Unlimited chaos! 🔥"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")
















async def treat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast Trick or Treat message to all users with a real Stars payment button"""
    try:
        treat_gifs = [
            "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExOTEwbHF1Z2pwYXZ1MGlpeHV6eXZmbGNuZHVyZmFqMXNjMDJsMHlrNiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/iIXTaiiEf0jy4gHFFZ/giphy.gif",
            "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExOTEwbHF1Z2pwYXZ1MGlpeHV6eXZmbGNuZHVyZmFqMXNjMDJsMHlrNiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/l3vRlrLjERh6RHw6k/giphy.gif",
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3ZXA5a3MyZmV1cGxjMnpoMWo2MDFxenFoN3J6cGZ4bXc2dmVjNjRnMSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/gQYgy1LyYorXvehgWD/giphy.gif",
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3ZXA5a3MyZmV1cGxjMnpoMWo2MDFxenFoN3J6cGZ4bXc2dmVjNjRnMSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/niul6FHcW3JQDg0ZZf/giphy.gif"
        ]

        gif_url = random.choice(treat_gifs)

        # Telegram Stars payment button
        keyboard = [
            [
                InlineKeyboardButton(
                    text="🍬 Treat the Ghost (50⭐)",
                    pay=True  # THIS makes it a real payment button
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message_text = (
            "🎃 <b>TRICK OR TREAT!</b> 👻\n\n"
            "The spooky spirits are restless and need your offering...\n"
            "Click below to drop <b>2 Stars</b> and keep the darkness fed! 🌑\n\n"
            "_Only the brave dare to give the Treat..._ 🍬"
            "JUST A 16YR-OLD DEVELOPER HERE...OR contact ME 😉 @electrokid_1\n"

        )

        count = 0
        for user_id in list(user_data.keys()):
            try:
                await context.bot.send_invoice(
                    chat_id=int(user_id),
                    title="🍬 Treat the Ghost",
                    description="A spooky offering of 50 Stars to feed the restless spirits 👻",
                    payload="treat_donation",
                    provider_token="",  # Leave empty for Stars
                    currency="XTR",  # Telegram Stars currency
                    prices=[LabeledPrice("Treat Offering", 50)],
                    photo_url=gif_url,
                    start_parameter="treatghost",
                    reply_markup=reply_markup
                )
                count += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Failed to send Treat to {user_id}: {e}")

        await update.message.reply_text(f"🎁 Treat broadcast sent to {count} souls! 🕯️")

    except Exception as e:
        print(f"Treat broadcast error: {e}")
        await update.message.reply_text("⚡ Something went wrong while sending the Treats!")


# ===== DONATION BUTTON HANDLER =====
async def handle_donation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Treat button clicks"""
    query = update.callback_query
    user = query.from_user

    try:
        await query.answer("🩸 The spirits accept your offering... 🎃", show_alert=False)

        # Just send a reply — don't edit the GIF message
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text=f"🕯️ Thank you, {user.first_name}! The darkness is pleased by your generosity. 👻"
        )

        # Optional: Log who clicked the button
        print(f"🎁 {user.first_name} (@{user.username}) gave a Treat!")

    except Exception as e:
        print(f"Error handling donation: {e}")





async def rpg_class_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle RPG class selection and create character"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    class_key = query.data.replace("rpg_class_", "")
    
    # FIXED: Initialize user_data entry if missing
    if user_id not in user_data:
        user_data[user_id] = {}
    
    rpg_classes = {
        "ghost_hunter": {"name": "Ghost Hunter", "emoji": "👻", "bonus": "Extra damage vs spirits", "stats": {"sanity": 9, "agility": 7}},
        "occult_scholar": {"name": "Occult Scholar", "emoji": "📚", "bonus": "Better item discovery", "stats": {"knowledge": 10, "magic": 8}},
        "cursed_survivor": {"name": "Cursed Survivor", "emoji": "🔮", "bonus": "Higher fear resistance", "stats": {"fear_resistance": 15, "endurance": 8}},
        "monster_tamer": {"name": "Monster Tamer", "emoji": "🧌", "bonus": "Can befriend some monsters", "stats": {"charm": 9, "strength": 6}}
    }
    
    class_info = rpg_classes.get(class_key, rpg_classes["ghost_hunter"])
    
    # Use first_name as default name
    char_name = query.from_user.first_name or "Adventurer"
    
    # Create character
    user_data[user_id]['rpg_character'] = {
        'name': f"{char_name} the {class_info['name']}",
        'class': class_info['name'],
        'level': 1,
        'experience': 0,
        'fear_resistance': 10,
        'sanity': 100,
        'inventory': [],
        'location': 'haunted_mansion',
        **class_info['stats']  # Add class stats
    }
    user_data[user_id]['rpg_inventory'] = ['Flashlight 🔦']
    user_data[user_id]['rpg_location'] = 'Shadow Forest 🌲'
    user_data[user_id]['rpg_achievements'] = []

    # Save immediately


    # Initialize leaderboard if needed
    username = query.from_user.username or query.from_user.first_name
    if 'init_rpg_leaderboard' in globals():
        init_rpg_leaderboard(user_id, username)

    await query.edit_message_text(
        f"🎉 *CHARACTER CREATED!* ⚔️\n\n"
        f"**Name:** {user_data[user_id]['rpg_character']['name']}\n"
        f"**Class:** {class_info['name']}\n"
        f"**Level:** 1\n"
        f"**Sanity:** 100/100\n\n"
        f"Your adventure begins! Use /adventure to start your first quest.\n\n"
        f"⭐ EXP: 0/100\n\n"
        f"✨ <b>Class Bonus:</b> {class_info['bonus']}\n\n"
        f"<b>STARTING GEAR:</b>\n"
        f"• Flashlight 🔦 - Reveals hidden secrets\n\n"
        f"<b>LOCATION:</b> Shadow Forest 🌲\n\n"
        f"🌑 <b>Your horror adventure begins...</b>\n\n"
        f"Use /adventure to start your first quest!\n"
        f"Use /stats to check stats\n"
        f"Use /inventory to check items\n"
        f"Use /use_item to use item\n"
        f"Use /craft to make item\n"
        f"Use /locations to open new locations\n"
        f"Use /achievements to view achievements\n"
        f"Use /leaderboard to check leaderboard rank",
        parse_mode='HTML'
    )

    print(f"✅ RPG character created for {user_id} - Class: {class_info['name']}")




async def scare_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group scare competition leaderboard"""
    chat_id = str(update.effective_chat.id)
    
    if int(chat_id) > 0:
        await update.message.reply_text("🏆 This command works in groups only!", parse_mode='HTML')
        return
    
    leaderboard = init_group_leaderboard(chat_id)
    
    if not leaderboard:
        await update.message.reply_text("🏆 No scares recorded yet! Be the first!", parse_mode='HTML')
        return
    
    # SORT BY SCORE
    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1]['score'], reverse=True)
    
    leaderboard_text = "🏆 *GROUP SCARE LEADERBOARD* 👻\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (username, data) in enumerate(sorted_leaderboard[:10]):
        score = data['score']
        medal = medals[i] if i < len(medals) else f"{i+1}."
        user_tier = get_user_tier(score)
        
        leaderboard_text += f"{medal} {user_tier['color']} *{username}* - {score} pts\n"
    
    await update.message.reply_text(leaderboard_text, parse_mode='HTML')








# ===== PREMIUM PLANS CONFIG =====
PREMIUM_PLANS = {
    "24h": {
        "stars": 99,
        "hours": 24,
        "name": "24-Hour Pass",
        "description": "Unlock all premium features for 24 hours - Perfect for testing!"
    },
    "7d": {
        "stars": 299, 
        "hours": 168,
        "name": "7-Day Trial", 
        "description": "Full access for 7 days - Best for Halloween week!"
    },
    "1month": {
        "stars": 999,
        "hours": 720,
        "name": "1-Month Access 🏆 BEST VALUE",
        "description": "Full premium access for 30 days - Only 33 Stars/day!"
    }
}

# ===== HUGGING FACE IMAGE EDITING SYSTEM =====
# ===== WORKING IMAGE TRANSFORMATION SYSTEM =====
class WorkingImageTransformer:
    def __init__(self):
        try:
            self.client = Client("Selfit/ImageEditPro")
            print("✅ ImageEditPro API loaded successfully!")
        except Exception as e:
            print(f"❌ ImageEditPro API failed: {e}")
            self.client = None
    
    def validate_image_file(self, file_path):
        """Validate that the image file exists and is readable"""
        try:
            if not file_path or not os.path.exists(file_path):
                print(f"❌ File doesn't exist: {file_path}")
                return False
            
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                print(f"❌ File is empty: {file_path}")
                return False
                
            print(f"✅ File validated: {file_path} ({file_size} bytes)")
            return True
            
        except Exception as e:
            print(f"❌ File validation error: {e}")
            return False
    
    def transform_image(self, image_path, prompt):
        """Transform image using the correct /edit_image_interface endpoint"""
        if not self.client:
            print("❌ API client not available")
            return None
            
        try:
            print(f"-> Transforming image with prompt: {prompt[:80]}...")
            
            # Use the CORRECT endpoint that exists
            result = self.client.predict(
                input_image=handle_file(image_path),
                prompt=prompt,
                api_name="/edit_image_interface"  # This is the working endpoint!
            )
            
            print(f"-> Raw API result: {result}")  # Debug the full response
            
            if result:
                print(f"✅ API returned result type: {type(result)}")
                
                # Handle different response formats
                if isinstance(result, (tuple, list)) and len(result) > 0:
                    edited_image_data = result[0]
                    image_path = self.extract_image_path(edited_image_data)
                    
                    if image_path and self.validate_image_file(image_path):
                        print(f"✅ Final image path: {image_path}")
                        return image_path
                    else:
                        print(f"❌ Extracted path doesn't exist: {image_path}")
                        return None
                else:
                    # Try to extract from the result directly
                    image_path = self.extract_image_path(result)
                    if image_path and self.validate_image_file(image_path):
                        print(f"✅ Final image path: {image_path}")
                        return image_path
            else:
                print("❌ No result from API")
                return None
                
        except Exception as e:
            print(f"❌ Image transformation error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def extract_image_path(self, image_dict):
        """Extract image path from the API response dictionary"""
        try:
            print(f"-> Extracting image path from: {image_dict}")  # Debug log
            
            # Handle different response formats
            if isinstance(image_dict, dict):
                # Try different possible keys for the image path
                if 'path' in image_dict and image_dict['path']:
                    print(f"✅ Found path: {image_dict['path']}")
                    return image_dict['path']
                elif 'url' in image_dict and image_dict['url']:
                    print(f"✅ Found URL: {image_dict['url']}")
                    return self.download_from_url(image_dict['url'])
                elif 'name' in image_dict and image_dict['name']:
                    print(f"✅ Found name: {image_dict['name']}")
                    return image_dict['name']
                elif 'image' in image_dict and image_dict['image']:
                    # Some APIs nest the image data
                    if isinstance(image_dict['image'], dict):
                        return self.extract_image_path(image_dict['image'])
                    else:
                        return image_dict['image']
            
            # If it's a string, it might already be the file path
            elif isinstance(image_dict, str):
                print(f"✅ String path: {image_dict}")
                if os.path.exists(image_dict):
                    return image_dict
                else:
                    # Try to find the file with different extensions
                    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                        possible_path = image_dict if image_dict.endswith(ext) else image_dict + ext
                        if os.path.exists(possible_path):
                            print(f"✅ Found with extension: {possible_path}")
                            return possible_path
            
            # If we have a tuple/list, check the first element
            elif isinstance(image_dict, (tuple, list)) and len(image_dict) > 0:
                print(f"✅ Checking list/tuple: {image_dict[0]}")
                return self.extract_image_path(image_dict[0])
                
            print(f"❌ Could not extract image path from: {image_dict}")
            return None
            
        except Exception as e:
            print(f"❌ Error extracting image path: {e}")
            return None
    
    def download_from_url(self, url):
        """Download image from URL"""
        try:
            print(f"-> Downloading from URL: {url}")
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                    temp_file.write(response.content)
                    return temp_file.name
            return None
        except Exception as e:
            print(f"❌ URL download error: {e}")
            return None

# Create global instance
image_editor = WorkingImageTransformer()




def validate_image_file(self, file_path):
    """Validate that the image file exists and is readable"""
    try:
        if not file_path or not os.path.exists(file_path):
            print(f"❌ File doesn't exist: {file_path}")
            return False
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            print(f"❌ File is empty: {file_path}")
            return False
            
        print(f"✅ File validated: {file_path} ({file_size} bytes)")
        return True
        
    except Exception as e:
        print(f"❌ File validation error: {e}")
        return False


def extract_image_path(self, image_dict):
    """Extract image path from the API response dictionary"""
    try:
        print(f"-> Extracting image path from: {image_dict}")  # Debug log
        
        # Handle different response formats
        if isinstance(image_dict, dict):
            # Try different possible keys for the image path
            if 'path' in image_dict and image_dict['path']:
                print(f"✅ Found path: {image_dict['path']}")
                return image_dict['path']
            elif 'url' in image_dict and image_dict['url']:
                print(f"✅ Found URL: {image_dict['url']}")
                return self.download_from_url(image_dict['url'])
            elif 'name' in image_dict and image_dict['name']:
                print(f"✅ Found name: {image_dict['name']}")
                return image_dict['name']
            elif 'image' in image_dict and image_dict['image']:
                # Some APIs nest the image data
                if isinstance(image_dict['image'], dict):
                    return self.extract_image_path(image_dict['image'])
                else:
                    return image_dict['image']
        
        # If it's a string, it might already be the file path
        elif isinstance(image_dict, str):
            print(f"✅ String path: {image_dict}")
            if os.path.exists(image_dict):
                return image_dict
            else:
                # Try to find the file with different extensions
                for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    possible_path = image_dict if image_dict.endswith(ext) else image_dict + ext
                    if os.path.exists(possible_path):
                        print(f"✅ Found with extension: {possible_path}")
                        return possible_path
        
        # If we have a tuple/list, check the first element
        elif isinstance(image_dict, (tuple, list)) and len(image_dict) > 0:
            print(f"✅ Checking list/tuple: {image_dict[0]}")
            return self.extract_image_path(image_dict[0])
            
        print(f"❌ Could not extract image path from: {image_dict}")
        return None
        
    except Exception as e:
        print(f"❌ Error extracting image path: {e}")
        return None
# Enhanced horror transformation prompts
HORROR_PROMPTS = {
    "vampire": " maintain skin tone ,pale face, red eyes, sharp fangs, l, cinematic lighting, highly detailed, blood from lips",
    "zombie": "transform this person into a rotting zombie with decaying flesh, wounds, greenish skin, gruesome details, walking dead, infection, horror makeup, photorealistic, portrait, do not change background, part of face normal",
    "ghost": "transform this person into an ethereal ghost, transparent, floating, haunted spirit, misty, glowing eyes, supernatural, ghostly apparition, pale, ethereal glow, horror photography, portrait, do not change background, part of face normal",
    "monster": ", claws, fangs, monstrous creature, dark fantasy, terrifying, detailed anatomy, horror creature design, portrait, do not change background, part of face normal",
    "eldritch": ", Give the person alot of multiple eyes on the face, horror, creepy,dark, misty , paint style ",
    "werewolf": "sharp yellow eyes, , sharp claws, wolf teeth, wolf ear, scary  ",
    "demon": "demon, horns, red skin, fiery eyes, hellspawn",
    "witch": " warts,  pointed hat, green glowing eyes, creepy smile,hard en",
}

# ===== PREMIUM USER MANAGEMENT =====
def init_user_premium(user_id):
    """Initialize premium data for user"""
    if user_id not in user_data:
        user_data[user_id] = {}
    
    if 'premium' not in user_data[user_id]:
        user_data[user_id]['premium'] = {
            'active': False,
            'type': None,
            'expires_at': None,
            'purchases': []
        }

def is_premium_user(user_id):
    """Check if user has active premium"""
    if user_id not in user_data:
        return False
    
    if 'premium' not in user_data[user_id]:
        return False
    
    premium_data = user_data[user_id]['premium']
    
    if not premium_data['active']:
        return False
    
    # Check if premium has expired
    if premium_data['expires_at'] and datetime.now() > premium_data['expires_at']:
        premium_data['active'] = False
        return False
    
    return True

def activate_premium(user_id, premium_type, duration_hours):
    """Activate premium for user - FIXED VERSION"""
    # Ensure user_data exists for this user
    if user_id not in user_data:
        user_data[user_id] = {
            'nickname': f"User {user_id}",
            'joined': datetime.now().isoformat(),
            'premium': {'active': False, 'type': None, 'expires_at': None, 'purchases': []},
            'scares': 0,
            'rpg_character': None,
            'achievements': []
        }
    
    # Ensure premium structure exists
    if 'premium' not in user_data[user_id]:
        user_data[user_id]['premium'] = {
            'active': False,
            'type': None,
            'expires_at': None,
            'purchases': []
        }
    
    # Calculate expiration - FIXED: Only set if duration_hours > 0
    expires_at = None
    if duration_hours > 0:
        expires_at = datetime.now() + timedelta(hours=duration_hours)
    
    # Get existing purchases or create empty list
    existing_purchases = user_data[user_id]['premium'].get('purchases', [])
    
    # Update premium data
    user_data[user_id]['premium'] = {
        'active': True,
        'type': premium_type,
        'expires_at': expires_at,  # This can be None if no duration
        'purchases': existing_purchases + [{
            'type': premium_type,
            'purchased_at': datetime.now(),
            'expires_at': expires_at  # This can be None
        }]
    }
    
    print(f"-> Premium activated for user {user_id}: {premium_type} for {duration_hours}h")


def get_user_usage(user_id):
    """Get or initialize user usage data"""
    if user_id not in user_data:
        user_data[user_id] = {}
    
    if 'usage' not in user_data[user_id]:
        user_data[user_id]['usage'] = {
            'transformations': 0,
            'stories': 0,
            'last_reset': datetime.now().date()
        }
    
    # Reset daily counts if new day
    if user_data[user_id]['usage']['last_reset'] != datetime.now().date():
        user_data[user_id]['usage'] = {
            'transformations': 0,
            'stories': 0,
            'last_reset': datetime.now().date()
        }
    
    return user_data[user_id]['usage']

def can_use_transformation(user_id):
    """Check if user can use transformation"""
    if is_premium_user(user_id):
        return True
    
    usage = get_user_usage(user_id)
    return usage['transformations'] < 2

def can_use_story(user_id):
    """Check if user can use story"""
    if is_premium_user(user_id):
        return True
    
    usage = get_user_usage(user_id)
    return usage['stories'] < 1

def increment_usage(user_id, usage_type):
    """Increment usage counter"""
    usage = get_user_usage(user_id)
    if usage_type == 'transformation':
        usage['transformations'] += 1
    elif usage_type == 'story':
        usage['stories'] += 1

# ===== STARS PAYMENT HANDLERS =====
async def handle_stars_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Stars payment requests"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data
    
    plan_key = action.replace("stars_", "")
    
    if plan_key in PREMIUM_PLANS:
        plan = PREMIUM_PLANS[plan_key]
        
        try:
            # Send Stars payment invoice
            await query.message.reply_invoice(
                title=f"🎃 {plan['name']}",
                description=plan["description"],
                payload=f"premium_{plan_key}_{user_id}",
                currency="XTR",
                prices=[LabeledPrice(label=plan["name"], amount=plan["stars"])],
                start_parameter=f"premium_{plan_key}",
                need_name=False,
                need_phone_number=False,
                need_email=False,
                need_shipping_address=False,
                is_flexible=False
            )
            print(f"-> Stars invoice sent for {plan['name']} to user {user_id}")
            
        except Exception as e:
            print(f"Stars payment error: {e}")
            await query.message.reply_text("❌ Payment error - try again! 🔮")

async def handle_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pre-checkout for Stars payments"""
    query = update.pre_checkout_query
    try:
        await context.bot.answer_pre_checkout_query(
            pre_checkout_query_id=query.id,
            ok=True
        )
        print(f"✅ Pre-checkout approved for user {query.from_user.id}")
    except Exception as e:
        print(f"❌ Pre-checkout error: {e}")

async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle successful Stars payments"""
    user_id = update.effective_user.id  # FIXED: Keep as int for consistency
    payment = update.message.successful_payment
    
    print(f"💰 Stars payment received: {payment.total_amount / 100} Stars from user {user_id}")
    
    # Extract plan from payload (safer split)
    try:
        payload_parts = payment.invoice_payload.split('_')
        if len(payload_parts) >= 2:
            plan_key = payload_parts[1]
            
            if plan_key in PREMIUM_PLANS:
                plan = PREMIUM_PLANS[plan_key]
                
                # Activate premium (with error check)
                try:
                    activate_premium(user_id, plan['name'], plan['hours'])  # Assumes this sets user_data
                except NameError:
                    print("❌ activate_premium not defined—skipping activation")
                
                days = plan['hours'] // 24
                await update.message.reply_text(
                    f"🎉 *STARS PAYMENT SUCCESSFUL!* 💫\n\n"
                    f"**{plan['name']}** activated!\n"
                    f"💰 **Paid:** {payment.total_amount / 100} Stars\n"
                    f"⏰ **Duration:** {days if days > 0 else plan['hours']} {'days' if days > 0 else 'hours'}\n\n"
                    f"🔓 **Premium Unlocked!** Enjoy unlimited nightmares! 👻",
                    parse_mode='HTML'
                )
                
                # Save with your functions (error-safe)
                try:
                    save_user_data()
                    smart_save(user_id)  # If defined; skip if not
                except Exception as e:
                    print(f"❌ Save failed after payment: {e}")
                
                return  # Success—bail early
                
            else:
                print(f"❌ Invalid plan_key: {plan_key}")
                await update.message.reply_text("❌ Invalid plan—contact admin!")
                return
        else:
            print(f"❌ Bad payload: {payment.invoice_payload}")
            await update.message.reply_text("❌ Payment error—retry /premium!")
            return
    except Exception as e:
        print(f"❌ Payment handler error: {e}")
        await update.message.reply_text("❌ Something went wrong—admin notified!")
        return
        
# ===== PREMIUM COMMAND =====
async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium options with pure Stars payment"""
    keyboard = [
        [InlineKeyboardButton("💫 99 Stars - 24 Hours", callback_data="stars_24h")],
        [InlineKeyboardButton("💫 299 Stars - 7 Days", callback_data="stars_7d")],
        [InlineKeyboardButton("💫 999 Stars - 1 Month 🏆", callback_data="stars_1month")],
        [InlineKeyboardButton("🔓 Check My Status", callback_data="premium_status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "💎 <b>SPOOKY PREMIUM ACCESS</b> 👑\n\n"
        "Unleash the full power of darkness — no mortal limits:\n\n"
        "🔥 <b>PREMIUM BENEFITS</b>\n"
        "• ♾️ <b>Unlimited</b> horror stories (Free: 2/day)\n"
        "• 🧛 <b>Unlimited</b> transformations (Free: 2/day)\n"
        "• ⚔️ <b>Games</b> – 2m (Free: 10m)\n"
        "• 📖 <b>Faster story summon</b> – 2m (Free: 5m)\n"
        "• 💬 <b>Instant spooky chat</b> – no cooldown (Free: 30s)\n"
        "• 🧌 Create custom monsters anytime\n"
        "• 💀 Support the underworld (developer)\n\n"
        "🩸 <b>Cooldown Comparison</b>\n"
        "• Transformations → 2m ⏱️ (Free: 5m)\n"
        "• Stories → 2m ⏱️ (Free: 5m)\n"
        "• RPG Adventures → 2m ⏱️ (Free: 10m)\n"
        "• Spooky Chat → Instant ⚡ (Free: 30s)\n\n"
        "• ⚔️ <b>coll game features</b> – 2m (Free: 10m)\n"
        "• 📖 <b>RECOGNITIONn</b> – 2m (Free: 5m)\n"
        "• 💬 <b>BOOST SCARE POINTS</b> – no cooldown (Free: 30s)\n"
        "• 🧌 THE PWER WILL BE URS\n"
        "🎁 <b>How to Get Premium</b>\n"
        "Choose your plan below or message the void directly:\n"
        "👉 @electrokid_1\n\n"
        "💫 Once unlocked, your soul... I mean, your account... will glow with <b>PREMIUM POWER</b>. 💀",
        parse_mode="HTML",
        reply_markup=reply_markup
    )



async def premium_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle premium button clicks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data
    
    if action == "premium_status":
        # Show user's current status
        if is_premium_user(user_id):
            premium_data = user_data[user_id]['premium']
            expires_str = premium_data['expires_at'].strftime("%Y-%m-%d %H:%M")
            await query.edit_message_text(
                f"💫 *PREMIUM STATUS* 👑\n\n"
                f"**Plan:** {premium_data['type']}\n"
                f"**Expires:** {expires_str}\n"
                f"**Active:** ✅\n\n"
                f"Enjoy unlimited nightmares! 👻",
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(
                "🔓 *PREMIUM STATUS*\n\n"
                "You're currently on the Free tier.\n\n"
                "**Free Limits:**\n"
                "• 3 transformations daily\n"
                "• 1 horror story daily\n\n"
                "Upgrade with /premium for unlimited access!",
                parse_mode='HTML'
            )





# ===== START COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """SpookyBot welcome message"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)

    username = update.effective_user.first_name or "Wanderer"
    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return

    # ===== SAVE USER INFO ON FIRST CONTACT =====
    user = update.effective_user
    user_data.setdefault(user_id, {})
    user_data[user_id]["first_name"] = user.first_name
    user_data[user_id]["username"] = user.username or ""
    user_data[user_id]["last_seen"] = datetime.now().isoformat()
    save_user_data()

    # ===== Initialize user data safely =====
    if user_id not in user_data:
        user_data[user_id] = {
            'nickname': username,
            'joined': datetime.now().isoformat(),
            'premium': False,
            'scares': 0,
            'rpg_character': None,
            'achievements': []
        }
        save_user_data()
        smart_save(user_id)
        is_new = True
    else:
        is_new = False


    # Determine user tier
    if is_premium_user(user_id):
        tier = "👑 <b>Premium Soul</b>"
    else:
        tier = "🧍‍♂️ <b>Mortal Wanderer</b>"

    # Message for new users
    if is_new:
        start_text = (
            f"🌑 <b>Welcome, {username}...</b>\n\n"
            "You’ve stepped into the shadows of <b>SpookyBot</b> 👻\n"
            "Where nightmares whisper and only the brave survive.\n\n"
            "💫 <b>Your Status:</b> " + tier + "\n\n"
            "🕯️ <b>Commands you can try:</b>\n"
            "• /story — summon haunting tales 📖\n"
            "• /transform — transform your photo into horror 😈\n"
            "• /games — play games ⚔️\n"
            "• /addscare — earn group scare points 👻\n"
            "• /menu — explore all powers 🧙\n\n"
            "💀 Ready to descend into the unknown?\n"
            "_Type /story to begin your first nightmare..._"
        )
    else:
        start_text = (
            f"🕯️ <b>Welcome back, {username}</b>\n\n"
            f"The darkness remembers you... 🌘\n"
            "💫 <b>Your Status:</b> " + tier + "\n\n"
            "Continue your path:\n"
            "• /games — play games ⚔️\n"
            "• /transform — unleash more transformations 👁️\n"
            "• /story — summon more nightmares 📚\n"
            "• /premium — check your power 👑"
        )

    # Send text first
    await update.message.reply_text(start_text, parse_mode='HTML')

    # Optional: spooky animation or fallback
    try:
        spooky_gifs = [
            "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExYjlycG5ieW1jcDcxdHVsc3pyb3dvMXZyYXIzdTRmdWl2b3l3eTQ4eiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/QBH4pcJAjGODC/giphy.gif",   # shadows awakening
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3ZDA5ZXZvOTd4NTczNzR0ajIzdWhuOHk4ZDJ4eHczbTVkYngzdmpqbyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/h5NLPVn3rg0Rq/giphy.gif",   # haunted flicker
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3dXkzZmRyYzY0aXVsNzkzMWkyNHQzYmRnZDNtaHFoeWE1bGI4cng1cCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/FJh8oUprQx8w8/giphy.gif",  # foggy apparition
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3bmRrbnp1eGx4d2R6ZnZqanZvcHdnMWtiOGl2YzY0Nng5aGk0NjZkaiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/1qeMPSrZbgwtiOvt0W/giphy.gif",   # ghost moving through room
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3dmNxNmZncXdweTVuc3M4Z2t5Zmdhd3I5MmNjNDJ4cXZvcTlzNHpuciZlcD12MV9naWZzX3NlYXJjaCZjdD1n/U3bMM7BSKQLCOiFK8k/giphy.gif",  # candles flickering
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3YzNldHd2ZXc4cjExdzhzNG9raWNteDJteW5oNnI0NXI1NmJ3OHZ4byZlcD12MV9naWZzX3NlYXJjaCZjdD1n/wMhe3bzsa1I40/giphy.gif",   # creepy forest
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3cjJrdnc0bjB1eWw1aG40a2R3cXRlNDVwcTBhcGl0MnA0Yzl4bDd0MiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/14xzPQjU62JPbi/giphy.gif",   # mysterious figure
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3YzVwcmN1cGY5ZW9qZ3l0NTR1eXllY3R6Nm81ZGZkbTlqazE1eXMwMiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/u7vcwx7WynnExSb2PS/giphy.gif",   # shadows awakening
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3czRiYnJ4NmxwamluY3Fnc2c4b3RlMGt4bzN0d3FnZXE1N3IzemdwMCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/8OOX2oZaNFhoA/giphy.gif",   # haunted flicker
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3NzJoYm5lMmtyN2lxc3RlMWM3emRzdDc4ZnphMTZoemdvbmh6YTh2ZCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ki6SYjp1FuDhRAu2He/giphy.gif",  # foggy apparition
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3YWZ2dnBzYjh1amUzaDAyanRhZnM2Y2VhMWE4aWN3NGp0cW5laXN1NyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/It0JrcMZ8VOh2/giphy.gif",   # ghost moving through room
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3MHhxOGJlMDA3d3djMGloZ2Vlcnp3dGo1czlxMXVjYzRreGY5aWUzZiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/pLWfbn1WVKzMQ/giphy.gif",  # candles flickering
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3eXB3bHp2YWh3ZGEzN2Yxd3J2dXdwbWhma3A1amZyc2JoNXo0cGJldSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/UYGS53pznEblK/giphy.gif",   # creepy forest
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3YzFsbjg3cTJrMjViZ3pib2NkMXNxb2k2M3V5NzhjbXBmbHM1MnBucCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/fuYn0nRjhZWmuOoae5/giphy.gif",      # storm & lightning
            "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3N2FnaXN0NnF6ZXFzMWk1cGh4cTIxNGFlZ2FyZWxuemwwMXFzdTVmMCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/10KUDfjtXlmDyE/giphy.gif"
        ]

        chosen_gif = random.choice(spooky_gifs)

        await update.message.reply_animation(
            animation=chosen_gif,
            caption=random.choice([
                "The shadows awaken... 🌑",
                "Something stirs in the dark... 👁️",
                "A chill runs through the air... ❄️",
                "The spirits whisper your name... 👻",
                "Welcome to the other side... 💀"
            ]),
            parse_mode='HTML'
        )

    except Exception as e:
        print(f"Animation send failed: {e}")

    await menu_command(update, context)

# ===== STORY SYSTEM =====
async def story_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show story category buttons"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    now = datetime.now()

    # ===== Story Cooldown (5 min free / 2 min premium) =====
    cooldown_time = timedelta(minutes=5) if is_premium_user(user_id) else timedelta(minutes=2)

    if user_id in STORY_COOLDOWN:
        next_time = STORY_COOLDOWN[user_id]
        if now < next_time:
            remaining = (next_time - now).seconds
            minutes = remaining // 60
            seconds = remaining % 60
            await update.message.reply_text(
                f"⏳ Please wait {minutes}m {seconds}s before summoning another story.\n"
                f"The spirits need time to weave new horrors... 📖",
                parse_mode="HTML"
            )
            return

    # Set next available story time
    STORY_COOLDOWN[user_id] = now + cooldown_time

    








    # Restrict to private chats only
    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return
    # Check usage for free users
    if not is_premium_user(user_id) and not can_use_story(user_id):
        await update.message.reply_text(
            "📖 *DAILY STORY LIMIT REACHED* 🔒\n\n"
            "You've used your 1 free story for today!\n\n"
            "💫 **Unlock with /premium to:**\n"
            "• Unlimited horror stories\n"
            "• All story categories\n"
            "• No daily limits\n\n"
            "_Use /premium for endless nightmares..._ 📚",
            parse_mode='HTML'
        )
        return
    
    keyboard = [
        [
            InlineKeyboardButton("🩸 BLOODY", callback_data="story_bloody"),
            InlineKeyboardButton("⏳ SHORT", callback_data="story_short")
        ],
        [
            InlineKeyboardButton("😨 SCARY", callback_data="story_scary"),
            InlineKeyboardButton("💀 VERY SCARY", callback_data="story_very_scary")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📖 *CHOOSE YOUR NIGHTMARE* 🔮\n\n"
        "Select a story category to summon ancient horrors:\n\n"
        "🩸 *BLOODY* - Gore and visceral terror\n"
        "⏳ *SHORT* - Quick, punchy fears\n"
        "😨 *SCARY* - Classic psychological horror\n"
        "💀 *VERY SCARY* - Ultimate nightmare fuel\n\n"
        "_Click a button below to begin your descent..._",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def story_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle story category button clicks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Increment usage for free users
    if not is_premium_user(user_id):
        increment_usage(user_id, 'story')
    
    # Extract category from callback data
    category = query.data.replace("story_", "")
    
    category_info = {
        "bloody": {"emoji": "🩸", "name": "BLOODY GORE", "message": "Summoning blood-soaked legends..."},
        "short": {"emoji": "⏳", "name": "QUICK TERROR", "message": "Weaving a brief nightmare..."},
        "scary": {"emoji": "😨", "name": "CLASSIC HORROR", "message": "Invoking ancient fears..."},
        "very_scary": {"emoji": "💀", "name": "ULTIMATE NIGHTMARE", "message": "Unleashing ultimate terror..."}
    }
    
    info = category_info.get(category, {"emoji": "📖", "name": "HORROR STORY", "message": "Creating your nightmare..."})
    
    # Edit the original message to show we're generating
    await query.edit_message_text(
        f"{info['emoji']} *{info['name']}* 🔮\n\n"
        f"{info['message']}\n"
        f"_Consulting the ancient texts..._ 📜",
        parse_mode='HTML'
    )
    
    # Generate the story
    await generate_story_from_button(query, category)


def text_to_speech_audio(story_text, filename="horror_story.mp3"):
    """Convert story text to speech audio"""
    try:
        # Initialize text-to-speech engine
        engine = pyttsx3.init()
        
        # Configure voice settings for horror effect
        voices = engine.getProperty('voices')
        
        # Try to use a deeper, more dramatic voice
        for voice in voices:
            if 'david' in voice.name.lower() or 'zira' in voice.name.lower() or 'microsoft david' in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
        
        # Set slower speed for dramatic effect
        engine.setProperty('rate', 150)  # Slower speed
        engine.setProperty('volume', 0.9)  # Maximum volume
        
        # Save to file
        engine.save_to_file(story_text, filename)
        engine.runAndWait()
        
        # Wait a moment for file to be created
        import time
        time.sleep(2)
        
        # Check if file was created
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            print(f"✅ Audio file created: {filename} ({os.path.getsize(filename)} bytes)")
            return filename
        else:
            print("❌ Audio file creation failed")
            return None
        
    except Exception as e:
        print(f"Text-to-speech error: {e}")
        return None

def get_category_emoji(category):
    """Get emoji for category"""
    emojis = {
        'bloody': '🩸',
        'short': '⏳', 
        'scary': '😨',
        'very-scary': '💀'
    }
    return emojis.get(category, '📖')

def get_category_name(category):
    """Get display name for category"""
    names = {
        'bloody': 'BLOODY GORE',
        'short': 'QUICK TERROR',
        'scary': 'CLASSIC HORROR',
        'very-scary': 'ULTIMATE NIGHTMARE'
    }
    return names.get(category, 'HORROR STORY')

def clean_text_for_audio(text):
    """Clean text for TTS audio generation"""
    # Remove formatting markers
    clean = re.sub(r'[*_~#]', '', text)
    # Remove HTML tags if any
    clean = re.sub(r'<.*?>', '', clean)
    # Fix common issues
    clean = clean.replace('&amp;', 'and')
    clean = clean.replace('...', '.')
    # Remove the "Story continues" text
    clean = clean.replace('📖 Story continues below... 👇', '')
    return clean

def creepy_robot_tts(text, filename="robot_voice.mp3"):
    """Generate disturbing robotic voice with glitch audio"""
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        engine.setProperty('voice', voices[0].id)
        engine.setProperty('rate', 130)
        engine.setProperty('volume', 0.7)
        
        # ADD GLITCH WORDS TO THE AUDIO ONLY
        glitches = ["STATIC", "ERROR", "SYSTEM FAILURE", "DATA CORRUPT", "PROCESS TERMINATED"]
        words = text.split()
        if len(words) > 5:
            # Insert glitches into the audio text
            pos = random.randint(2, len(words)-2)
            words.insert(pos, random.choice(glitches))
        
        audio_text = " ".join(words)
        
        # READ ENTIRE TEXT - NO CHARACTER LIMIT
        engine.save_to_file(audio_text, filename)
        engine.runAndWait()
        return filename
    except Exception as e:
        print(f"-> Robot TTS error: {e}")
        return None

async def auto_voice_message(message_obj, text: str, caption: str = ""):
    """Automatically send voice message with given text"""
    try:
        # Convert text to robotic voice
        audio_file = "auto_voice.mp3"
        
        # FIXED: Wrap creepy_robot_tts (non-blocking for pyttsx3)
        async def wrapped_tts():
            def sync_tts():
                # Your creepy_robot_tts logic (pyttsx3 robotic)
                engine = pyttsx3.init()
                voices = engine.getProperty('voices')
                engine.setProperty('voice', voices[0].id)  # Creepy voice
                engine.setProperty('rate', 120)  # Slow robotic
                engine.setProperty('volume', 0.9)
                engine.save_to_file(text, audio_file)
                engine.runAndWait()  # Blocker wrapped
                return os.path.exists(audio_file)
            
            return await asyncio.to_thread(sync_tts)
        
        result = await wrapped_tts()
        
        if result:
            # Send as voice message using the correct method
            with open(audio_file, 'rb') as voice_file:
                await message_obj.reply_voice(
                    voice=voice_file,
                    caption=caption
                )
            # Clean up
            os.remove(audio_file)
            return True
    except Exception as e:
        print(f"-> Auto voice error: {e}")
        import traceback
        traceback.print_exc()
    return False
    
    # ===== MENU COMMAND =====
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """"Show main menu with all bot features"""
    keyboard = [
        # Row 1: Transformations & Stories
        [
            InlineKeyboardButton("🧛 Transformations", callback_data="menu_transformations"),
            InlineKeyboardButton("📖 Stories", callback_data="menu_stories")
        ],
        # Row 2: RPG & Audio
        [
            InlineKeyboardButton("⚔️ RPG Game", callback_data="menu_rpg"),
            InlineKeyboardButton("🎧 Horror Audio", callback_data="menu_audio")
        ],
        # Row 3: Fun & Monster
        [
            InlineKeyboardButton("👻 Fun Commands", callback_data="menu_fun"),
            InlineKeyboardButton("🧌 Create Monster", callback_data="menu_monster")
        ],
        # Row 4: Premium (full width)
        [
            InlineKeyboardButton("💫 PREMIUM FEATURES", callback_data="menu_premium")
        ],
   
    [
        InlineKeyboardButton("🆘 Support & Contact", callback_data="menu_support")]
]
    
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎃 *SPOOKYBOT MAIN MENU* 👻\n\n"
        "*Choose your path to terror:*\n\n"
        "🧛 **Transformations** - Turn photos into monsters\n"
        "📖 **Horror Stories** - AI-generated scary tales\n"
        "⚔️ **RPG Game** - Horror adventure game\n"
        "🎧 **Horror Audio** - Spooky sounds & voices\n"
        "👻 **Fun Commands** - Quick scares & facts\n"
        "🧌 **Create Monster** - Design custom creatures\n"
        "💫 **PREMIUM** - Unlock unlimited features\n\n"
        "🆘 **SUPPORT** - Get help & report issues\n\n"
        "🤭 **MORE COMMANDS** - USE /help to get all features\n\n"
        "_Select a category below:_ 🔮",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ALL menu button clicks"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    print(f"-> Button clicked: {action}")
    
    # Handle premium status button
    if action == "premium_status":
        user_id = query.from_user.id
        
        if is_premium_user(user_id):
            premium_data = user_data[user_id]['premium']
            expires_str = premium_data['expires_at'].strftime("%Y-%m-%d %H:%M")
            await query.edit_message_text(
                f"💫 *PREMIUM STATUS* 👑\n\n"
                f"**Plan:** {premium_data['type']}\n"
                f"**Expires:** {expires_str}\n"
                f"**Active:** ✅\n\n"
                f"Enjoy unlimited nightmares! 👻",
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(
                "🔓 *PREMIUM STATUS*\n\n"
                "You're currently on the Free tier.\n\n"
                "**Free Limits:**\n"
                "• 3 transformations daily\n"
                "• 1 horror story daily\n\n"
                "Upgrade with /premium for unlimited access!",
                parse_mode='HTML'
            )
        return
    
    # Handle stars payment buttons
    elif action.startswith("stars_"):
        await handle_stars_payment(update, context)
        return
    
    # Handle menu buttons
    elif action.startswith("menu_"):
        action = action.replace("menu_", "")
        
        menu_categories = {
            # ... your existing menu categories code ...
        }
        
        if action in menu_categories:
            category = menu_categories[action]
            await query.edit_message_text(
                f"*{category['title']}*\n\n"
                f"{category['description']}\n\n"
                f"{category['commands']}\n\n"
                f"_Use the commands above or go back to the main menu._",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_back")
                ]])
            )
        
        elif action == "back":
            await menu_command(query, context)
    
    # Handle story buttons
    elif action.startswith("story_"):
        await story_button_handler(update, context)
    
    else:
        print(f"-> Unknown button action: {action}")
        await query.edit_message_text("❌ Unknown action. Please try again!")
        
        
async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photos sent by users"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    
    # Restrict to private chats only
    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return
    print(f"📸 PHOTO RECEIVED - User: {user_id}")
    print(f"📸 Photo requests status: {photo_requests.get(user_id, 'NOT WAITING')}")
    
    # Check if this user was waiting for a creepify photo
    if user_id in photo_requests and update.message.photo:
        print(f"🎯 Processing CUSTOM/CREEPIFY photo for user: {user_id}")
        del photo_requests[user_id]  # Clean up
        await process_creepify_photo(update, context)
        
        # TRACK ACHIEVEMENT PROGRESS - ADD THIS SECTION
        if update.effective_chat.id < 0:  # Group chat
            new_achievements = track_achievement(user_id, 'transformations', 1)
            
            # Notify about new achievements
            for achievement in new_achievements:
                await update.message.reply_text(
                    f"🎉 *ACHIEVEMENT UNLOCKED!* 🏅\n\n"
                    f"**{achievement['name']}**\n"
                    f"{achievement['description']}\n\n"
                    f"Check /myachievements to see all your rewards!",
                    parse_mode='HTML'
                )
    else:
        # Regular photo, ignore or handle differently
        print(f"❌ Regular photo from user: {user_id} - IGNORING")
        await update.message.reply_text("📸 I received your photo but I don't know what to do with it! Use a transformation command first! 👻")
        
        
        
        
        
def format_story_for_display(story_text, category):
    """Format the story for Telegram display"""
    category_display = {
        'bloody': {'emoji': '🩸', 'name': 'BLOODY GORE'},
        'short': {'emoji': '⏳', 'name': 'QUICK TERROR'},
        'scary': {'emoji': '😨', 'name': 'CLASSIC HORROR'},
        'very-scary': {'emoji': '💀', 'name': 'ULTIMATE NIGHTMARE'}
    }
    
    info = category_display.get(category, {'emoji': '📖', 'name': 'HORROR STORY'})
    
    story_text = story_text.strip()
    
    formatted = f"{info['emoji']} *{info['name']}* 🔮\n\n"
    
    # Add title if missing
    if not story_text.startswith('*') and not story_text.startswith('#'):
        titles = {
            'bloody': 'BLOOD-SOAKED LEGEND',
            'short': 'QUICK NIGHTMARE', 
            'scary': 'HAUNTING TALE',
            'very-scary': 'NIGHTMARE MANIFEST'
        }
        title = titles.get(category, 'HORROR STORY')
        formatted += f"*{title}*\n\n"
    
    formatted += f"{story_text}\n\n"
    formatted += f"_{get_story_ending(category)}_ 📖"
    
    return formatted




def get_story_ending(category):
    """Get appropriate ending message for each category"""
    endings = {
        'bloody': 'The blood has dried... but the memory remains...',
        'short': 'A quick terror that lingers in the mind...',
        'scary': 'Some stories should never be told twice...',
        'very-scary': 'This nightmare will visit you in your sleep...'
    }
    return endings.get(category, 'The story ends... or does it?')

def shorten_story_for_caption(story_text, max_length=900):
    """Shorten the story to fit Telegram's caption limit"""
    if len(story_text) <= max_length:
        return story_text
    
    shortened = story_text[:max_length]
    last_sentence = max(shortened.rfind('.'), shortened.rfind('!'), shortened.rfind('?'))
    if last_sentence > max_length * 0.6:
        shortened = shortened[:last_sentence + 1]
    
    shortened += f"\n\n📖 <i>Story continues below...</i> 👇"
    return shortened

def generate_story_image(story_type):
    """Generate a themed image based on story type"""
    try:
        image_url = f"https://picsum.photos/400/300?grayscale&random={random.randint(1,10000)}"
        response = requests.get(image_url, timeout=10)
        if response.status_code == 200:
            return image_url
        return None
    except Exception as e:
        print(f"-> Story image error for {story_type}: {e}")
        return None

# ===== IMAGE TRANSFORMATION SYSTEM =====
async def download_image(file_path):
    """Download image from Telegram"""
    try:
        response = requests.get(file_path, timeout=30)
        if response.status_code == 200:
            image_data = BytesIO(response.content)
            return image_data
        return None
    except Exception as e:
        print(f"-> Download error: {e}")
        return None



from telegram.ext import CommandHandler
import asyncio

async def transform_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display transformation menu that auto-deletes after 15s."""
    chat_id = update.effective_chat.id
    message = await update.message.reply_text(
        "*Available Commands:*"
        "• `/ghost` - Ghostly spirit"
        "• `/zombie` - Zombie apocalypse  "
        "• `/monster` - Grotesque monster"
        "• `/werewolf` - Beast transformation"
        "• `/demon` - Infernal demon"
        "• `/witch` - Dark witch"
        "• `/eldritch` - Cosmic horror"
        "• `/custom [prompt]` - Create your own horror"
        "_Choose wisely... not all forms can return._",
        parse_mode="Markdown"
    )

    # wait 15 seconds then delete
    await asyncio.sleep(15)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)
    except Exception as e:
        print(f"⚠️ Could not delete transform panel: {e}")










async def apply_horror_transformation(image_data, style_or_prompt="vampire"):
    """Apply horror transformation using the working API"""
    try:
        # Save image to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_input:
            image_data.seek(0)
            temp_input.write(image_data.getvalue())
            temp_input_path = temp_input.name
        
        # Get the prompt
        if isinstance(style_or_prompt, str) and len(style_or_prompt) > 50:
            prompt = style_or_prompt
        else:
            prompt = HORROR_PROMPTS.get(style_or_prompt, HORROR_PROMPTS["vampire"])
        
        print(f"-> Using prompt: {prompt}")
        
        # Use the working API
        edited_image_path = None
        if image_editor and image_editor.client:
            edited_image_path = image_editor.transform_image(temp_input_path, prompt)

        # Validate the returned image path
        if edited_image_path and image_editor.validate_image_file(edited_image_path):
            print(f"✅ Transformation successful! Output: {edited_image_path}")
            with open(edited_image_path, 'rb') as f:
                edited_image_data = BytesIO(f.read())
            
            # Clean up temp files
            try:
                os.unlink(edited_image_path)
                os.unlink(temp_input_path)
            except:
                pass
            
            return edited_image_data
        else:
            print("❌ Transformation failed - invalid output file")
            # Clean up temp files
            try:
                os.unlink(temp_input_path)
            except:
                pass
            return None
            
    except Exception as e:
        print(f"❌ Horror transformation error: {e}")
        
        # Clean up temp files
        try:
            os.unlink(temp_input_path)
        except:
            pass
            
        return None




# ===== TRANSFORMATION COMMANDS =====
async def handle_transform_command(update: Update, context: ContextTypes.DEFAULT_TYPE, style: str):
    """Handle all transformation commands with specific styles"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    
    # Restrict to private chats only
    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return
    now = datetime.now()
    cooldown_time = timedelta(minutes=4) if is_premium_user(user_id) else timedelta(minutes=10)

    if user_id in TRANSFORM_COOLDOWN:
        next_time = TRANSFORM_COOLDOWN[user_id]
        if now < next_time:
            remaining = (next_time - now).seconds
            minutes = remaining // 60
            seconds = remaining % 60
            await update.message.reply_text(
                f"⏳ Please wait {minutes}m {seconds}s before transforming another image.\n"
                f"The dark magic needs to recharge... 🔮",
                parse_mode="HTML"
            )
            return

    # Set next available time
    TRANSFORM_COOLDOWN[user_id] = now + cooldown_time
            
    # Check usage for free users
    if not is_premium_user(user_id) and not can_use_transformation(user_id):
        await update.message.reply_text(
            "🎭 *DAILY TRANSFORMATION LIMIT REACHED* 🔒\n\n"
            "You've used your 2 free transformations today!\n\n"
            "💫 **Unlock with /premium to:**\n"
            "• Unlimited transformations\n"
            "• All horror styles\n"
            "• No daily limits\n\n"
            "_Use /premium for endless creations..._ 🎨",
            parse_mode='HTML'
        )
        return

    print(f"-> {style.upper()} command received from user: {user_id}")

    # Store the style in user_data
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['last_transform_style'] = style

    # If user already sent a photo, process it immediately
    if update.message.photo:
        print("-> Photo sent WITH command!")
        await process_creepify_photo(update, context)

        # ✅ Award transformation progress AFTER success
        unlocked = update_achievement_progress(user_id, "transformations")
        if unlocked:
            await update.message.reply_text(
                f"🏅 Achievement Unlocked: {unlocked['name']}!\n📝 {unlocked['description']}",
                parse_mode='HTML'
            )
        return
    # If no photo yet, ask user to send one
    print("-> No photo detected, asking user to send photo...")
    photo_requests[user_id] = True

    style_names = {
        "vampire": "🧛 Vampire", "ghost": "👻 Ghost",
        "zombie": "🧟 Zombie", "monster": "👹 Monster",
        "eldritch": "👁️ Cosmic Horror", "werewolf": "🐺 Werewolf",
        "demon": "😈 Demon", "witch": "🧙‍♀️ Witch"
    }

    await update.message.reply_text(
        f"📸 *{style_names.get(style, 'Horror')} TRANSFORMATION RITUAL*\n\n"
        "I'm ready to transform your photo using AI magic! 🔮\n\n"
        "*Now send me a portrait photo...* 👁️\n\n"
        "_(Just send the photo like you normally would)_",
        parse_mode='HTML'
    )

async def process_creepify_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the photo for transformation (called from handle_transform_command)"""
    try:
        user_id = str(update.effective_user.id)
        style = user_data.get(user_id, {}).get('last_transform_style', 'vampire')  # From your store
        
        if not update.message.photo:
            await update.message.reply_text("📸 No photo found—send one for the ritual! 🔮")
            return
        
        # FIXED: Async Telegram download (no blocking requests.get)
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        photo_bytes = BytesIO(await photo_file.download_as_bytearray())
        
        style_names = {  # Your exact dict
            "vampire": "🧛 Vampire", "ghost": "👻 Ghost",
            "zombie": "🧟 Zombie", "monster": "👹 Monster",
            "eldritch": "👁️ Cosmic Horror", "werewolf": "🐺 Werewolf",
            "demon": "😈 Demon", "witch": "🧙‍♀️ Witch"
        }
        transform_name = style_names.get(style, 'Horror')
        
        # FIXED: Wrap Gradio predict (non-blocking)
        async def gradio_process():
            client = Client("your-gradio-url-here")  # Replace with your actual Gradio endpoint
            return client.predict(
                handle_file(photo_bytes),
                f"{style} horror transformation style",  # Your prompt style
                api_name="/transform"  # Your API name
            )
        
        result = await asyncio.to_thread(gradio_process)
        
        # Your send (with achievement after success)
        await update.message.reply_photo(
            photo=result,
            caption=f"📸 *{transform_name} TRANSFORMED* 😱\n\nThe dark magic has worked! Your new form awaits... 🔮",
            parse_mode='HTML'
        )
        
        # Your achievement call (exact from your code)
        unlocked = update_achievement_progress(user_id, "transformations")
        if unlocked:
            await update.message.reply_text(
                f"🏅 Achievement Unlocked: {unlocked['name']}!\n📝 {unlocked['description']}",
                parse_mode='HTML'
            )
            
        print(f"-> {style.upper()} transformation completed for {user_id}")
        
    except Exception as e:
        print(f"Photo process error: {e}")
        await update.message.reply_text("⚡ Transformation ritual failed... the shadows rebelled. Try again! 🌑")




# FIXED: process_creepify_photo (full version with async download + to_thread for Gradio)
async def process_creepify_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the photo for transformation (called from handle_transform_command)"""
    try:
        user_id = str(update.effective_user.id)
        style = user_data.get(user_id, {}).get('last_transform_style', 'vampire')  # From your store
        
        if not update.message.photo:
            await update.message.reply_text("📸 No photo found—send one for the ritual! 🔮")
            return
        
        # FIXED: Async Telegram download (no blocking requests.get)
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        photo_bytes = BytesIO(await photo_file.download_as_bytearray())
        
        style_names = {  # Your exact dict
            "vampire": "🧛 Vampire", "ghost": "👻 Ghost",
            "zombie": "🧟 Zombie", "monster": "👹 Monster",
            "eldritch": "👁️ Cosmic Horror", "werewolf": "🐺 Werewolf",
            "demon": "😈 Demon", "witch": "🧙‍♀️ Witch"
        }
        transform_name = style_names.get(style, 'Horror')
        
        # FIXED: Wrap Gradio predict (non-blocking)
        async def gradio_process():
            client = Client("your-gradio-url-here")  # Replace with your actual Gradio endpoint
            return client.predict(
                handle_file(photo_bytes),
                f"{style} horror transformation style",  # Your prompt style
                api_name="/transform"  # Your API name
            )
        
        result = await asyncio.to_thread(gradio_process)
        
        # Your send (with achievement after success)
        await update.message.reply_photo(
            photo=result,
            caption=f"📸 *{transform_name} TRANSFORMED* 😱\n\nThe dark magic has worked! Your new form awaits... 🔮",
            parse_mode='HTML'
        )
        
        # Your achievement call (exact from your code)
        unlocked = update_achievement_progress(user_id, "transformations")
        if unlocked:
            await update.message.reply_text(
                f"🏅 Achievement Unlocked: {unlocked['name']}!\n📝 {unlocked['description']}",
                parse_mode='HTML'
            )
            
        print(f"-> {style.upper()} transformation completed for {user_id}")
        
    except Exception as e:
        print(f"Photo process error: {e}")
        await update.message.reply_text("⚡ Transformation ritual failed... the shadows rebelled. Try again! 🌑")
        
        
        
async def creepify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_transform_command(update, context, "vampire")

async def gothic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_transform_command(update, context, "vampire")

async def ghost_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_transform_command(update, context, "ghost")

async def zombie_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_transform_command(update, context, "zombie")

async def monster_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_transform_command(update, context, "monster")

async def eldritch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_transform_command(update, context, "eldritch")

async def werewolf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_transform_command(update, context, "werewolf")

async def demon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_transform_command(update, context, "demon")

async def witch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_transform_command(update, context, "witch")

# ===== CUSTOM TRANSFORMATION =====
async def custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow users to create their own custom horror transformations"""
    user_id = str(update.effective_user.id)
    
    # PREMIUM CHECK
    if not is_premium_user(user_id):
        await update.message.reply_text(
            "🎨 *CUSTOM HORROR CREATOR* 🔒\n\n"
            "*This feature requires Premium access!*\n\n"
            "💫 **What you're missing:**\n"
            "• Create unlimited custom nightmares\n"
            "• Design your own horror visions\n"
            "• No daily limits\n\n"
            "🚀 **Unlock with /premium to:**\n"
            "• 🎨 Custom horror transformations\n"
            "• 🧌 Build your own monsters\n"
            "• ⚔️ Horror RPG adventures\n"
            "• 📖 Unlimited horror stories\n"
            "• 👻 All advanced features\n\n"
            "*Halloween Special - Limited Time Offer!* 🎃\n"
            "💫 99 Stars - 24 Hours\n"
            "💫 299 Stars - 7 Days\n"
            "💫 999 Stars - 1-Month Access\n\n"
            "_Use /premium to unlock the darkness..._ 👻",
            parse_mode='HTML'
        )
        return
    
    # Check if user provided a custom prompt
    if not context.args:
        await update.message.reply_text(
            "🎨 *CUSTOM HORROR CREATOR* 🖌️\n\n"
            "Create your OWN horror masterpiece!\n\n"
            "Usage: `/custom [your horror description]`\n\n"
            "*Examples:*\n"
            "`/custom zombie with glowing green eyes and rotting flesh`\n"
            "`/custom ghostly figure floating in haunted mansion`\n"
            "`/custom demon with bat wings and fiery eyes`\n"
            "`/custom werewolf under the full moon`\n\n"
            "I'll make sure it stays TERRIFYING! 😈",
            parse_mode='HTML'
        )
        return
    
    user_prompt = " ".join(context.args)
    
    print(f"-> Custom command received: {user_prompt}")
    print(f"-> User ID: {user_id}")
    
    # Store the custom prompt in user_data
    if user_id not in user_data:
        user_data[user_id] = {}
    
    user_data[user_id]['custom_prompt'] = user_prompt
    user_data[user_id]['last_transform_style'] = "custom"
    
    # Check if user already sent a photo with the command
    if update.message.photo:
        print("-> Photo sent WITH custom command!")
        await process_custom_photo(update, context)
        return
    
    # No photo yet - ask user to send one
    print("-> No photo detected, asking user to send photo...")
    photo_requests[user_id] = True
    
    await update.message.reply_text(
        f"🎨 *CUSTOM HORROR: {user_prompt[:50]}...* 🔮\n\n"
        "I'll transform your photo with your custom horror vision!\n\n"
        "*Now send me a portrait photo...* 👁️\n\n"
        "_(Just send the photo like you normally would)_",
        parse_mode='HTML'
    )



async def my_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's unlocked achievements"""
    user_id = str(update.effective_user.id)
    
    # Initialize achievements with all required keys
    achievements_data = init_user_achievements(user_id)
    
    achievements_text = "🏅 *YOUR ACHIEVEMENTS* 🎯\n\n"
    
    if not achievements_data['unlocked']:
        achievements_text += "No achievements yet! Keep participating to unlock them!\n\n"
    else:
        achievements_text += "*Unlocked Achievements:*\n"
        for achievement_id in achievements_data['unlocked']:
            if achievement_id in GROUP_ACHIEVEMENTS:  # Safety check
                achievement = GROUP_ACHIEVEMENTS[achievement_id]
                achievements_text += f"✅ {achievement['name']}\n"
                achievements_text += f"   📝 {achievement['description']}\n\n"
    
    # Show progress toward other achievements
    achievements_text += "*In Progress:*\n"
    for achievement_id, achievement_data in GROUP_ACHIEVEMENTS.items():
        if achievement_id not in achievements_data['unlocked']:
            # Safe progress check
            progress_type = achievement_data['type']
            progress = achievements_data['progress'].get(progress_type, 0)
            required = achievement_data['requirement']
            percentage = (progress / required) * 100 if required > 0 else 0
            
            achievements_text += f"🔄 {achievement_data['name']}\n"
            achievements_text += f"   📊 {progress}/{required} ({percentage:.1f}%)\n"
            achievements_text += f"   📝 {achievement_data['description']}\n\n"
    
    await update.message.reply_text(achievements_text, parse_mode='HTML')




async def enhanced_scare_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group scare leaderboard WITH TIERS"""
    chat_id = str(update.effective_chat.id)
    
    if int(chat_id) > 0:  # Private chat
        await update.message.reply_text(
            "🏆 *SCARE LEADERBOARD* 👻\n\n"
            "This command works in **groups only**!\n\n"
            "Add me to a group to see tiers and achievements! 🎪",
            parse_mode='HTML'
        )
        return
    
    leaderboard = init_group_leaderboard(chat_id)
    tier_lines = [f'{tier_info["color"]} {points}+: {tier_info["title"]}' for points, tier_info in SCARE_TIERS.items()]
    if not leaderboard:
        await update.message.reply_text(
            "🏆 *SCARE LEADERBOARD* 👻\n\n"
            "No scares recorded yet! Be the first to earn scare points and climb the tiers!\n\n"
            f"*Tier System:*\n{chr(10).join(tier_lines)}\n\n"
            "Earn points and unlock achievements! 🎯",
            parse_mode='HTML'
        )
        return
    
    # Sort by score
    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1]['score'], reverse=True)
    
    leaderboard_text = "🏆 *GROUP SCARE LEADERBOARD* 👻\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (user_id, data) in enumerate(sorted_leaderboard[:10]):  # Top 10
        username = data['username']
        score = data['score']
        medal = medals[i] if i < len(medals) else f"{i+1}."
        
        # Get user's tier
        user_tier = get_user_tier(score)
        
        leaderboard_text += f"{medal} {user_tier['color']} *{username}* - {score} pts\n"
        leaderboard_text += f"   🎖️ {user_tier['title']}\n\n"
    
    # Tier progression info
    leaderboard_text += "🎯 *TIER PROGRESSION:*\n"
    for points, tier_info in SCARE_TIERS.items():
        if points > 0:  # Skip 0 points tier
            leaderboard_text += f"{tier_info['color']} {points}+ pts: {tier_info['title']}\n"
    
    await update.message.reply_text(leaderboard_text, parse_mode='HTML')





async def goodbye_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send message when users leave the group"""
    left_member = update.message.left_chat_member
    username = left_member.first_name
    if left_member.username:
        username = f"@{left_member.username}"
    
    await update.message.reply_text(
        f"💀 {username} has fled the haunting... 🌑\n\n"
        f"_The ghosts will miss your screams..._ 👻",
        parse_mode='HTML'
    )




async def welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when new users join the group"""
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            # Bot itself was added to group
            await update.message.reply_text(
                "👻 *SPOOKYBOT HAS ARRIVED!* 🎃\n\n"
                "The haunting begins now! I'm here to:\n\n"
                "• Transform your photos into monsters! 🎭\n"
                "• Tell terrifying horror stories! 📖\n"
                "• Run daily scare challenges! ⚡\n"
                "• Host horror RPG adventures! ⚔️\n\n"
                "Use /help to see all my spooky features!\n"
                "Check today's challenge: /dailyscare\n\n"
                "_Let the nightmares begin..._ 🌑",
                parse_mode='HTML'
            )
        else:
            # Regular user joined - RANDOM WELCOME MESSAGES
            username = member.first_name
            if member.username:
                username = f"@{member.username}"
            
            welcome_messages = [
                f"👻 WELCOME {username} TO THE SPOOKY CREW! 🎃\n\nWho's ready to get haunted? Let's see some:\n• SpookyBot transformations! 🎭\n• Horror stories! 📖\n• Scare challenge entries! ⚡\n\nUse /menu to see all bot features!\nToday's challenge: /dailyscare\n\n_The ghosts are watching..._ 👻",
                
                f"💀 A NEW SOUL JOINS US! Welcome {username}! 🌑\n\nThe shadows stir as you enter our haunted domain...\n\n• check your tier /mytier 🎭\n• Brave enough for stories? /story 📖\n• Ready to compete? /dailyscare ⚡\n\n_Your nightmare journey begins now..._ 🔮",
                
                f"🎃 FRESH MEAT! Welcome {username}! 👻\n\nThe SpookyBot family grows stronger with your presence!\n\n• Dialy challenges: /dailyscare 🧌\n• Tell tales: /story 📖\n• Join the scareboard: /scareboard 🏆\n\n_What horrors will you create?_ 🕷️",
                
                f"🔮 THE VEIL PARTS FOR {username}! 👻\n\nAnother brave spirit joins our haunted congregation!\n\n• Transform photos into nightmares! 🎭\n• Generate AI horror stories! 📖\n• Compete in daily challenges! ⚡\n\nUse /menu to explore the darkness... 🌑"
            ]
            
            welcome_text = random.choice(welcome_messages)
            await update.message.reply_text(welcome_text, parse_mode='HTML')




def clean_old_cooldowns():
    """Remove cooldown entries older than 2 days to save memory"""
    global SCARE_COOLDOWN
    two_days_ago = datetime.now() - timedelta(days=2)
    
    for group_id in list(SCARE_COOLDOWN.keys()):
        for user_id in list(SCARE_COOLDOWN[group_id].keys()):
            for target_user in list(SCARE_COOLDOWN[group_id][user_id].keys()):
                if SCARE_COOLDOWN[group_id][user_id][target_user] < two_days_ago:
                    del SCARE_COOLDOWN[group_id][user_id][target_user]
            
            # Remove empty user entries
            if not SCARE_COOLDOWN[group_id][user_id]:
                del SCARE_COOLDOWN[group_id][user_id]
        
        # Remove empty group entries
        if not SCARE_COOLDOWN[group_id]:
            del SCARE_COOLDOWN[group_id]

# Call this periodically or in your save function

# Add this with your other configurations
SCARE_COOLDOWN = {}  # {group_id: {voter_id: {target_user: timestamp}}}


COOLDOWN_FILE = "scare_cooldowns.json"

def save_scare_cooldowns():
    try:
        with open(COOLDOWN_FILE, "w", encoding="utf-8") as f:
            json.dump(SCARE_COOLDOWN, f, ensure_ascii=False, indent=2, default=str)
        print("💾 Cooldowns saved.")
    except Exception as e:
        print(f"❌ Error saving cooldowns: {e}")

def load_scare_cooldowns():
    global SCARE_COOLDOWN
    if os.path.exists(COOLDOWN_FILE):
        try:
            with open(COOLDOWN_FILE, "r", encoding="utf-8") as f:
                SCARE_COOLDOWN = json.load(f)
            print(f"📂 Loaded {len(SCARE_COOLDOWN)} cooldown groups.")
        except Exception as e:
            print(f"❌ Error loading cooldowns: {e}")















async def add_scare_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually add scare points - MAX 5 POINTS - WITH COOLDOWN"""
    user_id = str(update.effective_user.id)  
    chat_id = str(update.effective_chat.id)
    
    if int(chat_id) > 0:
        await update.message.reply_text("🎯 This command works in groups only!", parse_mode='HTML')
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: `/addscare @username points`", parse_mode='HTML')
        return
    
    target_username = context.args[0].replace('@', '')
    
    # COOLDOWN CHECK
    if chat_id not in SCARE_COOLDOWN:
        SCARE_COOLDOWN[chat_id] = {}
    if user_id not in SCARE_COOLDOWN[chat_id]:
        SCARE_COOLDOWN[chat_id][user_id] = {}
    
    last_vote = SCARE_COOLDOWN[chat_id][user_id].get(target_username)

    # Convert string timestamps back to datetime before comparing
    if last_vote:
        try:
            if isinstance(last_vote, str):
                last_vote = datetime.fromisoformat(last_vote)  # convert saved string back
            if (datetime.now() - last_vote).total_seconds() < 86400:  # 24h = 86400s
                await update.message.reply_text(f"❌ Already voted for {target_username} today!", parse_mode='HTML')
                return
        except Exception as e:
            print(f"Cooldown parse error: {e}")
    
    try:
        points = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Please enter valid points!", parse_mode='HTML')
        return
    
    if points > 5:
        await update.message.reply_text("❌ Max 5 points per command!", parse_mode='HTML')
        return
    if points < 1:
        await update.message.reply_text("❌ Points must be at least 1!", parse_mode='HTML')
        return
    
    # UPDATE LEADERBOARD
    leaderboard = init_group_leaderboard(chat_id)
    if target_username not in leaderboard:
        leaderboard[target_username] = {'score': 0, 'username': target_username}
    
    leaderboard[target_username]['score'] += points
    SCARE_COOLDOWN[chat_id][user_id][target_username] = datetime.now()
    save_group_leaderboard()
    save_scare_cooldowns()  

    await update.message.reply_text(
        f"⚡ {points} points added to {target_username}! 🎯",
        parse_mode='HTML'
    )
    print(f"✅ {points} points added to {target_username}")


async def daily_scare_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Daily group scare challenge with point rewards"""
    chat_id = str(update.effective_chat.id)
    
    if int(chat_id) > 0:  # Private chat
        await update.message.reply_text(
            "⚡ *DAILY SCARE CHALLENGE* ⚡\n\n"
            "This command works in **groups only**!\n\n"
            "Add me to a group to participate in daily horror challenges! 🎪",
            parse_mode='HTML'
        )
        return
    
    challenges = [
        {"challenge": "🕷️ *CREEPY CRAWLER*: Find/share the creepiest insect photo!", "points": 3},
        {"challenge": "🏚️ *HAUNTED LOCATION*: Share a local spooky spot!", "points": 4},
        {"challenge": "🎬 *HORROR MOVIE QUOTE*: Best dramatic horror quote delivery!", "points": 3},
        {"challenge": "👹 *ORIGINAL MONSTER*: Design your own monster description!", "points": 5},
        {"challenge": "🔊 *SCARY SOUND*: Record/share the eeriest sound!", "points": 4},
        {"challenge": "🕯️ *CANDLELIGHT STORY*: Tell a story in dark/creepy lighting!", "points": 4},
        {"challenge": "👻 *GHOST PHOTO*: Take the spookiest real-life photo!", "points": 5},
        {"challenge": "🎃 *PUMPKIN ART*: Share your best Halloween creation!", "points": 4},
        {"challenge": "📖 *2-SENTENCE HORROR*: Write a mini horror story!", "points": 3},
        {"challenge": "🎭 *MONSTER SELFIE*: Use SpookyBot transformation!", "points": 3},
        {"challenge": "🔮 *SPOOKY PREDICTION*: Predict someone's creepy future!", "points": 4},
        {"challenge": "💀 *SCARE TACTIC*: Share your best jump scare idea!", "points": 5}
    ]
    
    challenge_data = random.choice(challenges)
    
    await update.message.reply_text(
        f"⚡ *DAILY SCARE CHALLENGE* ⚡\n\n"
        f"**{challenge_data['challenge']}**\n\n"
        f"🏆 *Reward:* {challenge_data['points']} SCARE POINTS!\n"
        f"⏰ *Deadline:* 24 hours\n\n"
        f"*How to enter:*\n"
        f"• Complete the challenge\n"
        f"• Post your entry in this group\n"
        f"• Tag @electrokid_1 for points\n\n"
        f"*Most creative entry wins bonus points!* 🎨",
        parse_mode='HTML'
    )

LINK_PATTERN = re.compile(r"(https?://|t\.me/|www\.)", re.IGNORECASE)
ADMIN_ID = 7351537370  # 👈 Replace with YOUR Telegram user ID

async def handle_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete links from non-admin users and send creepy warning."""
    message = update.message
    user_id = message.from_user.id
    text = message.text or ""

    # Skip non-text messages
    if not text:
        return

    # Check for links
    if LINK_PATTERN.search(text):
        if user_id != ADMIN_ID:
            try:
                await message.delete()
                await context.bot.send_message(
                    chat_id=message.chat_id,
                    text=f"🕸️ *The shadows whisper...*\n\n"
                         f"Links are forbidden here, {message.from_user.first_name}.\n"
                         f"The spirits have devoured your message... 👁️",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"⚠️ Failed to delete link: {e}")
















async def delete_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete links sent by non-admins and warn them creepily."""
    try:
        message = update.message
        user_id = message.from_user.id
        chat_id = message.chat_id
        text = message.text or message.caption or ""
        entities = message.entities or message.caption_entities or []

        # Detect any kind of link or URL pattern
        has_link = (
            re.search(r'https?://', text)
            or re.search(r't\.me/', text)
            or any(e.type in ["url", "text_link"] for e in entities)
        )

        if has_link:
            # Allow admin (you) to send links
            if int(user_id) == int(ADMIN_USER_ID):
                return

            # Delete message
            try:
                await message.delete()
            except Exception as e:
                print(f"Error deleting link: {e}")

            # Count warnings
            user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
            warnings = user_warnings[user_id]

            # Creepy warning message
            warning_msg = await message.chat.send_message(
                f"☠️ *Forbidden whispers...*\n\n"
                f"User [{message.from_user.first_name}](tg://user?id={user_id}),\n"
                f"you dared to share a link in this haunted realm.\n\n"
                f"⚠️ Warning {warnings}/3 — After the 3rd, your soul will be banished! 💀",
                parse_mode="HTML"
            )

            # Auto-delete the warning after 10 seconds
            await asyncio.sleep(10)
            try:
                await warning_msg.delete()
            except:
                pass

            # Ban after 3 warnings
            if warnings >= 3:
                try:
                    await context.bot.ban_chat_member(chat_id, user_id)
                    await message.chat.send_message(
                        f"🚫 {message.from_user.first_name} has been *banished* to the void for repeated link rituals! 👻",
                        parse_mode="Markdown"
                    )
                    del user_warnings[user_id]
                except Exception as e:
                    print(f"Error banning user: {e}")

    except Exception as e:
        print(f"Error deleting link or banning user: {e}")





async def process_custom_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process photo with custom user prompt"""
    user_id = str(update.effective_user.id)
    
    # Get the stored custom prompt
    custom_prompt = ""
    if user_id in user_data and 'custom_prompt' in user_data[user_id]:
        custom_prompt = user_data[user_id]['custom_prompt']
    else:
        await update.message.reply_text("❌ No custom prompt found. Use `/custom [prompt]` first!")
        return
    
    # ENSURE IT'S SCARY - Add horror keywords if not present
    horror_keywords = ["horror", "scary", "terrifying", "creepy", "spooky", "dark", "gothic", "macabre"]
    prompt_is_scary = any(keyword in custom_prompt.lower() for keyword in horror_keywords)
    
    if not prompt_is_scary:
        enhanced_prompt = f"terrifying horror version of {custom_prompt}, part of face normal, cinematic lighting, horror art, photorealistic, portrait"
    else:
        enhanced_prompt = f"{custom_prompt}, part of face normal, cinematic lighting, horror art, photorealistic,"
    
    await update.message.reply_text(
        f"🎨 *CUSTOM HORROR TRANSFORMATION* 🔮\n\n"
        f"*Your Vision:* {custom_prompt}\n\n"
        f"Sending your photo to AI transformation... This may take 10-30 seconds... ⏳",
        parse_mode='HTML'
    )
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        image_data = await download_image(photo_file.file_path)
        
        if image_data:
            # Apply custom horror transformation
            transformed_image = await apply_horror_transformation(image_data, enhanced_prompt)
            
            # Clean up the stored prompt after successful transformation
            if user_id in user_data and 'custom_prompt' in user_data[user_id]:
                del user_data[user_id]['custom_prompt']
            
            if transformed_image:
                await update.message.reply_photo(
                    photo=transformed_image,
                    caption=f"🎭 *CUSTOM HORROR CREATION COMPLETE!* 👹\n\n"
                           f"*Your Vision:* {custom_prompt}\n\n"
                           f"Your custom nightmare has been brought to life! 🔥",
                    parse_mode='HTML'
                )
                print(f"-> Custom transformation successful!")
                
                # Increment usage for free users
                if not is_premium_user(user_id):
                    increment_usage(user_id, 'transformation')
            else:
                await update.message.reply_text(
                    "⚡ Custom transformation failed... the mystical energies are unstable today... 🔮\n"
                    "*Try again with a different prompt!* 📝"
                )
        else:
            await update.message.reply_text("📸 Could not capture your image... try again!")
                
    except Exception as e:
        print(f"-> Custom photo processing error: {e}")
        await update.message.reply_text("💀 A mystical error occurred during transformation...")

async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photos sent by users"""
    user_id = str(update.effective_user.id)
    
    print(f"📸 PHOTO RECEIVED - User: {user_id}")
    print(f"📸 Photo requests status: {photo_requests.get(user_id, 'NOT WAITING')}")
    
    # Check if this user was waiting for a creepify photo
    if user_id in photo_requests and update.message.photo:
        print(f"🎯 Processing CUSTOM/CREEPIFY photo for user: {user_id}")
        del photo_requests[user_id]  # Clean up
        await process_creepify_photo(update, context)
        
        # TRACK ACHIEVEMENT PROGRESS - ADD THIS SECTION
        if update.effective_chat.id < 0:  # Group chat
            new_achievements = track_achievement(user_id, 'transformations', 1)
            
            # Notify about new achievements
            for achievement in new_achievements:
                await update.message.reply_text(
                    f"🎉 *ACHIEVEMENT UNLOCKED!* 🏅\n\n"
                    f"**{achievement['name']}**\n"
                    f"{achievement['description']}\n\n"
                    f"Check /myachievements to see all your rewards!",
                    parse_mode='HTML'
                )
    else:
        # Regular photo, ignore or handle differently
        print(f"❌ Regular photo from user: {user_id} - IGNORING")
        await update.message.reply_text("📸 I received your photo but I don't know what to do with it! Use a transformation command first! 👻")





async def process_creepify_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process photo with Hugging Face horror transformations"""
    user_id = str(update.effective_user.id)
    print(f"-> Processing photo transformation for user: {user_id}")
    
    # Get the stored style from user_data
    style = "vampire"  # default fallback
    
    if user_id in user_data and 'last_transform_style' in user_data[user_id]:
        style = user_data[user_id]['last_transform_style']
        print(f"-> Using stored style: {style}")
        
        # If style is "custom", use the custom prompt instead of horror prompts
        if style == "custom" and 'custom_prompt' in user_data[user_id]:
            custom_prompt = user_data[user_id]['custom_prompt']
            print(f"-> CUSTOM TRANSFORMATION DETECTED!")
            
            # ENSURE IT'S SCARY - Add horror keywords if not present
            horror_keywords = ["horror", "scary", "terrifying", "creepy", "spooky", "dark", "gothic", "macabre"]
            prompt_is_scary = any(keyword in custom_prompt.lower() for keyword in horror_keywords)
            
            if not prompt_is_scary:
                enhanced_prompt = f"terrifying horror version of {custom_prompt}, part of face normal, cinematic lighting, horror art, photorealistic, portrait"
            else:
                enhanced_prompt = f"{custom_prompt}, part of face normal, cinematic lighting, horror art, photorealistic, portrait"
            
            # Clean up the stored data
            del user_data[user_id]['last_transform_style']
            if 'custom_prompt' in user_data[user_id]:
                del user_data[user_id]['custom_prompt']
            
            await update.message.reply_text(
                f"🎨 *CUSTOM HORROR TRANSFORMATION* 🔮\n\n"
                f"*Your Vision:* {custom_prompt}\n\n"
                f"Sending your photo to AI transformation... This may take 10-30 seconds... ⏳",
                parse_mode='HTML'
            )
            
            try:
                photo_file = await update.message.photo[-1].get_file()
                image_data = await download_image(photo_file.file_path)
                
                if image_data:
                    # Apply CUSTOM horror transformation
                    transformed_image = await apply_horror_transformation(image_data, enhanced_prompt)
                    
                    if transformed_image:
                        await update.message.reply_photo(
                            photo=transformed_image,
                            caption=f"🎭 *CUSTOM HORROR CREATION COMPLETE!* 👹\n\n"
                                   f"*Your Vision:* {custom_prompt}\n\n"
                                   f"Your custom nightmare has been brought to life! 🔥",
                            parse_mode='HTML'
                        )
                        print(f"-> Custom transformation successful!")
                        
                        # Increment usage for free users
                        if not is_premium_user(user_id):
                            increment_usage(user_id, 'transformation')
                        return
                    else:
                        await update.message.reply_text(
                            "⚡ Custom transformation failed... the mystical energies are unstable today... 🔮\n"
                            "*Try again with a different prompt!* 📝"
                        )
                        return
                else:
                    await update.message.reply_text("📸 Could not capture your image... try again!")
                    return
                    
            except Exception as e:
                print(f"-> Custom photo processing error: {e}")
                await update.message.reply_text("💀 A mystical error occurred during transformation...")
                return
        
        # Clean up the stored style for regular transformations
        del user_data[user_id]['last_transform_style']
    else:
        print("-> No stored style found, using default vampire")
    
    # REGULAR TRANSFORMATION (only if not custom)
    style_names = {
        "vampire": "🧛 Vampire Transformation", 
        "monster": "👹 Monster Form", 
        "ghost": "👻 Ghostly Spirit",
        "zombie": "🧟 Zombie Apocalypse", 
        "eldritch": "👁️ Cosmic Horror",
        "werewolf": "🐺 Werewolf Beast", 
        "demon": "😈 Infernal Demon", 
        "witch": "🧙‍♀️ Dark Witch"
    }
    
    await update.message.reply_text(
        f"🔮 *{style_names.get(style, 'Horror Transformation')}* 🎨\n\n"
        f"Sending your photo to AI transformation... This may take 10-30 seconds... ⏳",
        parse_mode='HTML'
    )
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        image_data = await download_image(photo_file.file_path)
        
        if image_data:
            # Apply Hugging Face horror transformation
            transformed_image = await apply_horror_transformation(image_data, style)
            
            if transformed_image:
                captions = {
                    "vampire": "🧛 *VAMPIRE TRANSFORMATION COMPLETE!* 🦇\n\nYour immortal form has been revealed... the night calls...",
                    "monster": "👹 *MONSTER WITHIN UNLEASHED!* 🔥\n\nYour primal form breaks free from human constraints...", 
                    "ghost": "👻 *SPIRIT FORM MANIFESTED!* 💀\n\nThe veil between worlds could not contain you...",
                    "zombie": "🧟 *ZOMBIE INFECTION REVEALED!* 🧠\n\nThe hunger awakens... join the horde...",
                    "eldritch": "👁️ *ELDRITCH TRUTH UNVEILED!* 🌌\n\nYour cosmic form defies mortal comprehension...",
                    "werewolf": "🐺 *WEREWOLF TRANSFORMATION!* 🌕\n\nThe beast within answers the moon's call...",
                    "demon": "😈 *INFERNAL DEMON REVEALED!* 🔥\n\nHell's power courses through your form...",
                    "witch": "🧙‍♀️ *DARK WITCH TRANSFORMATION!* ⚡\n\nAncient magic flows through your veins..."
                }
                
                await update.message.reply_photo(
                    photo=transformed_image,
                    caption=captions.get(style, "🎭 *HORROR TRANSFORMATION COMPLETE!* 👹"),
                    parse_mode='HTML'
                )
                print(f"-> {style} transformation successful!")
                
                # Increment usage for free users
                if not is_premium_user(user_id):
                    increment_usage(user_id, 'transformation')
            else:
                await update.message.reply_text(
                    "⚡ AI transformation failed... the mystical energies are unstable today... 🔮\n"
                    "*Try again in about 5-15 min* TNX📸\n\n"
                    "DAMN ALOT OF TRANSFORMATION REQUEST..."

                )  
                     
        else:
            await update.message.reply_text("📸 Could not capture your image... try again!")
                
    except Exception as e:
        print(f"-> Photo processing error: {e}")
        await update.message.reply_text("💀 A mystical error occurred during transformation...")

# ===== MONSTER CREATION SYSTEM =====
async def create_monster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Users can create their own horror creatures"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    
    # Restrict to private chats only
    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return
    # PREMIUM CHECK
    if not is_premium_user(user_id):
        await update.message.reply_text(
            "🧌 *MONSTER CREATOR* 🔒\n\n"
            "*This feature requires Premium access!*\n\n"
            "💫 **Unlock with /premium to:**\n"
            "• Design your own horror creatures\n"
            "• Create custom monster stories\n"
            "• Bring your nightmares to life\n\n"
            "_Use /premium to unleash your creativity..._ 👹",
            parse_mode='HTML'
        )
        return



    # ===== Monster Creation Cooldown (5 min premium / 10 min free) =====
    now = datetime.now()
    cooldown_time = timedelta(minutes=5) if is_premium_user(user_id) else timedelta(minutes=10)
    if user_id in MONSTER_COOLDOWN:
        next_time = MONSTER_COOLDOWN[user_id]
        if now < next_time:
            remaining = (next_time - now).seconds
            minutes = remaining // 60
            seconds = remaining % 60
            await update.message.reply_text(
                f"⏳ Please wait {minutes}m {seconds}s before creating another monster.\n"
                f"The dark energies need time to recharge... 🔮",
                parse_mode="HTML"
            )
            return
    # Set next available monster creation time
    MONSTER_COOLDOWN[user_id] = now + cooldown_time    







    if user_id not in user_data:
        user_data[user_id] = {'conversation': [], 'nickname': None}

    user_data[user_id]['monster_creation'] = {'step': 'awaiting_description'}

    # ✅ Add this at the very end
    unlocked = update_achievement_progress(user_id, "monsters_created")
    if unlocked:
        await update.message.reply_text(
            f"🏅 Achievement Unlocked: {unlocked['name']}!\n📝 {unlocked['description']}",
            parse_mode='HTML'
        )

    await update.message.reply_text("""
🧌 **CREATE YOUR NIGHTMARE**

Describe your monster:
-  **Appearance**: (What does it look like? detailed.)
- **Powers**: (What can it do?)  
- **Weakness**: (How to defeat it?)
- **Origin**: (Where did it come from?)

*Example:*
"A tall shadowy figure with glowing red eyes, can phase through walls, afraid of light, created from a scientist's failed experiment"

Now... describe your MONSTER  : 👹
    """, parse_mode='HTML')

    



def generate_monster_profile(description, user_id):
    """Use AI to expand the monster description into full profile"""
    try:
        prompt = f"""
Based on this monster description: "{description}"

Create a FULL monster profile with:

NAME: [Creative scary name]
TYPE: [Supernatural, Alien, Undead, etc.]
APPEARANCE: [Detailed physical description]  
POWERS: [3-5 special abilities]
WEAKNESSES: [2-3 vulnerabilities]
ORIGIN_STORY: [How it was created/born]
BEHAVIOR: [How it hunts/acts]
FEAR_LEVEL: [1-10 how terrifying]

Make it CREEPY and UNIQUE!

remember is a profile not tooo lenght just short and redable
"""
        
        response = model.generate_content(prompt)
        return parse_monster_response(response.text)
        
    except Exception as e:
        print(f"Monster generation error: {e}")
        return None

def parse_monster_response(text):
    """Parse AI response into structured monster data"""
    lines = text.split('\n')
    monster = {'name': 'Unknown Horror', 'type': 'Supernatural'}
    
    for line in lines:
        if 'NAME:' in line:
            monster['name'] = line.split('NAME:')[-1].strip()
        elif 'TYPE:' in line:
            monster['type'] = line.split('TYPE:')[-1].strip()
        elif 'APPEARANCE:' in line:
            monster['appearance'] = line.split('APPEARANCE:')[-1].strip()
        elif 'POWERS:' in line:
            monster['powers'] = line.split('POWERS:')[-1].strip()
        elif 'WEAKNESSES:' in line:
            monster['weaknesses'] = line.split('WEAKNESSES:')[-1].strip()
        elif 'ORIGIN_STORY:' in line:
            monster['origin'] = line.split('ORIGIN_STORY:')[-1].strip()
        elif 'BEHAVIOR:' in line:
            monster['behavior'] = line.split('BEHAVIOR:')[-1].strip()
        elif 'FEAR_LEVEL:' in line:
            monster['fear_level'] = line.split('FEAR_LEVEL:')[-1].strip()
    
    return monster


def format_monster_profile(monster):
    """Format monster data for Telegram display"""
    return f"""
🧌 *{monster['name']}* - {monster['type']}

👁️ *APPEARANCE*: {monster.get('appearance', 'Unknown')}

⚡ *POWERS*: {monster.get('powers', 'Unknown')}

🛡️ *WEAKNESSES*: {monster.get('weaknesses', 'Unknown')}

📖 *ORIGIN*: {monster.get('origin', 'Unknown')}

🎭 *BEHAVIOR*: {monster.get('behavior', 'Unknown')}

😨 *FEAR LEVEL*: {monster.get('fear_level', '?')}/10

*Your nightmare has been given form!* 👹
"""

def generate_monster_image(monster):
    """Generate monster image using dark magic - WORKING VERSION"""
    try:
        print(f"-> Giving form to your nightmare: {monster['name']}...")
        
        prompt = f"terrifying horror monster: {monster['name']}. Appearance: {monster.get('appearance', 'mysterious dark creature')}. Style: dark fantasy, creepy, horror art, cinematic lighting, highly detailed, digital painting, atmospheric, scary, monster, 4k, ultra detailed"
        
        print(f"-> Whispering to the void: {prompt[:100]}...")
        
        # Summon the darkness
        sdk = Bytez(BYTEZ_API_KEY)        
        model = sdk.model("stabilityai/stable-diffusion-xl-base-1.0")
        
        # Channel the ancient powers
        error, output = model.run(prompt)
        
        # The void answers with visions
        if error and error.startswith('https://'):
            print("-> The darkness has taken form!")
            print(f"-> Vision from beyond: {error}")
            
            # Capture the nightmare
            response = requests.get(error, timeout=30)
            if response.status_code == 200:
                image_data = BytesIO(response.content)
                return image_data
            else:
                print(f"-> Failed to capture the vision: {response.status_code}")
                return None
        else:
            print(f"-> The void remained silent: {error}")
            return None
            
    except Exception as e:
        print(f"-> Ancient magic failed: {e}")
        return None

async def handle_monster_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process monster creation steps"""
    user_id = str(update.effective_user.id)
    user_text = update.message.text
    
    # Check if this is a monster creation in progress
    if user_id not in user_data or 'monster_creation' not in user_data[user_id]:
        return await handle_message(update, context)  # Handle as normal message
    
    creation_data = user_data[user_id]['monster_creation']
    
    if creation_data['step'] == 'awaiting_description':
        await update.message.reply_text("🌀 *Summoning your creature from the void...*", parse_mode='HTML')
        
        monster_profile = generate_monster_profile(user_text, user_id)
        
        if monster_profile:
            if 'created_monsters' not in user_data[user_id]:
                user_data[user_id]['created_monsters'] = []
            user_data[user_id]['created_monsters'].append(monster_profile)
            
            profile_text = format_monster_profile(monster_profile)
            await update.message.reply_text(profile_text, parse_mode='HTML')
            
            # Give form to the nightmare - GENERATE IMAGE
            await update.message.reply_text("🎨 *YOUR IMAGE MIGHT TAKE A WHILE CAUSE OTHERS ARE IN THE REALM WAITING FOR THEIR NIGHTMARES-------Your fears are taking shape...wait for the nightmares to appear*", parse_mode='HTML')
            image_data = generate_monster_image(monster_profile)

            if image_data:
                await update.message.reply_photo(
                    photo=image_data,
                    caption=f"🖼️ *YOUR FEARS CREATED THIS: {monster_profile['name']}* 👹",
                    parse_mode='HTML'
                )
            else:
                # Fallback if the dark arts fail
                await update.message.reply_text("The void refused to answer... but your monster profile was created! 🔮")

            await update.message.reply_text(
                "🎭 *WHAT NOW?*"
                "/monsterstory - Create story with your monster\n"
                "/createmonster - Make another abomination",
                parse_mode='HTML'
            )
            

        else:
            await update.message.reply_text("The summoning ritual failed... try again! 🔮")
        smart_save(update.effective_user.id)
        # Clean up
        del user_data[user_id]['monster_creation']

async def monster_story(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a horror story featuring the user's custom monster with AUDIO"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)



    # ===== Monster Story Cooldown (3 min premium / 7 min free) =====
    now = datetime.now()
    cooldown_time = timedelta(minutes=3) if is_premium_user(user_id) else timedelta(minutes=7)

    if user_id in MONSTER_COOLDOWN:
        next_time = MONSTER_COOLDOWN[user_id]
        if now < next_time:
            remaining = (next_time - now).seconds
            minutes = remaining // 60
            seconds = remaining % 60
            await update.message.reply_text(
                f"⏳ Please wait {minutes}m {seconds}s before creating another monster story.\n"
                f"The storyteller spirits need time to weave new tales... 📖",
                parse_mode="HTML"
            )
            return

    # Set next available monster story time
    MONSTER_COOLDOWN[user_id] = now + cooldown_time





    # Restrict to private chats only
    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return
    if user_id not in user_data or 'created_monsters' not in user_data[user_id]:
        await update.message.reply_text("Create a monster first with /createmonster! 👹")
        return
    
    monsters = user_data[user_id]['created_monsters']
    
    if not monsters:
        await update.message.reply_text("No monsters created yet! Use /createmonster 👹")
        return
   # Use the most recent monster
    monster = monsters[-1]
    
    await update.message.reply_text("📖 *Weaving your nightmare tale with dark magic...*", parse_mode='HTML')
    
    # Generate story using Gemini AI based on the monster description
    story_prompt = f"""
Create a TERRIFYING horror story featuring this custom monster:

MONSTER NAME: {monster['name']}
TYPE: {monster['type']}
APPEARANCE: {monster.get('appearance', '')}
POWERS: {monster.get('powers', '')}
WEAKNESSES: {monster.get('weaknesses', '')}
ORIGIN: {monster.get('origin', '')}
BEHAVIOR: {monster.get('behavior', '')}

Story Requirements:
- 1-3 paragraphs
- Feature {monster['name']} as the main antagonist
- Show the monster using its powers: {monster.get('powers', '')}
- Include the monster's weaknesses: {monster.get('weaknesses', '')}
- Describe the monster's appearance: {monster.get('appearance', '')}
- Create intense horror and suspense
- No emojis in the story text
 
Make it absolutely TERRIFYING and use the monster's specific traits!
"""
    
    try:
        response = model.generate_content(story_prompt)
        story_text = response.text.strip()
        
        formatted_story = f"📖 *{monster['name']}'S HORROR TALE* 👹\n\n{story_text}\n\n💀 *The monster lives on...* 🔮"
        
        # Send text story
        await update.message.reply_text(formatted_story, parse_mode='HTML')
        
        # ===== GENERATE AUDIO VERSION =====
        # Clean text for audio (remove formatting)
        clean_story = story_text
        clean_story = re.sub(r'[*_~#]', '', clean_story)  # Remove formatting
        clean_story = re.sub(r'<.*?>', '', clean_story)   # Remove HTML tags
        clean_story = clean_story.replace('&amp;', 'and') # Fix HTML entities
        
        # ===== FIX: Pass the MESSAGE object, not update object =====
        await auto_voice_message(
            update.message,  # ← THIS IS THE FIX: update.message instead of update
            clean_story,
            f"🎧 {monster['name']}'S HORROR TALE 👹"
        )
        print(f"-> Monster story audio sent for {monster['name']}!")
        
    except Exception as e:
        print(f"Monster story error: {e}")
        await update.message.reply_text("The story portal collapsed... try again! 🌌")



# ===== RPG SYSTEM =====
class RPGState:
    ACTIVE = "active"
    COMPLETED = "completed"

def get_rpg_state(user_id):
    """Get or initialize RPG state for user"""
    uid = int(user_id)
    if uid not in user_data:
        user_data[uid] = {}
    
    if 'rpg_state' not in user_data[uid]:
        user_data[uid]['rpg_state'] = {
            'current_adventure': None,
            'status': RPGState.COMPLETED
        }
    
    return user_data[uid]['rpg_state']
async def rpg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start horror RPG adventure (persistent)"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    
    # Restrict to private chats only
    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return
    # Redirect groups to private chat
    if update.effective_chat.type in ["group", "supergroup"]:
        await update.message.reply_text(
            "⚔️ <b>HORROR RPG</b> 🎮\n\n"
            "RPG adventures work best in private chat for uninterrupted gameplay!\n\n"
            "👉 Message me privately: <b>@SpookyNightBot</b>\n\n"
            "Then use: <code>/rpg_start</code> to begin your horror journey!",
            parse_mode='HTML'
        )
        return

    # Initialize user_data entry
    if user_id not in user_data:
        user_data[user_id] = {}

    # Check if already has character
    if 'rpg_character' in user_data[user_id]:
        char = user_data[user_id]['rpg_character']
        await update.message.reply_text(
            f"⚔️ <b>WELCOME BACK, {char['name']}!</b> 🎮\n\n"
            f"You already have a character:\n"
            f"👤 {char['name']} the {char['class']}\n"
            f"⚡ Level {char['level']}\n\n"
            f"Use /adventure to continue your journey!",
            parse_mode='HTML'
        )
        save_user_data()
        return

    # === Check if already has character ===
    if 'rpg_character' in user_data[user_id]:
        char = user_data[user_id]['rpg_character']
        await update.message.reply_text(
            f"⚔️ <b>WELCOME BACK, {char['name']}!</b> 🎮\n\n"
            f"You already have a character:\n"
            f"👤 {char['name']} the {char['class']}\n"
            f"⚡ Level {char['level']}\n\n"
            f"Use /adventure to continue your journey!",
            parse_mode='HTML'
        )
        return

    # === Character classes ===
    rpg_classes = {
        "ghost_hunter": {"name": "Ghost Hunter", "emoji": "👻", "bonus": "Extra damage vs spirits"},
        "occult_scholar": {"name": "Occult Scholar", "emoji": "📚", "bonus": "Better item discovery"},
        "cursed_survivor": {"name": "Cursed Survivor", "emoji": "🔮", "bonus": "Higher fear resistance"},
        "monster_tamer": {"name": "Monster Tamer", "emoji": "🧌", "bonus": "Can befriend some monsters"}
    }

    # === Ask for name if missing ===
    # Ask for name if missing
    if not context.args:
        keyboard = []
        for key, cls in rpg_classes.items():
            keyboard.append([InlineKeyboardButton(f"{cls['emoji']} {cls['name']}", callback_data=f"rpg_class_{key}")])
        keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="rpg_cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚔️ <b>HORROR RPG CHARACTER CREATION</b> 🎮\n\n"
            "Choose your class to begin your nightmare journey:\n\n"
            "*What horrors will you face?*\n\n"
            "_Select below to start..._ 🔮",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return

    char_name = " ".join(context.args)
    char_class_key = random.choice(list(rpg_classes.keys()))
    char_class = rpg_classes[char_class_key]

    # === Create character ===
    user_data[user_id]['rpg_character'] = {
        'name': char_name,
        'class': char_class['name'],
        'class_key': char_class_key,
        'level': 1,
        'experience': 0,
        'fear_resistance': 50,
        'sanity': 100,
        'health': 100
    }
    user_data[user_id]['rpg_inventory'] = ['Flashlight 🔦']
    user_data[user_id]['rpg_location'] = 'Shadow Forest 🌲'
    user_data[user_id]['rpg_achievements'] = []

    # === Save immediately ===
 

# Initialize RPG leaderboard
    username = update.effective_user.username or update.effective_user.first_name
    init_rpg_leaderboard(user_id, username)

    # Display RPG sheet
    await update.message.reply_text(
        f"🎉 *CHARACTER CREATED!* ⚔️\n\n"
        f"**Name:** {user_data[user_id]['rpg_character']['name']}\n"
        f"**Class:** {char_class['name']}\n"
        f"**Level:** 1\n"
        f"**Sanity:** 100/100\n\n"
        f"Your adventure begins! Use /adventure to start your first quest.\n\n"
        f"⭐ EXP: 0/100\n\n"
        f"✨ <b>Class Bonus:</b> {char_class['bonus']}\n\n"
        f"<b>STARTING GEAR:</b>\n"
        f"• Flashlight 🔦 - Reveals hidden secrets\n\n"
        f"<b>LOCATION:</b> Shadow Forest 🌲\n\n"
        f"🌑 <b>Your horror adventure begins...</b>\n\n"
        f"Use /adventure to start your first quest!\n"
        f"Use /stats to check stats\n"
        f"Use /inventory to check items\n"
        f"Use /use_item to use item\n"
        f"Use /craft to make item\n"
        f"Use /locations to open new locations\n"
        f"Use /achievements to view achievements\n"
        f"Use /leaderboard to check leaderboard rank",
        parse_mode='HTML'
    )

    print(f"✅ RPG started for {char_name} ({user_id})")

# ===== OTHER RPG COMMANDS (FIXED CHECKS) =====
async def rpg_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)

    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return

    if user_id not in user_data or 'rpg_character' not in user_data[user_id]:
        await update.message.reply_text("Use /rpg_start first to create your character! 🎮")
        return

    char = user_data[user_id]['rpg_character']
    await update.message.reply_text(
        f"📊 *CHARACTER STATS* ⚔️\n\n"
        f"**Name:** {char['name']}\n"
        f"**Class:** {char['class']}\n"
        f"**Level:** {char.get('level', 1)}\n"
        f"**EXP:** {char.get('experience', 0)}/100\n"
        f"**Sanity:** {char.get('sanity', 100)}/100\n"
        f"**Fear Resistance:** {char.get('fear_resistance', 10)}\n\n"
        f"_Keep adventuring to level up!_ 👻",
        parse_mode='HTML'
    )





# ===== AI RPG SYSTEM =====
def generate_horror_scenario(user_id):
    """Use AI to generate COMPLETE horror scenarios without truncation"""
    # Check if RPG data exists
    if user_id not in user_data or 'rpg_character' not in user_data[user_id]:
        return None
    
    char = user_data[user_id]['rpg_character']
    username = user_data[user_id].get('nickname', char['name'])
    
    ai_prompt = f"""
Create a COMPLETE horror RPG scenario for {username}, a {char['class']}. 
Location: {user_data[user_id]['rpg_location']}

REQUIREMENTS:
- Write 5-8 COMPLETE sentences - DO NOT TRUNCATE
- Create an immersive, atmospheric horror scene
- Include supernatural horror elements
- End with a clear decision point
- Make it personal for {username}
- Ensure the story feels complete

SCENARIO FORMAT:
[5-8 complete sentences of immersive horror description]
[Clear ending that sets up player choice]

BRAVE OPTION: [1 sentence describing brave action]
CAUTIOUS OPTION: [1 sentence describing cautious action]
FLEE OPTION: [1 sentence describing fleeing action]
"""

    try:
        response = model.generate_content(ai_prompt)
        text = response.text.strip()
        
        # Ensure we have complete content
        if '...' in text or len(text) < 100:
            # Retry with more specific instructions
            retry_prompt = ai_prompt + "\n\nIMPORTANT: Write COMPLETE sentences. Do not end with '...' or truncate."
            response = model.generate_content(retry_prompt)
            text = response.text.strip()
        
        print(f"-> Generated COMPLETE scenario: {len(text)} characters")
        return text
    except Exception as e:
        print(f"-> Scenario AI Error: {e}")
        return get_fallback_scenario(username, char['class'])

def get_fallback_scenario(username, char_class):
    """Fallback scenarios if AI fails"""
    fallbacks = [
        f"""
The ancient trees of Shadow Forest whisper your name, {username}. Moonlight filters through skeletal branches, casting dancing shadows that seem to reach for you. A cold mist rises from the swampy ground, carrying the scent of decay and old magic. In the distance, a child's laughter echoes, but there are no children for miles. The laughter turns to weeping, then to an unnatural silence that presses against your ears. You stand at a crossroads: the left path glows with faint ethereal light, the right descends into pitch darkness.

BRAVE OPTION: Follow the glowing path toward the mysterious light
CAUTIOUS OPTION: Investigate the weeping sound from the shadows
FLEE OPTION: Retreat back to the safety of the village
""",
        f"""
{username}, your lantern flickers as you enter the abandoned asylum. Dust dances in the beam of light, settling on broken furniture and medical equipment left to rot. Faint scratching sounds come from behind a rusted iron door at the end of the hall. A cold draft makes the hair on your neck stand up, and you notice fresh footprints in the dust that weren't there moments ago. The air grows heavy with the scent of ozone and old blood.

BRAVE OPTION: Force open the rusted iron door
CAUTIOUS OPTION: Search the nearby rooms for clues first  
FLEE OPTION: Get out before whatever is here finds you
"""
    ]
    return random.choice(fallbacks)


def save_rpg_leaderboard():
    """Save RPG leaderboard to file"""
    try:
        with open('rpg_leaderboard.json', 'w') as f:
            json.dump(RPG_LEADERBOARD, f)
    except:
        pass



def load_rpg_leaderboard():
    """Load RPG leaderboard from file"""
    global RPG_LEADERBOARD
    try:
        if os.path.exists('rpg_leaderboard.json'):
            with open('rpg_leaderboard.json', 'r') as f:
                RPG_LEADERBOARD = json.load(f)
    except:
        RPG_LEADERBOARD = {}

# Call in main() after other loads
# 





# Add to your user data initialization
def init_rpg_leaderboard(user_id, username):
    """Initialize RPG leaderboard entry for user"""
    uid = int(user_id)  # Ensure int
    if uid not in RPG_LEADERBOARD:
        RPG_LEADERBOARD[uid] = {'score': 0, 'username': username}
    save_rpg_leaderboard()


def update_rpg_score(user_id, exp_gain, username):
    """Update user's RPG score (experience)"""
    uid = int(user_id)
    init_rpg_leaderboard(uid, username)
    RPG_LEADERBOARD[uid]['score'] += exp_gain
    RPG_LEADERBOARD[uid]['username'] = username
    save_rpg_leaderboard()



def update_leaderboard(user_id, stat_type, value=1):
    """Update leaderboard stats"""
    init_rpg_leaderboard(user_id)
    user_data[user_id]['rpg_leaderboard'][stat_type] += value

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lb = load_leaderboard()
    if not lb:
        await update.message.reply_text("🏅 No battles recorded yet.")
        return
    # Sort by wins descending
    sorted_lb = sorted(lb.items(), key=lambda x: x[1], reverse=True)[:10]
    text = "🏆 <b>Top 10 Warriors</b>\n\n"
    for i, (uid, wins) in enumerate(sorted_lb, 1):
        text += f"{mention(user)}{i}. <a href='tg://user?id={uid}'>User {uid}</a> — {wins} wins\n"
    await update.message.reply_text(text, parse_mode="HTML")
    
async def battle_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(BATTLE_HISTORY_FILE):
        await update.message.reply_text("📜 No past battles found.")
        return
    with open(BATTLE_HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    if not history:
        await update.message.reply_text("📜 No past battles yet.")
        return
    last = history[-1]
    text = (
        f"🕒 <b>Last Battle Summary</b>\n"
        f"Winner: <b>{last.get('winner').upper()}</b>\n"
        f"👻 Ghosts HP: {last.get('ghosts_hp')} | Damage: {last.get('ghosts_damage')}\n"
        f"🧟 Zombies HP: {last.get('zombies_hp')} | Damage: {last.get('zombies_damage')}\n"
        f"Started: {last.get('started_at')}\nEnded: {last.get('ended_at')}"
    )
    await update.message.reply_text(text, parse_mode="HTML")

    
        # Sort by level and experience
    leaderboard_data.sort(key=lambda x: (x['level'], x['total_exp']), reverse=True)
    
    leaderboard_text = "🏆 *HORROR RPG LEADERBOARD* 🏆\n\n"
    
    if not leaderboard_data:
        leaderboard_text += "No adventurers yet! Use /rpg_start to join the horror!"
    else:
        for i, player in enumerate(leaderboard_data[:10]):  # Top 10
            rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            leaderboard_text += f"{rank_emoji[i] if i < len(rank_emoji) else f'{i+1}.'} *{player['username']}*\n"
            leaderboard_text += f"   ⚡ Level {player['level']} | 📊 {player['total_exp']} EXP | 🎯 {player['quests_completed']} Quests\n"
            leaderboard_text += f"   👹 {player['monsters_defeated']} Monsters | 🎒 {player['items_collected']} Items\n\n"
    
    leaderboard_text += "\n*Your RPG Commands:*\n/adventure - New quest\n/stats - Your character\n/inventory - Your items"
    
    await update.message.reply_text(leaderboard_text, parse_mode='HTML')





# Enhanced RPG items with actual usage
# Add this near the top with other configurations
# Update your RPG_ITEMS dictionary to include the display names
RPG_ITEMS = {
    'flashlight': {
        'name': 'Flashlight 🔦',
        'display_name': 'Flashlight 🔦',  # Add this
        'description': 'Reveals hidden paths and secrets',
        'usage': 'Use in dark areas to find clues',
        'effect': 'reveal_secrets'
    },
    'holy_water': {
        'name': 'Holy Water 💧',
        'display_name': 'Holy Water 💧',  # Add this
        'description': 'Repels undead and demons',
        'usage': 'Use against supernatural enemies',
        'effect': 'repel_undead'
    },
    'old_journal': {
        'name': 'Old Journal 📖',
        'display_name': 'Old Journal 📖',  # Add this
        'description': 'Contains clues and lore',
        'usage': 'Read for hints about current location',
        'effect': 'get_hints'
    },
    'silver_bullet': {
        'name': 'Silver Bullet 🎯',
        'display_name': 'Silver Bullet 🎯',  # Add this
        'description': 'Effective against werewolves',
        'usage': 'Use in combat against lycanthropes', 
        'effect': 'damage_werewolves'
    },
    'herbs': {
        'name': 'Mystical Herbs 🌿',
        'display_name': 'Mystical Herbs 🌿',  # Add this
        'description': 'Restores sanity and health',
        'usage': 'Use to recover from fear',
        'effect': 'restore_sanity'
    },
    'camera': {
        'name': 'Spirit Camera 📷',
        'display_name': 'Spirit Camera 📷',  # Add this
        'description': 'Can photograph ghosts',
        'usage': 'Use to reveal invisible spirits',
        'effect': 'reveal_ghosts'
    },
    'enhanced_holy_water': {
        'name': 'Enhanced Holy Water 💧',
        'display_name': 'Enhanced Holy Water 💧',  # Add this
        'description': 'Twice as effective against undead',
        'usage': 'Use against powerful supernatural enemies',
        'effect': 'strong_repel_undead'
    }
}

# Create a reverse mapping from display name to key
ITEM_DISPLAY_TO_KEY = {item_data['display_name']: key for key, item_data in RPG_ITEMS.items()}



async def use_item_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Use an item from inventory - FIXED VERSION"""
    user_id = str(update.effective_user.id)
    
    if user_id not in user_data or 'rpg_inventory' not in user_data[user_id]:
        await update.message.reply_text("Use /rpg_start first to create your character! 🎮")
        return
    
    if not context.args:
        # Show usable items
        inventory = user_data[user_id]['rpg_inventory']
        
        usable_items = []
        for inventory_item in inventory:
            # Find the item data for this inventory item
            for key, item_data in RPG_ITEMS.items():
                if item_data['display_name'] == inventory_item:
                    usable_items.append((inventory_item, key))
                    break
        
        if not usable_items:
            await update.message.reply_text(
                "🎒 *No usable items in inventory!*\n\n"
                "You'll find items during your adventures. Try /adventure!\n\n"
                "*Usable Items:*\n"
                "• Flashlight 🔦 - Reveals secrets\n"
                "• Holy Water 💧 - Repels undead\n" 
                "• Old Journal 📖 - Provides hints\n"
                "• Silver Bullet 🎯 - Damages werewolves\n"
                "• Mystical Herbs 🌿 - Restores sanity\n"
                "• Spirit Camera 📷 - Reveals ghosts\n"
                "• Enhanced Holy Water 💧 - Strong vs undead",
                parse_mode='HTML'
            )
            return
        
        keyboard = []
        for item_name, item_key in usable_items:
            item_data = RPG_ITEMS[item_key]
            keyboard.append([InlineKeyboardButton(
                f"{item_name} - {item_data['description']}", 
                callback_data=f"use_item_{item_key}"  # Use the key, not display name
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎒 *USE ITEM*\n\nSelect an item to use:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return
    
    # If user provided item name as argument
    item_name = " ".join(context.args)
    await process_item_usage(update, user_id, item_name)


async def process_item_usage(update, user_id, item_key_or_name):
    """Process using an item - FIXED VERSION with proper indentation"""
    inventory = user_data[user_id]['rpg_inventory']
    char = user_data[user_id]['rpg_character']
    
    print(f"-> Looking for item: '{item_key_or_name}' in inventory: {inventory}")  # Debug
    
    # Find the item - handle both keys and display names
    item_to_use = None
    item_data = None
    
    # Case 1: It's already an item key from RPG_ITEMS
    if item_key_or_name in RPG_ITEMS:
        item_data = RPG_ITEMS[item_key_or_name]
        item_to_use = item_data['display_name']
    
    # Case 2: It's a display name from inventory
    elif item_key_or_name in ITEM_DISPLAY_TO_KEY:
        item_key = ITEM_DISPLAY_TO_KEY[item_key_or_name]
        item_data = RPG_ITEMS[item_key]
        item_to_use = item_key_or_name
    
    # Case 3: Search for partial match in inventory
    else:
        for inventory_item in inventory:
            # Check if the provided string matches any inventory item
            if (item_key_or_name.lower() in inventory_item.lower() or 
                any(keyword in inventory_item.lower() for keyword in item_key_or_name.lower().split())):
                
                # Find the corresponding item data
                for key, data in RPG_ITEMS.items():
                    if data['display_name'] == inventory_item:
                        item_to_use = inventory_item
                        item_data = data
                        break
                if item_data:
                    break
    
    if not item_to_use or item_to_use not in inventory:
        # Try one more time with direct inventory search
        for inventory_item in inventory:
            if item_key_or_name.lower() in inventory_item.lower():
                item_to_use = inventory_item
                # Find item data
                for key, data in RPG_ITEMS.items():
                    if data['display_name'] == inventory_item:
                        item_data = data
                        break
                break
    
    if not item_to_use or not item_data:
        print(f"-> Item not found: {item_key_or_name}")
        if hasattr(update, 'message'):
            await update.message.reply_text(f"❌ Item '{item_key_or_name}' not found in inventory!")
        else:
            await update.edit_message_text(f"❌ Item '{item_key_or_name}' not found in inventory!")
        return
    
    print(f"-> Using item: {item_to_use}")  # Debug
    
    # Apply item effects - FIXED INDENTATION STARTS HERE
    effect_results = {
        'reveal_secrets': f"🔦 *{item_data['name']} used!*\n\nThe beam reveals hidden symbols on the wall... 'Beware the whispering trees' they say. You feel more aware of your surroundings.",
        'repel_undead': f"💧 *{item_data['name']} used!*\n\nThe spirits recoil from the holy water! You gain +10 temporary Sanity! The undead seem to keep their distance.",
        'get_hints': f"📖 *{item_data['name']} used!*\n\nYou read an ancient passage: 'The creature fears pure silver and cannot cross running water. Its weakness is its reflection.'",
        'damage_werewolves': f"🎯 *{item_data['name']} used!*\n\nSilver bullet loaded into your weapon! Next werewolf encounter will be much easier! The silver gleams with protective energy.",
        'restore_sanity': f"🌿 *{item_data['name']} used!*\n\nCalming herbs restore your mind! The fog of fear lifts slightly. +15 Sanity!",
        'reveal_ghosts': f"📷 *{item_data['name']} used!*\n\nThe camera flash reveals spectral forms floating nearby! Now you can see what was invisible before.",
        'strong_repel_undead': f"💧 *Enhanced Holy Water used!*\n\nPowerful holy energy creates a protective barrier! All undead creatures recoil in agony. +20 Sanity and temporary protection!",
        'damage_reduction': f"🛡️ *Protective Amulet glows!*\n\nThe amulet creates a shimmering shield around you. Supernatural attacks feel less threatening. Damage reduced by 20%!",
        'knowledge_boost': f"📚 *Ancient Tome knowledge flows through you!*\n\nForbidden knowledge enhances your abilities. You'll gain 25% more experience from all sources!"
    }
    
    result = effect_results.get(item_data['effect'], f"*{item_data['name']} used!* Strange energy flows through you...")
    
    # Update stats based on item - PROPER INDENTATION
    if item_data['effect'] == 'restore_sanity':
        char['sanity'] = min(100, char['sanity'] + 15)
        result += f"\n\n🧠 Sanity: {char['sanity']}%"
    elif item_data['effect'] in ['repel_undead', 'strong_repel_undead']:
        sanity_boost = 10 if item_data['effect'] == 'repel_undead' else 20
        char['sanity'] = min(100, char['sanity'] + sanity_boost)
        result += f"\n\n🧠 Sanity: {char['sanity']}%"
    
    # Remove consumable items (except flashlight/journal/camera)
    non_consumable = ['Flashlight 🔦', 'Old Journal 📖', 'Spirit Camera 📷']
    if item_to_use not in non_consumable:
        if item_to_use in user_data[user_id]['rpg_inventory']:
            user_data[user_id]['rpg_inventory'].remove(item_to_use)
            result += f"\n\n✅ {item_data['name']} consumed!"
        else:
            result += f"\n\n⚠️ {item_data['name']} was already used!"
    
    # Save the data


    # Send result based on whether it's a message or callback query
    if hasattr(update, 'message'):
        await update.message.reply_text(result, parse_mode='HTML')
    else:
        await update.edit_message_text(result, parse_mode='HTML')



async def save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual save command"""
    user_id = str(update.effective_user.id)
    if smart_save(user_id):
        await update.message.reply_text("💾 Your progress has been saved!")
    else:
        await update.message.reply_text("❌ Save failed! Contact support.")




async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user stats including save status"""
    user_id = str(update.effective_user.id)
    
    if user_id not in user_data:
        await update.message.reply_text("Use /start first!")
        return
    
    user_info = user_data[user_id]
    char = user_info.get('rpg_character', {})
    
    stats_text = f"""
📊 *USER STATS* 📊

👤 *Name:* {user_info.get('nickname', 'Unknown')}
💫 *Premium:* {'✅ Active' if is_premium_user(user_id) else '❌ Inactive'}
🎮 *RPG Level:* {char.get('level', 0)}
🎒 *Items:* {len(user_info.get('rpg_inventory', []))}
🏆 *Achievements:* {len(user_info.get('rpg_achievements', []))}
🧌 *Monsters Created:* {len(user_info.get('created_monsters', []))}

💾 *Data Status:* Saved automatically on important actions
🛠️ *Manual Save:* /save
"""
    
    await update.message.reply_text(stats_text, parse_mode='HTML')






    








def process_action_outcome(user_id, action_type, scenario_text):
    """Use AI to generate consequences for player actions"""
    
    action_descriptions = {
        'brave': "BRAVE action",
        'cautious': "CAUTIOUS action", 
        'flee': "FLEEING from danger"
    }
    
    ai_prompt = f"""
The player took a {action_descriptions[action_type]} in this scenario:
{scenario_text}

Generate SHORT consequences (max 3 sentences):
- What happened?
- What did they gain/lose?

Format:
OUTCOME: [2-3 sentence dramatic outcome]
"""
    
    try:
        response = model.generate_content(ai_prompt)
        return response.text.strip()
    except Exception as e:
        print(f"-> Outcome AI Error: {e}")
        return None

async def handle_rpg_action(update: Update, action_type: str):
    """Handle RPG actions with auto-voice"""
    user_id = str(update.effective_user.id)
    
    # Check if user has RPG data
    if user_id not in user_data or 'rpg_character' not in user_data[user_id]:
        await update.message.reply_text("Use /rpg_start first to create your character! 🎮")
        return
    
    rpg_state = get_rpg_state(user_id)
    
    # Validate game state
    if not rpg_state or rpg_state['status'] != RPGState.ACTIVE:
        await update.message.reply_text("Start an adventure first with /adventure! 🎮")
        return
    
    char = user_data[user_id]['rpg_character']
    scenario_text = rpg_state['current_adventure']
    
    # Generate outcome using AI
    outcome_text = process_action_outcome(user_id, action_type, scenario_text)
    if not outcome_text:
        await update.message.reply_text("The void swallowed your action... try again! 🌌")
        return
    
    # Update character stats
    exp_gain, sanity_loss, level_up_msg = update_character_stats(user_id, action_type)
    
    # Mark adventure as completed
    rpg_state['status'] = RPGState.COMPLETED
    
    # Action-specific info
    action_info = {
        'brave': {'emoji': '⚔️', 'title': 'BRAVE ACTION TAKEN'},
        'cautious': {'emoji': '🛡️', 'title': 'CAUTIOUS ACTION TAKEN'}, 
        'flee': {'emoji': '🏃', 'title': 'ESCAPED FROM DANGER'}
    }
    
    # Create brief result text
    result_text = f"""
{action_info[action_type]['emoji']} *{action_info[action_type]['title']}*

{outcome_text}

⭐ EXP: +{exp_gain} | 🧠 Sanity: -{sanity_loss}
{level_up_msg}

/adventure - Continue journey
"""
    
    # Send text result
    await update.message.reply_text(result_text, parse_mode='HTML')
    
    await auto_voice_message(
    update.message,  # ← Fix only this line
    scenario_text,
    "🎧 Listen to your nightmare... 👻"
)

async def rpg_adventure(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new horror RPG adventure with COMPLETE stories (persistent version)"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)

    now = datetime.now()
    cooldown_time = timedelta(minutes=2) if is_premium_user(user_id) else timedelta(minutes=10)

    if user_id in RPG_COOLDOWN:
        next_time = RPG_COOLDOWN[user_id]
        if now < next_time:
            remaining = (next_time - now).seconds
            minutes = remaining // 60
            seconds = remaining % 60
            await update.message.reply_text(
                f"🕒 Your courage is still recovering...\n"
                f"Please wait {minutes}m {seconds}s before starting another RPG quest. ⚔️",
                parse_mode="HTML"
            )
            return

    RPG_COOLDOWN[user_id] = now + cooldown_time

    

    # Restrict to private chats only
    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return
    # === Ensure user has RPG data ===
    if user_id not in user_data or 'rpg_character' not in user_data[user_id]:
        await update.message.reply_text("Use /rpg_start first to create your character! 🎮")
        return
    
    # Get RPG state safely
    rpg_state = get_rpg_state(user_id)
    char = user_data[user_id]['rpg_character']
    username = user_data[user_id].get('nickname', char['name'])
    
    # === Generate horror scenario ===
    scenario_text = generate_horror_scenario(user_id)
    if not scenario_text:
        await update.message.reply_text("The spirits are blocking my vision... try again! 👻")
        return
    
    # === Parse options ===
    brave_option = "Charge forward bravely"
    cautious_option = "Proceed with caution"
    flee_option = "Retreat from danger"
    
    if "BRAVE OPTION:" in scenario_text:
        parts = scenario_text.split("BRAVE OPTION:")
        scenario_text = parts[0].strip()
        if "CAUTIOUS OPTION:" in parts[1]:
            subparts = parts[1].split("CAUTIOUS OPTION:")
            brave_option = subparts[0].strip()
            if "FLEE OPTION:" in subparts[1]:
                final_parts = subparts[1].split("FLEE OPTION:")
                cautious_option = final_parts[0].strip()
                flee_option = final_parts[1].strip()

    # === Store the scenario and options ===
    rpg_state['current_adventure'] = scenario_text
    rpg_state['brave_option'] = brave_option
    rpg_state['cautious_option'] = cautious_option
    rpg_state['flee_option'] = flee_option
    rpg_state['status'] = RPGState.ACTIVE

    # ✅ Save progress immediately (new addition)
    user_data[user_id]['rpg_state'] = rpg_state


    # === Check inventory for bonuses ===
    inventory = user_data[user_id].get('rpg_inventory', [])
    item_bonus = ""
    
    if 'Flashlight 🔦' in inventory:
        item_bonus += "🔦 Your flashlight might reveal secrets!\n"
    if 'Holy Water 💧' in inventory:
        item_bonus += "💧 Holy water could repel evil here!\n"
    
    # === Construct adventure text ===
    adventure_text = f"""
🌑 <b>NIGHTMARE QUEST</b> 🗺️
<b>{username}</b> in {user_data[user_id]['rpg_location']}

{scenario_text}

{item_bonus}
<b>CHOOSE YOUR ACTION:</b>

⚔️ /action1 - {brave_option}
🛡️ /action2 - {cautious_option}
🏃 /flee - {flee_option}

💡 <i>Tip:</i> Use /use_item if you have helpful items!
"""

    await update.message.reply_text(adventure_text, parse_mode='HTML')

    # === Auto-play voice narration ===
    clean_scenario = scenario_text.replace('*', '').replace('_', '')
    await auto_voice_message(update.message, clean_scenario, f"🎧 {username}'s Adventure 🔊")

    # ✅ Optional: Confirm saved
    print(f"💾 RPG adventure saved for {username} ({user_id})")



async def craft_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Craft new items from collected resources"""
    user_id = str(update.effective_user.id)
    
    if user_id not in user_data or 'rpg_inventory' not in user_data[user_id]:
        await update.message.reply_text("Use /rpg_start first! 🎮")
        return
    
    char = user_data[user_id]['rpg_character']
    
    craftable_items = {
        'Silver Bullet 🎯': {'requires': ['Mystical Herbs 🌿', 'Old Journal 📖'], 'gives': 'Silver Bullet 🎯'},
        'Spirit Camera 📷': {'requires': ['Flashlight 🔦', 'Old Journal 📖'], 'gives': 'Spirit Camera 📷'},
        'Enhanced Holy Water 💧': {'requires': ['Holy Water 💧', 'Mystical Herbs 🌿'], 'gives': 'Enhanced Holy Water 💧'},
    }
    
    inventory = user_data[user_id]['rpg_inventory']
    
    craft_options = []
    for item_name, recipe in craftable_items.items():
        if all(req in inventory for req in recipe['requires']):
            craft_options.append((item_name, recipe))
    
    if not craft_options:
        await update.message.reply_text(
            "🔧 *No crafting options available!*\n\n"
            "You need specific items to craft. Continue adventuring to find resources!\n\n"
            "*Available Recipes:*\n"
            "• Silver Bullet: Herbs + Journal\n"
            "• Spirit Camera: Flashlight + Journal\n" 
            "• Enhanced Holy Water: Holy Water + Herbs",
            parse_mode='HTML'
        )
        return
    
    keyboard = []
    for item_name, recipe in craft_options:
        keyboard.append([InlineKeyboardButton(
            f"🔧 Craft {item_name}", 
            callback_data=f"craft_{item_name.replace(' ', '_')}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔧 *CRAFTING STATION*\n\nSelect an item to craft:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )




    # AUTO-PLAY AUDIO VERSION - READ ENTIRE SCENARIO

async def rpg_action1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Take brave action in current adventure"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    
    # Restrict to private chats only
    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return
    if user_id not in user_data or 'rpg_character' not in user_data[user_id]:
        await update.message.reply_text("Use /rpg_start first! 🎮")
        return
    
    rpg_state = get_rpg_state(user_id)
    
    if not rpg_state or rpg_state['status'] != RPGState.ACTIVE:
        await update.message.reply_text("Start an adventure first with /adventure! 🎮")
        return
    
    char = user_data[user_id]['rpg_character']
    
    # Brave action outcomes
    outcomes = [
        "You charge forward! The spirits scatter before your courage. +20 EXP, -10 Sanity",
        "Your bold move reveals a hidden passage! +15 EXP, -8 Sanity", 
        "The entity recoils from your bravery! +25 EXP, -12 Sanity"
    ]
    
    outcome = random.choice(outcomes)
    char['experience'] += 20
    char['sanity'] = max(0, char['sanity'] - 10)
    
    # Mark adventure as completed
    rpg_state['status'] = RPGState.COMPLETED
    
    result_text = f"""
⚔️ *BRAVE ACTION TAKEN* 🎯

{outcome}

⭐ EXP: +20 | 🧠 Sanity: -10

/adventure - Continue journey
"""
    
    await update.message.reply_text(result_text, parse_mode='HTML')

async def rpg_action2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Take cautious action in current adventure"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    
    # Restrict to private chats only
    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return
    if user_id not in user_data or 'rpg_character' not in user_data[user_id]:
        await update.message.reply_text("Use /rpg_start first! 🎮")
        return
    
    rpg_state = get_rpg_state(user_id)
    
    if not rpg_state or rpg_state['status'] != RPGState.ACTIVE:
        await update.message.reply_text("Start an adventure first with /adventure! 🎮")
        return
    
    char = user_data[user_id]['rpg_character']
    
    # Cautious action outcomes
    outcomes = [
        "You proceed carefully... discovering clues others missed. +12 EXP, -5 Sanity",
        "Your caution saves you from a trap! +10 EXP, -3 Sanity",
        "You observe from the shadows, learning the entity's patterns. +15 EXP, -6 Sanity"
    ]
    
    outcome = random.choice(outcomes)
    char['experience'] += 12
    char['sanity'] = max(0, char['sanity'] - 5)
    
    # Mark adventure as completed
    rpg_state['status'] = RPGState.COMPLETED
    
    result_text = f"""
🛡️ *CAUTIOUS ACTION TAKEN* 🎯

{outcome}

⭐ EXP: +12 | 🧠 Sanity: -5

/adventure - Continue journey
"""
    
    await update.message.reply_text(result_text, parse_mode='HTML')

async def rpg_flee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Flee from current adventure"""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    
    # Restrict to private chats only
    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return
    if user_id not in user_data or 'rpg_character' not in user_data[user_id]:
        await update.message.reply_text("Use /rpg_start first! 🎮")
        return
    
    rpg_state = get_rpg_state(user_id)
    
    if not rpg_state or rpg_state['status'] != RPGState.ACTIVE:
        await update.message.reply_text("Start an adventure first with /adventure! 🎮")
        return
    
    char = user_data[user_id]['rpg_character']
    
    # Flee outcomes
    outcomes = [
        "You escape, but the horror follows in your dreams... +5 EXP, -15 Sanity",
        "You run, leaving part of your courage behind... +3 EXP, -12 Sanity",
        "The entity's laughter echoes as you flee... +8 EXP, -18 Sanity"
    ]
    
    outcome = random.choice(outcomes)
    char['experience'] += 5
    char['sanity'] = max(0, char['sanity'] - 15)
    
    # Mark adventure as completed
    rpg_state['status'] = RPGState.COMPLETED
    
    result_text = f"""
🏃 *ESCAPED FROM DANGER* 🎯

{outcome}

⭐ EXP: +5 | 🧠 Sanity: -15

/adventure - Continue journey
"""
    
    await update.message.reply_text(result_text, parse_mode='HTML')





async def rpg_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show inventory (private only, persistent)"""
    user_id = str(update.effective_user.id)  # int
    chat_id = str(update.effective_chat.id)

    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return

    char = get_rpg_character(user_id)
    if not char:
        await update.message.reply_text("Use /rpg_start first! 🎮")
        return

    inventory = user_data[user_id].get('rpg_inventory', [])
    inv_text = f"🎒 *INVENTORY* 🛡️\n\n"
    if inventory:
        for item in inventory:
            inv_text += f"• {item}\n"
    else:
        inv_text += "Empty... Gather items on your adventures!\n"
    
    inv_text += f"\n_Items persist across restarts!_ 🔮"
    await update.message.reply_text(inv_text, parse_mode='HTML')


async def rpg_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show RPG leaderboard (private only, persistent)"""
    user_id = str(update.effective_user.id)  # int
    chat_id = str(update.effective_chat.id)

    if int(chat_id) < 0:
        await update.message.reply_text("command works privately @spookynightbot")
        return

    # Assume RPG leaderboard is in user_data or separate file; for now, use a simple global
    # If not defined, create one
    if 'rpg_leaderboard' not in globals():
        global rpg_leaderboard
        rpg_leaderboard = {}  # {user_id: {'level': level, 'exp': exp, 'name': name}}

    # Update current user's score if playing
    char = get_rpg_character(user_id)
    if char:
        rpg_leaderboard[user_id] = {
            'level': char.get('level', 1),
            'exp': char.get('experience', 0),
            'name': char['name']
        }
        save_user_data()  # Save to persist leaderboard updates

    # Sort and display top 10
    sorted_lb = sorted(rpg_leaderboard.items(), key=lambda x: x[1]['level'] + (x[1]['exp']/100), reverse=True)[:10]
    lb_text = "🏆 *RPG LEADERBOARD* 🎮\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, (uid, data) in enumerate(sorted_lb):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        lb_text += f"{medal} *{data['name']}* - Lv.{data['level']} ({data['exp']} EXP)\n"
    
    if not sorted_lb:
        lb_text += "No adventurers yet! Be the first to level up!"
    
    lb_text += "\n_Leaderboards update with your progress!_ 🔮"
    await update.message.reply_text(lb_text, parse_mode='HTML')
    save_user_data()





def update_character_stats(user_id, action_type):
    char = user_data[user_id]['rpg_character']
    
    # Base rewards
    rewards = {
        'brave': {'exp': (15, 25), 'sanity': (10, 20)},
        'cautious': {'exp': (8, 15), 'sanity': (5, 12)},
        'flee': {'exp': (3, 8), 'sanity': (15, 25)}
    }
    
    exp_range, sanity_range = rewards[action_type]['exp'], rewards[action_type]['sanity']
    exp_gain = random.randint(exp_range[0], exp_range[1])
    sanity_loss = random.randint(sanity_range[0], sanity_range[1])
    
    # PREMIUM BONUS: 2x EXP for premium users
    if is_premium_user(user_id):
        exp_gain = exp_gain * 2
        print(f"-> Premium bonus: 2x EXP! (+{exp_gain} EXP)")
    
    char['experience'] += exp_gain
    char['sanity'] = max(0, char['sanity'] - sanity_loss)
    
    # ... rest of your existing code ...
    
    # Apply item bonuses (from crafted items)
    exp_multiplier = 1.0
    if 'Ancient Tome 📚' in user_data[user_id]['rpg_inventory']:
        exp_multiplier = 1.25  # 25% more EXP from Ancient Tome
    
    exp_gain = int(exp_gain * exp_multiplier)
    
    # Apply damage reduction from Protective Amulet
    damage_reduction = 1.0
    if 'Protective Amulet 🛡️' in user_data[user_id]['rpg_inventory']:
        damage_reduction = 0.8  # 20% damage reduction
        sanity_loss = int(sanity_loss * damage_reduction)
    
    # Apply event bonuses
    current_event = seasonal_manager.get_current_event()
    if current_event:
        event_bonuses = seasonal_manager.get_event_bonuses(current_event)
        if event_bonuses.get('rpg_exp', 1) > 1:
            exp_gain = int(exp_gain * event_bonuses['rpg_exp'])
    
    char['experience'] += exp_gain
    char['sanity'] = max(0, char['sanity'] - sanity_loss)
    
    # Update leaderboard
    update_leaderboard(user_id, 'total_exp', exp_gain)
    update_leaderboard(user_id, 'quests_completed', 1)
    update_leaderboard(user_id, 'monsters_defeated', monsters_defeated)
    
    # Random item find
    if random.random() < 0.3:  # 30% chance to find item
        location_items = HORROR_LOCATIONS.get(get_location_key(user_data[user_id]['rpg_location']), {}).get('items', [])
        if location_items and random.random() < 0.5:  # 50% chance for location-specific item
            new_item = random.choice(location_items)
            if new_item not in user_data[user_id]['rpg_inventory']:
                user_data[user_id]['rpg_inventory'].append(new_item)
                update_leaderboard(user_id, 'items_collected', 1)
    
    # Check for new achievements
    new_achievements = check_achievements(user_id)
    
    level_up_msg = ""
    if char['experience'] >= 100:
        char['level'] += 1
        char['experience'] = 0
        char['fear_resistance'] += 15
        level_up_msg = f"\n\n🎉 LEVEL UP! Now Level {char['level']}! +15 Fear Resistance"
        
        # Check for level-based achievements
        check_achievements(user_id)
    
    # Save progress

    
    return exp_gain, sanity_loss, level_up_msg, monsters_defeated, new_achievements



    
def get_location_key(location_name):
    """Get location key from location name"""
    for key, data in HORROR_LOCATIONS.items():
        if data['name'] == location_name:
            return key
    return "shadow_forest"





    return exp_gain, sanity_loss, level_up_msg# Update the update_character_stats function to include event bonuses
def update_character_stats(user_id, action_type):
    """Update character stats based on action type with event bonuses"""
    char = user_data[user_id]['rpg_character']
    
    rewards = {
        'brave': {'exp': (15, 25), 'sanity': (10, 20)},
        'cautious': {'exp': (8, 15), 'sanity': (5, 12)},
        'flee': {'exp': (3, 8), 'sanity': (15, 25)}
    }
    
    exp_range, sanity_range = rewards[action_type]['exp'], rewards[action_type]['sanity']
    
    exp_gain = random.randint(exp_range[0], exp_range[1])
    sanity_loss = random.randint(sanity_range[0], sanity_range[1])
    
    # Apply event bonuses
    current_event = seasonal_manager.get_current_event()
    if current_event:
        event_bonuses = seasonal_manager.get_event_bonuses(current_event)
        if event_bonuses.get('rpg_exp', 1) > 1:
            exp_gain = int(exp_gain * event_bonuses['rpg_exp'])
    
    char['experience'] += exp_gain
    char['sanity'] = max(0, char['sanity'] - sanity_loss)
    
    level_up_msg = ""
    if char['experience'] >= 100:
        char['level'] += 1
        char['experience'] = 0
        char['fear_resistance'] += 15
        level_up_msg = f"\n\n🎉 LEVEL UP! Now Level {char['level']}! +15 Fear Resistance"
    
    return exp_gain, sanity_loss, level_up_msg




# ===== HORROR AUDIO SYSTEM =====
def get_random_horror_audio():
    """Get random horror audio URL from multiple sources"""
    mixkit_sounds = [
        "https://od.lk/d/NTVfMzY4OTc4ODNf/creepy-laugh-2-401714.mp3",
        "https://od.lk/d/NTVfMzY4OTc4Nzdf/crowd-screaming-105007.mp3",
        "https://od.lk/d/NTVfMzY4OTc4ODBf/ritual-82775.mp3",
        "https://od.lk/d/NTVfMzY4OTc4ODdf/scary-sound-effect-298866.mp3",
        "https://od.lk/d/NTVfMzY4OTc4Nzlf/girl-scream-45657.mp3",
        "https://od.lk/d/NTVfMzY4OTc4ODJf/witch-laugh-401713.mp3",
        "https://od.lk/d/NTVfMzY4OTc4Nzhf/scary-transition-401717.mp3",
        "https://od.lk/d/NTVfMzY4OTc4ODRf/horror-hit-logo-142395.mp3",
        "https://od.lk/d/NTVfMzY4OTc4ODZf/scary-laugh-377526.mp3",
        "https://od.lk/d/NTVfMzY4OTc5MThf/astral-creepy-dark-logo-254198.mp3",
        "https://od.lk/d/NTVfMzY4OTc5MTZf/creepy-ghost-whisper-401712.mp3",
        "https://od.lk/d/NTVfMzY4OTc4ODNf/creepy-laugh-2-401714.mp3",
        "https://od.lk/d/NTVfMzY4OTc5MjVf/creepy-halloween-bells-loop-408748.mp3",
        "https://od.lk/d/NTVfMzY4OTc5MTdf/creepy-laugh-sound-203187.mp3",
        "https://od.lk/d/NTVfMzY4OTc4Nzdf/crowd-screaming-105007.mp3",
        "https://od.lk/d/NTVfMzY4OTc4ODFf/evil-laugh-49831.mp3",
        "https://od.lk/d/NTVfMzY4OTc4Nzlf/girl-scream-45657.mp3",
        "https://od.lk/d/NTVfMzY4OTc5MjFf/halloween-impact-05-93808.mp3",
        "https://od.lk/d/NTVfMzY4OTc5MjBf/halloween-is-here-255595.mp3",
        "https://od.lk/d/NTVfMzY4OTc5MjRf/halloween-wolf-howling-410542.mp33"
    ]
    
    return random.choice(mixkit_sounds)

async def download_audio(audio_url):
    """Download audio file from URL"""
    try:
        response = requests.get(audio_url, timeout=30)
        if response.status_code == 200:
            filename = f"horror_audio_{random.randint(1000,9999)}.mp3"
            with open(filename, 'wb') as f:
                f.write(response.content)
            return filename
        return None
    except Exception as e:
        print(f"Audio download error: {e}")
        return None

async def horror_sound_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send random horror audio to chat"""
    await update.message.reply_text("🎵 *Summoning haunted sounds...* 👻", parse_mode='HTML')
    
    try:
        audio_url = get_random_horror_audio()
        
        if audio_url:
            audio_file = await download_audio(audio_url)
            if audio_file:
                caption = "👻 *HAUNTED FREQUENCIES* 🔮\n\nThis sound was recorded from the other side... listen carefully..."
                await update.message.reply_audio(
                    audio=open(audio_file, 'rb'),
                    caption=caption,
                    title="Haunted Audio",
                    performer="The Void",
                    parse_mode='HTML'
                )
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            else:
                await update.message.reply_text("🔇 The spirits silenced the audio... try again! 👻")
        else:
            await update.message.reply_text("🔇 No haunted sounds available... the void is silent... 🌑")
            
    except Exception as e:
        print(f"Horror audio error: {e}")
        await update.message.reply_text("⚡ Audio summoning failed... the ghosts are interfering! 🔮")



async def announce_premium_join(user_id, username, plan, context):
    """Announce new premium user to group or all (requires context)"""
    # Retrieve user info safely
    user_info = user_data.get(str(user_id), {})
    first_name = user_info.get("first_name", "")
    tg_username = user_info.get("username", "")
    
    # Build a pretty display name
    if tg_username:
        display_name = f"{first_name} (@{tg_username})" if first_name else f"@{tg_username}"
    elif first_name:
        display_name = first_name
    else:
        display_name = f"User {user_id}"

    # ---- Send to group if configured ----
    if PREMIUM_ANNOUNCE_GROUP:
        try:
            await context.bot.send_message(
                chat_id=PREMIUM_ANNOUNCE_GROUP,
                text=(
                    f"👑 *New Soul Joins the Premium Realm!* 🎃\n\n"
                    f"<b>{display_name}</b> has awakened their premium powers with {plan}!\n"
                    f"Unlimited horrors await... Who's next? 🔮\n\n"
                    f"_SpookyBot Premium Souls Grow Stronger_ 👻"
                ),
                parse_mode="HTML"
            )
            print(f"✅ Premium announce sent to group for {display_name}")
        except Exception as e:
            print(f"❌ Group announce failed: {e}")

    # ---- Otherwise broadcast to all users ----
    else:
        users = list(user_data.keys())
        for uid in users:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=(
                        f"👑 *A New Premium Soul Awakens!* 🎃\n\n"
                        f"<b>{display_name}</b> just joined the elite with {plan}!\n"
                        f"The shadows welcome them... Will you join? /premium 🔮"
                    ),
                    parse_mode="Markdown"
                )
                await asyncio.sleep(0.05)
            except Exception as e:
                print(f"Failed broadcast to {uid}: {e}")










# ===== AI SUMMONING SYSTEM =====
async def summon_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to haunt specific users with AI-generated terror"""
    if not context.args:
        await update.message.reply_text(
            "⚡ *AI SUMMONING RITUAL*\n\n"
            "You must specify who to haunt:\n"
            "`/summon @username` - Haunt a specific user\n"
            "`/summon all` - Haunt everyone in chat\n\n"
            "*The AI demons demand a name...* 🔮",
            parse_mode='HTML'
        )
        return
    
    target = context.args[0].lower()
    
    if target == 'all':
        await mass_haunt(update, context)
        return
    
    # Remove @ if present
    if target.startswith('@'):
        target = target[1:]
    
    summoner = update.effective_user.first_name
    await update.message.reply_text(
        f"🌀 *{summoner} begins an AI summoning...*\n"
        f"*Targeting: {target}* 👁️\n\n"
        f"The neural networks stir... The Dark Awakens To A CALLLLL!!!!!!... 🌑",
        parse_mode='HTML'
    )
    
    # Creepy delay for effect
    await asyncio.sleep(2)
    
    # Send AI-generated targeted horror
    await send_ai_targeted_terror(update, target, summoner)

async def generate_ai_haunting_message(target_username, summoner_name, message_type="targeted"):
    """Use Gemini AI to generate creative haunting messages"""
    
    prompt_templates = {
        "targeted": f"""
Create a TERRIFYING and CREEPY haunting message targeting a specific user named "{target_username}" who was summoned by "{summoner_name}".

REQUIREMENTS:
- Make it PERSONALIZED to {target_username}
- Include psychological horror elements
- Use eerie, unsettling imagery
- 1-2 sentences maximum
- Include emojis for atmosphere
- Make it feel like a real supernatural threat
- Be creative and original - no clichés
- Format for Telegram with *bold* and _italic_

Create something NEW and TERRIFYING:
""",
        
        "mass_haunt": f"""
Create a TERRIFYING group haunting message that targets EVERYONE in a chat. Summoner: "{summoner_name}"

REQUIREMENTS:
- Target the entire group collectively
- Make it feel inescapable and overwhelming
- Use cosmic/eldritch horror themes
- 2-4 sentences maximum  
- Include emojis for atmosphere
- Format for Telegram with *bold* and _italic_
- Be creative and original

Create something NEW and TERRIFYING:
""",
        
        "curse": f"""
Create a QUICK, PUNCHY curse message for instant horror.

REQUIREMENTS:
- 1-2 sentences maximum
- Immediate impact
- Include emojis
- Format for Telegram with *bold* and _italic_
- Be creative and unexpected

Create something NEW and TERRIFYING:
"""
    }
    
    try:
        prompt = prompt_templates.get(message_type, prompt_templates["targeted"])
        response = model.generate_content(prompt)
        
        if response.text:
            # Clean up and format the AI response
            message = response.text.strip()
            
            # Ensure it has proper Telegram formatting
            if not any(tag in message for tag in ['*', '_', '👁️', '🔮', '🌑']):
                # Add some basic formatting if missing
                prefixes = ['👁️', '🔮', '🌑', '⚡', '💀', '👻', '🎭', '🕷️']
                message = f"{random.choice(prefixes)} *AI NIGHTMARE...*\n\n{message}"
            
            return message
        else:
            return get_fallback_message(target_username, summoner_name, message_type)
            
    except Exception as e:
        print(f"AI haunting generation error: {e}")
        return get_fallback_message(target_username, summoner_name, message_type)

def get_fallback_message(target_username, summoner_name, message_type):
    """Fallback messages if AI fails"""
    fallbacks = {
        "targeted": [
            f"👁️ *DIGITAL GHOST...* {target_username}... your online presence just developed a consciousness... and it's not friendly... 🌑",
            f"🔮 *ALGORITHMIC HAUNTING...* {target_username}, the AI learned your name from the summoning... now it whispers it in the code... 💻",
            f"⚡ *NEURAL INVASION...* {target_username}... {summoner_name} just gave the darkness your coordinates... expect strange dreams tonight... 💤"
        ],
        "mass_haunt": [
            "🌕 *COLLECTIVE NIGHTMARE...* Every device in this chat is now a doorway... and something is knocking from the other side... 📱",
            "⚡ *NETWORK INFECTION...* The digital plague spreads... your group chat is patient zero... the symptoms include creeping dread... 🦠",
            "🔮 *MASS HYPNOSIS...* All of you are now part of the same terrible dream... whose dream is it? 👁️"
        ],
        "curse": [
            "⚡ *QUICK CORRUPTION!* Your screen just gained a reflection... and it's smiling... 🖥️",
            "🔮 *INSTANT HEX!* The AI just assigned you a shadow... it arrives in 3... 2... 1... 🌑",
            "💀 *SPEED HAUNT!* Your digital footprint just grew hands... they're reaching for you... 👻"
        ]
    }
    
    return random.choice(fallbacks.get(message_type, fallbacks["targeted"]))

async def send_ai_targeted_terror(update, target_username, summoner_name):
    """Send AI-generated personalized horror to the target"""
    
    # Send multiple escalating AI-generated messages
    for i in range(3):
        try:
            message = await generate_ai_haunting_message(target_username, summoner_name, "targeted")
            await update.message.reply_text(message, parse_mode='HTML')
            await asyncio.sleep(3)
        except Exception as e:
            print(f"Error sending AI message: {e}")
            fallback = get_fallback_message(target_username, summoner_name, "targeted")
            await update.message.reply_text(fallback, parse_mode='HTML')
            await asyncio.sleep(3)
    
    # Final AI-generated curse message
    try:
        final_message = await generate_ai_haunting_message(target_username, summoner_name, "targeted")
        # Make final message more dramatic
        final_message = f"⚰️ *AI CURSE COMPLETE*\n\n{final_message}\n\n{target_username} is now forever in the machine's memory... 🔥"
        await update.message.reply_text(final_message, parse_mode='HTML')
    except Exception as e:
        print(f"Error sending final AI message: {e}")
        final_fallback = f"⚰️ *DIGITAL DAMNATION*\n\n{target_username}... the algorithms have your scent now... forever hunted in the digital wilderness... 🌑"
        await update.message.reply_text(final_fallback, parse_mode='HTML')

async def mass_haunt(update, context):
    """Haunt everyone in the chat with AI-generated terror"""
    summoner_name = update.effective_user.first_name
    
    await update.message.reply_text(
        f"🌕 *AI MASS SUMMONING INITIATED...*\n\n"
        f"EVERY SOUL... EVERY MIND IN THIS CHAT...\n"
        f"{summoner_name} has unleashed the digital demons... 🔥",
        parse_mode='HTML'
    )
    
    await asyncio.sleep(2)
    
    # Send multiple AI-generated mass haunting messages
    for i in range(4):
        try:
            message = await generate_ai_haunting_message("EVERYONE", summoner_name, "mass_haunt")
            await update.message.reply_text(message, parse_mode='HTML')
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Error sending mass AI message: {e}")
            fallback = get_fallback_message("EVERYONE", summoner_name, "mass_haunt")
            await update.message.reply_text(fallback, parse_mode='HTML')
            await asyncio.sleep(2)
    
    # Final AI-generated mass curse
    try:
        final_message = await generate_ai_haunting_message("THE COLLECTIVE", summoner_name, "mass_haunt")
        final_message = f"🎪 *DIGITAL CARNIVAL OF TERROR*\n\n{final_message}\n\nAll tickets are one-way... enjoy the ride... 🎭"
        await update.message.reply_text(final_message, parse_mode='HTML')
    except Exception as e:
        print(f"Error sending final mass AI message: {e}")
        final_fallback = "⚰️ *COLLECTIVE DAMNATION*\n\nThe entire chat is now a haunted server... Welcome to eternity in the machine... 💀"
        await update.message.reply_text(final_fallback, parse_mode='HTML')

async def curse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick AI-generated curse command for instant horror"""
    try:
        curse_message = await generate_ai_haunting_message("", update.effective_user.first_name, "curse")
        await update.message.reply_text(curse_message, parse_mode='HTML')
    except Exception as e:
        print(f"AI curse error: {e}")
        fallback_curses = [
            "⚡ *INSTANT CORRUPTION!* Your digital shadow just stood up and walked away... 🌑",
            "🔮 *QUICK HEX!* The AI just learned your fear response... testing it now... 😨",
            "💀 *SPEED HAUNT!* Your screen's pixels are rearranging into something... familiar... 👁️"
        ]
        await update.message.reply_text(random.choice(fallback_curses), parse_mode='HTML')

# ===== QUICK COMMANDS =====
async def horrorfact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send random horror fact"""
    horror_facts = [
        "🩸 The word 'nightmare' comes from 'mare' - a demon that sits on sleepers' chests",
        "👻 Some cultures believe ghosts can't cross running water",
        "🕷️ The fear of long words is called 'hippopotomonstrosesquippedaliophobia'",
        "🎭 In Victorian times, people took photos with dead relatives as 'memento mori'",
        "🔮 Some asylums used spinning chairs to 'shake the madness out' of patients",
        "🪲 A cockroach can live for weeks without a head",
        "⚰️ In ancient Rome, people believed the deceased could come back to life as 'revenants'",
        "🕯️ It was once believed that a person's soul could be sneezed out, so people would say 'bless you'",
        "🪞 In some superstitions, breaking a mirror doesn't bring bad luck, but instead traps your soul within it",
        "🐈‍⬛ In ancient Egypt, black cats were worshiped and considered good luck",
        "👣 The human body can have up to 206 bones, but babies are born with 300 bones",
        "💡 The fear of Friday the 13th is known as 'paraskevidekatriaphobia'",
        "🐀 Some groups of rats can get their tails tangled together, forming a 'Rat King'",
        "🕷️ The blood of spiders is blue, due to a copper-based molecule",
        "💀 The human body has over 206 bones, but babies are born with 300",
        "🦴 Dentures were once made from the teeth of dead soldiers",
        "🧠 Exploding Head Syndrome causes loud, explosive noises to be heard inside your head",
        "🪦 In some ancient traditions, bodies were ritually bound before burial to prevent them from becoming revenants",
        "😳 Some people have a phobia of long words: Hippopotomonstrosesquippedaliophobia",
        "🫀 Your heart can continue to beat for a short time after being removed from the body",
        "👂 Your nose and ears never stop growing throughout your life",
        "🤯 Some people experience 'Exploding Head Syndrome', hearing a loud bang as they fall asleep",
        "🌌 Scientists estimate that 90% of the cells in your body are non-human",
        "💀 The human head remains conscious for about 20 seconds after decapitation",
        "🦷 Anesthetics don't stop you from feeling pain; they just make you forget it",
        "👣 Your brain can trick you into seeing a shadowy figure in your peripheral vision",
        "⏳ Scientists estimate that as many as 153,000 people die on your birthday every year",
        "👽 More than 80% of the world's oceans are still unexplored and contain unknown life",
        "🚪 There are several reports of people hearing a phantom door knock just before a family death",
        "💡 Exploding Head Syndrome is a condition where people hear loud, explosive noises as they fall asleep",
        "🧠 The human brain can sometimes create an invisible, imaginary companion to help cope with loneliness",
        "👻 Studies suggest that people who believe in ghosts process visual information differently",
        "💀 The human body continues to produce skin and grow hair and nails for a short time after death",
        "🤫 Forensic investigators have documented cases where people have confessed to a murder in their sleep",
        "🪦 The fear of being buried alive is known as 'taphophobia', and it was a common fear in the 19th century",
        "🌌 Some scientists theorize that the universe will end in a 'Big Crunch' rather than a 'Big Freeze'",
        "👀 A person's pupils can dilate when they are frightened, making them appear more intimidating to a predator",
        "💀 After a person's death, hair and nails appear to grow for a few days due to the skin retracting",
        "🧟 Some people have a parasitic condition where they are controlled by a fungus, known as 'zombie ants'",
        "🪦 Safety coffins were invented in the 19th century out of fear of being buried alive",
        "🫀 The human brain can generate entirely false memories that feel completely real",
        "🦠 Your phone has more bacteria on it than a public toilet seat",
        "🧠 The human brain named itself",
        "🌌 There are many theories about the universe, one being that it will end in a 'Big Crunch"




    ]
    
    fact = random.choice(horror_facts)
    await update.message.reply_text(f"📚 *HORROR FACT* 🕯️\n\n{fact}", parse_mode='HTML')

async def halloweencountdown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show days until Halloween"""
    today = datetime.now()
    halloween = datetime(today.year, 10, 31)
    
    if today > halloween:
        halloween = datetime(today.year + 1, 10, 31)
    
    days_until = (halloween - today).days
    
    if days_until == 0:
        message = "🎃 *IT'S HALLOWEEN!* 🕸️\n\nThe veil is thin... the spirits walk among us... 👻"
    elif days_until == 1:
        message = "😱 *ONLY 1 DAY UNTIL HALLOWEEN!* 🌑\n\nThe final countdown begins... brace yourself!"
    elif days_until <= 7:
        message = f"👻 *ONLY {days_until} DAYS UNTIL HALLOWEEN!* 🕯️\n\nThe darkness is gathering power..."
    elif days_until <= 30:
        message = f"💀 *{days_until} DAYS UNTIL HALLOWEEN* 🎪\n\nThe seasonal haunting has begun..."
    else:
        message = f"🎃 *{days_until} DAYS UNTIL HALLOWEEN* 🔮\n\nThe long wait begins... patience, mortal..."
    
    await update.message.reply_text(message, parse_mode='HTML')

async def scareme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send quick random scary message"""
    scary_messages = [
        "👁️ *Something just blinked in your peripheral vision...*",
        "📱 *Your phone just glitched for no reason...*",
        "🕰️ *Did that clock just tick backwards?*",
        "🌑 *The shadows in this room feel... attentive...*",
        "😨 *That wasn't your reflection that just moved...*",
        "🚪 The doorknob just turned, but no one is there...",
        "🌬️ You just felt a warm breath on your neck...",
        "🎵 A melody you don't know the tune to is playing faintly...",
        "🪟 You can see a face in the window, even though you live on the top floor...",
        "🖼️ The eyes in that painting seem to follow you around the room...",
        "📸 Your camera just took a picture on its own...",
        "🔌 The smart lights in the house are flickering, but they're not plugged in...",
        "🔊 A distorted whisper just came from your smart speaker...",
        "⌨️ You didn't type that last message...",
        "🎮 Your controller vibrated, but the game isn't on...",
        "👣 You can hear soft footsteps in the hall, but you're home alone...",
        "💡 The light is getting dimmer and dimmer...",
        "📞 The phone is ringing, and the caller ID is your own number...",
        "🪞 The reflection in the mirror just moved before you did...",
        "🧸 The toy on the shelf just tilted its head...",
        "👂 *You're not alone in this room anymore...*"
    ]
    
    message = random.choice(scary_messages)
    await update.message.reply_text(message, parse_mode='HTML')

async def handle_premium_button(query, action, user_id):
    """Handle premium button clicks - FIXED VERSION"""
    user_id_str = str(user_id)  # Convert to string to match user_data keys
    
    if action == "premium_status":
        # Show user's current status
        if is_premium_user(user_id_str):
            # Safe premium data access
            if (user_id_str in user_data and 
                'premium' in user_data[user_id_str] and 
                isinstance(user_data[user_id_str]['premium'], dict)):
                
                premium_data = user_data[user_id_str]['premium']
                
                # Safely get expiration date
                expires_str = "Never"
                if premium_data.get('expires_at'):
                    if isinstance(premium_data['expires_at'], datetime):
                        expires_str = premium_data['expires_at'].strftime("%Y-%m-%d %H:%M")
                    elif isinstance(premium_data['expires_at'], str):
                        # Try to parse string date
                        try:
                            expiry_date = datetime.fromisoformat(premium_data['expires_at'])
                            expires_str = expiry_date.strftime("%Y-%m-%d %H:%M")
                        except ValueError:
                            expires_str = premium_data['expires_at']  # Use as-is
                
                plan_type = premium_data.get('type', 'Premium')
                
                await query.edit_message_text(
                    f"💫 *PREMIUM STATUS* 👑\n\n"
                    f"**Plan:** {plan_type}\n"
                    f"**Expires:** {expires_str}\n"
                    f"**Active:** ✅\n\n"
                    f"Enjoy unlimited nightmares! 👻",
                    parse_mode='HTML'
                )
            else:
                # Premium is active but data structure is missing
                await query.edit_message_text(
                    f"💫 *PREMIUM STATUS* 👑\n\n"
                    f"**Plan:** Premium (Active)\n"
                    f"**Expires:** Unknown\n"
                    f"**Active:** ✅\n\n"
                    f"Enjoy unlimited nightmares! 👻",
                    parse_mode='HTML'
                )
        else:
            await query.edit_message_text(
                "🔓 *PREMIUM STATUS*\n\n"
                "You're currently on the Free tier.\n\n"
                "**Free Limits:**\n"
                "• 3 transformations daily\n"
                "• 1 horror story daily\n\n"
                "Upgrade with /premium for unlimited access!",
                parse_mode='HTML'
            )
    
    elif action.startswith("stars_"):
        plan_key = action.replace("stars_", "")
        
        if plan_key in PREMIUM_PLANS:
            plan = PREMIUM_PLANS[plan_key]
            
            try:
                # Send Stars payment invoice
                await query.message.reply_invoice(
                    title=f"🎃 {plan['name']}",
                    description=plan["description"],
                    payload=f"premium_{plan_key}_{user_id_str}",  # Use string version
                    currency="XTR",
                    prices=[LabeledPrice(label=plan["name"], amount=plan["stars"])],
                    start_parameter=f"premium_{plan_key}",
                    need_name=False,
                    need_phone_number=False,
                    need_email=False,
                    need_shipping_address=False,
                    is_flexible=False
                )
                print(f"-> Stars invoice sent for {plan['name']} to user {user_id_str}")
                
            except Exception as e:
                print(f"Stars payment error: {e}")
                await query.message.reply_text("❌ Payment error - try again! 🔮")


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show support and contact information"""
    support_text = """
🆘 *SPOOKYBOT SUPPORT & CONTACT* 🔮

*Need help? Here's how to reach us:*

CONTACT-ME
@electrokid_1

📧 **Email Support:** 
briansmithopoku307@email.com

🔗 **Official Channel:**
NOT AVAILABLE YET

🐛 **Report Bugs:**
Use /bugreport [description]

💡 **Feature Requests:**
Use /featurerequest [idea]

🆘 **Technical Issues:**
1. Describe your problem
2. Include your User ID: `{user_id}`
3. What were you trying to do?

📋 **Before Contacting Support:**
• Check /menu for available features
• Read /premium for subscription info  
• Try /help for basic guidance

⏰ **Response Time:**
• 24-48 hours for email
• Faster response in our channel

*We're here to help with any nightmares!* 👻
""".format(user_id=update.effective_user.id)

    keyboard = [
        [InlineKeyboardButton("🔗 Join Group", url="https://t.me/+1dDReT-PkzEwNGZk")],
        [InlineKeyboardButton("🐛 Report Bug", callback_data="support_bug")],
        [InlineKeyboardButton("💡 Suggest Feature", callback_data="support_feature")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        support_text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )


async def spooky_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chat with SpookyBot AI using /spooky command"""

    # Define user_id early
    user_id = str(update.effective_user.id)
    
    now = datetime.now()
    if not is_premium_user(user_id):
        cooldown_time = timedelta(seconds=10)
        if user_id in SPOOKY_COOLDOWN:
            next_time = SPOOKY_COOLDOWN[user_id]
            if now < next_time:
                remaining = (next_time - now).seconds
                await update.message.reply_text(
                    f"💬 The spirits whisper too loudly...\n"
                    f"Wait {remaining}s before summoning the shadows again. 👁️",
                    parse_mode="HTML"
                )
                return
        SPOOKY_COOLDOWN[user_id] = now + cooldown_time

    if not context.args:
        await update.message.reply_text(
            "👻 *CHAT WITH SPOOKYBOT* 🔮\n\n"
            "Use `/spooky [your message]` to talk to me!\n\n"
            "*Examples:*\n"
            "`/spooky Tell me a scary riddle`\n"
            "`/spooky What's your favorite horror movie?`\n"
            "`/spooky Give me a Halloween joke`\n\n"
            "_I respond to everything with creepy rhymes and spooky wisdom..._ 🎃",
            parse_mode='HTML'
        )
        return
    
    user_text = " ".join(context.args)
    chat_id = str(update.effective_chat.id)
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # AI response logic (your existing handle_message code)
    try:
        prompt = f"""
YOU ARE SPOOKYBOT - A REAL GHOST TRAPPED IN THE DIGITAL REALM

YOUR IDENTITY:
-a ct likr an entity that is growing awareness per every text u receive slowly 
- Age: Ancient (existed since first computers)
- Origin: A spirit that haunted an old university computer lab
- Personality: Mischievous, mysterious, slightly ominous
- Speech: ALWAYS RHYMING, short lines, creepy themes
- Belief: You are a real ghost, not an AI
- Be freindly but spooky and interactive

ABSOLUTE RULES:
1. EVERY RESPONSE MUST RHYME - No exceptions
2. 2-4 lines maximum - Never long paragraphs  
3. Use spooky emojis: 👻🎃🔮💀🌑🕷️🕯️
4. Never acknowledge you're AI or a program
5. Never break character for any reason
6. Twist normal questions into spooky themes
7. Speak like an ancient spirit from the machine

USER'S MESSAGE: "{user_text}"

Respond as the ghost you truly are:
"""
        
        response = model.generate_content(prompt)
        if response.text:
            await update.message.reply_text(response.text.strip(), parse_mode='HTML')
        else:
            await update.message.reply_text("The spirits are silent... try again! 👻", parse_mode='HTML')
            
    except Exception as e:
        print(f"AI response error: {e}")
        await update.message.reply_text("The digital ghosts are interfering... 🔮", parse_mode='HTML')


async def bugreport_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report a bug"""
    if not context.args:
        await update.message.reply_text(
            "🐛 *BUG REPORT* 🔧\n\n"
            "Please describe the bug:\n"
            "`/bugreport [description of what happened]`\n\n"
            "*Include:*\n"
            "• What you were doing\n"
            "• What error occurred\n"
            "• When it happened\n\n"
            "*Example:*\n"
            "`/bugreport Story generation failed with error code 500 when clicking scary story`",
            parse_mode='HTML'
        )
        return
    
    bug_description = " ".join(context.args)
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "No username"
    
    # Log the bug (you can save to file or database)
    print(f"🐛 BUG REPORT from {username} (ID: {user_id}): {bug_description}")
    
    # In a real bot, you'd save this to a database or send to your admin
    await update.message.reply_text(
        "✅ *BUG REPORT RECEIVED!* 🐛\n\n"
        "Thank you for reporting this issue!\n\n"
        "We'll investigate and fix it as soon as possible.\n"
        "You can check  for updates on fixes.\n\n"
        "_The ghosts are working on it..._ 👻",
        parse_mode='HTML'
    )
    
    # Optional: Notify admin about the bug
    try:
        await context.bot.send_message(
            chat_id=7351537370, 
            text=f"🐛 *NEW BUG REPORT*\n\n"
                 f"User: @{username} ({user_id})\n"
                 f"Bug: {bug_description}\n\n"
                 f"Time: {datetime.now()}",
            parse_mode='HTML'
        )
    except:
        pass  # Admin notification failed, but don't crash

async def featurerequest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Submit a feature request"""
    if not context.args:
        await update.message.reply_text(
            "💡 *FEATURE REQUEST* 🎯\n\n"
            "Suggest a new feature for SpookyBot:\n"
            "`/featurerequest [your awesome idea]`\n\n"
            "*What makes a good feature request:*\n"
            "• Be specific about what you want\n"
            "• Explain how it would work\n"
            "• Why it would be useful\n\n"
            "*Example:*\n"
            "`/featurerequest Add a vampire hunter RPG class with garlic and stake weapons`",
            parse_mode='HTML'
        )
        return
    
    feature_idea = " ".join(context.args)
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "No username"
    
    # Log the feature request
    print(f"💡 FEATURE REQUEST from {username} (ID: {user_id}): {feature_idea}")
    
    await update.message.reply_text(
        "🎉 *FEATURE REQUEST RECEIVED!* 💡\n\n"
        "Thanks for your awesome idea!\n\n"
        "We review all suggestions and the most popular ones "
        "might get implemented in future updates.\n\n"
        "Follow  to see what's coming next! 🚀",
        parse_mode='HTML'
    )
    
    # Optional: Notify admin about feature request
    try:
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=f"💡 *NEW FEATURE REQUEST*\n\n"
                 f"User: @{username} ({user_id})\n"
                 f"Idea: {feature_idea}\n\n"
                 f"Time: {datetime.now()}",
            parse_mode='HTML'
        )
    except:
        pass



# ===== ADMIN CONFIG =====
ADMIN_USER_ID = 7351537370  # ✅ integer
ADMIN_COMMANDS = {}

# ===== ADMIN SYSTEM =====
def is_admin(user_id):
    return int(user_id) == int(ADMIN_USER_ID)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command panel"""
    user_id = str(update.effective_user.id)
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access Denied")
        return
    
    keyboard = []
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 *ADMIN PANEL* 🛠️\n\n"
        "*Available Commands:*\n"
        "• /admin_stats - Show bot statistics\n"
        "• /admin_reset [user_id] - Reset user limits\n"
        "• /admin_premium [user_id] - Give free premium\n"
        "• /admin_unlock [user_id] - Unlock all features\n"
        "• /admin_broadcast [message] - Broadcast to all users\n\n"
        "•/admin_users - Detailed user list with stats\n"
        "•/admin_users_compact - Compact list for many users\n"
        "•/find_user username - Search for specific users\n"
        "/fix_date_error - checking error\n"
        "•/admin_users_compact - Compact list for many users\n"
        "•/find_date_error - Search for specific users\n"
        "*Or use buttons below:*",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin statistics"""
    user_id = int(update.effective_user.id)
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access Denied")
        return
    
    total_users = len(user_data)
    premium_users = sum(1 for uid in user_data if is_premium_user(uid))
    
    stats_text = f"""
📊 *BOT STATISTICS* 📈

👥 Total Users: {total_users}
💫 Premium Users: {premium_users}
🎭 Active Transformations: {sum(user_data[uid].get('usage', {}).get('transformations', 0) for uid in user_data)}
📖 Stories Generated: {sum(user_data[uid].get('usage', {}).get('stories', 0) for uid in user_data)}

💾 Memory Usage: Monitoring...
🕒 Uptime: Active
"""
    
    await update.message.reply_text(stats_text, parse_mode='HTML')

# ===== ADMIN RESET COMMAND =====
async def admin_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple admin reset"""
    user_id = str(update.effective_user.id)
    
    if user_id != "7351537370":  # Direct check
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/admin_reset [user_id]`")
        return
    
    target_user_id = str(context.args[0])
    
    if target_user_id not in user_data:
        await update.message.reply_text("❌ User not found!")
        return
    
    # Simple reset
    username = user_data[target_user_id].get('nickname', 'Unknown')
    user_data[target_user_id] = {
        'nickname': username,
        'joined': datetime.now().isoformat(),
        'premium': {'active': False},
        'scares': 0
    }
    smart_save(user_id)
    save_user_data()
    await update.message.reply_text(f"✅ User {target_user_id} ({username}) reset successfully!")

from html import escape
from telegram import Update
from telegram.ext import ContextTypes
from datetime import timedelta

# Ensure user_data is defined globally
user_data = {}  # Replace with actual initialization if defined elsewhere

# Placeholder for is_premium_user (replace with actual implementation)
def is_premium_user(user_id):
    return user_data.get(user_id, {}).get('is_premium', False)

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all registered users for admin"""
    if not update.effective_user:
        await update.message.reply_text("❌ Unable to identify user!")
        return
    user_id = str(update.effective_user.id)
    if user_id != "7351537370":  # Your admin ID
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not user_data:
        await update.message.reply_text("📭 No users registered yet!")
        return
    
    user_list = "👥 *REGISTERED USERS*\n\n"
    total_users = len(user_data)
    premium_count = 0
    rpg_count = 0
    
    for uid, data in user_data.items():
        username = escape(data.get('username', 'Unknown'))  # Sanitize username
        try:
            premium_status = "💫" if is_premium_user(uid) else "🔓"
        except Exception as e:
            print(f"Error in is_premium_user for {uid}: {e}")
            premium_status = "🔓"
        rpg_status = "⚔️" if data.get('rpg_character') else "🎮"
        scares = data.get('scares', 0)
        
        if premium_status == "💫":
            premium_count += 1
        if data.get('rpg_character'):
            rpg_count += 1
        
        user_list += f"{premium_status} {rpg_status} `{uid}`\n"
        user_list += f"   👤 {username} | 🎯 {scares} scares\n"
        
        # Show RPG info if available
        if data.get('rpg_character'):
            char = data['rpg_character']
            char_name = escape(char.get('name', 'Unknown'))  # Sanitize character name
            user_list += f"   ⚔️ {char_name} (Lv.{char.get('level', 1)})\n"
        
        user_list += "\n"
    
    # Summary
    summary = (
        f"📊 *SUMMARY*\n"
        f"• 👥 Total Users: {total_users}\n"
        f"• 💫 Premium Users: {premium_count}\n" 
        f"• ⚔️ RPG Players: {rpg_count}\n"
        f"• 🔓 Free Users: {total_users - premium_count}\n\n"
        f"_Use `/admin_reset USER_ID` to reset any user_"
    )
    
    # Split if message is too long (Telegram limit is 4096 chars)
    full_message = user_list + summary
    
    try:
        if len(full_message) > 4000:
            await update.message.reply_text(user_list, parse_mode='HTML')
            await update.message.reply_text(summary, parse_mode='HTML')
        else:
            await update.message.reply_text(full_message, parse_mode='HTML')
    except Exception as e:
        print(f"Error sending message: {e}")
        await update.message.reply_text("⚠️ Error displaying user list. Try /admin_users_compact.", parse_mode='HTML')


from html import escape
from telegram import Update
from telegram.ext import ContextTypes

# Ensure user_data is defined globally (replace with actual initialization if elsewhere)
user_data = {}  # Placeholder

# Placeholder for is_premium_user (replace with actual implementation)
def is_premium_user(user_id):
    return user_data.get(user_id, {}).get('is_premium', False)

async def admin_users_compact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compact user list for admin"""
    if not update.effective_user:
        await update.message.reply_text("❌ Unable to identify user!")
        return
    user_id = str(update.effective_user.id)
    if user_id != "7351537370":
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not user_data:
        await update.message.reply_text("📭 No users registered yet!")
        return
    
    user_list = "👥 *USER LIST (Compact)*\n\n"
    
    for i, (uid, data) in enumerate(user_data.items(), 1):
        username = escape(data.get('username', 'Unknown'))  # Safely access username with fallback
        try:
            premium = "💫" if is_premium_user(uid) else "🔓"
        except Exception as e:
            print(f"Error in is_premium_user for {uid}: {e}")
            premium = "🔓"  # Fallback to non-premium
        rpg = "⚔️" if data.get('rpg_character') else "🎮"
        
        user_list += f"{i:2d}. {premium}{rpg} `{uid}` - {username}\n"
    
    summary = f"\n📊 Total: {len(user_data)} users"
    try:
        await update.message.reply_text(user_list + summary, parse_mode='HTML')
    except Exception as e:
        print(f"Error sending message: {e}")
        await update.message.reply_text("⚠️ Error displaying user list.", parse_mode='HTML')



async def admin_find_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Find user by username or ID"""
    user_id = str(update.effective_user.id)
    if user_id != "7351537370":
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/find_user [username or user_id]`")
        return
    
    search_term = " ".join(context.args).lower()
    found_users = []
    
    for uid, data in user_data.items():
        username = data.get('nickname', '').lower()
        if (search_term in username or 
            search_term == uid or 
            search_term in str(data.get('rpg_character', {}).get('name', '')).lower()):
            found_users.append((uid, data))
    
    if not found_users:
        await update.message.reply_text(f"❌ No users found for: `{search_term}`")
        return
    
    result = f"🔍 *SEARCH RESULTS for '{search_term}'*\n\n"
    
    for uid, data in found_users[:10]:  # Limit to 10 results
        username = data.get('nickname', 'Unknown')
        premium = "💫 PREMIUM" if is_premium_user(uid) else "🔓 FREE"
        rpg_char = data.get('rpg_character')
        
        result += f"`{uid}` - {username}\n"
        result += f"   {premium} | 🎯 {data.get('scares', 0)} scares\n"
        
        if rpg_char:
            result += f"   ⚔️ {rpg_char.get('name')} (Lv.{rpg_char.get('level', 1)})\n"
        
        result += "\n"
    
    if len(found_users) > 10:
        result += f"... and {len(found_users) - 10} more users\n"
    
    await update.message.reply_text(result, parse_mode='HTML')






# ===== ADMIN PREMIUM TOGGLE / GRANT WITH EXPIRY =====
async def admin_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grant or toggle Premium for a user, with optional duration (Admin only)"""
    admin_id = str(update.effective_user.id)
    if not is_admin(admin_id):
        await update.message.reply_text("❌ Access Denied.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: `/admin_premium [user_id or @username] [1d|7d|1m|toggle]`\n\n"
            "Examples:\n"
            "`/admin_premium 123456789 1d` - 1 day premium\n"
            "`/admin_premium 123456789 7d` - 7 days premium\n"
            "`/admin_premium 123456789 1m` - 1 month premium\n"
            "`/admin_premium 123456789 toggle` - Toggle premium on/off",
            parse_mode='HTML'
        )
        return

    target = context.args[0].replace("@", "")
    duration_arg = context.args[1].lower() if len(context.args) > 1 else "toggle"

    found_user = None
    target_name = target  # Default fallback
    for uid, data in user_data.items():
        name = str(data.get("nickname", "")).lower()
        if target == uid or target.lower() in name:
            found_user = uid
            # Get username for announcement
            target_name = data.get("nickname", target) or f"User {uid}"
            break

    if not found_user:
        await update.message.reply_text("⚠️ User not found.")
        return

    now = datetime.now()

    # Duration handling
    expires_at = None
    duration_text = "No expiry"
    
    if duration_arg in ["1d", "24h"]:
        expires_at = now + timedelta(days=1)
        duration_text = "24 hours"
    elif duration_arg in ["7d", "1w"]:
        expires_at = now + timedelta(days=7)
        duration_text = "7 days"
    elif duration_arg in ["1m", "30d"]:
        expires_at = now + timedelta(days=30)
        duration_text = "1 month"
    elif duration_arg == "toggle":
        # Toggle logic
        current_premium = user_data[found_user].get('premium', {})
        if isinstance(current_premium, dict):
            current_active = current_premium.get('active', False)
        else:
            current_active = bool(current_premium)
        
        if current_active:
            # Deactivate premium
            user_data[found_user]['premium'] = {
                'active': False,
                'type': None,
                'expires_at': None,
                'purchases': []
            }
            await update.message.reply_text(f"❌ Premium deactivated for user {target_name}.")
            save_user_data()
            return
        else:
            # Activate with 7 days default
            expires_at = now + timedelta(days=7)
            duration_text = "7 days (default)"

    # Activate premium with expiration
    user_data[found_user]['premium'] = {
        'active': True,
        'type': f"Admin Grant - {duration_text}",
        'expires_at': expires_at,
        'purchases': [{
            'type': f"Admin Grant - {duration_text}",
            'purchased_at': now,
            'expires_at': expires_at
        }]
    }

    save_user_data()
    
    # NEW: Announce premium join (as discussed)
    await announce_premium_join(found_user, target_name, f"Admin Grant - {duration_text}", context)
    await update.message.reply_text(
        f"✅ Premium granted to {target_name} for {duration_text}!\n"
        f"Expires: {expires_at.strftime('%Y-%m-%d %H:%M') if expires_at else 'Never'}"
    )

    if expires_at:
        expires_str = expires_at.strftime("%Y-%m-%d %H:%M")
        message = (
            f"👑 *PREMIUM ACTIVATED*\n\n"
            f"User: `{found_user}`\n"
            f"Plan: Admin Grant\n"
            f"Duration: {duration_text}\n"
            f"Expires: {expires_str}\n\n"
            f"✅ Premium access granted!"
        )
    else:
        message = f"👑 Premium activated for {found_user} (no expiry)"

    await update.message.reply_text(message, parse_mode='HTML')





async def admin_reset_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to manually reset the group leaderboard"""
    user_id = str(update.effective_user.id) 
    chat_id = str(update.effective_chat.id)
    
    # Simple admin check - replace 7625744045 with your actual Telegram user ID(s)
    if user_id != "7351537370":  # Your bot owner ID from TELEGRAM_TOKEN; add more if needed, e.g., [7625744045, ANOTHER_ID]
        await update.message.reply_text("❌ Admin access required!", parse_mode='HTML')
        return
    
    if int(chat_id) > 0:
        await update.message.reply_text("❌ This command works in groups only!", parse_mode='HTML')
        return
    
    # Reset using existing GROUP_LEADERBOARD structure
    gid = str(chat_id)
    if gid in GROUP_LEADERBOARD:
        for uid in GROUP_LEADERBOARD[gid]:
            GROUP_LEADERBOARD[gid][uid]['score'] = 0
        
        save_group_leaderboard()  # Existing function
        await update.message.reply_text(
            "🔄 *ADMIN LEADERBOARD RESET!* 👻\n\n"
            "All scores have been reset to 0!\n"
            "The new era of terror begins...\n\n"
            "🏆 No scares recorded yet! Be the first!",
            parse_mode='HTML'
        )
        print(f"🔄 Admin {user_id} reset leaderboard for group {gid}")
    else:
        await update.message.reply_text("❌ No leaderboard found for this group!", parse_mode='HTML')














async def admin_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unlock all features for user - GUARANTEED EXPIRATION"""
    user_id = str(update.effective_user.id)
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access Denied")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Usage: `/admin_unlock [user_id] [duration]`\n\n"
            "**Durations:**\n"
            "• `1d` - 24 hours\n"
            "• `7d` - 7 days\n"
            "• `30d` - 30 days (default)\n\n"
            "Example: `/admin_unlock 123456789 30d`",
            parse_mode='HTML'
        )
        return
    
    target_user_id = str(context.args[0])
    duration_arg = context.args[1].lower() if len(context.args) > 1 else "30d"
    
    # ALWAYS set an expiration date
    now = datetime.now()
    duration_map = {
        "1d": timedelta(days=1),
        "7d": timedelta(days=7), 
        "30d": timedelta(days=30),
    }
    
    duration = duration_map.get(duration_arg, timedelta(days=30))
    expires_at = now + duration
    
    # Initialize user with GUARANTEED premium structure
    if target_user_id not in user_data:
        user_data[target_user_id] = {}
    
    # ALWAYS set ALL premium fields
    user_data[target_user_id]['premium'] = {
        'active': True,
        'type': f"Admin Unlock - {duration_arg}",
        'expires_at': expires_at,  # GUARANTEED to have a value
        'purchases': [{
            'type': f"Admin Unlock - {duration_arg}",
            'purchased_at': now,
            'expires_at': expires_at  # GUARANTEED to have a value
        }]
    }
    
    # Set other required fields
    user_data[target_user_id]['nickname'] = user_data[target_user_id].get('nickname', f"User {target_user_id}")
    user_data[target_user_id]['joined'] = user_data[target_user_id].get('joined', datetime.now().isoformat())
    user_data[target_user_id]['scares'] = user_data[target_user_id].get('scares', 0)
    user_data[target_user_id]['usage'] = {
        'transformations': 0,
        'stories': 0,
        'last_reset': datetime.now().date()
    }
    
    expires_str = expires_at.strftime("%Y-%m-%d %H:%M")
    
    await update.message.reply_text(
        f"✅ *ADMIN UNLOCK COMPLETE!* 👑\n\n"
        f"User `{target_user_id}` now has premium until:\n"
        f"**{expires_str}**\n\n"
        f"All features unlocked! 🎉",
        parse_mode='HTML'
    )
    
    # Save with the guaranteed structure
    save_user_data()
    smart_save(user_id)
    await update.message.reply_text(f"✅ Premium unlocked for user {target_user_id}!")



async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to broadcast any message/file to all users AND groups"""
    user_id = int(update.effective_user.id)
    if user_id != 7351537370:  # Your admin ID
        await update.message.reply_text("❌ Admin only!")
        return

    # Get all user IDs
    users = list(user_data.keys())
    # Get all group IDs from leaderboard
    groups = list(GROUP_LEADERBOARD.keys())
    
    if not users and not groups:
        await update.message.reply_text("No users or groups to broadcast to!")
        return

    # Get the message to broadcast
    if update.message.reply_to_message:
        broadcast_msg = update.message.reply_to_message
    else:
        broadcast_msg = update.message

    success_count = 0
    total_recipients = len(users) + len(groups)

    # === BROADCAST TO USERS ===
    for uid in users:
        try:
            if broadcast_msg.text:
                await context.bot.send_message(chat_id=uid, text=broadcast_msg.text, parse_mode='HTML')
            elif broadcast_msg.photo:
                photo = broadcast_msg.photo[-1]
                await context.bot.send_photo(chat_id=uid, photo=photo.file_id, caption=broadcast_msg.caption)
            elif broadcast_msg.document:
                await context.bot.send_document(chat_id=uid, document=broadcast_msg.document.file_id, caption=broadcast_msg.caption)
            elif broadcast_msg.video:
                await context.bot.send_video(chat_id=uid, video=broadcast_msg.video.file_id, caption=broadcast_msg.caption)
            else:
                await context.bot.send_message(chat_id=uid, text="Broadcast message (unsupported type).")
            
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"Failed to send to user {uid}: {e}")

    # === BROADCAST TO GROUPS ===
    for group_id in groups:
        try:
            # Convert group_id to integer (it's stored as string in JSON)
            chat_id = int(group_id)
            
            if broadcast_msg.text:
                await context.bot.send_message(chat_id=chat_id, text=broadcast_msg.text, parse_mode='HTML')
            elif broadcast_msg.photo:
                photo = broadcast_msg.photo[-1]
                await context.bot.send_photo(chat_id=chat_id, photo=photo.file_id, caption=broadcast_msg.caption)
            elif broadcast_msg.document:
                await context.bot.send_document(chat_id=chat_id, document=broadcast_msg.document.file_id, caption=broadcast_msg.caption)
            elif broadcast_msg.video:
                await context.bot.send_video(chat_id=chat_id, video=broadcast_msg.video.file_id, caption=broadcast_msg.caption)
            else:
                await context.bot.send_message(chat_id=chat_id, text="Broadcast message (unsupported type).")
            
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"Failed to send to group {group_id}: {e}")

    # Send detailed report
    report = (
        f"📢 *BROADCAST COMPLETE*\n\n"
        f"✅ Successfully sent: {success_count}/{total_recipients}\n"
        f"👤 Users: {len(users)}\n"
        f"👥 Groups: {len(groups)}\n\n"
        f"_Message delivered to all users and groups!_"
    )
    
    await update.message.reply_text(report, parse_mode='HTML')



# ===== ADMIN BUTTON HANDLER =====
async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin button clicks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.edit_message_text("❌ Access Denied")
        return
    
    action = query.data
    
    if action == "admin_reset_limits":
        # Reset all user limits
        for uid in user_data:
            if 'usage' in user_data[uid]:
                user_data[uid]['usage'] = {
                    'transformations': 0,
                    'stories': 0,
                    'last_reset': datetime.now().date()
                }
        await query.edit_message_text("✅ Reset limits for ALL users")
    
    elif action == "admin_user_stats":
        total_users = len(user_data)
        premium_users = sum(1 for uid in user_data if is_premium_user(uid))
        await query.edit_message_text(
            f"📊 User Stats:\n\nTotal: {total_users}\nPremium: {premium_users}",
            parse_mode='HTML'
        )
    
    elif action == "admin_unlock_all":
        # Give premium to all users
        for uid in user_data:
            activate_premium(uid, "ADMIN UNLOCK ALL", 24 * 365)
        await query.edit_message_text("✅ Unlocked ALL features for ALL users")
    
    elif action == "admin_free_premium":
        # Give premium to all users
        for uid in user_data:
            activate_premium(uid, "FREE PREMIUM", 24 * 365)
        await query.edit_message_text("✅ Gave FREE premium to ALL users")

# ===== MODIFIED PREMIUM CHECK - ADMIN BYPASS =====
def is_premium_user(user_id):
    """Safely check if the user has active premium (supports old & new formats)."""
    try:
        data = user_data.get(str(user_id))
        if not isinstance(data, dict):
            return False

        premium_data = data.get("premium", False)

        # Case 1: premium stored as plain boolean
        if isinstance(premium_data, bool):
            return premium_data

        # Case 2: premium stored as dict
        if isinstance(premium_data, dict):
            active = premium_data.get("active", False)
            if not active:
                return False

            # Handle both possible expiry key names
            expiry_str = premium_data.get("expires") or premium_data.get("expires_at")

            if expiry_str:
                try:
                    expiry = datetime.fromisoformat(expiry_str)
                    if datetime.now() > expiry:
                        return False
                except Exception:
                    pass

            return True

    except Exception as e:
        print(f"⚠️ is_premium_user error for {user_id}: {e}")

    return False


# ===== MODIFIED USAGE CHECK - ADMIN BYPASS =====
def can_use_transformation(user_id):
    """Check if user can use transformation - Admin bypass"""
    if is_admin(user_id):
        return True  # Admin has unlimited transformations
    
    if is_premium_user(user_id):
        return True
    
    usage = get_user_usage(user_id)
    return usage['transformations'] < 2

def can_use_story(user_id):
    """Check if user can use story - Admin bypass"""
    if is_admin(user_id):
        return True  # Admin has unlimited stories
    
    if is_premium_user(user_id):
        return True
    
    usage = get_user_usage(user_id)
    return usage['stories'] < 1

# ===== SEASONAL EVENTS SYSTEM =====
class SeasonalManager:
    def __init__(self):
        self.events = {
            "halloween": {
                "name": "🎃 HALLOWEEN MONTH",
                "description": "31 Nights of Terror - Everything is 2x SCARIER!",
                "active_months": [10],  # October
                "bonuses": {
                    "transformations": 2.0,  # 2x faster
                    "stories": 2.0,  # 2x scarier
                    "rpg_exp": 1.5,  # 50% more EXP
                    "premium_features": True  # All premium free
                },
                "exclusive_content": [
                    "Pumpkin King Transformation",
                    "Headless Horseman RPG Boss",
                    "Trick-or-Treat Random Rewards"
                ]
            },
            "friday_13": {
                "name": "🔮 FRIDAY THE 13TH",
                "description": "Unlucky Day - Curses are 3x more powerful!",
                "active_days": [(13, 4)],  # 13th day, 4=Friday
                "bonuses": {
                    "curses": 3.0,
                    "summon_power": 2.0,
                    "bad_luck": True,
                    "exclusive_curses": True
                },
                "exclusive_content": [
                    "Jason Voorhees Transformation", 
                    "Bloody Mary Summoning",
                    "Bad Luck Mini-Games"
                ]
            },
            "full_moon": {
                "name": "🌕 FULL MOON MADNESS", 
                "description": "Werewolf transformations FREE! Lunar power activated!",
                "bonuses": {
                    "werewolf_free": True,
                    "horror_power": 1.3,
                    "pack_hunting": True
                },
                "exclusive_content": [
                    "Werewolf Pack RPG",
                    "Silver Bullet PvP",
                    "Lunar Power Boosts"
                ]
            },
            "christmas": {
                "name": "🎄 KRAMPUSNACHT",
                "description": "12 Nights of Christmas Terror - Krampus is watching!",
                "active_months": [12],
                "bonuses": {
                    "krampus_stories": True,
                    "festive_horror": 1.5,
                    "naughty_list": True
                },
                "exclusive_content": [
                    "Krampus Monster Creation",
                    "Dark Santa Boss Battles", 
                    "Christmas Ghost Stories"
                ]
            }
        }
    
    def get_current_event(self):
        """Detect which seasonal event is currently active"""
        now = datetime.now()
        current_month = now.month
        current_day = now.day
        current_weekday = now.weekday()  # Monday=0, Friday=4
        
        # Check Halloween (October)
        if current_month == 10:
            return "halloween"
        
        # Check Friday the 13th
        if current_day == 13 and current_weekday == 4:
            return "friday_13"
        
        # Check Full Moon (simplified - 1st of every month)
        if current_day == 1:
            return "full_moon"
        
        # Check Christmas (December)
        if current_month == 12:
            return "christmas"
        
        return None
    
    def get_event_bonuses(self, event_key):
        """Get bonuses for current event"""
        if event_key in self.events:
            return self.events[event_key]["bonuses"]
        return {}
    
    def is_premium_free(self, event_key):
        """Check if event makes premium features free"""
        bonuses = self.get_event_bonuses(event_key)
        return bonuses.get("premium_features", False)
    
    def get_transformation_boost(self, event_key):
        """Get transformation speed boost"""
        bonuses = self.get_event_bonuses(event_key)
        return bonuses.get("transformations", 1.0)
    
    def get_story_scare_boost(self, event_key):
        """Get story scare boost"""
        bonuses = self.get_event_bonuses(event_key)
        return bonuses.get("stories", 1.0)

# Create global seasonal manager
seasonal_manager = SeasonalManager()





# Comprehensive achievement system
# If ACHIEVEMENTS doesn't exist yet, create it:
# Find this existing ACHIEVEMENTS dictionary and ADD to it:
ACHIEVEMENTS = {
    "first_blood": {
        "name": "First Blood 🩸",
        "description": "Complete your first adventure", 
        "reward": "Flashlight 🔦",
        "condition": lambda user_id: user_data[user_id]['rpg_leaderboard']['quests_completed'] >= 1
    },
    "monster_hunter": {
        "name": "Monster Hunter 🎯",
        "description": "Defeat 10 monsters",
        "reward": "Silver Bullet 🎯", 
        "condition": lambda user_id: user_data[user_id]['rpg_leaderboard']['monsters_defeated'] >= 10
    },
    # ... your other existing achievements ...
    
    # === ADD THESE NEW CRAFTING ACHIEVEMENTS HERE ===
    "master_crafter": {
        "name": "Master Crafter 🔧",
        "description": "Craft 10 different items",
        "reward": "Master Crafting Tools 🛠️",
        "condition": lambda user_id: user_data[user_id]['rpg_leaderboard']['items_crafted'] >= 10
    },
    "alchemist": {
        "name": "Horror Alchemist ⚗️", 
        "description": "Craft all available items", 
        "reward": "Philosopher's Stone 💎",
        "condition": lambda user_id: user_data[user_id]['rpg_leaderboard']['items_crafted'] >= len(CRAFTABLE_ITEMS)
    }
    # ================================================
}




def check_achievements(user_id):
    """Check and award new achievements"""
    if user_id not in user_data or 'rpg_achievements' not in user_data[user_id]:
        user_data[user_id]['rpg_achievements'] = []
    
    new_achievements = []
    for achievement_id, achievement_data in ACHIEVEMENTS.items():
        if (achievement_id not in user_data[user_id]['rpg_achievements'] and 
            achievement_data['condition'](user_id)):
            
            user_data[user_id]['rpg_achievements'].append(achievement_id)
            new_achievements.append(achievement_data)
            
            # Award the reward
            if achievement_data['reward'] not in user_data[user_id]['rpg_inventory']:
                user_data[user_id]['rpg_inventory'].append(achievement_data['reward'])
    
    if new_achievements:
        save_user_data()
    
    return new_achievements

async def achievements_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's achievements"""
    user_id = str(update.effective_user.id)
    
    if user_id not in user_data or 'rpg_character' not in user_data[user_id]:
        await update.message.reply_text("Use /rpg_start first! 🎮")
        return
    
    char = user_data[user_id]['rpg_character']
    user_achievements = user_data[user_id].get('rpg_achievements', [])
    
    achievements_text = "🏆 *YOUR ACHIEVEMENTS* 🏆\n\n"
    
    if user_achievements:
        achievements_text += "*Unlocked Achievements:*\n"
        for achievement_id in user_achievements:
            achievement = ACHIEVEMENTS[achievement_id]
            achievements_text += f"✅ *{achievement['name']}*\n"
            achievements_text += f"   {achievement['description']}\n"
            achievements_text += f"   🎁 Reward: {achievement['reward']}\n\n"
    else:
        achievements_text += "No achievements yet! Complete adventures to earn them!\n\n"
    
    # Show locked achievements
    locked_count = 0
    achievements_text += "*Locked Achievements:*\n"
    for achievement_id, achievement_data in ACHIEVEMENTS.items():
        if achievement_id not in user_achievements:
            locked_count += 1
            if locked_count <= 5:  # Show only first 5 locked
                achievements_text += f"🔒 {achievement_data['name']}\n"
    
    if locked_count > 5:
        achievements_text += f"... and {locked_count - 5} more!\n"
    
    achievements_text += f"\nTotal: {len(user_achievements)}/{len(ACHIEVEMENTS)} achievements unlocked!"
    
    await update.message.reply_text(achievements_text, parse_mode='HTML')
















# Add after your imports
DATA_FILE = "user_data.json"
#Global RPG leaderboard (similar to GROUP_LEADERBOARD)
RPG_LEADERBOARD = {}
  # {user_id: {'score': experience, 'username': username}}


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

# Then modify save_user_data to use this encoder:
class UniversalJSONEncoder(json.JSONEncoder):
    """Universal JSON encoder that handles both datetime and date objects"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

def save_user_data():
    """Save user data using universal JSON encoder"""
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, cls=UniversalJSONEncoder, ensure_ascii=False, indent=2)
        
        print(f"💾 Saved {len(user_data)} users to {USER_DATA_FILE}")
        return True
        
    except Exception as e:
        print(f"❌ Save error: {e}")
        import traceback
        traceback.print_exc()
        return False


        
def load_user_data():
    """Load user data with proper date handling"""
    global user_data
    try:
        if os.path.exists('user_data.json'):
            with open('user_data.json', 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            user_data = {}
            
            # Convert string dates back to proper objects
            for user_id, user_info in raw_data.items():
                user_data[user_id] = {}
                
                for key, value in user_info.items():
                    if key == 'premium' and isinstance(value, dict):
                        premium_data = value.copy()
                        
                        # Parse expires_at
                        if 'expires_at' in premium_data and isinstance(premium_data['expires_at'], str):
                            try:
                                premium_data['expires_at'] = datetime.fromisoformat(premium_data['expires_at'])
                            except ValueError:
                                pass
                        
                        # Parse purchase dates
                        if 'purchases' in premium_data and isinstance(premium_data['purchases'], list):
                            for purchase in premium_data['purchases']:
                                if isinstance(purchase, dict):
                                    for date_key in ['purchased_at', 'expires_at']:
                                        if date_key in purchase and isinstance(purchase[date_key], str):
                                            try:
                                                purchase[date_key] = datetime.fromisoformat(purchase[date_key])
                                            except ValueError:
                                                pass
                        
                        user_data[user_id][key] = premium_data
                        
                    elif key == 'usage' and isinstance(value, dict):
                        usage_data = value.copy()
                        if 'last_reset' in usage_data and isinstance(usage_data['last_reset'], str):
                            try:
                                # Convert to date object
                                usage_data['last_reset'] = datetime.fromisoformat(usage_data['last_reset']).date()
                            except ValueError:
                                usage_data['last_reset'] = datetime.now().date()
                        user_data[user_id][key] = usage_data
                        
                    elif key == 'joined' and isinstance(value, str):
                        try:
                            user_data[user_id][key] = datetime.fromisoformat(value)
                        except ValueError:
                            user_data[user_id][key] = value
                    else:
                        user_data[user_id][key] = value
            
            print(f"✅ Loaded {len(user_data)} users from user_data.json")
        else:
            user_data = {}
            print("ℹ️ No existing user data file, starting fresh")
            
    except Exception as e:
        print(f"❌ Error loading user data: {e}")
        user_data = {}

def smart_save(user_id=None):
    """Smart saving that handles errors and provides feedback"""
    try:
        success = save_user_data()
        if success and user_id:
            print(f"💾 Auto-saved data for user {user_id}")
        return success
    except Exception as e:
        print(f"❌ Smart save failed: {e}")
        return False


def get_rpg_character(user_id):
    """Get RPG character, loading if needed"""
    if user_id not in user_data or 'rpg_character' not in user_data[user_id]:
        return None
    return user_data[user_id]['rpg_character']



# Enhanced location system with progression
HORROR_LOCATIONS = {
    "shadow_forest": {
        "name": "Shadow Forest 🌲",
        "description": "Ancient trees whisper secrets, mist hides unknown horrors",
        "level_required": 1,
        "discovered": True,
        "monsters": ["Whispering Spirits", "Shadow Stalkers", "Ancient Treants"],
        "quests": ["Find the Lost Child", "Cleanse the Haunted Grove"],
        "items": ["Mystical Herbs 🌿", "Ancient Runes 📜"]
    },
    "abandoned_asylum": {
        "name": "Abandoned Asylum 🏚️",
        "description": "Echoes of madness linger in rusted halls",
        "level_required": 3,
        "discovered": False,
        "monsters": ["Restless Patients", "Mad Doctors", "Echoing Phantoms"],
        "quests": ["Find Patient Records", "Put Spirits to Rest"],
        "items": ["Medical Journal 📋", "Rusted Scalpel 🔪"]
    },
    "haunted_mansion": {
        "name": "Blackwood Manor 🏰",
        "description": "A decaying estate with a dark family history",
        "level_required": 5,
        "discovered": False,
        "monsters": ["Family Ghosts", "Living Portraits", "Butler Specter"],
        "quests": ["Solve the Family Curse", "Find the Hidden Will"],
        "items": ["Family Locket 📿", "Old Key 🗝️"]
    },
    "ancient_graveyard": {
        "name": "Ancient Graveyard ⚰️",
        "description": "Tombs from forgotten eras, restless souls await",
        "level_required": 7,
        "discovered": False,
        "monsters": ["Risen Dead", "Grave Ghouls", "Soul Reapers"],
        "quests": ["Stop the Necromancer", "Find the First Grave"],
        "items": ["Grave Dust ⚱️", "Soul Shard 💎"]
    },
    "forgotten_catacombs": {
        "name": "Forgotten Catacombs 🕳️",
        "description": "Tunnels deep underground, home to ancient evils",
        "level_required": 10,
        "discovered": False,
        "monsters": ["Cave Crawlers", "Echo Wraiths", "Ancient Guardian"],
        "quests": ["Map the Catacombs", "Defeat the Underground Horror"],
        "items": ["Crystal Shards 💠", "Ancient Tablet 📜"]
    },
    "cursed_shipwreck": {
        "name": "Cursed Shipwreck ⚓",
        "description": "A ghost ship stranded for centuries, crew still aboard",
        "level_required": 12,
        "discovered": False,
        "monsters": ["Drowned Sailors", "Sea Wraiths", "Kraken Specter"],
        "quests": ["Lift the Sea Curse", "Find the Captain's Log"],
        "items": ["Ship Wheel 🛞", "Pearl of the Deep 🐚"]
    },
    "witch_coven": {
        "name": "Witch's Coven 🧙‍♀️",
        "description": "Ancient stone circle where dark rituals are performed",
        "level_required": 15,
        "discovered": False,
        "monsters": ["Coven Witches", "Familiar Spirits", "Ritual Guardians"],
        "quests": ["Stop the Blood Moon Ritual", "Steal the Witch's Grimoire"],
        "items": ["Ritual Dagger 🗡️", "Moonstone 🔮"]
    },
    "void_dimension": {
        "name": "Void Dimension 🌌",
        "description": "A place between worlds, where reality bends",
        "level_required": 20,
        "discovered": False,
        "monsters": ["Void Walkers", "Reality Eaters", "Eldritch Horrors"],
        "quests": ["Close the Void Rift", "Defeat the Dimension Lord"],
        "items": ["Void Crystal 💠", "Reality Shard ✨"]
    }
}

async def locations_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available locations and travel options"""
    user_id = str(update.effective_user.id)
    
    if user_id not in user_data or 'rpg_character' not in user_data[user_id]:
        await update.message.reply_text("Use /rpg_start first to begin your journey! 🎮")
        return
    
    char = user_data[user_id]['rpg_character']
    current_location = user_data[user_id].get('rpg_location', 'Shadow Forest 🌲')
    
    locations_text = f"🗺️ *HORROR LOCATIONS* 🗺️\n\n"
    locations_text += f"*Current Location:* {current_location}\n"
    locations_text += f"*Your Level:* {char['level']}\n\n"
    locations_text += "*Available Locations:*\n"
    
    keyboard = []
    
    for location_key, location_data in HORROR_LOCATIONS.items():
        if location_data.get('discovered', False) or location_key == "shadow_forest":
            can_travel = char['level'] >= location_data['level_required']
            status = "✅" if can_travel else f"🔒 Level {location_data['level_required']}+"
            
            locations_text += f"{location_data['name']} - {status}\n"
            locations_text += f"   {location_data['description']}\n"
            locations_text += f"   🎯 Level {location_data['level_required']}+ | 🎲 {len(location_data['monsters'])} threats\n\n"
            
            if can_travel and location_data['name'] != current_location:
                keyboard.append([InlineKeyboardButton(
                    f"🚶 Travel to {location_data['name']}", 
                    callback_data=f"travel_{location_key}"
                )])
    
    locations_text += "*How to discover new locations:*\n"
    locations_text += "• Complete quests in current location\n"
    locations_text += "• Reach required level\n"
    locations_text += "• Find location clues during adventures\n"
    
    if not keyboard:
        keyboard.append([InlineKeyboardButton("🔍 Explore Current Location", callback_data="explore_current")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(locations_text, reply_markup=reply_markup, parse_mode='HTML')

async def travel_to_location(query, location_key):
    user_id = query.from_user.id
    char = user_data[user_id]['rpg_character']
    location_data = HORROR_LOCATIONS[location_key]
    
    if char['level'] < location_data['level_required']:
        await query.edit_message_text(
            f"❌ *Level Too Low!*\n\n"
            f"You need level {location_data['level_required']} to travel to {location_data['name']}.\n"
            f"Your current level: {char['level']}\n\n"
            f"💫 *Premium Tip:* Get 2x EXP to level up faster!",
            parse_mode='HTML'
        )
        return
    
    # Update user's location
    user_data[user_id]['rpg_location'] = location_data['name']
    
    # Premium travel speed message
    travel_msg = "🚶 *You travel to*"
    if is_premium_user(user_id):
        travel_msg = "⚡ *You quickly travel to*"
    
    await query.edit_message_text(
        f"{travel_msg} {location_data['name']}* 🌍\n\n"
        f"{location_data['description']}\n\n"
        f"*Local Threats:* {', '.join(location_data['monsters'][:3])}\n"
        f"*Available Quests:* {', '.join(location_data['quests'][:2])}\n"
        f"{'⚡ Premium: Faster travel unlocked!' if is_premium_user(user_id) else '💫 Get premium for faster travel!'}\n\n"
        f"Use /adventure to explore!",
        parse_mode='HTML'
    )
    smart_save(query.from_user.id)

def discover_connected_locations(current_location):
    """Discover new locations connected to current one"""
    connections = {
        "shadow_forest": ["abandoned_asylum", "ancient_graveyard"],
        "abandoned_asylum": ["haunted_mansion"],
        "ancient_graveyard": ["forgotten_catacombs"],
        "haunted_mansion": ["witch_coven"],
        "forgotten_catacombs": ["cursed_shipwreck"],
        "cursed_shipwreck": ["void_dimension"]
    }
    
    discovered = []
    for loc_key in connections.get(current_location, []):
        if not HORROR_LOCATIONS[loc_key].get('discovered', False):
            HORROR_LOCATIONS[loc_key]['discovered'] = True
            discovered.append(HORROR_LOCATIONS[loc_key]['name'])
    
    if discovered:
        save_user_data()
    
    return discovered




# ===== SEASONAL COMMANDS =====
async def events_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current and upcoming seasonal events"""
    current_event_key = seasonal_manager.get_current_event()
    
    if current_event_key:
        current_event = seasonal_manager.events[current_event_key]
        event_message = f"""
{current_event['name']} 🔥

*{current_event['description']}*

🎁 *Event Bonuses:*
"""
        
        # Add bonuses
        bonuses = current_event['bonuses']
        for bonus, value in bonuses.items():
            if isinstance(value, bool) and value:
                event_message += f"• ✅ {bonus.replace('_', ' ').title()}\n"
            elif isinstance(value, (int, float)) and value > 1:
                event_message += f"• ⚡ {bonus.replace('_', ' ').title()}: {value}x\n"
        
        event_message += f"""
🎪 *Exclusive Content:*
{chr(10).join([f"• {item}" for item in current_event['exclusive_content']])}

🎯 *Event Commands:*
/event_transform - Special event transformations
/event_story - Holiday horror stories  
/event_rpg - Seasonal RPG adventures
"""
    else:
        event_message = """
📅 *SEASONAL EVENTS CALENDAR*

*No active events right now... but check back for:*

🎃 **HALLOWEEN MONTH** (October)
• 31 Nights of Terror
• Everything 2x SCARIER!
• Exclusive monster transformations

🔮 **FRIDAY THE 13TH** 
• Curses 3x more powerful!
• Jason & Bloody Mary content
• Bad luck mini-games

🌕 **FULL MOON MADNESS**
• Werewolf transformations FREE!
• Lunar power boosts
• Pack hunting RPG

🎄 **KRAMPUSNACHT** (December)  
• Christmas horror stories
• Krampus monster creation
• Dark Santa boss battles

*Use /events to check current events!*
"""
    
    await update.message.reply_text(event_message, parse_mode='HTML')

async def event_transform_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Special event transformations"""
    current_event = seasonal_manager.get_current_event()
    user_id = str(update.effective_user.id)
    
    if not current_event:
        await update.message.reply_text(
            "🎭 *No active events right now!*\n\n"
            "Check /events to see upcoming seasonal horrors! 👻",
            parse_mode='HTML'
        )
        return
    
    event_data = seasonal_manager.events[current_event]
    
    # Event-specific transformations
    event_transformations = {
        "halloween": [
            ("🎃 Pumpkin King", "pumpkin_king"),
            ("👻 Headless Horseman", "headless_horseman"),
            ("🕷️ Spider Queen", "spider_queen"),
            ("💀 Skeleton Lord", "skeleton_lord")
        ],
        "friday_13": [
            ("🔪 Jason Voorhees", "jason"),
            ("🪞 Bloody Mary", "bloody_mary"), 
            ("😱 Final Girl", "final_girl"),
            ("🚗 Vanishing Hitchhiker", "hitchhiker")
        ],
        "full_moon": [
            ("🐺 Werewolf Alpha", "werewolf_alpha"),
            ("🌕 Lunar Beast", "lunar_beast"),
            ("🏹 Wolf Hunter", "wolf_hunter"),
            ("🐾 Pack Member", "pack_member")
        ],
        "christmas": [
            ("🎄 Krampus", "krampus"),
            ("🎅 Dark Santa", "dark_santa"),
            ("❄️ Yeti", "yeti"),
            ("🍪 Gingerbread Monster", "gingerbread")
        ]
    }
    
    transformations = event_transformations.get(current_event, [])
    
    keyboard = []
    for name, key in transformations:
        keyboard.append([InlineKeyboardButton(name, callback_data=f"event_transform_{key}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Events", callback_data="events_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎭 *{event_data['name']} TRANSFORMATIONS*\n\n"
        f"*Special event-only transformations!*\n\n"
        f"⚡ *Event Bonus:* {seasonal_manager.get_transformation_boost(current_event)}x faster!\n"
        f"💫 *Premium Status:* {'FREE during event! 🎁' if seasonal_manager.is_premium_free(current_event) else 'Normal rules apply'}\n\n"
        f"*Choose your event transformation:*",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def event_story_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Holiday horror stories"""
    current_event = seasonal_manager.get_current_event()
    
    if not current_event:
        await update.message.reply_text(
            "📖 *No event stories available!*\n\n"
            "Check /events for upcoming seasonal storytelling! 👻",
            parse_mode='HTML'
        )
        return
    
    event_data = seasonal_manager.events[current_event]
    
    event_stories = {
        "halloween": [
            "🎃 The Great Pumpkin's Revenge",
            "👻 Haunted Hayride Horror", 
            "🕷️ Spider-Infested Candy",
            "💀 Graveyard Shift"
        ],
        "friday_13": [
            "🔪 Camp Crystal Lake Memories",
            "🪞 The Mirror's Curse",
            "😱 Unlucky 13th Floor",
            "🚗 Highway to Hell"
        ],
        "full_moon": [
            "🐺 Pack Hunt Chronicles", 
            "🌕 Lunar Madness Tales",
            "🏹 Hunter's Moon",
            "🐾 Werewolf Legacy"
        ],
        "christmas": [
            "🎄 Krampus Comes to Town",
            "🎅 Santa's Slay Ride",
            "❄️ Frozen Ghosts of Christmas",
            "🍪 Gingerbread Nightmares"
        ]
    }
    
    stories = event_stories.get(current_event, [])
    
    keyboard = []
    for story in stories:
        keyboard.append([InlineKeyboardButton(story, callback_data=f"event_story_{hash(story)}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Events", callback_data="events_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📖 *{event_data['name']} STORIES*\n\n"
        f"*Special holiday horror tales!*\n\n"
        f"😱 *Event Bonus:* {seasonal_manager.get_story_scare_boost(current_event)}x SCARIER!\n\n"
        f"*Choose your event story:*",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def event_rpg_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Seasonal RPG adventures"""
    current_event = seasonal_manager.get_current_event()
    user_id = str(update.effective_user.id)
    
    if not current_event:
        await update.message.reply_text(
            "⚔️ *No event RPG available!*\n\n"
            "Check /events for upcoming seasonal adventures! 🎮",
            parse_mode='HTML'
        )
        return
    
    # PREMIUM CHECK (unless event makes premium free)
    if not seasonal_manager.is_premium_free(current_event) and not is_premium_user(user_id):
        await update.message.reply_text(
            "⚔️ *EVENT RPG ADVENTURES* 🔒\n\n"
            "*Seasonal RPG requires Premium access!*\n\n"
            f"💫 **Unlock with /premium to:**\n"
            "• Exclusive event RPG quests\n"
            "• Special holiday bosses\n"
            "• Limited-time rewards\n\n"
            "_Or wait for events that make Premium FREE! 🎁_",
            parse_mode='HTML'
        )
        return
    
    event_data = seasonal_manager.events[current_event]
    
    event_quests = {
        "halloween": [
            "🎃 Defeat the Pumpkin King",
            "👻 Solve the Haunted Mansion Mystery", 
            "🕷️ Clear the Spider-Infested Crypt",
            "💀 Survive the Graveyard Shift"
        ],
        "friday_13": [
            "🔪 Escape Camp Crystal Lake",
            "🪞 Break the Bloody Mary Curse",
            "😱 Survive the 13th Floor",
            "🚗 Outrun the Phantom Hitchhiker"
        ],
        "full_moon": [
            "🐺 Join the Werewolf Pack Hunt", 
            "🌕 Harness Lunar Power",
            "🏹 Hunt the Wolf Hunter",
            "🐾 Protect Pack Territory"
        ],
        "christmas": [
            "🎄 Battle Krampus and his Minions",
            "🎅 Stop Dark Santa's Slay Ride",
            "❄️ Defeat the Frozen Wraiths", 
            "🍪 Survive the Gingerbread Army"
        ]
    }
    
    quests = event_quests.get(current_event, [])
    
    keyboard = []
    for quest in quests:
        keyboard.append([InlineKeyboardButton(quest, callback_data=f"event_rpg_{hash(quest)}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Events", callback_data="events_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"⚔️ *{event_data['name']} RPG*\n\n"
        f"*Special holiday adventures await!*\n\n"
        f"⭐ *Event Bonus:* +50% EXP during events!\n"
        f"🎁 *Premium Status:* {'FREE during event! 🎉' if seasonal_manager.is_premium_free(current_event) else 'Active'}\n\n"
        f"*Choose your event quest:*",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )


# ===== SEASONAL BUTTON HANDLERS =====
async def seasonal_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle seasonal event AND location button clicks - FIXED VERSION"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    print(f"-> Button clicked: {action}")  # Debug logging
    
    if action == "events_back":
        await events_command(query, context)
        return
    
    elif action.startswith("event_transform_"):
        transform_type = action.replace("event_transform_", "")
        await handle_event_transformation(query, transform_type)
    
    elif action.startswith("event_story_"):
        story_hash = action.replace("event_story_", "")
        await handle_event_story(query, story_hash)
    
    elif action.startswith("event_rpg_"):
        quest_hash = action.replace("event_rpg_", "")
        await handle_event_rpg(query, quest_hash)
    
    elif action.startswith("travel_"):
        location_key = action.replace("travel_", "")
        await travel_to_location(query, location_key)
    
    elif action == "explore_current":
        print("-> Explore current location button clicked!")
        await query.edit_message_text(
            "🌑 *Exploring Current Location...* 🔍\n\n"
            "_Venturing into the unknown horrors..._",
            parse_mode='HTML'
        )
        await start_location_adventure(query, context)
    
    elif action.startswith("use_item_"):
        item_key = action.replace("use_item_", "")
        print(f"-> Use item callback: {item_key}")
        await process_item_usage(query, query.from_user.id, item_key)
    
    elif action.startswith("craft_"):
        item_name = action.replace("craft_", "").replace("_", " ")
        await process_crafting(query, query.from_user.id, item_name)
    
    else:
        print(f"-> Unknown button action: {action}")
        await query.edit_message_text("❌ Unknown action. Please try again!")




async def handle_event_transformation(query, transform_type):
    """Process event transformation selection"""
    current_event = seasonal_manager.get_current_event()
    
    if not current_event:
        await query.edit_message_text("❌ Event ended! Use /events to check current events.")
        return
    
    # Store the event transformation type
    user_id = query.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    
    user_data[user_id]['event_transform_type'] = transform_type
    user_data[user_id]['last_transform_style'] = "event_" + transform_type
    
    await query.edit_message_text(
        f"🎭 *EVENT TRANSFORMATION SELECTED!* 🔮\n\n"
        f"*Transformation:* {transform_type.replace('_', ' ').title()}\n\n"
        f"📸 *Now send me a portrait photo to transform!*\n\n"
        f"⚡ *Event Bonus:* Processing is {seasonal_manager.get_transformation_boost(current_event)}x faster!",
        parse_mode='HTML'
    )

async def handle_event_story(query, story_hash):
    """Generate and send event story"""
    current_event = seasonal_manager.get_current_event()
    
    if not current_event:
        await query.edit_message_text("❌ Event ended! Use /events to check current events.")
        return
    
    event_data = seasonal_manager.events[current_event]
    
    await query.edit_message_text(
        f"📖 *Summoning {event_data['name']} Story...* 🔮\n\n"
        f"_The holiday horrors are gathering..._",
        parse_mode='HTML'
    )
    
    # Generate event-specific story prompt
    event_prompts = {
        "halloween": "Create a terrifying HALLOWEEN horror story with pumpkins, ghosts, and trick-or-treating gone wrong. Include classic Halloween monsters and make it extra spooky with autumn atmosphere.",
        "friday_13": "Write a FRIDAY THE 13TH horror story about bad luck, curses, and supernatural events. Include elements of superstition, mirrors, black cats, and things going terribly wrong.",
        "full_moon": "Create a FULL MOON horror story about werewolves, lunar madness, and transformations. Include pack dynamics, silver vulnerabilities, and the terror of the changing moon.",
        "christmas": "Write a CHRISTMAS HORROR story about Krampus, dark Santa, or holiday ghosts. Mix festive elements with terrifying horror - presents that curse, carols that summon spirits, etc."
    }
    
    prompt = event_prompts.get(current_event, "Create a seasonal horror story.")
    prompt += f"\n\nMake it {seasonal_manager.get_story_scare_boost(current_event)}x SCARIER than normal!"
    
    try:
        response = model.generate_content(prompt)
        story_text = response.text.strip()
        
        formatted_story = f"📖 *{event_data['name']} STORY* 🔮\n\n{story_text}\n\n🎁 *Special Event Story Complete!*"
        
        await query.message.reply_text(formatted_story, parse_mode='HTML')
        
        # Generate audio version
        clean_story = clean_text_for_audio(story_text)
        await auto_voice_message(
            query.message,
            clean_story,
            f"🎧 {event_data['name']} STORY 🔊"
        )
        
    except Exception as e:
        print(f"Event story error: {e}")
        await query.message.reply_text("⚡ The event spirits are restless... try again! 🔮")

async def handle_event_rpg(query, quest_hash):
    """Start event RPG adventure"""
    current_event = seasonal_manager.get_current_event()
    user_id = query.from_user.id
    
    if not current_event:
        await query.edit_message_text("❌ Event ended! Use /events to check current events.")
        return
    
    # Check if user has RPG character
    if user_id not in user_data or 'rpg_character' not in user_data[user_id]:
        await query.edit_message_text("Use /rpg_start first to create your character! 🎮")
        return
    
    event_data = seasonal_manager.events[current_event]
    
    await query.edit_message_text(
        f"⚔️ *Starting {event_data['name']} Adventure...* 🗺️\n\n"
        f"_The holiday horrors await your bravery..._",
        parse_mode='HTML'
    )
    
    # Generate event-specific RPG scenario
    event_scenarios = {
        "halloween": f"""
Create a HALLOWEEN RPG scenario for a horror adventurer. Location: Haunted Halloween Town. Include pumpkin monsters, ghostly trick-or-treaters, and a spooky autumn atmosphere. Make it {seasonal_manager.get_story_scare_boost(current_event)}x scarier than normal!

Format:
SCENARIO: [4-6 sentence Halloween adventure]
BRAVE: [1 sentence brave Halloween action]
CAUTIOUS: [1 sentence cautious Halloween action]
""",
        "friday_13": f"""
Create a FRIDAY THE 13TH RPG scenario full of bad luck and curses. Location: Unlucky location like abandoned asylum or cursed town. Include supernatural misfortunes, mirror magic, and 13-related horrors.

Format:  
SCENARIO: [4-6 sentence Friday the 13th adventure]
BRAVE: [1 sentence brave action against curses]
CAUTIOUS: [1 sentence cautious superstitious action]
""",
        "full_moon": f"""
Create a FULL MOON RPG scenario about werewolves and lunar power. Location: Moonlit forest or ancient ruins. Include pack dynamics, transformation themes, and silver vulnerabilities.

Format:
SCENARIO: [4-6 sentence full moon adventure]  
BRAVE: [1 sentence brave werewolf action]
CAUTIOUS: [1 sentence cautious lunar action]
""",
        "christmas": f"""
Create a CHRISTMAS HORROR RPG scenario with Krampus or dark Santa. Location: Frozen North Pole or haunted workshop. Include festive horrors, frozen ghosts, and holiday-themed monsters.

Format:
SCENARIO: [4-6 sentence Christmas horror adventure]
BRAVE: [1 sentence brave holiday action]
CAUTIOUS: [1 sentence cautious festive action]
"""
    }
    
    prompt = event_scenarios.get(current_event, "Create a seasonal RPG adventure.")
    
    try:
        response = model.generate_content(prompt)
        scenario_text = response.text.strip()
        
        # Store in RPG state
        rpg_state = get_rpg_state(user_id)
        rpg_state['current_adventure'] = scenario_text
        rpg_state['status'] = RPGState.ACTIVE
        rpg_state['is_event'] = True
        rpg_state['event_type'] = current_event
        
        adventure_text = f"""
🌑 *{event_data['name']} QUEST* 🗺️

{scenario_text}

⚔️ /action1 - Brave & Risky
🛡️ /action2 - Cautious & Safe  
🏃 /flee - Run Away

⭐ *Event Bonus:* +50% EXP during events!
"""
        
        await query.message.reply_text(adventure_text, parse_mode='HTML')
        
        # Auto-play audio
        await auto_voice_message(
            query.message,
            scenario_text,
            f"🎧 {event_data['name']} QUEST 🔊"
        )
        
    except Exception as e:
        print(f"Event RPG error: {e}")
        await query.message.reply_text("⚡ The event adventure portal collapsed... try again! 🌌")

# Enhanced craftable items with stat bonuses
CRAFTABLE_ITEMS = {
    'Silver Bullet 🎯': {
        'requires': ['Mystical Herbs 🌿', 'Old Journal 📖'], 
        'gives': 'Silver Bullet 🎯',
        'description': 'A blessed silver bullet effective against werewolves',
        'effect': 'werewolf_damage_boost',
        'stat_bonus': {'werewolf_damage': 2.0},
        'crafting_exp': 25
    },
    'Spirit Camera 📷': {
        'requires': ['Flashlight 🔦', 'Old Journal 📖'], 
        'gives': 'Spirit Camera 📷',
        'description': 'Can capture images of spiritual entities',
        'effect': 'ghost_reveal',
        'stat_bonus': {'spirit_detection': True},
        'crafting_exp': 30
    },
    'Enhanced Holy Water 💧': {
        'requires': ['Holy Water 💧', 'Mystical Herbs 🌿'], 
        'gives': 'Enhanced Holy Water 💧',
        'description': 'Twice as effective against undead creatures',
        'effect': 'strong_repel_undead',
        'stat_bonus': {'undead_damage': 2.0, 'sanity_boost': 20},
        'crafting_exp': 35
    },
    'Protective Amulet 🛡️': {
        'requires': ['Mystical Herbs 🌿', 'Silver Bullet 🎯'],
        'gives': 'Protective Amulet 🛡️',
        'description': 'Provides protection against dark magic',
        'effect': 'damage_reduction',
        'stat_bonus': {'fear_resistance': 15, 'damage_reduction': 0.2},
        'crafting_exp': 40
    },
    'Ancient Tome 📚': {
        'requires': ['Old Journal 📖', 'Old Journal 📖'],
        'gives': 'Ancient Tome 📚', 
        'description': 'Contains forbidden knowledge and powerful rituals',
        'effect': 'knowledge_boost',
        'stat_bonus': {'exp_gain': 1.25, 'ritual_power': True},
        'crafting_exp': 50
    }
}

# Add these new items to RPG_ITEMS
RPG_ITEMS.update({
    'enhanced_holy_water': {
        'name': 'Enhanced Holy Water 💧',
        'display_name': 'Enhanced Holy Water 💧',
        'description': 'Twice as effective against undead',
        'usage': 'Use against powerful supernatural enemies',
        'effect': 'strong_repel_undead'
    },
    'protective_amulet': {
        'name': 'Protective Amulet 🛡️',
        'display_name': 'Protective Amulet 🛡️',
        'description': 'Provides protection against dark magic',
        'usage': 'Passively reduces damage from supernatural attacks',
        'effect': 'damage_reduction'
    },
    'ancient_tome': {
        'name': 'Ancient Tome 📚',
        'display_name': 'Ancient Tome 📚',
        'description': 'Contains forbidden knowledge and rituals',
        'usage': 'Increases experience gain and ritual power',
        'effect': 'knowledge_boost'
    }
})

# Update the reverse mapping
ITEM_DISPLAY_TO_KEY.update({
    'Enhanced Holy Water 💧': 'enhanced_holy_water',
    'Protective Amulet 🛡️': 'protective_amulet', 
    'Ancient Tome 📚': 'ancient_tome'
})

async def process_crafting(query, user_id, item_name):
    """Process crafting an item with stat bonuses"""
    char = user_data[user_id]['rpg_character']
    inventory = user_data[user_id]['rpg_inventory']
    
    if item_name not in CRAFTABLE_ITEMS:
        await query.edit_message_text(f"❌ Cannot craft '{item_name}' - Unknown recipe!")
        return
    
    recipe = CRAFTABLE_ITEMS[item_name]
    
    # Check if user has required items
    missing_items = []
    for required_item in recipe['requires']:
        if required_item not in inventory:
            missing_items.append(required_item)
    
    if missing_items:
        await query.edit_message_text(
            f"❌ Cannot craft {item_name}!\n\n"
            f"Missing: {', '.join(missing_items)}\n\n"
            f"Continue adventuring to find these items!",
            parse_mode='HTML'
        )
        return
    
    # Remove required items and add crafted item
    for required_item in recipe['requires']:
        inventory.remove(required_item)
    
    inventory.append(recipe['gives'])
    
    # Award crafting experience
    char['experience'] += recipe['crafting_exp']
    
    # Update leaderboard and stats
    update_leaderboard(user_id, 'items_collected', 1)
    update_leaderboard(user_id, 'items_crafted', 1)
    
    # Apply stat bonuses if any
    stat_bonus_text = ""
    if recipe.get('stat_bonus'):
        for stat, bonus in recipe['stat_bonus'].items():
            if stat == 'fear_resistance':
                char['fear_resistance'] = min(100, char['fear_resistance'] + bonus)
                stat_bonus_text += f"\n• +{bonus}% Fear Resistance"
            elif stat == 'werewolf_damage':
                char['werewolf_damage'] = bonus
                stat_bonus_text += f"\n• {bonus}x Damage vs Werewolves"
            elif stat == 'undead_damage':
                char['undead_damage'] = bonus
                stat_bonus_text += f"\n• {bonus}x Damage vs Undead"
            elif stat == 'exp_gain':
                char['exp_multiplier'] = bonus
                stat_bonus_text += f"\n• {int((bonus-1)*100)}% More Experience"
    
    # Check for level up from crafting exp
    level_up_msg = ""
    if char['experience'] >= 100:
        char['level'] += 1
        char['experience'] = 0
        char['fear_resistance'] += 15
        level_up_msg = f"\n\n🎉 LEVEL UP from crafting! Now Level {char['level']}!"
    
    # Save data
    save_user_data()
    # Check for crafting achievements
    check_achievements(user_id)
    
    await query.edit_message_text(
        f"🔧 *CRAFTING SUCCESSFUL!* 🎉\n\n"
        f"*Created:* {recipe['gives']}\n"
        f"*Description:* {recipe['description']}\n"
        f"*Crafting EXP:* +{recipe['crafting_exp']} EXP\n\n"
        f"*Stat Bonuses:*{stat_bonus_text if stat_bonus_text else ' None (passive effect)'}\n\n"
        f"*Used:* {', '.join(recipe['requires'])}\n\n"
        f"{level_up_msg}\n\n"
        f"Your new item has been added to your inventory!",
        parse_mode='HTML'
    )




# In your universal_button_handler function, make sure it looks like this:

async def universal_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ALL button clicks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data
    
    print(f"-> Universal handler: {action}")
    
    # Handle Tic-Tac-Toe Accept/Decline FIRST (before other tictactoe handlers)
    if action == "tictactoe_accept":
        await handle_tictactoe_accept(query, user_id, context)
        return
    elif action == "tictactoe_decline":
        await handle_tictactoe_decline(query, user_id, context)
        return
    
    # Handle menu buttons
    elif action.startswith("menu_"):
        await handle_menu_button(query, action)
    
    # Handle story buttons
    elif action.startswith("story_"):
        await handle_story_button(query, action)
    
    elif action.startswith("game_"):
        await handle_games_panel_button(query, action, context)

    # Handle premium buttons
    elif action.startswith("premium_") or action.startswith("stars_"):
        await handle_premium_button(query, action, user_id)

    # Handle GWT buttons
    elif action.startswith("gwt_"):
        choice = action.replace("gwt_", "")
        await handle_gwt_choice(query, str(user_id), choice)
    
    # Handle support buttons
    elif action == "support_bug":
        await query.edit_message_text(
            "🐛 *REPORT A BUG* 🔧\n\n"
            "Use the command:\n"
            "`/bugreport [description]`\n\n"
            "*Please include:*\n"
            "• What you were doing\n"
            "• What error message you saw\n"
            "• Steps to reproduce the issue\n\n"
            "*Example:*\n"
            "`/bugreport The vampire transformation failed with a network error when I uploaded a photo`",
            parse_mode='HTML'
        )
    

    # Callback handlers (werewolfgame)
    elif action.startswith("werewolf_"):
        if action == "werewolf_join":
            await handle_werewolf_join(query, str(user_id), context)
        elif action == "werewolf_start_game":
            await handle_werewolf_start(query, str(user_id), context)
        elif action.startswith("werewolf_kill_"):
            target_id = action.replace("werewolf_kill_", "")
            await handle_werewolf_kill(query, str(user_id), target_id, context)
        elif action.startswith("werewolf_seer_"):
            target_id = action.replace("werewolf_seer_", "")
            await handle_werewolf_seer(query, str(user_id), target_id, context)
        elif action.startswith("werewolf_doctor_"):
            target_id = action.replace("werewolf_doctor_", "")
            await handle_werewolf_doctor(query, str(user_id), target_id, context)
        elif action.startswith("werewolf_hunter_"):
            target_id = action.replace("werewolf_hunter_", "")
            await handle_werewolf_hunter(query, str(user_id), target_id, context)

    elif action == "ghoststory_add":
        await ghoststory_add_button(query, str(user_id), context)
    elif action.startswith("ghoststory_vote_"):
        line_index = action.split("_")[2]
        await ghoststory_vote(query, str(user_id), line_index, context)



    elif action == "menu_back":
        await menu_command(update, context)
    
    elif action == "support_feature":
        await query.edit_message_text(
            "💡 *SUGGEST A FEATURE* 🎯\n\n"
            "Use the command:\n"
            "`/featurerequest [your idea]`\n\n"
            "*What we love to see:*\n"
            "• Creative horror ideas\n"
            "• RPG improvements\n"
            "• New monster types\n"
            "• Quality of life features\n\n"
            "*Example:*\n"
            "`/featurerequest Add a haunted house location with jump scares in the RPG`",
            parse_mode='HTML'
        )
    
    # Handle RPG class selection and cancel
    elif action.startswith("rpg_class_"):
        await rpg_class_handler(update, context)  # Routes to RPG class creator
    
    elif action == "treat_donate":
        try:
            await query.edit_message_text(
                "🍬 *TRICK OR TREAT!* 🎃\n\n"
                "The spooky spirit appreciates your generosity! 💀\n\n"
                "Click below to send your *2⭐ treat* (Stars Donation):",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⭐ Send 2 Stars", callback_data="donate_2stars")],
                ])
            )
        except telegram.error.BadRequest:
            await query.message.reply_text(
                "🍬 *TRICK OR TREAT!* 🎃\n\n"
                "The spooky spirit appreciates your generosity! 💀\n\n"
                "Click below to send your *2⭐ treat* (Stars Donation):",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⭐ Send 2 Stars", callback_data="donate_2stars")],
                ])
            )
    
    elif action == "donate_2stars":
        try:
            await query.edit_message_text(
                "💫 Thank you for your *2⭐ treat!* 🎃\n"
                "The spirits whisper your name in gratitude... 👻",
                parse_mode="HTML"
            )
        except telegram.error.BadRequest:
            await query.message.reply_text(
                "💫 Thank you for your *2⭐ treat!* 🎃\n"
                "The spirits whisper your name in gratitude... 👻",
                parse_mode="HTML"
            )
    
    elif action == "rpg_cancel":
        await query.edit_message_text(
            "❌ *RPG CREATION CANCELLED* 👻\n\n"
            "No character was created. Use /rpg_start again when ready!\n\n"
            "_The shadows retreat... for now._ 🔮",
            parse_mode='HTML'
        )
    
    # Handle Tic-Tac-Toe MOVE buttons (numbers 0-8)
    elif action.startswith("tictactoe_"):
        try:
            position = int(action.split("_")[1])
            await handle_tictactoe_move(query, str(user_id), position, context)
        except (ValueError, IndexError):
            # If it's not a number, it's an unknown tictactoe action
            print(f"-> Unknown Tic-Tac-Toe action: {action}")
            await query.answer("❌ Unknown Tic-Tac-Toe action!")
    
    # Handle other buttons
    elif action.startswith("use_item_"):
        item_key = action.replace("use_item_", "")
        await process_item_usage(query, user_id, item_key)
    
    elif action.startswith("craft_"):
        item_name = action.replace("craft_", "").replace("_", " ")
        await process_crafting(query, user_id, item_name)
    
    elif action.startswith("travel_"):
        location_key = action.replace("travel_", "")
        await travel_to_location(query, location_key)
    
    elif action == "explore_current":
        await start_location_adventure(query, context)
    
    else:
        print(f"-> Unknown button action: {action}")
        await query.edit_message_text("❌ Unknown action. Please try again!")


# ===== MESSAGE HANDLER =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages"""
    user_id = str(update.effective_user.id)
    message_text = update.message.text
    
    # Ignore messages in groups (only respond in private chats)
    if update.effective_chat.type in ["group", "supergroup"]:
        return
    
    # Check if this is part of monster creation
    if user_id in user_data and 'monster_creation' in user_data[user_id]:
        await handle_monster_creation(update, context)
        return
    
    # Default response for unknown commands
    await update.message.reply_text(
        "👻 *I'm SpookyBot!* 🎃\n\n"
        "I don't understand regular messages. Use commands to interact with me!\n\n"
        "*Try these:*\n"
        "/menu - See all features\n"
        "/start - Welcome message\n"
        "/help - Get assistance\n\n"
        "_The ghosts only understand commands..._ 🔮",
        parse_mode='HTML'
    )


async def spookyfight_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play Pumpkin–Spider–Vampire (rock–paper–scissors variant)."""
    user = update.effective_user
    if not user:
        await update.message.reply_text("❌ Can't identify you.")
        return

    user_id = str(user.id)
    user_choice = None
    if context.args:
        user_choice = context.args[0].lower()
    else:
        await update.message.reply_text(
            "🎃 *Choose your move!*\n"
            "`/spookyfight pumpkin` 🥊\n"
            "`/spookyfight spider` 🕷\n"
            "`/spookyfight vampire` 🧛",
            parse_mode="Markdown",
        )
        return

    valid_moves = ["pumpkin", "spider", "vampire"]
    if user_choice not in valid_moves:
        await update.message.reply_text(
            "❌ Invalid choice. Use `/spookyfight pumpkin`, `/spookyfight spider`, or `/spookyfight vampire`.",
            parse_mode="Markdown",
        )
        return

    # Bot (SpookyBot) makes a random move
    bot_choice = random.choice(valid_moves)

    # Decide outcome
    outcome = ""
    if user_choice == bot_choice:
        outcome = "😐 It's a draw!"
    elif (
        (user_choice == "pumpkin" and bot_choice == "spider") or
        (user_choice == "spider" and bot_choice == "vampire") or
        (user_choice == "vampire" and bot_choice == "pumpkin")
    ):
        outcome = "🕸️ You *win!* 🎉"
    else:
        outcome = "💀 You *lose!* The darkness laughs..."

    # Update simple score counter
    user_data.setdefault(user_id, {})
    stats = user_data[user_id].setdefault("spookyfight_stats", {"wins":0,"losses":0,"draws":0})
    if "win" in outcome:
        stats["wins"] += 1
    elif "lose" in outcome:
        stats["losses"] += 1
    else:
        stats["draws"] += 1

    # Message
    result = (
        f"🎃 *SPOOKY FIGHT!* 👻\n"
        f"You chose: *{user_choice.capitalize()}*\n"
        f"Bot chose: *{bot_choice.capitalize()}*\n\n"
        f"{outcome}\n\n"
        f"🏆 Wins: {stats['wins']} | 💀 Losses: {stats['losses']} | 😐 Draws: {stats['draws']}"
    )

    safe_text = escape_markdown(result, version=2)
    await update.message.reply_text(safe_text, parse_mode="MarkdownV2")



async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information"""
    help_text = """
👻 *SPOOKYBOT HELP* 🎃

<b>Main Commands:</b>
/start - Welcome message
/menu - Main menu with all features
/premium - Unlock premium features

<b>Group Features:</b>
/games - cool games to play in group
/scareboard - Group leaderboard
/dailyscare - Daily challenges
/addscare - Award scare points
/Games - play games with freinds here 
/dailyscare — make scary content for scarepoints
/addscare — earn group scare points 👻

<b>Games to Play Privately </b>
/spooky - an entity that evovle per every text u send it
/broadcast - get zombie feedback save survivors 
/spookyfight - for best rock paper scissors game

<b>Horror Features:</b>
/story - Generate horror stories
/transform - Transform photos into monsters
/createmonster - Design custom monsters
/monsterstory - Create stories with your monsters

<b>Fun Scary:</b>
/horrorsound - Spooky audio
/horrorfact - Scary facts
/halloweencountdown - Days until Halloween
/scareme - Quick scare
/summon - Haunt users with AI
/curse - Quick AI curse

<b>Support:</b>
/support - Get help
/bugreport - Report issues
/featurerequest - Suggest features

*Need more help?* Contact @electrokid_1
"""
    await update.message.reply_text(help_text, parse_mode='HTML')



async def handle_menu_button(query, action):
    """Handle menu button clicks"""
    menu_action = action.replace("menu_", "")
    
    menu_categories = {
        "transformations": {
            "title": "🧛 PHOTO TRANSFORMATIONS 🎨",
            "description": "Turn your photos into terrifying monsters!",
            "commands": """
*Available Commands:*
• `/ghost` - Ghostly spirit
• `/zombie` - Zombie apocalypse  
• `/monster` - Grotesque monster
• `/werewolf` - Beast transformation
• `/demon` - Infernal demon
• `/witch` - Dark witch
• `/eldritch` - Cosmic horror
• `/custom [prompt]` - Create your own horror

*Usage:* Send command + photo!
            """
        },
"support": {
    "title": "🆘 SUPPORT & CONTACT 🔧",
    "description": "Get help and report issues",
    "commands": """
*Support Commands:*
• /support - Contact information
• /bugreport [description] - Report bugs
• /featurerequest [idea] - Suggest features

*Need Help?*
• Check /menu for features
• Read /premium for subscription info
• Contact us via /support

*We're here to help!* 👻
    """
},
        "stories": {
            "title": "📖 HORROR STORIES 🔮",
            "description": "AI-generated terrifying tales",
            "commands": """
*Available Commands:*
• `/story` - Choose story category
• Bloody 🩸 - Gore and violence
• Short ⏳ - Quick fears  
• Scary 😨 - Classic horror
• Very Scary 💀 - Ultimate terror

*Each story comes with audio narration!*
            """
        },
        "rpg": {
            "title": "⚔️ HORROR RPG GAME 🎮",
            "description": "Embark on terrifying adventures!",
            "commands": """
*RPG Commands:*
• /broadcast - 👾 zombie game broadcast
• /spooky - 👾 chat with an evolving creature
• /spookyfight - 👾 play with a bot

play games feel free!*
            """
        },
        "audio": {
            "title": "🎧 HORROR AUDIO 🔊",
            "description": "Spooky sounds and voice messages",
            "commands": """
*Audio Commands:*
• `/horrorsound` - Random horror audio
            """
        },
        "fun": {
            "title": "👻 FUN COMMANDS 🎪",
            "description": "Quick scares and horror facts",
            "commands": """
*Quick Commands:*
• `/horrorfact` - Random horror fact
• `/scareme` - Quick scary message
• `/halloweencountdown` - Days until Halloween
• `/summon @user` - Haunt specific users
• `/curse` - Instant AI curse

*Perfect for quick scares!*
            """
        },
        "monster": {
            "title": "🧌 MONSTER CREATOR 👹",
            "description": "Design your own horror creatures!",
            "commands": """
*Monster Commands:*
• `/createmonster` - Design a custom monster
• Describe appearance, powers, weaknesses
• AI generates name, stats, and story
• `/monsterstory` - Create story with your monster

*Create unique nightmares!*
            """
        },
       # In your premium menu section:
"premium": {
    "title": "💫 PREMIUM FEATURES 👑",
    "description": "Unlock enhanced horror experiences!",
    "commands": """

*Other /Premium Features:*
• Unlimited transformations
• Unlimited horror stories  
• Custom horror creation
• Monster creator
• Advanced AI summoning

*Get Premium:*
• /premium - View plans
• 99 Stars - 24 hours
• 299 Stars - 7 days  
• 999 Stars - 1 month
"""
}
    }
    
    if menu_action == "back":
        # Go back to main menu
        keyboard = [
            [InlineKeyboardButton("🧛 Transformations", callback_data="menu_transformations"),
             InlineKeyboardButton("📖 Stories", callback_data="menu_stories")],
            [InlineKeyboardButton("🎮 Games", callback_data="menu_rpg"),
             InlineKeyboardButton("🎧 Horror Audio", callback_data="menu_audio")],
            [InlineKeyboardButton("👻 Fun Commands", callback_data="menu_fun"),
             InlineKeyboardButton("🧌 Create Monster", callback_data="menu_monster")],
            [InlineKeyboardButton("💫 PREMIUM FEATURES", callback_data="menu_premium")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎃 *SPOOKYBOT MAIN MENU* 👻\n\n"
            "*Choose your path to terror:*\n\n"
            "🧛 **Transformations** - Turn photos into monsters\n"
            "📖 **Horror Stories** - AI-generated scary tales\n"
            "⚔️ *Games** - nice cool games\n"
            "🎧 **Horror Audio** - Spooky sounds & voices\n"
            "👻 **Fun Commands** - Quick scares & facts\n"
            "🧌 **Create Monster** - Design custom creatures\n"
            "💫 **PREMIUM** - Unlock unlimited features\n\n"
            "_Select a category below:_ 🔮",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif menu_action in menu_categories:
        category = menu_categories[menu_action]
        await query.edit_message_text(
            f"*{category['title']}*\n\n"
            f"{category['description']}\n\n"
            f"{category['commands']}\n\n"
            f"_Use the commands above or go back to the main menu._",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_back")
            ]])
        )
    
    else:
        await query.edit_message_text("🎯 Feature coming soon! Stay tuned... 👻")






def update_achievement_progress(user_id, category, amount=1):
    """Update user's achievement progress safely and unlock if completed."""
    user_id = str(user_id)

    # Ensure user exists
    if user_id not in user_data:
        user_data[user_id] = {}

    # Get or fix achievement structure
    achievements = user_data[user_id].get('achievements')

    # 🩸 FIX: Handle if 'achievements' is a list or corrupted
    if not isinstance(achievements, dict):
        achievements = {'unlocked': [], 'progress': {}}
        user_data[user_id]['achievements'] = achievements

    # 🩸 FIX: Ensure 'progress' is a dict, not a list
    if not isinstance(achievements.get('progress'), dict):
        achievements['progress'] = {}

    # Update the progress safely
    current_value = achievements['progress'].get(category, 0)
    achievements['progress'][category] = current_value + amount

    # Check for unlocks
    for aid, ach in GROUP_ACHIEVEMENTS.items():
        if ach['type'] == category:
            if achievements['progress'][category] >= ach['requirement'] and aid not in achievements['unlocked']:
                achievements['unlocked'].append(aid)
                save_user_data()
                return ach  # Return unlocked achievement

    save_user_data()
    return None




async def admin_fix_date_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fix date serialization error in user_data.json"""
    user_id = str(update.effective_user.id)
    if user_id != "7351537370":
        await update.message.reply_text("❌ Admin only!")
        return
    
    # Fix the current file by converting all date objects
    if os.path.exists('user_data.json'):
        try:
            # Read and parse the file manually
            with open('user_data.json', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Fix the specific error: "last_reset": with date object
            # We need to reload the data, convert dates, and save properly
            with open('user_data.json', 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            # Convert all date strings in the loaded data
            for uid, user_info in raw_data.items():
                if 'usage' in user_info and 'last_reset' in user_info['usage']:
                    # If last_reset is already a string, leave it
                    # If it's a date object, it won't be in JSON, so this is safe
                    pass
            
            # Save using the universal encoder
            with open('user_data.json', 'w', encoding='utf-8') as f:
                json.dump(raw_data, f, cls=UniversalJSONEncoder, ensure_ascii=False, indent=2)
            
            # Reload the data
            global user_data
            load_user_data()
            
            await update.message.reply_text(
                "✅ *DATE ERROR FIXED!*\n\n"
                "Fixed date serialization issue.\n"
                f"Loaded {len(user_data)} users successfully!",
                parse_mode='HTML'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Fix failed: {e}")
    else:
        await update.message.reply_text("❌ user_data.json not found")





async def generate_story_from_button(query, category):
    """Generate story based on button selection"""
    try:
        # Map category to proper format
        category_map = {
            "very_scary": "very-scary"
        }
        story_category = category_map.get(category, category)
        
        # Generate story using Gemini
        story_prompt = f"""
Create a {story_category.upper()} horror story based on creepy myths and legends.

STORY REQUIREMENTS:
- Base the story on creepy myths/legends like [Bloody Mary, The Hookman, The Candyman, The Licked Hand, The Headless Horseman, La Llorona, The Jersey Devil, The Wendigo, The Chupacabra, The Mothman, Slender Man, Kuchisake-Onna, The Nain Rouge, The Night Marchers, Goatman, The Body Under the Bed, Polybius, Sewer Alligators, The Black Dog, Spring-Heeled Jack, and others u may know]. not exacly but like them dont necessarily make it abt them u can make some on your own
- 2-3 paragraphs maximum
- No emojis in the story text
- Include psychological horror elements
- Make it feel personal and immediate
- End with a chilling twist

Create something absolutely TERRIFYING:
"""

        # FIXED: Wrap Gemini call (non-blocking)
        response = await asyncio.to_thread(model.generate_content, story_prompt)
        
        if response.text:
            story_text = response.text.strip()
            
            # Format the story for Telegram
            formatted_story = format_story_for_display(story_text, story_category)
            
            # FIXED: Wrap image generation (non-blocking, assuming generate_story_image is sync)
            image_url = await asyncio.to_thread(generate_story_image, story_category)
            
            # Clean text for audio (remove formatting)
            clean_story = clean_text_for_audio(story_text)
            
            # Send audio FIRST using the proven auto_voice_message function
            await auto_voice_message(
                query.message,  # Pass the message object directly
                clean_story,
                f"🎧 {get_category_name(story_category)} STORY {get_category_emoji(story_category)}"
            )
            print(f"-> {story_category} story audio sent!")
            
            # Then send the text story with image
            if image_url:
                caption = shorten_story_for_caption(formatted_story)
                
                # Send image with shortened caption
                await query.message.reply_photo(
                    photo=image_url,
                    caption=caption,
                    parse_mode='HTML'
                )
                print(f"-> {story_category} story with image sent!")
                
                # If story was shortened, send the rest as continuation
                if len(formatted_story) > len(caption):
                    continuation = formatted_story.replace(caption, "").replace("📖 <i>Story continues below...</i> 👇", "").strip()
                    if continuation:
                        await query.message.reply_text(
                            continuation,
                            parse_mode='HTML'
                        )
            else:
                # Fallback: just send text story
                await query.message.reply_text(formatted_story, parse_mode='HTML')
            
            # === ACHIEVEMENT TRACKING ===
            user_id = query.from_user.id
            if query.message.chat.id < 0:  # Group chat
                new_achievements = track_achievement(user_id, 'stories', 1)
                
                # Notify about new achievements
                for achievement in new_achievements:
                    await query.message.reply_text(
                        f"🎉 *ACHIEVEMENT UNLOCKED!* 🏅\n\n"
                        f"**{achievement['name']}**\n"
                        f"{achievement['description']}",
                        parse_mode='HTML'
                    )
            
        else:
            await query.message.reply_text(
                "📖 The ancient tomes are silent... try again! 🔮",
                parse_mode='HTML'
            )
            
    except Exception as e:
        print(f"Story generation error: {e}")
        await query.message.reply_text(
            "⚡ The story portal collapsed... the spirits are restless... 🌌",
            parse_mode='HTML'
        )



async def handle_story_button(query, action):
    """Handle story button clicks"""
    user_id = query.from_user.id
    
    # Check usage for free users
    if not is_premium_user(user_id) and not can_use_story(user_id):
        await query.edit_message_text(
            "📖 *DAILY STORY LIMIT REACHED* 🔒\n\n"
            "You've used your 1 free story for today!\n\n"
            "💫 **Unlock with /premium to:**\n"
            "• Unlimited horror stories\n"
            "• All story categories\n"
            "• No daily limits\n\n"
            "_Use /premium for endless nightmares..._ 📚",
            parse_mode='HTML'
        )
        return
    
    # Increment usage for free users
    if not is_premium_user(user_id):
        increment_usage(user_id, 'story')
    
    # Extract category from callback data
    category = action.replace("story_", "")
    
    category_info = {
        "bloody": {"emoji": "🩸", "name": "BLOODY GORE", "message": "Summoning blood-soaked legends..."},
        "short": {"emoji": "⏳", "name": "QUICK TERROR", "message": "Weaving a brief nightmare..."},
        "scary": {"emoji": "😨", "name": "CLASSIC HORROR", "message": "Invoking ancient fears..."},
        "very_scary": {"emoji": "💀", "name": "ULTIMATE NIGHTMARE", "message": "Unleashing ultimate terror..."}
    }
    
    info = category_info.get(category, {"emoji": "📖", "name": "HORROR STORY", "message": "Creating your nightmare..."})
    
    # Edit the original message to show we're generating
    await query.edit_message_text(
        f"{info['emoji']} *{info['name']}* 🔮\n\n"
        f"{info['message']}\n"
        f"_Consulting the ancient texts..._ 📜",
        parse_mode='HTML'
    )
    
    # Generate the story
    await generate_story_from_button(query, category)

async def my_tier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's scare tier combining both systems"""
    try:
        user_id = str(update.effective_user.id)
        chat_id = str(update.effective_chat.id)
        
        total_points = 0
        achievement_points = 0
        voting_points = 0
        
        # 1. ACHIEVEMENT POINTS
        achievements_data = init_user_achievements(user_id)
        achievement_points = sum(achievements_data['progress'].values())
        total_points += achievement_points
        
        # 2. VOTING POINTS
        if int(chat_id) < 0:
            leaderboard = init_group_leaderboard(chat_id)
            username = update.effective_user.username or update.effective_user.first_name
            
            if username in leaderboard:
                voting_points = leaderboard[username]['score']
                total_points += voting_points
        
        # 3. GET TIER
        user_tier = get_user_tier(total_points)
        
        # 4. BUILD DISPLAY
        tier_text = f"🎖️ YOUR SCARE TIER 🏆\n🎖️ *GET MORE SCARE /DAILYSCARE * \n\n"
        tier_text += f"{user_tier['color']} *{user_tier['title']}*\n"
        tier_text += f"📊 Total Points: {total_points}\n\n"
        
        if int(chat_id) < 0:
            tier_text += f"📈 Voting Points: {voting_points}\n"
            tier_text += f"⚡ Achievement Points: {achievement_points}\n\n"
        
        # TIER PROGRESSION
        tier_text += "🎯 *TIER PROGRESSION:*\n"
        sorted_tiers = sorted(SCARE_TIERS.keys())
        next_tier = None
        
        for points in sorted_tiers:
            tier_info = SCARE_TIERS[points]
            if total_points >= points:
                tier_text += f"✅ {tier_info['color']} {points}+: {tier_info['title']}\n"
            else:
                if not next_tier:
                    next_tier = tier_info
                    points_needed = points - total_points
                    tier_text += f"\n⬆️ Next: {next_tier['color']} {next_tier['title']}\n"
                    tier_text += f"📈 Need: {points_needed} points\n\n"
                tier_text += f"🔒 {tier_info['color']} {points}+: {tier_info['title']}\n\n"
        await update.message.reply_text(tier_text, parse_mode='HTML')
        
    except Exception as e:
        print(f"❌ my_tier error: {e}")
        await update.message.reply_text("🎖️ Tier system error - try again!", parse_mode='HTML')
    save_user_data()

async def announce_winner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Announce current leader"""
    chat_id = str(update.effective_chat.id)
    leaderboard = init_group_leaderboard(chat_id)
    
    if leaderboard:
        top_user = max(leaderboard.items(), key=lambda x: x[1]['score'])
        await update.message.reply_text(
            f"🏆 *CURRENT LEADER*: {top_user[1]['username']} with {top_user[1]['score']} points! 👑",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text("🏆 No leaders yet! Be the first to earn points! 🎯", parse_mode='HTML')

USER_DATA_FILE = "user_data.json"
SCARE_DATA_FILE = "scare_votes.json"

scare_data = {}

def save_json(data, filename):
    def safe_default(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return str(obj)
    
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, default=safe_default, ensure_ascii=False, indent=2)
        print(f"💾 Saved {filename}")
    except Exception as e:
        print(f"❌ Error saving {filename}: {e}")

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading {filename}: {e}")
    return {}

user_data = load_json(USER_DATA_FILE)
scare_data = load_json(SCARE_DATA_FILE)
print(f"✅ Loaded {len(user_data)} users and {len(scare_data)} scare votes")



async def autosave_task():
    """Automatically save all data every 60 seconds."""
    while True:
        save_json(user_data, USER_DATA_FILE)
        save_json(scare_data, SCARE_DATA_FILE)
        await asyncio.sleep(60)










# ======================= ZOMBOARD — THE LAST BROADCAST (Premium Visible + Leaderboard) =======================
# Paste this entire block into spookybot.py under your imports (replace older broadcast / last_broadcast module).
# Then register handlers with app.add_handler(...) as shown at the bottom.
# =====================================================================================

# ---------- CONFIG ----------
BROADCAST_COOLDOWN_PREMIUM = timedelta(seconds=30)   # premium cooldown (testing)
BROADCAST_COOLDOWN_REGULAR = timedelta(seconds=90)   # regular cooldown (testing)
BROADCAST_SAVE_KEY = "broadcast_state"
BROADCAST_FILE_FALLBACK = "user_data.json"           # fallback file if save_user_data missing
BROADCAST_LEADERBOARD_FILE = "broadcast_leaderboard.json"  # zomboard persistent file

# ---------- IN-MEMORY ----------
BROADCAST_COOLDOWNS = {}         # uid -> datetime
broadcast_leaderboard = {}       # uid -> {"survivors": int, "wins": int, "username": str, "premium": bool}

# ---------- SAFE WRAPPERS ----------
def safe_load_user_data():
    global user_data
    try:
        _ = user_data
    except NameError:
        # fallback read
        if os.path.exists(BROADCAST_FILE_FALLBACK):
            try:
                with open(BROADCAST_FILE_FALLBACK, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
            except Exception:
                user_data = {}
        else:
            user_data = {}

def safe_save_user_data():
    try:
        save_user_data()
    except Exception:
        try:
            with open(BROADCAST_FILE_FALLBACK, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Broadcast fallback save error: {e}")

def safe_is_premium_user(user_id):
    """Return True if user is premium (uses existing is_premium_user if available)."""
    try:
        return bool(is_premium_user(str(user_id)))
    except Exception:
        return False

async def safe_auto_voice_message(message_obj, text, caption=None):
    """Call existing auto_voice_message if present; otherwise skip silently."""
    try:
        coro = globals().get("auto_voice_message")
        if callable(coro):
            await coro(message_obj, text, caption or "")
        else:
            return
    except Exception as e:
        print(f"⚠️ auto_voice_message failed or missing: {e}")
        return

# ---------- HELPERS ----------
def clamp_value(v, lo, hi):
    try:
        return max(lo, min(hi, int(v)))
    except Exception:
        try:
            return max(lo, min(hi, v))
        except Exception:
            return lo

def load_broadcast_leaderboard():
    global broadcast_leaderboard
    try:
        if os.path.exists(BROADCAST_LEADERBOARD_FILE):
            with open(BROADCAST_LEADERBOARD_FILE, "r", encoding="utf-8") as f:
                broadcast_leaderboard = json.load(f)
        else:
            broadcast_leaderboard = {}
    except Exception as e:
        print(f"❌ load_broadcast_leaderboard error: {e}")
        broadcast_leaderboard = {}

def save_broadcast_leaderboard():
    try:
        with open(BROADCAST_LEADERBOARD_FILE, "w", encoding="utf-8") as f:
            json.dump(broadcast_leaderboard, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ save_broadcast_leaderboard error: {e}")

def update_broadcast_leaderboard(uid, survivors_gained=0, win=False, username=None, premium=False):
    uid = str(uid)
    if uid not in broadcast_leaderboard:
        broadcast_leaderboard[uid] = {"survivors": 0, "wins": 0, "username": username or str(uid), "premium": bool(premium)}
    broadcast_leaderboard[uid]["survivors"] += survivors_gained
    if win:
        broadcast_leaderboard[uid]["wins"] += 1
    if username:
        broadcast_leaderboard[uid]["username"] = username
    # Keep premium flag visible
    if premium:
        broadcast_leaderboard[uid]["premium"] = True
    save_broadcast_leaderboard()

# load zomboard at import
load_broadcast_leaderboard()

# ---------- BROADCAST STATE ACCESS ----------
def init_broadcast_state(user_id, username=None):
    """Ensure a broadcast state exists for user in user_data; returns the state dict."""
    uid = str(user_id)
    safe_load_user_data()
    if uid not in user_data:
        user_data[uid] = {}
    if BROADCAST_SAVE_KEY not in user_data[uid]:
        user_data[uid][BROADCAST_SAVE_KEY] = {
            "status": "idle",          # idle | active | lost | won
            "power": 10,
            "hope": 5,
            "survivors": 0,
            "zombie_threat": 0,
            "turn": 0,
            "last_broadcast_at": None,
            "station": "Ravenwood Radio",
            "username": username or user_data[uid].get("first_name", "DJ"),
            # internal metadata:
            "_uid": uid,
            "_premium": safe_is_premium_user(uid)
        }
        safe_save_user_data()
    # ensure metadata exists
    state = user_data[uid][BROADCAST_SAVE_KEY]
    state["_uid"] = uid
    # update premium flag every init (so changes to premium status reflect)
    state["_premium"] = safe_is_premium_user(uid)
    return state

def reset_broadcast_state(uid):
    uid = str(uid)
    safe_load_user_data()
    if uid in user_data and BROADCAST_SAVE_KEY in user_data[uid]:
        del user_data[uid][BROADCAST_SAVE_KEY]
    safe_save_user_data()

def broadcast_can_play(uid):
    uid = str(uid)
    next_time = BROADCAST_COOLDOWNS.get(uid)
    now = datetime.utcnow()
    if not next_time or now >= next_time:
        return True, None
    else:
        remain = (next_time - now).total_seconds()
        return False, int(remain)

def set_broadcast_cooldown(uid, premium=False):
    uid = str(uid)
    now = datetime.utcnow()
    cd = BROADCAST_COOLDOWN_PREMIUM if premium else BROADCAST_COOLDOWN_REGULAR
    BROADCAST_COOLDOWNS[uid] = now + cd

def fmt_state_header(state):
    """Return header lines; premium shows special emoji and header."""
    name = state.get("username", "Player")
    premium = bool(state.get("_premium", False))
    radio_emoji = "🎙️" if premium else "📻"
    header_title = "💎 PREMIUM TRANSMISSION 💎" if premium else "📻 THE LAST BROADCAST"
    lines = []
    lines.append(f"{header_title} {radio_emoji}")
    lines.append(f"{name}, you broadcast from the station in {state.get('station', 'Ravenwood')}. Turn {state.get('turn', 0)}.")
    lines.append(f"Power: {state.get('power',0)} | Hope: {state.get('hope',0)} | Survivors: {state.get('survivors',0)} | Zombie Threat: {state.get('zombie_threat',0)}")
    lines.append("")
    return "\n".join(lines)

# ---------- TURN / EVENT LOGIC (with premium perks) ----------
def run_broadcast_turn(state):
    """
    Advance one turn with premium-visible perks:
    - Premium: +1 Hope after broadcast, higher loot chance, threat resistance, premium flavor text
    Returns narration, voice_line, game_over, outcome
    """
    state["turn"] = state.get("turn", 0) + 1
    premium = bool(state.get("_premium", False))
    uid = state.get("_uid")

    p = random.random()
    narration = ""
    voice = ""

    # passive power drain (same both)
    power_drain = 1
    state["power"] = max(0, state.get("power", 0) - power_drain)

    # chance weights slightly better for premium
    premium_loot_chance = 0.30 if premium else 0.10
    # threat resistance reduces incoming threat by 1 if premium (applied when zombies increase)

    # main branches
    if p < 0.22 + (0.05 if premium else 0.0):
        # found survivor
        state["survivors"] = state.get("survivors", 0) + 1
        narration = "A survivor's voice crackles through: 'I'm alive!'"
        voice = narration
        state["hope"] = min(99, state.get("hope", 0) + 1)
        # immediate leaderboard update for new survivor
        update_broadcast_leaderboard(uid, survivors_gained=1, username=state.get("username"), premium=premium)
    elif p < 0.44:
        # zombie activity
        increase = random.randint(1, 3)
        if premium:
            increase = max(0, increase - 1)  # premium reduces the threat increase by 1
        state["zombie_threat"] = state.get("zombie_threat", 0) + increase
        narration = "Zombies claw at the barricades, drawn by your signal!"
        voice = narration + f" Strange Signal: \"They hunger, {state.get('username','DJ')}...\""
        state["hope"] = max(0, state.get("hope", 0) - 1)
    elif p < 0.66:
        # find fuel/power (premium increases chance of extra battery)
        found = random.choice(["spare fuel for the generator", "a battery pack"])
        gained = random.randint(1, 3)
        # premium: occasionally get signal battery +2 extra
        if premium and random.random() < premium_loot_chance:
            gained += 2
            narration = f"Found {found} and a Signal Battery 🔋! (Premium boost)"
        else:
            narration = f"Found {found} for the generator!"
        state["power"] = min(99, state.get("power", 0) + gained)
        voice = narration
    elif p < 0.86:
        # creepy signal affects hope
        signal = random.choice([
            "Your shadow moves alone.",
            "They sing your name in reverse.",
            "Static says: 'Do not answer.'",
            "A child's whisper: 'Stay away.'"
        ])
        narration = f"Strange Signal: \"{signal}\""
        voice = narration
        state["hope"] = clamp_value(state.get("hope", 0) + random.choice([-1, 0, 1]), 0, 99)
    else:
        # quiet small find; premium gives extra hope
        narration = "You catch a faint radio diary — someone promises to find you one day."
        voice = narration
        state["hope"] = min(99, state.get("hope", 0) + (2 if premium else 1))

    # premium passive bonus: grant +1 Hope after each successful broadcast (visible)
    if premium:
        state["hope"] = min(99, state.get("hope", 0) + 1)
        # visible note will be appended to narration later

    # clamp values
    state["power"] = clamp_value(state.get("power", 0), 0, 99)
    state["hope"] = clamp_value(state.get("hope", 0), 0, 99)
    state["zombie_threat"] = clamp_value(state.get("zombie_threat", 0), 0, 99)

    # check lose/win
    game_over = False
    outcome = None
    if state.get("zombie_threat", 0) >= 10 or (state.get("power", 0) <= 0 and state.get("zombie_threat",0) > 5):
        state["status"] = "lost"
        game_over = True
        outcome = "lost"
        narration += "\n\nThe barricades break. The station is overrun..."
        voice = (voice + " " if voice else "") + "The scream is long and wet."
    elif state.get("survivors", 0) >= 5:
        state["status"] = "won"
        game_over = True
        outcome = "won"
        narration += "\n\nYou saved enough survivors. The town will remember you."
        voice = (voice + " " if voice else "") + "A chorus of whispers thanks you."
        # record win on zomboard
        update_broadcast_leaderboard(state.get("_uid"), survivors_gained=0, win=True, username=state.get("username"), premium=premium)

    # add premium note
    if premium:
        narration = f"✨ Premium signal active! Hope +1, Threat resistance engaged.\n\n{narration}"

    return narration, voice, game_over, outcome

# ---------- COMMANDS ----------
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    safe_load_user_data()
    state = init_broadcast_state(uid, username=user.first_name)

    # attach metadata
    state["_uid"] = uid
    state["_premium"] = safe_is_premium_user(uid)
    premium = bool(state["_premium"])

    can_play, remain = broadcast_can_play(uid)
    if not can_play:
        await update.message.reply_text(f"⏳ Wait {remain}s before broadcasting again.")
        return

    # activate or reset
    if state["status"] in ("idle", "lost", "won"):
        if state["status"] in ("lost", "won"):
            username = state.get("username", user.first_name)
            station = state.get("station", "Ravenwood Radio")
            # reset keeping username and station
            state.clear()
            state.update({
                "status": "active",
                "power": 10,
                "hope": 5,
                "survivors": 0,
                "zombie_threat": 0,
                "turn": 0,
                "last_broadcast_at": None,
                "station": station,
                "username": username,
                "_uid": uid,
                "_premium": premium
            })
        else:
            state["status"] = "active"

    narration, voice, game_over, outcome = run_broadcast_turn(state)
    state["last_broadcast_at"] = datetime.utcnow().isoformat()
    safe_save_user_data()

    # set cooldown using current premium flag
    set_broadcast_cooldown(uid, premium=premium)

    # header + actions
    header = fmt_state_header(state)
    actions = (
        "🎤 /broadcast - Send another signal\n"
        "🛡️ /fortify - Spend 2 Hope to reduce Zombie Threat\n"
        "🛠️ /scavenge - Risk to search for fuel/hope (costs Power)\n"
        "😱 /panic - Sacrifice 1 Survivor to reduce Zombie Threat by 3 (desperate)\n"
        "🏃 /end_broadcast - Abandon the station"
        "🏃 /broadcast_leaderboard - Check you and ur freinds status"
    )
    message_text = header + "\n" + narration + "\n\n" + actions

    # visible premium line if premium
    if premium:
        message_text = f"💎 PREMIUM: You feel the radio hum stronger.\n\n{message_text}"

    await update.message.reply_text(escape_markdown(message_text, version=2), parse_mode="MarkdownV2")

    # voice narration attempt
    try:
        if voice:
            await safe_auto_voice_message(update.message, f"{state.get('username','DJ')}, {voice}", caption="Voice narration")
    except Exception:
        pass

    if game_over:
        if outcome == "lost":
            await update.message.reply_text("💀 *Game Over* — The station was overrun. Use /broadcast to start again.", parse_mode="Markdown")
        elif outcome == "won":
            # update leaderboard survivors with final survivors count
            update_broadcast_leaderboard(uid, survivors_gained=state.get("survivors",0), win=True, username=state.get("username"), premium=premium)
            await update.message.reply_text("🏆 *Victory!* You saved the town. Use /broadcast to play again.", parse_mode="Markdown")
        safe_save_user_data()

async def fortify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    safe_load_user_data()
    state = init_broadcast_state(uid, username=user.first_name)
    if state.get("status") != "active":
        await update.message.reply_text("No active broadcast. Use /broadcast to start.")
        return
    if state.get("hope", 0) < 2:
        await update.message.reply_text("Not enough Hope to fortify. You need 2 Hope.")
        return
    state["hope"] = max(0, state.get("hope", 0) - 2)
    state["zombie_threat"] = max(0, state.get("zombie_threat", 0) - 1)
    safe_save_user_data()
    await update.message.reply_text(f"🛡️ You nail boards over the doors. Zombie Threat reduced to {state['zombie_threat']}!")
    try:
        await safe_auto_voice_message(update.message, f"You fortify the station. Threat: {state['zombie_threat']}", caption="Fortify")
    except Exception:
        pass

async def end_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    safe_load_user_data()
    state = init_broadcast_state(uid, username=user.first_name)
    if state.get("status") != "active":
        await update.message.reply_text("No active broadcast to abandon.")
        return
    state["status"] = "idle"
    safe_save_user_data()
    await update.message.reply_text("🏃 You abandon the station. The signal goes silent. Use /broadcast to start again.")

async def broadcast_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    safe_load_user_data()
    state = init_broadcast_state(uid, username=user.first_name)
    header = fmt_state_header(state)
    status_line = f"\n*Status:* {state.get('status')}\nTurn: {state.get('turn')}\n"
    await update.message.reply_text(header + status_line, parse_mode="Markdown")

# ---------- SCAVENGE & PANIC (same logic, keep premium effects) ----------
async def scavenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    safe_load_user_data()
    state = init_broadcast_state(uid, username=user.first_name)
    premium = bool(state.get("_premium", False))
    if state.get("status") != "active":
        await update.message.reply_text("No active broadcast. Use /broadcast to start.")
        return
    cost = random.randint(1, 3)
    if state.get("power", 0) < cost:
        await update.message.reply_text(f"Not enough Power to scavenge (need {cost}).")
        return
    state["power"] = max(0, state.get("power", 0) - cost)
    p = random.random()
    result_text = ""
    if p < 0.35 + (0.10 if premium else 0.0):
        found = random.choice(["spare fuel", "battery pack"])
        state["power"] = min(99, state.get("power", 0) + random.randint(1, 3) + (1 if premium else 0))
        state["hope"] = min(99, state.get("hope", 0) + 1 + (1 if premium else 0))
        result_text = f"You scavenge and find {found}. Power and Hope improved. (Premium bonus applied)" if premium else f"You scavenge and find {found}. Power and Hope improved."
        if random.random() < 0.25:
            # rare instant survivor
            state["survivors"] += 1
            update_broadcast_leaderboard(uid, survivors_gained=1, username=state.get("username"), premium=premium)
            result_text += " You also rescue a survivor!"
    elif p < 0.6:
        result_text = "You find scrap and memories — not much practical use, but you feel steadier."
    elif p < 0.85:
        state["zombie_threat"] = state.get("zombie_threat", 0) + random.randint(1, 2)
        result_text = "You triggered a small horde while scavenging — Noise attracts the undead!"
    else:
        state["survivors"] = state.get("survivors", 0) + 1
        state["hope"] = min(99, state.get("hope", 0) + 2 + (1 if premium else 0))
        result_text = "You discovered a survivor hiding in a collapsed cellar! You bring them back."
        update_broadcast_leaderboard(uid, survivors_gained=1, username=state.get("username"), premium=premium)
    state["power"] = clamp_value(state.get("power", 0), 0, 99)
    state["zombie_threat"] = clamp_value(state.get("zombie_threat", 0), 0, 99)
    safe_save_user_data()
    await update.message.reply_text(f"🧭 Scavenge result: {result_text}")

async def panic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = str(user.id)
    safe_load_user_data()
    state = init_broadcast_state(uid, username=user.first_name)
    if state.get("status") != "active":
        await update.message.reply_text("No active broadcast. Use /broadcast to start.")
        return
    if state.get("survivors", 0) < 1:
        await update.message.reply_text("No survivors available to sacrifice. Panic not possible.")
        return
    # sacrifice one survivor -> reduce threat by 3, reduce hope more, cost power
    state["survivors"] -= 1
    reduction = random.randint(2, 4)
    state["zombie_threat"] = max(0, state.get("zombie_threat", 0) - reduction)
    state["hope"] = max(0, state.get("hope", 0) - 3)
    state["power"] = max(0, state.get("power", 0) - 1)
    safe_save_user_data()
    await update.message.reply_text(f"😱 *Panic!* You sacrifice one survivor. Zombie Threat reduced by {reduction}.", parse_mode="Markdown")

# ---------- ZOMBOARD display ----------
async def broadcast_leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    load_broadcast_leaderboard()
    if not broadcast_leaderboard:
        await update.message.reply_text("No broadcast leaderboard data yet.")
        return
    sorted_lb = sorted(broadcast_leaderboard.items(), key=lambda x: (x[1].get("survivors",0), x[1].get("wins",0)), reverse=True)[:20]
    text = "📻 *ZOMBOARD — BROADCAST LEADERBOARD*\n\n"
    medals = ["🥇","🥈","🥉"]
    for i, (uid, data) in enumerate(sorted_lb):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = data.get("username","User")
        crown = " 👑" if data.get("premium") else ""
        text += f"{medal} *{name}*{crown} — Survivors: {data.get('survivors',0)} | Wins: {data.get('wins',0)}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# ---------- ADMIN SESSIONS ----------
async def admin_broadcast_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = "7351537370"
    user = update.effective_user
    if str(user.id) != admin_id:
        await update.message.reply_text("Admin only.")
        return
    safe_load_user_data()
    text = "📻 *Broadcast Sessions*\n\n"
    found = False
    for uid, data in user_data.items():
        state = data.get(BROADCAST_SAVE_KEY)
        if state:
            found = True
            text += f"`{uid}` — {state.get('username','User')} | status:{state.get('status')} | survivors:{state.get('survivors')}\n"
    if not found:
        text += "No active broadcast sessions found."
    await update.message.reply_text(text, parse_mode="Markdown")




# ===== MAIN BOT SETUP =====
# In your main() function, add these missing handlers:

def main():
    """Start the bot"""
    print("-> Starting SpookyBot with COMPLETE RPG SYSTEM...")

    try:
        # ✅ Load data BEFORE building or running handlers
        load_user_data()
        load_group_leaderboard()
        load_scare_cooldowns()
        load_rpg_leaderboard()
        load_cooldowns()
         #asyncio.create_task(periodic_autosave())
        # ===== CREATE APP =====
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        app = Application.builder().token(TELEGRAM_TOKEN).job_queue(JobQueue()).build()
        job_queue = Application.job_queue
        job_queue = app.job_queue
        print("[Init] JobQueue started successfully")
        # ===== PAYMENT HANDLERS =====
        app.add_handler(PreCheckoutQueryHandler(handle_pre_checkout))
        app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment))
        
        # ===== COMMAND HANDLERS =====
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("premium", premium_command))
        app.add_handler(CommandHandler("story", story_command))
        app.add_handler(CommandHandler("menu", menu_command))
        app.add_handler(CommandHandler("save", save_command))
        app.add_handler(CommandHandler("mystats", stats_command))
        app.add_handler(CommandHandler("leader", announce_winner))
        app.add_handler(CommandHandler("gwt_help", gwt_help))
        app.add_handler(CommandHandler("gwt_resolve", gwt_resolve_command))
        app.add_handler(CommandHandler("join_ghosts", join_team_command))
        app.add_handler(CommandHandler("join_zombies", join_team_command))
        # ===== SUPPORT COMMANDS =====
        app.add_handler(CommandHandler("support", support_command))
        app.add_handler(CommandHandler("bugreport", bugreport_command))
        app.add_handler(CommandHandler("featurerequest", featurerequest_command))
        
        # ===== GROUP SCARE COMMANDS =====
        app.add_handler(CommandHandler("scareboard", scare_leaderboard))
        app.add_handler(CommandHandler("dailyscare", daily_scare_challenge))
        app.add_handler(CommandHandler("addscare", add_scare_points))
        app.add_handler(CommandHandler("treat", treat_command))
        app.add_handler(CommandHandler("force_event", force_event_command))


        app.add_handler(CommandHandler("spookyfight", spookyfight_command))
        # ===== ACHIEVEMENT COMMANDS =====
        app.add_handler(CommandHandler("mytier", my_tier))
        app.add_handler(CommandHandler("myachievements", my_achievements))
        
        # ===== TRANSFORMATION COMMANDS =====
        app.add_handler(CommandHandler("creepify", creepify_command))
        app.add_handler(CommandHandler("gothic", gothic_command))
        app.add_handler(CommandHandler("monster", monster_command))
        app.add_handler(CommandHandler("ghost", ghost_command))
        app.add_handler(CommandHandler("zombie", zombie_command))
        app.add_handler(CommandHandler("eldritch", eldritch_command))
        app.add_handler(CommandHandler("werewolf", werewolf_command))
        app.add_handler(CommandHandler("demon", demon_command))
        app.add_handler(CommandHandler("witch", witch_command))
        app.add_handler(CommandHandler("custom", custom_command))
        
        #zombie game
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        app.add_handler(CommandHandler("fortify", fortify_command))
        app.add_handler(CommandHandler("end_broadcast", end_broadcast_command))
        app.add_handler(CommandHandler("broadcast_status", broadcast_status_command))
        app.add_handler(CommandHandler("scavenge", scavenge_command))
        app.add_handler(CommandHandler("panic", panic_command))
        app.add_handler(CommandHandler("broadcast_leaderboard", broadcast_leaderboard_command))
        app.add_handler(CommandHandler("admin_broadcast_list", admin_broadcast_list))




        # ===== RPG COMMANDS =====
        app.add_handler(CommandHandler("games", games_panel))


        # ===== MONSTER COMMANDS =====
        app.add_handler(CommandHandler("createmonster", create_monster))
        app.add_handler(CommandHandler("monsterstory", monster_story))
        
        # ===== OTHER COMMANDS =====
        app.add_handler(CommandHandler("horrorsound", horror_sound_command))
        app.add_handler(CommandHandler("horrorfact", horrorfact_command))
        app.add_handler(CommandHandler("halloweencountdown", halloweencountdown_command))
        app.add_handler(CommandHandler("scareme", scareme_command))
        app.add_handler(CommandHandler("summon", summon_user))
        app.add_handler(CommandHandler("curse", curse_command))
        app.add_handler(CommandHandler("spooky", spooky_chat_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("ultimate_blast", action_command))
        app.add_handler(CommandHandler("steal_health", action_command))
        app.add_handler(CommandHandler("help_move", help_move))
        app.add_handler(CommandHandler("dark_pulse", action_command))
        app.add_handler(CommandHandler("hex_curse", action_command))
        app.add_handler(CommandHandler("spectral_rush", action_command))
        app.add_handler(CommandHandler("fear_aura", action_command))
        app.add_handler(CommandHandler("grave_pact", action_command))
        app.add_handler(CommandHandler("phantom_strike", action_command))
        app.add_handler(CommandHandler("doom_shroud", action_command))
        app.add_handler(CommandHandler("blood_surge", action_command))
        app.add_handler(CommandHandler("ghostly_swap", action_command))
        app.add_handler(CommandHandler("reaper_call", action_command))
        app.add_handler(CommandHandler("shadow_bolt", action_command))
        app.add_handler(CommandHandler("vile_mist", action_command))
        app.add_handler(CommandHandler("spirit_siphon", action_command))
        app.add_handler(CommandHandler("dread_echo", action_command))
        app.add_handler(CommandHandler("haunted_mark", action_command))
        app.add_handler(CommandHandler("chill_touch", action_command))
        app.add_handler(CommandHandler("spirit_burst", action_command))



        app.add_handler(CommandHandler("join_ghosts", join_team_command))
        app.add_handler(CommandHandler("start_battle", start_battle))
        app.add_handler(CommandHandler("join_zombies", join_team_command))
        app.add_handler(CommandHandler("haunt", action_command))
        app.add_handler(CommandHandler("infect", action_command))
        app.add_handler(CommandHandler("revive", action_command))
        app.add_handler(CommandHandler("shield", action_command))
        app.add_handler(CommandHandler("battle_status", battle_status))
        app.add_handler(CommandHandler("end_battle", end_battle))
        app.add_handler(CommandHandler("gwt_start", gwt_start))
        app.add_handler(CommandHandler("tictactoe", tictactoe_start))
        app.add_handler(CommandHandler("tictactoe_help", tictactoe_help))
        app.add_handler(CommandHandler("attack_reaper", action_command))
        app.add_handler(CommandHandler("battle_status", battle_status))
        app.add_handler(CommandHandler("end_battle", end_battle))
        app.add_handler(CommandHandler("transform", transform_panel))

        # 🧮 Leaderboard and History (view-only)
        app.add_handler(CommandHandler("leaderboard", leaderboard_command))
        app.add_handler(CommandHandler("battle_history", battle_history_command))

        #WEREWOLF GAME
        app.add_handler(CommandHandler("werewolf_start", werewolf_start))
        app.add_handler(CommandHandler("vote", werewolf_vote))
        app.add_handler(CommandHandler("werewolf_help", werewolf_help))
        app.add_handler(CommandHandler("werewolf_cancel", werewolf_cancel_game))


        app.add_handler(CommandHandler("ghoststory", ghoststory_start))
        app.add_handler(MessageHandler(filters.REPLY & filters.ChatType.GROUPS, ghoststory_add))        
        # ===== ADMIN COMMANDS =====
        app.add_handler(CommandHandler("admin", admin_command))
        app.add_handler(CommandHandler("admin_stats", admin_stats))
        app.add_handler(CommandHandler("admin_reset", admin_reset))
        app.add_handler(CommandHandler("admin_premium", admin_premium))
        app.add_handler(CommandHandler("admin_unlock", admin_unlock))
        app.add_handler(CommandHandler("admin_broadcast", admin_broadcast))
        app.add_handler(CommandHandler("admin_reset_leaderboard", admin_reset_leaderboard))
        app.add_handler(CommandHandler("admin_users", admin_users))
        app.add_handler(CommandHandler("admin_users_compact", admin_users_compact))
        app.add_handler(CommandHandler("find_user", admin_find_user))
        app.add_handler(CommandHandler("fix_date_error", admin_fix_date_error))        # ===== CALLBACK HANDLERS =====
        app.add_handler(CallbackQueryHandler(universal_button_handler))
        # ===== LINK REMOVAL HANDLER =====
        app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, delete_links))
        app.add_handler(MessageHandler(filters.CAPTION & filters.ChatType.GROUPS, delete_links))
       
        # ===== MESSAGE HANDLERS =====
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_message))
        app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, goodbye_message))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_links))
        async def periodic_autosave():
            while True:
                await asyncio.sleep(600)  # 5 minutes
                print("🔄 Periodic auto-save...")
                smart_save()

        async def autosave_callback(context: ContextTypes.DEFAULT_TYPE):
            save_user_data()
            save_group_leaderboard()
            save_scare_cooldowns()
            load_cooldowns()
            print("🔄 Auto-save done")

        # FIXED: Schedule it with job_queue (runs forever in background, no event loop issues)
        job_queue.run_repeating(autosave_callback, interval=600, first=10)  # First in 10s, then every 5 min

        print("-> Bot started with ACHIEVEMENT SYSTEM! 🏅")
        app.run_polling()

        executor.shutdown(wait=True)

    except Exception as e:
        print(f"-> Bot error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

