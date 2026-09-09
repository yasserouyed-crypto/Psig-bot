const {
  Client, GatewayIntentBits, REST, Routes,
  SlashCommandBuilder, EmbedBuilder,
  ActionRowBuilder, ButtonBuilder, ButtonStyle,
  PermissionFlagsBits
} = require('discord.js');
const fs = require('fs');
require('dotenv').config();
const http = require('http');
http.createServer((req, res) => res.end('OK')).listen(10000);
const CONFIG_PATH = './config.json';

function getConfig() {
  if (!fs.existsSync(CONFIG_PATH)) return {};
  return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
}

function saveConfig(data) {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(data, null, 2));
}

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMembers]
});

const commands = [
  new SlashCommandBuilder()
    .setName('sos')
    .setDescription('Envoyer une demande d\'aide au staff')
    .addStringOption(opt => opt.setName('raison').setDescription('Raison de votre demande').setRequired(true)),

  new SlashCommandBuilder()
    .setName('preuvestaff')
    .setDescription('Donner un rôle à un membre')
    .addUserOption(opt => opt.setName('membre').setDescription('Membre à qui donner le rôle').setRequired(true))
    .addRoleOption(opt => opt.setName('role').setDescription('Rôle à donner').setRequired(true)),

  new SlashCommandBuilder()
    .setName('config-sos')
    .setDescription('Configurer le système SOS')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addSubcommand(sub => sub.setName('salon').setDescription('Définir le salon SOS').addChannelOption(opt => opt.setName('salon').setDescription('Salon').setRequired(true)))
    .addSubcommand(sub => sub.setName('role_staff').setDescription('Définir le rôle staff SOS').addRoleOption(opt => opt.setName('role').setDescription('Rôle').setRequired(true)))
    .addSubcommand(sub => sub.setName('voir').setDescription('Voir la config SOS')),

  new SlashCommandBuilder()
    .setName('config-staff')
    .setDescription('Configurer le système preuvestaff')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addSubcommand(sub => sub.setName('role').setDescription('Définir le rôle donnable via /preuvestaff').addRoleOption(opt => opt.setName('role').setDescription('Rôle').setRequired(true)))
    .addSubcommand(sub => sub.setName('voir').setDescription('Voir la config staff')),

  new SlashCommandBuilder()
    .setName('help')
    .setDescription('Afficher toutes les commandes')

].map(c => c.toJSON());

client.once('ready', async () => {
  console.log(`✅ Nexis Bot connecté : ${client.user.tag}`);
  const rest = new REST({ version: '10' }).setToken(process.env.TOKEN);
  try {
    await rest.put(Routes.applicationCommands(client.user.id), { body: commands });
    console.log('✅ Commandes enregistrées');
  } catch (err) {
    console.error('❌ Erreur:', err);
  }
});

client.on('interactionCreate', async interaction => {
  if (interaction.isChatInputCommand()) {

    // /help
    if (interaction.commandName === 'help') {
      return interaction.reply({
        embeds: [new EmbedBuilder()
          .setTitle('📖 Nexis Bot — Aide')
          .setColor(0x5865F2)
          .addFields(
            { name: '🆘 `/sos [raison]`', value: 'Envoyer une demande SOS au staff' },
            { name: '👮 `/preuvestaff [@membre] [@role]`', value: 'Donner un rôle à un membre' },
            { name: '⚙️ `/config-sos salon`', value: 'Définir le salon de réception des SOS' },
            { name: '⚙️ `/config-sos role_staff`', value: 'Définir le rôle staff pour les SOS' },
            { name: '⚙️ `/config-sos voir`', value: 'Voir la configuration SOS' },
            { name: '⚙️ `/config-staff role`', value: 'Définir le rôle donnable via /preuvestaff' },
            { name: '⚙️ `/config-staff voir`', value: 'Voir la configuration staff' },
            { name: '📖 `/help`', value: 'Afficher ce message' }
          )
          .setFooter({ text: 'Nexis Bot • Développé par Yasser' })
          .setTimestamp()
        ],
        ephemeral: true
      });
    }

    // /sos
    if (interaction.commandName === 'sos') {
      const config = getConfig();
      if (!config.sos_channel) {
        return interaction.reply({ content: '❌ Le salon SOS n\'est pas configuré.', ephemeral: true });
      }
      const sosChannel = await client.channels.fetch(config.sos_channel).catch(() => null);
      if (!sosChannel) {
        return interaction.reply({ content: '❌ Salon SOS introuvable.', ephemeral: true });
      }
      const raison = interaction.options.getString('raison');
      const user = interaction.user;
      const embed = new EmbedBuilder()
        .setTitle('🆘 Nouvelle demande SOS')
        .setColor(0xFF0000)
        .addFields(
          { name: '👤 Utilisateur', value: `${user.tag} (${user.id})`, inline: true },
          { name: '🏠 Serveur', value: interaction.guild ? interaction.guild.name : 'Inconnu', inline: true },
          { name: '📋 Raison', value: raison },
          { name: '📊 Statut', value: '⏳ En attente...' }
        )
        .setThumbnail(user.displayAvatarURL())
        .setTimestamp()
        .setFooter({ text: 'Nexis Bot — Système SOS' });

      const row = new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId(`sos_accept_${user.id}`).setLabel('✅ Accepter').setStyle(ButtonStyle.Success),
        new ButtonBuilder().setCustomId(`sos_refuse_${user.id}`).setLabel('❌ Refuser').setStyle(ButtonStyle.Danger)
      );

      await sosChannel.send({
        content: config.sos_staff_role ? `<@&${config.sos_staff_role}> — Nouvelle demande SOS !` : '🆘 Nouvelle demande SOS !',
        embeds: [embed],
        components: [row]
      });

      return interaction.reply({ content: '✅ Ta demande SOS a été envoyée !', ephemeral: true });
    }

    // /preuvestaff
    if (interaction.commandName === 'preuvestaff') {
      const config = getConfig();
      const staffRoleId = config.staff_role;

      if (staffRoleId) {
        const member = await interaction.guild?.members.fetch(interaction.user.id).catch(() => null);
        if (!member || !member.roles.cache.has(staffRoleId)) {
          return interaction.reply({ content: '❌ Tu n\'as pas le rôle staff pour utiliser cette commande.', ephemeral: true });
        }
      }

      const membre = interaction.options.getMember('membre');
      const role = interaction.options.getRole('role');

      await membre.roles.add(role).catch(() => null);

      return interaction.reply({
        embeds: [new EmbedBuilder()
          .setColor(0x00FF99)
          .setTitle('✅ Rôle attribué')
          .addFields(
            { name: '👤 Membre', value: `${membre.user.tag}`, inline: true },
            { name: '🎭 Rôle', value: `${role}`, inline: true },
            { name: '👮 Staff', value: `${interaction.user.tag}`, inline: true }
          )
          .setTimestamp()
          .setFooter({ text: 'Nexis Bot — PreuveStaff' })
        ]
      });
    }

    // /config-sos
    if (interaction.commandName === 'config-sos') {
      const config = getConfig();
      const sub = interaction.options.getSubcommand();

      if (sub === 'salon') {
        const salon = interaction.options.getChannel('salon');
        config.sos_channel = salon.id;
        saveConfig(config);
        return interaction.reply({ embeds: [new EmbedBuilder().setColor(0x00FF99).setTitle('✅ Salon SOS défini').setDescription(`${salon}`)], ephemeral: true });
      }

      if (sub === 'role_staff') {
        const role = interaction.options.getRole('role');
        config.sos_staff_role = role.id;
        saveConfig(config);
        return interaction.reply({ embeds: [new EmbedBuilder().setColor(0x00FF99).setTitle('✅ Rôle staff SOS défini').setDescription(`${role}`)], ephemeral: true });
      }

      if (sub === 'voir') {
        return interaction.reply({
          embeds: [new EmbedBuilder()
            .setColor(0x5865F2)
            .setTitle('⚙️ Config SOS')
            .addFields(
              { name: '📢 Salon SOS', value: config.sos_channel ? `<#${config.sos_channel}>` : '❌ Non défini', inline: true },
              { name: '👮 Rôle Staff', value: config.sos_staff_role ? `<@&${config.sos_staff_role}>` : '❌ Non défini', inline: true }
            )
          ],
          ephemeral: true
        });
      }
    }

    // /config-staff
    if (interaction.commandName === 'config-staff') {
      const config = getConfig();
      const sub = interaction.options.getSubcommand();

      if (sub === 'role') {
        const role = interaction.options.getRole('role');
        config.staff_role = role.id;
        saveConfig(config);
        return interaction.reply({ embeds: [new EmbedBuilder().setColor(0x00FF99).setTitle('✅ Rôle staff défini').setDescription(`${role}`)], ephemeral: true });
      }

      if (sub === 'voir') {
        return interaction.reply({
          embeds: [new EmbedBuilder()
            .setColor(0x5865F2)
            .setTitle('⚙️ Config Staff')
            .addFields(
              { name: '🎭 Rôle Staff', value: config.staff_role ? `<@&${config.staff_role}>` : '❌ Non défini', inline: true }
            )
          ],
          ephemeral: true
        });
      }
    }
  }

  // Boutons SOS
  if (interaction.isButton()) {
    if (!interaction.customId.startsWith('sos_')) return;

    const config = getConfig();
    if (config.sos_staff_role) {
      const member = await interaction.guild?.members.fetch(interaction.user.id).catch(() => null);
      if (!member || !member.roles.cache.has(config.sos_staff_role)) {
        return interaction.reply({ content: '❌ Tu n\'as pas le rôle staff.', ephemeral: true });
      }
    }

    const isAccept = interaction.customId.startsWith('sos_accept_');
    const targetUserId = interaction.customId.replace('sos_accept_', '').replace('sos_refuse_', '');
    const staff = interaction.user;

    const oldEmbed = interaction.message.embeds[0];
    const newEmbed = EmbedBuilder.from(oldEmbed)
      .setColor(isAccept ? 0x00FF99 : 0xFF4444)
      .spliceFields(3, 1, { name: '📊 Statut', value: isAccept ? `✅ Accepté par ${staff.tag}` : `❌ Refusé par ${staff.tag}` })
      .addFields({ name: '👮 Staff', value: `${staff.tag} (${staff.id})` });

    const disabledRow = new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId('done1').setLabel('✅ Accepté').setStyle(ButtonStyle.Success).setDisabled(true),
      new ButtonBuilder().setCustomId('done2').setLabel('❌ Refusé').setStyle(ButtonStyle.Danger).setDisabled(true)
    );

    await interaction.update({ embeds: [newEmbed], components: [disabledRow] });

    const targetUser = await client.users.fetch(targetUserId).catch(() => null);
    if (targetUser) {
      await targetUser.send({
        embeds: [new EmbedBuilder()
          .setColor(isAccept ? 0x00FF99 : 0xFF4444)
          .setTitle(isAccept ? '✅ SOS Accepté' : '❌ SOS Refusé')
          .setDescription(`Ton SOS a été **${isAccept ? 'accepté' : 'refusé'}** par **${staff.tag}**`)
          .setTimestamp()
        ]
      }).catch(() => null);
    }
  }
});

client.login(process.env.TOKEN);
