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
import time
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord.ext import commands, tasks

# ═══════════════════════ CONFIGURATION ═══════════════════════
TOKEN = os.getenv("DISCORD_TOKEN") or "COLLE_TON_TOKEN_ICI"
OWNER_IDS = [0]                 # Tes IDs (fondateurs du bot)
SUPPORT_GUILD_ID = 0            # ID du serveur support officiel du bot
STAFF_ROLE_IDS = [0]            # IDs des rôles staff DANS le serveur support
SUPPORT_NAME = "Phénix Support"
SUPPORT_LOGO = ""               # URL d'une image (optionnel)
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
    "strikes": {}, "warns": {}, "bl_autoban": False,
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
    return discord.Embed(title=title, description=desc, color=color)

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
        if not (is_staff_member(ctx.author) or ctx.author.guild_permissions.administrator):
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
    if not cfg["enabled"] or m.guild_permissions.manage_messages or m.id in OWNER_IDS:
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
    if not cfg["enabled"] or not cfg["raid"]["on"]:
        return
    now = time.time()
    dq = join_track[member.guild.id]
    dq.append((now, member))
    while dq and now - dq[0][0] > cfg["raid"]["seconds"]:
        dq.popleft()
    if len(dq) < cfg["raid"]["joins"]:
        return
    victims = [x[1] for x in dq]
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

@bot.command(aliases=["mute", "timeout"])
@commands.guild_only()
@commands.has_permissions(moderate_members=True)
async def tempmute(ctx, member: discord.Member, minutes: int, *, raison: str = "Non précisée"):
    await member.timeout(timedelta(minutes=min(minutes, 40320)), reason=raison)
    await ctx.send(embed=emb("🔇 Mute", f"{member.mention} — {minutes} min — {raison}", WARN))

@bot.command()
@commands.guild_only()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(embed=emb("🔊 Unmute", member.mention, OK))

@bot.command(aliases=["clear"])
@commands.guild_only()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, n: int):
    d = await ctx.channel.purge(limit=min(n, 200) + 1)
    await ctx.send(embed=emb("🧹 Nettoyage", f"{len(d)-1} messages supprimés.", OK), delete_after=5)

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(embed=emb("🔒 Salon verrouillé", color=KO))

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None)
    await ctx.send(embed=emb("🔓 Salon déverrouillé", color=OK))

@bot.command()
@commands.guild_only()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, secondes: int):
    await ctx.channel.edit(slowmode_delay=max(0, min(secondes, 21600)))
    await ctx.send(embed=emb("🐢 Slowmode", f"{secondes}s", OK))

# ═══════════════════════ ÉCONOMIE / IDENTITÉ / MÉTIERS ═══════════════════════
JOBS = {
    "Chômeur": (0, 0), "Livreur": (200, 450), "Taxi": (250, 550), "Mécanicien": (350, 700),
    "Policier": (450, 800), "Gendarme": (450, 800), "Pompier": (450, 800),
    "Médecin": (600, 1100), "Concessionnaire": (600, 1200), "Avocat": (700, 1400),
}

@bot.command(aliases=["creeridentite", "identite"])
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
@bot.command()
async def ping(ctx):
    await ctx.send(embed=emb("🏓 Pong", f"{round(bot.latency * 1000)} ms", OK))

@bot.command(aliases=["aide", "h"])
async def help(ctx):
    e = emb("📖 Aide — préfixe `RP!` (ou rp! / Rp!)")
    e.add_field(name="🆘 Support", value="`sos <motif>` · `preuve` · `verifpreuve <code>`\nStaff : `setsos #salon` · `setraid #salon` (support uniquement)", inline=False)
    e.add_field(name="⛔ Blacklist (staff)", value="`bl add/remove/info/list/export` · `bl server add/remove` · `bl autoban on/off`", inline=False)
    e.add_field(name="🛡️ Automod & Modération", value="`automod` (on/off/toggle/set/badword/logs/ignore)\n`warn` `warns` `clearwarns` `kick` `ban` `unban` `mute` `unmute` `purge` `lock` `unlock` `slowmode`", inline=False)
    e.add_field(name="🚗 Automobile", value="`concession` `acheter` `garage` `conduire` `plein` `reparer` `vendre` `rouler [km]`\n`permis` `permis passer` `retraitpermis` `amende` `amendes` `payer`", inline=False)
    e.add_field(name="💼 Économie & identité", value="`cni <prénom> <nom> <âge>` `macni` `solde` `deposer` `retirer` `donner` `metier` `travail` `classement`", inline=False)
    e.add_field(name="🎭 Roleplay", value="`me` `do` `des` `annonce` `casier` `ajoutcasier` `effacercasier`\n`17` `18` `15` (appels) · `setservice police|pompier|samu @role`", inline=False)
    await ctx.send(embed=e)

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
    cleanup.start()

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("RP!help · Roleplay"))
    print(f"Connecté : {bot.user} ({len(bot.guilds)} serveurs)")

if __name__ == "__main__":
    bot.run(TOKEN)
