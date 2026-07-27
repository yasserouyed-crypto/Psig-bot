require('dotenv').config();
const { REST, Routes, SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const config = require('./config.json');

const commands = [
  // ----- Tickets -----
  new SlashCommandBuilder().setName('panel-ticket').setDescription('Publie le panneau de tickets de support').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild),
  new SlashCommandBuilder().setName('close').setDescription('Ferme le ticket en cours'),
  new SlashCommandBuilder().setName('recrutement').setDescription('Candidature de recrutement'),
  new SlashCommandBuilder().setName('staff').setDescription("Candidature pour l'équipe staff"),
  new SlashCommandBuilder().setName('signalement').setDescription('Signaler un problème'),
  new SlashCommandBuilder().setName('gang').setDescription('Demande de création de gang'),
  new SlashCommandBuilder().setName('entreprise').setDescription("Demande de création d'entreprise"),
  new SlashCommandBuilder().setName('entreprises').setDescription('Liste des entreprises du serveur'),
  new SlashCommandBuilder().setName('entreprise-ajouter').setDescription('Ajoute une entreprise à la liste (staff)').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('nom').setDescription('Nom').setRequired(true))
    .addStringOption(o => o.setName('secteur').setDescription("Secteur d'activité").setRequired(true))
    .addUserOption(o => o.setName('proprietaire').setDescription('Propriétaire').setRequired(true)),

  // ----- Sanctions -----
  new SlashCommandBuilder().setName('kick').setDescription('Expulse un membre').setDefaultMemberPermissions(PermissionFlagsBits.KickMembers)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)).addStringOption(o => o.setName('raison').setDescription('Raison').setRequired(false)),
  new SlashCommandBuilder().setName('ban').setDescription('Bannit un membre').setDefaultMemberPermissions(PermissionFlagsBits.BanMembers)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)).addStringOption(o => o.setName('raison').setDescription('Raison').setRequired(false)),
  new SlashCommandBuilder().setName('tempban').setDescription('Bannit temporairement un membre').setDefaultMemberPermissions(PermissionFlagsBits.BanMembers)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)).addIntegerOption(o => o.setName('heures').setDescription('Durée en heures').setRequired(true)).addStringOption(o => o.setName('raison').setDescription('Raison').setRequired(false)),
  new SlashCommandBuilder().setName('unban').setDescription('Débannit un membre via son ID').setDefaultMemberPermissions(PermissionFlagsBits.BanMembers)
    .addStringOption(o => o.setName('id').setDescription("ID Discord du membre").setRequired(true)),
  new SlashCommandBuilder().setName('softban').setDescription('Bannit puis débannit aussitôt (nettoie les messages)').setDefaultMemberPermissions(PermissionFlagsBits.BanMembers)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)).addStringOption(o => o.setName('raison').setDescription('Raison').setRequired(false)),
  new SlashCommandBuilder().setName('mute').setDescription('Rend un membre muet').setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)).addIntegerOption(o => o.setName('minutes').setDescription('Durée').setRequired(true)).addStringOption(o => o.setName('raison').setDescription('Raison').setRequired(false)),
  new SlashCommandBuilder().setName('unmute').setDescription('Retire le mute').setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)),
  new SlashCommandBuilder().setName('timeout').setDescription('Applique un timeout').setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)).addIntegerOption(o => o.setName('minutes').setDescription('Durée').setRequired(true)).addStringOption(o => o.setName('raison').setDescription('Raison').setRequired(false)),
  new SlashCommandBuilder().setName('untimeout').setDescription('Retire le timeout').setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)),
  new SlashCommandBuilder().setName('warn').setDescription('Avertit un membre').setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)).addStringOption(o => o.setName('raison').setDescription('Raison').setRequired(true)),
  new SlashCommandBuilder().setName('warnings').setDescription("Liste les avertissements d'un membre")
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(false)),
  new SlashCommandBuilder().setName('unwarn').setDescription('Retire un avertissement par ID').setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)).addStringOption(o => o.setName('id').setDescription("ID de l'avertissement").setRequired(true)),
  new SlashCommandBuilder().setName('clearwarns').setDescription("Efface tous les avertissements d'un membre").setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)),
  new SlashCommandBuilder().setName('note').setDescription('Ajoute une note interne (staff)').setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)).addStringOption(o => o.setName('texte').setDescription('Contenu de la note').setRequired(true)),
  new SlashCommandBuilder().setName('notes').setDescription("Liste les notes internes d'un membre").setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)),
  new SlashCommandBuilder().setName('deletenote').setDescription('Supprime une note par ID').setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addStringOption(o => o.setName('id').setDescription('ID de la note').setRequired(true)),
  new SlashCommandBuilder().setName('casier').setDescription('Affiche le casier judiciaire complet')
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(false)),
  new SlashCommandBuilder().setName('staffstats').setDescription('Statistiques et classement des modérateurs').setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers),

  // ----- Administration -----
  new SlashCommandBuilder().setName('clear').setDescription('Supprime des messages').setDefaultMemberPermissions(PermissionFlagsBits.ManageMessages)
    .addIntegerOption(o => o.setName('nombre').setDescription('Nombre de messages (max 100)').setRequired(true)),
  new SlashCommandBuilder().setName('lock').setDescription('Verrouille le salon').setDefaultMemberPermissions(PermissionFlagsBits.ManageChannels),
  new SlashCommandBuilder().setName('unlock').setDescription('Déverrouille le salon').setDefaultMemberPermissions(PermissionFlagsBits.ManageChannels),
  new SlashCommandBuilder().setName('slowmode').setDescription('Règle le mode lent du salon').setDefaultMemberPermissions(PermissionFlagsBits.ManageChannels)
    .addIntegerOption(o => o.setName('secondes').setDescription('Secondes entre chaque message (0 = désactivé)').setRequired(true)),
  new SlashCommandBuilder().setName('nuke').setDescription('Recrée le salon (supprime tout son historique)').setDefaultMemberPermissions(PermissionFlagsBits.ManageChannels),
  new SlashCommandBuilder().setName('embed').setDescription('Envoie un message en embed').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('titre').setDescription('Titre').setRequired(true)).addStringOption(o => o.setName('texte').setDescription('Contenu').setRequired(true)).addStringOption(o => o.setName('couleur').setDescription('Couleur hex (ex: #FF0000)').setRequired(false)),
  new SlashCommandBuilder().setName('roleinfo').setDescription("Affiche les infos d'un rôle")
    .addRoleOption(o => o.setName('role').setDescription('Le rôle').setRequired(true)),

  // ----- Configuration -----
  new SlashCommandBuilder().setName('set-welcome').setDescription('Définit le salon de bienvenue').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addChannelOption(o => o.setName('salon').setDescription('Salon').setRequired(true)),
  new SlashCommandBuilder().setName('set-reglement').setDescription('Définit le règlement').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('texte').setDescription('Texte du règlement').setRequired(true)),
  new SlashCommandBuilder().setName('set-liens').setDescription('Définit les liens utiles').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('texte').setDescription('Texte des liens').setRequired(true)),
  new SlashCommandBuilder().setName('set-urgence').setDescription("Définit les numéros d'urgence").setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('texte').setDescription('Texte').setRequired(true)),
  new SlashCommandBuilder().setName('set-horaire').setDescription('Définit les horaires').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('texte').setDescription('Texte').setRequired(true)),
  new SlashCommandBuilder().setName('set-suggestions').setDescription('Définit le salon de suggestions').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addChannelOption(o => o.setName('salon').setDescription('Salon').setRequired(true)),
  new SlashCommandBuilder().setName('set-logs').setDescription('Définit le salon de logs').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addChannelOption(o => o.setName('salon').setDescription('Salon').setRequired(true)),

  // ----- Informations -----
  new SlashCommandBuilder().setName('reglement').setDescription('Affiche le règlement'),
  new SlashCommandBuilder().setName('liens').setDescription('Affiche les liens utiles'),
  new SlashCommandBuilder().setName('urgence').setDescription("Affiche les numéros d'urgence"),
  new SlashCommandBuilder().setName('horaire').setDescription('Affiche les horaires'),
  new SlashCommandBuilder().setName('codes').setDescription('Affiche les codes radio'),
  new SlashCommandBuilder().setName('roles').setDescription('Liste les rôles du serveur'),
  new SlashCommandBuilder().setName('help').setDescription('Affiche toutes les commandes'),

  // ----- Niveaux -----
  new SlashCommandBuilder().setName('rank').setDescription('Affiche ton niveau').addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(false)),
  new SlashCommandBuilder().setName('leaderboard').setDescription('Classement des membres actifs'),

  // ----- Roleplay -----
  new SlashCommandBuilder().setName('creer-personnage').setDescription('Crée ta fiche de personnage')
    .addStringOption(o => o.setName('nom').setDescription('Nom').setRequired(true)).addIntegerOption(o => o.setName('age').setDescription('Âge').setRequired(true)).addStringOption(o => o.setName('description').setDescription('Description').setRequired(true)),
  new SlashCommandBuilder().setName('profil').setDescription('Affiche une fiche de personnage').addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(false)),
  new SlashCommandBuilder().setName('id').setDescription("Affiche la carte d'identité RP (alias de /profil)").addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(false)),
  new SlashCommandBuilder().setName('me').setDescription('Effectue une action RP').addStringOption(o => o.setName('action').setDescription('Action').setRequired(true)),
  new SlashCommandBuilder().setName('dire').setDescription('Parle en tant que ton personnage').addStringOption(o => o.setName('message').setDescription('Message').setRequired(true)),
  new SlashCommandBuilder().setName('cni').setDescription("Génère une carte d'identité RP")
    .addStringOption(o => o.setName('nom').setDescription('Nom complet').setRequired(true)).addStringOption(o => o.setName('naissance').setDescription('Date de naissance').setRequired(true)).addStringOption(o => o.setName('adresse').setDescription('Adresse').setRequired(true)),
  new SlashCommandBuilder().setName('carte-identite').setDescription("Consulte une carte d'identité enregistrée")
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(false)),

  // ----- Utilitaires -----
  new SlashCommandBuilder().setName('ping').setDescription('Latence du bot'),
  new SlashCommandBuilder().setName('avatar').setDescription("Affiche l'avatar d'un membre").addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(false)),
  new SlashCommandBuilder().setName('userinfo').setDescription("Informations sur un membre").addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(false)),
  new SlashCommandBuilder().setName('serverinfo').setDescription('Informations sur le serveur'),
  new SlashCommandBuilder().setName('suggestion').setDescription('Envoie une suggestion').addStringOption(o => o.setName('texte').setDescription('Ta suggestion').setRequired(true)),
  new SlashCommandBuilder().setName('annonce').setDescription('Publie une annonce').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('titre').setDescription('Titre').setRequired(true)).addStringOption(o => o.setName('message').setDescription('Message').setRequired(true)).addChannelOption(o => o.setName('salon').setDescription('Salon').setRequired(false)),
  new SlashCommandBuilder().setName('sondage').setDescription('Lance un sondage')
    .addStringOption(o => o.setName('question').setDescription('Question').setRequired(true)).addStringOption(o => o.setName('option1').setDescription('Option 1').setRequired(true)).addStringOption(o => o.setName('option2').setDescription('Option 2').setRequired(true)).addStringOption(o => o.setName('option3').setDescription('Option 3').setRequired(false)).addStringOption(o => o.setName('option4').setDescription('Option 4').setRequired(false)),

  // ----- Fun -----
  new SlashCommandBuilder().setName('8ball').setDescription('Pose une question à la boule magique'),
  new SlashCommandBuilder().setName('des').setDescription('Lance un dé').addIntegerOption(o => o.setName('faces').setDescription('Nombre de faces (défaut 6)').setRequired(false)),
  new SlashCommandBuilder().setName('pileouface').setDescription('Pile ou face'),
].map(cmd => cmd.toJSON());

const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);

(async () => {
  try {
    console.log('Déploiement des commandes slash...');
    await rest.put(Routes.applicationGuildCommands(process.env.CLIENT_ID, config.guildId), { body: commands });
    console.log(`Commandes slash déployées avec succès (${commands.length}).`);
  } catch (error) {
    console.error(error);
  }
})();
