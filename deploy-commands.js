require('dotenv').config();
const { REST, Routes, SlashCommandBuilder, PermissionFlagsBits, ChannelType } = require('discord.js');

const commands = [
  // ----- Tickets -----
  new SlashCommandBuilder().setName('panel-ticket').setDescription('Publie le panneau de tickets de support').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild),
  new SlashCommandBuilder().setName('ticket-categorie-ajouter').setDescription('Ajoute une catégorie de ticket personnalisée').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('nom').setDescription('Nom de la catégorie').setRequired(true))
    .addStringOption(o => o.setName('description').setDescription('Description affichée').setRequired(true))
    .addStringOption(o => o.setName('emoji').setDescription('Emoji (ex: 🎫)').setRequired(false)),
  new SlashCommandBuilder().setName('ticket-categorie-supprimer').setDescription('Supprime une catégorie de ticket').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('nom').setDescription('Nom exact de la catégorie').setRequired(true)),
  new SlashCommandBuilder().setName('ticket-categorie-liste').setDescription('Liste les catégories de tickets actuelles'),
  new SlashCommandBuilder().setName('panel').setDescription("Ouvre le centre de contrôle de l'administration").setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild),
  new SlashCommandBuilder().setName('config').setDescription('Menu de configuration du bot (tickets, bienvenue, niveaux, logs...)').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild),
  new SlashCommandBuilder().setName('backup').setDescription('Sauvegarde et restauration du serveur').setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addSubcommand(s => s.setName('create').setDescription('Crée une nouvelle sauvegarde (rôles, catégories, salons)'))
    .addSubcommand(s => s.setName('list').setDescription('Liste les sauvegardes disponibles'))
    .addSubcommand(s => s.setName('restore').setDescription('Restaure une sauvegarde (avec confirmation)').addStringOption(o => o.setName('id').setDescription('ID de la sauvegarde (vide = la plus récente)').setRequired(false))),

  new SlashCommandBuilder().setName('antiraid').setDescription('Système anti-raid').setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addSubcommand(s => s.setName('setup').setDescription("Configure le salon d'alertes").addChannelOption(o => o.setName('salon_alertes').setDescription('Salon des alertes').setRequired(true)))
    .addSubcommand(s => s.setName('on').setDescription("Active l'anti-raid"))
    .addSubcommand(s => s.setName('off').setDescription("Désactive l'anti-raid"))
    .addSubcommand(s => s.setName('status').setDescription('Affiche le statut actuel'))
    .addSubcommand(s => s.setName('config').setDescription('Affiche la configuration des seuils'))
    .addSubcommand(s => s.setName('lockdown').setDescription('Verrouille manuellement le serveur'))
    .addSubcommand(s => s.setName('unlock').setDescription('Lève le verrouillage manuel'))
    .addSubcommand(s => s.setName('test').setDescription('Teste le calcul de score sans impact réel')),

  new SlashCommandBuilder().setName('antinuke').setDescription('Système anti-nuke').setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addSubcommand(s => s.setName('on').setDescription("Active l'anti-nuke"))
    .addSubcommand(s => s.setName('off').setDescription("Désactive l'anti-nuke"))
    .addSubcommand(s => s.setName('status').setDescription('Affiche le statut actuel'))
    .addSubcommand(s => s.setName('protect-role').setDescription('Protège un rôle').addRoleOption(o => o.setName('role').setDescription('Rôle à protéger').setRequired(true)))
    .addSubcommand(s => s.setName('unprotect-role').setDescription('Retire la protection d\'un rôle').addRoleOption(o => o.setName('role').setDescription('Rôle').setRequired(true)))
    .addSubcommand(s => s.setName('protect-user').setDescription('Protège un utilisateur (jamais sanctionné)').addUserOption(o => o.setName('membre').setDescription('Membre à protéger').setRequired(true)))
    .addSubcommand(s => s.setName('unprotect-user').setDescription('Retire la protection d\'un utilisateur').addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true))),

  new SlashCommandBuilder().setName('security').setDescription('Sécurité du serveur')
    .addSubcommand(s => s.setName('status').setDescription('Tableau de bord sécurité complet')),
  new SlashCommandBuilder().setName('close').setDescription('Ferme le ticket en cours'),
  new SlashCommandBuilder().setName('recrutement').setDescription('Candidature de recrutement'),
  new SlashCommandBuilder().setName('config-questions').setDescription('Personnalise les questions d\'un formulaire').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('formulaire').setDescription('Quel formulaire').setRequired(true).addChoices(
      { name: 'Recrutement', value: 'recrutement' }, { name: 'Staff', value: 'staff' }, { name: 'Signalement', value: 'signalement' }, { name: 'Gang', value: 'gang' },
    ))
    .addStringOption(o => o.setName('question1').setDescription('Question 1').setRequired(true))
    .addStringOption(o => o.setName('question2').setDescription('Question 2').setRequired(false))
    .addStringOption(o => o.setName('question3').setDescription('Question 3').setRequired(false))
    .addStringOption(o => o.setName('question4').setDescription('Question 4').setRequired(false))
    .addStringOption(o => o.setName('question5').setDescription('Question 5').setRequired(false)),
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
  new SlashCommandBuilder().setName('set-welcome').setDescription('Définit ou désactive le salon de bienvenue').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addChannelOption(o => o.setName('salon').setDescription('Salon (laisse vide pour désactiver)').setRequired(false)),
  new SlashCommandBuilder().setName('set-message-bienvenue').setDescription('Personnalise le texte du message de bienvenue').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('texte').setDescription('Texte (variables : {membre} {pseudo} {serveur})').setRequired(true)),
  new SlashCommandBuilder().setName('set-salon-departs').setDescription('Définit ou désactive le salon des départs').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addChannelOption(o => o.setName('salon').setDescription('Salon (laisse vide pour désactiver)').setRequired(false)),
  new SlashCommandBuilder().setName('set-message-depart').setDescription('Personnalise le texte du message de départ').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('texte').setDescription('Texte (variables : {membre} {pseudo} {serveur})').setRequired(true)),
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
  new SlashCommandBuilder().setName('set-staffrole').setDescription('Définit le rôle staff qui gère les tickets et la modération').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addRoleOption(o => o.setName('role').setDescription('Rôle staff').setRequired(true)),
  new SlashCommandBuilder().setName('set-ticketcategorie').setDescription('Définit la catégorie où créer les salons de tickets').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addChannelOption(o => o.setName('categorie').setDescription('Catégorie').addChannelTypes(ChannelType.GuildCategory).setRequired(true)),
  new SlashCommandBuilder().setName('set-rolecivil').setDescription('Définit le rôle donné automatiquement aux nouveaux membres').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addRoleOption(o => o.setName('role').setDescription('Rôle civil').setRequired(true)),
  new SlashCommandBuilder().setName('panel-reglement').setDescription('Publie le règlement avec un bouton d\'acceptation').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild),
  new SlashCommandBuilder().setName('set-role-reglement').setDescription('Définit le rôle donné après acceptation du règlement').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addRoleOption(o => o.setName('role').setDescription('Rôle à donner').setRequired(true)),

  // ----- Informations -----
  new SlashCommandBuilder().setName('reglement').setDescription('Affiche le règlement'),
  new SlashCommandBuilder().setName('liens').setDescription('Affiche les liens utiles'),
  new SlashCommandBuilder().setName('urgence').setDescription("Affiche les numéros d'urgence"),
  new SlashCommandBuilder().setName('horaire').setDescription('Affiche les horaires'),
  new SlashCommandBuilder().setName('codes').setDescription('Affiche les codes radio'),
  new SlashCommandBuilder().setName('roles').setDescription('Liste les rôles du serveur'),
  new SlashCommandBuilder().setName('help').setDescription('Affiche toutes les commandes'),

  // ----- Niveaux -----
  new SlashCommandBuilder().setName('niveau').setDescription('Système de niveaux')
    .addSubcommand(s => s.setName('voir').setDescription('Affiche ton niveau et tes statistiques').addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(false)))
    .addSubcommand(s => s.setName('ajouter').setDescription("Ajoute de l'XP à un membre (staff)").addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)).addIntegerOption(o => o.setName('xp').setDescription("Quantité d'XP").setRequired(true)))
    .addSubcommand(s => s.setName('retirer').setDescription("Retire de l'XP à un membre (staff)").addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)).addIntegerOption(o => o.setName('xp').setDescription("Quantité d'XP").setRequired(true)))
    .addSubcommand(s => s.setName('set').setDescription('Définit le niveau exact d\'un membre (staff)').addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)).addIntegerOption(o => o.setName('niveau').setDescription('Niveau').setRequired(true)))
    .addSubcommand(s => s.setName('reset').setDescription('Réinitialise le niveau d\'un membre (staff)').addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true)))
    .addSubcommand(s => s.setName('config').setDescription('Définit le salon des messages de niveau (staff)').addChannelOption(o => o.setName('salon').setDescription('Salon (vide = salon courant)').setRequired(false)))
    .addSubcommand(s => s.setName('recompense').setDescription('Associe un rôle à un niveau (staff)').addIntegerOption(o => o.setName('niveau').setDescription('Niveau requis').setRequired(true)).addRoleOption(o => o.setName('role').setDescription('Rôle donné').setRequired(true))),
  new SlashCommandBuilder().setName('classement').setDescription('Classement des membres les plus actifs (paginé)'),

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

  // ----- Nouvelles commandes utiles -----
  new SlashCommandBuilder().setName('membercount').setDescription('Affiche le nombre de membres du serveur'),
  new SlashCommandBuilder().setName('choose').setDescription('Choisit aléatoirement parmi une liste')
    .addStringOption(o => o.setName('options').setDescription('Options séparées par des virgules').setRequired(true)),
  new SlashCommandBuilder().setName('say').setDescription('Fait envoyer un message au bot').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('message').setDescription('Le message à envoyer').setRequired(true))
    .addChannelOption(o => o.setName('salon').setDescription('Salon (par défaut : ce salon)').setRequired(false)),
  new SlashCommandBuilder().setName('nickname').setDescription("Change le pseudo d'un membre").setDefaultMemberPermissions(PermissionFlagsBits.ManageNicknames)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true))
    .addStringOption(o => o.setName('pseudo').setDescription('Nouveau pseudo (vide pour réinitialiser)').setRequired(false)),
  new SlashCommandBuilder().setName('purge-user').setDescription("Supprime les derniers messages d'un membre").setDefaultMemberPermissions(PermissionFlagsBits.ManageMessages)
    .addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(true))
    .addIntegerOption(o => o.setName('nombre').setDescription('Nombre max de messages (défaut 50)').setRequired(false)),
  new SlashCommandBuilder().setName('afk').setDescription('Indique que tu es absent')
    .addStringOption(o => o.setName('raison').setDescription("Raison de l'absence").setRequired(false)),
  new SlashCommandBuilder().setName('remind').setDescription('Programme un rappel privé')
    .addIntegerOption(o => o.setName('minutes').setDescription('Dans combien de minutes').setRequired(true))
    .addStringOption(o => o.setName('message').setDescription('Le rappel').setRequired(true)),
  new SlashCommandBuilder().setName('giveaway').setDescription('Lance un giveaway').setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addStringOption(o => o.setName('prix').setDescription('Ce qui est à gagner').setRequired(true))
    .addIntegerOption(o => o.setName('minutes').setDescription('Durée en minutes').setRequired(true))
    .addIntegerOption(o => o.setName('gagnants').setDescription('Nombre de gagnants (défaut 1)').setRequired(false)),

  // ----- Absences staff -----
  new SlashCommandBuilder().setName('absence').setDescription('Gestion des absences staff')
    .addSubcommand(s => s.setName('declarer').setDescription('Déclare une absence')
      .addStringOption(o => o.setName('date_debut').setDescription('Date de début (ex: 12/08/2026)').setRequired(true))
      .addStringOption(o => o.setName('date_fin').setDescription('Date de fin').setRequired(true))
      .addStringOption(o => o.setName('motif').setDescription('Motif').setRequired(true)))
    .addSubcommand(s => s.setName('accepter').setDescription('Accepte une demande (staff)').addStringOption(o => o.setName('id').setDescription('ID de la demande').setRequired(true)))
    .addSubcommand(s => s.setName('refuser').setDescription('Refuse une demande (staff)').addStringOption(o => o.setName('id').setDescription('ID de la demande').setRequired(true)).addStringOption(o => o.setName('raison').setDescription('Raison du refus').setRequired(false)))
    .addSubcommand(s => s.setName('liste').setDescription('Liste les demandes en attente'))
    .addSubcommand(s => s.setName('actuel').setDescription('Affiche les absences validées en cours')),

  // ----- Service staff -----
  new SlashCommandBuilder().setName('service').setDescription('Gestion du service staff')
    .addSubcommand(s => s.setName('prendre').setDescription('Prendre son service'))
    .addSubcommand(s => s.setName('terminer').setDescription('Terminer son service'))
    .addSubcommand(s => s.setName('liste').setDescription('Liste les staffs en service'))
    .addSubcommand(s => s.setName('stats').setDescription('Statistiques de service').addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(false))),

  // ----- Évaluations staff -----
  new SlashCommandBuilder().setName('evaluation').setDescription('Évaluations du staff')
    .addSubcommand(s => s.setName('creer').setDescription('Évalue un membre du staff')
      .addUserOption(o => o.setName('membre').setDescription('Membre à évaluer').setRequired(true))
      .addIntegerOption(o => o.setName('activite').setDescription('Activité (1-5)').setRequired(true).setMinValue(1).setMaxValue(5))
      .addIntegerOption(o => o.setName('serieux').setDescription('Sérieux (1-5)').setRequired(true).setMinValue(1).setMaxValue(5))
      .addIntegerOption(o => o.setName('rp').setDescription('RP (1-5)').setRequired(true).setMinValue(1).setMaxValue(5))
      .addIntegerOption(o => o.setName('moderation').setDescription('Modération (1-5)').setRequired(true).setMinValue(1).setMaxValue(5))
      .addIntegerOption(o => o.setName('communication').setDescription('Communication (1-5)').setRequired(true).setMinValue(1).setMaxValue(5))
      .addIntegerOption(o => o.setName('travail_equipe').setDescription("Travail d'équipe (1-5)").setRequired(true).setMinValue(1).setMaxValue(5))
      .addStringOption(o => o.setName('commentaire').setDescription('Commentaire').setRequired(false)))
    .addSubcommand(s => s.setName('voir').setDescription('Voit les évaluations d\'un membre').addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(false))),

  // ----- Roblox -----
  new SlashCommandBuilder().setName('roblox').setDescription('Lien de compte Roblox')
    .addSubcommand(s => s.setName('lier').setDescription('Lie ton compte Roblox à ton profil').addStringOption(o => o.setName('id').setDescription('Roblox User ID').setRequired(true)).addStringOption(o => o.setName('pseudo').setDescription('Pseudo Roblox').setRequired(true)))
    .addSubcommand(s => s.setName('voir').setDescription('Voir le compte Roblox lié').addUserOption(o => o.setName('membre').setDescription('Membre').setRequired(false))),

  // ----- Utilitaires supplémentaires -----
  new SlashCommandBuilder().setName('timestamp').setDescription('Génère un horodatage Discord')
    .addStringOption(o => o.setName('style').setDescription('Style (f, d, t, R...)').setRequired(false)),
  new SlashCommandBuilder().setName('channelinfo').setDescription('Infos sur le salon actuel'),
  new SlashCommandBuilder().setName('calc').setDescription('Calculatrice simple').addStringOption(o => o.setName('expression').setDescription('Ex: (2+3)*4').setRequired(true)),
].map(cmd => cmd.toJSON());

const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);
const OLD_GUILD_ID = '1529088552271609940'; // ancien serveur où les commandes étaient enregistrées individuellement (avant le passage en global)

(async () => {
  try {
    // Nettoie les anciennes commandes propres à un seul serveur (cause des doublons)
    await rest.put(Routes.applicationGuildCommands(process.env.CLIENT_ID, OLD_GUILD_ID), { body: [] }).catch(() => {});
    console.log('Anciennes commandes locales supprimées.');

    console.log('Déploiement des commandes slash (global)...');
    await rest.put(Routes.applicationCommands(process.env.CLIENT_ID), { body: commands });
    console.log(`Commandes slash déployées avec succès (${commands.length}).`);
  } catch (error) {
    console.error(error);
  }
})();
