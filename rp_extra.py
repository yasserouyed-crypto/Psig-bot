"""
rp_extra.py — Commandes RP avancées (identité, police, entreprises, économie, immersion…)
Fichier à placer À CÔTÉ de bot.py : il est chargé automatiquement au démarrage.
Si ce fichier est absent ou contient une erreur, le bot démarre quand même sans lui.
"""
import random
import string
import time
from typing import Optional

import discord
from discord.ext import commands

core = None  # module principal (bot.py), injecté au chargement
SEP = "━━━━━━━━━━━━━━━━━━━━"

LAW_JOBS = {"Policier", "Gendarme"}
SERVICE_JOBS = {"Policier", "Gendarme", "Pompier", "Médecin"}
GRADES = ["Stagiaire", "Employé", "Confirmé", "Responsable", "Directeur", "Patron"]
MANAGER_GRADES = {"responsable", "directeur", "patron", "chef", "capitaine", "commandant", "major", "colonel", "commissaire"}

SHOP = {  # clé: (nom, prix)
    "pain": ("🥖 Pain", 4), "eau": ("💧 Bouteille d'eau", 2), "burger": ("🍔 Burger", 12), "cafe": ("☕ Café", 3),
    "telephone": ("📱 Téléphone", 450), "radio": ("📻 Radio", 300), "menottes": ("🔗 Menottes", 150),
    "gilet": ("🦺 Gilet pare-balles", 1200), "trousse": ("🩹 Trousse de soin", 80),
    "jerrican": ("⛽ Jerrican", 40), "crochet": ("🔓 Kit de crochetage", 350),
}
PROPERTIES = {  # clé: (nom, prix)
    "studio": ("🏢 Studio", 60000), "appartement": ("🏙️ Appartement T3", 150000), "maison": ("🏡 Maison", 320000),
    "villa": ("🏖️ Villa", 900000), "garage": ("🅿️ Garage", 40000), "local": ("🏪 Local commercial", 250000),
}
LICENCES = {"voiture": (300, 0.7), "moto": (400, 0.65), "camion": (800, 0.55), "bateau": (500, 0.6), "arme": (1500, 0.4)}

RP_DEFAULT = {
    "staff_roles": [], "log": None, "radio": None, "dispatch": None, "annonces": None, "plaintes": None,
    "wanted": {}, "plaintes_list": [], "temoignages": [], "dossiers": [], "logs": [],
}

# ═══════════════════════ OUTILS ═══════════════════════
def U(uid):
    u = core.udata(uid)
    u.setdefault("grade", None)
    u.setdefault("on_duty", False)
    u.setdefault("duty_since", 0)
    u.setdefault("phone", None)
    u.setdefault("inventory", {})
    u.setdefault("properties", [])
    u.setdefault("last_salary", 0)
    u.setdefault("permis_extra", {})
    u.setdefault("cuffed", False)
    return u

def R(guild):
    return core.merge(RP_DEFAULT, core.gcfg(guild.id).setdefault("rp", {}))

def money(n):
    return core.money(n)

def emb(title, desc=None, color=None):
    return core.emb(title, desc, color if color is not None else core.COLOR)

def err(text):
    return core.err(text)

def rp_name(member):
    i = U(member.id)["identity"]
    return f"{i['prenom']} {i['nom']}" if i else member.display_name

def fmt_phone(p):
    return " ".join(p[i:i + 2] for i in range(0, len(p), 2))

def phone_of(uid):
    u = U(uid)
    if not u["phone"]:
        used = {d.get("phone") for d in core.db.data["users"].values()}
        while True:
            p = "06" + "".join(random.choices(string.digits, k=8))
            if p not in used:
                break
        u["phone"] = p
        core.db.save()
    return u["phone"]

def is_rp_admin(ctx):
    m = ctx.author
    if m.id in core.OWNER_IDS or m.guild_permissions.manage_guild:
        return True
    return any(r.id in R(ctx.guild)["staff_roles"] for r in m.roles)

def is_law(ctx):
    return is_rp_admin(ctx) or U(ctx.author.id)["job"] in LAW_JOBS

def rp_admin():
    def pred(ctx):
        if ctx.guild and is_rp_admin(ctx):
            return True
        raise commands.CheckFailure("Réservé au **staff RP** (permission *Gérer le serveur* ou rôle défini avec `RP!rpconfig staff @role`).")
    return commands.check(pred)

def law():
    def pred(ctx):
        if ctx.guild and is_law(ctx):
            return True
        raise commands.CheckFailure("Réservé aux **Policiers / Gendarmes** (`RP!metier`) ou au staff RP.")
    return commands.check(pred)

async def need_char(ctx, member=None):
    member = member or ctx.author
    if not U(member.id)["identity"]:
        who = "Tu n'as" if member == ctx.author else f"{member.display_name} n'a"
        await ctx.send(embed=err(f"{who} pas de personnage. `RP!creerpersonnage`."))
        return False
    return True

def chan(ctx, key):
    return ctx.guild.get_channel(R(ctx.guild)[key] or 0) or ctx.channel

async def rplog(guild, text):
    r = R(guild)
    r["logs"].append({"t": int(time.time()), "text": text[:300]})
    del r["logs"][:-200]
    core.db.save()
    ch = guild.get_channel(r["log"] or 0)
    if ch:
        e = discord.Embed(title="📜 Journal RP", description=text[:1900], color=core.COLOR, timestamp=discord.utils.utcnow())
        try:
            await ch.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            pass

def next_id(items):
    return max([x["id"] for x in items] + [0]) + 1

def fiche_embed(member, guild):
    u = U(member.id)
    i = u["identity"]
    e = emb(f"📇 Fiche RP — {rp_name(member)}")
    e.set_thumbnail(url=member.display_avatar.url)
    if not i:
        e.description = "Aucun personnage créé. `RP!creerpersonnage`"
        return e
    e.description = SEP
    e.add_field(name="👤 Identité", value=f"{i['prenom']} {i['nom']} · {i['age']} ans · {i.get('nationalite', '—')}", inline=False)
    e.add_field(name="🪪 N° CNI", value=f"`{i['num']}`")
    e.add_field(name="📱 Téléphone", value=fmt_phone(phone_of(member.id)))
    e.add_field(name="💼 Métier", value=u["job"] + (f" · {u['grade']}" if u["grade"] else ""))
    e.add_field(name="🕐 Service", value="🟢 En service" if u["on_duty"] else "🔴 Hors service")
    e.add_field(name="💰 Argent", value=money(u["money"] + u["bank"]))
    perms = ["voiture ✅" if u["permis"]["valid"] else "voiture ❌"] + [f"{k} ✅" for k, v in u["permis_extra"].items() if v]
    e.add_field(name="🪪 Permis", value=", ".join(perms))
    e.add_field(name="🚗 Véhicules", value=str(len(u["cars"])))
    e.add_field(name="🏠 Biens", value=str(len(u["properties"])))
    e.add_field(name="📂 Casier", value=f"{len(u['casier'])} entrée(s)")
    e.add_field(name="🧾 Amendes impayées", value=str(sum(1 for f in u["fines"] if not f["paid"])))
    if i.get("description"):
        e.add_field(name="📝 Description", value=i["description"][:200], inline=False)
    w = R(guild)["wanted"].get(str(member.id))
    if w:
        e.add_field(name="🚨 RECHERCHÉ", value=w["reason"][:200], inline=False)
        e.color = core.KO
    return e

# ═══════════════════════ FORMULAIRES / VUES ═══════════════════════
class OpenModalView(discord.ui.View):
    """Bouton qui ouvre un formulaire (une commande préfixe ne peut pas ouvrir un formulaire directement)."""
    def __init__(self, author, factory, label="Ouvrir le formulaire", emoji="📝"):
        super().__init__(timeout=300)
        self.author, self.factory = author, factory
        btn = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.primary)
        btn.callback = self.cb
        self.add_item(btn)

    async def cb(self, inter):
        if inter.user.id != self.author.id:
            return await inter.response.send_message("Ce bouton n'est pas pour toi.", ephemeral=True)
        await inter.response.send_modal(self.factory())

class CharModal(discord.ui.Modal, title="🪪 Créer ton personnage"):
    prenom = discord.ui.TextInput(label="Prénom", max_length=24)
    nom = discord.ui.TextInput(label="Nom", max_length=24)
    age = discord.ui.TextInput(label="Âge (16 à 99)", max_length=2)
    nationalite = discord.ui.TextInput(label="Nationalité", required=False, max_length=24, default="Française")
    bio = discord.ui.TextInput(label="Description (optionnel)", style=discord.TextStyle.paragraph,
                                       required=False, max_length=200)

    async def on_submit(self, inter):
        u = U(inter.user.id)
        age = str(self.age).strip()
        if u["identity"]:
            return await inter.response.send_message("Tu as déjà un personnage.", ephemeral=True)
        if not age.isdigit() or not 16 <= int(age) <= 99:
            return await inter.response.send_message("❌ Âge invalide (16 à 99).", ephemeral=True)
        u["identity"] = {
            "prenom": str(self.prenom).strip().capitalize(), "nom": str(self.nom).strip().upper(), "age": int(age),
            "num": "".join(random.choices(string.digits, k=12)),
            "nationalite": str(self.nationalite).strip() or "Française", "description": str(self.bio).strip(),
        }
        core.db.save()
        phone_of(inter.user.id)
        await inter.response.send_message(embed=fiche_embed(inter.user, inter.guild))

class ReportModal(discord.ui.Modal):
    def __init__(self, titre, kind):
        super().__init__(title=f"📝 {kind.capitalize()}"[:45])
        self.titre, self.kind = titre, kind
        self.lieu = discord.ui.TextInput(label="Lieu", max_length=80)
        self.faits = discord.ui.TextInput(label="Contenu / faits", style=discord.TextStyle.paragraph, max_length=1000)
        self.impliques = discord.ui.TextInput(label="Personnes impliquées", required=False, max_length=200)
        for item in (self.lieu, self.faits, self.impliques):
            self.add_item(item)

    async def on_submit(self, inter):
        r = R(inter.guild)
        d = {"id": next_id(r["dossiers"]), "kind": self.kind, "titre": self.titre[:100], "auteur": inter.user.id,
             "lieu": str(self.lieu), "contenu": str(self.faits), "impliques": str(self.impliques), "date": int(time.time())}
        r["dossiers"].append(d)
        core.db.save()
        e = emb(f"📁 {self.kind.capitalize()} n°{d['id']} — {d['titre']}", color=core.WARN)
        e.add_field(name="📍 Lieu", value=d["lieu"]).add_field(name="✍️ Auteur", value=inter.user.mention)
        e.add_field(name="📝 Contenu", value=d["contenu"][:900], inline=False)
        if d["impliques"]:
            e.add_field(name="👥 Impliqués", value=d["impliques"], inline=False)
        e.timestamp = discord.utils.utcnow()
        ch = inter.guild.get_channel(r["dispatch"] or 0) or inter.guild.get_channel(r["log"] or 0) or inter.channel
        await ch.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
        if ch != inter.channel:
            await inter.response.send_message(f"✅ {self.kind.capitalize()} n°{d['id']} enregistré.", ephemeral=True)
        else:
            await inter.response.send_message("✅ Enregistré.", ephemeral=True)
        await rplog(inter.guild, f"📁 {self.kind} n°{d['id']} « {d['titre']} » par {inter.user.mention}")

class InvoiceView(discord.ui.View):
    def __init__(self, issuer, target, amount, motif):
        super().__init__(timeout=900)
        self.issuer, self.target, self.amount, self.motif = issuer, target, amount, motif
        self.message = None

    async def interaction_check(self, inter):
        if inter.user.id != self.target.id:
            await inter.response.send_message("Cette facture ne t'est pas adressée.", ephemeral=True)
            return False
        return True

    def _done(self, inter, text, color):
        e = inter.message.embeds[0]
        for i, f in enumerate(e.fields):
            if f.name.endswith("Statut"):
                e.set_field_at(i, name=f.name, value=text, inline=False)
        e.color = color
        return e

    @discord.ui.button(label="Payer", emoji="✅", style=discord.ButtonStyle.success)
    async def pay(self, inter, button):
        t, i = U(self.target.id), U(self.issuer.id)
        if t["money"] < self.amount:
            return await inter.response.send_message("Tu n'as pas assez de liquide.", ephemeral=True)
        t["money"] -= self.amount
        i["money"] += self.amount
        core.db.save()
        await inter.response.edit_message(embed=self._done(inter, "✅ Payée", core.OK), view=None)
        self.stop()
        await rplog(inter.guild, f"🧾 Facture payée : {self.target.mention} → {self.issuer.mention} ({money(self.amount)}) — {self.motif}")

    @discord.ui.button(label="Refuser", emoji="❌", style=discord.ButtonStyle.danger)
    async def refuse(self, inter, button):
        await inter.response.edit_message(embed=self._done(inter, "❌ Refusée", core.KO), view=None)
        self.stop()

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass

class SceneView(discord.ui.View):
    def __init__(self, author, titre):
        super().__init__(timeout=3600)
        self.author, self.titre, self.members = author, titre, [author.id]

    def embed(self):
        e = emb(f"🎬 {self.titre}", f"Scène lancée par {self.author.mention}\n{SEP}")
        e.add_field(name=f"👥 Participants ({len(self.members)})", value=" ".join(f"<@{i}>" for i in self.members)[:1000])
        return e

    @discord.ui.button(label="Participer / Quitter", emoji="🎭", style=discord.ButtonStyle.primary)
    async def toggle(self, inter, button):
        uid = inter.user.id
        if uid in self.members:
            if uid == self.author.id:
                return await inter.response.send_message("Tu es l'organisateur de la scène.", ephemeral=True)
            self.members.remove(uid)
        else:
            self.members.append(uid)
        await inter.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Terminer", emoji="🏁", style=discord.ButtonStyle.danger)
    async def end(self, inter, button):
        if inter.user.id != self.author.id and not inter.user.guild_permissions.manage_guild:
            return await inter.response.send_message("Seul l'organisateur peut terminer la scène.", ephemeral=True)
        e = self.embed()
        e.title = f"🏁 {self.titre} (terminée)"
        e.color = core.KO
        await inter.response.edit_message(embed=e, view=None)
        self.stop()

RP_HELP = {
    "Identité & personnage": ("🪪", [
        ("identite @membre/ID", "Afficher l'identité d'un membre"), ("creerpersonnage", "Créer son personnage"),
        ("fiche @membre/ID", "Afficher une fiche RP"), ("setnom @membre nom", "Modifier le nom RP (staff RP)"),
        ("setage @membre âge", "Modifier l'âge RP (staff RP)"), ("setmetier @membre métier", "Attribuer un métier (staff RP)"),
        ("setgrade @membre grade", "Modifier un grade (staff RP)")]),
    "Police & sécurité": ("🚔", [
        ("menotter @membre", "Action RP de menottage"), ("fouille @membre", "Fouille RP (inventaire, argent)"),
        ("amende @membre montant raison", "Attribuer une amende RP"), ("arrestation @membre raison", "Enregistrer une arrestation"),
        ("avisrecherche @membre raison", "Créer un avis de recherche"), ("recherches", "Voir les avis de recherche"),
        ("leverrecherche @membre", "Lever un avis de recherche"), ("radio message", "Envoyer un message radio"),
        ("renfort lieu raison", "Demander des renforts"), ("rapport sujet", "Rapport d'intervention")]),
    "Entreprises & métiers": ("🏢", [
        ("recruter @membre métier", "Recruter un membre"), ("licencier @membre raison", "Licencier (staff RP)"),
        ("promotion @membre grade", "Promouvoir un membre"), ("demotion @membre grade raison", "Rétrograder un membre"),
        ("service on/off", "Prendre / terminer son service"), ("effectif", "Voir les agents en service"),
        ("facture @membre montant motif", "Créer une facture RP")]),
    "Économie & inventaire": ("💰", [
        ("payer @membre montant", "Paiement RP (ou `payer <id>` pour une amende)"), ("inventaire", "Afficher ton inventaire"),
        ("boutique", "Voir les objets à vendre"), ("acheter objet [quantité]", "Acheter un objet (ou un véhicule)"),
        ("vendre objet [quantité]", "Vendre un objet (ou un véhicule par ID)"), ("banque", "Compte RP"),
        ("salaire", "Récupérer son salaire (toutes les 6 h)")]),
    "Vie quotidienne": ("🏙️", [
        ("annuaire [nom]", "Consulter l'annuaire"), ("telephone @membre message", "Envoyer un SMS RP"),
        ("annonce texte", "Publier une annonce"), ("plainte @membre raison", "Déposer une plainte"),
        ("permis [type]", "Voir tes permis (voiture, moto, camion, bateau, arme)"), ("permis passer [type]", "Passer un permis"),
        ("vehicule", "Consulter ses véhicules"), ("immobilier", "Tes propriétés (catalogue/acheter/vendre)"),
        ("urgence lieu raison", "Déclarer une urgence")]),
    "Administration RP": ("🛠️", [
        ("rphelp", "Afficher toutes les commandes RP"), ("setargent @membre montant", "Modifier l'argent RP"),
        ("resetpersonnage @membre", "Réinitialiser un personnage"), ("rplogs", "Journaux RP"),
        ("rpconfig", "Configuration RP (staff, logs, radio, dispatch…)")]),
    "Immersion RP": ("🎬", [
        ("scene titre", "Créer une scène RP"), ("dice [faces]", "Lancer un dé"),
        ("911 message", "Simuler un appel aux secours"), ("dispatch message", "Envoyer une alerte RP"),
        ("temoin @membre description", "Enregistrer un témoignage"), ("dossier titre | id", "Créer ou consulter un dossier RP")]),
}

class RPHelpView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=180)
        self.author = author
        sel = discord.ui.Select(placeholder="📂 Choisis une catégorie",
                                options=[discord.SelectOption(label=k, emoji=v[0], value=k) for k, v in RP_HELP.items()])
        sel.callback = self.on_select
        self.add_item(sel)

    async def interaction_check(self, inter):
        if inter.user.id != self.author.id:
            await inter.response.send_message("Fais ta propre commande `RP!rphelp`.", ephemeral=True)
            return False
        return True

    async def on_select(self, inter):
        await inter.response.edit_message(embed=rp_help_embed(inter.data["values"][0]), view=self)

def rp_help_embed(name):
    emo, rows = RP_HELP[name]
    e = discord.Embed(title=f"{emo} {name}", color=core.COLOR,
                      description=SEP + "\n" + "\n".join(f"▸ `RP!{c}` → {d}" for c, d in rows))
    e.set_footer(text="Préfixe : RP! · rp! · Rp!  |  Menu ci-dessous pour changer de catégorie")
    return e

# ═══════════════════════ COMMANDES ═══════════════════════
class RPExtra(commands.Cog, name="RP avancé"):
    def __init__(self, bot, old):
        self.bot, self.old = bot, old

    # ───────── Identité et personnage ─────────
    @commands.command(name="identite", aliases=["identité", "identity"])
    @commands.guild_only()
    async def identite(self, ctx, member: Optional[discord.Member] = None):
        member = member or ctx.author
        if not await need_char(ctx, member):
            return
        await ctx.invoke(core.macni, member=member)

    @commands.command(name="creerpersonnage", aliases=["creerperso"])
    @commands.guild_only()
    async def creerpersonnage(self, ctx):
        if U(ctx.author.id)["identity"]:
            return await ctx.send(embed=err("Tu as déjà un personnage. `RP!fiche`."))
        await ctx.send(embed=emb("🪪 Création de personnage", "Appuie sur le bouton pour remplir le formulaire."),
                       view=OpenModalView(ctx.author, CharModal, "Créer mon personnage", "🪪"))

    @commands.command(name="fiche")
    @commands.guild_only()
    async def fiche(self, ctx, member: Optional[discord.Member] = None):
        await ctx.send(embed=fiche_embed(member or ctx.author, ctx.guild))

    @commands.command(name="setnom")
    @commands.guild_only()
    @rp_admin()
    async def setnom(self, ctx, member: discord.Member, *, nom: str):
        if not await need_char(ctx, member):
            return
        U(member.id)["identity"]["nom"] = nom[:24].upper()
        core.db.save()
        await ctx.send(embed=emb("✅ Nom modifié", f"{member.mention} → **{nom[:24].upper()}**", core.OK))
        await rplog(ctx.guild, f"✏️ {ctx.author.mention} a changé le nom de {member.mention} en {nom[:24].upper()}")

    @commands.command(name="setage")
    @commands.guild_only()
    @rp_admin()
    async def setage(self, ctx, member: discord.Member, age: int):
        if not await need_char(ctx, member):
            return
        if not 16 <= age <= 99:
            return await ctx.send(embed=err("Âge entre 16 et 99."))
        U(member.id)["identity"]["age"] = age
        core.db.save()
        await ctx.send(embed=emb("✅ Âge modifié", f"{member.mention} → **{age} ans**", core.OK))
        await rplog(ctx.guild, f"✏️ {ctx.author.mention} a changé l'âge de {member.mention} ({age})")

    @commands.command(name="setmetier")
    @commands.guild_only()
    @rp_admin()
    async def setmetier(self, ctx, member: discord.Member, *, metier: str):
        match = next((j for j in core.JOBS if j.lower() == metier.lower()), None)
        if not match:
            return await ctx.send(embed=err("Métier inconnu : " + ", ".join(core.JOBS)))
        u = U(member.id)
        u["job"], u["grade"] = match, (None if match == "Chômeur" else (u["grade"] or "Stagiaire"))
        u["on_duty"] = False
        core.db.save()
        await ctx.send(embed=emb("✅ Métier attribué", f"{member.mention} → **{match}**", core.OK))
        await rplog(ctx.guild, f"💼 {ctx.author.mention} a attribué le métier {match} à {member.mention}")

    @commands.command(name="setgrade")
    @commands.guild_only()
    @rp_admin()
    async def setgrade(self, ctx, member: discord.Member, *, grade: str):
        u = U(member.id)
        if u["job"] == "Chômeur":
            return await ctx.send(embed=err("Ce membre est chômeur : `RP!setmetier` d'abord."))
        u["grade"] = grade[:30]
        core.db.save()
        await ctx.send(embed=emb("✅ Grade modifié", f"{member.mention} → **{grade[:30]}**", core.OK))
        await rplog(ctx.guild, f"🎖️ {ctx.author.mention} a mis {member.mention} au grade {grade[:30]}")

    # ───────── Police et sécurité ─────────
    @commands.command(name="menotter")
    @commands.guild_only()
    @law()
    async def menotter(self, ctx, member: discord.Member):
        if member.bot or member == ctx.author:
            return await ctx.send(embed=err("Cible invalide."))
        t = U(member.id)
        t["cuffed"] = not t["cuffed"]
        core.db.save()
        if t["cuffed"]:
            txt, color = f"🔗 **{rp_name(ctx.author)}** menotte **{rp_name(member)}**.", core.KO
        else:
            txt, color = f"🔓 **{rp_name(ctx.author)}** retire les menottes de **{rp_name(member)}**.", core.OK
        await ctx.send(embed=emb("🚔 Menottage", txt, color))
        await rplog(ctx.guild, f"🔗 {ctx.author.mention} → {member.mention} ({'menotté' if t['cuffed'] else 'libéré'})")

    @commands.command(name="fouille")
    @commands.guild_only()
    @law()
    async def fouille(self, ctx, member: discord.Member):
        t = U(member.id)
        inv = "\n".join(f"{SHOP.get(k, (k,))[0]} ×{q}" for k, q in t["inventory"].items() if q > 0) or "Rien."
        e = emb(f"🔎 Fouille de {rp_name(member)}", f"**{rp_name(ctx.author)}** fouille **{rp_name(member)}**.\n{SEP}", core.WARN)
        e.add_field(name="🎒 Objets", value=inv[:900], inline=False)
        e.add_field(name="💵 Liquide", value=money(t["money"])).add_field(name="🪪 Permis", value="✅" if t["permis"]["valid"] else "❌")
        e.add_field(name="🚨 Recherché", value="Oui" if str(member.id) in R(ctx.guild)["wanted"] else "Non")
        await ctx.send(embed=e)
        await rplog(ctx.guild, f"🔎 {ctx.author.mention} a fouillé {member.mention}")

    @commands.command(name="amende")
    @commands.guild_only()
    @law()
    async def amende(self, ctx, member: discord.Member, montant: int, *, raison: str):
        if member.bot or not 1 <= montant <= 50000:
            return await ctx.send(embed=err("Montant entre 1 et 50 000 € et cible valide."))
        core.add_fine(U(member.id), montant, raison[:100], rp_name(ctx.author))
        core.db.save()
        await ctx.send(embed=emb("🧾 Amende", f"{member.mention} : **{money(montant)}**\n📝 {raison[:100]}\n👮 {rp_name(ctx.author)}", core.WARN))
        await rplog(ctx.guild, f"🧾 Amende {money(montant)} à {member.mention} par {ctx.author.mention} — {raison[:100]}")

    @commands.command(name="arrestation")
    @commands.guild_only()
    @law()
    async def arrestation(self, ctx, member: discord.Member, *, raison: str):
        if member.bot or member == ctx.author:
            return await ctx.send(embed=err("Cible invalide."))
        t = U(member.id)
        t["casier"].append({"motif": raison[:150], "by": rp_name(ctx.author), "date": int(time.time())})
        t["cuffed"] = False
        core.db.save()
        await ctx.send(embed=emb("🚔 Arrestation", f"{member.mention} est placé en garde à vue.\n📝 {raison[:150]}\n👮 {rp_name(ctx.author)}", core.KO))
        await rplog(ctx.guild, f"🚔 {ctx.author.mention} a arrêté {member.mention} — {raison[:150]}")

    @commands.command(name="avisrecherche", aliases=["wanted"])
    @commands.guild_only()
    @law()
    async def avisrecherche(self, ctx, member: discord.Member, *, raison: str):
        r = R(ctx.guild)
        r["wanted"][str(member.id)] = {"reason": raison[:200], "by": ctx.author.id, "date": int(time.time())}
        core.db.save()
        e = emb("🚨 AVIS DE RECHERCHE", f"{SEP}\n**{rp_name(member)}** ({member.mention})\n📝 {raison[:200]}\n{SEP}", core.KO)
        e.set_thumbnail(url=member.display_avatar.url)
        e.set_footer(text=f"Émis par {rp_name(ctx.author)}")
        e.timestamp = discord.utils.utcnow()
        ch = chan(ctx, "dispatch")
        await ch.send(embed=e)
        if ch != ctx.channel:
            await ctx.send(embed=emb("✅ Avis de recherche publié", ch.mention, core.OK))
        await rplog(ctx.guild, f"🚨 Avis de recherche sur {member.mention} par {ctx.author.mention} — {raison[:100]}")

    @commands.command(name="recherches")
    @commands.guild_only()
    async def recherches(self, ctx):
        w = R(ctx.guild)["wanted"]
        txt = "\n".join(f"<@{uid}> — {d['reason'][:80]}" for uid, d in w.items()) or "Aucun avis de recherche."
        await ctx.send(embed=emb(f"🚨 Avis de recherche ({len(w)})", txt, core.KO))

    @commands.command(name="leverrecherche")
    @commands.guild_only()
    @law()
    async def leverrecherche(self, ctx, member: discord.Member):
        if R(ctx.guild)["wanted"].pop(str(member.id), None) is None:
            return await ctx.send(embed=err("Aucun avis sur ce membre."))
        core.db.save()
        await ctx.send(embed=emb("✅ Avis de recherche levé", member.mention, core.OK))
        await rplog(ctx.guild, f"✅ Avis de recherche levé sur {member.mention} par {ctx.author.mention}")

    @commands.command(name="radio")
    @commands.guild_only()
    async def radio(self, ctx, *, message: str):
        u = U(ctx.author.id)
        if u["job"] == "Chômeur" and not is_rp_admin(ctx):
            return await ctx.send(embed=err("Il faut avoir un métier (`RP!metier`) pour utiliser la radio."))
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        tag = f"{u['job']}" + (f" • {u['grade']}" if u["grade"] else "")
        e = discord.Embed(description=f"📻 **[{tag}] {rp_name(ctx.author)}**\n{message[:1500]}", color=0x2ECC71)
        await chan(ctx, "radio").send(embed=e, allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="renfort")
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def renfort(self, ctx, lieu: str, *, raison: str):
        if not is_law(ctx):
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(embed=err("Réservé aux forces de l'ordre."))
        rid = core.gcfg(ctx.guild.id)["services"].get("police")
        e = emb("🚨 Demande de renforts", color=core.KO)
        e.add_field(name="👮 Demandeur", value=f"{rp_name(ctx.author)} ({ctx.author.mention})", inline=False)
        e.add_field(name="📍 Lieu", value=lieu).add_field(name="📝 Raison", value=raison[:500], inline=False)
        e.timestamp = discord.utils.utcnow()
        ch = chan(ctx, "dispatch")
        await ch.send(content=f"<@&{rid}>" if rid else None, embed=e, allowed_mentions=discord.AllowedMentions(roles=True))
        if ch != ctx.channel:
            await ctx.send(embed=emb("✅ Renforts demandés", ch.mention, core.OK))
        await rplog(ctx.guild, f"🚨 Renforts demandés par {ctx.author.mention} à {lieu} — {raison[:100]}")

    @commands.command(name="rapport")
    @commands.guild_only()
    @law()
    async def rapport(self, ctx, *, sujet: str):
        await ctx.send(embed=emb("📝 Rapport d'intervention", f"Sujet : **{sujet[:100]}**\nAppuie sur le bouton pour le rédiger."),
                       view=OpenModalView(ctx.author, lambda: ReportModal(sujet, "rapport"), "Rédiger le rapport"))

    # ───────── Entreprises et métiers ─────────
    def _can_manage(self, ctx, target_job):
        if is_rp_admin(ctx):
            return True
        a = U(ctx.author.id)
        return a["job"] == target_job and (a["grade"] or "").lower() in MANAGER_GRADES

    @commands.command(name="recruter")
    @commands.guild_only()
    async def recruter(self, ctx, member: discord.Member, *, metier: str):
        match = next((j for j in core.JOBS if j.lower() == metier.lower() and j != "Chômeur"), None)
        if not match:
            return await ctx.send(embed=err("Métier inconnu : " + ", ".join(j for j in core.JOBS if j != "Chômeur")))
        if not self._can_manage(ctx, match):
            return await ctx.send(embed=err(f"Il faut être gérant du métier **{match}** (grade Responsable, Directeur, Patron, Chef…) ou staff RP."))
        t = U(member.id)
        if member.bot or not t["identity"]:
            return await ctx.send(embed=err("Cette personne doit avoir un personnage (`RP!creerpersonnage`)."))
        if t["job"] != "Chômeur" and not is_rp_admin(ctx):
            return await ctx.send(embed=err("Ce membre a déjà un métier."))
        t["job"], t["grade"], t["on_duty"] = match, "Stagiaire", False
        core.db.save()
        await ctx.send(embed=emb("🤝 Recrutement", f"{member.mention} rejoint **{match}** (grade Stagiaire).\nRecruté par {rp_name(ctx.author)}.", core.OK))
        await rplog(ctx.guild, f"🤝 {ctx.author.mention} a recruté {member.mention} chez {match}")

    @commands.command(name="licencier")
    @commands.guild_only()
    @rp_admin()
    async def licencier(self, ctx, member: discord.Member, *, raison: str):
        t = U(member.id)
        if t["job"] == "Chômeur":
            return await ctx.send(embed=err("Ce membre est déjà chômeur."))
        ancien = t["job"]
        t["job"], t["grade"], t["on_duty"] = "Chômeur", None, False
        core.db.save()
        await ctx.send(embed=emb("📤 Licenciement", f"{member.mention} est licencié de **{ancien}**.\n📝 {raison[:200]}", core.KO))
        await rplog(ctx.guild, f"📤 {ctx.author.mention} a licencié {member.mention} ({ancien}) — {raison[:150]}")

    async def _grade_change(self, ctx, member, grade, title, raison=None):
        t = U(member.id)
        if t["job"] == "Chômeur":
            return await ctx.send(embed=err("Ce membre n'a pas de métier."))
        if not self._can_manage(ctx, t["job"]):
            return await ctx.send(embed=err("Tu dois être gérant de son métier ou staff RP."))
        ancien = t["grade"] or "—"
        t["grade"] = grade[:30]
        core.db.save()
        txt = f"{member.mention} ({t['job']}) : **{ancien}** → **{grade[:30]}**"
        if raison:
            txt += f"\n📝 {raison[:150]}"
        await ctx.send(embed=emb(title, txt, core.OK if title.startswith("🎖️") else core.WARN))
        await rplog(ctx.guild, f"{title} {ctx.author.mention} → {member.mention} : {ancien} → {grade[:30]}")

    @commands.command(name="promotion")
    @commands.guild_only()
    async def promotion(self, ctx, member: discord.Member, *, grade: str):
        await self._grade_change(ctx, member, grade, "🎖️ Promotion")

    @commands.command(name="demotion")
    @commands.guild_only()
    async def demotion(self, ctx, member: discord.Member, grade: str, *, raison: str):
        await self._grade_change(ctx, member, grade, "⬇️ Rétrogradation", raison)

    @commands.command(name="service", aliases=["duty"])
    @commands.guild_only()
    async def service(self, ctx, etat: str):
        u = U(ctx.author.id)
        etat = etat.lower()
        if u["job"] == "Chômeur":
            return await ctx.send(embed=err("Tu n'as pas de métier (`RP!metier`)."))
        if etat in ("on", "start", "debut"):
            if u["on_duty"]:
                return await ctx.send(embed=err("Tu es déjà en service."))
            u["on_duty"], u["duty_since"] = True, int(time.time())
            core.db.save()
            await ctx.send(embed=emb("🟢 Prise de service", f"**{rp_name(ctx.author)}** — {u['job']}", core.OK))
        elif etat in ("off", "stop", "fin"):
            if not u["on_duty"]:
                return await ctx.send(embed=err("Tu n'es pas en service."))
            minutes = (int(time.time()) - u["duty_since"]) // 60
            u["on_duty"] = False
            core.db.save()
            await ctx.send(embed=emb("🔴 Fin de service", f"**{rp_name(ctx.author)}** — {minutes // 60} h {minutes % 60} min de service.", core.KO))
        else:
            return await ctx.send(embed=err("Utilise `RP!service on` ou `RP!service off`."))
        await rplog(ctx.guild, f"🕐 {ctx.author.mention} : service {'on' if u['on_duty'] else 'off'} ({u['job']})")

    @commands.command(name="effectif")
    @commands.guild_only()
    async def effectif(self, ctx):
        groups = {}
        for uid, d in core.db.data["users"].items():
            if d.get("on_duty"):
                m = ctx.guild.get_member(int(uid))
                if m:
                    groups.setdefault(d.get("job", "?"), []).append(f"{rp_name(m)}" + (f" ({d['grade']})" if d.get("grade") else ""))
        e = emb("🟢 Effectif en service", color=core.OK)
        if not groups:
            e.description = "Personne n'est en service."
        for job, names in groups.items():
            e.add_field(name=f"{job} ({len(names)})", value="\n".join(names)[:900], inline=False)
        await ctx.send(embed=e)

    @commands.command(name="facture", aliases=["invoice"])
    @commands.guild_only()
    async def facture(self, ctx, member: discord.Member, montant: int, *, motif: str):
        if U(ctx.author.id)["job"] == "Chômeur":
            return await ctx.send(embed=err("Il faut un métier pour émettre une facture."))
        if member.bot or member == ctx.author or not 1 <= montant <= 100000:
            return await ctx.send(embed=err("Cible invalide ou montant hors limites (1 à 100 000 €)."))
        e = emb("🧾 Facture", f"{SEP}\n{member.mention}, tu as reçu une facture.\n{SEP}", core.WARN)
        e.add_field(name="🏢 Émetteur", value=f"{rp_name(ctx.author)} ({U(ctx.author.id)['job']})")
        e.add_field(name="💶 Montant", value=money(montant)).add_field(name="📝 Motif", value=motif[:300], inline=False)
        e.add_field(name="📌 Statut", value="⏳ En attente de paiement", inline=False)
        v = InvoiceView(ctx.author, member, montant, motif[:100])
        v.message = await ctx.send(content=member.mention, embed=e, view=v, allowed_mentions=discord.AllowedMentions(users=True))

    # ───────── Économie et inventaire ─────────
    @commands.command(name="payer")
    @commands.guild_only()
    async def payer(self, ctx, cible: str, montant: Optional[int] = None):
        """RP!payer @membre montant  ou  RP!payer <id amende>"""
        if montant is None:
            if cible.isdigit():
                return await self.old["payer"].callback(ctx, int(cible))
            return await ctx.send(embed=err("Utilisation : `RP!payer @membre montant` (ou `RP!payer <id>` pour une amende)."))
        try:
            member = await commands.MemberConverter().convert(ctx, cible)
        except commands.BadArgument:
            return await ctx.send(embed=err("Membre introuvable."))
        u, t = U(ctx.author.id), U(member.id)
        if member.bot or member == ctx.author or not 0 < montant <= u["money"]:
            return await ctx.send(embed=err("Paiement impossible (cible invalide ou liquide insuffisant)."))
        u["money"] -= montant
        t["money"] += montant
        core.db.save()
        await ctx.send(embed=emb("💸 Paiement", f"{rp_name(ctx.author)} → {rp_name(member)} : **{money(montant)}**", core.OK))

    @commands.command(name="inventaire", aliases=["inv"])
    @commands.guild_only()
    async def inventaire(self, ctx):
        inv = U(ctx.author.id)["inventory"]
        txt = "\n".join(f"{SHOP.get(k, (k,))[0]} ×{q}" for k, q in inv.items() if q > 0) or "Ton inventaire est vide. `RP!boutique`"
        await ctx.send(embed=emb(f"🎒 Inventaire de {rp_name(ctx.author)}", txt))

    @commands.command(name="boutique", aliases=["shop"])
    async def boutique(self, ctx):
        txt = "\n".join(f"`{k}` — {n} · **{money(p)}**" for k, (n, p) in SHOP.items())
        await ctx.send(embed=emb("🛒 Boutique", txt + "\n\nAcheter : `RP!acheter <objet> [quantité]`"))

    @commands.command(name="acheter")
    @commands.guild_only()
    async def acheter(self, ctx, objet: str, quantite: int = 1):
        objet = objet.lower()
        if objet in core.CARS:
            return await self.old["acheter"].callback(ctx, objet)
        if objet not in SHOP:
            return await ctx.send(embed=err("Objet inconnu. `RP!boutique` ou `RP!concessionnaire`."))
        u = U(ctx.author.id)
        if not u["identity"]:
            return await ctx.send(embed=err("Crée d'abord ton personnage : `RP!creerpersonnage`."))
        if not 1 <= quantite <= 50:
            return await ctx.send(embed=err("Quantité entre 1 et 50."))
        nom, prix = SHOP[objet]
        total = prix * quantite
        if u["money"] < total:
            return await ctx.send(embed=err(f"Il te manque {money(total - u['money'])}."))
        u["money"] -= total
        u["inventory"][objet] = u["inventory"].get(objet, 0) + quantite
        core.db.save()
        await ctx.send(embed=emb("🛍️ Achat", f"{nom} ×{quantite} pour **{money(total)}**.", core.OK))

    @commands.command(name="vendre")
    @commands.guild_only()
    async def vendre(self, ctx, objet: str, quantite: int = 1):
        if objet.isdigit():
            return await self.old["vendre"].callback(ctx, int(objet))
        objet = objet.lower()
        u = U(ctx.author.id)
        if objet not in SHOP or u["inventory"].get(objet, 0) < quantite or quantite < 1:
            return await ctx.send(embed=err("Tu n'as pas assez de cet objet (`RP!inventaire`)."))
        gain = SHOP[objet][1] * quantite // 2
        u["inventory"][objet] -= quantite
        u["money"] += gain
        core.db.save()
        await ctx.send(embed=emb("💵 Vente", f"{SHOP[objet][0]} ×{quantite} pour **{money(gain)}** (50 %).", core.OK))

    @commands.command(name="banque", aliases=["bank"])
    @commands.guild_only()
    async def banque(self, ctx):
        u = U(ctx.author.id)
        a, b = core.JOBS.get(u["job"], (0, 0))
        e = emb(f"🏦 Compte de {rp_name(ctx.author)}")
        e.add_field(name="💵 Liquide", value=money(u["money"])).add_field(name="🏦 Banque", value=money(u["bank"]))
        e.add_field(name="💼 Salaire estimé", value=f"{a}–{b} €" if b else "Aucun")
        e.add_field(name="🧾 Amendes impayées", value=money(sum(f["amount"] for f in u["fines"] if not f["paid"])))
        e.set_footer(text="RP!deposer · RP!retirer · RP!payer · RP!salaire")
        await ctx.send(embed=e)

    @commands.command(name="salaire", aliases=["paie"])
    @commands.guild_only()
    async def salaire(self, ctx):
        u = U(ctx.author.id)
        a, b = core.JOBS.get(u["job"], (0, 0))
        if b == 0:
            return await ctx.send(embed=err("Tu es chômeur. `RP!metier`."))
        now = int(time.time())
        left = u["last_salary"] + 21600 - now
        if left > 0:
            return await ctx.send(embed=err(f"Prochain salaire <t:{now + left}:R>."))
        mult = 1 + 0.15 * GRADES.index(u["grade"]) if u["grade"] in GRADES else 1.0
        if u["on_duty"]:
            mult *= 1.2
        gain = int(random.randint(a, b) * mult)
        u["money"] += gain
        u["last_salary"] = now
        core.db.save()
        await ctx.send(embed=emb("💶 Salaire", f"**{u['job']}**" + (f" ({u['grade']})" if u["grade"] else "") + f" : **{money(gain)}**" + (" (bonus de service +20 %)" if u["on_duty"] else ""), core.OK))

    # ───────── Vie quotidienne ─────────
    @commands.command(name="annuaire", aliases=["contacts"])
    @commands.guild_only()
    async def annuaire(self, ctx, *, recherche: str = None):
        rows = []
        for uid, d in list(core.db.data["users"].items()):
            if d.get("identity"):
                m = ctx.guild.get_member(int(uid))
                if m:
                    rows.append((rp_name(m), fmt_phone(phone_of(m.id)), d.get("job", "—")))
        if recherche:
            rows = [r for r in rows if recherche.lower() in r[0].lower()]
        rows.sort()
        txt = "\n".join(f"📱 `{p}` — **{n}** ({j})" for n, p, j in rows[:30]) or "Aucun contact."
        await ctx.send(embed=emb(f"📒 Annuaire ({len(rows)})", txt))

    @commands.command(name="telephone", aliases=["tel", "sms"])
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def telephone(self, ctx, member: discord.Member, *, message: str):
        if member.bot or member == ctx.author:
            return await ctx.send(embed=err("Destinataire invalide."))
        e = discord.Embed(color=0x3498DB, description=f"📱 **SMS de {rp_name(ctx.author)}** (`{fmt_phone(phone_of(ctx.author.id))}`)\n{message[:1500]}")
        e.set_footer(text=f"Pour {rp_name(member)}")
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        await ctx.send(content=member.mention, embed=e, allowed_mentions=discord.AllowedMentions(users=True))

    @commands.command(name="annonce")
    @commands.guild_only()
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def annonce(self, ctx, *, texte: str):
        e = emb("📢 Annonce", texte[:1800], core.COLOR)
        e.set_author(name=rp_name(ctx.author), icon_url=ctx.author.display_avatar.url)
        e.add_field(name="📱 Contact", value=fmt_phone(phone_of(ctx.author.id)) if U(ctx.author.id)["identity"] else ctx.author.mention)
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        await chan(ctx, "annonces").send(embed=e, allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="plainte")
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def plainte(self, ctx, member: discord.Member, *, raison: str):
        r = R(ctx.guild)
        d = {"id": next_id(r["plaintes_list"]), "de": ctx.author.id, "contre": member.id, "raison": raison[:500], "date": int(time.time())}
        r["plaintes_list"].append(d)
        core.db.save()
        e = emb(f"📨 Plainte n°{d['id']}", color=core.WARN)
        e.add_field(name="✍️ Plaignant", value=f"{rp_name(ctx.author)} ({ctx.author.mention})", inline=False)
        e.add_field(name="🎯 Contre", value=f"{rp_name(member)} ({member.mention})", inline=False)
        e.add_field(name="📝 Motif", value=raison[:900], inline=False)
        e.timestamp = discord.utils.utcnow()
        ch = chan(ctx, "plaintes")
        await ch.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
        if ch != ctx.channel:
            await ctx.send(embed=emb("✅ Plainte déposée", f"Numéro **{d['id']}**.", core.OK))
        await rplog(ctx.guild, f"📨 Plainte n°{d['id']} de {ctx.author.mention} contre {member.mention}")

    @commands.group(name="permis", invoke_without_command=True)
    @commands.guild_only()
    async def permis(self, ctx, *, cible: Optional[str] = None):
        member, ptype = ctx.author, None
        if cible:
            try:
                member = await commands.MemberConverter().convert(ctx, cible)
            except commands.BadArgument:
                ptype = cible.lower()
        if ptype and ptype not in LICENCES:
            return await ctx.send(embed=err("Types : " + ", ".join(LICENCES) + "."))
        u = U(member.id)
        e = emb(f"🪪 Permis de {member.display_name}")
        for t in ([ptype] if ptype else LICENCES):
            if t == "voiture":
                e.add_field(name="🚗 Voiture", value=("✅ Valide" if u["permis"]["valid"] else "❌ Non valide") + f" · {u['permis']['points']}/12 pts")
            else:
                e.add_field(name=f"🪪 {t.capitalize()}", value="✅ Obtenu" if u["permis_extra"].get(t) else "❌ Non obtenu")
        if member == ctx.author:
            e.set_footer(text="RP!permis passer <type> — " + ", ".join(f"{k} {v[0]} €" for k, v in LICENCES.items()))
        await ctx.send(embed=e)

    @permis.command(name="passer")
    async def permis_passer(self, ctx, type_: str = "voiture"):
        t = type_.lower()
        if t not in LICENCES:
            return await ctx.send(embed=err("Types : " + ", ".join(LICENCES) + "."))
        if t == "voiture":
            return await self.old["permis"].get_command("passer").callback(ctx)
        u = U(ctx.author.id)
        if not u["identity"]:
            return await ctx.send(embed=err("Crée d'abord ton personnage : `RP!creerpersonnage`."))
        if u["permis_extra"].get(t):
            return await ctx.send(embed=err("Tu as déjà ce permis."))
        if t == "arme" and u["casier"]:
            return await ctx.send(embed=err("Le port d'arme est refusé avec un casier non vierge."))
        cost, chance = LICENCES[t]
        if u["money"] < cost:
            return await ctx.send(embed=err(f"L'examen coûte {money(cost)}."))
        u["money"] -= cost
        if random.random() < chance:
            u["permis_extra"][t] = True
            res = emb(f"🎓 Permis {t} obtenu !", color=core.OK)
        else:
            res = emb("📉 Échec", "Tu as raté l'examen. Retente !", core.KO)
        core.db.save()
        await ctx.send(embed=res)

    @commands.command(name="vehicule", aliases=["vehicules"])
    @commands.guild_only()
    async def vehicule(self, ctx, member: Optional[discord.Member] = None):
        await ctx.invoke(core.garage, member=member)

    @commands.group(name="immobilier", aliases=["immo"], invoke_without_command=True)
    @commands.guild_only()
    async def immobilier(self, ctx, member: Optional[discord.Member] = None):
        member = member or ctx.author
        props = U(member.id)["properties"]
        txt = "\n".join(f"{PROPERTIES[p['key']][0]} · depuis <t:{p['since']}:d>" for p in props if p["key"] in PROPERTIES) or "Aucune propriété."
        e = emb(f"🏠 Propriétés de {member.display_name}", txt)
        e.set_footer(text="RP!immobilier catalogue · acheter <clé> · vendre <clé>")
        await ctx.send(embed=e)

    @immobilier.command(name="catalogue")
    async def immo_catalogue(self, ctx):
        txt = "\n".join(f"`{k}` — {n} · **{money(p)}**" for k, (n, p) in PROPERTIES.items())
        await ctx.send(embed=emb("🏘️ Catalogue immobilier", txt + "\n\nAcheter : `RP!immobilier acheter <clé>`"))

    @immobilier.command(name="acheter")
    async def immo_acheter(self, ctx, cle: str):
        cle = cle.lower()
        u = U(ctx.author.id)
        if cle not in PROPERTIES:
            return await ctx.send(embed=err("Bien inconnu. `RP!immobilier catalogue`."))
        if not u["identity"]:
            return await ctx.send(embed=err("Crée d'abord ton personnage : `RP!creerpersonnage`."))
        if len(u["properties"]) >= 5:
            return await ctx.send(embed=err("Maximum 5 propriétés."))
        nom, prix = PROPERTIES[cle]
        if u["money"] < prix:
            return await ctx.send(embed=err(f"Il te manque {money(prix - u['money'])} en liquide."))
        u["money"] -= prix
        u["properties"].append({"key": cle, "since": int(time.time())})
        core.db.save()
        await ctx.send(embed=emb("🔑 Achat immobilier", f"Tu deviens propriétaire : {nom} pour **{money(prix)}**.", core.OK))

    @immobilier.command(name="vendre")
    async def immo_vendre(self, ctx, cle: str):
        cle = cle.lower()
        u = U(ctx.author.id)
        p = next((x for x in u["properties"] if x["key"] == cle), None)
        if not p or cle not in PROPERTIES:
            return await ctx.send(embed=err("Tu ne possèdes pas ce bien."))
        gain = int(PROPERTIES[cle][1] * 0.7)
        u["properties"].remove(p)
        u["money"] += gain
        core.db.save()
        await ctx.send(embed=emb("💵 Vente immobilière", f"{PROPERTIES[cle][0]} vendu **{money(gain)}** (70 %).", core.OK))

    async def _emergency(self, ctx, label, icon, lieu, raison):
        r = R(ctx.guild)
        ch = ctx.guild.get_channel(r["dispatch"] or 0) or ctx.channel
        svc = core.gcfg(ctx.guild.id)["services"]
        pings = " ".join(f"<@&{rid}>" for rid in svc.values() if rid)
        e = emb(f"{icon} {label}", color=core.KO)
        e.add_field(name="👤 Appelant", value=f"{rp_name(ctx.author)} ({ctx.author.mention})", inline=False)
        e.add_field(name="📍 Lieu", value=lieu).add_field(name="📝 Situation", value=raison[:700], inline=False)
        e.timestamp = discord.utils.utcnow()
        await ch.send(content=pings or None, embed=e, allowed_mentions=discord.AllowedMentions(roles=True))
        if ch != ctx.channel:
            await ctx.send(embed=emb("✅ Appel transmis", "Les secours ont été prévenus.", core.OK))
        await rplog(ctx.guild, f"{icon} {label} de {ctx.author.mention} à {lieu} — {raison[:100]}")

    @commands.command(name="urgence")
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def urgence(self, ctx, lieu: str, *, raison: str):
        await self._emergency(ctx, "Urgence", "🆘", lieu, raison)

    # ───────── Administration RP ─────────
    @commands.command(name="rphelp")
    async def rphelp(self, ctx):
        e = discord.Embed(title="🎭 Commandes RP", color=core.COLOR,
                          description=f"Choisis une catégorie dans le menu.\n{SEP}\n" +
                                      "\n".join(f"{v[0]} **{k}** — {len(v[1])} commande(s)" for k, v in RP_HELP.items()))
        await ctx.send(embed=e, view=RPHelpView(ctx.author))

    @commands.command(name="setargent")
    @commands.guild_only()
    @rp_admin()
    async def setargent(self, ctx, member: discord.Member, montant: int):
        if not 0 <= montant <= 10_000_000:
            return await ctx.send(embed=err("Montant entre 0 et 10 000 000."))
        U(member.id)["money"] = montant
        core.db.save()
        await ctx.send(embed=emb("✅ Argent modifié", f"{member.mention} : **{money(montant)}** en liquide.", core.OK))
        await rplog(ctx.guild, f"💰 {ctx.author.mention} a fixé l'argent de {member.mention} à {money(montant)}")

    @commands.command(name="resetpersonnage")
    @commands.guild_only()
    @rp_admin()
    async def resetpersonnage(self, ctx, member: discord.Member):
        v = core.Confirm(ctx.author)
        m = await ctx.send(embed=emb("⚠️ Réinitialisation", f"Tout le personnage de {member.mention} sera effacé (identité, argent, véhicules, biens, casier…). Confirmer ?", core.WARN), view=v)
        await v.wait()
        if not v.value:
            return await m.edit(embed=emb("Annulé", color=core.KO), view=None)
        core.db.data["users"][str(member.id)] = {}
        core.db.save()
        await m.edit(embed=emb("✅ Personnage réinitialisé", member.mention, core.OK), view=None)
        await rplog(ctx.guild, f"♻️ {ctx.author.mention} a réinitialisé le personnage de {member.mention}")

    @commands.command(name="rplogs")
    @commands.guild_only()
    @rp_admin()
    async def rplogs(self, ctx):
        logs = R(ctx.guild)["logs"][-15:]
        txt = "\n".join(f"<t:{x['t']}:t> {x['text']}" for x in reversed(logs)) or "Aucune entrée."
        await ctx.send(embed=emb("📜 Journaux RP (15 derniers)", txt[:4000]), allowed_mentions=discord.AllowedMentions.none())

    @commands.group(name="rpconfig", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def rpconfig(self, ctx):
        r = R(ctx.guild)
        def ch(i): return f"<#{i}>" if i else "❌ non défini (salon actuel)"
        e = emb("⚙️ Configuration RP")
        e.add_field(name="👮 Staff RP", value=" ".join(f"<@&{i}>" for i in r["staff_roles"]) or "Permission *Gérer le serveur* uniquement", inline=False)
        e.add_field(name="📜 Journal", value=ch(r["log"])).add_field(name="📻 Radio", value=ch(r["radio"]))
        e.add_field(name="📡 Dispatch", value=ch(r["dispatch"])).add_field(name="📢 Annonces", value=ch(r["annonces"]))
        e.add_field(name="📨 Plaintes", value=ch(r["plaintes"]))
        e.set_footer(text="rpconfig staff @role · logs|radio|dispatch|annonces|plaintes #salon")
        await ctx.send(embed=e)

    @rpconfig.command(name="staff")
    async def rpc_staff(self, ctx, role: discord.Role):
        r = R(ctx.guild)
        if role.id in r["staff_roles"]:
            r["staff_roles"].remove(role.id)
            txt = f"{role.mention} retiré du staff RP."
        else:
            r["staff_roles"].append(role.id)
            txt = f"{role.mention} ajouté au staff RP."
        core.db.save()
        await ctx.send(embed=emb("✅ Staff RP", txt, core.OK))

    async def _set_chan(self, ctx, key, channel, label):
        R(ctx.guild)[key] = channel.id
        core.db.save()
        await ctx.send(embed=emb(f"✅ {label}", channel.mention, core.OK))

    @rpconfig.command(name="logs")
    async def rpc_logs(self, ctx, channel: discord.TextChannel):
        await self._set_chan(ctx, "log", channel, "Journal RP")

    @rpconfig.command(name="radio")
    async def rpc_radio(self, ctx, channel: discord.TextChannel):
        await self._set_chan(ctx, "radio", channel, "Salon radio")

    @rpconfig.command(name="dispatch")
    async def rpc_dispatch(self, ctx, channel: discord.TextChannel):
        await self._set_chan(ctx, "dispatch", channel, "Salon dispatch")

    @rpconfig.command(name="annonces")
    async def rpc_annonces(self, ctx, channel: discord.TextChannel):
        await self._set_chan(ctx, "annonces", channel, "Salon des annonces")

    @rpconfig.command(name="plaintes")
    async def rpc_plaintes(self, ctx, channel: discord.TextChannel):
        await self._set_chan(ctx, "plaintes", channel, "Salon des plaintes")

    # ───────── Immersion RP ─────────
    @commands.command(name="scene")
    @commands.guild_only()
    async def scene(self, ctx, *, titre: str):
        v = SceneView(ctx.author, titre[:100])
        await ctx.send(embed=v.embed(), view=v)

    @commands.command(name="dice", aliases=["des", "de", "roll"])
    async def dice(self, ctx, faces: int = 6):
        faces = max(2, min(faces, 1000))
        await ctx.send(embed=emb("🎲 Lancer de dé", f"{ctx.author.mention} fait **{random.randint(1, faces)}** (d{faces})"))

    @commands.command(name="911")
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def appel911(self, ctx, *, message: str):
        await self._emergency(ctx, "Appel au 911", "📞", ctx.channel.mention, message)

    @commands.command(name="dispatch")
    @commands.guild_only()
    async def dispatch(self, ctx, *, message: str):
        if U(ctx.author.id)["job"] not in SERVICE_JOBS and not is_rp_admin(ctx):
            return await ctx.send(embed=err("Réservé aux services (Policier, Gendarme, Pompier, Médecin) ou au staff RP."))
        e = emb("📡 Dispatch", message[:1800], core.WARN)
        e.set_footer(text=f"{rp_name(ctx.author)} • {U(ctx.author.id)['job']}")
        e.timestamp = discord.utils.utcnow()
        ch = chan(ctx, "dispatch")
        await ch.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
        if ch != ctx.channel:
            await ctx.send(embed=emb("✅ Alerte envoyée", ch.mention, core.OK))

    @commands.command(name="temoin")
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def temoin(self, ctx, member: discord.Member, *, description: str):
        r = R(ctx.guild)
        d = {"id": next_id(r["temoignages"]), "temoin": ctx.author.id, "sujet": member.id, "texte": description[:800], "date": int(time.time())}
        r["temoignages"].append(d)
        core.db.save()
        e = emb(f"👁️ Témoignage n°{d['id']}", color=core.WARN)
        e.add_field(name="🧍 Témoin", value=f"{rp_name(ctx.author)} ({ctx.author.mention})", inline=False)
        e.add_field(name="🎯 Concerne", value=f"{rp_name(member)} ({member.mention})", inline=False)
        e.add_field(name="📝 Déclaration", value=description[:900], inline=False)
        e.timestamp = discord.utils.utcnow()
        ch = chan(ctx, "plaintes")
        await ch.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
        if ch != ctx.channel:
            await ctx.send(embed=emb("✅ Témoignage enregistré", f"Numéro **{d['id']}**.", core.OK))
        await rplog(ctx.guild, f"👁️ Témoignage n°{d['id']} de {ctx.author.mention} sur {member.mention}")

    @commands.command(name="dossier")
    @commands.guild_only()
    @law()
    async def dossier(self, ctx, *, arg: str):
        if arg.isdigit():
            d = next((x for x in R(ctx.guild)["dossiers"] if x["id"] == int(arg)), None)
            if not d:
                return await ctx.send(embed=err("Dossier introuvable."))
            e = emb(f"📁 {d['kind'].capitalize()} n°{d['id']} — {d['titre']}", color=core.WARN)
            e.add_field(name="📍 Lieu", value=d["lieu"]).add_field(name="✍️ Auteur", value=f"<@{d['auteur']}>")
            e.add_field(name="📝 Contenu", value=d["contenu"][:900], inline=False)
            if d["impliques"]:
                e.add_field(name="👥 Impliqués", value=d["impliques"], inline=False)
            e.add_field(name="🗓️ Date", value=f"<t:{d['date']}:f>")
            return await ctx.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
        await ctx.send(embed=emb("📁 Nouveau dossier", f"Titre : **{arg[:100]}**\nAppuie sur le bouton pour le remplir."),
                       view=OpenModalView(ctx.author, lambda: ReportModal(arg, "dossier"), "Remplir le dossier", "📁"))

async def setup(bot):
    global core
    core = bot.core
    names = ("acheter", "vendre", "payer", "permis", "amende", "arrestation", "fouille", "annonce", "des")
    old = {n: bot.remove_command(n) for n in names}
    try:
        await bot.add_cog(RPExtra(bot, old))
    except Exception:
        for cmd in old.values():  # on remet les anciennes commandes si le chargement échoue
            if cmd and not bot.get_command(cmd.name):
                bot.add_command(cmd)
        raise
    core.HELP.update({f"RP · {k}": v for k, v in RP_HELP.items()})
