"""
╔════════════════════════════════════════════════════════════════╗
║              🎭 PHÉNIX RP BOT — COMPLET & STYLÉ 🎭             ║
║  Préfixe : RP!  rp!  Rp!                                       ║
║  Commandes VRAIMENT fonctionnelles + Help interactif           ║
╚════════════════════════════════════════════════════════════════╝
"""
import discord
from discord.ext import commands, tasks
import json
import os
import time
import random
import secrets
from datetime import datetime

TOKEN = "MTU1ODE1MDU2NzM5MjQ1MjYxOQ.GUcDWi.MTG31DXBF6mCCEfG5dBiaz48L0kIQMBmGxHI4Q"
OWNER_IDS = [0]
SUPPORT_GUILD_ID = 0
STAFF_ROLE_IDS = [0]
SUPPORT_NAME = "Phénix Support"
DATA_FILE = "rp_data.json"

COLOR = 0xFF6B1A
OK = 0x2ECC71
KO = 0xE74C3C
WARN = 0xF39C12
INFO = 0x3498DB
STAFF = 0x9B59B6

# ═══════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════
class DB:
    def __init__(self, path):
        self.path = path
        self.data = {"users": {}, "guilds": {}, "blacklist": {"users": {}, "guilds": {}}, "proofs": {}}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.data.update(json.load(f))

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)

db = DB(DATA_FILE)

USER_DEFAULT = {
    "personnage": None,
    "argent": 5000,
    "banque": 10000,
    "inventaire": [],
    "service": False,
}

def get_user(uid):
    uid = str(uid)
    if uid not in db.data["users"]:
        db.data["users"][uid] = USER_DEFAULT.copy()
    return db.data["users"][uid]

# ═══════════════════════════════════════════════════════════════
# BOT
# ═══════════════════════════════════════════════════════════════
def get_prefix(bot_, msg):
    c = msg.content
    if c[:5].lower() == "asrp!":
        return c[:5]
    if c[:3].lower() == "rp!":
        return c[:3]
    return commands.when_mentioned(bot_, msg)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=get_prefix, intents=intents, case_insensitive=True, help_command=None)

def emb(title="", desc="", color=COLOR):
    e = discord.Embed(title=title, description=desc, color=color, timestamp=discord.utils.utcnow())
    e.set_footer(text=f"{SUPPORT_NAME} • RP!help")
    return e

def err(text):
    return emb("❌ Erreur", text, KO)

def is_staff(user):
    if user.id in OWNER_IDS:
        return True
    g = bot.get_guild(SUPPORT_GUILD_ID)
    m = g.get_member(user.id) if g else None
    return bool(m and any(r.id in STAFF_ROLE_IDS for r in m.roles))

def staff_only():
    def pred(ctx):
        if (ctx.prefix or "").lower() != "asrp!" or not is_staff(ctx.author):
            raise commands.CheckFailure("Réservé au staff : `asrp!...`")
        return True
    return commands.check(pred)

@bot.check
async def global_check(ctx):
    if ctx.author.id in OWNER_IDS:
        return True
    bl = db.data["blacklist"]["users"]
    if str(ctx.author.id) in bl:
        raise commands.CheckFailure(f"Tu es blacklist : {bl[str(ctx.author.id)]['reason']}")
    return True

@bot.event
async def on_command_error(ctx, e):
    e = getattr(e, "original", e)
    if isinstance(e, commands.CommandNotFound):
        return
    if isinstance(e, commands.MissingRequiredArgument):
        return await ctx.send(embed=err(f"Argument manquant : `{e.param.name}`. Tape `RP!help`."))
    if isinstance(e, commands.BadArgument):
        return await ctx.send(embed=err("Argument invalide. Tape `RP!help`."))
    if isinstance(e, commands.CheckFailure):
        return await ctx.send(embed=err(str(e)))
    print(f"Erreur : {e}")

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("RP!help • Phénix RP"))
    print(f"✅ {bot.user} • {len(bot.guilds)} serveurs")

# ═══════════════════════════════════════════════════════════════
# HELP INTERACTIF
# ═══════════════════════════════════════════════════════════════
CATEGORIES = {
    "identité": {
        "emoji": "🪪",
        "title": "Identité et personnage",
        "cmds": [
            ("creerpersonnage <prenom> <nom> <age>", "Créer ton personnage"),
            ("identité [@membre]", "Afficher une identité"),
            ("fiche [@membre]", "Fiche RP complète"),
            ("setnom <nom>", "Modifier ton nom"),
            ("setage <age>", "Modifier ton âge"),
            ("setmetier <métier>", "Changer de métier"),
        ]
    },
    "police": {
        "emoji": "🚔",
        "title": "Police et sécurité",
        "cmds": [
            ("amende @membre montant raison", "Attribuer une amende"),
            ("arrestation @membre raison", "Enregistrer une arrestation"),
            ("casier [@membre]", "Consulter le casier"),
            ("avisrecherche @membre raison", "Créer un avis de recherche"),
            ("radio <message>", "Envoyer sur la radio"),
            ("renfort <lieu> <raison>", "Demander des renforts"),
        ]
    },
    "économie": {
        "emoji": "💰",
        "title": "Économie et inventaire",
        "cmds": [
            ("solde [@membre]", "Voir son argent"),
            ("payer @membre montant", "Faire un paiement"),
            ("inventaire", "Voir son inventaire"),
            ("acheter <objet>", "Acheter un objet"),
            ("vendre <objet>", "Vendre un objet"),
            ("banque", "Voir son compte bancaire"),
            ("salaire", "Récupérer son salaire"),
        ]
    },
    "quotidien": {
        "emoji": "🏙️",
        "title": "Vie quotidienne",
        "cmds": [
            ("annonce <texte>", "Publier une annonce"),
            ("plainte @membre <raison>", "Déposer une plainte"),
            ("permis [type]", "Consulter un permis"),
            ("vehicule", "Voir ses véhicules"),
            ("immobilier", "Voir ses propriétés"),
            ("urgence <lieu> <raison>", "Déclarer une urgence"),
        ]
    },
    "immersion": {
        "emoji": "🎬",
        "title": "Immersion RP",
        "cmds": [
            ("dispatch <message>", "Envoyer une alerte"),
            ("temoin @membre <description>", "Enregistrer un témoignage"),
            ("dossier <titre>", "Créer un dossier RP"),
            ("journal <article>", "Publier un article"),
            ("flash <message>", "Alerte directe"),
        ]
    },
    "staff": {
        "emoji": "🛡️",
        "title": "Commandes Staff (asrp!)",
        "cmds": [
            ("identite", "Preuve que tu es staff"),
            ("server", "Lister tous les serveurs"),
            ("bl @user <raison>", "Ajouter à la blacklist"),
            ("bl-list", "Voir la blacklist"),
            ("dbl @user", "Retirer de la blacklist"),
            ("bl-check @user", "Vérifier si blacklist"),
            ("leave <id>", "Quitter un serveur"),
            ("send <channel_id> <msg>", "Envoyer un message"),
        ]
    },
}

class HelpView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=180)
        options = [discord.SelectOption(label=v["title"], value=k, emoji=v["emoji"]) 
                  for k, v in CATEGORIES.items()]
        sel = discord.ui.Select(placeholder="📂 Choisis une catégorie", options=options, min_values=1, max_values=1)
        sel.callback = self.on_select
        self.add_item(sel)
        self.author_id = author_id

    def build(self, key):
        cat = CATEGORIES[key]
        cmds = "\n".join(f"• `RP!{c[0]}` — {c[1]}" for c in cat["cmds"])
        return emb(f"{cat['emoji']}  {cat['title']}", f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n{cmds}", COLOR)

    async def interaction_check(self, inter):
        if inter.user.id != self.author_id:
            await inter.response.send_message("Ce menu n'est pas le tien.", ephemeral=True)
            return False
        return True

    async def on_select(self, inter):
        await inter.response.edit_message(embed=self.build(inter.data["values"][0]))

@bot.command(aliases=["aide", "h"])
async def help(ctx):
    """📖 Affiche l'aide du bot avec menu interactif."""
    e = emb("📖  Commandes Phénix RP", "Sélectionne une catégorie dans le menu ci-dessous.", COLOR)
    e.add_field(name="📂 Catégories disponibles", 
               value="\n".join(f"{v['emoji']} **{v['title']}**" for v in CATEGORIES.values()), 
               inline=False)
    v = HelpView(ctx.author.id)
    await ctx.send(embed=e, view=v)

# ═══════════════════════════════════════════════════════════════
# IDENTITÉ
# ═══════════════════════════════════════════════════════════════
@bot.command()
async def creerpersonnage(ctx, prenom: str, nom: str, age: int):
    """Créer un personnage RP."""
    u = get_user(ctx.author.id)
    if u["personnage"]:
        return await ctx.send(embed=err("Tu as déjà un personnage."))
    if not 16 <= age <= 120:
        return await ctx.send(embed=err("Âge entre 16 et 120 ans."))
    
    u["personnage"] = {
        "prenom": prenom.capitalize(),
        "nom": nom.upper(),
        "age": age,
        "metier": "Chômeur",
        "grade": "Aucun"
    }
    db.save()
    await ctx.send(embed=emb("✅  Personnage créé", f"{prenom} {nom}, {age} ans", OK))

@bot.command(aliases=["ident"])
async def identité(ctx, member: discord.Member = None):
    """Afficher une identité."""
    member = member or ctx.author
    u = get_user(member.id)
    p = u["personnage"]
    if not p:
        return await ctx.send(embed=err("Pas de personnage."))
    
    e = emb(f"🪪  {p['prenom']} {p['nom']}", 
           f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n👤 **{p['prenom']} {p['nom']}**\n🎂 {p['age']} ans\n💼 {p['metier']}\n🎖️ {p['grade']}", 
           COLOR)
    e.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=e)

@bot.command()
async def fiche(ctx, member: discord.Member = None):
    """Fiche RP complète."""
    member = member or ctx.author
    u = get_user(member.id)
    p = u["personnage"]
    if not p:
        return await ctx.send(embed=err("Pas de personnage."))
    
    e = emb(f"📋  Fiche RP — {p['prenom']} {p['nom']}", 
           f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n👤 {p['prenom']} {p['nom']}\n🎂 {p['age']} ans\n💼 {p['metier']}\n🎖️ {p['grade']}\n💰 {u['argent']} €\n🏦 {u['banque']} €", 
           INFO)
    e.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=e)

@bot.command()
async def setnom(ctx, nom: str):
    """Modifier son nom."""
    u = get_user(ctx.author.id)
    if not u["personnage"]:
        return await ctx.send(embed=err("Crée un personnage d'abord."))
    u["personnage"]["nom"] = nom.upper()
    db.save()
    await ctx.send(embed=emb("✅  Nom modifié", nom.upper(), OK))

@bot.command()
async def setage(ctx, age: int):
    """Modifier son âge."""
    u = get_user(ctx.author.id)
    if not u["personnage"] or not 16 <= age <= 120:
        return await ctx.send(embed=err("Personnage manquant ou âge invalide."))
    u["personnage"]["age"] = age
    db.save()
    await ctx.send(embed=emb("✅  Âge modifié", f"{age} ans", OK))

@bot.command()
async def setmetier(ctx, *, metier: str):
    """Changer de métier."""
    u = get_user(ctx.author.id)
    if not u["personnage"]:
        return await ctx.send(embed=err("Crée un personnage d'abord."))
    metiers = ["Chômeur", "Livreur", "Taxi", "Mécanicien", "Policier", "Pompier", "Médecin", "Avocat"]
    m = next((x for x in metiers if x.lower() == metier.lower()), None)
    if not m:
        return await ctx.send(embed=err(f"Métiers : {', '.join(metiers)}"))
    u["personnage"]["metier"] = m
    db.save()
    await ctx.send(embed=emb("✅  Métier changé", m, OK))

# ═══════════════════════════════════════════════════════════════
# POLICE
# ═══════════════════════════════════════════════════════════════
@bot.command()
async def amende(ctx, member: discord.Member, montant: int, *, raison: str):
    """Attribuer une amende."""
    if not 1 <= montant <= 50000:
        return await ctx.send(embed=err("Montant entre 1 et 50000."))
    u = get_user(member.id)
    if "amandes" not in u:
        u["amandes"] = []
    u["amandes"].append({"montant": montant, "raison": raison, "par": ctx.author.name})
    db.save()
    await ctx.send(embed=emb("🧾  Amende", f"{member.mention} • {montant} € • {raison}", WARN))

@bot.command()
async def arrestation(ctx, member: discord.Member, *, raison: str):
    """Enregistrer une arrestation."""
    u = get_user(member.id)
    if "arrests" not in u:
        u["arrests"] = []
    u["arrests"].append({"raison": raison, "par": ctx.author.name})
    db.save()
    await ctx.send(embed=emb("🚔  Arrestation", f"{member.mention} • {raison}", KO))

@bot.command()
async def casier(ctx, member: discord.Member = None):
    """Consulter le casier."""
    member = member or ctx.author
    u = get_user(member.id)
    arrests = u.get("arrests", [])
    txt = "\n".join(f"• {x['raison']} ({x['par']})" for x in arrests) if arrests else "Casier vierge ✅"
    await ctx.send(embed=emb(f"📂  Casier — {member.display_name}", txt, INFO))

@bot.command()
async def avisrecherche(ctx, member: discord.Member, *, raison: str):
    """Créer un avis de recherche."""
    await ctx.send(embed=emb("🚨  Avis de recherche", 
                            f"Suspect : {member.mention}\nRaison : {raison}\n⚠️ **DANGEREUX**", 
                            KO))

@bot.command()
async def radio(ctx, *, message: str):
    """Envoyer sur la radio."""
    await ctx.send(embed=emb("📻  Radio", f"{ctx.author.display_name} : {message}", INFO))

@bot.command()
async def renfort(ctx, lieu: str, *, raison: str):
    """Demander des renforts."""
    await ctx.send(embed=emb("🚓  Demande de renfort", f"Lieu : {lieu}\nRaison : {raison}", WARN))

# ═══════════════════════════════════════════════════════════════
# ÉCONOMIE
# ═══════════════════════════════════════════════════════════════
@bot.command()
async def solde(ctx, member: discord.Member = None):
    """Voir son argent."""
    member = member or ctx.author
    u = get_user(member.id)
    total = u["argent"] + u["banque"]
    e = emb(f"💰  Compte de {member.display_name}", 
           f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n💵 Liquide : {u['argent']} €\n🏦 Banque : {u['banque']} €\n💎 Total : {total} €", 
           COLOR)
    e.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=e)

@bot.command()
async def payer(ctx, member: discord.Member, montant: int):
    """Faire un paiement."""
    u1 = get_user(ctx.author.id)
    u2 = get_user(member.id)
    if montant > u1["argent"]:
        return await ctx.send(embed=err("Pas assez d'argent."))
    u1["argent"] -= montant
    u2["argent"] += montant
    db.save()
    await ctx.send(embed=emb("✅  Paiement", f"{ctx.author.mention} → {member.mention}\n{montant} €", OK))

@bot.command()
async def inventaire(ctx):
    """Voir son inventaire."""
    u = get_user(ctx.author.id)
    inv = u["inventaire"]
    txt = "\n".join(f"• {x}" for x in inv) if inv else "Inventaire vide."
    await ctx.send(embed=emb(f"🎒  Inventaire", txt, INFO))

@bot.command()
async def acheter(ctx, *, objet: str):
    """Acheter un objet."""
    u = get_user(ctx.author.id)
    prix = random.randint(50, 500)
    if u["argent"] < prix:
        return await ctx.send(embed=err(f"Il faut {prix} €, tu as {u['argent']} €."))
    u["argent"] -= prix
    u["inventaire"].append(objet)
    db.save()
    await ctx.send(embed=emb("✅  Achat", f"{objet} • {prix} €", OK))

@bot.command()
async def vendre(ctx, *, objet: str):
    """Vendre un objet."""
    u = get_user(ctx.author.id)
    if objet not in u["inventaire"]:
        return await ctx.send(embed=err("Tu n'as pas cet objet."))
    prix = random.randint(30, 300)
    u["inventaire"].remove(objet)
    u["argent"] += prix
    db.save()
    await ctx.send(embed=emb("✅  Vente", f"{objet} • {prix} €", OK))

@bot.command()
async def banque(ctx):
    """Voir son compte bancaire."""
    u = get_user(ctx.author.id)
    await ctx.send(embed=emb(f"🏦  Banque de {ctx.author.display_name}", 
                            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\nSolde : {u['banque']} €", 
                            INFO))

@bot.command()
async def salaire(ctx):
    """Récupérer son salaire."""
    u = get_user(ctx.author.id)
    p = u["personnage"]
    if not p or p["metier"] == "Chômeur":
        return await ctx.send(embed=err("Tu dois avoir un métier."))
    gain = random.randint(300, 1500)
    u["argent"] += gain
    db.save()
    await ctx.send(embed=emb("✅  Salaire reçu", f"{p['metier']} : {gain} € 💰", OK))

# ═══════════════════════════════════════════════════════════════
# VIE QUOTIDIENNE
# ═══════════════════════════════════════════════════════════════
@bot.command()
async def annonce(ctx, *, texte: str):
    """Publier une annonce."""
    await ctx.message.delete()
    await ctx.send(embed=emb(f"📢  Annonce de {ctx.author.display_name}", 
                            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n{texte}", 
                            COLOR))

@bot.command()
async def plainte(ctx, member: discord.Member, *, raison: str):
    """Déposer une plainte."""
    pid = secrets.token_hex(3).upper()
    await ctx.send(embed=emb(f"📋  Plainte contre {member.display_name}", 
                            f"Raison : {raison}\nID : `{pid}`\nPar : {ctx.author.mention}", 
                            WARN))

@bot.command()
async def permis(ctx, type_permis: str = "auto"):
    """Consulter un permis."""
    types = ["auto", "moto", "poids-lourd"]
    if type_permis.lower() not in types:
        return await ctx.send(embed=err(f"Types : {', '.join(types)}"))
    await ctx.send(embed=emb(f"🪪  Permis {type_permis}", "✅ Valide et à jour.", OK))

@bot.command()
async def vehicule(ctx):
    """Voir ses véhicules."""
    await ctx.send(embed=emb(f"🚗  Véhicules de {ctx.author.display_name}", 
                            "Aucun véhicule actuellement.", INFO))

@bot.command()
async def immobilier(ctx):
    """Voir ses propriétés."""
    await ctx.send(embed=emb(f"🏠  Propriétés de {ctx.author.display_name}", 
                            "Aucune propriété actuellement.", INFO))

@bot.command()
async def urgence(ctx, lieu: str, *, raison: str):
    """Déclarer une urgence."""
    await ctx.send(embed=emb("🆘  Urgence déclarée", 
                            f"Lieu : {lieu}\nType : {raison}\n⚠️ Dispatched", 
                            KO))

# ═══════════════════════════════════════════════════════════════
# IMMERSION RP
# ═══════════════════════════════════════════════════════════════
@bot.command()
async def dispatch(ctx, *, message: str):
    """Envoyer une alerte."""
    await ctx.send(embed=emb("📡  Dispatch", message, INFO))

@bot.command()
async def temoin(ctx, member: discord.Member, *, description: str):
    """Enregistrer un témoignage."""
    tid = secrets.token_hex(3).upper()
    await ctx.send(embed=emb(f"👁️  Témoignage — {member.display_name}", 
                            f"{description}\nID : `{tid}`", 
                            INFO))

@bot.command()
async def dossier(ctx, *, titre: str):
    """Créer un dossier RP."""
    did = secrets.token_hex(4).upper()
    await ctx.send(embed=emb(f"📂  Dossier RP", 
                            f"Titre : {titre}\nID : `{did}`\nPar : {ctx.author.mention}", 
                            INFO))

@bot.command()
async def journal(ctx, *, article: str):
    """Publier un article."""
    jid = secrets.token_hex(4).upper()
    preview = article[:200] + ("..." if len(article) > 200 else "")
    await ctx.send(embed=emb(f"📰  Article de presse", 
                            f"{preview}\n\nID : `{jid}`\nAuteur : {ctx.author.mention}", 
                            COLOR))

@bot.command()
async def flash(ctx, *, message: str):
    """Alerte directe."""
    await ctx.send(embed=emb(f"🔴  FLASH — ALERTE DIRECTE", message, KO))

# ═══════════════════════════════════════════════════════════════
# STAFF (asrp!)
# ═══════════════════════════════════════════════════════════════
@bot.command(name="identite")
@staff_only()
async def identite_staff(ctx):
    """Preuve que tu es staff avec grades."""
    code = secrets.token_hex(4).upper()
    exp = int(time.time()) + 86400
    
    # Récupérer les grades du membre
    uid = str(ctx.author.id)
    if "staff_grades" not in db.data:
        db.data["staff_grades"] = {}
    
    grades = db.data["staff_grades"].get(uid, [])
    grades_txt = "\n".join(f"• {g}" for g in grades) if grades else "Aucun grade"
    
    db.data["proofs"][code] = {"user": ctx.author.id, "exp": exp, "grades": grades}
    db.save()
    
    e = emb(f"🛡️  PREUVE STAFF", 
           f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n✅ **Membre vérifié du support**\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬", 
           STAFF)
    e.set_thumbnail(url=ctx.author.display_avatar.url)
    e.add_field(name="👤 Utilisateur", value=ctx.author.mention)
    e.add_field(name="🆔 ID", value=f"`{ctx.author.id}`")
    e.add_field(name="🎖️ Grade(s)", value=grades_txt, inline=False)
    e.add_field(name="📅 Généré le", value=f"<t:{int(time.time())}:f>")
    e.add_field(name="🔐 Code de vérification", value=f"`{code}`", inline=False)
    e.add_field(name="ℹ️ Info", value=f"Cet utilisateur est membre du staff officiel de **{SUPPORT_NAME}**.", inline=False)
    await ctx.send(embed=e)

@bot.command(name="ajouter")
@staff_only()
@commands.guild_only()
async def ajouter_grade(ctx, role_id: int, member: discord.Member = None):
    """Ajouter un rôle à un membre et l'enregistrer dans le staff."""
    member = member or ctx.author
    
    try:
        role = ctx.guild.get_role(role_id)
        if not role:
            return await ctx.send(embed=err(f"Rôle `{role_id}` non trouvé."))
        
        await member.add_roles(role)
        
        # Enregistrer dans la base de données
        if "staff_grades" not in db.data:
            db.data["staff_grades"] = {}
        
        uid = str(member.id)
        if uid not in db.data["staff_grades"]:
            db.data["staff_grades"][uid] = []
        
        if role.name not in db.data["staff_grades"][uid]:
            db.data["staff_grades"][uid].append(role.name)
        
        db.save()
        await ctx.send(embed=emb("✅  Grade ajouté", f"{member.mention} → {role.mention}", OK))
    except discord.HTTPException as e:
        await ctx.send(embed=err(str(e)))

@bot.command(name="retirer")
@staff_only()
@commands.guild_only()
async def retirer_grade(ctx, role_id: int, member: discord.Member = None):
    """Retirer un rôle à un membre."""
    member = member or ctx.author
    
    try:
        role = ctx.guild.get_role(role_id)
        if not role:
            return await ctx.send(embed=err(f"Rôle `{role_id}` non trouvé."))
        
        await member.remove_roles(role)
        
        # Retirer de la base de données
        if "staff_grades" not in db.data:
            db.data["staff_grades"] = {}
        
        uid = str(member.id)
        if uid in db.data["staff_grades"] and role.name in db.data["staff_grades"][uid]:
            db.data["staff_grades"][uid].remove(role.name)
        
        db.save()
        await ctx.send(embed=emb("✅  Grade retiré", f"{member.mention} ← {role.mention}", OK))
    except discord.HTTPException as e:
        await ctx.send(embed=err(str(e)))

@bot.command(name="server")
@staff_only()
async def server_list(ctx):
    """Lister tous les serveurs."""
    gs = sorted(bot.guilds, key=lambda g: g.member_count or 0, reverse=True)[:10]
    txt = "\n".join(f"`{g.id}` **{g.name}** — {g.member_count} 👥" for g in gs)
    await ctx.send(embed=emb(f"🏰  Serveurs ({len(bot.guilds)} total)", 
                            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n{txt}", 
                            STAFF))

@bot.command(name="bl")
@staff_only()
async def bl_add(ctx, user: discord.User, *, raison: str = "Non précisée"):
    """Ajouter à la blacklist."""
    db.data["blacklist"]["users"][str(user.id)] = {"reason": raison, "by": ctx.author.id, "date": int(time.time())}
    db.save()
    await ctx.send(embed=emb("⛔  Blacklist", f"{user} • {raison}", KO))

@bot.command(name="bl-list")
@staff_only()
async def bl_list_cmd(ctx):
    """Voir la blacklist."""
    users = db.data["blacklist"]["users"]
    if not users:
        return await ctx.send(embed=emb("⛔  Blacklist", "Aucun utilisateur blacklist.", OK))
    txt = "\n".join(f"• `{i}` {d['reason'][:50]}" for i, d in list(users.items())[:15])
    await ctx.send(embed=emb(f"⛔  Blacklist ({len(users)})", f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n{txt}", STAFF))

@bot.command(name="dbl")
@staff_only()
async def dbl_cmd(ctx, user: discord.User):
    """Retirer de la blacklist."""
    db.data["blacklist"]["users"].pop(str(user.id), None)
    db.save()
    await ctx.send(embed=emb("✅  Retiré", str(user), OK))

@bot.command(name="bl-check")
@staff_only()
async def bl_check(ctx, user: discord.User):
    """Vérifier si blacklist."""
    b = db.data["blacklist"]["users"].get(str(user.id))
    if b:
        await ctx.send(embed=emb("⛔  Blacklist", f"{user} • {b['reason']}", KO))
    else:
        await ctx.send(embed=emb("✅  Propre", str(user), OK))

@bot.command(name="leave")
@staff_only()
async def leave_cmd(ctx, guild_id: int):
    """Quitter un serveur."""
    g = bot.get_guild(guild_id)
    if not g or g.id == SUPPORT_GUILD_ID:
        return await ctx.send(embed=err("Serveur invalide."))
    await g.leave()
    await ctx.send(embed=emb("👋  Quitté", g.name, OK))

@bot.command(name="send")
@staff_only()
async def send_msg(ctx, channel_id: int, *, message: str):
    """Envoyer un message."""
    ch = bot.get_channel(channel_id)
    if not ch:
        return await ctx.send(embed=err("Salon non trouvé."))
    try:
        await ch.send(message)
        await ctx.send(embed=emb("✅  Envoyé", f"{ch.mention}", OK))
    except discord.HTTPException:
        await ctx.send(embed=err("Impossible d'envoyer."))

# ═══════════════════════════════════════════════════════════════
# LANCEMENT
# ═══════════════════════════════════════════════════════════════
@bot.event
async def on_guild_join(guild):
    if str(guild.id) in db.data["blacklist"]["guilds"]:
        await guild.leave()

if __name__ == "__main__":
    bot.run(TOKEN)
