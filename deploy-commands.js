require('dotenv').config();
const { REST, Routes, SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const config = require('./config.json');

const commands = [
  // ----- Tickets -----
  new SlashCommandBuilder()
    .setName('panel-ticket')
    .setDescription("Publie le panneau permettant d'ouvrir un ticket de demande de grade (PSIG)")
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild),

  new SlashCommandBuilder()
    .setName('close')
    .setDescription('Ferme le ticket en cours (à utiliser dans un salon de ticket)'),

  // ----- Modération -----
  new SlashCommandBuilder()
    .setName('kick')
    .setDescription('Expulse un membre du serveur')
    .setDefaultMemberPermissions(PermissionFlagsBits.KickMembers)
    .addUserOption(o => o.setName('membre').setDescription('Le membre à expulser').setRequired(true))
    .addStringOption(o => o.setName('raison').setDescription("Raison de l'expulsion").setRequired(false)),

  new SlashCommandBuilder()
    .setName('ban')
    .setDescription('Bannit un membre du serveur')
    .setDefaultMemberPermissions(PermissionFlagsBits.BanMembers)
    .addUserOption(o => o.setName('membre').setDescription('Le membre à bannir').setRequired(true))
    .addStringOption(o => o.setName('raison').setDescription('Raison du bannissement').setRequired(false)),

  new SlashCommandBuilder()
    .setName('mute')
    .setDescription('Rend un membre muet temporairement (timeout)')
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName('membre').setDescription('Le membre à rendre muet').setRequired(true))
    .addIntegerOption(o => o.setName('minutes').setDescription('Durée en minutes').setRequired(true))
    .addStringOption(o => o.setName('raison').setDescription('Raison').setRequired(false)),

  new SlashCommandBuilder()
    .setName('unmute')
    .setDescription("Retire le mode muet (timeout) d'un membre")
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName('membre').setDescription('Le membre à démuter').setRequired(true)),

  new SlashCommandBuilder()
    .setName('warn')
    .setDescription('Envoie un avertissement à un membre (journalisé)')
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers)
    .addUserOption(o => o.setName('membre').setDescription('Le membre à avertir').setRequired(true))
    .addStringOption(o => o.setName('raison').setDescription("Raison de l'avertissement").setRequired(true)),

  // ----- Bienvenue -----
  new SlashCommandBuilder()
    .setName('set-welcome')
    .setDescription('Définit le salon utilisé pour les messages de bienvenue')
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild)
    .addChannelOption(o => o.setName('salon').setDescription('Le salon de bienvenue').setRequired(true)),

  // ----- Niveaux -----
  new SlashCommandBuilder()
    .setName('rank')
    .setDescription("Affiche ton niveau et ton XP (ou celui d'un autre membre)")
    .addUserOption(o => o.setName('membre').setDescription('Le membre à consulter').setRequired(false)),

  new SlashCommandBuilder()
    .setName('leaderboard')
    .setDescription('Affiche le classement des membres les plus actifs'),
].map(cmd => cmd.toJSON());

const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);

(async () => {
  try {
    console.log('Déploiement des commandes slash...');
    await rest.put(
      Routes.applicationGuildCommands(process.env.CLIENT_ID, config.guildId),
      { body: commands }
    );
    console.log(`Commandes slash déployées avec succès (${commands.length}).`);
  } catch (error) {
    console.error(error);
  }
})();
