require('dotenv').config();
const fs = require('fs');
const path = require('path');
const http = require('http');
const {
  Client, GatewayIntentBits, Partials, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle,
  StringSelectMenuBuilder, ModalBuilder, TextInputBuilder, TextInputStyle, PermissionsBitField,
  ChannelType, AttachmentBuilder,
} = require('discord.js');
const config = require('./config.json');

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds, GatewayIntentBits.GuildMembers, GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent, GatewayIntentBits.GuildModeration, GatewayIntentBits.GuildVoiceStates,
  ],
  partials: [Partials.Channel, Partials.Message],
});

const COLOR = 0x2b6cb0;
const COLOR_LOG = 0x718096;
const PANEL_SELECT_ID = 'ticket_select_category';
const MODAL_ID = 'ticket_modal_details';
const CLAIM_BUTTON_ID = 'ticket_claim';
const CLOSE_BUTTON_ID = 'ticket_close';

// ---------- Stockage (fichiers JSON) ----------
const DATA_DIR = path.join(__dirname, 'data');
const SETTINGS_PATH = path.join(DATA_DIR, 'settings.json');
const LEVELS_PATH = path.join(DATA_DIR, 'levels.json');
const CHARACTERS_PATH = path.join(DATA_DIR, 'characters.json');
const CASIERS_PATH = path.join(DATA_DIR, 'casiers.json');
const ENTREPRISES_PATH = path.join(DATA_DIR, 'entreprises.json');

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
function loadJson(fp, fb) { try { return JSON.parse(fs.readFileSync(fp, 'utf8')); } catch { return fb; } }
function saveJson(fp, d) { fs.writeFileSync(fp, JSON.stringify(d, null, 2)); }

const DEFAULT_SETTINGS = {
  welcomeChannelId: null, suggestionsChannelId: null, logsChannelId: null,
  reglementText: "Aucun règlement défini. /set-reglement pour le configurer.",
  liensText: "Aucun lien défini. /set-liens pour les configurer.",
  urgenceText: "🚨 Police : 17 | 🚑 SAMU : 15 | 🚒 Pompiers : 18 | ☎️ Urgence unique : 112",
  horaireText: "Aucun horaire défini. /set-horaire pour le configurer.",
  automod: { antiInvite: true, antiCaps: true, antiMassMention: true, antiRaid: true },
  recentJoins: [],
};
let settings = { ...DEFAULT_SETTINGS, ...loadJson(SETTINGS_PATH, {}) };
settings.automod = { ...DEFAULT_SETTINGS.automod, ...(settings.automod || {}) };
let levels = loadJson(LEVELS_PATH, {});
let characters = loadJson(CHARACTERS_PATH, {});
// casiers[userId] = { history:[{id,type,raison,moderateur,date}], notes:[{id,texte,moderateur,date}] }
let casiers = loadJson(CASIERS_PATH, {});
let entreprises = loadJson(ENTREPRISES_PATH, []);

function genId() { return Date.now().toString(36) + Math.floor(Math.random() * 1000).toString(36); }
function getRecord(userId) {
  if (!casiers[userId]) casiers[userId] = { history: [], notes: [] };
  return casiers[userId];
}
function addSanction(userId, type, raison, moderateur) {
  const rec = getRecord(userId);
  const entry = { id: genId(), type, raison: raison || 'Non spécifiée', moderateur, date: new Date().toLocaleString('fr-FR') };
  rec.history.push(entry);
  saveJson(CASIERS_PATH, casiers);
  return entry;
}
function countType(rec, type) { return rec.history.filter(h => h.type === type).length; }

function xpForNextLevel(l) { return 100 * (l + 1); }
function addXp(userId, amount) {
  if (!levels[userId]) levels[userId] = { xp: 0, level: 0 };
  const u = levels[userId];
  u.xp += amount;
  let up = false;
  while (u.xp >= xpForNextLevel(u.level)) { u.xp -= xpForNextLevel(u.level); u.level += 1; up = true; }
  saveJson(LEVELS_PATH, levels);
  return { level: u.level, leveledUp: up };
}

const spamTracker = new Map();
const SPAM_WINDOW_MS = 5000, SPAM_LIMIT = 5;
const xpCooldown = new Map();
const INVITE_REGEX = /(discord\.gg|discord(?:app)?\.com\/invite)\/\S+/i;

function slugify(t) { return t.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '').slice(0, 20); }

async function findExistingTicket(guild, userId) {
  const category = guild.channels.cache.get(config.ticketCategoryId);
  if (!category) return null;
  return guild.channels.cache.find(ch => ch.parentId === config.ticketCategoryId && ch.topic === `ticket-owner:${userId}`);
}
const TICKET_CATEGORIES = ['Support technique', 'Signalement', 'Question générale', 'Autre'];

async function createTicketChannel(interaction, title, fields) {
  const guild = interaction.guild;
  const staffRole = guild.roles.cache.get(config.staffRoleId);
  const channel = await guild.channels.create({
    name: `ticket-${slugify(interaction.user.username)}`, type: ChannelType.GuildText,
    parent: config.ticketCategoryId || null, topic: `ticket-owner:${interaction.user.id}`,
    permissionOverwrites: [
      { id: guild.roles.everyone.id, deny: [PermissionsBitField.Flags.ViewChannel] },
      { id: interaction.user.id, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages, PermissionsBitField.Flags.ReadMessageHistory] },
      ...(staffRole ? [{ id: staffRole.id, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages, PermissionsBitField.Flags.ReadMessageHistory] }] : []),
    ],
  });
  const embed = new EmbedBuilder().setColor(COLOR).setTitle(title).addFields({ name: 'Demandeur', value: `<@${interaction.user.id}>`, inline: true }, ...fields).setTimestamp();
  const buttons = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId(CLAIM_BUTTON_ID).setLabel('Réclamer').setStyle(ButtonStyle.Primary).setEmoji('🖐️'),
    new ButtonBuilder().setCustomId(CLOSE_BUTTON_ID).setLabel('Fermer le ticket').setStyle(ButtonStyle.Danger).setEmoji('🔒'),
  );
  await channel.send({ content: `${staffRole ? `<@&${staffRole.id}> ` : ''}<@${interaction.user.id}>`, embeds: [embed], components: [buttons] });
  return channel;
}

async function sendLog(guild, embed) {
  const channelId = settings.logsChannelId || config.logChannelId;
  const channel = guild.channels.cache.get(channelId);
  if (channel) await channel.send({ embeds: [embed] }).catch(() => {});
}
async function logModeration(guild, action, targetUser, moderator, reason) {
  await sendLog(guild, new EmbedBuilder().setColor(COLOR).setTitle(`Modération — ${action}`)
    .addFields({ name: 'Membre', value: `<@${targetUser.id}>`, inline: true }, { name: 'Modérateur', value: `<@${moderator.id}>`, inline: true }, { name: 'Raison', value: reason || 'Non spécifiée' })
    .setTimestamp());
}

client.once('ready', () => console.log(`Connecté en tant que ${client.user.tag}`));

client.on('interactionCreate', async (interaction) => {
  try {
    const cmd = interaction.isChatInputCommand() ? interaction.commandName : null;

    // ===== TICKETS =====
    if (cmd === 'panel-ticket') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const embed = new EmbedBuilder().setColor(COLOR).setTitle('Support — Ouvrir un ticket').setDescription('Choisis une catégorie. Un salon privé sera créé.');
      const select = new StringSelectMenuBuilder().setCustomId(PANEL_SELECT_ID).setPlaceholder('Choisis une catégorie').addOptions(TICKET_CATEGORIES.map(c => ({ label: c, value: c })));
      await interaction.channel.send({ embeds: [embed], components: [new ActionRowBuilder().addComponents(select)] });
      return interaction.reply({ content: 'Panneau publié.', ephemeral: true });
    }
    if (cmd === 'close') {
      if (!interaction.channel.topic?.startsWith('ticket-owner:')) return interaction.reply({ content: "Utilisable seulement dans un ticket.", ephemeral: true });
      return closeTicket(interaction);
    }
    if (interaction.isStringSelectMenu() && interaction.customId === PANEL_SELECT_ID) {
      const existing = await findExistingTicket(interaction.guild, interaction.user.id);
      if (existing) return interaction.reply({ content: `Ticket déjà ouvert : <#${existing.id}>`, ephemeral: true });
      const category = interaction.values[0];
      const modal = new ModalBuilder().setCustomId(`${MODAL_ID}:${encodeURIComponent(category)}`).setTitle(`Ticket — ${category}`);
      modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('details').setLabel('Décris ta demande').setStyle(TextInputStyle.Paragraph).setRequired(true).setMaxLength(1000)));
      return interaction.showModal(modal);
    }
    if (interaction.isModalSubmit() && interaction.customId.startsWith(MODAL_ID)) {
      await interaction.deferReply({ ephemeral: true });
      const category = decodeURIComponent(interaction.customId.split(':')[1]);
      const details = interaction.fields.getTextInputValue('details');
      const channel = await createTicketChannel(interaction, `Ticket — ${category}`, [{ name: 'Catégorie', value: category, inline: true }, { name: 'Détails', value: details }]);
      return interaction.editReply({ content: `Ticket créé : <#${channel.id}>` });
    }
    if (interaction.isModalSubmit() && interaction.customId.startsWith('form_modal:')) {
      await interaction.deferReply({ ephemeral: true });
      const formType = interaction.customId.split(':')[1];
      const values = interaction.fields.fields.map(f => ({ name: f.customId, value: interaction.fields.getTextInputValue(f.customId) }));
      const titles = { recrutement: 'Candidature — Recrutement', staff: 'Candidature — Staff', signalement: 'Signalement', gang: 'Création de gang', entreprise: "Création d'entreprise" };
      const channel = await createTicketChannel(interaction, titles[formType] || 'Formulaire', values.map(v => ({ name: v.name, value: v.value })));
      return interaction.editReply({ content: `Demande envoyée : <#${channel.id}>` });
    }
    if (interaction.isButton() && interaction.customId === CLAIM_BUTTON_ID) {
      const staffRole = interaction.guild.roles.cache.get(config.staffRoleId);
      if (staffRole && !interaction.member.roles.cache.has(staffRole.id)) return interaction.reply({ content: "Réservé au staff.", ephemeral: true });
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setDescription(`🖐️ Réclamé par <@${interaction.user.id}>.`)] });
    }
    if (interaction.isButton() && interaction.customId === CLOSE_BUTTON_ID) return closeTicket(interaction);

    if (['recrutement', 'staff', 'signalement', 'gang'].includes(cmd)) {
      const cfgs = {
        recrutement: { title: 'Candidature — Recrutement', fields: [['motivation', 'Pourquoi nous rejoindre ?'], ['experience', 'Ton expérience']] },
        staff: { title: 'Candidature — Staff', fields: [['motivation', 'Pourquoi devenir staff ?'], ['disponibilite', 'Tes disponibilités']] },
        signalement: { title: 'Signalement', fields: [['sujet', 'Qui/quoi signales-tu ?'], ['details', 'Explique la situation']] },
        gang: { title: 'Création de gang', fields: [['nom', 'Nom du gang'], ['description', 'Description']] },
      };
      const c = cfgs[cmd];
      const modal = new ModalBuilder().setCustomId(`form_modal:${cmd}`).setTitle(c.title);
      c.fields.forEach(([id, label]) => modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId(id).setLabel(label).setStyle(TextInputStyle.Paragraph).setRequired(true).setMaxLength(500))));
      return interaction.showModal(modal);
    }
    if (cmd === 'entreprise') {
      const modal = new ModalBuilder().setCustomId('form_modal:entreprise').setTitle("Création d'entreprise");
      modal.addComponents(
        new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('nom').setLabel("Nom de l'entreprise").setStyle(TextInputStyle.Short).setRequired(true)),
        new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('secteur').setLabel("Secteur d'activité").setStyle(TextInputStyle.Short).setRequired(true)),
        new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('description').setLabel('Description').setStyle(TextInputStyle.Paragraph).setRequired(true)),
      );
      return interaction.showModal(modal);
    }
    if (cmd === 'entreprises') {
      if (entreprises.length === 0) return interaction.reply({ content: "Aucune entreprise enregistrée." });
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('🏢 Entreprises').setDescription(entreprises.map((e, i) => `**${i + 1}. ${e.nom}** — ${e.secteur} (<@${e.proprietaire}>)`).join('\n'))] });
    }
    if (cmd === 'entreprise-ajouter') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const nom = interaction.options.getString('nom'), secteur = interaction.options.getString('secteur'), proprietaire = interaction.options.getUser('proprietaire');
      entreprises.push({ nom, secteur, proprietaire: proprietaire.id });
      saveJson(ENTREPRISES_PATH, entreprises);
      return interaction.reply({ content: `✅ **${nom}** ajoutée.` });
    }

    // ===== SANCTIONS =====
    if (cmd === 'kick') {
      const target = interaction.options.getMember('membre'); const reason = interaction.options.getString('raison') || 'Non spécifiée';
      if (!target) return interaction.reply({ content: 'Introuvable.', ephemeral: true });
      if (!target.kickable) return interaction.reply({ content: 'Impossible d\'expulser ce membre.', ephemeral: true });
      await target.kick(reason);
      addSanction(target.id, 'kick', reason, interaction.user.tag);
      await interaction.reply({ content: `👢 <@${target.id}> expulsé. Raison : ${reason}` });
      await logModeration(interaction.guild, 'Expulsion', target.user, interaction.user, reason);
      return;
    }
    if (cmd === 'ban') {
      const target = interaction.options.getMember('membre'); const reason = interaction.options.getString('raison') || 'Non spécifiée';
      if (!target) return interaction.reply({ content: 'Introuvable.', ephemeral: true });
      if (!target.bannable) return interaction.reply({ content: 'Impossible de bannir ce membre.', ephemeral: true });
      await target.ban({ reason });
      addSanction(target.id, 'ban', reason, interaction.user.tag);
      await interaction.reply({ content: `🔨 <@${target.id}> banni. Raison : ${reason}` });
      await logModeration(interaction.guild, 'Bannissement', target.user, interaction.user, reason);
      return;
    }
    if (cmd === 'tempban') {
      const target = interaction.options.getMember('membre'); const heures = interaction.options.getInteger('heures');
      const reason = interaction.options.getString('raison') || 'Non spécifiée';
      if (!target) return interaction.reply({ content: 'Introuvable.', ephemeral: true });
      if (!target.bannable) return interaction.reply({ content: 'Impossible de bannir ce membre.', ephemeral: true });
      const userId = target.id; const guildId = interaction.guild.id;
      await target.ban({ reason: `${reason} (tempban ${heures}h)` });
      addSanction(userId, 'tempban', `${reason} (${heures}h)`, interaction.user.tag);
      await interaction.reply({ content: `🔨 <@${userId}> banni ${heures}h. Raison : ${reason}` });
      await logModeration(interaction.guild, 'Bannissement temporaire', target.user, interaction.user, `${reason} (${heures}h)`);
      setTimeout(async () => {
        const guild = client.guilds.cache.get(guildId);
        if (guild) await guild.members.unban(userId, 'Fin du tempban').catch(() => {});
      }, heures * 60 * 60 * 1000);
      return;
    }
    if (cmd === 'unban') {
      const userId = interaction.options.getString('id');
      await interaction.guild.members.unban(userId).catch(() => {});
      addSanction(userId, 'unban', 'Débanni', interaction.user.tag);
      await interaction.reply({ content: `✅ <@${userId}> débanni.` });
      return;
    }
    if (cmd === 'softban') {
      const target = interaction.options.getMember('membre'); const reason = interaction.options.getString('raison') || 'Non spécifiée';
      if (!target) return interaction.reply({ content: 'Introuvable.', ephemeral: true });
      await target.ban({ reason, deleteMessageSeconds: 7 * 24 * 60 * 60 });
      await interaction.guild.members.unban(target.id, 'Softban').catch(() => {});
      addSanction(target.id, 'softban', reason, interaction.user.tag);
      await interaction.reply({ content: `🧹 <@${target.id}> softban (messages supprimés, débanni aussitôt). Raison : ${reason}` });
      await logModeration(interaction.guild, 'Softban', target.user, interaction.user, reason);
      return;
    }
    if (cmd === 'mute' || cmd === 'timeout') {
      const target = interaction.options.getMember('membre'); const minutes = interaction.options.getInteger('minutes');
      const reason = interaction.options.getString('raison') || 'Non spécifiée';
      if (!target) return interaction.reply({ content: 'Introuvable.', ephemeral: true });
      if (!target.moderatable) return interaction.reply({ content: 'Impossible de rendre ce membre muet.', ephemeral: true });
      await target.timeout(minutes * 60 * 1000, reason);
      addSanction(target.id, cmd, `${reason} (${minutes} min)`, interaction.user.tag);
      await interaction.reply({ content: `🔇 <@${target.id}> muet ${minutes} min. Raison : ${reason}` });
      await logModeration(interaction.guild, cmd === 'mute' ? 'Mute' : 'Timeout', target.user, interaction.user, `${reason} (${minutes} min)`);
      return;
    }
    if (cmd === 'unmute' || cmd === 'untimeout') {
      const target = interaction.options.getMember('membre');
      if (!target) return interaction.reply({ content: 'Introuvable.', ephemeral: true });
      await target.timeout(null);
      await interaction.reply({ content: `🔊 <@${target.id}> peut reparler.` });
      await logModeration(interaction.guild, cmd === 'unmute' ? 'Unmute' : 'Untimeout', target.user, interaction.user, '—');
      return;
    }
    if (cmd === 'warn') {
      const target = interaction.options.getUser('membre'); const reason = interaction.options.getString('raison');
      const entry = addSanction(target.id, 'warn', reason, interaction.user.tag);
      await interaction.reply({ content: `⚠️ <@${target.id}> averti (ID: \`${entry.id}\`). Raison : ${reason}` });
      await logModeration(interaction.guild, 'Avertissement', target, interaction.user, reason);
      target.send(`⚠️ Averti sur **${interaction.guild.name}**. Raison : ${reason}`).catch(() => {});
      return;
    }
    if (cmd === 'warnings') {
      const target = interaction.options.getUser('membre') || interaction.user;
      const rec = getRecord(target.id); const warns = rec.history.filter(h => h.type === 'warn');
      if (warns.length === 0) return interaction.reply({ content: `<@${target.id}> n'a aucun avertissement.` });
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle(`⚠️ Avertissements — ${target.username}`).setDescription(warns.map(w => `\`${w.id}\` — ${w.raison} *(${w.date}, par ${w.moderateur})*`).join('\n'))] });
    }
    if (cmd === 'unwarn') {
      const target = interaction.options.getUser('membre'); const id = interaction.options.getString('id');
      const rec = getRecord(target.id); const before = rec.history.length;
      rec.history = rec.history.filter(h => !(h.type === 'warn' && h.id === id));
      saveJson(CASIERS_PATH, casiers);
      return interaction.reply({ content: rec.history.length < before ? `✅ Avertissement \`${id}\` retiré.` : `Aucun avertissement avec cet ID.` });
    }
    if (cmd === 'clearwarns') {
      const target = interaction.options.getUser('membre');
      const rec = getRecord(target.id); rec.history = rec.history.filter(h => h.type !== 'warn');
      saveJson(CASIERS_PATH, casiers);
      return interaction.reply({ content: `✅ Tous les avertissements de <@${target.id}> supprimés.` });
    }
    if (cmd === 'note') {
      const target = interaction.options.getUser('membre'); const texte = interaction.options.getString('texte');
      const rec = getRecord(target.id); const entry = { id: genId(), texte, moderateur: interaction.user.tag, date: new Date().toLocaleString('fr-FR') };
      rec.notes.push(entry); saveJson(CASIERS_PATH, casiers);
      return interaction.reply({ content: `📝 Note ajoutée (ID: \`${entry.id}\`).`, ephemeral: true });
    }
    if (cmd === 'notes') {
      const target = interaction.options.getUser('membre');
      const rec = getRecord(target.id);
      if (rec.notes.length === 0) return interaction.reply({ content: 'Aucune note.', ephemeral: true });
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle(`📝 Notes — ${target.username}`).setDescription(rec.notes.map(n => `\`${n.id}\` — ${n.texte} *(${n.date}, par ${n.moderateur})*`).join('\n'))], ephemeral: true });
    }
    if (cmd === 'deletenote') {
      const id = interaction.options.getString('id');
      let found = false;
      for (const uid in casiers) { const before = casiers[uid].notes.length; casiers[uid].notes = casiers[uid].notes.filter(n => n.id !== id); if (casiers[uid].notes.length < before) found = true; }
      saveJson(CASIERS_PATH, casiers);
      return interaction.reply({ content: found ? '✅ Note supprimée.' : 'Note introuvable.', ephemeral: true });
    }
    if (cmd === 'casier') {
      const target = interaction.options.getUser('membre') || interaction.user;
      const rec = getRecord(target.id);
      const embed = new EmbedBuilder().setColor(COLOR).setTitle(`📁 Casier judiciaire — ${target.username}`).setThumbnail(target.displayAvatarURL())
        .addFields(
          { name: 'Warns', value: `${countType(rec, 'warn')}`, inline: true },
          { name: 'Mutes', value: `${countType(rec, 'mute')}`, inline: true },
          { name: 'Timeouts', value: `${countType(rec, 'timeout')}`, inline: true },
          { name: 'Kicks', value: `${countType(rec, 'kick')}`, inline: true },
          { name: 'Bans', value: `${countType(rec, 'ban') + countType(rec, 'tempban') + countType(rec, 'softban')}`, inline: true },
          { name: 'Notes', value: `${rec.notes.length}`, inline: true },
        );
      if (rec.history.length > 0) {
        const last = rec.history[rec.history.length - 1];
        embed.addFields({ name: 'Dernière sanction', value: `${last.type} — ${last.raison} *(${last.date})*` });
        const histo = rec.history.slice(-10).reverse().map(h => `\`${h.id}\` **${h.type}** — ${h.raison} *(${h.date}, par ${h.moderateur})*`).join('\n');
        embed.addFields({ name: 'Historique (10 dernières)', value: histo });
      } else {
        embed.addFields({ name: 'Historique', value: 'Casier vierge.' });
      }
      return interaction.reply({ embeds: [embed] });
    }
    if (cmd === 'staffstats') {
      const tally = {};
      for (const uid in casiers) {
        for (const h of casiers[uid].history) {
          if (!tally[h.moderateur]) tally[h.moderateur] = { warn: 0, mute: 0, timeout: 0, kick: 0, ban: 0, tempban: 0, softban: 0, total: 0 };
          if (tally[h.moderateur][h.type] !== undefined) tally[h.moderateur][h.type]++;
          tally[h.moderateur].total++;
        }
      }
      const sorted = Object.entries(tally).sort((a, b) => b[1].total - a[1].total).slice(0, 10);
      if (sorted.length === 0) return interaction.reply({ content: "Aucune sanction enregistrée pour l'instant." });
      const lines = sorted.map(([mod, s], i) => `**${i + 1}. ${mod}** — ${s.total} sanction(s) (⚠️${s.warn} 🔇${s.mute + s.timeout} 👢${s.kick} 🔨${s.ban + s.tempban + s.softban})`);
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('📊 Statistiques Staff').setDescription(lines.join('\n'))] });
    }

    // ===== ADMINISTRATION =====
    if (cmd === 'clear') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageMessages)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const nombre = interaction.options.getInteger('nombre');
      const deleted = await interaction.channel.bulkDelete(nombre, true).catch(() => null);
      return interaction.reply({ content: `🧹 ${deleted ? deleted.size : 0} message(s) supprimé(s).`, ephemeral: true });
    }
    if (cmd === 'nuke') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageChannels)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const oldChannel = interaction.channel;
      const newChannel = await oldChannel.clone();
      await newChannel.setPosition(oldChannel.position);
      await oldChannel.delete();
      await newChannel.send({ embeds: [new EmbedBuilder().setColor(COLOR).setDescription('💥 Salon réinitialisé.')] });
      return;
    }
    if (cmd === 'lock') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageChannels)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      await interaction.channel.permissionOverwrites.edit(interaction.guild.roles.everyone, { SendMessages: false });
      return interaction.reply({ content: '🔒 Salon verrouillé.' });
    }
    if (cmd === 'unlock') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageChannels)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      await interaction.channel.permissionOverwrites.edit(interaction.guild.roles.everyone, { SendMessages: null });
      return interaction.reply({ content: '🔓 Salon déverrouillé.' });
    }
    if (cmd === 'slowmode') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageChannels)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const secondes = interaction.options.getInteger('secondes');
      await interaction.channel.setRateLimitPerUser(secondes);
      return interaction.reply({ content: secondes > 0 ? `🐌 Slowmode réglé sur ${secondes}s.` : '✅ Slowmode désactivé.' });
    }
    if (cmd === 'embed') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const titre = interaction.options.getString('titre'); const texte = interaction.options.getString('texte');
      const couleur = interaction.options.getString('couleur');
      const embed = new EmbedBuilder().setTitle(titre).setDescription(texte).setColor(couleur ? parseInt(couleur.replace('#', ''), 16) : COLOR);
      await interaction.channel.send({ embeds: [embed] });
      return interaction.reply({ content: '✅ Embed envoyé.', ephemeral: true });
    }
    if (cmd === 'roleinfo') {
      const role = interaction.options.getRole('role');
      const embed = new EmbedBuilder().setColor(role.color || COLOR).setTitle(`Rôle — ${role.name}`)
        .addFields({ name: 'Membres', value: `${role.members.size}`, inline: true }, { name: 'Couleur', value: role.hexColor, inline: true }, { name: 'Mentionnable', value: role.mentionable ? 'Oui' : 'Non', inline: true }, { name: 'Créé le', value: `<t:${Math.floor(role.createdTimestamp / 1000)}:D>`, inline: true });
      return interaction.reply({ embeds: [embed] });
    }

    // ===== CONFIG =====
    if (cmd === 'set-welcome') { settings.welcomeChannelId = interaction.options.getChannel('salon').id; saveJson(SETTINGS_PATH, settings); return interaction.reply({ content: '✅ Salon de bienvenue défini.', ephemeral: true }); }
    if (cmd === 'set-reglement') { settings.reglementText = interaction.options.getString('texte'); saveJson(SETTINGS_PATH, settings); return interaction.reply({ content: '✅ Règlement mis à jour.', ephemeral: true }); }
    if (cmd === 'set-liens') { settings.liensText = interaction.options.getString('texte'); saveJson(SETTINGS_PATH, settings); return interaction.reply({ content: '✅ Liens mis à jour.', ephemeral: true }); }
    if (cmd === 'set-urgence') { settings.urgenceText = interaction.options.getString('texte'); saveJson(SETTINGS_PATH, settings); return interaction.reply({ content: '✅ Urgences mises à jour.', ephemeral: true }); }
    if (cmd === 'set-horaire') { settings.horaireText = interaction.options.getString('texte'); saveJson(SETTINGS_PATH, settings); return interaction.reply({ content: '✅ Horaires mis à jour.', ephemeral: true }); }
    if (cmd === 'set-suggestions') { settings.suggestionsChannelId = interaction.options.getChannel('salon').id; saveJson(SETTINGS_PATH, settings); return interaction.reply({ content: '✅ Salon de suggestions défini.', ephemeral: true }); }
    if (cmd === 'set-logs') { settings.logsChannelId = interaction.options.getChannel('salon').id; saveJson(SETTINGS_PATH, settings); return interaction.reply({ content: '✅ Salon de logs défini.', ephemeral: true }); }

    // ===== INFOS =====
    if (cmd === 'reglement') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('📜 Règlement').setDescription(settings.reglementText)] });
    if (cmd === 'liens') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('🔗 Liens utiles').setDescription(settings.liensText)] });
    if (cmd === 'urgence') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle("🚨 Numéros d'urgence").setDescription(settings.urgenceText)] });
    if (cmd === 'horaire') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('🕒 Horaires').setDescription(settings.horaireText)] });
    if (cmd === 'codes') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('📻 Codes radio').setDescription("**10-20** : Position\n**10-4** : Message reçu\n**Code 0** : Urgence vitale\n**Code 1** : Intervention normale\n**Code 3** : Intervention urgente")] });
    if (cmd === 'roles') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('📋 Rôles').setDescription(interaction.guild.roles.cache.filter(r => r.id !== interaction.guild.id).sort((a, b) => b.position - a.position).map(r => `${r}`).join('\n') || 'Aucun')] });
    if (cmd === 'help') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('📖 Commandes').addFields(
      { name: '📜 Infos', value: '/reglement /roles /liens /urgence /horaire /codes' },
      { name: '🎭 RP', value: '/creer-personnage /profil /id /me /dire /cni /gang /entreprise /entreprises' },
      { name: '📁 Casier & Notes', value: '/casier /warn /warnings /unwarn /clearwarns /note /notes /deletenote' },
      { name: '👮 Sanctions', value: '/kick /ban /tempban /unban /softban /mute /unmute /timeout /untimeout' },
      { name: '⚙️ Administration', value: '/clear /lock /unlock /slowmode /nuke /embed /roleinfo /staffstats' },
      { name: '🎫 Support', value: '/panel-ticket /close /recrutement /staff /signalement' },
      { name: '🎉 Utilitaires', value: '/ping /avatar /userinfo /serverinfo /suggestion /annonce' },
      { name: '🎮 Fun', value: '/8ball /des /pileouface' },
      { name: '📈 Niveaux', value: '/rank /leaderboard' },
    )] });

    // ===== NIVEAUX =====
    if (cmd === 'rank') {
      const target = interaction.options.getUser('membre') || interaction.user;
      const data = levels[target.id] || { xp: 0, level: 0 };
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle(`Niveau de ${target.username}`).setThumbnail(target.displayAvatarURL()).addFields({ name: 'Niveau', value: `${data.level}`, inline: true }, { name: 'XP', value: `${data.xp} / ${xpForNextLevel(data.level)}`, inline: true })] });
    }
    if (cmd === 'leaderboard') {
      const sorted = Object.entries(levels).sort((a, b) => (b[1].level - a[1].level) || (b[1].xp - a[1].xp)).slice(0, 10);
      if (sorted.length === 0) return interaction.reply({ content: "Personne n'a encore gagné d'XP." });
      const lines = await Promise.all(sorted.map(async ([uid, d], i) => { const u = await client.users.fetch(uid).catch(() => null); return `**${i + 1}.** ${u ? u.username : 'Inconnu'} — Niveau ${d.level} (${d.xp} XP)`; }));
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('🏆 Classement').setDescription(lines.join('\n'))] });
    }

    // ===== RP =====
    if (cmd === 'creer-personnage') {
      const nom = interaction.options.getString('nom'), age = interaction.options.getInteger('age'), description = interaction.options.getString('description');
      characters[interaction.user.id] = { nom, age, description }; saveJson(CHARACTERS_PATH, characters);
      return interaction.reply({ content: `✅ Fiche créée pour **${nom}**.`, ephemeral: true });
    }
    if (cmd === 'profil' || cmd === 'id') {
      const target = interaction.options.getUser('membre') || interaction.user; const perso = characters[target.id];
      if (!perso) return interaction.reply({ content: "Pas de fiche. Utilise /creer-personnage.", ephemeral: true });
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle(`🪪 ${perso.nom}`).setThumbnail(target.displayAvatarURL()).addFields({ name: 'Âge', value: `${perso.age}`, inline: true }, { name: 'Joueur', value: `<@${target.id}>`, inline: true }, { name: 'Description', value: perso.description })] });
    }
    if (cmd === 'cni') {
      const nom = interaction.options.getString('nom'), naissance = interaction.options.getString('naissance'), adresse = interaction.options.getString('adresse');
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle("🪪 Carte Nationale d'Identité").setThumbnail(interaction.user.displayAvatarURL()).addFields({ name: 'Nom', value: nom, inline: true }, { name: 'Naissance', value: naissance, inline: true }, { name: 'Adresse', value: adresse })] });
    }
    if (cmd === 'me') { const action = interaction.options.getString('action'); const perso = characters[interaction.user.id]; return interaction.reply({ content: `*${perso ? perso.nom : interaction.user.username} ${action}*` }); }
    if (cmd === 'dire') { const texte = interaction.options.getString('message'); const perso = characters[interaction.user.id]; return interaction.reply({ content: `**${perso ? perso.nom : interaction.user.username} dit :** ${texte}` }); }

    // ===== UTILITAIRES =====
    if (cmd === 'ping') return interaction.reply({ content: `🏓 Pong ! ${client.ws.ping}ms` });
    if (cmd === 'avatar') { const target = interaction.options.getUser('membre') || interaction.user; return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle(`Avatar de ${target.username}`).setImage(target.displayAvatarURL({ size: 512 }))] }); }
    if (cmd === 'userinfo') {
      const target = interaction.options.getMember('membre') || interaction.member;
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle(`Infos — ${target.user.username}`).setThumbnail(target.user.displayAvatarURL()).addFields(
        { name: 'A rejoint', value: `<t:${Math.floor(target.joinedTimestamp / 1000)}:D>`, inline: true },
        { name: 'Compte créé', value: `<t:${Math.floor(target.user.createdTimestamp / 1000)}:D>`, inline: true },
        { name: 'Rôles', value: target.roles.cache.filter(r => r.id !== interaction.guild.id).map(r => `${r}`).join(', ') || 'Aucun' },
      )] });
    }
    if (cmd === 'serverinfo') {
      const g = interaction.guild;
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle(g.name).setThumbnail(g.iconURL()).addFields({ name: 'Membres', value: `${g.memberCount}`, inline: true }, { name: 'Créé le', value: `<t:${Math.floor(g.createdTimestamp / 1000)}:D>`, inline: true }, { name: 'Salons', value: `${g.channels.cache.size}`, inline: true })] });
    }
    if (cmd === 'suggestion') {
      const texte = interaction.options.getString('texte');
      const target = settings.suggestionsChannelId ? interaction.guild.channels.cache.get(settings.suggestionsChannelId) : interaction.channel;
      const sent = await target.send({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('💡 Suggestion').setDescription(texte).setFooter({ text: `Par ${interaction.user.username}` })] });
      await sent.react('👍'); await sent.react('👎');
      return interaction.reply({ content: `✅ Envoyée dans <#${target.id}>.`, ephemeral: true });
    }
    if (cmd === 'annonce') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const titre = interaction.options.getString('titre'), message = interaction.options.getString('message'), salon = interaction.options.getChannel('salon') || interaction.channel;
      await salon.send({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle(`📢 ${titre}`).setDescription(message).setFooter({ text: `Par ${interaction.user.username}` }).setTimestamp()] });
      return interaction.reply({ content: `✅ Publiée dans <#${salon.id}>.`, ephemeral: true });
    }
    if (cmd === 'sondage') {
      const question = interaction.options.getString('question');
      const options = [1, 2, 3, 4].map(i => interaction.options.getString(`option${i}`)).filter(Boolean);
      const emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣'];
      await interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle(`📊 ${question}`).setDescription(options.map((o, i) => `${emojis[i]} ${o}`).join('\n'))] });
      const sent = await interaction.fetchReply();
      for (let i = 0; i < options.length; i++) await sent.react(emojis[i]);
      return;
    }

    // ===== FUN =====
    if (cmd === '8ball') { const r = ['Oui, certainement.', 'Non, aucune chance.', 'Peut-être...', 'Demande plus tard.', "C'est certain !", 'Incertain.']; return interaction.reply({ content: `🎱 ${r[Math.floor(Math.random() * r.length)]}` }); }
    if (cmd === 'des') { const faces = interaction.options.getInteger('faces') || 6; return interaction.reply({ content: `🎲 **${Math.floor(Math.random() * faces) + 1}** (sur ${faces})` }); }
    if (cmd === 'pileouface') return interaction.reply({ content: `🪙 **${Math.random() < 0.5 ? 'Pile' : 'Face'}** !` });
  } catch (err) {
    console.error(err);
    if (interaction.isRepliable() && !interaction.replied && !interaction.deferred) interaction.reply({ content: "Erreur.", ephemeral: true }).catch(() => {});
  }
});

// ---------- Bienvenue + anti-raid ----------
client.on('guildMemberAdd', async (member) => {
  try {
    if (config.civilianRoleId) await member.roles.add(config.civilianRoleId).catch(() => {});

    // Détection compte récent
    const accountAge = Date.now() - member.user.createdTimestamp;
    if (accountAge < 7 * 24 * 60 * 60 * 1000) {
      await sendLog(member.guild, new EmbedBuilder().setColor(0xe53e3e).setTitle('⚠️ Compte récemment créé').setDescription(`<@${member.id}> a créé son compte il y a moins de 7 jours.`).setTimestamp());
    }

    // Anti-raid : trop d'arrivées rapprochées
    if (settings.automod.antiRaid) {
      const now = Date.now();
      settings.recentJoins = (settings.recentJoins || []).filter(t => now - t < 10000);
      settings.recentJoins.push(now);
      saveJson(SETTINGS_PATH, settings);
      if (settings.recentJoins.length >= 8) {
        await sendLog(member.guild, new EmbedBuilder().setColor(0xe53e3e).setTitle('🚨 Raid potentiel détecté').setDescription('8+ arrivées en moins de 10 secondes.').setTimestamp());
      }
    }

    await sendLog(member.guild, new EmbedBuilder().setColor(0x38a169).setTitle('➕ Arrivée').setDescription(`<@${member.id}> a rejoint le serveur.`).setTimestamp());

    const channelId = settings.welcomeChannelId;
    if (channelId) {
      const channel = member.guild.channels.cache.get(channelId);
      if (channel) await channel.send({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle(`Bienvenue sur ${member.guild.name} !`).setDescription(`Bienvenue <@${member.id}> !`).setThumbnail(member.user.displayAvatarURL()).setTimestamp()] });
    }
  } catch (err) { console.error('guildMemberAdd:', err); }
});
client.on('guildMemberRemove', async (member) => {
  await sendLog(member.guild, new EmbedBuilder().setColor(0xe53e3e).setTitle('➖ Départ').setDescription(`${member.user.tag} a quitté le serveur.`).setTimestamp());
});
client.on('guildMemberUpdate', async (oldM, newM) => {
  if (oldM.nickname !== newM.nickname) {
    await sendLog(newM.guild, new EmbedBuilder().setColor(COLOR_LOG).setTitle('✏️ Pseudo modifié').setDescription(`<@${newM.id}> : \`${oldM.nickname || oldM.user.username}\` → \`${newM.nickname || newM.user.username}\``).setTimestamp());
  }
});
client.on('messageDelete', async (message) => {
  if (!message.guild || message.author?.bot) return;
  await sendLog(message.guild, new EmbedBuilder().setColor(0xe53e3e).setTitle('🗑️ Message supprimé').addFields({ name: 'Auteur', value: `<@${message.author?.id}>`, inline: true }, { name: 'Salon', value: `${message.channel}`, inline: true }, { name: 'Contenu', value: message.content?.slice(0, 1000) || '[non disponible]' }).setTimestamp());
});
client.on('messageUpdate', async (oldMsg, newMsg) => {
  if (!newMsg.guild || newMsg.author?.bot || oldMsg.content === newMsg.content) return;
  await sendLog(newMsg.guild, new EmbedBuilder().setColor(0xd69e2e).setTitle('✏️ Message modifié').addFields({ name: 'Auteur', value: `<@${newMsg.author?.id}>`, inline: true }, { name: 'Salon', value: `${newMsg.channel}`, inline: true }, { name: 'Avant', value: oldMsg.content?.slice(0, 500) || '[vide]' }, { name: 'Après', value: newMsg.content?.slice(0, 500) || '[vide]' }).setTimestamp());
});
client.on('channelCreate', async (channel) => { if (channel.guild) await sendLog(channel.guild, new EmbedBuilder().setColor(0x38a169).setTitle('📁 Salon créé').setDescription(`${channel}`).setTimestamp()); });
client.on('channelDelete', async (channel) => { if (channel.guild) await sendLog(channel.guild, new EmbedBuilder().setColor(0xe53e3e).setTitle('🗑️ Salon supprimé').setDescription(`#${channel.name}`).setTimestamp()); });
client.on('roleCreate', async (role) => { await sendLog(role.guild, new EmbedBuilder().setColor(0x38a169).setTitle('🎭 Rôle créé').setDescription(`${role}`).setTimestamp()); });
client.on('roleDelete', async (role) => { await sendLog(role.guild, new EmbedBuilder().setColor(0xe53e3e).setTitle('🎭 Rôle supprimé').setDescription(`${role.name}`).setTimestamp()); });
client.on('voiceStateUpdate', async (oldS, newS) => {
  const member = newS.member || oldS.member;
  if (!oldS.channel && newS.channel) await sendLog(newS.guild, new EmbedBuilder().setColor(COLOR_LOG).setTitle('🔊 Connexion vocale').setDescription(`<@${member.id}> a rejoint ${newS.channel}`).setTimestamp());
  else if (oldS.channel && !newS.channel) await sendLog(oldS.guild, new EmbedBuilder().setColor(COLOR_LOG).setTitle('🔇 Déconnexion vocale').setDescription(`<@${member.id}> a quitté ${oldS.channel}`).setTimestamp());
  else if (oldS.channel && newS.channel && oldS.channel.id !== newS.channel.id) await sendLog(newS.guild, new EmbedBuilder().setColor(COLOR_LOG).setTitle('🔀 Changement de salon vocal').setDescription(`<@${member.id}> : ${oldS.channel} → ${newS.channel}`).setTimestamp());
});

// ---------- AutoMod + Anti-spam + XP ----------
client.on('messageCreate', async (message) => {
  if (message.author.bot || !message.guild) return;

  // Anti-lien d'invitation
  if (settings.automod.antiInvite && INVITE_REGEX.test(message.content) && !message.member.permissions.has(PermissionsBitField.Flags.ManageMessages)) {
    await message.delete().catch(() => {});
    await message.channel.send(`🔗 <@${message.author.id}>, les liens d'invitation ne sont pas autorisés.`).then(m => setTimeout(() => m.delete().catch(() => {}), 5000));
    await sendLog(message.guild, new EmbedBuilder().setColor(0xe53e3e).setTitle('🔗 Lien invitation bloqué').setDescription(`<@${message.author.id}> dans ${message.channel}`).setTimestamp());
    return;
  }
  // Anti-mentions massives
  if (settings.automod.antiMassMention && message.mentions.users.size >= 5) {
    await message.delete().catch(() => {});
    await sendLog(message.guild, new EmbedBuilder().setColor(0xe53e3e).setTitle('📢 Mentions massives bloquées').setDescription(`<@${message.author.id}> a mentionné ${message.mentions.users.size} membres.`).setTimestamp());
    return;
  }
  // Anti-caps (messages longs tout en majuscules)
  if (settings.automod.antiCaps && message.content.length > 15) {
    const letters = message.content.replace(/[^a-zA-Z]/g, '');
    const upper = message.content.replace(/[^A-Z]/g, '');
    if (letters.length > 10 && upper.length / letters.length > 0.7) {
      await message.delete().catch(() => {});
      await message.channel.send(`🔠 <@${message.author.id}>, évite les majuscules excessives.`).then(m => setTimeout(() => m.delete().catch(() => {}), 5000));
      return;
    }
  }

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
        await message.channel.send(`🔇 <@${message.author.id}> mis en sourdine 1 min (anti-spam).`);
        addSanction(message.author.id, 'timeout', 'Anti-spam automatique', 'AutoMod');
        await logModeration(message.guild, 'Anti-spam (mute auto)', message.author, client.user, 'Messages trop rapides');
      }
      const recent = await message.channel.messages.fetch({ limit: 10 });
      await message.channel.bulkDelete(recent.filter(m => m.author.id === message.author.id), true).catch(() => {});
    } catch (err) { console.error('Anti-spam:', err); }
    return;
  }

  // XP
  const lastGain = xpCooldown.get(message.author.id) || 0;
  if (now - lastGain < 30000) return;
  xpCooldown.set(message.author.id, now);
  const { level, leveledUp } = addXp(message.author.id, Math.floor(Math.random() * 10) + 5);
  if (leveledUp) message.channel.send(`🎉 <@${message.author.id}> passe **niveau ${level}** !`).catch(() => {});
});

async function closeTicket(interaction) {
  const channel = interaction.channel;
  const staffRole = interaction.guild.roles.cache.get(config.staffRoleId);
  if (staffRole && interaction.member && !interaction.member.roles.cache.has(staffRole.id)) return interaction.reply({ content: "Réservé au staff.", ephemeral: true });
  await interaction.reply({ content: 'Fermeture dans 5s... Génération du transcript.' });
  const messages = await channel.messages.fetch({ limit: 100 });
  const lines = [...messages.values()].reverse().map(m => `[${m.createdAt.toISOString()}] ${m.author?.tag ?? 'Inconnu'}: ${m.content || '[embed/composant]'}`);
  const tp = path.join(__dirname, `transcript-${channel.id}.txt`);
  fs.writeFileSync(tp, lines.join('\n') || 'Aucun message.');
  const logChannel = interaction.guild.channels.cache.get(settings.logsChannelId || config.logChannelId);
  if (logChannel) {
    const attachment = new AttachmentBuilder(tp, { name: `transcript-${channel.name}.txt` });
    await logChannel.send({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('Ticket fermé').addFields({ name: 'Salon', value: `#${channel.name}`, inline: true }, { name: 'Fermé par', value: `<@${interaction.user.id}>`, inline: true }).setTimestamp()], files: [attachment] }).catch(() => {});
  }
  fs.unlink(tp, () => {});
  setTimeout(() => channel.delete().catch(() => {}), 5000);
}

client.login(process.env.DISCORD_TOKEN);
const PORT = process.env.PORT || 3000;
http.createServer((req, res) => { res.writeHead(200, { 'Content-Type': 'text/plain' }); res.end('Bot en ligne.'); }).listen(PORT, () => console.log(`Serveur web actif sur le port ${PORT}`));
