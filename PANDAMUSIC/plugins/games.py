# ---------------------------------------------------------------
# PANDAMUSIC — games.py (family-friendly)
# Economy / Friendship / RPG / Fun
# ---------------------------------------------------------------

print("[games] loading plugin...", flush=True)

import json
import os
import random
import time

from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import bot, cdx, rgx, console
from .maintenance import block_if_maintenance, block_cb_if_maintenance

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DB = os.path.join(_BASE, "games_db.json")

SHOP = {
    "sword": {"price": 1500, "name": "⚔️ Sword", "atk": 15},
    "shield": {"price": 1200, "name": "🛡️ Shield", "def": 12},
    "armor": {"price": 2000, "name": "🥋 Armor", "def": 20},
    "potion": {"price": 500, "name": "🧪 Potion", "heal": 50},
    "boots": {"price": 800, "name": "👢 Boots", "spd": 10},
}

RIDDLES = [
    ("I have cities but no houses, forests but no trees, water but no fish. What am I?", "map"),
    ("What has keys but can't open locks?", "piano"),
    ("What gets wetter the more it dries?", "towel"),
    ("What has a head and a tail but no body?", "coin"),
    ("What can travel around the world while staying in a corner?", "stamp"),
    ("What has hands but cannot clap?", "clock"),
]


def _load() -> dict:
    try:
        if os.path.exists(_DB):
            with open(_DB, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"users": {}, "friends": {}}


def _save(data: dict):
    try:
        with open(_DB, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[games] save error: {e}", flush=True)


def _uid(u) -> str:
    return str(u)


def _user(data: dict, user_id: int) -> dict:
    key = _uid(user_id)
    if key not in data["users"]:
        data["users"][key] = {
            "coins": 1000,
            "bank": 0,
            "xp": 0,
            "wins": 0,
            "losses": 0,
            "inventory": {},
            "hp": 100,
            "last_daily": 0,
            "streak": 0,
            "last_claim": 0,
            "protect_until": 0,
            "alive": True,
            "last_kill": 0,
            "last_rob": 0,
        }
    u = data["users"][key]
    u.setdefault("coins", 1000)
    u.setdefault("inventory", {})
    u.setdefault("hp", 100)
    u.setdefault("alive", True)
    u.setdefault("protect_until", 0)
    u.setdefault("wins", 0)
    u.setdefault("losses", 0)
    u.setdefault("xp", 0)
    u.setdefault("streak", 0)
    u.setdefault("last_daily", 0)
    u.setdefault("last_claim", 0)
    u.setdefault("last_kill", 0)
    u.setdefault("last_rob", 0)
    return u


def _name(user) -> str:
    return (user.first_name or "User").replace("<", "").replace(">", "")


def _mention(user) -> str:
    return f'<a href="tg://user?id={user.id}">{_name(user)}</a>'


async def _target_user(client, message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if message.command and len(message.command) > 1:
        try:
            return await client.get_users(message.command[1])
        except Exception:
            return None
    return None


def _btn(text, **kwargs):
    return InlineKeyboardButton(text, **kwargs)


def games_menu_markup():
    return InlineKeyboardMarkup(
        [
            [
                _btn("💍 Social", callback_data="games_social"),
                _btn("💰 Economy", callback_data="games_economy"),
            ],
            [
                _btn("⚔️ RPG", callback_data="games_rpg"),
                _btn("🧠 AI & Fun", callback_data="games_fun"),
            ],
            [
                _btn("⬅️ Back", callback_data="help_menu"),
            ],
        ]
    )


def games_back_markup():
    return InlineKeyboardMarkup(
        [
            [
                _btn("🎮 Games", callback_data="games_menu"),
                _btn("⬅️ Help", callback_data="help_menu"),
            ]
        ]
    )


# ── Menu callbacks ─────────────────────────────────────────────

@bot.on_callback_query(rgx("games_menu"))
async def games_menu_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    text = (
        "<b>🎮 GAMES MENU</b>\n\n"
        "Pick a category below.\n"
        "All games use virtual coins — fun only, no real money."
    )
    try:
        await query.message.edit_text(text, reply_markup=games_menu_markup(), parse_mode=ParseMode.HTML)
    except Exception:
        try:
            await query.message.edit_caption(caption=text, reply_markup=games_menu_markup(), parse_mode=ParseMode.HTML)
        except Exception:
            pass
    await query.answer()


@bot.on_callback_query(rgx("games_social"))
async def games_social_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    text = (
        "<b>💍 Social & Friends</b>\n\n"
        "<b>/friend @user</b>\n↳ Send a friend request / add friend.\n\n"
        "<b>/friends</b>\n↳ See your friends list.\n\n"
        "<b>/unfriend @user</b>\n↳ Remove a friend.\n\n"
        "<b>/buddy</b>\n↳ Random buddy match suggestion."
    )
    try:
        await query.message.edit_text(text, reply_markup=games_back_markup(), parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await query.answer()


@bot.on_callback_query(rgx("games_economy"))
async def games_economy_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    text = (
        "<b>💰 Economy & Shop</b>\n\n"
        "<b>/bal</b> — Own wallet\n"
        "<b>/bal @user</b> or reply — See their wallet\n"
        "<b>/shop</b> — Buy items\n"
        "<b>/buy [item]</b> — Purchase from shop\n"
        "<b>/give [amt] @user</b> — Transfer (10% tax)\n"
        "<b>/claim</b> — Group bonus (2k)\n"
        "<b>/daily</b> — Daily streak rewards\n"
        "<b>/ranking</b> — Top richest players"
    )
    try:
        await query.message.edit_text(text, reply_markup=games_back_markup(), parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await query.answer()


@bot.on_callback_query(rgx("games_rpg"))
async def games_rpg_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    text = (
        "<b>⚔️ RPG & Battle</b>\n\n"
        "<b>/kill</b> (reply)\n↳ Game KO + random loot\n\n"
        "<b>/battle @user</b>\n↳ Friendly duel. Winner gains coins & XP!\n\n"
        "<b>/rob [amt]</b> reply or <b>/rob [amt] @user</b>\n↳ Steal up to their balance (risk of fail)\n\n"
        "<b>/protect</b>\n↳ Buy 24h shield (800 coins).\n\n"
        "<b>/revive</b>\n↳ Restore HP for 500 coins."
    )
    try:
        await query.message.edit_text(text, reply_markup=games_back_markup(), parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await query.answer()


@bot.on_callback_query(rgx("games_fun"))
async def games_fun_cb(client, query):
    if await block_cb_if_maintenance(query):
        return
    text = (
        "<b>🧠 AI & Fun</b>\n\n"
        "<b>/riddle</b> — Random riddle quiz\n"
        "<b>/dice</b> — Roll a dice\n"
        "<b>/slots</b> — Virtual slot machine\n"
        "<b>/coinflip</b> — Heads or tails\n\n"
        "Chatbot: use <b>/chaton</b> from Help menu."
    )
    try:
        await query.message.edit_text(text, reply_markup=games_back_markup(), parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await query.answer()


# ── Economy ────────────────────────────────────────────────────

@bot.on_message(cdx(["bal", "balance", "wallet"]))
async def bal_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return

    # own / reply / @user
    target = message.from_user
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    elif message.command and len(message.command) > 1:
        try:
            target = await client.get_users(message.command[1])
        except Exception:
            return await message.reply_text("❌ User not found.")

    if target.is_bot:
        return await message.reply_text("❌ Bots have no wallet.")

    data = _load()
    u = _user(data, target.id)
    _save(data)

    inv = u.get("inventory") or {}
    inv_txt = ", ".join(f"{k} x{v}" for k, v in inv.items()) if inv else "Empty"
    prot = "✅ Active" if u.get("protect_until", 0) > time.time() else "❌ None"
    whose = "Your" if target.id == message.from_user.id else _name(target) + "'s"

    text = (
        f"💰 <b>{whose} Balance — {_mention(target)}</b>\n\n"
        f"🪙 Coins: <code>{u['coins']:,}</code>\n"
        f"⭐ XP: <code>{u['xp']:,}</code>\n"
        f"❤️ HP: <code>{u['hp']}</code>\n"
        f"🛡️ Protect: {prot}\n"
        f"🏆 Wins: {u['wins']} | Losses: {u['losses']}\n"
        f"🔥 Daily streak: {u.get('streak', 0)}\n"
        f"🎒 Inventory: {inv_txt}"
    )
    await message.reply_text(text, parse_mode=ParseMode.HTML)


@bot.on_message(cdx("shop"))
async def shop_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    lines = ["🛒 <b>SHOP</b>\n", "Use <code>/buy itemname</code>\n"]
    for key, item in SHOP.items():
        lines.append(f"• <b>{item['name']}</b> (<code>{key}</code>) — {item['price']:,} coins")
    await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@bot.on_message(cdx("buy"))
async def buy_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    if len(message.command) < 2:
        return await message.reply_text("Usage: <code>/buy sword</code>", parse_mode=ParseMode.HTML)
    item_key = message.command[1].lower().strip()
    if item_key not in SHOP:
        return await message.reply_text("❌ Item not found. Use /shop")
    data = _load()
    u = _user(data, message.from_user.id)
    price = SHOP[item_key]["price"]
    if u["coins"] < price:
        return await message.reply_text(f"❌ Not enough coins. Need {price:,}.")
    u["coins"] -= price
    inv = u.setdefault("inventory", {})
    inv[item_key] = inv.get(item_key, 0) + 1
    _save(data)
    await message.reply_text(
        f"✅ Bought <b>{SHOP[item_key]['name']}</b> for {price:,} coins!",
        parse_mode=ParseMode.HTML,
    )


@bot.on_message(cdx(["give", "pay", "transfer"]))
async def give_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    if len(message.command) < 2:
        return await message.reply_text("Usage: <code>/give 100 @user</code> or reply with /give 100", parse_mode=ParseMode.HTML)
    try:
        amount = int(message.command[1].replace(",", ""))
    except ValueError:
        return await message.reply_text("❌ Invalid amount.")
    if amount <= 0:
        return await message.reply_text("❌ Amount must be positive.")

    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    elif len(message.command) > 2:
        try:
            target = await client.get_users(message.command[2])
        except Exception:
            target = None
    if not target:
        return await message.reply_text("❌ Reply to a user or mention them.")
    if target.id == message.from_user.id:
        return await message.reply_text("❌ You cannot give coins to yourself.")
    if target.is_bot:
        return await message.reply_text("❌ Cannot give to bots.")

    data = _load()
    sender = _user(data, message.from_user.id)
    receiver = _user(data, target.id)
    tax = max(1, int(amount * 0.10))
    total = amount + tax
    if sender["coins"] < total:
        return await message.reply_text(f"❌ Need {total:,} (amount + 10% tax). You have {sender['coins']:,}.")
    sender["coins"] -= total
    receiver["coins"] += amount
    _save(data)
    await message.reply_text(
        f"✅ {_mention(message.from_user)} sent <b>{amount:,}</b> coins to {_mention(target)}\n"
        f"💸 Tax: {tax:,}",
        parse_mode=ParseMode.HTML,
    )


@bot.on_message(cdx("daily"))
async def daily_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    data = _load()
    u = _user(data, message.from_user.id)
    now = time.time()
    last = float(u.get("last_daily") or 0)
    if now - last < 86400:
        left = int(86400 - (now - last))
        h, m = divmod(left // 60, 60)
        return await message.reply_text(f"⏳ Daily already claimed. Next in {h}h {m}m.")
    if now - last < 172800:
        u["streak"] = int(u.get("streak") or 0) + 1
    else:
        u["streak"] = 1
    reward = 500 + (u["streak"] * 50)
    reward = min(reward, 2000)
    u["coins"] += reward
    u["xp"] += 10
    u["last_daily"] = now
    _save(data)
    await message.reply_text(
        f"🎁 <b>Daily claimed!</b>\n🪙 +{reward:,} coins\n🔥 Streak: {u['streak']}\n⭐ +10 XP",
        parse_mode=ParseMode.HTML,
    )


@bot.on_message(cdx("claim"))
async def claim_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    if message.chat.type.name == "PRIVATE":
        return await message.reply_text("❌ /claim only works in groups.")
    data = _load()
    u = _user(data, message.from_user.id)
    now = time.time()
    last = float(u.get("last_claim") or 0)
    if now - last < 3600:
        left = int(3600 - (now - last))
        return await message.reply_text(f"⏳ Claim cooldown: {left // 60}m left.")
    reward = 2000
    u["coins"] += reward
    u["last_claim"] = now
    _save(data)
    await message.reply_text(
        f"🎉 Group bonus claimed! +<b>{reward:,}</b> coins",
        parse_mode=ParseMode.HTML,
    )


@bot.on_message(cdx(["ranking", "rich", "top"]))
async def ranking_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    data = _load()
    users = data.get("users") or {}
    ranked = sorted(users.items(), key=lambda x: int(x[1].get("coins", 0)), reverse=True)[:10]
    if not ranked:
        return await message.reply_text("No players yet.")
    lines = ["🏆 <b>TOP 10 RICHEST</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, u) in enumerate(ranked):
        medal = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} <code>{uid}</code> — {int(u.get('coins', 0)):,} coins")
    await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# ── Friendship ─────────────────────────────────────────────────

@bot.on_message(cdx(["friend", "addfriend"]))
async def friend_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    target = await _target_user(client, message)
    if not target:
        return await message.reply_text("Usage: reply or <code>/friend @user</code>", parse_mode=ParseMode.HTML)
    if target.id == message.from_user.id:
        return await message.reply_text("❌ That's you!")
    if target.is_bot:
        return await message.reply_text("❌ Bots can't be friends.")

    data = _load()
    a, b = sorted([str(message.from_user.id), str(target.id)])
    key = f"{a}:{b}"
    friends = data.setdefault("friends", {})
    if friends.get(key):
        return await message.reply_text("✅ You are already friends!")
    friends[key] = {"since": int(time.time())}
    _save(data)
    await message.reply_text(
        f"🤝 {_mention(message.from_user)} and {_mention(target)} are now friends!",
        parse_mode=ParseMode.HTML,
    )


@bot.on_message(cdx(["unfriend", "removefriend"]))
async def unfriend_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    target = await _target_user(client, message)
    if not target:
        return await message.reply_text("Usage: reply or <code>/unfriend @user</code>", parse_mode=ParseMode.HTML)
    data = _load()
    a, b = sorted([str(message.from_user.id), str(target.id)])
    key = f"{a}:{b}"
    friends = data.setdefault("friends", {})
    if key not in friends:
        return await message.reply_text("❌ You are not friends.")
    del friends[key]
    _save(data)
    await message.reply_text(
        f"👋 Unfriended {_mention(target)}.",
        parse_mode=ParseMode.HTML,
    )


@bot.on_message(cdx(["friends", "friendlist"]))
async def friends_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    data = _load()
    me = str(message.from_user.id)
    friends = data.get("friends") or {}
    ids = []
    for key in friends:
        parts = key.split(":")
        if me in parts:
            other = parts[0] if parts[1] == me else parts[1]
            ids.append(other)
    if not ids:
        return await message.reply_text("🙂 No friends yet. Use /friend @user")
    lines = [f"👥 <b>Friends ({len(ids)})</b>\n"]
    for i, uid in enumerate(ids[:20], 1):
        lines.append(f"{i}. <code>{uid}</code>")
    await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@bot.on_message(cdx(["buddy", "match"]))
async def buddy_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    tips = [
        "Be kind — good friends share /daily rewards vibes!",
        "Team up in /battle for fun practice.",
        "Gift coins with /give to surprise a friend.",
        "Play /slots together and compare luck!",
    ]
    await message.reply_text(
        f"🎲 <b>Buddy tip</b>\n\n{random.choice(tips)}\n\n"
        f"Use <code>/friend @user</code> to add someone!",
        parse_mode=ParseMode.HTML,
    )


# ── RPG ────────────────────────────────────────────────────────

@bot.on_message(cdx("kill"))
async def kill_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return

    if not (message.reply_to_message and message.reply_to_message.from_user):
        return await message.reply_text("Reply to a user with <code>/kill</code>", parse_mode=ParseMode.HTML)

    target = message.reply_to_message.from_user
    killer = message.from_user

    if target.id == killer.id:
        return await message.reply_text("❌ You can't target yourself.")
    if target.is_bot:
        return await message.reply_text("❌ Can't target bots.")

    data = _load()
    k = _user(data, killer.id)
    v = _user(data, target.id)

    now = time.time()
    if now - float(k.get("last_kill") or 0) < 30:
        left = int(30 - (now - float(k["last_kill"])))
        return await message.reply_text(f"⏳ Wait {left}s before next /kill.")

    if not k.get("alive", True):
        return await message.reply_text("💀 You need /revive first!")

    if v.get("protect_until", 0) > now:
        return await message.reply_text("🛡️ Target is protected!")

    if not v.get("alive", True):
        return await message.reply_text("💀 Target already down. They need /revive.")

    if random.random() > 0.55:
        k["last_kill"] = now
        fine = min(k["coins"], random.randint(20, 80))
        k["coins"] -= fine
        _save(data)
        return await message.reply_text(
            f"😅 Missed! {_mention(killer)} failed and lost <b>${fine}</b>",
            parse_mode=ParseMode.HTML,
        )

    loot = random.randint(50, 250)
    loot = min(loot, max(0, v["coins"]))
    v["coins"] = max(0, v["coins"] - loot)
    k["coins"] += loot
    k["xp"] += 10
    k["wins"] += 1
    v["losses"] += 1
    v["hp"] = 0
    v["alive"] = False
    k["last_kill"] = now
    _save(data)

    text = (
        f"📝 {_mention(killer)} kill {_mention(target)}!\n\n"
        f"😈 Killer: {_mention(killer)}\n"
        f"💀 Victim: {_mention(target)}\n"
        f"💵 Loot: ${loot}"
    )
    await message.reply_text(text, parse_mode=ParseMode.HTML)


@bot.on_message(cdx(["battle", "fight", "duel"]))
async def battle_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    target = await _target_user(client, message)
    if not target:
        return await message.reply_text("Usage: reply or <code>/battle @user</code>", parse_mode=ParseMode.HTML)
    if target.id == message.from_user.id:
        return await message.reply_text("❌ Can't battle yourself.")
    if target.is_bot:
        return await message.reply_text("❌ Can't battle bots.")

    data = _load()
    a = _user(data, message.from_user.id)
    b = _user(data, target.id)
    if not a.get("alive", True):
        return await message.reply_text("💀 You need /revive first!")
    if not b.get("alive", True):
        return await message.reply_text("💀 Opponent needs to /revive first.")

    a_roll = random.randint(1, 100) + min(20, a.get("xp", 0) // 50)
    b_roll = random.randint(1, 100) + min(20, b.get("xp", 0) // 50)
    stake = 100

    if a_roll >= b_roll:
        win, lose = a, b
        winner = message.from_user
        a["wins"] += 1
        b["losses"] += 1
    else:
        win, lose = b, a
        winner = target
        b["wins"] += 1
        a["losses"] += 1

    gain = min(stake, lose["coins"])
    lose["coins"] = max(0, lose["coins"] - gain)
    win["coins"] += gain
    win["xp"] += 15
    lose["hp"] = max(0, lose["hp"] - random.randint(5, 20))
    if lose["hp"] <= 0:
        lose["alive"] = False
        lose["hp"] = 0
    _save(data)

    await message.reply_text(
        f"⚔️ <b>BATTLE</b>\n\n"
        f"{_mention(message.from_user)} rolled <b>{a_roll}</b>\n"
        f"{_mention(target)} rolled <b>{b_roll}</b>\n\n"
        f"🏆 Winner: {_mention(winner)} (+{gain} coins, +15 XP)",
        parse_mode=ParseMode.HTML,
    )


@bot.on_message(cdx("rob"))
async def rob_cmd(client, message: Message):
    """
    /rob [amount]  (reply to user)
    /rob [amount] @user
    Max steal = victim ke paas jitna balance hai.
    """
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return

    if len(message.command) < 2:
        return await message.reply_text(
            "Usage:\n"
            "• Reply: <code>/rob 100</code>\n"
            "• Mention: <code>/rob 100 @user</code>",
            parse_mode=ParseMode.HTML,
        )

    try:
        amount = int(str(message.command[1]).replace(",", "").replace("$", ""))
    except ValueError:
        return await message.reply_text("❌ Invalid amount. Example: <code>/rob 100</code>", parse_mode=ParseMode.HTML)

    if amount <= 0:
        return await message.reply_text("❌ Amount must be positive.")

    # target: reply OR @user after amount
    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    elif len(message.command) > 2:
        try:
            target = await client.get_users(message.command[2])
        except Exception:
            target = None

    if not target:
        return await message.reply_text(
            "❌ Reply to a user or use <code>/rob 100 @user</code>",
            parse_mode=ParseMode.HTML,
        )
    if target.id == message.from_user.id:
        return await message.reply_text("❌ You can't rob yourself.")
    if target.is_bot:
        return await message.reply_text("❌ Can't rob bots.")

    data = _load()
    thief = _user(data, message.from_user.id)
    victim = _user(data, target.id)

    now = time.time()
    if now - float(thief.get("last_rob") or 0) < 20:
        left = int(20 - (now - float(thief["last_rob"])))
        return await message.reply_text(f"⏳ Wait {left}s before next /rob.")

    if victim.get("protect_until", 0) > now:
        return await message.reply_text("🛡️ Target is protected!")

    victim_bal = int(victim.get("coins") or 0)
    if victim_bal <= 0:
        return await message.reply_text(
            f"❌ {_mention(target)} has <b>$0</b> — nothing to rob.",
            parse_mode=ParseMode.HTML,
        )

    # only as much as they have
    steal = min(amount, victim_bal)
    capped = steal < amount

    success = random.random() < 0.45
    thief["last_rob"] = now

    if success:
        victim["coins"] = victim_bal - steal
        thief["coins"] = int(thief.get("coins") or 0) + steal
        _save(data)
        extra = f"\nℹ️ Asked ${amount:,} but target only had ${victim_bal:,}." if capped else ""
        await message.reply_text(
            f"🕵️ <b>ROB SUCCESS</b>\n\n"
            f"😈 Robber: {_mention(message.from_user)}\n"
            f"💀 Victim: {_mention(target)}\n"
            f"💵 Stolen: <b>${steal:,}</b>{extra}",
            parse_mode=ParseMode.HTML,
        )
    else:
        fine = min(int(thief.get("coins") or 0), max(50, steal // 2))
        thief["coins"] = int(thief.get("coins") or 0) - fine
        _save(data)
        await message.reply_text(
            f"🚨 <b>ROB FAILED</b>\n\n"
            f"{_mention(message.from_user)} got caught!\n"
            f"💸 Fine: <b>${fine:,}</b>",
            parse_mode=ParseMode.HTML,
        )


@bot.on_message(cdx("protect"))
async def protect_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    cost = 800
    data = _load()
    u = _user(data, message.from_user.id)
    if u["coins"] < cost:
        return await message.reply_text(f"❌ Need {cost} coins.")
    u["coins"] -= cost
    u["protect_until"] = time.time() + 86400
    _save(data)
    await message.reply_text("🛡️ Shield active for 24 hours!")


@bot.on_message(cdx("revive"))
async def revive_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    cost = 500
    data = _load()
    u = _user(data, message.from_user.id)
    if u.get("alive", True) and u.get("hp", 100) >= 100:
        return await message.reply_text("✅ You are already full HP.")
    if u["coins"] < cost:
        return await message.reply_text(f"❌ Need {cost} coins.")
    u["coins"] -= cost
    u["hp"] = 100
    u["alive"] = True
    _save(data)
    await message.reply_text("✨ Revived! HP restored to 100.")


# ── Fun ────────────────────────────────────────────────────────

@bot.on_message(cdx("dice"))
async def dice_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    try:
        await message.reply_dice(emoji="🎲")
    except Exception:
        n = random.randint(1, 6)
        await message.reply_text(f"🎲 You rolled <b>{n}</b>", parse_mode=ParseMode.HTML)


@bot.on_message(cdx(["slots", "slot"]))
async def slots_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    if not message.from_user:
        return
    cost = 50
    data = _load()
    u = _user(data, message.from_user.id)
    if u["coins"] < cost:
        return await message.reply_text(f"❌ Need {cost} coins to play.")
    u["coins"] -= cost
    icons = ["🍒", "🍋", "🔔", "⭐", "💎", "7️⃣"]
    a, b, c = random.choice(icons), random.choice(icons), random.choice(icons)
    if a == b == c:
        win = 500 if a == "💎" else 250
        u["coins"] += win
        result = f"🎉 JACKPOT! +{win} coins"
    elif a == b or b == c or a == c:
        win = 80
        u["coins"] += win
        result = f"✨ Nice! +{win} coins"
    else:
        result = "💨 No luck — try again"
    _save(data)
    await message.reply_text(f"🎰 | {a} | {b} | {c} |\n{result}")


@bot.on_message(cdx(["coinflip", "flip"]))
async def coinflip_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    side = random.choice(["Heads", "Tails"])
    await message.reply_text(f"🪙 <b>{side}</b>!", parse_mode=ParseMode.HTML)


@bot.on_message(cdx("riddle"))
async def riddle_cmd(client, message: Message):
    if await block_if_maintenance(message):
        return
    q, a = random.choice(RIDDLES)
    await message.reply_text(
        f"🧩 <b>Riddle</b>\n\n{q}\n\n<code>Reply with your answer!</code>\n"
        f"(Answer: spoiler — ||{a}||)",
        parse_mode=ParseMode.HTML,
    )


print("[games] plugin loaded OK", flush=True)
