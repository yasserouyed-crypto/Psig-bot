const {
  SlashCommandBuilder,
  EmbedBuilder,
  PermissionFlagsBits
} = require('discord.js');
const fs = require('fs');

const CONFIG_PATH = './config.json';

function getConfig() {
  if (!fs.existsSync(CONFIG_PATH)) return {};
  return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
}

function saveConfig(data) {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(data, null, 2));
}

module.exports = {
  data: new SlashCommandBuilder()
    .setName('config')
    .setDescription('Configurer le bot Nexis')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addSubcommand(sub =>
      sub.setName('sos_salon')
        .setDescription('Définir le salon de réception des SOS')
        .addChannelOption(opt =>
          opt.setName('salon')
            .setDescription('Salon où les SOS seront envoyés')
            .setRequired(true)
        )
    )
    .addSubcommand(sub =>
      sub.setName('staff_role')
        .setDescription('Définir le rôle staff autorisé à traiter les SOS')
        .addRoleOption(opt =>
          opt.setName('role')
            .setDescription('Rôle staff')
            .setRequired(true)
        )
    )
    .addSubcommand(sub =>
      sub.setName('voir')
        .setDescription('Voir la configuration actuelle')
    ),

  async execute(interaction, client) {
    const config = getConfig();
    const sub = interaction.options.getSubcommand();

    if (sub === 'sos_salon') {
      const salon = interaction.options.getChannel('salon');
      config.sos_channel = salon.id;
      saveConfig(config);
      return interaction.reply({
        embeds: [
          new EmbedBuilder()
            .setColor(0x00FF99)
            .setTitle('✅ Configuration mise à jour')
            .setDescription(`Salon SOS défini sur ${salon}`)
        ],
        ephemeral: true
      });
    }

    if (sub === 'staff_role') {
      const role = interaction.options.getRole('role');
      config.staff_role = role.id;
      saveConfig(config);
      return interaction.reply({
        embeds: [
          new EmbedBuilder()
            .setColor(0x00FF99)
            .setTitle('✅ Configuration mise à jour')
            .setDescription(`Rôle staff défini sur ${role}`)
        ],
        ephemeral: true
      });
    }

    if (sub === 'voir') {
      const sosChannel = config.sos_channel ? `<#${config.sos_channel}>` : '❌ Non défini';
      const staffRole = config.staff_role ? `<@&${config.staff_role}>` : '❌ Non défini';
      return interaction.reply({
        embeds: [
          new EmbedBuilder()
            .setColor(0x5865F2)
            .setTitle('⚙️ Configuration actuelle')
            .addFields(
              { name: '📢 Salon SOS', value: sosChannel, inline: true },
              { name: '👮 Rôle Staff', value: staffRole, inline: true }
            )
        ],
        ephemeral: true
      });
    }
  }
};
