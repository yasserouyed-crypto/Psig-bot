"""
╔══════════════════════════════════════════════╗
║  RP BOT — Automobile / Blacklist / Automod   ║
║  SOS support / Preuve staff / Économie RP    ║
║  Préfixe : RP!  rp!  Rp!  rP!  (insensible)  ║
╚══════════════════════════════════════════════╝
Installation : pip install -U discord.py
Lancement    : DISCORD_TOKEN=xxx python bot.py
"""
import asyncio
import copy
import io
import json
import os
import random
import re
import secrets
import string
import sys
import time
import unicodedata
from collections import defaultdict, deque
from datetime import timedelta
from typing import Optional

import discord
from aiohttp import web
from discord.ext import commands, tasks

# ═══════════════════════ CONFIGURATION ═══════════════════════
TOKEN = os.getenv("DISCORD_TOKEN") or "COLLE_TON_TOKEN_ICI"
OWNER_IDS = [1508469418093445310, 1544749886795157557, 1239641924407660604]  # Fondateurs
SUPPORT_GUILD_ID = 1544966656609095722  # Serveur support
STAFF_ROLE_IDS = [1558383923648794765]  # Rôle staff du support
LOG_ALL_CHANNEL_ID = 1558379808591712318    # Logs de toutes les commandes
LOG_STAFF_CHANNEL_ID = 1558379841487900753  # Logs des commandes staff / modération
SUPPORT_NAME = "Phénix Support"
BOT_NAME = "RP Bot"  # Nom affiché dans les embeds
SUPPORT_LOGO = ""               # URL d'une image (optionnel)
SUPPORT_INVITE = ""             # Lien d'invitation permanent du support (optionnel)
START = time.time()
DATA_FILE = "data.json"
COLOR = 0x5865F2
OK, KO, WARN = 0x57F287, 0xED4245, 0xFEE75C

# ═══════════════════════ BASE DE DONNÉES JSON ═══════════════════════
class DB:
    def __init__(self, path):
        self.path = path
        self.data = {"guilds": {}, "users": {}, "proofs": {}, "sos_channel": None,
                     "raid_channel": None, "blacklist": {"users": {}, "guilds": {}}}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.data.update(json.load(f))
        self.data["blacklist"].setdefault("users", {})
        self.data["blacklist"].setdefault("guilds", {})

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

db = DB(DATA_FILE)

def merge(default, data):
    for k, v in default.items():
        if k not in data:
            data[k] = copy.deepcopy(v)
        elif isinstance(v, dict) and isinstance(data[k], dict):
            merge(v, data[k])
    return data

GUILD_DEFAULT = {
    "automod": {
        "enabled": False,
        "spam": {"on": True, "messages": 5, "seconds": 5},
        "mentions": {"on": True, "max": 5},
        "links": {"on": False},
        "invites": {"on": True},
        "caps": {"on": True, "percent": 70, "min_len": 10},
        "emojis": {"on": True, "max": 10},
        "badwords": {"on": False, "words": []},
        "strikes": {"timeout": 3, "kick": 5, "ban": 7, "decay_hours": 24, "timeout_minutes": 10},
        "raid": {"on": True, "joins": 8, "seconds": 10, "action": "kick"},
        "log_channel": None, "ignored_channels": [], "ignored_roles": [],
    },
    "strikes": {}, "warns": {}, "bl_autoban": False, "whitelist": [],
    "config": {"suggest": None, "welcome": None, "autorole": None,
               "welcome_msg": "Bienvenue {user} sur **{server}** !", "leave": None,
               "leave_msg": "**{name}** a quitté **{server}**. À bientôt !"},
    "tickets": {"category": None, "staff_roles": [], "logs": None, "open": {}, "counter": 0},
    "services": {"police": None, "pompier": None, "samu": None},
}
USER_DEFAULT = {
    "money": 1500, "bank": 0, "job": "Chômeur", "identity": None,
    "permis": {"valid": False, "points": 12}, "cars": [], "active": None,
    "next_car": 1, "fines": [], "casier": [],
}

def gcfg(gid):
    return merge(GUILD_DEFAULT, db.data["guilds"].setdefault(str(gid), {}))

def udata(uid):
    return merge(USER_DEFAULT, db.data["users"].setdefault(str(uid), {}))

# ═══════════════════════ BOT ═══════════════════════
def get_prefix(bot_, msg):
    if msg.content[:3].lower() == "rp!":
        return msg.content[:3]
    return commands.when_mentioned(bot_, msg)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=get_prefix, intents=intents, case_insensitive=True,
                   help_command=None, strip_after_prefix=True)

class Blacklisted(commands.CheckFailure):
    pass

def emb(title, desc=None, color=COLOR):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text=f"{BOT_NAME} • RP!help")
    return e

def err(text):
    return emb("❌ Erreur", text, KO)

def money(n):
    return f"{int(n):,}".replace(",", " ") + " €"

def is_staff_member(user):
    if user.id in OWNER_IDS:
        return True
    g = bot.get_guild(SUPPORT_GUILD_ID)
    m = g.get_member(user.id) if g else None
    return bool(m and any(r.id in STAFF_ROLE_IDS for r in m.roles))

def staff_only():
    return commands.check(lambda ctx: is_staff_member(ctx.author))

def support_only():
    def pred(ctx):
        if not ctx.guild or ctx.guild.id != SUPPORT_GUILD_ID:
            raise commands.CheckFailure("Cette commande n'est utilisable que dans le **serveur support** du bot.")
        if not is_staff_member(ctx.author):
            raise commands.CheckFailure("Réservé au staff du support.")
        return True
    return commands.check(pred)

@bot.check
async def global_check(ctx):
    if ctx.author.id in OWNER_IDS:
        return True
    bl = db.data["blacklist"]
    if str(ctx.author.id) in bl["users"]:
        raise Blacklisted(f"Tu es blacklist du bot. Raison : {bl['users'][str(ctx.author.id)]['reason']}")
    if ctx.guild and str(ctx.guild.id) in bl["guilds"] and ctx.guild.id != SUPPORT_GUILD_ID:
        raise Blacklisted("Ce serveur est blacklist du bot.")
    return True

@bot.event
async def on_command_error(ctx, e):
    e = getattr(e, "original", e)
    if isinstance(e, commands.CommandNotFound):
        return
    if isinstance(e, discord.Forbidden):
        return await ctx.send(embed=err("Permission refusée (hiérarchie des rôles ou permissions manquantes)."))
    if isinstance(e, discord.HTTPException):
        return await ctx.send(embed=err(f"Discord a refusé : {str(e.text)[:200]}"))
    if isinstance(e, commands.MissingRequiredArgument):
        return await ctx.send(embed=err(f"Argument manquant : `{e.param.name}`.\nUtilise `RP!help`."))
    if isinstance(e, commands.CommandOnCooldown):
        return await ctx.send(embed=err(f"Patiente encore **{int(e.retry_after)}s**."))
    if isinstance(e, commands.MissingPermissions):
        return await ctx.send(embed=err("Tu n'as pas la permission pour ça."))
    if isinstance(e, (commands.BadArgument, commands.BadUnionArgument)):
        return await ctx.send(embed=err("Argument invalide. Vérifie la commande dans `RP!help`."))
    if isinstance(e, commands.NoPrivateMessage):
        return await ctx.send(embed=err("Utilisable uniquement dans un serveur."))
    if isinstance(e, commands.CheckFailure):
        return await ctx.send(embed=err(str(e) or "Tu ne peux pas utiliser cette commande."))
    print("Erreur :", repr(e))

# ═══════════════════════ BOUTONS D'ALERTE (SOS / RAID) ═══════════════════════
class AlertView(discord.ui.View):
    def __init__(self, url=None, claimed=False, resolved=False, label="Rejoindre le serveur"):
        super().__init__(timeout=None)
        self.claim.disabled = claimed or resolved
        self.resolve.disabled = resolved
        if url:
            self.add_item(discord.ui.Button(label=label, url=url, emoji="🔗"))

    async def _update(self, inter, status, resolved):
        if not is_staff_member(inter.user):
            return await inter.response.send_message("Réservé au staff du support.", ephemeral=True)
        e = inter.message.embeds[0]
        for i, f in enumerate(e.fields):
            if f.name.endswith("Statut"):
                e.set_field_at(i, name=f.name, value=f"{status} {inter.user.mention} (`{inter.user.id}`)", inline=False)
        e.color = OK if resolved else WARN
        url, label = None, "Rejoindre le serveur"
        for row in inter.message.components:
            for c in getattr(row, "children", []):
                if getattr(c, "url", None):
                    url, label = c.url, c.label
        await inter.response.edit_message(embed=e, view=AlertView(url, True, resolved, label))

    @discord.ui.button(label="Pris en charge", emoji="🛡️", style=discord.ButtonStyle.secondary, custom_id="alert:claim")
    async def claim(self, inter, button):
        await self._update(inter, "🛡️ Pris en charge par", False)

    @discord.ui.button(label="Résolu", emoji="✅", style=discord.ButtonStyle.success, custom_id="alert:resolve")
    async def resolve(self, inter, button):
        await self._update(inter, "✅ Résolu par", True)

async def get_invite(guild, channel=None):
    try:
        ch = channel or next((c for c in guild.text_channels if c.permissions_for(guild.me).create_instant_invite), None)
        if ch:
            return (await ch.create_invite(max_age=3600, max_uses=5, reason="Alerte support")).url
    except Exception:
        pass
    return None

# ═══════════════════════ SOS ═══════════════════════
@bot.command(name="setsos")
@commands.guild_only()
@support_only()
async def setsos(ctx, channel: discord.TextChannel):
    """Définit le salon des alertes SOS (support uniquement)."""
    db.data["sos_channel"] = channel.id
    db.save()
    await ctx.send(embed=emb("✅ Salon SOS configuré", f"Les alertes arriveront dans {channel.mention}.", OK))

@bot.command(name="setraid")
@commands.guild_only()
@support_only()
async def setraid(ctx, channel: discord.TextChannel):
    """Définit le salon des alertes RAID (support uniquement)."""
    db.data["raid_channel"] = channel.id
    db.save()
    await ctx.send(embed=emb("✅ Salon RAID configuré", f"Les alertes raid arriveront dans {channel.mention}.", OK))

@bot.command(name="sos")
@commands.guild_only()
@commands.cooldown(1, 120, commands.BucketType.user)
async def sos(ctx, *, motif: str):
    """RP!sos <motif> — demande d'aide envoyée au support du bot."""
    ch = bot.get_channel(db.data.get("sos_channel") or 0)
    if not ch:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(embed=err("Le salon SOS n'est pas configuré dans le support du bot."))
    if len(motif) > 900:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(embed=err("Motif trop long (900 caractères max)."))
    url = await get_invite(ctx.guild, ctx.channel)
    sid = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    e = emb("🚨 Alerte SOS", color=0xE67E22)
    e.add_field(name="👤 Déclenchée par", value=f"{ctx.author.mention} (`{ctx.author.id}`)", inline=False)
    e.add_field(name="🏰 Serveur", value=f"{ctx.guild.name} (`{ctx.guild.id}`)", inline=False)
    e.add_field(name="💬 Salon d'origine", value=ctx.channel.mention, inline=False)
    e.add_field(name="📝 Message", value=motif, inline=False)
    e.add_field(name="📌 Statut", value="⏳ En attente", inline=False)
    e.set_footer(text=f"ID: {sid} • {bot.user.name}")
    e.timestamp = discord.utils.utcnow()
    if SUPPORT_LOGO:
        e.set_thumbnail(url=SUPPORT_LOGO)
    await ch.send(embed=e, view=AlertView(url))
    await ctx.send(embed=emb("🆘 SOS envoyé", f"Le staff de **{SUPPORT_NAME}** a été prévenu.\nID : `{sid}`", OK))

# ═══════════════════════ PREUVE STAFF ═══════════════════════
@bot.command(name="preuve", aliases=["proof"])
async def preuve(ctx):
    """RP!preuve — prouve que tu es staff du support officiel (code vérifiable)."""
    g = bot.get_guild(SUPPORT_GUILD_ID)
    m = g.get_member(ctx.author.id) if g else None
    if not m or not (is_staff_member(ctx.author)):
        return await ctx.send(embed=err("Tu n'es pas staff du support officiel."))
    roles = [r.name for r in m.roles if r.id in STAFF_ROLE_IDS] or ["Fondateur"]
    code = secrets.token_hex(4).upper()
    exp = int(time.time()) + 86400
    db.data["proofs"][code] = {"user": m.id, "roles": roles, "exp": exp}
    db.save()
    e = emb(f"🛡️ Preuve de staff — {SUPPORT_NAME}", color=OK)
    e.add_field(name="👤 Membre", value=f"{m.mention} (`{m.id}`)", inline=False)
    e.add_field(name="🎖️ Grade(s)", value=", ".join(roles), inline=False)
    e.add_field(name="📅 Dans le support depuis", value=discord.utils.format_dt(m.joined_at, "D") if m.joined_at else "?", inline=False)
    e.add_field(name="🔐 Code de vérification", value=f"`{code}`\nVérifier : `RP!verifpreuve {code}`", inline=False)
    e.add_field(name="⏳ Valide jusqu'à", value=f"<t:{exp}:f> (<t:{exp}:R>)", inline=False)
    e.set_thumbnail(url=m.display_avatar.url)
    e.set_footer(text="Une capture peut être falsifiée : vérifie toujours le code.")
    await ctx.send(embed=e)

@bot.command(name="verifpreuve")
async def verifpreuve(ctx, code: str):
    """RP!verifpreuve <code> — vérifie l'authenticité d'une preuve."""
    p = db.data["proofs"].get(code.upper())
    if not p or p["exp"] < time.time():
        return await ctx.send(embed=err("Code **invalide ou expiré** : cette preuve n'est pas authentique."))
    e = emb("✅ Preuve authentique", f"<@{p['user']}> (`{p['user']}`) est bien staff de **{SUPPORT_NAME}**.\nGrade(s) : {', '.join(p['roles'])}", OK)
    await ctx.send(embed=e)

# ═══════════════════════ BLACKLIST ═══════════════════════
@bot.group(name="blacklist", aliases=["bl"], invoke_without_command=True)
@staff_only()
async def blacklist(ctx):
    await ctx.send(embed=emb("⛔ Blacklist", "`RP!bl add <@/id> [raison]`\n`RP!bl remove <@/id>`\n`RP!bl list`\n`RP!bl info <@/id>`\n"
                              "`RP!bl export`\n`RP!bl server add|remove <id_serveur> [raison]`\n`RP!bl autoban on|off` (dans ton serveur)"))

@blacklist.command(name="add")
async def bl_add(ctx, user: discord.User, *, raison: str = "Non précisée"):
    if user.id in OWNER_IDS:
        return await ctx.send(embed=err("Impossible de blacklist un owner."))
    db.data["blacklist"]["users"][str(user.id)] = {"reason": raison, "by": ctx.author.id, "date": int(time.time())}
    db.save()
    await ctx.send(embed=emb("⛔ Utilisateur blacklist", f"{user} (`{user.id}`)\nRaison : {raison}", KO))

@blacklist.command(name="remove", aliases=["del"])
async def bl_remove(ctx, user: discord.User):
    if db.data["blacklist"]["users"].pop(str(user.id), None) is None:
        return await ctx.send(embed=err("Cet utilisateur n'est pas blacklist."))
    db.save()
    await ctx.send(embed=emb("✅ Retiré de la blacklist", f"{user} (`{user.id}`)", OK))

@blacklist.command(name="info")
async def bl_info(ctx, user: discord.User):
    b = db.data["blacklist"]["users"].get(str(user.id))
    if not b:
        return await ctx.send(embed=emb("✅ Non blacklist", f"{user} n'est pas blacklist.", OK))
    await ctx.send(embed=emb("⛔ Blacklist", f"{user} (`{user.id}`)\nRaison : {b['reason']}\nPar : <@{b['by']}>\nLe : <t:{b['date']}:f>", KO))

@blacklist.command(name="list")
async def bl_list(ctx):
    users = db.data["blacklist"]["users"]
    if not users:
        return await ctx.send(embed=emb("⛔ Blacklist", "Aucun utilisateur blacklist."))
    lines = [f"`{i}` — {d['reason'][:60]}" for i, d in list(users.items())[:40]]
    guilds = db.data["blacklist"]["guilds"]
    e = emb(f"⛔ Blacklist ({len(users)} users / {len(guilds)} serveurs)", "\n".join(lines))
    await ctx.send(embed=e)

@blacklist.command(name="export")
async def bl_export(ctx):
    buf = io.BytesIO(json.dumps(db.data["blacklist"], ensure_ascii=False, indent=1).encode())
    await ctx.send(file=discord.File(buf, "blacklist.json"))

@blacklist.group(name="server", aliases=["serveur"], invoke_without_command=True)
async def bl_server(ctx):
    await ctx.send("`RP!bl server add <id> [raison]` / `RP!bl server remove <id>`")

@bl_server.command(name="add")
async def bl_server_add(ctx, guild_id: int, *, raison: str = "Non précisée"):
    db.data["blacklist"]["guilds"][str(guild_id)] = {"reason": raison, "by": ctx.author.id, "date": int(time.time())}
    db.save()
    g = bot.get_guild(guild_id)
    if g and guild_id != SUPPORT_GUILD_ID:
        await g.leave()
    await ctx.send(embed=emb("⛔ Serveur blacklist", f"`{guild_id}` — {raison}", KO))

@bl_server.command(name="remove")
async def bl_server_remove(ctx, guild_id: int):
    db.data["blacklist"]["guilds"].pop(str(guild_id), None)
    db.save()
    await ctx.send(embed=emb("✅ Serveur retiré", f"`{guild_id}`", OK))

@blacklist.command(name="autoban")
@commands.guild_only()
async def bl_autoban(ctx, mode: str):
    if not ctx.author.guild_permissions.administrator and ctx.author.id not in OWNER_IDS:
        return await ctx.send(embed=err("Administrateur requis."))
    gcfg(ctx.guild.id)["bl_autoban"] = mode.lower() in ("on", "oui", "true")
    db.save()
    await ctx.send(embed=emb("🛡️ Auto-ban blacklist", f"Statut : **{'activé' if gcfg(ctx.guild.id)['bl_autoban'] else 'désactivé'}**", OK))

@bot.event
async def on_guild_join(guild):
    if str(guild.id) in db.data["blacklist"]["guilds"]:
        await guild.leave()

# ═══════════════════════ AUTOMOD ═══════════════════════
spam_track = defaultdict(deque)
join_track = defaultdict(deque)
INVITE_RE = re.compile(r"(discord\.gg|discord(?:app)?\.com/invite)/\w+", re.I)
LINK_RE = re.compile(r"https?://\S+", re.I)
EMOJI_RE = re.compile(r"<a?:\w+:\d+>|[\U0001F300-\U0001FAFF\u2600-\u27BF]")

async def am_log(guild, cfg, embed):
    ch = guild.get_channel(cfg["log_channel"] or 0)
    if ch:
        try:
            await ch.send(embed=embed)
        except discord.HTTPException:
            pass

async def automod(msg):
    if not msg.guild or msg.author.bot or not isinstance(msg.author, discord.Member):
        return False
    cfg = gcfg(msg.guild.id)["automod"]
    m, c = msg.author, msg.content
    if not cfg["enabled"] or m.guild_permissions.manage_messages or m.id in OWNER_IDS or m.id in gcfg(msg.guild.id)["whitelist"]:
        return False
    if msg.channel.id in cfg["ignored_channels"] or any(r.id in cfg["ignored_roles"] for r in m.roles):
        return False
    reason, now = None, time.time()
    if cfg["spam"]["on"]:
        dq = spam_track[(msg.guild.id, m.id)]
        dq.append(now)
        while dq and now - dq[0] > cfg["spam"]["seconds"]:
            dq.popleft()
        if len(dq) >= cfg["spam"]["messages"]:
            reason = f"Spam ({len(dq)} messages en {cfg['spam']['seconds']}s)"
            dq.clear()
    if not reason and cfg["mentions"]["on"] and len(msg.mentions) + len(msg.role_mentions) > cfg["mentions"]["max"]:
        reason = "Trop de mentions"
    if not reason and cfg["invites"]["on"] and INVITE_RE.search(c):
        reason = "Invitation Discord interdite"
    if not reason and cfg["links"]["on"] and LINK_RE.search(c):
        reason = "Lien interdit"
    if not reason and cfg["caps"]["on"] and len(c) >= cfg["caps"]["min_len"]:
        letters = [x for x in c if x.isalpha()]
        if letters and sum(x.isupper() for x in letters) * 100 / len(letters) >= cfg["caps"]["percent"]:
            reason = "Abus de majuscules"
    if not reason and cfg["emojis"]["on"] and len(EMOJI_RE.findall(c)) > cfg["emojis"]["max"]:
        reason = "Trop d'émojis"
    if not reason and cfg["badwords"]["on"]:
        low = c.lower()
        if any(w in low for w in cfg["badwords"]["words"]):
            reason = "Mot interdit"
    if not reason:
        return False

    try:
        await msg.delete()
    except discord.HTTPException:
        pass
    g = gcfg(msg.guild.id)
    st = cfg["strikes"]
    lst = [t for t in g["strikes"].get(str(m.id), []) if now - t < st["decay_hours"] * 3600]
    lst.append(now)
    g["strikes"][str(m.id)] = lst
    db.save()
    n = len(lst)
    try:
        if n >= st["ban"]:
            action = "🔨 Ban"
            await m.ban(reason=f"Automod : {reason}")
        elif n >= st["kick"]:
            action = "👢 Expulsion"
            await m.kick(reason=f"Automod : {reason}")
        elif n >= st["timeout"]:
            action = f"🔇 Timeout {st['timeout_minutes']} min"
            await m.timeout(timedelta(minutes=st["timeout_minutes"]), reason=f"Automod : {reason}")
        else:
            action = "⚠️ Avertissement"
    except discord.HTTPException:
        action = "⚠️ Sanction impossible (permissions)"
    try:
        await msg.channel.send(f"{m.mention} 🛡️ **Automod** : {reason} — strike **{n}** ({action})", delete_after=8)
    except discord.HTTPException:
        pass
    e = emb("🛡️ Automod", color=WARN)
    e.add_field(name="Membre", value=f"{m} (`{m.id}`)")
    e.add_field(name="Raison", value=reason)
    e.add_field(name="Strikes / Action", value=f"{n} — {action}")
    e.add_field(name="Salon", value=msg.channel.mention)
    if c:
        e.add_field(name="Message", value=c[:500], inline=False)
    await am_log(msg.guild, cfg, e)
    return True

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return
    if await automod(msg):
        return
    await bot.process_commands(msg)

@bot.event
async def on_member_join(member):
    g = gcfg(member.guild.id)
    cfg = g["automod"]
    if g["bl_autoban"] and str(member.id) in db.data["blacklist"]["users"]:
        try:
            await member.ban(reason="Blacklist du bot")
        except discord.HTTPException:
            pass
        return
    if not cfg["raid"]["on"]:
        return
    now = time.time()
    dq = join_track[member.guild.id]
    dq.append((now, member))
    while dq and now - dq[0][0] > cfg["raid"]["seconds"]:
        dq.popleft()
    if len(dq) < cfg["raid"]["joins"]:
        return
    victims = [x[1] for x in dq if x[1].id not in g["whitelist"]]
    dq.clear()
    act = cfg["raid"]["action"]
    for v in victims:
        try:
            await (v.ban(reason="Anti-raid") if act == "ban" else v.kick(reason="Anti-raid"))
        except discord.HTTPException:
            pass
    e = emb("🚨 Raid détecté — Sanction appliquée", color=KO)
    e.add_field(name="🏰 Serveur", value=f"{member.guild.name} (`{member.guild.id}`)", inline=False)
    e.add_field(name="👥 Comptes concernés", value=f"{len(victims)} : " + ", ".join(f"`{v.id}`" for v in victims[:15]), inline=False)
    e.add_field(name="⚖️ Sanction appliquée", value=act.capitalize(), inline=False)
    e.add_field(name="📌 Statut", value="⏳ En attente", inline=False)
    e.set_footer(text=f"RaidID: {secrets.token_hex(6)}")
    e.timestamp = discord.utils.utcnow()
    await am_log(member.guild, cfg, e)
    ch = bot.get_channel(db.data.get("raid_channel") or 0)
    if ch:
        url = await get_invite(member.guild)
        await ch.send(embed=e, view=AlertView(url, label="Invitation serveur"))

@bot.group(name="automod", invoke_without_command=True)
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def automod_cmd(ctx):
    cfg = gcfg(ctx.guild.id)["automod"]
    e = emb(f"🛡️ Automod — {'✅ ACTIF' if cfg['enabled'] else '❌ INACTIF'}")
    for mod in ("spam", "mentions", "links", "invites", "caps", "emojis", "badwords", "raid"):
        d = cfg[mod]
        txt = ", ".join(f"{k}=`{v}`" for k, v in d.items() if k != "words")
        e.add_field(name=mod, value=txt, inline=False)
    s = cfg["strikes"]
    e.add_field(name="strikes", value=", ".join(f"{k}=`{v}`" for k, v in s.items()), inline=False)
    e.set_footer(text="RP!automod on/off | set <module> <clé> <valeur> | toggle <module> | badword add/remove <mot> | logs #salon | ignore #salon")
    await ctx.send(embed=e)

@automod_cmd.command(name="on")
async def am_on(ctx):
    gcfg(ctx.guild.id)["automod"]["enabled"] = True
    db.save()
    await ctx.send(embed=emb("✅ Automod activé", color=OK))

@automod_cmd.command(name="off")
async def am_off(ctx):
    gcfg(ctx.guild.id)["automod"]["enabled"] = False
    db.save()
    await ctx.send(embed=emb("❌ Automod désactivé", color=KO))

@automod_cmd.command(name="toggle")
async def am_toggle(ctx, module: str):
    d = gcfg(ctx.guild.id)["automod"].get(module.lower())
    if not isinstance(d, dict) or "on" not in d:
        return await ctx.send(embed=err("Module inconnu."))
    d["on"] = not d["on"]
    db.save()
    await ctx.send(embed=emb(f"Module {module}", "activé ✅" if d["on"] else "désactivé ❌", OK if d["on"] else KO))

@automod_cmd.command(name="set")
async def am_set(ctx, module: str, key: str, value: str):
    d = gcfg(ctx.guild.id)["automod"].get(module.lower())
    if not isinstance(d, dict) or key not in d or key == "words":
        return await ctx.send(embed=err("Module ou clé inconnu. Regarde `RP!automod`."))
    if isinstance(d[key], bool):
        d[key] = value.lower() in ("on", "true", "oui", "1")
    elif isinstance(d[key], int):
        if not value.isdigit():
            return await ctx.send(embed=err("Valeur numérique attendue."))
        d[key] = int(value)
    else:
        d[key] = value.lower()
    db.save()
    await ctx.send(embed=emb("✅ Seuil modifié", f"`{module}.{key}` = `{d[key]}`", OK))

@automod_cmd.command(name="badword")
async def am_badword(ctx, action: str, *, mot: str):
    words = gcfg(ctx.guild.id)["automod"]["badwords"]["words"]
    mot = mot.lower()
    if action.lower() == "add" and mot not in words:
        words.append(mot)
    elif action.lower() in ("remove", "del") and mot in words:
        words.remove(mot)
    db.save()
    await ctx.send(embed=emb("✅ Mots interdits mis à jour", f"{len(words)} mot(s) enregistré(s).", OK))
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

@automod_cmd.command(name="logs")
async def am_logs(ctx, channel: discord.TextChannel):
    gcfg(ctx.guild.id)["automod"]["log_channel"] = channel.id
    db.save()
    await ctx.send(embed=emb("✅ Logs automod", channel.mention, OK))

@automod_cmd.command(name="ignore")
async def am_ignore(ctx, target: discord.TextChannel | discord.Role):
    lst = gcfg(ctx.guild.id)["automod"]["ignored_roles" if isinstance(target, discord.Role) else "ignored_channels"]
    if target.id in lst:
        lst.remove(target.id)
    else:
        lst.append(target.id)
    db.save()
    await ctx.send(embed=emb("✅ Liste d'exceptions mise à jour", target.mention, OK))

# ═══════════════════════ MODÉRATION ═══════════════════════
@bot.command()
@commands.guild_only()
@commands.has_permissions(moderate_members=True)
async def warn(ctx, member: discord.Member, *, raison: str = "Non précisée"):
    w = gcfg(ctx.guild.id)["warns"].setdefault(str(member.id), [])
    w.append({"reason": raison, "by": ctx.author.id, "date": int(time.time())})
    db.save()
    await ctx.send(embed=emb("⚠️ Avertissement", f"{member.mention} — {raison}\nTotal : **{len(w)}**", WARN))

@bot.command()
@commands.guild_only()
@commands.has_permissions(moderate_members=True)
async def warns(ctx, member: discord.Member):
    w = gcfg(ctx.guild.id)["warns"].get(str(member.id), [])
    txt = "\n".join(f"`{i+1}` <t:{x['date']}:d> — {x['reason']}" for i, x in enumerate(w)) or "Aucun avertissement."
    await ctx.send(embed=emb(f"⚠️ Warns de {member}", txt))

@bot.command()
@commands.guild_only()
@commands.has_permissions(moderate_members=True)
async def clearwarns(ctx, member: discord.Member):
    gcfg(ctx.guild.id)["warns"].pop(str(member.id), None)
    gcfg(ctx.guild.id)["strikes"].pop(str(member.id), None)
    db.save()
    await ctx.send(embed=emb("✅ Warns et strikes effacés", member.mention, OK))

@bot.command()
@commands.guild_only()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, raison: str = "Non précisée"):
    await member.kick(reason=f"{ctx.author} : {raison}")
    await ctx.send(embed=emb("👢 Expulsé", f"{member} — {raison}", WARN))

@bot.command()
@commands.guild_only()
@commands.has_permissions(ban_members=True)
async def ban(ctx, user: discord.User, *, raison: str = "Non précisée"):
    await ctx.guild.ban(user, reason=f"{ctx.author} : {raison}")
    await ctx.send(embed=emb("🔨 Banni", f"{user} — {raison}", KO))

@bot.command()
@commands.guild_only()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user: discord.User):
    await ctx.guild.unban(user)
    await ctx.send(embed=emb("✅ Débanni", str(user), OK))



# ═══════════════════════ ÉCONOMIE / IDENTITÉ / MÉTIERS ═══════════════════════
JOBS = {
    "Chômeur": (0, 0), "Livreur": (200, 450), "Taxi": (250, 550), "Mécanicien": (350, 700),
    "Policier": (450, 800), "Gendarme": (450, 800), "Pompier": (450, 800),
    "Médecin": (600, 1100), "Concessionnaire": (600, 1200), "Avocat": (700, 1400),
}

@bot.command(aliases=["creeridentite"])
async def cni(ctx, prenom: str, nom: str, age: int):
    """RP!cni <prénom> <nom> <âge> — crée ta carte d'identité RP."""
    u = udata(ctx.author.id)
    if u["identity"]:
        return await ctx.send(embed=err("Tu as déjà une identité. Utilise `RP!macni`."))
    if not 16 <= age <= 99:
        return await ctx.send(embed=err("Âge RP entre 16 et 99."))
    u["identity"] = {"prenom": prenom.capitalize(), "nom": nom.upper(), "age": age, "num": "".join(random.choices(string.digits, k=12))}
    db.save()
    await ctx.invoke(macni)

@bot.command(aliases=["carte"])
async def macni(ctx, member: discord.Member = None):
    member = member or ctx.author
    i = udata(member.id)["identity"]
    if not i:
        return await ctx.send(embed=err("Aucune identité. Crée-la avec `RP!cni <prénom> <nom> <âge>`."))
    e = emb("🪪 Carte Nationale d'Identité", color=COLOR)
    e.add_field(name="Nom", value=i["nom"]).add_field(name="Prénom", value=i["prenom"]).add_field(name="Âge", value=f"{i['age']} ans")
    e.add_field(name="N°", value=f"`{i['num']}`").add_field(name="Métier", value=udata(member.id)["job"])
    e.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=e)

@bot.command(aliases=["argent", "balance", "bal"])
async def solde(ctx, member: discord.Member = None):
    member = member or ctx.author
    u = udata(member.id)
    e = emb(f"💰 Compte de {member.display_name}")
    e.add_field(name="Liquide", value=money(u["money"])).add_field(name="Banque", value=money(u["bank"]))
    await ctx.send(embed=e)

@bot.command(aliases=["dep"])
async def deposer(ctx, montant: int):
    u = udata(ctx.author.id)
    if not 0 < montant <= u["money"]:
        return await ctx.send(embed=err("Montant invalide."))
    u["money"] -= montant; u["bank"] += montant; db.save()
    await ctx.send(embed=emb("🏦 Dépôt", f"{money(montant)} déposés.", OK))

@bot.command(aliases=["ret"])
async def retirer(ctx, montant: int):
    u = udata(ctx.author.id)
    if not 0 < montant <= u["bank"]:
        return await ctx.send(embed=err("Montant invalide."))
    u["bank"] -= montant; u["money"] += montant; db.save()
    await ctx.send(embed=emb("🏦 Retrait", f"{money(montant)} retirés.", OK))

@bot.command(aliases=["pay", "virement"])
async def donner(ctx, member: discord.Member, montant: int):
    u, t = udata(ctx.author.id), udata(member.id)
    if member.bot or member == ctx.author or not 0 < montant <= u["money"]:
        return await ctx.send(embed=err("Virement impossible."))
    u["money"] -= montant; t["money"] += montant; db.save()
    await ctx.send(embed=emb("💸 Virement", f"{money(montant)} → {member.mention}", OK))

@bot.command(aliases=["job"])
async def metier(ctx, *, nom: str = None):
    u = udata(ctx.author.id)
    if not nom:
        txt = "\n".join(f"**{j}** — {a}-{b} €/travail" for j, (a, b) in JOBS.items())
        return await ctx.send(embed=emb("💼 Métiers disponibles", txt + "\n\nChoisir : `RP!metier <nom>`"))
    match = next((j for j in JOBS if j.lower() == nom.lower()), None)
    if not match:
        return await ctx.send(embed=err("Métier inconnu."))
    if not u["identity"]:
        return await ctx.send(embed=err("Crée d'abord ton identité : `RP!cni`."))
    u["job"] = match; db.save()
    await ctx.send(embed=emb("💼 Nouveau métier", f"Tu es maintenant **{match}**.", OK))

@bot.command(aliases=["work", "taf"])
@commands.cooldown(1, 1800, commands.BucketType.user)
async def travail(ctx):
    u = udata(ctx.author.id)
    a, b = JOBS.get(u["job"], (0, 0))
    if b == 0:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(embed=err("Tu es chômeur. Choisis un job avec `RP!metier`."))
    gain = random.randint(a, b)
    u["money"] += gain; db.save()
    await ctx.send(embed=emb("🛠️ Journée de travail", f"{u['job']} : tu gagnes **{money(gain)}**.", OK))

@bot.command(aliases=["top", "lb"])
async def classement(ctx):
    rows = sorted(db.data["users"].items(), key=lambda x: x[1].get("money", 0) + x[1].get("bank", 0), reverse=True)[:10]
    txt = "\n".join(f"**{i+1}.** <@{uid}> — {money(d.get('money', 0) + d.get('bank', 0))}" for i, (uid, d) in enumerate(rows))
    await ctx.send(embed=emb("🏆 Les plus riches", txt or "Personne pour l'instant."))

# ═══════════════════════ AUTOMOBILE ═══════════════════════
# clé: (nom, prix, réservoir L, conso L/100km)
CARS = {
    "clio": ("Renault Clio", 8000, 45, 6.0), "golf": ("VW Golf", 14000, 50, 6.5),
    "308": ("Peugeot 308", 16000, 52, 6.0), "moto": ("Yamaha MT-07", 7000, 14, 4.5),
    "megane": ("Mégane RS", 32000, 50, 9.0), "m3": ("BMW M3", 75000, 60, 11.0),
    "rs6": ("Audi RS6", 110000, 75, 12.0), "911": ("Porsche 911", 140000, 64, 11.0),
    "huracan": ("Lamborghini Huracán", 250000, 80, 14.0),
}
FUEL_PRICE = 2.0

def plate():
    L = string.ascii_uppercase
    return f"{random.choice(L)}{random.choice(L)}-{random.randint(100, 999)}-{random.choice(L)}{random.choice(L)}"

def get_car(u, cid=None):
    cid = cid if cid is not None else u["active"]
    return next((c for c in u["cars"] if c["id"] == cid), None)

def add_fine(u, amount, reason, by="Radar"):
    fid = max([f["id"] for f in u["fines"]] + [0]) + 1
    u["fines"].append({"id": fid, "amount": amount, "reason": reason, "by": str(by), "paid": False})

@bot.command(aliases=["concession", "catalogue"])
async def concessionnaire(ctx):
    txt = "\n".join(f"`{k}` — **{n}** · {money(p)} · {r}L · {c}L/100" for k, (n, p, r, c) in CARS.items())
    await ctx.send(embed=emb("🚗 Concession", txt + "\n\nAcheter : `RP!acheter <clé>`"))

@bot.command()
async def acheter(ctx, modele: str):
    u = udata(ctx.author.id)
    m = CARS.get(modele.lower())
    if not m:
        return await ctx.send(embed=err("Modèle inconnu. `RP!concession`."))
    if not u["identity"]:
        return await ctx.send(embed=err("Crée ton identité avant : `RP!cni`."))
    if u["money"] < m[1]:
        return await ctx.send(embed=err(f"Il te manque {money(m[1] - u['money'])} en liquide."))
    u["money"] -= m[1]
    car = {"id": u["next_car"], "model": modele.lower(), "plate": plate(), "fuel": float(m[2]), "health": 100}
    u["next_car"] += 1
    u["cars"].append(car)
    u["active"] = u["active"] or car["id"]
    db.save()
    await ctx.send(embed=emb("🎉 Achat réussi", f"**{m[0]}** — plaque `{car['plate']}` (ID `{car['id']}`)", OK))

@bot.command(aliases=["voitures"])
async def garage(ctx, member: discord.Member = None):
    member = member or ctx.author
    u = udata(member.id)
    if not u["cars"]:
        return await ctx.send(embed=emb("🏠 Garage vide"))
    txt = "\n".join(f"{'⭐' if c['id'] == u['active'] else '▫️'} `{c['id']}` **{CARS[c['model']][0]}** `{c['plate']}` · ⛽ {c['fuel']:.0f}L · 🔧 {c['health']}%" for c in u["cars"])
    await ctx.send(embed=emb(f"🏠 Garage de {member.display_name}", txt))

@bot.command()
async def conduire(ctx, car_id: int):
    u = udata(ctx.author.id)
    if not get_car(u, car_id):
        return await ctx.send(embed=err("Véhicule introuvable."))
    u["active"] = car_id; db.save()
    await ctx.send(embed=emb("🔑 Véhicule actif changé", f"ID `{car_id}`", OK))

@bot.command(aliases=["essence"])
async def plein(ctx):
    u = udata(ctx.author.id)
    c = get_car(u)
    if not c:
        return await ctx.send(embed=err("Aucun véhicule actif."))
    liters = CARS[c["model"]][2] - c["fuel"]
    cost = int(liters * FUEL_PRICE)
    if liters < 1:
        return await ctx.send(embed=err("Réservoir déjà plein."))
    if u["money"] < cost:
        return await ctx.send(embed=err(f"Plein à {money(cost)}, tu n'as pas assez."))
    u["money"] -= cost; c["fuel"] = float(CARS[c["model"]][2]); db.save()
    await ctx.send(embed=emb("⛽ Plein effectué", f"{liters:.0f}L pour {money(cost)}.", OK))

@bot.command(aliases=["repair"])
async def reparer(ctx):
    u = udata(ctx.author.id)
    c = get_car(u)
    if not c:
        return await ctx.send(embed=err("Aucun véhicule actif."))
    cost = int((100 - c["health"]) * CARS[c["model"]][1] / 400)
    if cost == 0:
        return await ctx.send(embed=err("Véhicule en parfait état."))
    if u["money"] < cost:
        return await ctx.send(embed=err(f"Réparation : {money(cost)}."))
    u["money"] -= cost; c["health"] = 100; db.save()
    await ctx.send(embed=emb("🔧 Réparé", f"Coût : {money(cost)}.", OK))

@bot.command()
async def vendre(ctx, car_id: int):
    u = udata(ctx.author.id)
    c = get_car(u, car_id)
    if not c:
        return await ctx.send(embed=err("Véhicule introuvable."))
    price = int(CARS[c["model"]][1] * 0.6 * (0.5 + c["health"] / 200))
    u["cars"].remove(c); u["money"] += price
    if u["active"] == car_id:
        u["active"] = u["cars"][0]["id"] if u["cars"] else None
    db.save()
    await ctx.send(embed=emb("💵 Véhicule vendu", f"{CARS[c['model']][0]} → {money(price)}", OK))

@bot.group(invoke_without_command=True)
async def permis(ctx, member: discord.Member = None):
    member = member or ctx.author
    p = udata(member.id)["permis"]
    e = emb(f"🪪 Permis de {member.display_name}", color=OK if p["valid"] else KO)
    e.add_field(name="Statut", value="✅ Valide" if p["valid"] else "❌ Non valide / retiré").add_field(name="Points", value=f"{p['points']}/12")
    if member == ctx.author and not p["valid"]:
        e.set_footer(text="Passe-le avec RP!permis passer (300 €)")
    await ctx.send(embed=e)

@permis.command(name="passer")
async def permis_passer(ctx):
    u = udata(ctx.author.id)
    if not u["identity"]:
        return await ctx.send(embed=err("Crée ton identité : `RP!cni`."))
    if u["permis"]["valid"]:
        return await ctx.send(embed=err("Tu as déjà ton permis."))
    if u["money"] < 300:
        return await ctx.send(embed=err("L'examen coûte 300 €."))
    u["money"] -= 300
    if random.random() < 0.7:
        u["permis"] = {"valid": True, "points": 12}
        res = emb("🎓 Permis obtenu !", "Félicitations, tu peux conduire.", OK)
    else:
        res = emb("📉 Échec", "Tu as raté l'examen. Retente !", KO)
    db.save()
    await ctx.send(embed=res)

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_messages=True)
async def retraitpermis(ctx, member: discord.Member):
    udata(member.id)["permis"] = {"valid": False, "points": 0}; db.save()
    await ctx.send(embed=emb("🚫 Permis retiré", member.mention, KO))

@bot.command(aliases=["drive"])
@commands.cooldown(1, 15, commands.BucketType.user)
async def rouler(ctx, km: int = 10):
    u = udata(ctx.author.id)
    c = get_car(u)
    if not c:
        return await ctx.send(embed=err("Aucun véhicule actif."))
    if not 1 <= km <= 300:
        return await ctx.send(embed=err("Distance entre 1 et 300 km."))
    if c["health"] <= 0:
        return await ctx.send(embed=err("Véhicule en épave : `RP!reparer`."))
    need = km * CARS[c["model"]][3] / 100
    if c["fuel"] < need:
        return await ctx.send(embed=err(f"Pas assez d'essence ({c['fuel']:.1f}L, il faut {need:.1f}L)."))
    c["fuel"] = round(c["fuel"] - need, 1)
    ev = []
    p = u["permis"]
    if not p["valid"] and random.random() < 0.35:
        add_fine(u, 500, "Conduite sans permis", "Contrôle routier")
        ev.append("🚓 Contrôle de police : **conduite sans permis** (500 €).")
    if km >= 10 and random.random() < 0.15:
        amt = random.choice([45, 90, 135, 200])
        add_fine(u, amt, "Excès de vitesse")
        ev.append(f"📸 Flash radar : excès de vitesse (**{amt} €**).")
        if p["valid"]:
            p["points"] -= random.choice([1, 2])
            if p["points"] <= 0:
                p.update(valid=False, points=0)
                ev.append("🚫 **Permis invalidé** (0 point).")
    if random.random() < 0.06:
        dmg = random.randint(10, 40)
        c["health"] = max(0, c["health"] - dmg)
        ev.append(f"💥 Accrochage ! Véhicule endommagé (-{dmg}%).")
    db.save()
    e = emb("🚗 Trajet terminé", f"{CARS[c['model']][0]} · **{km} km** · ⛽ {need:.1f}L consommés\n⛽ {c['fuel']:.0f}L restants · 🔧 {c['health']}%", OK)
    if ev:
        e.add_field(name="Événements", value="\n".join(ev), inline=False)
    await ctx.send(embed=e)

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_messages=True)
async def amende(ctx, member: discord.Member, montant: int, *, motif: str):
    if not 1 <= montant <= 50000:
        return await ctx.send(embed=err("Montant entre 1 et 50 000 €."))
    add_fine(udata(member.id), montant, motif, ctx.author.display_name)
    db.save()
    await ctx.send(embed=emb("🧾 Amende", f"{member.mention} : **{money(montant)}** — {motif}", WARN))

@bot.command(aliases=["pv"])
async def amendes(ctx):
    f = [x for x in udata(ctx.author.id)["fines"] if not x["paid"]]
    txt = "\n".join(f"`{x['id']}` **{money(x['amount'])}** — {x['reason']} ({x['by']})" for x in f) or "Aucune amende impayée 🎉"
    await ctx.send(embed=emb("🧾 Tes amendes", txt + ("\n\nPayer : `RP!payer <id>`" if f else "")))

@bot.command()
async def payer(ctx, fine_id: int):
    u = udata(ctx.author.id)
    f = next((x for x in u["fines"] if x["id"] == fine_id and not x["paid"]), None)
    if not f:
        return await ctx.send(embed=err("Amende introuvable."))
    if u["money"] < f["amount"]:
        return await ctx.send(embed=err("Pas assez de liquide."))
    u["money"] -= f["amount"]; f["paid"] = True; db.save()
    await ctx.send(embed=emb("✅ Amende payée", money(f["amount"]), OK))

# ═══════════════════════ CASIER / SERVICES / RP ═══════════════════════
@bot.command()
async def casier(ctx, member: discord.Member = None):
    member = member or ctx.author
    c = udata(member.id)["casier"]
    txt = "\n".join(f"`{i+1}` <t:{x['date']}:d> — {x['motif']} ({x['by']})" for i, x in enumerate(c)) or "Casier vierge."
    await ctx.send(embed=emb(f"📂 Casier judiciaire de {member.display_name}", txt))

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_messages=True)
async def ajoutcasier(ctx, member: discord.Member, *, motif: str):
    udata(member.id)["casier"].append({"motif": motif, "by": ctx.author.display_name, "date": int(time.time())}); db.save()
    await ctx.send(embed=emb("📂 Casier mis à jour", f"{member.mention} — {motif}", WARN))

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_messages=True)
async def effacercasier(ctx, member: discord.Member):
    udata(member.id)["casier"] = []; db.save()
    await ctx.send(embed=emb("🧽 Casier effacé", member.mention, OK))

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def setservice(ctx, service: str, role: discord.Role):
    if service.lower() not in ("police", "pompier", "samu"):
        return await ctx.send(embed=err("Services : police, pompier, samu."))
    gcfg(ctx.guild.id)["services"][service.lower()] = role.id; db.save()
    await ctx.send(embed=emb("✅ Service configuré", f"{service} → {role.mention}", OK))

async def appel(ctx, service, icon, label, msg):
    rid = gcfg(ctx.guild.id)["services"].get(service)
    e = emb(f"{icon} Appel au {label}", color=KO)
    e.add_field(name="Appelant", value=ctx.author.mention).add_field(name="Lieu", value=ctx.channel.mention)
    e.add_field(name="Message", value=msg, inline=False)
    await ctx.send(content=f"<@&{rid}>" if rid else None, embed=e,
                   allowed_mentions=discord.AllowedMentions(roles=True))

@bot.command(name="17")
@commands.guild_only()
@commands.cooldown(1, 30, commands.BucketType.user)
async def c17(ctx, *, msg: str):
    await appel(ctx, "police", "🚓", "17 — Police/Gendarmerie", msg)

@bot.command(name="18")
@commands.guild_only()
@commands.cooldown(1, 30, commands.BucketType.user)
async def c18(ctx, *, msg: str):
    await appel(ctx, "pompier", "🚒", "18 — Pompiers", msg)

@bot.command(name="15")
@commands.guild_only()
@commands.cooldown(1, 30, commands.BucketType.user)
async def c15(ctx, *, msg: str):
    await appel(ctx, "samu", "🚑", "15 — SAMU", msg)

@bot.command()
async def me(ctx, *, action: str):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass
    await ctx.send(embed=discord.Embed(description=f"**{ctx.author.display_name}** *{action}*", color=0x9B59B6),
                   allowed_mentions=discord.AllowedMentions.none())

@bot.command(name="do")
async def do_(ctx, *, texte: str):
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass
    await ctx.send(embed=discord.Embed(description=f"**[DO]** {texte} — *{ctx.author.display_name}*", color=0x3498DB),
                   allowed_mentions=discord.AllowedMentions.none())

@bot.command(aliases=["de", "dice"])
async def des(ctx, faces: int = 6):
    await ctx.send(embed=emb("🎲 Lancer de dé", f"{ctx.author.mention} fait **{random.randint(1, max(2, min(faces, 1000)))}** (d{faces})"))

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_messages=True)
async def annonce(ctx, *, texte: str):
    await ctx.message.delete()
    e = emb("📢 Annonce", texte, COLOR)
    e.set_footer(text=f"Par {ctx.author.display_name}")
    await ctx.send(embed=e)

# ═══════════════════════ AIDE / DIVERS ═══════════════════════
# ═══════════════════════ AIDE (menu par catégories) ═══════════════════════
HELP = {
    "Général": ("🔧", [
        ("ping", "Ping du bot"), ("config", "Configurer les systèmes bonus du bot"),
        ("botinfo", "Infos du bot"), ("userinfo @user/id", "Infos utilisateur"),
        ("serverinfo", "Infos serveur"), ("invite", "Inviter le bot"),
        ("support", "Serveur support"), ("antiraid", "État de l'anti-raid"),
        ("sos raison", "Alerte staff"), ("raidalert", "Alerte raid"),
        ("suggest suggestion", "Suggestion"),
        ("report @user/id raison + preuve_image", "Signaler un utilisateur"),
        ("client", "Afficher la shard du serveur"), ("contact", "Contacter l'équipe du bot"),
        ("news", "Derniers changements du bot"), ("help", "Ce menu")]),
    "Modération": ("🛡️", [
        ("ban @user/ID raison", "Bannir"), ("unban ID", "Débannir"),
        ("kick @user/ID raison", "Expulser"), ("timeout @user/ID temps raison", "Mute (10m, 2h, 1d)"),
        ("untimeout @user/ID", "Unmute"), ("clear 1-100/ID/lien", "Supprimer des messages"),
        ("nuke", "Reset du salon"), ("lock #salon/ID", "Verrouiller un salon"),
        ("unlock #salon/ID", "Déverrouiller un salon"), ("slowmode #salon/ID temps", "Mode lent"),
        ("softban @user/ID", "Ban puis déban (supprime les messages 24h)"),
        ("warn @user raison", "Avertir"), ("warns @user", "Voir les warns"),
        ("clearwarns @user", "Effacer warns + strikes"), ("wl", "Whitelist du serveur")]),
    "Vocal & Rôles": ("🎙️", [
        ("moov @user/ID #vocal/ID/lien", "Déplacer un membre en vocal"),
        ("disconnect @user/ID", "Déconnecter du vocal"), ("vocmute @user/ID", "Mute vocal"),
        ("vocunmute @user/ID", "Unmute vocal"), ("mutecasque @user/ID", "Couper le casque"),
        ("unmutecasque @user/ID", "Rétablir le casque"), ("nickname @user/ID pseudo", "Changer un pseudo"),
        ("roleadd @user/ID @role/ID", "Ajouter des rôles (10 max)"),
        ("roleremove @user/ID @role/ID", "Retirer des rôles (10 max)"),
        ("derank @user/ID", "Retirer tous les rôles")]),
    "Automod": ("🤖", [
        ("automod", "Voir la config de l'automod du bot"), ("automod on/off", "Activer / désactiver"),
        ("automod toggle <module>", "Activer un module"),
        ("automod set <module> <clé> <val>", "Régler les seuils"),
        ("automod badword add/remove <mot>", "Mots interdits"), ("automod logs #salon", "Salon de logs"),
        ("automod ignore #salon/@role", "Exceptions"),
        ("automodnatif", "AutoMod natif de Discord (mentions, spam, insultes, invites, liens)"),
        ("antiraid on/off", "Anti-raid")]),
    "Staff du bot": ("⛔", [
        ("blacklist add/remove/info/list/export", "Blacklist utilisateurs (alias bl)"),
        ("bl server add/remove <id>", "Blacklist serveurs"), ("bl autoban on/off", "Ban auto des blacklist"),
        ("setsos #salon", "Salon SOS (support)"), ("setraid #salon", "Salon RAID (support)"),
        ("setreport #salon", "Salon des signalements (support)"),
        ("preuve", "Prouver que tu es staff du support"), ("verifpreuve code", "Vérifier une preuve"),
        ("backup", "Reçois data.json en MP (fondateurs)"),
        ("restore", "Restaurer data.json, fichier joint (fondateurs)"),
        ("panel", "Panel staff interactif (support uniquement)"), ("serveurs", "Liste des serveurs du bot"), ("quitter <id>", "Faire quitter un serveur")]),
    "Tickets": ("🎫", [
        ("ticket setup [#salon]", "Envoyer le panneau de tickets"), ("ticket staff @role", "Ajouter/retirer un rôle staff"),
        ("ticket logs #salon", "Salon des transcripts"), ("ticket category <catégorie>", "Catégorie des tickets"),
        ("ticket add @user", "Ajouter quelqu'un au ticket"), ("ticket remove @user", "Retirer quelqu'un du ticket"),
        ("ticket rename <nom>", "Renommer le ticket"), ("ticket close", "Fermer le ticket (transcript)"),
        ("ticket list", "Tickets ouverts")]),
    "Arrivées & Config": ("⚙️", [
        ("config", "Voir la configuration du serveur"), ("config welcome #salon [message]", "Message d'arrivée"),
        ("config leave #salon [message]", "Message de départ"), ("config test welcome|leave", "Tester les messages"),
        ("config autorole @role", "Rôle donné à l'arrivée"), ("config suggest #salon", "Salon des suggestions"),
        ("config logs #salon", "Logs automod / anti-raid"), ("config off <clé>", "Désactiver (suggest, welcome, leave, autorole)")]),
    "Automobile": ("🚗", [
        ("concessionnaire", "Catalogue des véhicules (alias concession)"), ("acheter <clé>", "Acheter"), ("garage", "Tes véhicules"),
        ("conduire <id>", "Choisir le véhicule actif"), ("plein", "Faire le plein"),
        ("reparer", "Réparer"), ("vendre <id>", "Vendre"), ("rouler [km]", "Rouler (radar, accidents…)"),
        ("permis / permis passer", "Voir / passer le permis"), ("retraitpermis @user", "Retirer le permis (staff)"),
        ("amende @user montant motif", "Mettre une amende (staff)"), ("amendes", "Tes amendes"),
        ("payer <id>", "Payer une amende")]),
    "Économie & Identité": ("💼", [
        ("cni prénom nom âge", "Créer ton identité"), ("macni [@user]", "Carte d'identité"),
        ("solde [@user]", "Argent"), ("deposer / retirer <montant>", "Banque"),
        ("donner @user montant", "Virement"), ("metier [nom]", "Voir / choisir un métier"),
        ("travail", "Travailler (30 min)"), ("daily", "Récompense quotidienne"),
        ("pari montant", "Casino"), ("classement", "Les plus riches")]),
    "Roleplay": ("🎭", [
        ("me action", "Action RP"), ("do description", "Description RP"),
        ("17 / 18 / 15 message", "Appeler police / pompiers / SAMU"),
        ("setservice police|pompier|samu @role", "Rôle ping des services"),
        ("casier [@user]", "Casier judiciaire"), ("ajoutcasier @user motif", "Ajouter au casier (staff)"),
        ("effacercasier @user", "Effacer le casier (staff)"),
        ("arrestation @user motif", "Arrêter quelqu'un (Policier/Gendarme)"),
        ("fouille @user", "Fouiller (Policier/Gendarme)"), ("braquage @user", "Braquer un joueur (risqué !)"),
        ("annonce texte", "Publier une annonce")]),
    "Fun": ("🎉", [
        ("avatar [@user]", "Photo de profil"), ("pileouface", "Pile ou face"), ("8ball question", "Boule magique"),
        ("des [faces]", "Lancer de dé"), ("sondage question", "Sondage 👍/👎")]),
}

def documented():
    txt = " ".join(c for _, (_, rows) in HELP.items() for c, _d in rows).lower()
    txt = "".join(ch for ch in unicodedata.normalize("NFD", txt) if unicodedata.category(ch) != "Mn")
    return set(re.findall(r"[a-z0-9]+", txt))

def categories(user):
    """Catégories visibles (le staff du bot voit en plus sa catégorie). 'Autres' = filet de sécurité automatique."""
    cats = {k: v for k, v in HELP.items() if k != "Staff du bot" or is_staff_member(user)}
    doc = documented()
    extra = sorted(c.name for c in bot.commands if c.name not in doc)
    if extra:
        cats["Autres"] = ("📦", [(n, bot.get_command(n).short_doc or "—") for n in extra])
    return cats

SEP = "━━━━━━━━━━━━━━━━━━━━"

def help_embed(name, user):
    cats = categories(user)
    if name not in cats:
        name = "Accueil"
    if name == "Accueil":
        total = sum(len(v[1]) for v in cats.values())
        lines = "\n".join(f"{v[0]} **{k}** — {len(v[1])} commande(s)" for k, v in cats.items())
        e = discord.Embed(title=f"📖 {BOT_NAME} — Centre d'aide", color=COLOR,
                          description=f"Choisis une catégorie dans le menu ci-dessous.\n{SEP}\n{lines}\n{SEP}\n"
                                      f"🔹 Préfixe : `RP!` · `rp!` · `Rp!`\n🔹 Urgence : `RP!sos <motif>`\n🔹 Support : `RP!support`")
        e.set_footer(text=f"{total} commandes au total • {SUPPORT_NAME}")
    else:
        emo, rows = cats[name]
        e = discord.Embed(title=f"{emo} {name}", color=COLOR,
                          description=SEP + "\n" + "\n".join(f"▸ `RP!{c}` → {d}" for c, d in rows))
        e.set_footer(text="Préfixe : RP! · rp! · Rp!  |  Menu ci-dessous pour changer de catégorie")
    if SUPPORT_LOGO:
        e.set_thumbnail(url=SUPPORT_LOGO)
    return e

class HelpView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=180)
        self.user = user
        opts = [discord.SelectOption(label="Accueil", emoji="🏠", value="Accueil")]
        opts += [discord.SelectOption(label=n, emoji=v[0], value=n) for n, v in categories(user).items()]
        sel = discord.ui.Select(placeholder="📂 Choisis une catégorie", options=opts[:25])
        sel.callback = self.on_select
        self.add_item(sel)

    async def interaction_check(self, inter):
        if inter.user.id != self.user.id:
            await inter.response.send_message("Fais ta propre commande `RP!help`.", ephemeral=True)
            return False
        return True

    async def on_select(self, inter):
        await inter.response.edit_message(embed=help_embed(inter.data["values"][0], self.user), view=self)

@bot.command(name="help", aliases=["aide", "h"])
async def help_cmd(ctx):
    await ctx.send(embed=help_embed("Accueil", ctx.author), view=HelpView(ctx.author))

# ═══════════════════════ OUTILS ═══════════════════════
NEWS = [
    "🆕 Menu d'aide par catégories (`RP!help`)",
    "🆕 Commandes vocales, rôles, nuke, softban, whitelist",
    "🆕 AutoMod natif Discord (`RP!automodnatif`)",
    "🆕 Signalements avec preuve image (`RP!report`)",
    "🆕 Braquage, arrestation, fouille, casino, daily",
]

def parse_duration(s):
    m = re.fullmatch(r"(\d+)\s*([smhdj]?)", s.lower().strip())
    if not m:
        return None
    return int(m[1]) * {"": 60, "s": 1, "m": 60, "h": 3600, "d": 86400, "j": 86400}[m[2]]

def is_boss(ctx):
    return ctx.author.id in OWNER_IDS or ctx.author == ctx.guild.owner

def can_act(ctx, target):
    return is_boss(ctx) or target.top_role < ctx.author.top_role

def assignable(ctx, role):
    return (not role.is_default() and not role.managed and role < ctx.guild.me.top_role
            and (is_boss(ctx) or role < ctx.author.top_role))

class Confirm(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=30)
        self.author, self.value = author, None

    async def interaction_check(self, inter):
        if inter.user.id != self.author.id:
            await inter.response.send_message("Ce n'est pas pour toi.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.danger)
    async def yes(self, inter, button):
        self.value = True
        await inter.response.defer()
        self.stop()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def no(self, inter, button):
        self.value = False
        await inter.response.defer()
        self.stop()

# ═══════════════════════ MODÉRATION (suite) ═══════════════════════
@bot.command(name="timeout", aliases=["mute", "tempmute"])
@commands.guild_only()
@commands.has_permissions(moderate_members=True)
async def timeout_cmd(ctx, member: discord.Member, temps: str, *, raison: str = "Non précisée"):
    s = parse_duration(temps)
    if not s or s > 2419200:
        return await ctx.send(embed=err("Durée invalide (ex : `10m`, `2h`, `1d` — 28 jours max)."))
    if not can_act(ctx, member):
        return await ctx.send(embed=err("Tu ne peux pas sanctionner ce membre (hiérarchie)."))
    await member.timeout(timedelta(seconds=s), reason=f"{ctx.author} : {raison}")
    await ctx.send(embed=emb("🔇 Timeout", f"{member.mention} — **{temps}** — {raison}", WARN))

@bot.command(name="untimeout", aliases=["unmute"])
@commands.guild_only()
@commands.has_permissions(moderate_members=True)
async def untimeout(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(embed=emb("🔊 Timeout retiré", member.mention, OK))

@bot.command(name="clear", aliases=["purge"])
@commands.guild_only()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, cible: str):
    """clear 1-100 | clear <ID message> | clear <lien message>"""
    if cible.isdigit() and 1 <= int(cible) <= 100:
        deleted = await ctx.channel.purge(limit=int(cible) + 1)
    else:
        m = re.search(r"(\d{17,20})/?\s*$", cible)
        if not m:
            return await ctx.send(embed=err("Utilise un nombre (1-100), un ID de message ou un lien de message."))
        deleted = await ctx.channel.purge(limit=500, after=discord.Object(id=int(m[1])))
    await ctx.send(embed=emb("🧹 Nettoyage", f"{max(0, len(deleted) - 1)} message(s) supprimé(s).", OK), delete_after=5)

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_channels=True)
async def nuke(ctx):
    v = Confirm(ctx.author)
    m = await ctx.send(embed=emb("☢️ Nuke", "Le salon sera **recréé à l'identique** (tous les messages disparaissent). Confirmer ?", WARN), view=v)
    await v.wait()
    if not v.value:
        return await m.edit(embed=emb("Annulé", color=KO), view=None)
    old = ctx.channel
    new = await old.clone(reason=f"Nuke par {ctx.author}")
    await new.edit(position=old.position)
    await old.delete()
    await new.send(embed=emb("☢️ Salon nuke", f"Par {ctx.author.mention}", OK))

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: Optional[discord.TextChannel] = None):
    ch = channel or ctx.channel
    await ch.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(embed=emb("🔒 Salon verrouillé", ch.mention, KO))

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: Optional[discord.TextChannel] = None):
    ch = channel or ctx.channel
    await ch.set_permissions(ctx.guild.default_role, send_messages=None)
    await ctx.send(embed=emb("🔓 Salon déverrouillé", ch.mention, OK))

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, channel: Optional[discord.TextChannel] = None, temps: str = "0"):
    ch = channel or ctx.channel
    s = 0 if temps in ("0", "off") else (int(temps) if temps.isdigit() else parse_duration(temps))
    if s is None or s > 21600:
        return await ctx.send(embed=err("Temps invalide (ex : `5`, `30s`, `2m`, max 6h)."))
    await ch.edit(slowmode_delay=s)
    await ctx.send(embed=emb("🐢 Slowmode", f"{ch.mention} : **{s}s**", OK))

@bot.command()
@commands.guild_only()
@commands.has_permissions(ban_members=True)
async def softban(ctx, user: discord.User, *, raison: str = "Softban"):
    await ctx.guild.ban(user, delete_message_seconds=86400, reason=f"{ctx.author} : {raison}")
    await ctx.guild.unban(user, reason="Softban")
    await ctx.send(embed=emb("🧹 Softban", f"{user} — messages des dernières 24h supprimés.", WARN))

@bot.group(name="wl", aliases=["whitelist"], invoke_without_command=True)
@commands.guild_only()
@commands.has_permissions(administrator=True)
async def wl(ctx):
    ids = gcfg(ctx.guild.id)["whitelist"]
    txt = "\n".join(f"<@{i}> (`{i}`)" for i in ids) or "Personne."
    await ctx.send(embed=emb("✅ Whitelist (ignorée par l'automod et l'anti-raid)", txt + "\n\n`RP!wl add <@/id>` · `RP!wl remove <@/id>`"))

@wl.command(name="add")
async def wl_add(ctx, user: discord.User):
    w = gcfg(ctx.guild.id)["whitelist"]
    if user.id not in w:
        w.append(user.id)
    db.save()
    await ctx.send(embed=emb("✅ Whitelist", f"{user} ajouté.", OK))

@wl.command(name="remove", aliases=["del"])
async def wl_remove(ctx, user: discord.User):
    w = gcfg(ctx.guild.id)["whitelist"]
    if user.id in w:
        w.remove(user.id)
    db.save()
    await ctx.send(embed=emb("✅ Whitelist", f"{user} retiré.", OK))

# ═══════════════════════ VOCAL & RÔLES ═══════════════════════
@bot.command(aliases=["move"])
@commands.guild_only()
@commands.has_permissions(move_members=True)
async def moov(ctx, member: discord.Member, channel: discord.VoiceChannel):
    if not member.voice:
        return await ctx.send(embed=err("Ce membre n'est pas en vocal."))
    await member.move_to(channel)
    await ctx.send(embed=emb("🎙️ Déplacé", f"{member.mention} → {channel.mention}", OK))

@bot.command()
@commands.guild_only()
@commands.has_permissions(move_members=True)
async def disconnect(ctx, member: discord.Member):
    if not member.voice:
        return await ctx.send(embed=err("Ce membre n'est pas en vocal."))
    await member.move_to(None)
    await ctx.send(embed=emb("🔌 Déconnecté du vocal", member.mention, WARN))

async def voice_flag(ctx, member, **kw):
    if not member.voice:
        return await ctx.send(embed=err("Ce membre n'est pas en vocal."))
    await member.edit(**kw)
    await ctx.send(embed=emb("🎙️ Vocal mis à jour", member.mention, OK))

@bot.command()
@commands.guild_only()
@commands.has_permissions(mute_members=True)
async def vocmute(ctx, member: discord.Member):
    await voice_flag(ctx, member, mute=True)

@bot.command()
@commands.guild_only()
@commands.has_permissions(mute_members=True)
async def vocunmute(ctx, member: discord.Member):
    await voice_flag(ctx, member, mute=False)

@bot.command()
@commands.guild_only()
@commands.has_permissions(deafen_members=True)
async def mutecasque(ctx, member: discord.Member):
    await voice_flag(ctx, member, deafen=True)

@bot.command()
@commands.guild_only()
@commands.has_permissions(deafen_members=True)
async def unmutecasque(ctx, member: discord.Member):
    await voice_flag(ctx, member, deafen=False)

@bot.command(aliases=["nick"])
@commands.guild_only()
@commands.has_permissions(manage_nicknames=True)
async def nickname(ctx, member: discord.Member, *, pseudo: str):
    if not can_act(ctx, member):
        return await ctx.send(embed=err("Hiérarchie insuffisante."))
    await member.edit(nick=None if pseudo.lower() in ("reset", "aucun") else pseudo[:32])
    await ctx.send(embed=emb("✏️ Pseudo modifié", member.mention, OK))

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_roles=True)
async def roleadd(ctx, member: discord.Member, roles: commands.Greedy[discord.Role]):
    ok = [r for r in roles[:10] if assignable(ctx, r)]
    if not ok:
        return await ctx.send(embed=err("Aucun rôle valide (hiérarchie, rôle géré ou @everyone)."))
    await member.add_roles(*ok, reason=f"RP!roleadd par {ctx.author}")
    await ctx.send(embed=emb("✅ Rôles ajoutés", f"{member.mention} : " + " ".join(r.mention for r in ok), OK))

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_roles=True)
async def roleremove(ctx, member: discord.Member, roles: commands.Greedy[discord.Role]):
    ok = [r for r in roles[:10] if assignable(ctx, r)]
    if not ok:
        return await ctx.send(embed=err("Aucun rôle valide (hiérarchie, rôle géré ou @everyone)."))
    await member.remove_roles(*ok, reason=f"RP!roleremove par {ctx.author}")
    await ctx.send(embed=emb("✅ Rôles retirés", f"{member.mention} : " + " ".join(r.mention for r in ok), WARN))

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_roles=True)
async def derank(ctx, member: discord.Member):
    if not can_act(ctx, member):
        return await ctx.send(embed=err("Hiérarchie insuffisante."))
    roles = [r for r in member.roles if assignable(ctx, r)]
    if roles:
        await member.remove_roles(*roles, reason=f"RP!derank par {ctx.author}")
    await ctx.send(embed=emb("⬇️ Derank", f"{member.mention} : {len(roles)} rôle(s) retiré(s).", WARN))

# ═══════════════════════ AUTOMOD NATIF DISCORD ═══════════════════════
async def make_rule(ctx, name, trigger):
    await ctx.guild.create_automod_rule(
        name=f"RP | {name}", event_type=discord.AutoModRuleEventType.message_send, trigger=trigger,
        actions=[discord.AutoModRuleAction(type=discord.AutoModRuleActionType.block_message)],
        enabled=True, reason=f"RP!automodnatif par {ctx.author}")
    await ctx.send(embed=emb("✅ Règle AutoMod créée", f"**RP | {name}**", OK))

@bot.group(name="automodnatif", aliases=["nautomod"], invoke_without_command=True)
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def automodnatif(ctx):
    await ctx.send(embed=emb("🤖 AutoMod natif Discord",
        "`RP!automodnatif mentions [limite]`\n`RP!automodnatif spam`\n`RP!automodnatif insultes`\n"
        "`RP!automodnatif invites`\n`RP!automodnatif liens`\n`RP!automodnatif list`\n`RP!automodnatif clear` (supprime les règles RP)"))

@automodnatif.command(name="mentions")
async def an_mentions(ctx, limite: int = 5):
    await make_rule(ctx, "Mentions", discord.AutoModTrigger(
        type=discord.AutoModRuleTriggerType.mention_spam, mention_limit=max(1, min(limite, 50))))

@automodnatif.command(name="spam")
async def an_spam(ctx):
    await make_rule(ctx, "Spam", discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.spam))

@automodnatif.command(name="insultes")
async def an_insultes(ctx):
    await make_rule(ctx, "Insultes", discord.AutoModTrigger(
        type=discord.AutoModRuleTriggerType.keyword_preset,
        presets=discord.AutoModPresets(profanity=True, sexual_content=True, slurs=True)))

@automodnatif.command(name="invites")
async def an_invites(ctx):
    await make_rule(ctx, "Invitations", discord.AutoModTrigger(
        type=discord.AutoModRuleTriggerType.keyword, keyword_filter=["*discord.gg/*", "*discord.com/invite/*"]))

@automodnatif.command(name="liens")
async def an_liens(ctx):
    await make_rule(ctx, "Liens", discord.AutoModTrigger(
        type=discord.AutoModRuleTriggerType.keyword, keyword_filter=["*http://*", "*https://*"]))

@automodnatif.command(name="list")
async def an_list(ctx):
    rules = await ctx.guild.fetch_automod_rules()
    txt = "\n".join(f"{'🟢' if r.enabled else '🔴'} {r.name}" for r in rules) or "Aucune règle."
    await ctx.send(embed=emb("🤖 Règles AutoMod du serveur", txt))

@automodnatif.command(name="clear")
async def an_clear(ctx):
    n = 0
    for r in await ctx.guild.fetch_automod_rules():
        if r.name.startswith("RP | "):
            await r.delete(reason=f"RP!automodnatif clear par {ctx.author}")
            n += 1
    await ctx.send(embed=emb("🗑️ Règles supprimées", f"{n} règle(s) RP supprimée(s).", OK))

# ═══════════════════════ GÉNÉRAL ═══════════════════════
@bot.command(aliases=["bi", "stats"])
async def botinfo(ctx):
    e = emb(f"🤖 {bot.user.name}")
    e.add_field(name="Serveurs", value=len(bot.guilds)).add_field(name="Utilisateurs", value=sum(g.member_count or 0 for g in bot.guilds))
    e.add_field(name="Ping", value=f"{round(bot.latency * 1000)} ms").add_field(name="Uptime", value=str(timedelta(seconds=int(time.time() - START))))
    e.add_field(name="Commandes", value=len(bot.commands)).add_field(name="discord.py", value=discord.__version__)
    e.set_thumbnail(url=bot.user.display_avatar.url)
    await ctx.send(embed=e)

@bot.command(aliases=["ui", "whois"])
async def userinfo(ctx, user: Optional[discord.User] = None):
    user = user or ctx.author
    e = emb(f"👤 {user}")
    e.set_thumbnail(url=user.display_avatar.url)
    e.add_field(name="ID", value=f"`{user.id}`").add_field(name="Compte créé", value=discord.utils.format_dt(user.created_at, "R"))
    e.add_field(name="Bot", value="Oui" if user.bot else "Non")
    m = ctx.guild.get_member(user.id) if ctx.guild else None
    if m:
        e.add_field(name="Arrivé", value=discord.utils.format_dt(m.joined_at, "R") if m.joined_at else "?")
        e.add_field(name="Rôle principal", value=m.top_role.mention).add_field(name="Rôles", value=len(m.roles) - 1)
    if is_staff_member(ctx.author):
        b = db.data["blacklist"]["users"].get(str(user.id))
        e.add_field(name="⛔ Blacklist bot", value=f"Oui — {b['reason']}" if b else "Non", inline=False)
    await ctx.send(embed=e)

@bot.command(aliases=["si"])
@commands.guild_only()
async def serverinfo(ctx):
    g = ctx.guild
    e = emb(f"🏰 {g.name}")
    if g.icon:
        e.set_thumbnail(url=g.icon.url)
    e.add_field(name="ID", value=f"`{g.id}`").add_field(name="Propriétaire", value=f"<@{g.owner_id}>")
    e.add_field(name="Membres", value=g.member_count).add_field(name="Salons", value=len(g.channels))
    e.add_field(name="Rôles", value=len(g.roles)).add_field(name="Boosts", value=g.premium_subscription_count)
    e.add_field(name="Créé", value=discord.utils.format_dt(g.created_at, "R"))
    await ctx.send(embed=e)

@bot.command()
async def invite(ctx):
    url = discord.utils.oauth_url(bot.user.id, permissions=discord.Permissions(administrator=True),
                                  scopes=("bot", "applications.commands"))
    await ctx.send(embed=emb("📨 Inviter le bot", f"[Clique ici pour m'ajouter]({url})", OK))

@bot.command()
async def support(ctx):
    url = SUPPORT_INVITE
    if not url and bot.get_guild(SUPPORT_GUILD_ID):
        url = await get_invite(bot.get_guild(SUPPORT_GUILD_ID))
    await ctx.send(embed=emb(f"🆘 {SUPPORT_NAME}", f"[Rejoindre le support]({url})" if url else "Lien indisponible pour le moment.", COLOR))

@bot.group(invoke_without_command=True)
@commands.guild_only()
async def antiraid(ctx):
    r = gcfg(ctx.guild.id)["automod"]["raid"]
    e = emb(f"🚨 Anti-raid — {'✅ ACTIF' if r['on'] else '❌ INACTIF'}",
            f"Seuil : **{r['joins']} arrivées en {r['seconds']}s**\nSanction : **{r['action']}**\n"
            f"Modifier : `RP!automod set raid joins 10`", OK if r["on"] else KO)
    await ctx.send(embed=e)

@antiraid.command(name="on")
@commands.has_permissions(manage_guild=True)
async def antiraid_on(ctx):
    gcfg(ctx.guild.id)["automod"]["raid"]["on"] = True
    db.save()
    await ctx.send(embed=emb("✅ Anti-raid activé", color=OK))

@antiraid.command(name="off")
@commands.has_permissions(manage_guild=True)
async def antiraid_off(ctx):
    gcfg(ctx.guild.id)["automod"]["raid"]["on"] = False
    db.save()
    await ctx.send(embed=emb("❌ Anti-raid désactivé", color=KO))

@bot.command()
@commands.guild_only()
@commands.cooldown(1, 300, commands.BucketType.guild)
async def raidalert(ctx, *, details: str = "Raid en cours sur le serveur"):
    ch = bot.get_channel(db.data.get("raid_channel") or 0)
    if not ch:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(embed=err("Le salon RAID n'est pas configuré dans le support du bot."))
    e = emb("🚨 Alerte RAID (manuelle)", color=KO)
    e.add_field(name="👤 Déclenchée par", value=f"{ctx.author.mention} (`{ctx.author.id}`)", inline=False)
    e.add_field(name="🏰 Serveur", value=f"{ctx.guild.name} (`{ctx.guild.id}`)", inline=False)
    e.add_field(name="📝 Détails", value=details[:900], inline=False)
    e.add_field(name="📌 Statut", value="⏳ En attente", inline=False)
    e.timestamp = discord.utils.utcnow()
    await ch.send(embed=e, view=AlertView(await get_invite(ctx.guild, ctx.channel), label="Invitation serveur"))
    await ctx.send(embed=emb("🚨 Alerte raid envoyée", "Le staff du support a été prévenu.", OK))

@bot.command()
@commands.guild_only()
@commands.cooldown(1, 60, commands.BucketType.user)
async def suggest(ctx, *, suggestion: str):
    ch = ctx.guild.get_channel(gcfg(ctx.guild.id)["config"]["suggest"] or 0)
    if not ch:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(embed=err("Aucun salon de suggestions. Un admin doit faire `RP!config suggest #salon`."))
    e = emb("💡 Suggestion", suggestion[:1800], COLOR)
    e.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
    m = await ch.send(embed=e)
    await m.add_reaction("✅")
    await m.add_reaction("❌")
    await ctx.send(embed=emb("✅ Suggestion envoyée", ch.mention, OK))

@bot.command(name="setreport")
@commands.guild_only()
@support_only()
async def setreport(ctx, channel: discord.TextChannel):
    db.data["report_channel"] = channel.id
    db.save()
    await ctx.send(embed=emb("✅ Salon des signalements configuré", channel.mention, OK))

@bot.command()
@commands.guild_only()
@commands.cooldown(1, 120, commands.BucketType.user)
async def report(ctx, user: discord.User, *, raison: str):
    ch = bot.get_channel(db.data.get("report_channel") or 0)
    img = next((a for a in ctx.message.attachments if (a.content_type or "").startswith("image")), None)
    if not ch or not img:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(embed=err("Salon de signalements non configuré." if not ch else "Joins une **image de preuve** à ta commande."))
    f = await img.to_file(filename="preuve." + (img.filename.rsplit(".", 1)[-1] if "." in img.filename else "png"))
    e = emb("📢 Signalement", color=0xE74C3C)
    e.add_field(name="🎯 Signalé", value=f"{user} (`{user.id}`)", inline=False)
    e.add_field(name="👤 Par", value=f"{ctx.author.mention} (`{ctx.author.id}`)", inline=False)
    e.add_field(name="🏰 Serveur", value=f"{ctx.guild.name} (`{ctx.guild.id}`)", inline=False)
    e.add_field(name="📝 Raison", value=raison[:900], inline=False)
    e.add_field(name="📌 Statut", value="⏳ En attente", inline=False)
    e.set_image(url=f"attachment://{f.filename}")
    e.timestamp = discord.utils.utcnow()
    await ch.send(embed=e, file=f, view=AlertView(await get_invite(ctx.guild, ctx.channel)))
    await ctx.send(embed=emb("✅ Signalement envoyé", "Merci, le staff va l'examiner.", OK))

@bot.command()
async def client(ctx):
    sid = ctx.guild.shard_id if ctx.guild else 0
    e = emb("🧩 Shard", f"Ce serveur tourne sur la shard **#{sid}** / {bot.shard_count or 1}\nPing : **{round(bot.latency * 1000)} ms**")
    await ctx.send(embed=e)

@bot.command()
async def contact(ctx):
    url = SUPPORT_INVITE or "via `RP!support`"
    owners = " ".join(f"<@{i}>" for i in OWNER_IDS if i)
    await ctx.send(embed=emb("📬 Contacter l'équipe", f"Support : {url}\nFondateur(s) : {owners or '—'}\nUrgence : `RP!sos <motif>`"))

@bot.command()
async def news(ctx):
    await ctx.send(embed=emb("📰 Dernières nouveautés", "\n".join(NEWS)))

@bot.group(name="config", invoke_without_command=True)
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def config(ctx):
    c = gcfg(ctx.guild.id)["config"]
    t = gcfg(ctx.guild.id)["tickets"]
    def ch(i): return f"<#{i}>" if i else "❌ non défini"
    e = emb("⚙️ Configuration du serveur", "Modifie avec `RP!config <option>`")
    e.add_field(name="👋 Arrivées", value=ch(c["welcome"])).add_field(name="🚪 Départs", value=ch(c["leave"]))
    e.add_field(name="🎭 Autorôle", value=f"<@&{c['autorole']}>" if c["autorole"] else "❌ non défini")
    e.add_field(name="💡 Suggestions", value=ch(c["suggest"]))
    e.add_field(name="📜 Logs automod", value=ch(gcfg(ctx.guild.id)["automod"]["log_channel"]))
    e.add_field(name="🎫 Tickets", value=f"{len(t['staff_roles'])} rôle(s) staff · logs {ch(t['logs'])}")
    e.add_field(name="Variables des messages", value="`{user}` `{name}` `{server}` `{count}`", inline=False)
    e.set_footer(text="config welcome|leave|suggest|logs #salon · config autorole @role · config test welcome|leave · config off <clé>")
    await ctx.send(embed=e)

@config.command(name="leave")
async def cfg_leave(ctx, channel: discord.TextChannel, *, message: str = None):
    c = gcfg(ctx.guild.id)["config"]
    c["leave"] = channel.id
    if message:
        c["leave_msg"] = message[:500]
    db.save()
    await ctx.send(embed=emb("✅ Message de départ", f"{channel.mention}\n{c['leave_msg']}", OK))

@config.command(name="test")
async def cfg_test(ctx, kind: str = "welcome"):
    if kind.lower() in ("leave", "depart", "départ"):
        await leave_listener(ctx.author)
    else:
        await welcome_listener(ctx.author)
    await ctx.send(embed=emb("🧪 Test envoyé", "Regarde dans le salon configuré.", OK), delete_after=6)


@config.command(name="suggest")
async def cfg_suggest(ctx, channel: discord.TextChannel):
    gcfg(ctx.guild.id)["config"]["suggest"] = channel.id
    db.save()
    await ctx.send(embed=emb("✅ Salon de suggestions", channel.mention, OK))

@config.command(name="logs")
async def cfg_logs(ctx, channel: discord.TextChannel):
    gcfg(ctx.guild.id)["automod"]["log_channel"] = channel.id
    db.save()
    await ctx.send(embed=emb("✅ Salon de logs automod / anti-raid", channel.mention, OK))

@config.command(name="welcome")
async def cfg_welcome(ctx, channel: discord.TextChannel, *, message: str = None):
    c = gcfg(ctx.guild.id)["config"]
    c["welcome"] = channel.id
    if message:
        c["welcome_msg"] = message[:500]
    db.save()
    await ctx.send(embed=emb("✅ Message de bienvenue", f"{channel.mention}\n{c['welcome_msg']}\n\nVariables : `{{user}}` `{{server}}` `{{count}}`", OK))

@config.command(name="autorole")
async def cfg_autorole(ctx, role: discord.Role):
    if not assignable(ctx, role):
        return await ctx.send(embed=err("Je ne peux pas (ou tu ne peux pas) attribuer ce rôle."))
    gcfg(ctx.guild.id)["config"]["autorole"] = role.id
    db.save()
    await ctx.send(embed=emb("✅ Autorôle", role.mention, OK))

@config.command(name="off")
async def cfg_off(ctx, cle: str):
    c = gcfg(ctx.guild.id)["config"]
    if cle.lower() not in ("suggest", "welcome", "leave", "autorole"):
        return await ctx.send(embed=err("Clés : suggest, welcome, leave, autorole."))
    c[cle.lower()] = None
    db.save()
    await ctx.send(embed=emb("✅ Désactivé", cle, OK))

def fmt_msg(txt, member):
    return (txt.replace("{user}", member.mention).replace("{name}", member.display_name)
            .replace("{server}", member.guild.name).replace("{count}", str(member.guild.member_count)))

@bot.listen("on_member_join")
async def welcome_listener(member):
    c = gcfg(member.guild.id)["config"]
    if c["autorole"]:
        role = member.guild.get_role(c["autorole"])
        if role:
            try:
                await member.add_roles(role, reason="Autorôle")
            except discord.HTTPException:
                pass
    ch = member.guild.get_channel(c["welcome"] or 0)
    if ch:
        e = discord.Embed(title="👋 Bienvenue !", description=fmt_msg(c["welcome_msg"], member), color=OK,
                          timestamp=discord.utils.utcnow())
        e.set_author(name=member.guild.name, icon_url=member.guild.icon.url if member.guild.icon else None)
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="🗓️ Compte créé", value=discord.utils.format_dt(member.created_at, "R"))
        e.set_footer(text=f"Membre n°{member.guild.member_count}")
        try:
            await ch.send(content=member.mention, embed=e, allowed_mentions=discord.AllowedMentions(users=True))
        except discord.HTTPException:
            pass

@bot.listen("on_member_remove")
async def leave_listener(member):
    if member.bot:
        return
    c = gcfg(member.guild.id)["config"]
    ch = member.guild.get_channel(c["leave"] or 0)
    if ch:
        e = discord.Embed(title="🚪 Départ", description=fmt_msg(c["leave_msg"], member), color=KO,
                          timestamp=discord.utils.utcnow())
        e.set_thumbnail(url=member.display_avatar.url)
        if member.joined_at:
            e.add_field(name="⏳ Était là depuis", value=discord.utils.format_dt(member.joined_at, "R"))
        e.set_footer(text=f"{member.guild.member_count} membres restants")
        try:
            await ch.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            pass

# ═══════════════════════ ROLEPLAY (suite) ═══════════════════════
def law_only():
    def pred(ctx):
        if ctx.guild and (ctx.author.guild_permissions.manage_messages or udata(ctx.author.id)["job"] in ("Policier", "Gendarme")):
            return True
        raise commands.CheckFailure("Réservé aux **Policiers / Gendarmes** (`RP!metier`) ou au staff.")
    return commands.check(pred)

@bot.command()
@commands.guild_only()
@law_only()
async def arrestation(ctx, cible: discord.Member, *, motif: str):
    udata(cible.id)["casier"].append({"motif": motif, "by": ctx.author.display_name, "date": int(time.time())})
    db.save()
    e = emb("🚔 Arrestation", f"{cible.mention} est placé en garde à vue.\n**Motif :** {motif}\n**Par :** {ctx.author.mention}", KO)
    await ctx.send(embed=e)

@bot.command()
@commands.guild_only()
@law_only()
async def fouille(ctx, cible: discord.Member):
    t = udata(cible.id)
    e = emb(f"🔎 Fouille de {cible.display_name}")
    e.add_field(name="Liquide", value=money(t["money"])).add_field(name="Véhicules", value=len(t["cars"]))
    e.add_field(name="Amendes impayées", value=len([f for f in t["fines"] if not f["paid"]])).add_field(name="Casier", value=f"{len(t['casier'])} entrée(s)")
    e.add_field(name="Permis", value="✅" if t["permis"]["valid"] else "❌")
    await ctx.send(embed=e)

@bot.command(aliases=["rob"])
@commands.guild_only()
@commands.cooldown(1, 3600, commands.BucketType.user)
async def braquage(ctx, cible: discord.Member):
    u, t = udata(ctx.author.id), udata(cible.id)
    if cible.bot or cible == ctx.author or not u["identity"] or t["money"] < 500:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(embed=err("Braquage impossible (identité requise, cible valide avec au moins 500 € en liquide)."))
    if random.random() < 0.4:
        stolen = min(int(t["money"] * random.uniform(0.1, 0.3)), 5000)
        t["money"] -= stolen
        u["money"] += stolen
        res = emb("🔫 Braquage réussi", f"{ctx.author.mention} dérobe **{money(stolen)}** à {cible.mention} !", WARN)
    else:
        add_fine(u, 1000, "Tentative de braquage", "Police")
        u["casier"].append({"motif": "Tentative de braquage", "by": "Police", "date": int(time.time())})
        res = emb("🚔 Braquage raté", f"{ctx.author.mention} se fait arrêter ! Amende de 1 000 € + casier.", KO)
    db.save()
    await ctx.send(embed=res)

# ═══════════════════════ ÉCONOMIE / FUN (suite) ═══════════════════════
@bot.command()
async def daily(ctx):
    u = udata(ctx.author.id)
    now = int(time.time())
    left = u.get("last_daily", 0) + 86400 - now
    if left > 0:
        return await ctx.send(embed=err(f"Reviens <t:{now + left}:R>."))
    gain = random.randint(400, 900)
    u["money"] += gain
    u["last_daily"] = now
    db.save()
    await ctx.send(embed=emb("🎁 Récompense quotidienne", f"Tu gagnes **{money(gain)}**.", OK))

@bot.command(aliases=["casino", "bet"])
@commands.cooldown(1, 10, commands.BucketType.user)
async def pari(ctx, montant: int):
    u = udata(ctx.author.id)
    if not 0 < montant <= min(u["money"], 50000):
        ctx.command.reset_cooldown(ctx)
        return await ctx.send(embed=err("Mise invalide (max 50 000 € et ton liquide)."))
    if random.random() < 0.45:
        u["money"] += montant
        res = emb("🎰 Gagné !", f"+{money(montant)}", OK)
    else:
        u["money"] -= montant
        res = emb("🎰 Perdu…", f"-{money(montant)}", KO)
    db.save()
    await ctx.send(embed=res)

@bot.command(aliases=["pp"])
async def avatar(ctx, user: Optional[discord.User] = None):
    user = user or ctx.author
    e = emb(f"🖼️ Avatar de {user}")
    e.set_image(url=user.display_avatar.url)
    await ctx.send(embed=e)

@bot.command(aliases=["pf", "coinflip"])
async def pileouface(ctx):
    await ctx.send(embed=emb("🪙 Pile ou face", random.choice(["**Pile** !", "**Face** !"])))

@bot.command(name="8ball", aliases=["boule"])
async def eightball(ctx, *, question: str):
    r = random.choice(["Oui, clairement.", "Sans aucun doute.", "Peut-être…", "Redemande plus tard.",
                       "Je ne pense pas.", "Non.", "Les signes disent oui.", "Très improbable."])
    await ctx.send(embed=emb("🎱 Boule magique", f"**{question[:200]}**\n{r}"))

@bot.command()
@commands.guild_only()
async def sondage(ctx, *, question: str):
    e = emb("📊 Sondage", question[:1500], COLOR)
    e.set_footer(text=f"Par {ctx.author.display_name}")
    m = await ctx.send(embed=e)
    await m.add_reaction("👍")
    await m.add_reaction("👎")

@bot.command()
async def ping(ctx):
    await ctx.send(embed=emb("🏓 Pong", f"{round(bot.latency * 1000)} ms", OK))

# ═══════════════════════ LOGS DES COMMANDES ═══════════════════════
STAFF_COMMANDS = {
    "ban", "unban", "kick", "timeout", "untimeout", "clear", "nuke", "softban", "warn", "clearwarns",
    "lock", "unlock", "slowmode", "wl", "moov", "disconnect", "vocmute", "vocunmute", "mutecasque",
    "unmutecasque", "nickname", "roleadd", "roleremove", "derank", "automod", "automodnatif", "antiraid",
    "blacklist", "setsos", "setraid", "setreport", "preuve", "config", "retraitpermis", "amende",
    "ajoutcasier", "effacercasier", "arrestation", "fouille", "setservice", "serveurs", "quitter", "backup", "restore", "panel",
    "setargent", "setgrade", "setmetier", "setnom", "setage", "licencier", "resetpersonnage", "rpconfig", "rplogs",
}

@bot.listen("on_command_completion")
async def log_commands(ctx):
    root = ctx.command.root_parent or ctx.command
    e = discord.Embed(title=f"📜 RP!{ctx.command.qualified_name}", color=COLOR, timestamp=discord.utils.utcnow())
    e.add_field(name="👤 Auteur", value=f"{ctx.author} (`{ctx.author.id}`)", inline=False)
    e.add_field(name="🏰 Serveur", value=f"{ctx.guild.name} (`{ctx.guild.id}`)" if ctx.guild else "Messages privés", inline=False)
    if ctx.guild:
        e.add_field(name="💬 Salon", value=ctx.channel.mention, inline=False)
    e.add_field(name="⌨️ Message", value=f"`{ctx.message.content[:500]}`", inline=False)
    targets = [LOG_ALL_CHANNEL_ID]
    if root.name in STAFF_COMMANDS:
        targets.append(LOG_STAFF_CHANNEL_ID)
    for cid in targets:
        ch = bot.get_channel(cid)
        if ch:
            try:
                await ch.send(embed=e)
            except discord.HTTPException:
                pass

# ═══════════════════════ SAUVEGARDE + SITE WEB (Render / UptimeRobot) ═══════════════════════
async def start_web():
    """Mini site web : permet à UptimeRobot de garder le bot éveillé sur Render."""
    app = web.Application()

    async def home(_):
        return web.Response(text="RP bot en ligne ✅")

    app.router.add_get("/", home)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "8080"))).start()

@bot.command()
async def backup(ctx):
    """RP!backup — reçois data.json en message privé (fondateurs)."""
    if ctx.author.id not in OWNER_IDS:
        raise commands.CheckFailure("Réservé aux fondateurs.")
    db.save()
    try:
        await ctx.author.send("💾 Sauvegarde de `data.json`", file=discord.File(DATA_FILE))
        await ctx.send(embed=emb("💾 Sauvegarde envoyée", "Regarde tes messages privés.", OK))
    except discord.HTTPException:
        await ctx.send(embed=err("Impossible de t'écrire en MP : ouvre tes messages privés."))

@bot.command()
async def restore(ctx):
    """RP!restore + data.json en pièce jointe — restaure une sauvegarde (fondateurs)."""
    if ctx.author.id not in OWNER_IDS:
        raise commands.CheckFailure("Réservé aux fondateurs.")
    if not ctx.message.attachments:
        return await ctx.send(embed=err("Joins ton fichier `data.json` au message."))
    try:
        data = json.loads((await ctx.message.attachments[0].read()).decode("utf-8"))
        assert isinstance(data, dict) and "users" in data and "guilds" in data
    except Exception:
        return await ctx.send(embed=err("Fichier invalide."))
    for k, v in {"proofs": {}, "sos_channel": None, "raid_channel": None, "blacklist": {"users": {}, "guilds": {}}}.items():
        data.setdefault(k, v)
    db.data = data
    db.save()
    await ctx.send(embed=emb("✅ Sauvegarde restaurée", f"{len(data['users'])} joueur(s), {len(data['guilds'])} serveur(s).", OK))

@tasks.loop(hours=12)
async def auto_backup():
    if not OWNER_IDS:
        return
    try:
        db.save()
        owner = await bot.fetch_user(OWNER_IDS[0])
        await owner.send("💾 Sauvegarde automatique de `data.json`", file=discord.File(DATA_FILE))
    except Exception:
        pass

# ═══════════════════════ TICKETS ═══════════════════════
def tcfg(guild):
    return gcfg(guild.id)["tickets"]

def is_ticket_staff(member, t):
    return member.guild_permissions.manage_channels or any(r.id in t["staff_roles"] for r in member.roles)

class TicketModal(discord.ui.Modal, title="🎫 Ouvrir un ticket"):
    motif = discord.ui.TextInput(label="Motif de ta demande", style=discord.TextStyle.paragraph,
                                 max_length=500, placeholder="Explique ton problème en quelques mots…")

    async def on_submit(self, inter):
        await create_ticket(inter, str(self.motif))

async def create_ticket(inter, motif):
    g, t = inter.guild, tcfg(inter.guild)
    for cid, d in t["open"].items():
        if d["owner"] == inter.user.id and g.get_channel(int(cid)):
            return await inter.response.send_message(f"Tu as déjà un ticket ouvert : <#{cid}>", ephemeral=True)
    await inter.response.defer(ephemeral=True)
    try:
        cat = g.get_channel(t["category"] or 0)
        if not isinstance(cat, discord.CategoryChannel):
            cat = await g.create_category("🎫 Tickets", overwrites={
                g.default_role: discord.PermissionOverwrite(view_channel=False),
                g.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True, send_messages=True)})
            t["category"] = cat.id
        t["counter"] += 1
        ow = {
            g.default_role: discord.PermissionOverwrite(view_channel=False),
            inter.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, read_message_history=True),
            g.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True,
                                              read_message_history=True, embed_links=True),
        }
        for rid in t["staff_roles"]:
            r = g.get_role(rid)
            if r:
                ow[r] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True,
                                                    read_message_history=True, manage_messages=True)
        num = f"{t['counter']:04d}"
        ch = await g.create_text_channel(f"ticket-{num}", category=cat, overwrites=ow,
                                         topic=f"Ticket de {inter.user} ({inter.user.id})")
    except discord.HTTPException:
        return await inter.followup.send("❌ Je n'ai pas la permission de créer le salon (gérer les salons).", ephemeral=True)
    t["open"][str(ch.id)] = {"owner": inter.user.id, "claimed": None, "opened": int(time.time()), "reason": motif[:500]}
    db.save()
    e = discord.Embed(title=f"🎫 Ticket #{num}", color=COLOR, timestamp=discord.utils.utcnow(),
                      description=f"Bonjour {inter.user.mention}, un membre du staff va te répondre.\n{SEP}")
    e.add_field(name="👤 Auteur", value=f"{inter.user.mention} (`{inter.user.id}`)", inline=False)
    e.add_field(name="📝 Motif", value=motif[:900], inline=False)
    e.add_field(name="📌 Statut", value="⏳ En attente d'un membre du staff", inline=False)
    e.set_thumbnail(url=inter.user.display_avatar.url)
    e.set_footer(text="Utilise les boutons ci-dessous")
    mentions = " ".join(f"<@&{r}>" for r in t["staff_roles"])
    await ch.send(content=f"{inter.user.mention} {mentions}".strip(), embed=e, view=TicketControls(),
                  allowed_mentions=discord.AllowedMentions(users=True, roles=True))
    await inter.followup.send(f"✅ Ticket créé : {ch.mention}", ephemeral=True)

async def close_ticket(channel, closer):
    t = tcfg(channel.guild)
    d = t["open"].get(str(channel.id))
    lines = []
    async for m in channel.history(limit=3000, oldest_first=True):
        att = " ".join(a.url for a in m.attachments)
        lines.append(f"[{m.created_at:%Y-%m-%d %H:%M}] {m.author} : {m.content} {att}".strip())
    data = ("\n".join(lines) or "(vide)").encode("utf-8")
    e = discord.Embed(title=f"🔒 Ticket fermé — {channel.name}", color=KO, timestamp=discord.utils.utcnow())
    if d:
        e.add_field(name="👤 Auteur", value=f"<@{d['owner']}>")
        e.add_field(name="🛡️ Pris en charge", value=f"<@{d['claimed']}>" if d["claimed"] else "Personne")
        e.add_field(name="📝 Motif", value=d["reason"][:300], inline=False)
        e.add_field(name="⏱️ Ouvert", value=f"<t:{d['opened']}:R>")
    e.add_field(name="🔐 Fermé par", value=closer.mention)
    logs = channel.guild.get_channel(t["logs"] or 0)
    if logs:
        try:
            await logs.send(embed=e, file=discord.File(io.BytesIO(data), f"{channel.name}.txt"))
        except discord.HTTPException:
            pass
    owner = channel.guild.get_member(d["owner"]) if d else None
    if owner:
        try:
            await owner.send(f"🔒 Ton ticket **{channel.name}** sur **{channel.guild.name}** est fermé. Transcript :",
                             file=discord.File(io.BytesIO(data), f"{channel.name}.txt"))
        except discord.HTTPException:
            pass
    t["open"].pop(str(channel.id), None)
    db.save()
    await channel.delete(reason=f"Ticket fermé par {closer}")

class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ouvrir un ticket", emoji="🎫", style=discord.ButtonStyle.primary, custom_id="ticket:open")
    async def open_ticket(self, inter, button):
        if str(inter.user.id) in db.data["blacklist"]["users"]:
            return await inter.response.send_message("Tu es blacklist du bot.", ephemeral=True)
        await inter.response.send_modal(TicketModal())

class TicketControls(discord.ui.View):
    def __init__(self, claimed=False):
        super().__init__(timeout=None)
        self.claim.disabled = claimed

    @discord.ui.button(label="Prendre en charge", emoji="🛡️", style=discord.ButtonStyle.secondary, custom_id="ticket:claim")
    async def claim(self, inter, button):
        t = tcfg(inter.guild)
        d = t["open"].get(str(inter.channel.id))
        if not d:
            return await inter.response.send_message("Ticket introuvable.", ephemeral=True)
        if not is_ticket_staff(inter.user, t):
            return await inter.response.send_message("Réservé au staff.", ephemeral=True)
        d["claimed"] = inter.user.id
        db.save()
        e = inter.message.embeds[0]
        for i, f in enumerate(e.fields):
            if f.name.endswith("Statut"):
                e.set_field_at(i, name=f.name, value=f"🛡️ Pris en charge par {inter.user.mention}", inline=False)
        e.color = OK
        await inter.response.edit_message(embed=e, view=TicketControls(claimed=True))

    @discord.ui.button(label="Fermer", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="ticket:close")
    async def close(self, inter, button):
        t = tcfg(inter.guild)
        d = t["open"].get(str(inter.channel.id))
        if not d:
            return await inter.response.send_message("Ticket introuvable.", ephemeral=True)
        if inter.user.id != d["owner"] and not is_ticket_staff(inter.user, t):
            return await inter.response.send_message("Tu ne peux pas fermer ce ticket.", ephemeral=True)
        v = Confirm(inter.user)
        await inter.response.send_message("Fermer ce ticket ? Un transcript sera sauvegardé.", view=v, ephemeral=True)
        await v.wait()
        if v.value:
            await close_ticket(inter.channel, inter.user)

@bot.group(name="ticket", invoke_without_command=True)
@commands.guild_only()
async def ticket(ctx):
    await ctx.send(embed=emb("🎫 Système de tickets",
        "**Admin :**\n`RP!ticket setup [#salon]` — envoie le panneau\n`RP!ticket staff @role` — ajoute/retire un rôle staff\n"
        "`RP!ticket logs #salon` — transcripts\n`RP!ticket category <catégorie>`\n\n"
        "**Dans un ticket (staff) :**\n`RP!ticket add @user` · `RP!ticket remove @user`\n`RP!ticket rename <nom>` · `RP!ticket close`\n"
        "`RP!ticket list` — tickets ouverts"))

@ticket.command(name="setup")
@commands.has_permissions(manage_guild=True)
async def ticket_setup(ctx, channel: Optional[discord.TextChannel] = None):
    ch = channel or ctx.channel
    t = tcfg(ctx.guild)
    e = discord.Embed(title="🎫 Besoin d'aide ?", color=COLOR,
                      description=f"{SEP}\nClique sur le bouton ci-dessous pour **ouvrir un ticket**.\n"
                                  "Un salon privé sera créé, visible uniquement par toi et le staff.\n\n"
                                  "📌 Un seul ticket à la fois\n📝 Explique clairement ton problème\n"
                                  f"🔐 Un transcript est sauvegardé à la fermeture\n{SEP}")
    e.set_footer(text=f"{ctx.guild.name} • Support")
    if ctx.guild.icon:
        e.set_thumbnail(url=ctx.guild.icon.url)
    await ch.send(embed=e, view=TicketPanel())
    warn = "" if t["staff_roles"] else "\n⚠️ Aucun rôle staff défini : `RP!ticket staff @role`."
    await ctx.send(embed=emb("✅ Panneau envoyé", f"{ch.mention}{warn}", OK))

@ticket.command(name="staff")
@commands.has_permissions(manage_guild=True)
async def ticket_staff(ctx, role: discord.Role):
    t = tcfg(ctx.guild)
    if role.id in t["staff_roles"]:
        t["staff_roles"].remove(role.id)
        txt = f"{role.mention} retiré."
    else:
        t["staff_roles"].append(role.id)
        txt = f"{role.mention} ajouté au staff des tickets."
    db.save()
    await ctx.send(embed=emb("✅ Staff tickets", txt, OK))

@ticket.command(name="logs")
@commands.has_permissions(manage_guild=True)
async def ticket_logs(ctx, channel: discord.TextChannel):
    tcfg(ctx.guild)["logs"] = channel.id
    db.save()
    await ctx.send(embed=emb("✅ Salon des transcripts", channel.mention, OK))

@ticket.command(name="category", aliases=["categorie"])
@commands.has_permissions(manage_guild=True)
async def ticket_category(ctx, category: discord.CategoryChannel):
    tcfg(ctx.guild)["category"] = category.id
    db.save()
    await ctx.send(embed=emb("✅ Catégorie des tickets", category.name, OK))

def in_ticket(ctx):
    t = tcfg(ctx.guild)
    return t, t["open"].get(str(ctx.channel.id))

@ticket.command(name="add")
async def ticket_add(ctx, member: discord.Member):
    t, d = in_ticket(ctx)
    if not d or not is_ticket_staff(ctx.author, t):
        return await ctx.send(embed=err("À utiliser dans un ticket, par le staff."))
    await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
    await ctx.send(embed=emb("➕ Membre ajouté", member.mention, OK))

@ticket.command(name="remove")
async def ticket_remove(ctx, member: discord.Member):
    t, d = in_ticket(ctx)
    if not d or not is_ticket_staff(ctx.author, t):
        return await ctx.send(embed=err("À utiliser dans un ticket, par le staff."))
    if member.id == d["owner"]:
        return await ctx.send(embed=err("Tu ne peux pas retirer l'auteur du ticket."))
    await ctx.channel.set_permissions(member, overwrite=None)
    await ctx.send(embed=emb("➖ Membre retiré", member.mention, WARN))

@ticket.command(name="rename")
async def ticket_rename(ctx, *, nom: str):
    t, d = in_ticket(ctx)
    if not d or not is_ticket_staff(ctx.author, t):
        return await ctx.send(embed=err("À utiliser dans un ticket, par le staff."))
    await ctx.channel.edit(name=nom[:90])
    await ctx.send(embed=emb("✏️ Ticket renommé", nom[:90], OK))

@ticket.command(name="close")
async def ticket_close(ctx):
    t, d = in_ticket(ctx)
    if not d:
        return await ctx.send(embed=err("Ce salon n'est pas un ticket."))
    if ctx.author.id != d["owner"] and not is_ticket_staff(ctx.author, t):
        return await ctx.send(embed=err("Tu ne peux pas fermer ce ticket."))
    await ctx.send(embed=emb("🔒 Fermeture dans 5 secondes…", "Transcript en cours de sauvegarde.", WARN))
    await asyncio.sleep(5)
    await close_ticket(ctx.channel, ctx.author)

@ticket.command(name="list")
async def ticket_list(ctx):
    t = tcfg(ctx.guild)
    if not is_ticket_staff(ctx.author, t):
        return await ctx.send(embed=err("Réservé au staff."))
    txt = "\n".join(f"<#{cid}> — <@{d['owner']}> — {('🛡️ <@%d>' % d['claimed']) if d['claimed'] else '⏳ libre'}"
                    for cid, d in t["open"].items()) or "Aucun ticket ouvert."
    await ctx.send(embed=emb(f"🎫 Tickets ouverts ({len(t['open'])})", txt))

# ═══════════════════════ COMMANDES STAFF DU BOT (staff du support officiel uniquement) ═══════════════════════
@bot.command(name="serveurs", aliases=["guilds"])
@staff_only()
async def serveurs(ctx):
    gs = sorted(bot.guilds, key=lambda g: g.member_count or 0, reverse=True)[:25]
    txt = "\n".join(f"**{g.name}** — {g.member_count} membres — `{g.id}`" for g in gs)
    await ctx.send(embed=emb(f"🌐 {len(bot.guilds)} serveur(s)", txt or "Aucun."))

@bot.command(name="quitter")
@staff_only()
async def quitter(ctx, guild_id: int):
    g = bot.get_guild(guild_id)
    if not g:
        return await ctx.send(embed=err("Serveur introuvable."))
    if g.id == SUPPORT_GUILD_ID:
        return await ctx.send(embed=err("Impossible de quitter le support officiel."))
    await g.leave()
    await ctx.send(embed=emb("🚪 Serveur quitté", f"{g.name} (`{g.id}`)", WARN))

# ═══════════════════════ PANEL STAFF (support officiel uniquement) ═══════════════════════
def panel_embed():
    bl = db.data["blacklist"]
    tickets = sum(len(g.get("tickets", {}).get("open", {})) for g in db.data["guilds"].values())
    e = discord.Embed(title="🛠️ Panel staff", color=COLOR, timestamp=discord.utils.utcnow(),
                      description=f"{SEP}\nTableau de bord du bot — réservé au staff du support officiel.\n{SEP}")
    e.add_field(name="🌐 Serveurs", value=str(len(bot.guilds)))
    e.add_field(name="👥 Utilisateurs", value=str(sum(g.member_count or 0 for g in bot.guilds)))
    e.add_field(name="🏓 Ping", value=f"{round(bot.latency * 1000)} ms")
    e.add_field(name="⛔ Blacklist", value=f"{len(bl['users'])} users · {len(bl['guilds'])} serveurs")
    e.add_field(name="🎫 Tickets ouverts", value=str(tickets))
    e.add_field(name="🎮 Joueurs RP", value=str(len(db.data["users"])))
    e.add_field(name="⏱️ Uptime", value=str(timedelta(seconds=int(time.time() - START))))
    e.add_field(name="⌨️ Commandes", value=str(len(bot.commands)))
    e.set_footer(text=f"{BOT_NAME} • Actualisé")
    if SUPPORT_LOGO:
        e.set_thumbnail(url=SUPPORT_LOGO)
    return e

async def panel_log(inter, text):
    ch = bot.get_channel(LOG_STAFF_CHANNEL_ID)
    if ch:
        e = discord.Embed(title="🛠️ Action panel staff", description=text, color=WARN, timestamp=discord.utils.utcnow())
        e.set_author(name=str(inter.user), icon_url=inter.user.display_avatar.url)
        try:
            await ch.send(embed=e)
        except discord.HTTPException:
            pass

def parse_id(txt):
    t = str(txt).strip()
    return int(t) if t.isdigit() else None

class PanelBlacklistModal(discord.ui.Modal, title="⛔ Blacklist un utilisateur"):
    target = discord.ui.TextInput(label="ID de l'utilisateur", max_length=20)
    reason = discord.ui.TextInput(label="Raison", style=discord.TextStyle.paragraph, required=False, max_length=300)

    async def on_submit(self, inter):
        uid = parse_id(self.target)
        if not is_staff_member(inter.user) or uid is None or uid in OWNER_IDS:
            return await inter.response.send_message("❌ ID invalide ou action interdite.", ephemeral=True)
        reason = str(self.reason).strip() or "Non précisée"
        db.data["blacklist"]["users"][str(uid)] = {"reason": reason, "by": inter.user.id, "date": int(time.time())}
        db.save()
        await inter.response.send_message(f"⛔ `{uid}` est blacklist.", ephemeral=True)
        await panel_log(inter, f"⛔ Blacklist de `{uid}`\nRaison : {reason}")

class PanelUnblacklistModal(discord.ui.Modal, title="✅ Retirer de la blacklist"):
    target = discord.ui.TextInput(label="ID de l'utilisateur", max_length=20)

    async def on_submit(self, inter):
        uid = parse_id(self.target)
        if not is_staff_member(inter.user) or uid is None:
            return await inter.response.send_message("❌ ID invalide.", ephemeral=True)
        if db.data["blacklist"]["users"].pop(str(uid), None) is None:
            return await inter.response.send_message("Cet utilisateur n'est pas blacklist.", ephemeral=True)
        db.save()
        await inter.response.send_message(f"✅ `{uid}` retiré de la blacklist.", ephemeral=True)
        await panel_log(inter, f"✅ Retrait blacklist de `{uid}`")

class PanelLookupModal(discord.ui.Modal, title="🔎 Rechercher un utilisateur"):
    target = discord.ui.TextInput(label="ID de l'utilisateur", max_length=20)

    async def on_submit(self, inter):
        uid = parse_id(self.target)
        if not is_staff_member(inter.user) or uid is None:
            return await inter.response.send_message("❌ ID invalide.", ephemeral=True)
        try:
            u = await bot.fetch_user(uid)
        except discord.HTTPException:
            return await inter.response.send_message("Utilisateur introuvable.", ephemeral=True)
        b = db.data["blacklist"]["users"].get(str(uid))
        mutual = [g.name for g in bot.guilds if g.get_member(uid)]
        rp = db.data["users"].get(str(uid))
        e = discord.Embed(title=f"🔎 {u}", color=KO if b else COLOR)
        e.set_thumbnail(url=u.display_avatar.url)
        e.add_field(name="ID", value=f"`{uid}`").add_field(name="Compte créé", value=discord.utils.format_dt(u.created_at, "R"))
        e.add_field(name="⛔ Blacklist", value=f"Oui — {b['reason']}" if b else "Non", inline=False)
        e.add_field(name="🌐 Serveurs en commun", value=", ".join(mutual[:10]) or "Aucun", inline=False)
        if rp:
            e.add_field(name="🎮 Profil RP", value=f"{money(rp.get('money', 0) + rp.get('bank', 0))} · {rp.get('job', '—')} · {len(rp.get('cars', []))} véhicule(s)", inline=False)
        await inter.response.send_message(embed=e, ephemeral=True)

class PanelLeaveModal(discord.ui.Modal, title="🚪 Quitter un serveur"):
    target = discord.ui.TextInput(label="ID du serveur", max_length=20)

    async def on_submit(self, inter):
        gid = parse_id(self.target)
        g = bot.get_guild(gid) if gid else None
        if not is_staff_member(inter.user) or not g or g.id == SUPPORT_GUILD_ID:
            return await inter.response.send_message("❌ Serveur introuvable ou protégé.", ephemeral=True)
        await g.leave()
        await inter.response.send_message(f"🚪 J'ai quitté **{g.name}**.", ephemeral=True)
        await panel_log(inter, f"🚪 Serveur quitté : **{g.name}** (`{g.id}`)")

class StaffPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, inter):
        if not is_staff_member(inter.user):
            await inter.response.send_message("Réservé au staff du support officiel.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Actualiser", emoji="🔄", style=discord.ButtonStyle.secondary, custom_id="panel:refresh")
    async def refresh(self, inter, button):
        await inter.response.edit_message(embed=panel_embed(), view=self)

    @discord.ui.button(label="Blacklist", emoji="⛔", style=discord.ButtonStyle.danger, custom_id="panel:bl_add")
    async def bl_add(self, inter, button):
        await inter.response.send_modal(PanelBlacklistModal())

    @discord.ui.button(label="Retirer BL", emoji="✅", style=discord.ButtonStyle.success, custom_id="panel:bl_remove")
    async def bl_remove(self, inter, button):
        await inter.response.send_modal(PanelUnblacklistModal())

    @discord.ui.button(label="Rechercher", emoji="🔎", style=discord.ButtonStyle.primary, custom_id="panel:lookup")
    async def lookup(self, inter, button):
        await inter.response.send_modal(PanelLookupModal())

    @discord.ui.button(label="Serveurs", emoji="🌐", style=discord.ButtonStyle.secondary, custom_id="panel:servers")
    async def servers(self, inter, button):
        gs = sorted(bot.guilds, key=lambda g: g.member_count or 0, reverse=True)[:25]
        txt = "\n".join(f"**{g.name}** — {g.member_count} — `{g.id}`" for g in gs) or "Aucun."
        await inter.response.send_message(embed=emb(f"🌐 {len(bot.guilds)} serveur(s)", txt), ephemeral=True)

    @discord.ui.button(label="Quitter serveur", emoji="🚪", style=discord.ButtonStyle.danger, custom_id="panel:leave")
    async def leave(self, inter, button):
        await inter.response.send_modal(PanelLeaveModal())

    @discord.ui.button(label="Backup", emoji="💾", style=discord.ButtonStyle.secondary, custom_id="panel:backup")
    async def backup_btn(self, inter, button):
        if inter.user.id not in OWNER_IDS:
            return await inter.response.send_message("Réservé aux fondateurs.", ephemeral=True)
        db.save()
        try:
            await inter.user.send("💾 Sauvegarde de `data.json`", file=discord.File(DATA_FILE))
            await inter.response.send_message("💾 Sauvegarde envoyée en MP.", ephemeral=True)
        except discord.HTTPException:
            await inter.response.send_message("Impossible de t'écrire en MP.", ephemeral=True)

@bot.command(name="panel", aliases=["staffpanel"])
@commands.guild_only()
@support_only()
async def panel(ctx):
    """Panel staff interactif (support officiel uniquement)."""
    await ctx.send(embed=panel_embed(), view=StaffPanel())

# ═══════════════════════ LANCEMENT ═══════════════════════
@tasks.loop(minutes=30)
async def cleanup():
    now = time.time()
    for k in [k for k, v in db.data["proofs"].items() if v["exp"] < now]:
        del db.data["proofs"][k]
    db.save()

@bot.event
async def setup_hook():
    bot.add_view(AlertView())
    bot.add_view(TicketPanel())
    bot.add_view(TicketControls())
    bot.add_view(StaffPanel())
    bot.core = sys.modules[__name__]  # donne accès à bot.py à l'extension
    try:
        await bot.load_extension("rp_extra")
    except Exception as e:
        print("Extension rp_extra non chargée :", repr(e))
    cleanup.start()
    auto_backup.start()
    await start_web()

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("RP!help · Roleplay"))
    print(f"Connecté : {bot.user} ({len(bot.guilds)} serveurs)")

if __name__ == "__main__":
    bot.run(TOKEN)
