require('dotenv').config();
const fs = require('fs');
const path = require('path');
const {
  Client,
  GatewayIntentBits,
  Partials,
  EmbedBuilder,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  StringSelectMenuBuilder,
  ModalBuilder,
  TextInputBuilder,
  TextInputStyle,
  PermissionsBitField,
  ChannelType,
  AttachmentBuilder,
} = require('discord.js');
const config = require('./config.json');

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
  partials: [Partials.Channel],
});

const COLOR = 0x0b1d3a; // bleu nuit, sobre style forces de l'ordre
const PANEL_SELECT_ID = 'psig_select_grade';
const MODAL_ID = 'psig_modal_motivation';
const CLAIM_BUTTON_ID = 'psig_claim';
const CLOSE_BUTTON_ID = 'psig_close';

// ---------- Utilitaires ----------

function slugify(text) {
  return text
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
    .slice(0, 20);
}

async function findExistingTicket(guild, userId) {
  const category = guild.channels.cache.get(config.ticketCategoryId);
  if (!category) return null;
  return guild.channels.cache.find(
    ch => ch.parentId === config.ticketCategoryId && ch.topic === `ticket-owner:${userId}`
  );
}

// ---------- Prêt ----------

client.once('ready', () => {
  console.log(`Connecté en tant que ${client.user.tag}`);
});

// ---------- Interactions ----------

client.on('interactionCreate', async (interaction) => {
  try {
    // /panel-ticket : publie le panneau
    if (interaction.isChatInputCommand() && interaction.commandName === 'panel-ticket') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) {
        return interaction.reply({ content: "Tu n'as pas la permission d'utiliser cette commande.", ephemeral: true });
      }

      const embed = new EmbedBuilder()
        .setColor(COLOR)
        .setTitle('PSIG — Demande de grade')
        .setDescription(
          'Tu souhaites demander un changement de grade au sein du PSIG ?\n\n' +
          'Sélectionne le grade que tu demandes dans le menu ci-dessous. ' +
          'Un salon privé sera créé pour que tu puisses échanger avec le commandement.'
        )
        .setFooter({ text: 'PSIG — Système de tickets' });

      const select = new StringSelectMenuBuilder()
        .setCustomId(PANEL_SELECT_ID)
        .setPlaceholder('Choisis le grade demandé')
        .addOptions(
          config.grades.map(grade => ({ label: grade, value: grade }))
        );

      const row = new ActionRowBuilder().addComponents(select);

      await interaction.channel.send({ embeds: [embed], components: [row] });
      return interaction.reply({ content: 'Panneau publié.', ephemeral: true });
    }

    // /close : ferme le ticket courant
    if (interaction.isChatInputCommand() && interaction.commandName === 'close') {
      if (!interaction.channel.topic?.startsWith('ticket-owner:')) {
        return interaction.reply({ content: "Cette commande ne fonctionne que dans un salon de ticket.", ephemeral: true });
      }
      return closeTicket(interaction);
    }

    // Sélection du grade -> ouvre le formulaire (modal)
    if (interaction.isStringSelectMenu() && interaction.customId === PANEL_SELECT_ID) {
      const existing = await findExistingTicket(interaction.guild, interaction.user.id);
      if (existing) {
        return interaction.reply({
          content: `Tu as déjà un ticket ouvert : <#${existing.id}>`,
          ephemeral: true,
        });
      }

      const grade = interaction.values[0];

      const modal = new ModalBuilder()
        .setCustomId(`${MODAL_ID}:${encodeURIComponent(grade)}`)
        .setTitle(`Demande — ${grade}`);

      const motivationInput = new TextInputBuilder()
        .setCustomId('motivation')
        .setLabel('Pourquoi mérites-tu ce grade ?')
        .setStyle(TextInputStyle.Paragraph)
        .setRequired(true)
        .setMaxLength(1000);

      const anciennete = new TextInputBuilder()
        .setCustomId('anciennete')
        .setLabel("Depuis quand es-tu au PSIG ?")
        .setStyle(TextInputStyle.Short)
        .setRequired(true)
        .setMaxLength(100);

      modal.addComponents(
        new ActionRowBuilder().addComponents(motivationInput),
        new ActionRowBuilder().addComponents(anciennete)
      );

      return interaction.showModal(modal);
    }

    // Soumission du formulaire -> création du ticket
    if (interaction.isModalSubmit() && interaction.customId.startsWith(MODAL_ID)) {
      await interaction.deferReply({ ephemeral: true });

      const grade = decodeURIComponent(interaction.customId.split(':')[1]);
      const motivation = interaction.fields.getTextInputValue('motivation');
      const anciennete = interaction.fields.getTextInputValue('anciennete');

      const guild = interaction.guild;
      const staffRole = guild.roles.cache.get(config.staffRoleId);

      const channel = await guild.channels.create({
        name: `grade-${slugify(interaction.user.username)}`,
        type: ChannelType.GuildText,
        parent: config.ticketCategoryId || null,
        topic: `ticket-owner:${interaction.user.id}`,
        permissionOverwrites: [
          {
            id: guild.roles.everyone.id,
            deny: [PermissionsBitField.Flags.ViewChannel],
          },
          {
            id: interaction.user.id,
            allow: [
              PermissionsBitField.Flags.ViewChannel,
              PermissionsBitField.Flags.SendMessages,
              PermissionsBitField.Flags.ReadMessageHistory,
            ],
          },
          ...(staffRole
            ? [{
                id: staffRole.id,
                allow: [
                  PermissionsBitField.Flags.ViewChannel,
                  PermissionsBitField.Flags.SendMessages,
                  PermissionsBitField.Flags.ReadMessageHistory,
                ],
              }]
            : []),
        ],
      });

      const embed = new EmbedBuilder()
        .setColor(COLOR)
        .setTitle(`Demande de grade — ${grade}`)
        .addFields(
          { name: 'Demandeur', value: `<@${interaction.user.id}>`, inline: true },
          { name: 'Grade demandé', value: grade, inline: true },
          { name: 'Ancienneté', value: anciennete, inline: false },
          { name: 'Motivation', value: motivation, inline: false },
        )
        .setTimestamp();

      const buttons = new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId(CLAIM_BUTTON_ID).setLabel('Réclamer').setStyle(ButtonStyle.Primary).setEmoji('🖐️'),
        new ButtonBuilder().setCustomId(CLOSE_BUTTON_ID).setLabel('Fermer le ticket').setStyle(ButtonStyle.Danger).setEmoji('🔒'),
      );

      await channel.send({
        content: `${staffRole ? `<@&${staffRole.id}> ` : ''}<@${interaction.user.id}>`,
        embeds: [embed],
        components: [buttons],
      });

      return interaction.editReply({ content: `Ton ticket a été créé : <#${channel.id}>` });
    }

    // Réclamer le ticket
    if (interaction.isButton() && interaction.customId === CLAIM_BUTTON_ID) {
      const staffRole = interaction.guild.roles.cache.get(config.staffRoleId);
      if (staffRole && !interaction.member.roles.cache.has(staffRole.id)) {
        return interaction.reply({ content: "Seul le staff peut réclamer un ticket.", ephemeral: true });
      }
      const embed = new EmbedBuilder()
        .setColor(COLOR)
        .setDescription(`🖐️ Ticket réclamé par <@${interaction.user.id}>.`);
      return interaction.reply({ embeds: [embed] });
    }

    // Fermer le ticket
    if (interaction.isButton() && interaction.customId === CLOSE_BUTTON_ID) {
      return closeTicket(interaction);
    }
  } catch (err) {
    console.error(err);
    if (interaction.isRepliable() && !interaction.replied && !interaction.deferred) {
      interaction.reply({ content: "Une erreur est survenue.", ephemeral: true }).catch(() => {});
    }
  }
});

// ---------- Fermeture + transcript ----------

async function closeTicket(interaction) {
  const channel = interaction.channel;
  const staffRole = interaction.guild.roles.cache.get(config.staffRoleId);
  if (staffRole && interaction.member && !interaction.member.roles.cache.has(staffRole.id)) {
    return interaction.reply({ content: "Seul le staff peut fermer un ticket.", ephemeral: true });
  }

  await interaction.reply({ content: 'Fermeture du ticket dans 5 secondes... Génération du transcript.' });

  // Génère un transcript texte simple
  const messages = await channel.messages.fetch({ limit: 100 });
  const sorted = [...messages.values()].reverse();
  const lines = sorted.map(m => {
    const time = m.createdAt.toISOString();
    const author = m.author?.tag ?? 'Inconnu';
    const content = m.content || '[embed/composant]';
    return `[${time}] ${author}: ${content}`;
  });
  const transcriptPath = path.join(__dirname, `transcript-${channel.id}.txt`);
  fs.writeFileSync(transcriptPath, lines.join('\n') || 'Aucun message.');

  const logChannel = interaction.guild.channels.cache.get(config.logChannelId);
  if (logChannel) {
    const attachment = new AttachmentBuilder(transcriptPath, { name: `transcript-${channel.name}.txt` });
    const logEmbed = new EmbedBuilder()
      .setColor(COLOR)
      .setTitle('Ticket fermé')
      .addFields(
        { name: 'Salon', value: `#${channel.name}`, inline: true },
        { name: 'Fermé par', value: `<@${interaction.user.id}>`, inline: true },
      )
      .setTimestamp();
    await logChannel.send({ embeds: [logEmbed], files: [attachment] }).catch(() => {});
  }

  fs.unlink(transcriptPath, () => {});

  setTimeout(() => {
    channel.delete().catch(() => {});
  }, 5000);
}

client.login(process.env.DISCORD_TOKEN);
