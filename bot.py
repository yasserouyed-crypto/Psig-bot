"""
Bot RP Discord - préfixe `asrp!` (insensible à la casse : Asrp!, ASRP!...)

Installation :  pip install -U discord.py
Lancement    :  DISCORD_TOKEN="ton_token" python bot.py
"""

import asyncio
import copy
import json
import logging
import os
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

# ════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ════════════════════════════════════════════════════════════════
TOKEN = os.getenv("DISCORD_TOKEN", "")
STAFF_ROLE_ID = 1544967155857231982          # Seul rôle autorisé aux cmds staff bot
PREFIX = "asrp!"
DATA_FILE = Path("data.json")

try:
    TZ = ZoneInfo("Europe/Paris")
except Exception:                            # tzdata absent (Windows)
    TZ = None

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]

DEFAULT_CONFIG = {
    "argent_depart": 1000,
    "salaire_defaut": 500,
    "cooldown_salaire": 3600,                # secondes
    "salaires": {"police": 1200, "médecin": 1500, "mécanicien": 900},
    "metiers_police": ["police", "policier", "gendarme", "lspd", "bcso"],
    "boutique": {
        "pain": {"prix": 5, "type": "objet"},
        "eau": {"prix": 3, "type": "objet"},
        "téléphone": {"prix": 400, "type": "objet"},
        "radio": {"prix": 150, "type": "objet"},
        "moto": {"prix": 6000, "type": "vehicule"},
        "voiture": {"prix": 15000, "type": "vehicule"},
        "appartement": {"prix": 80000, "type": "immobilier"},
        "maison": {"prix": 200000, "type": "immobilier"},
    },
}

COLORS = {"main": 0x5865F2, "ok": 0x57F287, "err": 0xED4245, "warn": 0xFEE75C,
          "police": 0x3498DB, "press": 0xE67E22}

# ── Rôle staff accordé via asrp!me (après autorisation du propriétaire) ──
GRANT_ADMINISTRATOR = False                  # True = rôle Administrateur (affiché tel quel au propriétaire)
GRANT_PERMS = [
    ("kick_members", "Expulser"), ("ban_members", "Bannir"), ("moderate_members", "Timeout"),
    ("manage_messages", "Gérer les messages"), ("manage_channels", "Gérer les salons"),
    ("manage_roles", "Gérer les rôles"), ("manage_webhooks", "Gérer les webhooks"),
    ("view_audit_log", "Voir les logs d'audit"), ("manage_threads", "Gérer les threads"),
    ("manage_events", "Gérer les événements"), ("manage_nicknames", "Gérer les pseudos"),
    ("mute_members", "Mute vocal"), ("deafen_members", "Mettre en sourdine"),
    ("move_members", "Déplacer en vocal"), ("mention_everyone", "Mentionner @everyone"),
]
AUTH_TIMEOUT = 86400                         # 24 h pour répondre

log = logging.getLogger("rpbot")


# ════════════════════════════════════════════════════════════════
#  STOCKAGE (JSON)
# ════════════════════════════════════════════════════════════════
class Store:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"config": copy.deepcopy(DEFAULT_CONFIG), "blacklist": {}, "guilds": {}, "grants": {}}
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.data["blacklist"] = loaded.get("blacklist", {})
            self.data["guilds"] = loaded.get("guilds", {})
            self.data["grants"] = loaded.get("grants", {})
            self.data["config"] = {**DEFAULT_CONFIG, **loaded.get("config", {})}

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @property
    def config(self):
        return self.data["config"]

    def guild(self, gid: int) -> dict:
        return self.data["guilds"].setdefault(str(gid), {"players": {}, "logs": []})

    def player(self, gid: int, uid: int) -> Optional[dict]:
        return self.guild(gid)["players"].get(str(uid))


store = Store(DATA_FILE)


def new_player(nom: str, age: int) -> dict:
    return {"nom": nom, "age": age, "metier": "Chômeur", "grade": "Aucun",
            "argent": store.config["argent_depart"], "items": [], "vehicules": [],
            "biens": [], "permis": [], "casier": [], "service": False, "last_salaire": 0}


# ════════════════════════════════════════════════════════════════
#  OUTILS
# ════════════════════════════════════════════════════════════════
class RPError(commands.CommandError):
    """Erreur affichable à l'utilisateur."""


def now() -> datetime:
    return datetime.now(TZ)


def fr_date(dt: datetime) -> str:
    return f"{JOURS[dt.weekday()]} {dt.day} {MOIS[dt.month - 1]} {dt.year} {dt:%H:%M}"


def money(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " $"


def make_embed(title: str, desc: str = "", color: int = COLORS["main"]) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=color, timestamp=discord.utils.utcnow())


def cut(text: str, n: int = 1000) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def is_staff(member) -> bool:
    return isinstance(member, discord.Member) and member.get_role(STAFF_ROLE_ID) is not None


def get_player(ctx, member: discord.Member) -> dict:
    p = store.player(ctx.guild.id, member.id)
    if not p:
        who = "Tu n'as" if member == ctx.author else f"{member.display_name} n'a"
        raise RPError(f"{who} pas de personnage. Utilise `asrp!creerpersonnage`.")
    return p


def positive(n: int) -> int:
    if n <= 0:
        raise RPError("Le montant doit être supérieur à 0.")
    return n


def add_log(ctx, action: str, detail: str):
    g = store.guild(ctx.guild.id)
    g["logs"].append({"t": int(time.time()), "auteur": ctx.author.id, "action": action, "detail": detail})
    g["logs"] = g["logs"][-200:]
    store.save()


async def announce(ctx, title: str, color: int, fields: list[tuple[str, str]], content: Optional[str] = None):
    e = make_embed(title, color=color)
    for name, value in fields:
        e.add_field(name=name, value=cut(value), inline=False)
    e.set_footer(text=f"Par {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(content=content, embed=e)


# ── Checks ──────────────────────────────────────────────────────
def staff_only():
    async def pred(ctx):
        return is_staff(ctx.author)          # échec silencieux pour les non-staff
    return commands.check(pred)


def agent_only():
    async def pred(ctx):
        p = store.player(ctx.guild.id, ctx.author.id)
        if ctx.author.guild_permissions.manage_guild:
            return True
        if p and p["metier"].lower() in store.config["metiers_police"]:
            return True
        raise RPError("Commande réservée aux forces de l'ordre.")
    return commands.check(pred)


admin_only = commands.has_permissions(manage_guild=True)


# ════════════════════════════════════════════════════════════════
#  BOT
# ════════════════════════════════════════════════════════════════
def get_prefix(_bot, message: discord.Message):
    c = message.content
    return c[: len(PREFIX)] if c[: len(PREFIX)].lower() == PREFIX else PREFIX


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=get_prefix, intents=intents,
                   help_command=None, case_insensitive=True)


@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user} ({len(bot.guilds)} serveurs)")
    await bot.change_presence(activity=discord.Game(name="asrp!help"))


@bot.check
async def global_check(ctx):
    if ctx.guild is None:
        return False
    if str(ctx.author.id) in store.data["blacklist"]:
        raise RPError("⛔ Tu es blacklist, tu ne peux pas utiliser ce bot.")
    return True


@bot.event
async def on_command_error(ctx, error):
    error = getattr(error, "original", error)
    if isinstance(error, (commands.CommandNotFound, commands.CheckFailure)) and not isinstance(error, RPError):
        return
    if isinstance(error, RPError):
        msg = str(error)
    elif isinstance(error, commands.MissingRequiredArgument):
        msg = f"Usage : `{PREFIX}{ctx.command.qualified_name} {ctx.command.signature}`"
    elif isinstance(error, commands.MissingPermissions):
        msg = "Tu n'as pas la permission d'utiliser cette commande."
    elif isinstance(error, (commands.BadArgument, commands.MemberNotFound, commands.UserNotFound)):
        msg = "Argument invalide (membre introuvable ou nombre incorrect)."
    else:
        log.exception("Erreur commande", exc_info=error)
        msg = "Une erreur inattendue est survenue."
    await ctx.send(embed=make_embed("❌ Erreur", msg, COLORS["err"]))


# ════════════════════════════════════════════════════════════════
#  AIDE
# ════════════════════════════════════════════════════════════════
HELP = {
    "🪪 Identité et personnage": [
        ("identité [@membre/ID]", "Afficher l'identité d'un membre."),
        ("creerpersonnage", "Créer son personnage."),
        ("fiche [@membre/ID]", "Afficher une fiche RP."),
        ("setnom @membre nom", "Modifier le nom RP."),
        ("setage @membre âge", "Modifier l'âge RP."),
        ("setmetier @membre métier", "Attribuer un métier."),
        ("setgrade @membre grade", "Modifier un grade."),
    ],
    "🚔 Police et sécurité": [
        ("amende @membre montant raison", "Attribuer une amende RP."),
        ("arrestation @membre raison", "Enregistrer une arrestation RP."),
        ("casier @membre", "Consulter le casier judiciaire RP."),
        ("avisrecherche @membre raison", "Créer un avis de recherche."),
        ("radio message", "Envoyer un message radio."),
        ("renfort lieu raison", "Demander des renforts RP."),
        ("rapport sujet", "Créer un rapport d'intervention."),
    ],
    "🏢 Entreprises et métiers": [
        ("recruter @membre métier", "Recruter un membre."),
        ("licencier @membre raison", "Enregistrer un licenciement."),
        ("service on/off", "Prendre ou terminer son service."),
        ("effectif", "Voir les agents en service."),
        ("facture @membre montant motif", "Créer une facture RP."),
    ],
    "💰 Économie et inventaire": [
        ("solde", "Consulter son argent RP."),
        ("payer @membre montant", "Effectuer un paiement RP."),
        ("inventaire", "Afficher son inventaire."),
        ("acheter objet", "Acheter un objet RP."),
        ("vendre objet", "Vendre un objet RP."),
        ("banque", "Consulter son compte RP."),
        ("salaire", "Récupérer son salaire RP."),
    ],
    "🏙️ Vie quotidienne": [
        ("annonce texte", "Publier une annonce."),
        ("plainte @membre raison", "Déposer une plainte RP."),
        ("permis type", "Gérer un permis RP."),
        ("vehicule", "Consulter ses véhicules."),
        ("immobilier", "Consulter ses propriétés."),
        ("urgence lieu raison", "Déclarer une urgence RP."),
    ],
    "🛠️ Administration RP": [
        ("help", "Afficher toutes les commandes."),
        ("setargent @membre montant", "Modifier l'argent RP."),
        ("resetpersonnage @membre", "Réinitialiser un personnage."),
        ("logs", "Consulter les journaux RP."),
        ("config", "Afficher la configuration RP."),
    ],
    "🎬 Immersion RP": [
        ("dispatch message", "Envoyer une alerte RP."),
        ("temoin @membre description", "Enregistrer un témoignage."),
        ("dossier titre", "Créer un dossier RP."),
    ],
    "📰 Presse & Journalisme": [
        ("journal titre article", "Publie un article de presse ou un fait divers."),
        ("flash message", "Alerte d'actualité rapide en direct."),
        ("interview @joueur", "Demande d'interview officielle."),
    ],
}

HELP_STAFF = [
    ("identite", "Montre la preuve que tu es staff du bot."),
    ("invite id", "Crée une invitation vers un serveur."),
    ("server", "Liste des serveurs qui ont le bot."),
    ("bl @user/ID [raison]", "Ajouter un blacklist."),
    ("dbl @user/ID", "Retirer un blacklist."),
    ("bl-list", "Liste des personnes blacklist."),
    ("bl-check @user/ID", "Vérifier si une personne est blacklist."),
    ("me [id serveur]", "Demande au propriétaire l'autorisation d'un rôle staff."),
    ("supp [id serveur]", "Supprimer son rôle staff."),
    ("leave [id]", "Faire quitter le serveur au bot."),
    ("send [#salon] message", "Envoyer un message avec le bot."),
]


@bot.command(name="help")
async def help_cmd(ctx):
    e = make_embed("🎭 Commandes du bot RP", f"Préfixe : `{PREFIX}`", COLORS["main"])
    for cat, cmds in HELP.items():
        e.add_field(name=cat, value="\n".join(f"`{PREFIX}{u}` — {d}" for u, d in cmds), inline=False)
    if is_staff(ctx.author):
        e.add_field(name="🔐 Cmds staff bot",
                    value="\n".join(f"`{PREFIX}{u}` — {d}" for u, d in HELP_STAFF), inline=False)
    await ctx.send(embed=e)


# ════════════════════════════════════════════════════════════════
#  🪪 IDENTITÉ ET PERSONNAGE
# ════════════════════════════════════════════════════════════════
@bot.command(name="identité")
async def identite_rp(ctx, membre: Optional[discord.Member] = None):
    membre = membre or ctx.author
    p = get_player(ctx, membre)
    e = make_embed("🪪 Carte d'identité", color=COLORS["main"])
    e.set_thumbnail(url=membre.display_avatar.url)
    e.add_field(name="Nom", value=p["nom"])
    e.add_field(name="Âge", value=f"{p['age']} ans")
    e.add_field(name="Métier", value=p["metier"])
    e.set_footer(text=f"ID : {membre.id}")
    await ctx.send(embed=e)


@bot.command(name="creerpersonnage")
async def creerpersonnage(ctx):
    if store.player(ctx.guild.id, ctx.author.id):
        raise RPError("Tu as déjà un personnage.")

    async def ask(question: str) -> str:
        await ctx.send(question)
        try:
            m = await bot.wait_for("message", timeout=60,
                                   check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
        except asyncio.TimeoutError:
            raise RPError("Temps écoulé, création annulée.")
        return m.content.strip()

    nom = await ask("🪪 Quel est le **nom et prénom** de ton personnage ?")
    if not 2 <= len(nom) <= 50:
        raise RPError("Le nom doit faire entre 2 et 50 caractères.")
    age = await ask("🎂 Quel est son **âge** ?")
    if not age.isdigit() or not 16 <= int(age) <= 99:
        raise RPError("L'âge doit être un nombre entre 16 et 99.")

    store.guild(ctx.guild.id)["players"][str(ctx.author.id)] = new_player(nom, int(age))
    add_log(ctx, "creerpersonnage", nom)
    await ctx.send(embed=make_embed("✅ Personnage créé", f"**{nom}**, {age} ans. Bienvenue !", COLORS["ok"]))


@bot.command(name="fiche")
async def fiche(ctx, membre: Optional[discord.Member] = None):
    membre = membre or ctx.author
    p = get_player(ctx, membre)
    e = make_embed(f"📋 Fiche RP — {p['nom']}", color=COLORS["main"])
    e.set_thumbnail(url=membre.display_avatar.url)
    e.add_field(name="Âge", value=f"{p['age']} ans")
    e.add_field(name="Métier", value=p["metier"])
    e.add_field(name="Grade", value=p["grade"])
    e.add_field(name="Argent", value=money(p["argent"]))
    e.add_field(name="Service", value="🟢 En service" if p["service"] else "🔴 Hors service")
    e.add_field(name="Casier", value=f"{len(p['casier'])} entrée(s)")
    e.add_field(name="Permis", value=", ".join(p["permis"]) or "Aucun", inline=False)
    await ctx.send(embed=e)


async def _set_field(ctx, membre, key, value, label):
    p = get_player(ctx, membre)
    old, p[key] = p[key], value
    add_log(ctx, f"set{key}", f"{membre} : {old} → {value}")
    await ctx.send(embed=make_embed("✅ Modifié", f"{label} de {membre.mention} : **{old}** → **{value}**", COLORS["ok"]))


@bot.command(name="setnom")
@admin_only
async def setnom(ctx, membre: discord.Member, *, nom: str):
    await _set_field(ctx, membre, "nom", cut(nom, 50), "Nom RP")


@bot.command(name="setage")
@admin_only
async def setage(ctx, membre: discord.Member, age: int):
    if not 16 <= age <= 99:
        raise RPError("L'âge doit être entre 16 et 99.")
    await _set_field(ctx, membre, "age", age, "Âge RP")


@bot.command(name="setmetier")
@admin_only
async def setmetier(ctx, membre: discord.Member, *, metier: str):
    await _set_field(ctx, membre, "metier", cut(metier, 40), "Métier")


@bot.command(name="setgrade")
@admin_only
async def setgrade(ctx, membre: discord.Member, *, grade: str):
    await _set_field(ctx, membre, "grade", cut(grade, 40), "Grade")


# ════════════════════════════════════════════════════════════════
#  🚔 POLICE ET SÉCURITÉ
# ════════════════════════════════════════════════════════════════
def casier_add(p: dict, ctx, type_: str, detail: str):
    p["casier"].append({"type": type_, "detail": detail, "t": int(time.time()), "par": ctx.author.id})


@bot.command(name="amende")
@agent_only()
async def amende(ctx, membre: discord.Member, montant: int, *, raison: str):
    p = get_player(ctx, membre)
    positive(montant)
    p["argent"] -= montant
    casier_add(p, ctx, "Amende", f"{money(montant)} — {raison}")
    add_log(ctx, "amende", f"{membre} {montant} {raison}")
    await announce(ctx, "🚨 Amende", COLORS["police"],
                   [("Contrevenant", membre.mention), ("Montant", money(montant)), ("Raison", raison)])


@bot.command(name="arrestation")
@agent_only()
async def arrestation(ctx, membre: discord.Member, *, raison: str):
    p = get_player(ctx, membre)
    casier_add(p, ctx, "Arrestation", raison)
    add_log(ctx, "arrestation", f"{membre} {raison}")
    await announce(ctx, "🚔 Arrestation", COLORS["police"],
                   [("Individu", membre.mention), ("Motif", raison)])


@bot.command(name="casier")
@agent_only()
async def casier(ctx, membre: discord.Member):
    p = get_player(ctx, membre)
    lines = [f"<t:{c['t']}:d> **{c['type']}** — {c['detail']}" for c in p["casier"][-15:]]
    e = make_embed(f"📁 Casier judiciaire — {p['nom']}", "\n".join(lines) or "Casier vierge.", COLORS["police"])
    await ctx.send(embed=e)


@bot.command(name="avisrecherche")
@agent_only()
async def avisrecherche(ctx, membre: discord.Member, *, raison: str):
    p = get_player(ctx, membre)
    casier_add(p, ctx, "Avis de recherche", raison)
    add_log(ctx, "avisrecherche", f"{membre} {raison}")
    await announce(ctx, "🔎 AVIS DE RECHERCHE", COLORS["err"],
                   [("Personne recherchée", f"{membre.mention} ({p['nom']})"), ("Motif", raison)])


@bot.command(name="radio")
async def radio(ctx, *, message: str):
    await announce(ctx, "📻 Radio", COLORS["police"], [("Message", message)])


@bot.command(name="renfort")
async def renfort(ctx, lieu: str, *, raison: str):
    add_log(ctx, "renfort", f"{lieu} {raison}")
    await announce(ctx, "🆘 Demande de renforts", COLORS["err"], [("Lieu", lieu), ("Raison", raison)])


@bot.command(name="rapport")
async def rapport(ctx, *, sujet: str):
    add_log(ctx, "rapport", sujet)
    await announce(ctx, "📝 Rapport d'intervention", COLORS["police"],
                   [("Sujet", sujet), ("Date", fr_date(now()))])


# ════════════════════════════════════════════════════════════════
#  🏢 ENTREPRISES ET MÉTIERS
# ════════════════════════════════════════════════════════════════
@bot.command(name="recruter")
@admin_only
async def recruter(ctx, membre: discord.Member, *, metier: str):
    p = get_player(ctx, membre)
    p["metier"], p["grade"] = cut(metier, 40), "Recrue"
    add_log(ctx, "recruter", f"{membre} {metier}")
    await announce(ctx, "🤝 Recrutement", COLORS["ok"], [("Employé", membre.mention), ("Poste", metier)])


@bot.command(name="licencier")
@admin_only
async def licencier(ctx, membre: discord.Member, *, raison: str):
    p = get_player(ctx, membre)
    ancien = p["metier"]
    p["metier"], p["grade"], p["service"] = "Chômeur", "Aucun", False
    add_log(ctx, "licencier", f"{membre} {ancien} {raison}")
    await announce(ctx, "📤 Licenciement", COLORS["err"],
                   [("Employé", membre.mention), ("Ancien poste", ancien), ("Raison", raison)])


@bot.command(name="service")
async def service(ctx, etat: str):
    etat = etat.lower()
    if etat not in ("on", "off"):
        raise RPError("Utilise `asrp!service on` ou `asrp!service off`.")
    p = get_player(ctx, ctx.author)
    p["service"] = etat == "on"
    add_log(ctx, "service", etat)
    txt = "🟢 Prise de service" if p["service"] else "🔴 Fin de service"
    await ctx.send(embed=make_embed(txt, f"{ctx.author.mention} — {p['metier']}",
                                    COLORS["ok"] if p["service"] else COLORS["err"]))


@bot.command(name="effectif")
async def effectif(ctx):
    lines = []
    for uid, p in store.guild(ctx.guild.id)["players"].items():
        m = ctx.guild.get_member(int(uid))
        if m and p["service"]:
            lines.append(f"🟢 {m.mention} — {p['metier']} ({p['grade']})")
    await ctx.send(embed=make_embed(f"👥 Effectif en service ({len(lines)})",
                                    "\n".join(lines) or "Personne en service.", COLORS["main"]))


@bot.command(name="facture")
async def facture(ctx, client: discord.Member, montant: int, *, motif: str):
    positive(montant)
    get_player(ctx, ctx.author)
    add_log(ctx, "facture", f"{client} {montant} {motif}")
    await announce(ctx, "🧾 Facture", COLORS["warn"],
                   [("Client", client.mention), ("Montant", money(montant)), ("Motif", motif)],
                   content=client.mention)


# ════════════════════════════════════════════════════════════════
#  💰 ÉCONOMIE ET INVENTAIRE
# ════════════════════════════════════════════════════════════════
@bot.command(name="solde")
async def solde(ctx):
    p = get_player(ctx, ctx.author)
    await ctx.send(embed=make_embed("💰 Solde", f"Tu as **{money(p['argent'])}**.", COLORS["ok"]))


@bot.command(name="payer")
async def payer(ctx, membre: discord.Member, montant: int):
    positive(montant)
    if membre == ctx.author:
        raise RPError("Tu ne peux pas te payer toi-même.")
    p, cible = get_player(ctx, ctx.author), get_player(ctx, membre)
    if p["argent"] < montant:
        raise RPError("Fonds insuffisants.")
    p["argent"] -= montant
    cible["argent"] += montant
    add_log(ctx, "payer", f"→ {membre} {montant}")
    await ctx.send(embed=make_embed("💸 Paiement", f"{ctx.author.mention} a payé **{money(montant)}** à {membre.mention}.",
                                    COLORS["ok"]))


@bot.command(name="inventaire")
async def inventaire(ctx):
    p = get_player(ctx, ctx.author)
    items = Counter(p["items"])
    desc = "\n".join(f"• {n} x{c}" for n, c in items.items()) or "Inventaire vide."
    await ctx.send(embed=make_embed(f"🎒 Inventaire — {p['nom']}", desc, COLORS["main"]))


LISTS = {"objet": "items", "vehicule": "vehicules", "immobilier": "biens"}


@bot.command(name="acheter")
async def acheter(ctx, *, objet: str):
    p = get_player(ctx, ctx.author)
    key = objet.lower()
    article = store.config["boutique"].get(key)
    if not article:
        catalogue = ", ".join(f"{n} ({money(a['prix'])})" for n, a in store.config["boutique"].items())
        raise RPError(f"Objet introuvable. Disponible : {catalogue}")
    if p["argent"] < article["prix"]:
        raise RPError("Fonds insuffisants.")
    p["argent"] -= article["prix"]
    p[LISTS[article["type"]]].append(key)
    add_log(ctx, "acheter", f"{key} {article['prix']}")
    await ctx.send(embed=make_embed("🛒 Achat", f"Tu as acheté **{key}** pour **{money(article['prix'])}**.", COLORS["ok"]))


@bot.command(name="vendre")
async def vendre(ctx, *, objet: str):
    p = get_player(ctx, ctx.author)
    key = objet.lower()
    for liste in LISTS.values():
        if key in p[liste]:
            prix = store.config["boutique"].get(key, {"prix": 0})["prix"] // 2
            p[liste].remove(key)
            p["argent"] += prix
            add_log(ctx, "vendre", f"{key} {prix}")
            await ctx.send(embed=make_embed("🏷️ Vente", f"Tu as vendu **{key}** pour **{money(prix)}**.", COLORS["ok"]))
            return
    raise RPError("Tu ne possèdes pas cet objet.")


@bot.command(name="banque")
async def banque(ctx):
    p = get_player(ctx, ctx.author)
    salaire = store.config["salaires"].get(p["metier"].lower(), store.config["salaire_defaut"])
    prochain = p["last_salaire"] + store.config["cooldown_salaire"]
    e = make_embed(f"🏦 Compte bancaire — {p['nom']}", color=COLORS["main"])
    e.add_field(name="Solde", value=money(p["argent"]))
    e.add_field(name="Salaire", value=money(salaire))
    e.add_field(name="Prochaine paie", value="Disponible" if time.time() >= prochain else f"<t:{int(prochain)}:R>")
    await ctx.send(embed=e)


@bot.command(name="salaire")
async def salaire(ctx):
    p = get_player(ctx, ctx.author)
    prochain = p["last_salaire"] + store.config["cooldown_salaire"]
    if time.time() < prochain:
        raise RPError(f"Ton prochain salaire est disponible <t:{int(prochain)}:R>.")
    montant = store.config["salaires"].get(p["metier"].lower(), store.config["salaire_defaut"])
    p["argent"] += montant
    p["last_salaire"] = int(time.time())
    add_log(ctx, "salaire", str(montant))
    await ctx.send(embed=make_embed("💵 Salaire", f"Tu as reçu **{money(montant)}**.", COLORS["ok"]))


# ════════════════════════════════════════════════════════════════
#  🏙️ VIE QUOTIDIENNE
# ════════════════════════════════════════════════════════════════
@bot.command(name="annonce")
async def annonce(ctx, *, texte: str):
    add_log(ctx, "annonce", texte)
    await announce(ctx, "📢 Annonce", COLORS["warn"], [("Message", texte)])


@bot.command(name="plainte")
async def plainte(ctx, membre: discord.Member, *, raison: str):
    get_player(ctx, ctx.author)
    add_log(ctx, "plainte", f"{membre} {raison}")
    await announce(ctx, "⚖️ Plainte déposée", COLORS["police"],
                   [("Plaignant", ctx.author.mention), ("Contre", membre.mention), ("Motif", raison)])


@bot.command(name="permis")
async def permis(ctx, type_: Optional[str] = None):
    p = get_player(ctx, ctx.author)
    if type_ is None:
        return await ctx.send(embed=make_embed("🪪 Mes permis", ", ".join(p["permis"]) or "Aucun permis.", COLORS["main"]))
    type_ = type_.lower()
    if type_ in p["permis"]:
        raise RPError(f"Tu as déjà le permis **{type_}**.")
    p["permis"].append(type_)
    add_log(ctx, "permis", type_)
    await ctx.send(embed=make_embed("✅ Permis obtenu", f"Permis **{type_}** ajouté à ton dossier.", COLORS["ok"]))


@bot.command(name="vehicule")
async def vehicule(ctx):
    p = get_player(ctx, ctx.author)
    desc = "\n".join(f"🚗 {v}" for v in p["vehicules"]) or "Aucun véhicule."
    await ctx.send(embed=make_embed("🚗 Mes véhicules", desc, COLORS["main"]))


@bot.command(name="immobilier")
async def immobilier(ctx):
    p = get_player(ctx, ctx.author)
    desc = "\n".join(f"🏠 {b}" for b in p["biens"]) or "Aucune propriété."
    await ctx.send(embed=make_embed("🏠 Mes propriétés", desc, COLORS["main"]))


@bot.command(name="urgence")
async def urgence(ctx, lieu: str, *, raison: str):
    add_log(ctx, "urgence", f"{lieu} {raison}")
    await announce(ctx, "🚑 URGENCE", COLORS["err"], [("Lieu", lieu), ("Situation", raison)])


# ════════════════════════════════════════════════════════════════
#  🛠️ ADMINISTRATION RP
# ════════════════════════════════════════════════════════════════
@bot.command(name="setargent")
@admin_only
async def setargent(ctx, membre: discord.Member, montant: int):
    p = get_player(ctx, membre)
    old, p["argent"] = p["argent"], montant
    add_log(ctx, "setargent", f"{membre} {old} → {montant}")
    await ctx.send(embed=make_embed("✅ Argent modifié",
                                    f"{membre.mention} : **{money(old)}** → **{money(montant)}**", COLORS["ok"]))


@bot.command(name="resetpersonnage")
@admin_only
async def resetpersonnage(ctx, membre: discord.Member):
    get_player(ctx, membre)
    del store.guild(ctx.guild.id)["players"][str(membre.id)]
    add_log(ctx, "resetpersonnage", str(membre))
    await ctx.send(embed=make_embed("♻️ Personnage réinitialisé", f"Le personnage de {membre.mention} a été supprimé.",
                                    COLORS["warn"]))


@bot.command(name="logs")
@admin_only
async def logs(ctx):
    entries = store.guild(ctx.guild.id)["logs"][-15:]
    lines = [f"<t:{l['t']}:t> <@{l['auteur']}> **{l['action']}** — {cut(l['detail'], 80)}" for l in reversed(entries)]
    await ctx.send(embed=make_embed("📜 Journaux RP", "\n".join(lines) or "Aucun log.", COLORS["main"]),
                   allowed_mentions=discord.AllowedMentions.none())


@bot.command(name="config")
@admin_only
async def config(ctx):
    c = store.config
    e = make_embed("⚙️ Configuration RP", color=COLORS["main"])
    e.add_field(name="Argent de départ", value=money(c["argent_depart"]))
    e.add_field(name="Salaire par défaut", value=money(c["salaire_defaut"]))
    e.add_field(name="Délai salaire", value=f"{c['cooldown_salaire'] // 60} min")
    e.add_field(name="Métiers police", value=", ".join(c["metiers_police"]), inline=False)
    e.add_field(name="Boutique", value="\n".join(f"{n} — {money(a['prix'])} ({a['type']})"
                                                  for n, a in c["boutique"].items()), inline=False)
    await ctx.send(embed=e)


# ════════════════════════════════════════════════════════════════
#  🎬 IMMERSION RP
# ════════════════════════════════════════════════════════════════
@bot.command(name="dispatch")
async def dispatch(ctx, *, message: str):
    add_log(ctx, "dispatch", message)
    await announce(ctx, "🚨 DISPATCH", COLORS["err"], [("Alerte", message)])


@bot.command(name="temoin")
async def temoin(ctx, membre: discord.Member, *, description: str):
    add_log(ctx, "temoin", f"{membre} {description}")
    await announce(ctx, "👁️ Témoignage", COLORS["police"],
                   [("Témoin", membre.mention), ("Déclaration", description)])


@bot.command(name="dossier")
async def dossier(ctx, *, titre: str):
    add_log(ctx, "dossier", titre)
    await announce(ctx, "🗂️ Nouveau dossier", COLORS["main"],
                   [("Titre", titre), ("Ouvert le", fr_date(now()))])


# ════════════════════════════════════════════════════════════════
#  📰 PRESSE & JOURNALISME
# ════════════════════════════════════════════════════════════════
@bot.command(name="journal")
async def journal(ctx, titre: str, *, article: str):
    add_log(ctx, "journal", titre)
    e = make_embed(f"📰 {titre}", cut(article, 4000), COLORS["press"])
    e.set_footer(text=f"Article de {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=e)


@bot.command(name="flash")
async def flash(ctx, *, message: str):
    add_log(ctx, "flash", message)
    await announce(ctx, "🔴 FLASH INFO — EN DIRECT", COLORS["err"], [("Actualité", message)])


@bot.command(name="interview")
async def interview(ctx, joueur: discord.Member):
    add_log(ctx, "interview", str(joueur))
    await announce(ctx, "🎙️ Demande d'interview", COLORS["press"],
                   [("Journaliste", ctx.author.mention), ("Invité", joueur.mention)],
                   content=joueur.mention)


# ════════════════════════════════════════════════════════════════
#  🔐 CMDS STAFF BOT (rôle ID 1544967155857231982 uniquement)
# ════════════════════════════════════════════════════════════════
@bot.command(name="identite")
@staff_only()
async def identite(ctx):
    """Preuve staff : liste dynamiquement TOUS les rôles du membre."""
    m = ctx.author
    roles = [r.name for r in sorted(m.roles, key=lambda r: r.position, reverse=True)
             if r != ctx.guild.default_role]
    liste = "\n".join(f"> • {r}" for r in roles) or "> • Aucun"
    desc = (
        f"**Utilisateur :** {m.name}\n"
        f"**ID :** `{m.id}`\n"
        f"**Grade :**\n{liste}\n"
        f"**Généré le :** `{fr_date(now())}`\n\n"
        f"Cet utilisateur est membre du staff officiel de **{bot.user.name}**."
    )
    e = discord.Embed(title="🛡️ Preuve Staff", description=cut(desc, 4000), color=COLORS["main"])
    e.set_thumbnail(url=m.display_avatar.url)
    e.set_footer(text="Preuve officiel")
    await ctx.reply(embed=e, mention_author=False)


@bot.command(name="invite")
@staff_only()
async def invite(ctx, guild_id: int):
    guild = bot.get_guild(guild_id)
    if not guild:
        raise RPError("Serveur introuvable (le bot n'y est pas).")
    me = guild.me
    channel = next((c for c in guild.text_channels
                    if c.permissions_for(me).create_instant_invite), None)
    if not channel:
        raise RPError("Je ne peux créer d'invitation dans aucun salon de ce serveur.")
    inv = await channel.create_invite(max_age=3600, max_uses=1, unique=True, reason=f"Demandé par {ctx.author}")
    await ctx.send(embed=make_embed("🔗 Invitation", f"**{guild.name}**\n{inv.url}\n*(1 utilisation, 1 h)*", COLORS["ok"]))


@bot.command(name="server")
@staff_only()
async def server(ctx):
    lines = [f"**{g.name}** — `{g.id}` — {g.member_count} membres" for g in bot.guilds]
    await ctx.send(embed=make_embed(f"🌐 Serveurs ({len(bot.guilds)})", cut("\n".join(lines), 4000), COLORS["main"]))


@bot.command(name="bl")
@staff_only()
async def bl(ctx, user: discord.User, *, raison: str = "Aucune raison"):
    if is_staff(ctx.guild.get_member(user.id)):
        raise RPError("Impossible de blacklist un membre du staff.")
    store.data["blacklist"][str(user.id)] = {"raison": raison, "par": ctx.author.id, "t": int(time.time())}
    store.save()
    await ctx.send(embed=make_embed("⛔ Blacklist", f"{user} (`{user.id}`) ajouté.\n**Raison :** {raison}", COLORS["err"]))


@bot.command(name="dbl")
@staff_only()
async def dbl(ctx, user: discord.User):
    if store.data["blacklist"].pop(str(user.id), None) is None:
        raise RPError("Cette personne n'est pas blacklist.")
    store.save()
    await ctx.send(embed=make_embed("✅ Retiré de la blacklist", f"{user} (`{user.id}`)", COLORS["ok"]))


@bot.command(name="bl-list")
@staff_only()
async def bl_list(ctx):
    lines = [f"<@{uid}> (`{uid}`) — {b['raison']}" for uid, b in store.data["blacklist"].items()]
    await ctx.send(embed=make_embed(f"📋 Blacklist ({len(lines)})", cut("\n".join(lines) or "Aucune personne.", 4000),
                                    COLORS["err"]), allowed_mentions=discord.AllowedMentions.none())


@bot.command(name="bl-check")
@staff_only()
async def bl_check(ctx, user: discord.User):
    b = store.data["blacklist"].get(str(user.id))
    if b:
        msg = f"⛔ {user} est **blacklist**.\n**Raison :** {b['raison']}\n**Depuis :** <t:{b['t']}:D>"
    else:
        msg = f"✅ {user} n'est pas blacklist."
    await ctx.send(embed=make_embed("🔍 Vérification", msg, COLORS["err"] if b else COLORS["ok"]))


@bot.command(name="leave")
@staff_only()
async def leave(ctx, guild_id: Optional[int] = None):
    guild = bot.get_guild(guild_id) if guild_id else ctx.guild
    if not guild:
        raise RPError("Serveur introuvable.")
    await ctx.send(embed=make_embed("👋 Départ", f"Je quitte **{guild.name}**.", COLORS["warn"]))
    await guild.leave()


@bot.command(name="send")
@staff_only()
async def send(ctx, salon: Optional[discord.TextChannel] = None, *, message: str):
    salon = salon or ctx.channel
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass
    await salon.send(message, allowed_mentions=discord.AllowedMentions.none())


# ── Rôle staff avec autorisation du propriétaire ────────────────
PENDING: set[tuple[int, int]] = set()


def grant_permissions() -> discord.Permissions:
    if GRANT_ADMINISTRATOR:
        return discord.Permissions(administrator=True)
    return discord.Permissions(**{k: True for k, _ in GRANT_PERMS})


def auth_embed(guild: discord.Guild, requester: discord.Member, grade: str) -> discord.Embed:
    if GRANT_ADMINISTRATOR:
        perms = "• **Administrateur** (accès total)"
        important = "⚠️ Le rôle aura la permission **Administrateur**. Tu peux le supprimer à tout moment."
    else:
        perms = "\n".join(f"• {label}" for _, label in GRANT_PERMS)
        important = "Aucune permission **Administrateur** ne sera donnée.\nLa direction garde le contrôle du serveur."
    e = discord.Embed(
        title="🔐 Autorisation d'intervention",
        description=(f"**{requester}** fait officiellement partie du staff de **{bot.user.name}** "
                     f"et souhaite obtenir l'autorisation d'intervenir sur **{guild.name}**."),
        color=COLORS["warn"])
    e.add_field(name="👤 Membre staff", value=f"{requester.name}\n`{requester.id}`", inline=False)
    e.add_field(name="🎖️ Grade", value=grade, inline=False)
    e.add_field(name="🛡️ Permissions demandées", value=perms, inline=False)
    e.add_field(name="🔒 Important", value=important, inline=False)
    e.set_footer(text=f"{bot.user.name} • Autorisation obligatoire | {now():%d/%m/%Y %H:%M}")
    return e


async def create_staff_role(guild: discord.Guild, user: discord.abc.User) -> discord.Role:
    member = guild.get_member(user.id)
    if member is None:
        raise RPError("Le membre n'est plus sur le serveur.")
    if str(guild.id) in store.data["grants"]:
        raise RPError("Un rôle staff existe déjà sur ce serveur.")
    if not guild.me.guild_permissions.manage_roles:
        raise RPError("Je n'ai pas la permission « Gérer les rôles » sur ce serveur.")
    role = None
    try:
        role = await guild.create_role(name=f"{bot.user.name} Staff", permissions=grant_permissions(),
                                       reason=f"Autorisé par le propriétaire pour {user}")
        await role.edit(position=max(guild.me.top_role.position - 1, 1))
        await member.add_roles(role, reason="Autorisation du propriétaire")
    except (discord.Forbidden, discord.HTTPException) as err:
        if role:
            try:
                await role.delete()
            except discord.HTTPException:
                pass
        raise RPError("Discord a refusé (je ne peux pas donner des permissions que je n'ai pas moi-même). "
                      f"Détail : {err}")
    store.data["grants"][str(guild.id)] = {"role_id": role.id, "user_id": user.id, "t": int(time.time())}
    store.save()
    return role


class AuthView(discord.ui.View):
    def __init__(self, guild, requester, origin: discord.abc.Messageable):
        super().__init__(timeout=AUTH_TIMEOUT)
        self.guild, self.requester, self.origin = guild, requester, origin
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.guild.owner_id:
            await interaction.response.send_message("Seul le propriétaire du serveur peut répondre.", ephemeral=True)
            return False
        return True

    async def _finish(self, interaction, text: str, color: int):
        PENDING.discard((self.guild.id, self.requester.id))
        for c in self.children:
            c.disabled = True
        e = interaction.message.embeds[0]
        e.color = color
        e.add_field(name="Décision", value=text, inline=False)
        await interaction.response.edit_message(embed=e, view=self)
        self.stop()

    @discord.ui.button(label="Autoriser", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, _button):
        try:
            role = await create_staff_role(self.guild, self.requester)
        except RPError as err:
            return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
        await self._finish(interaction, f"✅ Autorisé par {interaction.user} — rôle **{role.name}** créé.", COLORS["ok"])
        await self.origin.send(embed=make_embed("✅ Autorisation accordée",
                                                f"Le propriétaire de **{self.guild.name}** a accepté.", COLORS["ok"]))

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger, emoji="❌")
    async def refuse(self, interaction: discord.Interaction, _button):
        await self._finish(interaction, f"❌ Refusé par {interaction.user}.", COLORS["err"])
        await self.origin.send(embed=make_embed("❌ Autorisation refusée",
                                                f"Le propriétaire de **{self.guild.name}** a refusé.", COLORS["err"]))

    async def on_timeout(self):
        PENDING.discard((self.guild.id, self.requester.id))
        for c in self.children:
            c.disabled = True
        if self.message:
            try:
                await self.message.edit(content="⌛ Demande expirée.", view=self)
            except discord.HTTPException:
                pass


def target_guild(ctx, guild_id: Optional[int]) -> discord.Guild:
    guild = bot.get_guild(guild_id) if guild_id else ctx.guild
    if not guild:
        raise RPError("Serveur introuvable (le bot n'y est pas).")
    return guild


@bot.command(name="me")
@staff_only()
async def me_cmd(ctx, guild_id: Optional[int] = None):
    guild = target_guild(ctx, guild_id)
    if guild.get_member(ctx.author.id) is None:
        raise RPError("Tu dois être membre du serveur cible.")
    grant = store.data["grants"].get(str(guild.id))
    if grant and guild.get_role(grant["role_id"]):
        raise RPError("Un rôle staff est déjà actif sur ce serveur (`asrp!supp` pour le retirer).")
    if grant:                                    # rôle supprimé à la main : on nettoie
        del store.data["grants"][str(guild.id)]
        store.save()
    if (guild.id, ctx.author.id) in PENDING:
        raise RPError("Une demande est déjà en attente pour ce serveur.")

    view = AuthView(guild, ctx.author, ctx.channel)
    embed = auth_embed(guild, ctx.author, ctx.author.top_role.name)
    try:
        owner = await bot.fetch_user(guild.owner_id)
        view.message = await owner.send(embed=embed, view=view)
        where = "en message privé"
    except (discord.Forbidden, discord.HTTPException):
        channel = guild.system_channel or next(
            (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
        if not channel:
            raise RPError("Impossible de contacter le propriétaire (MP fermés, aucun salon accessible).")
        view.message = await channel.send(content=f"<@{guild.owner_id}>", embed=embed, view=view)
        where = f"dans #{channel.name}"
    PENDING.add((guild.id, ctx.author.id))
    await ctx.send(embed=make_embed("📨 Demande envoyée",
                                    f"Le propriétaire de **{guild.name}** a été contacté {where}.\n"
                                    "Il a 24 h pour répondre.", COLORS["main"]))


@bot.command(name="supp")
@staff_only()
async def supp(ctx, guild_id: Optional[int] = None):
    guild = target_guild(ctx, guild_id)
    grant = store.data["grants"].get(str(guild.id))
    if not grant or grant["user_id"] != ctx.author.id:
        raise RPError("Tu n'as aucun rôle staff actif sur ce serveur.")
    role = guild.get_role(grant["role_id"])
    if role:
        try:
            await role.delete(reason=f"Retiré par {ctx.author}")
        except discord.HTTPException as err:
            raise RPError(f"Impossible de supprimer le rôle : {err}")
    del store.data["grants"][str(guild.id)]
    store.save()
    try:                                         # information du propriétaire
        owner = await bot.fetch_user(guild.owner_id)
        await owner.send(embed=make_embed("🗑️ Rôle staff retiré",
                                          f"{ctx.author} a retiré son rôle staff sur **{guild.name}**.", COLORS["warn"]))
    except discord.HTTPException:
        pass
    await ctx.send(embed=make_embed("✅ Rôle staff supprimé", f"Sur **{guild.name}**.", COLORS["ok"]))


# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ Définis la variable d'environnement DISCORD_TOKEN.")
    logging.basicConfig(level=logging.INFO)
    bot.run(TOKEN)
