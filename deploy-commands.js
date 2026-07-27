require('dotenv').config();
const { REST, Routes, SlashCommandBuilder } = require('discord.js');
const config = require('./config.json');

const commands = [
  new SlashCommandBuilder()
    .setName('panel-ticket')
    .setDescription("Publie le panneau permettant d'ouvrir un ticket de demande de grade (PSIG)")
    .setDefaultMemberPermissions(0), // visible uniquement par les membres avec la permission Administrateur par défaut
  new SlashCommandBuilder()
    .setName('close')
    .setDescription('Ferme le ticket en cours (à utiliser dans un salon de ticket)'),
].map(cmd => cmd.toJSON());

const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);

(async () => {
  try {
    console.log('Déploiement des commandes slash...');
    await rest.put(
      Routes.applicationGuildCommands(process.env.CLIENT_ID, config.guildId),
      { body: commands }
    );
    console.log('Commandes slash déployées avec succès.');
  } catch (error) {
    console.error(error);
  }
})();
