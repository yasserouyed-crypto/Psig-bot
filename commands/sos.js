const {
  SlashCommandBuilder,
  EmbedBuilder,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
} = require('discord.js');
const fs = require('fs');

const CONFIG_PATH = './config.json';

function getConfig() {
  if (!fs.existsSync(CONFIG_PATH)) return {};
  return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
}

module.exports = {
  data: new SlashCommandBuilder()
    .setName('sos')
    .setDescription('Envoyer une demande d\'aide au staff')
    .addStringOption(opt =>
      opt.setName('raison')
        .setDescription('Raison de votre demande SOS')
        .setRequired(true)
    ),

  async execute(interaction, client) {
    const config = getConfig();
    const sosChannelId = config.sos_channel;
    const staffRoleId = config.staff_role;

    if (!sosChannelId) {
      return interaction.reply({
        content: '❌ Le salon SOS n\'est pas configuré.',
        ephemeral: true
      });
    }

    const sosChannel = await client.channels.fetch(sosChannelId).catch(() => null);
    if (!sosChannel) {
      return interaction.reply({
        content: '❌ Le salon SOS est introuvable.',
        ephemeral: true
      });
    }

    const raison = interaction.options.getString('raison');
    const user = interaction.user;
    const guild = interaction.guild;

    const embed = new EmbedBuilder()
      .setTitle('🆘 Nouvelle demande SOS')
      .setColor(0xFF0000)
      .addFields(
        { name: '👤 Utilisateur', value: `${user.tag} (${user.id})`, inline: true },
        { name: '🏠 Serveur', value: guild ? guild.name : 'Inconnu', inline: true },
        { name: '📋 Raison', value: raison },
        { name: '📊 Statut', value: '⏳ En attente...' }
      )
      .setThumbnail(user.displayAvatarURL())
      .setTimestamp()
      .setFooter({ text: 'Nexis Bot — Système SOS' });

    const row = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(`sos_accept_${user.id}`)
        .setLabel('✅ Accepter')
        .setStyle(ButtonStyle.Success),
      new ButtonBuilder()
        .setCustomId(`sos_refuse_${user.id}`)
        .setLabel('❌ Refuser')
        .setStyle(ButtonStyle.Danger)
    );

    const pingText = staffRoleId ? `<@&${staffRoleId}>` : '';
    await sosChannel.send({
      content: pingText ? `${pingText} — Nouvelle demande SOS !` : '🆘 Nouvelle demande SOS !',
      embeds: [embed],
      components: [row]
    });

    await interaction.reply({
      content: '✅ Ta demande SOS a bien été envoyée au staff !',
      ephemeral: true
    });
  }
};
