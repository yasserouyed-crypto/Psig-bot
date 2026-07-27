require('dotenv').config();
const fs = require('fs');
const path = require('path');
const http = require('http');
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
    GatewayIntentBits.GuildModeration,
  ],
  partials: [Partials.Channel],
});

const COLOR = 0x0b1d3a; // bleu nuit, sobre style forces de l'ordre
const PANEL_SELECT_ID = 'psig_select_grade';
const MODAL_ID = 'psig_modal_motivation';
const CLAIM_BUTTON_ID = 'psig_claim';
const CLOSE_BUTTON_ID = 'psig_close';

// ---------- Stockage simple (fichiers JSON) ----------

const DATA_DIR = path.join(__dirname, 'data');
const SETTINGS_PATH = path.join(DATA_DIR, 'settings.json');
const LEVELS_PATH = path.join(DATA_DIR, 'levels.json');

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

function loadJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return fallback;
  }
}
function saveJson(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
}

let settings = loadJson(SETTINGS_PATH, { welcomeChannelId: null });
let levels = loadJson(LEVELS_PATH, {}); // { userId: { xp, level } }

function xpForNextLevel(level) {
  return 100 * (level + 1);
}

function addXp(userId, amount) {
  if (!levels[userId]) levels[userId] = { xp: 0, level: 0 };
  const user = levels[userId];
  user.xp += amount;
  let leveledUp = false;
  while (user.xp >= xpForNextLevel(user.level)) {
    user.xp -= xpForNextLevel(user.level);
    user.level += 1;
    leveledUp = true;
  }
  saveJson(LEVELS_PATH, levels);
  return { level: user.level, leveledUp };
}

// Anti-spam : garde en mémoire les derniers messages par utilisateur
const spamTracker = new Map(); // userId -> [timestamps]
const SPAM_WINDOW_MS = 5000;
const SPAM_LIMIT = 5;

// Cooldown XP (1 message compté toutes les 30s par utilisateur)
const xpCooldown = new Map(); // userId -> timestamp dernier gain

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

    // ----- Modération -----
    if (interaction.isChatInputCommand() && interaction.commandName === 'kick') {
      const target = interaction.options.getMember('membre');
      const reason = interaction.options.getString('raison') || 'Non spécifiée';
      if (!target) return interaction.reply({ content: 'Membre introuvable.', ephemeral: true });
      if (!target.kickable) return interaction.reply({ content: "Je ne peux pas expulser ce membre (rôle trop haut ou permissions insuffisantes).", ephemeral: true });
      await target.kick(reason);
      await interaction.reply({ content: `👢 <@${target.id}> a été expulsé. Raison : ${reason}` });
      await logModeration(interaction.guild, 'Expulsion', target.user, interaction.user, reason);
      return;
    }

    if (interaction.isChatInputCommand() && interaction.commandName === 'ban') {
      const target = interaction.options.getMember('membre');
      const reason = interaction.options.getString('raison') || 'Non spécifiée';
      if (!target) return interaction.reply({ content: 'Membre introuvable.', ephemeral: true });
      if (!target.bannable) return interaction.reply({ content: "Je ne peux pas bannir ce membre (rôle trop haut ou permissions insuffisantes).", ephemeral: true });
      await target.ban({ reason });
      await interaction.reply({ content: `🔨 <@${target.id}> a été banni. Raison : ${reason}` });
      await logModeration(interaction.guild, 'Bannissement', target.user, interaction.user, reason);
      return;
    }

    if (interaction.isChatInputCommand() && interaction.commandName === 'mute') {
      const target = interaction.options.getMember('membre');
      const minutes = interaction.options.getInteger('minutes');
      const reason = interaction.options.getString('raison') || 'Non spécifiée';
      if (!target) return interaction.reply({ content: 'Membre introuvable.', ephemeral: true });
      if (!target.moderatable) return interaction.reply({ content: "Je ne peux pas rendre ce membre muet (rôle trop haut ou permissions insuffisantes).", ephemeral: true });
      await target.timeout(minutes * 60 * 1000, reason);
      await interaction.reply({ content: `🔇 <@${target.id}> est muet pendant ${minutes} minute(s). Raison : ${reason}` });
      await logModeration(interaction.guild, 'Mute', target.user, interaction.user, `${reason} (${minutes} min)`);
      return;
    }

    if (interaction.isChatInputCommand() && interaction.commandName === 'unmute') {
      const target = interaction.options.getMember('membre');
      if (!target) return interaction.reply({ content: 'Membre introuvable.', ephemeral: true });
      await target.timeout(null);
      await interaction.reply({ content: `🔊 <@${target.id}> peut de nouveau parler.` });
      await logModeration(interaction.guild, 'Unmute', target.user, interaction.user, '—');
      return;
    }

    if (interaction.isChatInputCommand() && interaction.commandName === 'warn') {
      const target = interaction.options.getUser('membre');
      const reason = interaction.options.getString('raison');
      await interaction.reply({ content: `⚠️ <@${target.id}> a reçu un avertissement. Raison : ${reason}` });
      await logModeration(interaction.guild, 'Avertissement', target, interaction.user, reason);
      target.send(`⚠️ Tu as reçu un avertissement sur **${interaction.guild.name}**. Raison : ${reason}`).catch(() => {});
      return;
    }

    // ----- Bienvenue -----
    if (interaction.isChatInputCommand() && interaction.commandName === 'set-welcome') {
      const channel = interaction.options.getChannel('salon');
      settings.welcomeChannelId = channel.id;
      saveJson(SETTINGS_PATH, settings);
      return interaction.reply({ content: `✅ Le salon de bienvenue est maintenant <#${channel.id}>.`, ephemeral: true });
    }

    // ----- Niveaux -----
    if (interaction.isChatInputCommand() && interaction.commandName === 'rank') {
      const target = interaction.options.getUser('membre') || interaction.user;
      const data = levels[target.id] || { xp: 0, level: 0 };
      const needed = xpForNextLevel(data.level);
      const embed = new EmbedBuilder()
        .setColor(COLOR)
        .setTitle(`Niveau de ${target.username}`)
        .setThumbnail(target.displayAvatarURL())
        .addFields(
          { name: 'Niveau', value: `${data.level}`, inline: true },
          { name: 'XP', value: `${data.xp} / ${needed}`, inline: true },
        );
      return interaction.reply({ embeds: [embed] });
    }

    if (interaction.isChatInputCommand() && interaction.commandName === 'leaderboard') {
      const sorted = Object.entries(levels)
        .sort((a, b) => (b[1].level - a[1].level) || (b[1].xp - a[1].xp))
        .slice(0, 10);
      if (sorted.length === 0) {
        return interaction.reply({ content: "Personne n'a encore gagné d'XP." });
      }
      const lines = await Promise.all(sorted.map(async ([userId, d], i) => {
        const user = await client.users.fetch(userId).catch(() => null);
        const name = user ? user.username : 'Utilisateur inconnu';
        return `**${i + 1}.** ${name} — Niveau ${d.level} (${d.xp} XP)`;
      }));
      const embed = new EmbedBuilder()
        .setColor(COLOR)
        .setTitle('🏆 Classement PSIG')
        .setDescription(lines.join('\n'));
      return interaction.reply({ embeds: [embed] });
    }
  } catch (err) {
    console.error(err);
    if (interaction.isRepliable() && !interaction.replied && !interaction.deferred) {
      interaction.reply({ content: "Une erreur est survenue.", ephemeral: true }).catch(() => {});
    }
  }
});

// ---------- Journal de modération ----------

async function logModeration(guild, action, targetUser, moderator, reason) {
  const logChannel = guild.channels.cache.get(config.logChannelId);
  if (!logChannel) return;
  const embed = new EmbedBuilder()
    .setColor(COLOR)
    .setTitle(`Modération — ${action}`)
    .addFields(
      { name: 'Membre', value: `<@${targetUser.id}>`, inline: true },
      { name: 'Modérateur', value: `<@${moderator.id}>`, inline: true },
      { name: 'Raison', value: reason || 'Non spécifiée', inline: false },
    )
    .setTimestamp();
  await logChannel.send({ embeds: [embed] }).catch(() => {});
}

// ---------- Bienvenue + rôle civil automatique ----------

client.on('guildMemberAdd', async (member) => {
  try {
    if (config.civilianRoleId) {
      await member.roles.add(config.civilianRoleId).catch(() => {});
    }
    const channelId = settings.welcomeChannelId;
    if (!channelId) return;
    const channel = member.guild.channels.cache.get(channelId);
    if (!channel) return;
    const embed = new EmbedBuilder()
      .setColor(COLOR)
      .setTitle('Nouveau membre au PSIG')
      .setDescription(`Bienvenue <@${member.id}> sur le serveur !\nTu as reçu le rôle **Civil Côte d'Azur**.`)
      .setThumbnail(member.user.displayAvatarURL())
      .setTimestamp();
    await channel.send({ embeds: [embed] });
  } catch (err) {
    console.error('Erreur guildMemberAdd:', err);
  }
});

// ---------- Anti-spam + gain d'XP ----------

client.on('messageCreate', async (message) => {
  if (message.author.bot || !message.guild) return;

  // Anti-spam
  const now = Date.now();
  const timestamps = (spamTracker.get(message.author.id) || []).filter(t => now - t < SPAM_WINDOW_MS);
  timestamps.push(now);
  spamTracker.set(message.author.id, timestamps);

  if (timestamps.length > SPAM_LIMIT) {
    spamTracker.set(message.author.id, []);
    try {
      const member = await message.guild.members.fetch(message.author.id);
      if (member.moderatable) {
        await member.timeout(60 * 1000, 'Anti-spam automatique');
        await message.channel.send(`🔇 <@${message.author.id}> a été mis en sourdine 1 minute (anti-spam).`);
        await logModeration(message.guild, 'Anti-spam (mute auto)', message.author, client.user, 'Envoi de messages trop rapide');
      }
      // Supprime les messages récents de spam dans ce salon
      const recent = await message.channel.messages.fetch({ limit: 10 });
      const toDelete = recent.filter(m => m.author.id === message.author.id);
      await message.channel.bulkDelete(toDelete, true).catch(() => {});
    } catch (err) {
      console.error('Erreur anti-spam:', err);
    }
    return;
  }

  // Gain d'XP (cooldown 30s)
  const lastGain = xpCooldown.get(message.author.id) || 0;
  if (now - lastGain < 30000) return;
  xpCooldown.set(message.author.id, now);

  const gained = Math.floor(Math.random() * 10) + 5; // entre 5 et 14 XP
  const { level, leveledUp } = addXp(message.author.id, gained);
  if (leveledUp) {
    message.channel.send(`🎉 <@${message.author.id}> passe **niveau ${level}** !`).catch(() => {});
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

// ---------- Petit serveur web (requis par Render pour garder le service actif) ----------
const PORT = process.env.PORT || 3000;
http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/plain' });
  res.end('PSIG Bot en ligne.');
}).listen(PORT, () => {
  console.log(`Serveur web actif sur le port ${PORT} (requis par Render)`);
});
