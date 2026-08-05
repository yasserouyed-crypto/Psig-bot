require('dotenv').config();
const fs = require('fs');
const path = require('path');
const http = require('http');
const {
  Client, GatewayIntentBits, Partials, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle,
  StringSelectMenuBuilder, RoleSelectMenuBuilder, ChannelSelectMenuBuilder, UserSelectMenuBuilder, ModalBuilder, TextInputBuilder, TextInputStyle, PermissionsBitField,
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

const COLOR = 0x00d9ff;       // Cyan premium — couleur principale
const COLOR_DARK = 0x0a0e27;  // Bleu nuit profond
const COLOR_ACCENT = 0x5865f2;// Bleu accent (boutons)
const COLOR_SUCCESS = 0x2ecc71;
const COLOR_WARNING = 0xf5a623;
const COLOR_DANGER = 0xe53e3e;
const COLOR_LOG = 0x4a5568;
const BOT_ICON = () => client.user.displayAvatarURL();
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
const RAPPORTS_PATH = path.join(DATA_DIR, 'rapports.json');
const CNI_PATH = path.join(DATA_DIR, 'cni.json');
const CANDIDATURES_PATH = path.join(DATA_DIR, 'candidatures.json');
const BACKUPS_PATH = path.join(DATA_DIR, 'backups.json');

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
function loadJson(fp, fb) { try { return JSON.parse(fs.readFileSync(fp, 'utf8')); } catch { return fb; } }
function saveJson(fp, d) { fs.writeFileSync(fp, JSON.stringify(d, null, 2)); }

const DEFAULT_SETTINGS = {
  welcomeChannelId: null, suggestionsChannelId: null, logsChannelId: null,
  staffRoleId: null, ticketCategoryId: null, civilianRoleId: null,
  reglementText: "Aucun règlement défini. /set-reglement pour le configurer.",
  liensText: "Aucun lien défini. /set-liens pour les configurer.",
  urgenceText: "🚨 Police : 17 | 🚑 SAMU : 15 | 🚒 Pompiers : 18 | ☎️ Urgence unique : 112",
  horaireText: "Aucun horaire défini. /set-horaire pour le configurer.",
  automod: { antiInvite: true, antiCaps: true, antiMassMention: true, antiRaid: true },
  recentJoins: [],
  levelRewards: {},
  levelUpChannelId: null,
  reglementRoleId: null,
  ticketCategories: [],
};
// settingsAll[guildId] = { ...DEFAULT_SETTINGS }  -> réglages propres à CHAQUE serveur
let settingsAll = loadJson(SETTINGS_PATH, {});
function getSettings(guildId) {
  if (!settingsAll[guildId]) settingsAll[guildId] = JSON.parse(JSON.stringify(DEFAULT_SETTINGS));
  settingsAll[guildId].automod = { ...DEFAULT_SETTINGS.automod, ...(settingsAll[guildId].automod || {}) };
  return settingsAll[guildId];
}
function saveSettings() { saveJson(SETTINGS_PATH, settingsAll); }

let levels = loadJson(LEVELS_PATH, {}); // clé: `${guildId}:${userId}`
let characters = loadJson(CHARACTERS_PATH, {}); // clé: `${guildId}:${userId}`
// casiers[`${guildId}:${userId}`] = { history:[{id,type,raison,moderateur,date}], notes:[{id,texte,moderateur,date}] }
let casiers = loadJson(CASIERS_PATH, {});
let entreprises = loadJson(ENTREPRISES_PATH, []); // { nom, secteur, proprietaire, guildId }
let rapports = loadJson(RAPPORTS_PATH, []); // { id, guildId, auteur, service, description, date }
let cniData = loadJson(CNI_PATH, {}); // clé: `${guildId}:${userId}`
let candidatures = loadJson(CANDIDATURES_PATH, []); // [{id, type, userId, channelId, guildId, statut, date}]
let backups = loadJson(BACKUPS_PATH, {}); // backups[guildId] = { date, roles:[...], categories:[...], channels:[...] }

function createServerBackup(guild) {
  const roles = guild.roles.cache
    .filter(r => r.id !== guild.id && !r.managed)
    .sort((a, b) => b.position - a.position)
    .map(r => ({ name: r.name, color: r.color, hoist: r.hoist, mentionable: r.mentionable, permissions: r.permissions.bitfield.toString(), position: r.position }));
  const categories = guild.channels.cache
    .filter(ch => ch.type === ChannelType.GuildCategory)
    .map(ch => ({ name: ch.name, position: ch.position }));
  const channels = guild.channels.cache
    .filter(ch => ch.type === ChannelType.GuildText || ch.type === ChannelType.GuildVoice)
    .map(ch => ({ name: ch.name, type: ch.type, parentName: ch.parent?.name || null, position: ch.position, topic: ch.topic || null }));
  backups[guild.id] = { date: new Date().toLocaleString('fr-FR'), roles, categories, channels };
  saveJson(BACKUPS_PATH, backups);
  return backups[guild.id];
}

async function restoreServerBackup(guild) {
  const backup = backups[guild.id];
  if (!backup) return { rolesCreated: 0, categoriesCreated: 0, channelsCreated: 0, error: 'Aucune sauvegarde trouvée.' };
  let rolesCreated = 0, categoriesCreated = 0, channelsCreated = 0;

  for (const r of backup.roles) {
    if (!guild.roles.cache.find(role => role.name === r.name)) {
      await guild.roles.create({ name: r.name, color: r.color, hoist: r.hoist, mentionable: r.mentionable, permissions: BigInt(r.permissions) }).catch(() => {});
      rolesCreated++;
    }
  }
  for (const c of backup.categories) {
    if (!guild.channels.cache.find(ch => ch.type === ChannelType.GuildCategory && ch.name === c.name)) {
      await guild.channels.create({ name: c.name, type: ChannelType.GuildCategory }).catch(() => {});
      categoriesCreated++;
    }
  }
  for (const ch of backup.channels) {
    const exists = guild.channels.cache.find(gc => gc.name === ch.name && gc.type === ch.type);
    if (!exists) {
      const parent = ch.parentName ? guild.channels.cache.find(gc => gc.type === ChannelType.GuildCategory && gc.name === ch.parentName) : null;
      await guild.channels.create({ name: ch.name, type: ch.type, parent: parent?.id || null, topic: ch.topic || undefined }).catch(() => {});
      channelsCreated++;
    }
  }
  return { rolesCreated, categoriesCreated, channelsCreated };
}

function key(guildId, userId) { return `${guildId}:${userId}`; }

function genId() { return Date.now().toString(36) + Math.floor(Math.random() * 1000).toString(36); }
function getRecord(k) {
  if (!casiers[k]) casiers[k] = { history: [], notes: [] };
  return casiers[k];
}
function addSanction(k, type, raison, moderateur) {
  const rec = getRecord(k);
  const entry = { id: genId(), type, raison: raison || 'Non spécifiée', moderateur, date: new Date().toLocaleString('fr-FR') };
  rec.history.push(entry);
  saveJson(CASIERS_PATH, casiers);
  return entry;
}
function countType(rec, type) { return rec.history.filter(h => h.type === type).length; }

function xpForNextLevel(l) { return 100 * (l + 1); }
function addXp(k, amount) {
  if (!levels[k]) levels[k] = { xp: 0, level: 0, messages: 0 };
  const u = levels[k];
  u.xp += amount;
  u.messages = (u.messages || 0) + 1;
  let up = false;
  while (u.xp >= xpForNextLevel(u.level)) { u.xp -= xpForNextLevel(u.level); u.level += 1; up = true; }
  saveJson(LEVELS_PATH, levels);
  return { level: u.level, leveledUp: up };
}
function progressBar(current, total, length = 14) {
  const ratio = Math.max(0, Math.min(1, current / total));
  const filled = Math.round(ratio * length);
  return '▰'.repeat(filled) + '▱'.repeat(length - filled);
}
function getRank(k) {
  const sorted = Object.entries(levels).sort((a, b) => (b[1].level - a[1].level) || (b[1].xp - a[1].xp));
  const idx = sorted.findIndex(([id]) => id === k);
  return idx === -1 ? sorted.length + 1 : idx + 1;
}
async function checkLevelRewards(guild, member, level) {
  const roleId = (getSettings(guild.id).levelRewards || {})[level];
  if (!roleId) return;
  await member.roles.add(roleId).catch(() => {});
}


const spamTracker = new Map();
const activePolls = new Map(); // pollId -> { question, options, votes: { userId: optionIndex } }
const SPAM_WINDOW_MS = 5000, SPAM_LIMIT = 5;
const xpCooldown = new Map();
const INVITE_REGEX = /(discord\.gg|discord(?:app)?\.com\/invite)\/\S+/i;

function slugify(t) { return t.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '').slice(0, 20); }

async function findExistingTicket(guild, userId) {
  const s = getSettings(guild.id);
  const category = guild.channels.cache.get(s.ticketCategoryId);
  if (!category) return null;
  return guild.channels.cache.find(ch => ch.parentId === s.ticketCategoryId && ch.topic === `ticket-owner:${userId}`);
}
const DEFAULT_TICKET_CATEGORIES = [
  { nom: 'Fondation', emoji: '👑', desc: '• Décale / Fusion.\n• Propositions.' },
  { nom: 'Reports Staff', emoji: '🚫', desc: "• Pour signaler le comportement abusif d'un Staff." },
  { nom: 'Partenariats', emoji: '🔗', desc: '• Demande de partenariat avec notre serveur.' },
  { nom: 'Questions', emoji: '❓', desc: "• Pose une question générale à l'équipe." },
  { nom: 'Unban', emoji: '🔓', desc: '• Demande de débannissement.' },
  { nom: 'Reports Joueurs', emoji: '🚨', desc: '• Signale un joueur qui enfreint le règlement.' },
  { nom: 'Entreprises', emoji: '🏢', desc: "• Demande liée à la création ou gestion d'une entreprise." },
];
function getTicketCategories(guildId) {
  const s = getSettings(guildId);
  if (!s.ticketCategories) s.ticketCategories = [];
  return s.ticketCategories;
}
const SUBJECT_BUTTON_ID = 'ticket_subject';
const ADD_BUTTON_ID = 'ticket_add';
const REMOVE_BUTTON_ID = 'ticket_remove';
const SUBJECT_MODAL_ID = 'ticket_modal_subject';
const ADD_MODAL_ID = 'ticket_modal_add';
const REMOVE_MODAL_ID = 'ticket_modal_remove';

async function createTicketChannel(interaction, title, fields, description, candidatureId) {
  const guild = interaction.guild;
  const s = getSettings(guild.id);
  const staffRole = guild.roles.cache.get(s.staffRoleId);
  let channel;
  try {
    channel = await guild.channels.create({
      name: `ticket-${slugify(interaction.user.username)}`, type: ChannelType.GuildText,
      parent: s.ticketCategoryId || null, topic: `ticket-owner:${interaction.user.id}`,
      permissionOverwrites: [
        { id: guild.roles.everyone.id, deny: [PermissionsBitField.Flags.ViewChannel] },
        { id: interaction.user.id, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages, PermissionsBitField.Flags.ReadMessageHistory] },
        { id: client.user.id, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages, PermissionsBitField.Flags.ReadMessageHistory, PermissionsBitField.Flags.ManageChannels, PermissionsBitField.Flags.EmbedLinks, PermissionsBitField.Flags.AttachFiles] },
        ...(staffRole ? [{ id: staffRole.id, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages, PermissionsBitField.Flags.ReadMessageHistory] }] : []),
      ],
    });
  } catch (err) {
    console.error('Erreur création ticket:', err);
    if (err.code === 50013) {
      throw new Error("Le bot n'a pas la permission \"Gérer les salons\" sur ce serveur (ou son rôle est trop bas dans la liste des rôles). Un membre du staff doit corriger ça dans Paramètres du serveur → Rôles.");
    }
    throw err;
  }
  const embed = new EmbedBuilder().setColor(COLOR).setTitle(title)
    .setDescription(description || `Bonjour <@${interaction.user.id}>, notre équipe d'assistance a été notifiée et va prendre en charge votre demande dans les plus brefs délais.\n\nVous pouvez utiliser les boutons d'action ci-dessous pour administrer ce salon.`)
    .addFields(...fields).setTimestamp();
  const buttons = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId(CLOSE_BUTTON_ID).setLabel('Fermer').setStyle(ButtonStyle.Danger).setEmoji('🔒'),
    new ButtonBuilder().setCustomId(CLAIM_BUTTON_ID).setLabel('Prendre en charge').setStyle(ButtonStyle.Success).setEmoji('🛡️'),
  );
  const buttons2 = new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId(SUBJECT_BUTTON_ID).setLabel('Sujet').setStyle(ButtonStyle.Secondary).setEmoji('⚙️'),
    new ButtonBuilder().setCustomId(ADD_BUTTON_ID).setLabel('Ajouter').setStyle(ButtonStyle.Success).setEmoji('👍'),
    new ButtonBuilder().setCustomId(REMOVE_BUTTON_ID).setLabel('Retirer').setStyle(ButtonStyle.Danger).setEmoji('👎'),
  );
  const components = [buttons, buttons2];
  if (candidatureId) {
    components.push(new ActionRowBuilder().addComponents(
      new ButtonBuilder().setCustomId(`candidature_accept:${candidatureId}`).setLabel('Accepter').setStyle(ButtonStyle.Success).setEmoji('✅'),
      new ButtonBuilder().setCustomId(`candidature_refuse:${candidatureId}`).setLabel('Refuser').setStyle(ButtonStyle.Danger).setEmoji('❌'),
    ));
  }
  await channel.send({ content: `${staffRole ? `<@&${staffRole.id}> ` : ''}<@${interaction.user.id}>`, embeds: [embed], components });
  return channel;
}

async function sendLog(guild, embed) {
  const channelId = getSettings(guild.id).logsChannelId;
  const channel = guild.channels.cache.get(channelId);
  if (channel) await channel.send({ embeds: [embed] }).catch(() => {});
}
async function logModeration(guild, action, targetUser, moderator, reason) {
  await sendLog(guild, new EmbedBuilder().setColor(COLOR).setTitle(`Modération — ${action}`)
    .addFields({ name: 'Membre', value: `<@${targetUser.id}>`, inline: true }, { name: 'Modérateur', value: `<@${moderator.id}>`, inline: true }, { name: 'Raison', value: reason || 'Non spécifiée' })
    .setTimestamp());
}

async function askAI(question) {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) return "L'IA n'est pas encore configurée (clé API manquante).";
  try {
    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages: [
          { role: 'system', content: 'Tu es un assistant utile et concis sur un serveur Discord. Réponds en français.' },
          { role: 'user', content: question },
        ],
        max_tokens: 500,
      }),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      console.error('Erreur IA (réponse API) :', JSON.stringify(data));
      return `Erreur IA : ${data?.error?.message || 'réponse invalide de l\'API'}.`;
    }
    const text = data?.choices?.[0]?.message?.content;
    if (!text) console.error('Erreur IA (pas de texte) :', JSON.stringify(data));
    return text ? text.slice(0, 1900) : "Je n'ai pas pu générer de réponse, réessaie avec une autre question.";
  } catch (err) {
    console.error('Erreur IA (exception) :', err);
    return "Une erreur est survenue en contactant l'IA.";
  }
}

client.once('ready', () => {
  console.log(`Connecté en tant que ${client.user.tag}`);
  // Sauvegarde automatique de tous les serveurs toutes les 24h (protection anti-raid)
  const autoBackup = () => {
    client.guilds.cache.forEach(guild => {
      try { createServerBackup(guild); } catch (err) { console.error('Erreur backup auto:', guild.id, err); }
    });
    console.log(`Sauvegarde automatique effectuée pour ${client.guilds.cache.size} serveur(s).`);
  };
  setTimeout(autoBackup, 60 * 1000); // première sauvegarde 1 min après le démarrage
  setInterval(autoBackup, 24 * 60 * 60 * 1000);
});

client.on('interactionCreate', async (interaction) => {
  try {
    if (!interaction.guildId) {
      if (interaction.isRepliable()) await interaction.reply({ content: "Cette commande ne fonctionne que sur un serveur Discord.", ephemeral: true }).catch(() => {});
      return;
    }
    if (!interaction.guild) {
      // Le bot vient peut-être de se reconnecter (réveil après inactivité) : on recharge le serveur concerné
      await client.guilds.fetch(interaction.guildId).catch(() => {});
    }
    if (!interaction.guild) {
      // Deuxième tentative après un court délai, au cas où Discord n'a pas encore fini de synchroniser
      await new Promise(r => setTimeout(r, 700));
      await client.guilds.fetch(interaction.guildId).catch(() => {});
    }
    if (!interaction.guild) {
      if (interaction.isRepliable()) await interaction.reply({ content: "Le bot vient de redémarrer, réessaie dans quelques secondes.", ephemeral: true }).catch(() => {});
      return;
    }
    const cmd = interaction.isChatInputCommand() ? interaction.commandName : null;

    // ===== TICKETS =====
    if (cmd === 'panel-ticket') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const categories = getTicketCategories(interaction.guild.id);
      if (categories.length === 0) {
        return interaction.reply({
          embeds: [new EmbedBuilder().setColor(COLOR_DANGER).setTitle('❌ Système de tickets non configuré')
            .setDescription("Aucune catégorie de ticket n'a été créée pour le moment.\n\nUtilise `/ticket-categorie-ajouter` pour créer ta première catégorie, puis relance `/panel-ticket`.")],
          ephemeral: true,
        });
      }
      const embed = new EmbedBuilder().setColor(COLOR)
        .setAuthor({ name: interaction.guild.name, iconURL: interaction.guild.iconURL() || undefined })
        .setThumbnail(BOT_ICON())
        .setTitle("🎫 ・ Centre d'Assistance & Recours")
        .setDescription("Choisis la catégorie correspondant à ta demande dans le menu ci-dessous.\n*Un salon privé sera créé instantanément pour toi.*")
        .addFields(categories.map(c => ({ name: `${c.emoji}  Tickets ${c.nom}`, value: c.desc })))
        .setFooter({ text: `${interaction.guild.name} • Support premium`, iconURL: BOT_ICON() })
        .setTimestamp();
      const select = new StringSelectMenuBuilder().setCustomId(PANEL_SELECT_ID).setPlaceholder("Choisissez le motif d'ouverture...")
        .addOptions(categories.map((c, idx) => ({ label: `Tickets ${c.nom}`, description: "Ouvrir un ticket d'assistance", emoji: c.emoji, value: `${idx}` })));
      await interaction.channel.send({ embeds: [embed], components: [new ActionRowBuilder().addComponents(select)] });
      return interaction.reply({ content: '✅ Panneau publié.', ephemeral: true });
    }
    if (cmd === 'ticket-categorie-ajouter') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const categories = getTicketCategories(interaction.guild.id);
      if (categories.length >= 20) return interaction.reply({ content: "Maximum de 20 catégories atteint.", ephemeral: true });
      const nom = interaction.options.getString('nom');
      const emoji = interaction.options.getString('emoji') || '🎫';
      const description = interaction.options.getString('description');
      categories.push({ nom, emoji, desc: `• ${description}` });
      saveSettings();
      return interaction.reply({ content: `✅ Catégorie **${nom}** ajoutée. Republie le panneau avec /panel-ticket pour la voir apparaître.`, ephemeral: true });
    }
    if (cmd === 'ticket-categorie-supprimer') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const s = getSettings(interaction.guild.id);
      const categories = getTicketCategories(interaction.guild.id);
      const nom = interaction.options.getString('nom');
      const before = categories.length;
      s.ticketCategories = categories.filter(c => c.nom.toLowerCase() !== nom.toLowerCase());
      saveSettings();
      return interaction.reply({ content: s.ticketCategories.length < before ? `✅ Catégorie **${nom}** supprimée.` : `Catégorie introuvable.`, ephemeral: true });
    }
    if (cmd === 'ticket-categorie-liste') {
      const categories = getTicketCategories(interaction.guild.id);
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('🎫 Catégories de tickets').setDescription(categories.map(c => `${c.emoji} **${c.nom}** — ${c.desc}`).join('\n\n'))], ephemeral: true });
    }
    // ===== CONFIGURATION (façon DraftBot) =====
    // ===== SAUVEGARDE DU SERVEUR (anti-raid) =====
    if (cmd === 'backup-creer') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.Administrator)) return interaction.reply({ content: "Permission refusée (Administrateur requis).", ephemeral: true });
      await interaction.deferReply({ ephemeral: true });
      const backup = createServerBackup(interaction.guild);
      return interaction.editReply({ content: `✅ Sauvegarde créée : ${backup.roles.length} rôle(s), ${backup.categories.length} catégorie(s), ${backup.channels.length} salon(s).` });
    }
    if (cmd === 'backup-restaurer') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.Administrator)) return interaction.reply({ content: "Permission refusée (Administrateur requis).", ephemeral: true });
      await interaction.deferReply({ ephemeral: true });
      const result = await restoreServerBackup(interaction.guild);
      if (result.error) return interaction.editReply({ content: `❌ ${result.error}` });
      return interaction.editReply({ content: `✅ Restauration terminée : ${result.rolesCreated} rôle(s), ${result.categoriesCreated} catégorie(s) et ${result.channelsCreated} salon(s) recréés (seuls les éléments manquants ont été recréés, rien n'a été dupliqué).` });
    }
    if (cmd === 'backup-info') {
      const backup = backups[interaction.guild.id];
      if (!backup) return interaction.reply({ content: "Aucune sauvegarde n'existe pour ce serveur. Utilise `/backup-creer`.", ephemeral: true });
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('💾 Dernière sauvegarde').addFields(
        { name: 'Date', value: backup.date, inline: true },
        { name: 'Rôles', value: `${backup.roles.length}`, inline: true },
        { name: 'Catégories', value: `${backup.categories.length}`, inline: true },
        { name: 'Salons', value: `${backup.channels.length}`, inline: true },
      )], ephemeral: true });
    }

    if (cmd === 'config') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const embed = new EmbedBuilder().setColor(COLOR).setThumbnail(BOT_ICON())
        .setTitle('⚙️ Choisissez une catégorie de commandes...');
      const select = new StringSelectMenuBuilder().setCustomId('config_main_menu').setPlaceholder('Sélectionne une catégorie').addOptions(
        { label: 'Tickets', description: 'Rôle staff, catégorie, types de tickets', emoji: '🎫', value: 'tickets' },
        { label: 'Bienvenue', description: 'Salon et rôle automatique', emoji: '👋', value: 'bienvenue' },
        { label: 'Niveaux', description: 'Salon des annonces de niveau', emoji: '📈', value: 'niveaux' },
        { label: 'Modération & Logs', description: 'Salon des logs', emoji: '🔨', value: 'logs' },
        { label: 'Règlement', description: 'Rôle donné après acceptation', emoji: '📜', value: 'reglement' },
        { label: 'Suggestions', description: 'Salon des suggestions', emoji: '💡', value: 'suggestions' },
      );
      return interaction.reply({ embeds: [embed], components: [new ActionRowBuilder().addComponents(select)], ephemeral: true });
    }
    if (interaction.isStringSelectMenu() && interaction.customId === 'config_main_menu') {
      const s = getSettings(interaction.guild.id);
      const value = interaction.values[0];
      const backRow = new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('config_back').setLabel('◀️ Retour').setStyle(ButtonStyle.Secondary));

      if (value === 'tickets') {
        const embed = new EmbedBuilder().setColor(COLOR).setTitle('🎫 Configuration — Tickets')
          .setDescription(
            `**Rôle staff :** ${s.staffRoleId ? `<@&${s.staffRoleId}>` : 'Non défini'}\n` +
            `**Catégorie tickets :** ${s.ticketCategoryId ? `<#${s.ticketCategoryId}>` : 'Non définie'}\n` +
            `**Types de tickets :** ${getTicketCategories(interaction.guild.id).length} configuré(s)\n\n` +
            `Utilise les menus ci-dessous pour choisir le rôle et la catégorie.\nPour gérer les types de tickets, utilise \`/ticket-categorie-ajouter\`, \`/ticket-categorie-supprimer\` et \`/ticket-categorie-liste\`.`
          );
        const roleSelect = new ActionRowBuilder().addComponents(new RoleSelectMenuBuilder().setCustomId('config_role_staff').setPlaceholder('Choisir le rôle staff'));
        const catSelect = new ActionRowBuilder().addComponents(new ChannelSelectMenuBuilder().setCustomId('config_channel_ticketcat').setPlaceholder('Choisir la catégorie tickets').addChannelTypes(ChannelType.GuildCategory));
        return interaction.update({ embeds: [embed], components: [roleSelect, catSelect, backRow] });
      }
      if (value === 'bienvenue') {
        const embed = new EmbedBuilder().setColor(COLOR).setTitle('👋 Configuration — Bienvenue')
          .setDescription(`**Salon de bienvenue :** ${s.welcomeChannelId ? `<#${s.welcomeChannelId}>` : 'Non défini'}\n**Rôle automatique :** ${s.civilianRoleId ? `<@&${s.civilianRoleId}>` : 'Non défini'}`);
        const chanSelect = new ActionRowBuilder().addComponents(new ChannelSelectMenuBuilder().setCustomId('config_channel_welcome').setPlaceholder('Choisir le salon de bienvenue').addChannelTypes(ChannelType.GuildText));
        const roleSelect = new ActionRowBuilder().addComponents(new RoleSelectMenuBuilder().setCustomId('config_role_civil').setPlaceholder('Choisir le rôle automatique'));
        return interaction.update({ embeds: [embed], components: [chanSelect, roleSelect, backRow] });
      }
      if (value === 'niveaux') {
        const embed = new EmbedBuilder().setColor(COLOR).setTitle('📈 Configuration — Niveaux')
          .setDescription(`**Salon des annonces de niveau :** ${s.levelUpChannelId ? `<#${s.levelUpChannelId}>` : "Salon où le membre écrit (par défaut)"}\n\nPour les récompenses de rôle par niveau, utilise \`/niveau recompense\`.`);
        const chanSelect = new ActionRowBuilder().addComponents(new ChannelSelectMenuBuilder().setCustomId('config_channel_levelup').setPlaceholder('Choisir le salon de niveau').addChannelTypes(ChannelType.GuildText));
        return interaction.update({ embeds: [embed], components: [chanSelect, backRow] });
      }
      if (value === 'logs') {
        const embed = new EmbedBuilder().setColor(COLOR).setTitle('🔨 Configuration — Modération & Logs')
          .setDescription(`**Salon des logs :** ${s.logsChannelId ? `<#${s.logsChannelId}>` : 'Non défini'}`);
        const chanSelect = new ActionRowBuilder().addComponents(new ChannelSelectMenuBuilder().setCustomId('config_channel_logs').setPlaceholder('Choisir le salon de logs').addChannelTypes(ChannelType.GuildText));
        return interaction.update({ embeds: [embed], components: [chanSelect, backRow] });
      }
      if (value === 'reglement') {
        const embed = new EmbedBuilder().setColor(COLOR).setTitle('📜 Configuration — Règlement')
          .setDescription(`**Rôle donné après acceptation :** ${s.reglementRoleId ? `<@&${s.reglementRoleId}>` : 'Non défini'}\n\nUtilise \`/set-reglement\` pour changer le texte, puis \`/panel-reglement\` pour le publier avec un bouton d'acceptation.`);
        const roleSelect = new ActionRowBuilder().addComponents(new RoleSelectMenuBuilder().setCustomId('config_role_reglement').setPlaceholder('Choisir le rôle à donner'));
        return interaction.update({ embeds: [embed], components: [roleSelect, backRow] });
      }
      if (value === 'suggestions') {
        const embed = new EmbedBuilder().setColor(COLOR).setTitle('💡 Configuration — Suggestions')
          .setDescription(`**Salon des suggestions :** ${s.suggestionsChannelId ? `<#${s.suggestionsChannelId}>` : 'Salon courant (par défaut)'}`);
        const chanSelect = new ActionRowBuilder().addComponents(new ChannelSelectMenuBuilder().setCustomId('config_channel_suggestions').setPlaceholder('Choisir le salon de suggestions').addChannelTypes(ChannelType.GuildText));
        return interaction.update({ embeds: [embed], components: [chanSelect, backRow] });
      }
    }
    if (interaction.isButton() && interaction.customId === 'config_back') {
      const embed = new EmbedBuilder().setColor(COLOR).setThumbnail(BOT_ICON()).setTitle('⚙️ Choisissez une catégorie de commandes...');
      const select = new StringSelectMenuBuilder().setCustomId('config_main_menu').setPlaceholder('Sélectionne une catégorie').addOptions(
        { label: 'Tickets', description: 'Rôle staff, catégorie, types de tickets', emoji: '🎫', value: 'tickets' },
        { label: 'Bienvenue', description: 'Salon et rôle automatique', emoji: '👋', value: 'bienvenue' },
        { label: 'Niveaux', description: 'Salon des annonces de niveau', emoji: '📈', value: 'niveaux' },
        { label: 'Modération & Logs', description: 'Salon des logs', emoji: '🔨', value: 'logs' },
        { label: 'Règlement', description: 'Rôle donné après acceptation', emoji: '📜', value: 'reglement' },
        { label: 'Suggestions', description: 'Salon des suggestions', emoji: '💡', value: 'suggestions' },
      );
      return interaction.update({ embeds: [embed], components: [new ActionRowBuilder().addComponents(select)] });
    }
    if (interaction.isRoleSelectMenu() && interaction.customId.startsWith('config_role_')) {
      const s = getSettings(interaction.guild.id);
      const role = interaction.roles.first();
      const map = { config_role_staff: 'staffRoleId', config_role_civil: 'civilianRoleId', config_role_reglement: 'reglementRoleId' };
      s[map[interaction.customId]] = role.id;
      saveSettings();
      return interaction.reply({ content: `✅ ${role} enregistré.`, ephemeral: true });
    }
    if (interaction.isChannelSelectMenu() && interaction.customId.startsWith('config_channel_')) {
      const s = getSettings(interaction.guild.id);
      const channel = interaction.channels.first();
      const map = { config_channel_ticketcat: 'ticketCategoryId', config_channel_welcome: 'welcomeChannelId', config_channel_levelup: 'levelUpChannelId', config_channel_logs: 'logsChannelId', config_channel_suggestions: 'suggestionsChannelId' };
      s[map[interaction.customId]] = channel.id;
      saveSettings();
      return interaction.reply({ content: `✅ ${channel} enregistré.`, ephemeral: true });
    }

    // ===== CENTRE DE CONTRÔLE =====
    if (cmd === 'panel') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const embed = new EmbedBuilder().setColor(COLOR)
        .setAuthor({ name: interaction.guild.name, iconURL: interaction.guild.iconURL() || undefined })
        .setThumbnail(BOT_ICON())
        .setTitle('🤖 ・ Centre de contrôle')
        .setDescription("Bienvenue dans le tableau de bord d'administration. Sélectionne une catégorie ci-dessous.")
        .setFooter({ text: `${interaction.guild.name} • Panneau premium`, iconURL: BOT_ICON() })
        .setTimestamp();
      const row1 = new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId('panel_members').setLabel('Gérer les membres').setEmoji('👥').setStyle(ButtonStyle.Primary),
        new ButtonBuilder().setCustomId('panel_tickets').setLabel('Voir les tickets').setEmoji('🎫').setStyle(ButtonStyle.Primary),
        new ButtonBuilder().setCustomId('panel_stats').setLabel('Statistiques').setEmoji('📊').setStyle(ButtonStyle.Primary),
        new ButtonBuilder().setCustomId('panel_announce').setLabel('Créer une annonce').setEmoji('📢').setStyle(ButtonStyle.Success),
      );
      const row2 = new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId('panel_applications').setLabel('Candidatures').setEmoji('📄').setStyle(ButtonStyle.Secondary),
        new ButtonBuilder().setCustomId('panel_sanctions').setLabel('Sanctions').setEmoji('⚖️').setStyle(ButtonStyle.Danger),
        new ButtonBuilder().setCustomId('panel_reports').setLabel('Rapports').setEmoji('📝').setStyle(ButtonStyle.Secondary),
        new ButtonBuilder().setCustomId('panel_settings').setLabel('Paramètres').setEmoji('⚙️').setStyle(ButtonStyle.Secondary),
      );
      return interaction.reply({ embeds: [embed], components: [row1, row2] });
    }

    if (interaction.isButton() && interaction.customId.startsWith('panel_')) {
      const action = interaction.customId;
      const guild = interaction.guild;
      const s = getSettings(guild.id);

      if (action === 'panel_members') {
        const embed = new EmbedBuilder().setColor(COLOR).setTitle('👥 ・ Gestion des membres')
          .setDescription('Sélectionne un membre ci-dessous pour voir ses infos et agir sur lui (rôles, sanctions, casier).')
          .addFields(
            { name: 'Total membres', value: `${guild.memberCount}`, inline: true },
            { name: 'Bots', value: `${guild.members.cache.filter(m => m.user.bot).size}`, inline: true },
          );
        const userSelect = new ActionRowBuilder().addComponents(new UserSelectMenuBuilder().setCustomId('panel_select_member').setPlaceholder('Choisir un membre'));
        return interaction.reply({ embeds: [embed], components: [userSelect], ephemeral: true });
      }

      if (action === 'panel_tickets') {
        const cat = guild.channels.cache.get(s.ticketCategoryId);
        const open = cat ? guild.channels.cache.filter(ch => ch.parentId === s.ticketCategoryId) : null;
        const embed = new EmbedBuilder().setColor(COLOR).setTitle('🎫 ・ Tickets ouverts')
          .setFooter({ text: "Affiche tous les salons de la catégorie configurée, y compris ceux créés par d'autres bots si elle est partagée." });
        if (!cat) embed.setDescription("Aucune catégorie de tickets configurée. Utilise `/set-ticketcategorie` ou `/config` → Tickets.");
        else if (open.size === 0) embed.setDescription('Aucun ticket ouvert actuellement.');
        else embed.setDescription(open.map(ch => `${ch}`).join('\n'));
        return interaction.reply({ embeds: [embed], ephemeral: true });
      }

      if (action === 'panel_stats') {
        const prefix = `${guild.id}:`;
        const totalSanctions = Object.entries(casiers).filter(([k]) => k.startsWith(prefix)).reduce((sum, [, r]) => sum + r.history.length, 0);
        const topLevels = Object.entries(levels).filter(([k]) => k.startsWith(prefix)).sort((a, b) => (b[1].level - a[1].level) || (b[1].xp - a[1].xp)).slice(0, 3);
        const cat = guild.channels.cache.get(s.ticketCategoryId);
        const openTickets = cat ? guild.channels.cache.filter(ch => ch.parentId === s.ticketCategoryId && ch.topic?.startsWith('ticket-owner:')).size : 0;
        const topLines = topLevels.length ? topLevels.map(([k, d], i) => `**${i + 1}.** <@${k.split(':')[1]}> — Niveau ${d.level}`).join('\n') : 'Aucune donnée';
        const embed = new EmbedBuilder().setColor(COLOR).setTitle('📊 ・ Statistiques du serveur')
          .addFields(
            { name: 'Membres', value: `${guild.memberCount}`, inline: true },
            { name: 'Tickets ouverts', value: `${openTickets}`, inline: true },
            { name: 'Sanctions totales', value: `${totalSanctions}`, inline: true },
            { name: '🏆 Top niveaux', value: topLines },
          );
        return interaction.reply({ embeds: [embed], ephemeral: true });
      }

      if (action === 'panel_announce') {
        const modal = new ModalBuilder().setCustomId('panel_announce_modal').setTitle('Créer une annonce');
        modal.addComponents(
          new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('titre').setLabel('Titre').setStyle(TextInputStyle.Short).setRequired(true)),
          new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('message').setLabel('Message').setStyle(TextInputStyle.Paragraph).setRequired(true)),
        );
        return interaction.showModal(modal);
      }

      if (action === 'panel_applications') {
        const cat = guild.channels.cache.get(s.ticketCategoryId);
        const open = cat ? guild.channels.cache.filter(ch => ch.parentId === s.ticketCategoryId && ch.topic?.startsWith('ticket-owner:')) : null;
        const embed = new EmbedBuilder().setColor(COLOR).setTitle('📄 ・ Candidatures en cours')
          .setDescription(open && open.size > 0 ? open.map(ch => `${ch}`).join('\n') : "Aucune candidature ouverte.\nUtilise `/recrutement` ou `/staff` pour candidater.");
        return interaction.reply({ embeds: [embed], ephemeral: true });
      }

      if (action === 'panel_sanctions') {
        const modal = new ModalBuilder().setCustomId('panel_sanctions_modal').setTitle('Consulter un casier');
        modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('membre').setLabel('ID ou mention du membre').setStyle(TextInputStyle.Short).setRequired(true)));
        return interaction.showModal(modal);
      }

      if (action === 'panel_reports') {
        const guildReports = rapports.filter(r => r.guildId === guild.id).slice(-5).reverse();
        const embed = new EmbedBuilder().setColor(COLOR).setTitle('📝 ・ Derniers rapports')
          .setDescription(guildReports.length ? guildReports.map(r => `**${r.service}** — <@${r.auteur}> *(${r.date})*\n${r.description.slice(0, 100)}`).join('\n\n') : 'Aucun rapport enregistré.');
        const row = new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('panel_report_create').setLabel('Créer un rapport').setEmoji('📝').setStyle(ButtonStyle.Success));
        return interaction.reply({ embeds: [embed], components: [row], ephemeral: true });
      }

      if (action === 'panel_report_create') {
        const modal = new ModalBuilder().setCustomId('panel_report_modal').setTitle('Créer un rapport');
        modal.addComponents(
          new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('service').setLabel('Service (Police, SAMU, Justice...)').setStyle(TextInputStyle.Short).setRequired(true)),
          new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('description').setLabel('Description du rapport').setStyle(TextInputStyle.Paragraph).setRequired(true)),
        );
        return interaction.showModal(modal);
      }

      if (action === 'panel_settings') {
        const embed = new EmbedBuilder().setColor(COLOR).setTitle('⚙️ ・ Paramètres actuels')
          .addFields(
            { name: 'Rôle staff', value: s.staffRoleId ? `<@&${s.staffRoleId}>` : 'Non défini', inline: true },
            { name: 'Catégorie tickets', value: s.ticketCategoryId ? `<#${s.ticketCategoryId}>` : 'Non définie', inline: true },
            { name: 'Salon logs', value: s.logsChannelId ? `<#${s.logsChannelId}>` : 'Non défini', inline: true },
            { name: 'Salon bienvenue', value: s.welcomeChannelId ? `<#${s.welcomeChannelId}>` : 'Non défini', inline: true },
            { name: 'Rôle civil auto', value: s.civilianRoleId ? `<@&${s.civilianRoleId}>` : 'Non défini', inline: true },
          )
          .setDescription("Utilise `/config` pour tout modifier facilement.");
        return interaction.reply({ embeds: [embed], ephemeral: true });
      }
    }

    // ----- Gestion de membre depuis le Centre de contrôle -----
    if (interaction.isUserSelectMenu() && interaction.customId === 'panel_select_member') {
      const member = interaction.members.first();
      const embed = new EmbedBuilder().setColor(COLOR).setThumbnail(member.user.displayAvatarURL())
        .setTitle(`👤 ${member.user.username}`)
        .addFields(
          { name: 'A rejoint le', value: `<t:${Math.floor(member.joinedTimestamp / 1000)}:D>`, inline: true },
          { name: 'Compte créé', value: `<t:${Math.floor(member.user.createdTimestamp / 1000)}:D>`, inline: true },
          { name: 'Rôles', value: member.roles.cache.filter(r => r.id !== interaction.guild.id).map(r => `${r}`).join(', ') || 'Aucun' },
        );
      const actionRow = new ActionRowBuilder().addComponents(
        new ButtonBuilder().setCustomId(`panel_maction:warn:${member.id}`).setLabel('Avertir').setEmoji('⚠️').setStyle(ButtonStyle.Secondary),
        new ButtonBuilder().setCustomId(`panel_maction:kick:${member.id}`).setLabel('Expulser').setEmoji('👢').setStyle(ButtonStyle.Danger),
        new ButtonBuilder().setCustomId(`panel_maction:ban:${member.id}`).setLabel('Bannir').setEmoji('🔨').setStyle(ButtonStyle.Danger),
        new ButtonBuilder().setCustomId(`panel_maction:casier:${member.id}`).setLabel('Voir le casier').setEmoji('📁').setStyle(ButtonStyle.Secondary),
      );
      const roleSelect = new ActionRowBuilder().addComponents(
        new RoleSelectMenuBuilder().setCustomId(`panel_member_roles:${member.id}`).setPlaceholder('Modifier les rôles de ce membre')
          .setMinValues(0).setMaxValues(25)
          .setDefaultRoles(member.roles.cache.filter(r => r.id !== interaction.guild.id).map(r => r.id))
      );
      return interaction.reply({ embeds: [embed], components: [actionRow, roleSelect], ephemeral: true });
    }

    if (interaction.isRoleSelectMenu() && interaction.customId.startsWith('panel_member_roles:')) {
      const userId = interaction.customId.split(':')[1];
      const member = await interaction.guild.members.fetch(userId).catch(() => null);
      if (!member) return interaction.reply({ content: 'Membre introuvable.', ephemeral: true });
      try {
        await member.roles.set(interaction.values);
        return interaction.reply({ content: `✅ Rôles de <@${userId}> mis à jour.`, ephemeral: true });
      } catch (err) {
        console.error('Erreur modification rôles panel:', err);
        return interaction.reply({ content: "❌ Impossible de modifier certains rôles (rôle du bot trop bas, ou rôle géré automatiquement par Discord).", ephemeral: true });
      }
    }

    if (interaction.isButton() && interaction.customId.startsWith('panel_maction:')) {
      const [, actionType, userId] = interaction.customId.split(':');
      if (actionType === 'casier') {
        const rec = getRecord(key(interaction.guild.id, userId));
        const embed = new EmbedBuilder().setColor(COLOR).setTitle(`📁 Casier — <@${userId}>`)
          .addFields(
            { name: 'Warns', value: `${countType(rec, 'warn')}`, inline: true },
            { name: 'Mutes/Timeouts', value: `${countType(rec, 'mute') + countType(rec, 'timeout')}`, inline: true },
            { name: 'Kicks', value: `${countType(rec, 'kick')}`, inline: true },
            { name: 'Bans', value: `${countType(rec, 'ban') + countType(rec, 'tempban') + countType(rec, 'softban')}`, inline: true },
          );
        return interaction.reply({ embeds: [embed], ephemeral: true });
      }
      const modal = new ModalBuilder().setCustomId(`panel_maction_modal:${actionType}:${userId}`).setTitle(
        actionType === 'warn' ? 'Avertir ce membre' : actionType === 'kick' ? 'Expulser ce membre' : 'Bannir ce membre'
      );
      modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('raison').setLabel('Raison').setStyle(TextInputStyle.Paragraph).setRequired(true).setMaxLength(500)));
      return interaction.showModal(modal);
    }

    if (interaction.isModalSubmit() && interaction.customId.startsWith('panel_maction_modal:')) {
      const [, actionType, userId] = interaction.customId.split(':');
      const raison = interaction.fields.getTextInputValue('raison');
      const member = await interaction.guild.members.fetch(userId).catch(() => null);
      if (!member) return interaction.reply({ content: 'Membre introuvable.', ephemeral: true });
      if (actionType === 'warn') {
        addSanction(key(interaction.guild.id, userId), 'warn', raison, interaction.user.tag);
        await logModeration(interaction.guild, 'Avertissement', member.user, interaction.user, raison);
        member.user.send(`⚠️ Averti sur **${interaction.guild.name}**. Raison : ${raison}`).catch(() => {});
        return interaction.reply({ content: `⚠️ <@${userId}> a été averti.`, ephemeral: true });
      }
      if (actionType === 'kick') {
        if (!member.kickable) return interaction.reply({ content: 'Impossible d\'expulser ce membre.', ephemeral: true });
        await member.kick(raison);
        addSanction(key(interaction.guild.id, userId), 'kick', raison, interaction.user.tag);
        await logModeration(interaction.guild, 'Expulsion', member.user, interaction.user, raison);
        return interaction.reply({ content: `👢 <@${userId}> a été expulsé.`, ephemeral: true });
      }
      if (actionType === 'ban') {
        if (!member.bannable) return interaction.reply({ content: 'Impossible de bannir ce membre.', ephemeral: true });
        await member.ban({ reason: raison });
        addSanction(key(interaction.guild.id, userId), 'ban', raison, interaction.user.tag);
        await logModeration(interaction.guild, 'Bannissement', member.user, interaction.user, raison);
        return interaction.reply({ content: `🔨 <@${userId}> a été banni.`, ephemeral: true });
      }
    }

    if (interaction.isModalSubmit() && interaction.customId === 'panel_announce_modal') {
      const titre = interaction.fields.getTextInputValue('titre');
      const message = interaction.fields.getTextInputValue('message');
      const embed = new EmbedBuilder().setColor(COLOR).setAuthor({ name: interaction.guild.name, iconURL: interaction.guild.iconURL() || undefined })
        .setTitle(`📢 ${titre}`).setDescription(message).setThumbnail(BOT_ICON()).setFooter({ text: `Annoncé par ${interaction.user.username}`, iconURL: interaction.user.displayAvatarURL() }).setTimestamp();
      await interaction.channel.send({ embeds: [embed] });
      return interaction.reply({ content: '✅ Annonce publiée.', ephemeral: true });
    }

    if (interaction.isModalSubmit() && interaction.customId === 'panel_sanctions_modal') {
      const raw = interaction.fields.getTextInputValue('membre');
      const userId = raw.replace(/[<@!>]/g, '').trim();
      const rec = getRecord(key(interaction.guild.id, userId));
      const embed = new EmbedBuilder().setColor(COLOR).setTitle(`⚖️ Casier — <@${userId}>`)
        .addFields(
          { name: 'Warns', value: `${countType(rec, 'warn')}`, inline: true },
          { name: 'Sanctions totales', value: `${rec.history.length}`, inline: true },
        );
      if (rec.history.length > 0) {
        const last = rec.history[rec.history.length - 1];
        embed.addFields({ name: 'Dernière sanction', value: `${last.type} — ${last.raison} *(${last.date})*` });
      }
      return interaction.reply({ embeds: [embed], ephemeral: true });
    }

    if (interaction.isModalSubmit() && interaction.customId === 'panel_report_modal') {
      const service = interaction.fields.getTextInputValue('service');
      const description = interaction.fields.getTextInputValue('description');
      const entry = { id: genId(), guildId: interaction.guild.id, auteur: interaction.user.id, service, description, date: new Date().toLocaleString('fr-FR') };
      rapports.push(entry);
      saveJson(RAPPORTS_PATH, rapports);
      const embed = new EmbedBuilder().setColor(COLOR).setTitle('📝 Nouveau rapport').setAuthor({ name: interaction.user.username, iconURL: interaction.user.displayAvatarURL() })
        .addFields({ name: 'Service', value: service, inline: true }, { name: 'Date', value: entry.date, inline: true }, { name: 'Description', value: description }).setTimestamp();
      await sendLog(interaction.guild, embed);
      return interaction.reply({ content: '✅ Rapport enregistré et envoyé dans le salon de logs.', ephemeral: true });
    }

    if (cmd === 'close') {
      if (!interaction.channel.topic?.startsWith('ticket-owner:')) return interaction.reply({ content: "Utilisable seulement dans un ticket.", ephemeral: true });
      return closeTicket(interaction);
    }
    if (interaction.isStringSelectMenu() && interaction.customId === PANEL_SELECT_ID) {
      const existing = await findExistingTicket(interaction.guild, interaction.user.id);
      if (existing) return interaction.reply({ content: `Ticket déjà ouvert : <#${existing.id}>`, ephemeral: true });
      const idx = parseInt(interaction.values[0], 10);
      const categories = getTicketCategories(interaction.guild.id);
      const category = categories[idx]?.nom || 'Support';
      const modal = new ModalBuilder().setCustomId(`${MODAL_ID}:${encodeURIComponent(category)}`).setTitle(`Ticket — ${category}`);
      modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('details').setLabel('Décris ta demande').setStyle(TextInputStyle.Paragraph).setRequired(true).setMaxLength(1000)));
      return interaction.showModal(modal);
    }
    if (interaction.isModalSubmit() && interaction.customId.startsWith(MODAL_ID)) {
      await interaction.deferReply({ ephemeral: true });
      const category = decodeURIComponent(interaction.customId.split(':')[1]);
      const details = interaction.fields.getTextInputValue('details');
      const channel = await createTicketChannel(interaction, `🎟️ Ticket d'Assistance : ${category}`, [{ name: 'Détails', value: details }]);
      return interaction.editReply({ content: `Ticket créé : <#${channel.id}>` });
    }
    if (interaction.isModalSubmit() && interaction.customId.startsWith('form_modal:')) {
      await interaction.deferReply({ ephemeral: true });
      const formType = interaction.customId.split(':')[1];
      const values = interaction.fields.fields.map(f => ({ name: f.customId, value: interaction.fields.getTextInputValue(f.customId) }));
      const titles = { recrutement: 'Candidature — Recrutement', staff: 'Candidature — Staff', signalement: 'Signalement', gang: 'Création de gang', entreprise: "Création d'entreprise" };
      const isCandidature = formType === 'recrutement' || formType === 'staff';
      let candidatureId = null;
      if (isCandidature) {
        candidatureId = genId();
        candidatures.push({ id: candidatureId, type: formType, userId: interaction.user.id, guildId: interaction.guild.id, channelId: null, statut: 'en_attente', date: new Date().toLocaleString('fr-FR') });
      }
      const channel = await createTicketChannel(interaction, titles[formType] || 'Formulaire', values.map(v => ({ name: v.name, value: v.value })), null, candidatureId);
      if (isCandidature) {
        const c = candidatures.find(x => x.id === candidatureId);
        if (c) { c.channelId = channel.id; saveJson(CANDIDATURES_PATH, candidatures); }
      }
      return interaction.editReply({ content: `Demande envoyée : <#${channel.id}>` });
    }
    if (interaction.isButton() && interaction.customId.startsWith('candidature_accept:')) {
      const s = getSettings(interaction.guild.id);
      const staffRole = interaction.guild.roles.cache.get(s.staffRoleId);
      if (staffRole && !interaction.member.roles.cache.has(staffRole.id)) return interaction.reply({ content: "Réservé au staff.", ephemeral: true });
      const id = interaction.customId.split(':')[1];
      const c = candidatures.find(x => x.id === id);
      if (!c) return interaction.reply({ content: 'Candidature introuvable.', ephemeral: true });
      c.statut = 'acceptee'; saveJson(CANDIDATURES_PATH, candidatures);
      await interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR_SUCCESS).setDescription(`✅ Candidature **acceptée** par <@${interaction.user.id}>.`)] });
      const candidat = await client.users.fetch(c.userId).catch(() => null);
      if (candidat) candidat.send(`🎉 Ta candidature sur **${interaction.guild.name}** a été **acceptée** !`).catch(() => {});
      return;
    }
    if (interaction.isButton() && interaction.customId.startsWith('candidature_refuse:')) {
      const s = getSettings(interaction.guild.id);
      const staffRole = interaction.guild.roles.cache.get(s.staffRoleId);
      if (staffRole && !interaction.member.roles.cache.has(staffRole.id)) return interaction.reply({ content: "Réservé au staff.", ephemeral: true });
      const id = interaction.customId.split(':')[1];
      const c = candidatures.find(x => x.id === id);
      if (!c) return interaction.reply({ content: 'Candidature introuvable.', ephemeral: true });
      c.statut = 'refusee'; saveJson(CANDIDATURES_PATH, candidatures);
      await interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR_DANGER).setDescription(`❌ Candidature **refusée** par <@${interaction.user.id}>.`)] });
      const candidat = await client.users.fetch(c.userId).catch(() => null);
      if (candidat) candidat.send(`Ta candidature sur **${interaction.guild.name}** a été **refusée**. N'hésite pas à retenter plus tard.`).catch(() => {});
      return;
    }
    if (interaction.isButton() && interaction.customId === CLAIM_BUTTON_ID) {
      const staffRole = interaction.guild.roles.cache.get(getSettings(interaction.guild.id).staffRoleId);
      if (staffRole && !interaction.member.roles.cache.has(staffRole.id)) return interaction.reply({ content: "Réservé au staff.", ephemeral: true });
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setDescription(`🖐️ Réclamé par <@${interaction.user.id}>.`)] });
    }
    if (interaction.isButton() && interaction.customId === CLOSE_BUTTON_ID) return closeTicket(interaction);

    // Boutons de gestion du ticket : Sujet / Ajouter / Retirer
    if (interaction.isButton() && [SUBJECT_BUTTON_ID, ADD_BUTTON_ID, REMOVE_BUTTON_ID].includes(interaction.customId)) {
      const staffRole = interaction.guild.roles.cache.get(getSettings(interaction.guild.id).staffRoleId);
      if (staffRole && !interaction.member.roles.cache.has(staffRole.id)) return interaction.reply({ content: "Réservé au staff.", ephemeral: true });

      if (interaction.customId === SUBJECT_BUTTON_ID) {
        const modal = new ModalBuilder().setCustomId(SUBJECT_MODAL_ID).setTitle('Modifier le sujet du ticket');
        modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('sujet').setLabel('Nouveau sujet').setStyle(TextInputStyle.Short).setRequired(true).setMaxLength(80)));
        return interaction.showModal(modal);
      }
      if (interaction.customId === ADD_BUTTON_ID) {
        const modal = new ModalBuilder().setCustomId(ADD_MODAL_ID).setTitle('Ajouter un membre au ticket');
        modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('membre').setLabel('ID ou mention du membre').setStyle(TextInputStyle.Short).setRequired(true)));
        return interaction.showModal(modal);
      }
      if (interaction.customId === REMOVE_BUTTON_ID) {
        const modal = new ModalBuilder().setCustomId(REMOVE_MODAL_ID).setTitle('Retirer un membre du ticket');
        modal.addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('membre').setLabel('ID ou mention du membre').setStyle(TextInputStyle.Short).setRequired(true)));
        return interaction.showModal(modal);
      }
    }

    if (interaction.isModalSubmit() && interaction.customId === SUBJECT_MODAL_ID) {
      const sujet = interaction.fields.getTextInputValue('sujet');
      await interaction.channel.setName(`ticket-${slugify(sujet)}`).catch(() => {});
      await interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setDescription(`⚙️ Sujet mis à jour : **${sujet}**`)] });
      return;
    }
    if (interaction.isModalSubmit() && (interaction.customId === ADD_MODAL_ID || interaction.customId === REMOVE_MODAL_ID)) {
      const raw = interaction.fields.getTextInputValue('membre');
      const userId = raw.replace(/[<@!>]/g, '').trim();
      const member = await interaction.guild.members.fetch(userId).catch(() => null);
      if (!member) return interaction.reply({ content: "Membre introuvable. Vérifie l'ID ou la mention.", ephemeral: true });
      if (interaction.customId === ADD_MODAL_ID) {
        await interaction.channel.permissionOverwrites.edit(member.id, { ViewChannel: true, SendMessages: true, ReadMessageHistory: true });
        return interaction.reply({ content: `👍 <@${member.id}> a été ajouté au ticket.` });
      } else {
        await interaction.channel.permissionOverwrites.delete(member.id).catch(() => {});
        return interaction.reply({ content: `👎 <@${member.id}> a été retiré du ticket.` });
      }
    }

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
      const guildEntreprises = entreprises.filter(e => e.guildId === interaction.guild.id);
      if (guildEntreprises.length === 0) return interaction.reply({ content: "Aucune entreprise enregistrée." });
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('🏢 Entreprises').setDescription(guildEntreprises.map((e, i) => `**${i + 1}. ${e.nom}** — ${e.secteur} (<@${e.proprietaire}>)`).join('\n'))] });
    }
    if (cmd === 'entreprise-ajouter') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const nom = interaction.options.getString('nom'), secteur = interaction.options.getString('secteur'), proprietaire = interaction.options.getUser('proprietaire');
      entreprises.push({ nom, secteur, proprietaire: proprietaire.id, guildId: interaction.guild.id });
      saveJson(ENTREPRISES_PATH, entreprises);
      return interaction.reply({ content: `✅ **${nom}** ajoutée.` });
    }

    // ===== SANCTIONS =====
    if (cmd === 'kick') {
      const target = interaction.options.getMember('membre'); const reason = interaction.options.getString('raison') || 'Non spécifiée';
      if (!target) return interaction.reply({ content: 'Introuvable.', ephemeral: true });
      if (!target.kickable) return interaction.reply({ content: 'Impossible d\'expulser ce membre.', ephemeral: true });
      await target.kick(reason);
      addSanction(key(interaction.guild.id, target.id), 'kick', reason, interaction.user.tag);
      await interaction.reply({ content: `👢 <@${target.id}> expulsé. Raison : ${reason}` });
      await logModeration(interaction.guild, 'Expulsion', target.user, interaction.user, reason);
      return;
    }
    if (cmd === 'ban') {
      const target = interaction.options.getMember('membre'); const reason = interaction.options.getString('raison') || 'Non spécifiée';
      if (!target) return interaction.reply({ content: 'Introuvable.', ephemeral: true });
      if (!target.bannable) return interaction.reply({ content: 'Impossible de bannir ce membre.', ephemeral: true });
      await target.ban({ reason });
      addSanction(key(interaction.guild.id, target.id), 'ban', reason, interaction.user.tag);
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
      addSanction(key(interaction.guild.id, userId), 'tempban', `${reason} (${heures}h)`, interaction.user.tag);
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
      addSanction(key(interaction.guild.id, userId), 'unban', 'Débanni', interaction.user.tag);
      await interaction.reply({ content: `✅ <@${userId}> débanni.` });
      return;
    }
    if (cmd === 'softban') {
      const target = interaction.options.getMember('membre'); const reason = interaction.options.getString('raison') || 'Non spécifiée';
      if (!target) return interaction.reply({ content: 'Introuvable.', ephemeral: true });
      await target.ban({ reason, deleteMessageSeconds: 7 * 24 * 60 * 60 });
      await interaction.guild.members.unban(target.id, 'Softban').catch(() => {});
      addSanction(key(interaction.guild.id, target.id), 'softban', reason, interaction.user.tag);
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
      addSanction(key(interaction.guild.id, target.id), cmd, `${reason} (${minutes} min)`, interaction.user.tag);
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
      const entry = addSanction(key(interaction.guild.id, target.id), 'warn', reason, interaction.user.tag);
      await interaction.reply({ content: `⚠️ <@${target.id}> averti (ID: \`${entry.id}\`). Raison : ${reason}` });
      await logModeration(interaction.guild, 'Avertissement', target, interaction.user, reason);
      target.send(`⚠️ Averti sur **${interaction.guild.name}**. Raison : ${reason}`).catch(() => {});
      return;
    }
    if (cmd === 'warnings') {
      const target = interaction.options.getUser('membre') || interaction.user;
      const rec = getRecord(key(interaction.guild.id, target.id)); const warns = rec.history.filter(h => h.type === 'warn');
      if (warns.length === 0) return interaction.reply({ content: `<@${target.id}> n'a aucun avertissement.` });
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle(`⚠️ Avertissements — ${target.username}`).setDescription(warns.map(w => `\`${w.id}\` — ${w.raison} *(${w.date}, par ${w.moderateur})*`).join('\n'))] });
    }
    if (cmd === 'unwarn') {
      const target = interaction.options.getUser('membre'); const id = interaction.options.getString('id');
      const rec = getRecord(key(interaction.guild.id, target.id)); const before = rec.history.length;
      rec.history = rec.history.filter(h => !(h.type === 'warn' && h.id === id));
      saveJson(CASIERS_PATH, casiers);
      return interaction.reply({ content: rec.history.length < before ? `✅ Avertissement \`${id}\` retiré.` : `Aucun avertissement avec cet ID.` });
    }
    if (cmd === 'clearwarns') {
      const target = interaction.options.getUser('membre');
      const rec = getRecord(key(interaction.guild.id, target.id)); rec.history = rec.history.filter(h => h.type !== 'warn');
      saveJson(CASIERS_PATH, casiers);
      return interaction.reply({ content: `✅ Tous les avertissements de <@${target.id}> supprimés.` });
    }
    if (cmd === 'note') {
      const target = interaction.options.getUser('membre'); const texte = interaction.options.getString('texte');
      const rec = getRecord(key(interaction.guild.id, target.id)); const entry = { id: genId(), texte, moderateur: interaction.user.tag, date: new Date().toLocaleString('fr-FR') };
      rec.notes.push(entry); saveJson(CASIERS_PATH, casiers);
      return interaction.reply({ content: `📝 Note ajoutée (ID: \`${entry.id}\`).`, ephemeral: true });
    }
    if (cmd === 'notes') {
      const target = interaction.options.getUser('membre');
      const rec = getRecord(key(interaction.guild.id, target.id));
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
      const rec = getRecord(key(interaction.guild.id, target.id));
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
      const prefix = `${interaction.guild.id}:`;
      for (const k in casiers) {
        if (!k.startsWith(prefix)) continue;
        for (const h of casiers[k].history) {
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
    if (cmd === 'set-welcome') { const s = getSettings(interaction.guild.id); s.welcomeChannelId = interaction.options.getChannel('salon').id; saveSettings(); return interaction.reply({ content: '✅ Salon de bienvenue défini.', ephemeral: true }); }
    if (cmd === 'set-reglement') { const s = getSettings(interaction.guild.id); s.reglementText = interaction.options.getString('texte'); saveSettings(); return interaction.reply({ content: '✅ Règlement mis à jour.', ephemeral: true }); }
    if (cmd === 'set-liens') { const s = getSettings(interaction.guild.id); s.liensText = interaction.options.getString('texte'); saveSettings(); return interaction.reply({ content: '✅ Liens mis à jour.', ephemeral: true }); }
    if (cmd === 'set-urgence') { const s = getSettings(interaction.guild.id); s.urgenceText = interaction.options.getString('texte'); saveSettings(); return interaction.reply({ content: '✅ Urgences mises à jour.', ephemeral: true }); }
    if (cmd === 'set-horaire') { const s = getSettings(interaction.guild.id); s.horaireText = interaction.options.getString('texte'); saveSettings(); return interaction.reply({ content: '✅ Horaires mis à jour.', ephemeral: true }); }
    if (cmd === 'set-suggestions') { const s = getSettings(interaction.guild.id); s.suggestionsChannelId = interaction.options.getChannel('salon').id; saveSettings(); return interaction.reply({ content: '✅ Salon de suggestions défini.', ephemeral: true }); }
    if (cmd === 'set-logs') { const s = getSettings(interaction.guild.id); s.logsChannelId = interaction.options.getChannel('salon').id; saveSettings(); return interaction.reply({ content: '✅ Salon de logs défini.', ephemeral: true }); }
    if (cmd === 'set-staffrole') { const s = getSettings(interaction.guild.id); s.staffRoleId = interaction.options.getRole('role').id; saveSettings(); return interaction.reply({ content: '✅ Rôle staff défini.', ephemeral: true }); }
    if (cmd === 'set-ticketcategorie') { const s = getSettings(interaction.guild.id); s.ticketCategoryId = interaction.options.getChannel('categorie').id; saveSettings(); return interaction.reply({ content: '✅ Catégorie des tickets définie.', ephemeral: true }); }
    if (cmd === 'set-rolecivil') { const s = getSettings(interaction.guild.id); s.civilianRoleId = interaction.options.getRole('role').id; saveSettings(); return interaction.reply({ content: '✅ Rôle civil automatique défini.', ephemeral: true }); }

    // ===== INFOS =====
    if (cmd === 'reglement') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('📜 Règlement').setDescription(getSettings(interaction.guild.id).reglementText)] });
    if (cmd === 'panel-reglement') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const s = getSettings(interaction.guild.id);
      const embed = new EmbedBuilder().setColor(COLOR)
        .setAuthor({ name: interaction.guild.name, iconURL: interaction.guild.iconURL() || undefined })
        .setThumbnail(BOT_ICON())
        .setTitle('📜 ・ Règlement du serveur')
        .setDescription(s.reglementText)
        .setFooter({ text: 'Appuie sur le bouton ci-dessous pour accepter et accéder au serveur.' });
      const row = new ActionRowBuilder().addComponents(new ButtonBuilder().setCustomId('reglement_accept').setLabel("J'accepte le règlement").setEmoji('✅').setStyle(ButtonStyle.Success));
      await interaction.channel.send({ embeds: [embed], components: [row] });
      return interaction.reply({ content: '✅ Panneau de règlement publié.', ephemeral: true });
    }
    if (interaction.isButton() && interaction.customId === 'reglement_accept') {
      const s = getSettings(interaction.guild.id);
      if (!s.reglementRoleId) return interaction.reply({ content: "Aucun rôle n'est configuré pour l'acceptation du règlement (utilise /set-role-reglement).", ephemeral: true });
      if (interaction.member.roles.cache.has(s.reglementRoleId)) return interaction.reply({ content: '✅ Tu as déjà accepté le règlement.', ephemeral: true });
      await interaction.member.roles.add(s.reglementRoleId).catch(() => {});
      return interaction.reply({ content: '✅ Règlement accepté, bienvenue sur le serveur !', ephemeral: true });
    }
    if (cmd === 'set-role-reglement') {
      if (!interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      const s = getSettings(interaction.guild.id);
      s.reglementRoleId = interaction.options.getRole('role').id;
      saveSettings();
      return interaction.reply({ content: '✅ Rôle donné après acceptation du règlement défini.', ephemeral: true });
    }
    if (cmd === 'liens') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('🔗 Liens utiles').setDescription(getSettings(interaction.guild.id).liensText)] });
    if (cmd === 'urgence') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle("🚨 Numéros d'urgence").setDescription(getSettings(interaction.guild.id).urgenceText)] });
    if (cmd === 'horaire') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('🕒 Horaires').setDescription(getSettings(interaction.guild.id).horaireText)] });
    if (cmd === 'codes') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('📻 Codes radio').setDescription("**10-20** : Position\n**10-4** : Message reçu\n**Code 0** : Urgence vitale\n**Code 1** : Intervention normale\n**Code 3** : Intervention urgente")] });
    if (cmd === 'roles') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle('📋 Rôles').setDescription(interaction.guild.roles.cache.filter(r => r.id !== interaction.guild.id).sort((a, b) => b.position - a.position).map(r => `${r}`).join('\n') || 'Aucun')] });
    if (cmd === 'help') return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR)
      .setAuthor({ name: client.user.username, iconURL: BOT_ICON() })
      .setThumbnail(BOT_ICON())
      .setTitle('📖 ・ Centre de commandes')
      .setDescription(`Voici toutes les commandes disponibles sur **${interaction.guild.name}**.`)
      .addFields(
      { name: '📜  Infos', value: '`/reglement` `/roles` `/liens` `/urgence` `/horaire` `/codes`' },
      { name: '🎭  RP', value: '`/creer-personnage` `/profil` `/id` `/me` `/dire` `/cni` `/carte-identite` `/gang` `/entreprise` `/entreprises`' },
      { name: '📁  Casier & Notes', value: '`/casier` `/warn` `/warnings` `/unwarn` `/clearwarns` `/note` `/notes` `/deletenote`' },
      { name: '👮  Sanctions', value: '`/kick` `/ban` `/tempban` `/unban` `/softban` `/mute` `/unmute` `/timeout` `/untimeout`' },
      { name: '⚙️  Administration', value: '`/clear` `/lock` `/unlock` `/slowmode` `/nuke` `/embed` `/roleinfo` `/staffstats`' },
      { name: '🤖  Centre de contrôle', value: '`/panel` `/config`' },
      { name: '🎫  Support & Tickets', value: '`/panel-ticket` `/close` `/recrutement` `/staff` `/signalement` `/ticket-categorie-ajouter` `/ticket-categorie-supprimer` `/ticket-categorie-liste`' },
      { name: '📜  Règlement', value: '`/panel-reglement` `/set-role-reglement`' },
      { name: '🎉  Utilitaires', value: '`/ping` `/avatar` `/userinfo` `/serverinfo` `/suggestion` `/annonce` `/sondage`' },
      { name: '🎮  Fun', value: '`/8ball` `/des` `/pileouface`' },
      { name: '🔧  Configuration (staff)', value: '`/config` `/set-staffrole` `/set-ticketcategorie` `/set-rolecivil` `/set-welcome` `/set-logs` `/set-reglement` `/set-liens` `/set-urgence` `/set-horaire` `/set-suggestions`' },
      { name: '📈  Niveaux', value: '`/niveau voir` `/niveau ajouter` `/niveau retirer` `/niveau set` `/niveau reset` `/niveau config` `/niveau recompense` `/classement`' },
    ).setFooter({ text: `${interaction.guild.name} • Bot premium`, iconURL: BOT_ICON() }).setTimestamp()] });

    // ===== NIVEAUX =====
    if (cmd === 'niveau') {
      const sub = interaction.options.getSubcommand();
      const gid = interaction.guild.id;

      if (sub === 'voir') {
        const target = interaction.options.getUser('membre') || interaction.user;
        const k = key(gid, target.id);
        const data = levels[k] || { xp: 0, level: 0, messages: 0 };
        const needed = xpForNextLevel(data.level);
        const embed = new EmbedBuilder().setColor(0xf5a623)
          .setAuthor({ name: target.username, iconURL: target.displayAvatarURL() })
          .setTitle('📊 Statistiques de niveau')
          .addFields(
            { name: '🏅 Niveau', value: `${data.level}`, inline: true },
            { name: '⭐ XP', value: `${data.xp} / ${needed}`, inline: true },
            { name: '📈 Rang', value: `#${getRank(k)}`, inline: true },
            { name: '💬 Messages envoyés', value: `${data.messages || 0}`, inline: true },
            { name: `Progression → Niveau ${data.level + 1}`, value: `${progressBar(data.xp, needed)}  ${data.xp}/${needed} XP` },
          );
        return interaction.reply({ embeds: [embed] });
      }

      if (['ajouter', 'retirer', 'set', 'reset', 'config', 'recompense'].includes(sub) && !interaction.memberPermissions.has(PermissionsBitField.Flags.ManageGuild)) {
        return interaction.reply({ content: "Permission refusée.", ephemeral: true });
      }

      if (sub === 'ajouter') {
        const target = interaction.options.getUser('membre'); const xp = interaction.options.getInteger('xp');
        const { level, leveledUp } = addXp(key(gid, target.id), xp);
        return interaction.reply({ content: `✅ ${xp} XP ajouté(s) à <@${target.id}>. Niveau actuel : ${level}${leveledUp ? ' (a monté de niveau !)' : ''}` });
      }
      if (sub === 'retirer') {
        const target = interaction.options.getUser('membre'); const xp = interaction.options.getInteger('xp');
        const k = key(gid, target.id);
        if (!levels[k]) levels[k] = { xp: 0, level: 0, messages: 0 };
        levels[k].xp = Math.max(0, levels[k].xp - xp);
        saveJson(LEVELS_PATH, levels);
        return interaction.reply({ content: `✅ ${xp} XP retiré(s) à <@${target.id}>.` });
      }
      if (sub === 'set') {
        const target = interaction.options.getUser('membre'); const niveau = interaction.options.getInteger('niveau');
        const k = key(gid, target.id);
        levels[k] = { xp: 0, level: niveau, messages: (levels[k]?.messages) || 0 };
        saveJson(LEVELS_PATH, levels);
        return interaction.reply({ content: `✅ <@${target.id}> est maintenant niveau ${niveau}.` });
      }
      if (sub === 'reset') {
        const target = interaction.options.getUser('membre');
        levels[key(gid, target.id)] = { xp: 0, level: 0, messages: 0 };
        saveJson(LEVELS_PATH, levels);
        return interaction.reply({ content: `✅ Niveau de <@${target.id}> réinitialisé.` });
      }
      if (sub === 'config') {
        const salon = interaction.options.getChannel('salon');
        const s = getSettings(gid);
        s.levelUpChannelId = salon ? salon.id : null;
        saveSettings();
        return interaction.reply({ content: salon ? `✅ Les messages de niveau seront envoyés dans <#${salon.id}>.` : '✅ Les messages de niveau seront envoyés dans le salon où le membre écrit.', ephemeral: true });
      }
      if (sub === 'recompense') {
        const niveau = interaction.options.getInteger('niveau'); const role = interaction.options.getRole('role');
        const s = getSettings(gid);
        s.levelRewards = s.levelRewards || {};
        s.levelRewards[niveau] = role.id;
        saveSettings();
        return interaction.reply({ content: `✅ Le rôle ${role} sera donné automatiquement au niveau ${niveau}.` });
      }
    }

    if (cmd === 'classement') {
      const page = 0;
      return interaction.reply({ embeds: [buildClassementEmbed(interaction.guild.id, page)], components: [buildClassementRow(interaction.guild.id, page)] });
    }
    if (interaction.isButton() && interaction.customId.startsWith('classement_page:')) {
      const parts = interaction.customId.split(':');
      const gid = parts[1]; const page = parseInt(parts[2], 10);
      return interaction.update({ embeds: [buildClassementEmbed(gid, page)], components: [buildClassementRow(gid, page)] });
    }

    // ===== RP =====
    if (cmd === 'creer-personnage') {
      const nom = interaction.options.getString('nom'), age = interaction.options.getInteger('age'), description = interaction.options.getString('description');
      characters[key(interaction.guild.id, interaction.user.id)] = { nom, age, description }; saveJson(CHARACTERS_PATH, characters);
      return interaction.reply({ content: `✅ Fiche créée pour **${nom}**.`, ephemeral: true });
    }
    if (cmd === 'profil' || cmd === 'id') {
      const target = interaction.options.getUser('membre') || interaction.user; const perso = characters[key(interaction.guild.id, target.id)];
      if (!perso) return interaction.reply({ content: "Pas de fiche. Utilise /creer-personnage.", ephemeral: true });
      return interaction.reply({ embeds: [new EmbedBuilder().setColor(COLOR).setTitle(`🪪 ${perso.nom}`).setThumbnail(target.displayAvatarURL()).addFields({ name: 'Âge', value: `${perso.age}`, inline: true }, { name: 'Joueur', value: `<@${target.id}>`, inline: true }, { name: 'Description', value: perso.description })] });
    }
    if (cmd === 'cni') {
      const nom = interaction.options.getString('nom'), naissance = interaction.options.getString('naissance'), adresse = interaction.options.getString('adresse');
      const existing = cniData[key(interaction.guild.id, interaction.user.id)];
      const numero = existing ? existing.numero : `${Math.floor(Math.random() * 90 + 10)}-${genId().toUpperCase()}`;
      const delivree = existing ? existing.delivree : new Date().toLocaleDateString('fr-FR');
      cniData[key(interaction.guild.id, interaction.user.id)] = { nom, naissance, adresse, numero, delivree };
      saveJson(CNI_PATH, cniData);
      const embed = new EmbedBuilder().setColor(COLOR).setTitle("🪪 Carte Nationale d'Identité").setThumbnail(interaction.user.displayAvatarURL())
        .addFields(
          { name: 'Nom', value: nom, inline: true }, { name: 'Naissance', value: naissance, inline: true }, { name: 'N° de carte', value: numero, inline: true },
          { name: 'Adresse', value: adresse }, { name: 'Délivrée le', value: delivree, inline: true },
        );
      return interaction.reply({ embeds: [embed] });
    }
    if (cmd === 'carte-identite') {
      const target = interaction.options.getUser('membre') || interaction.user;
      const carte = cniData[key(interaction.guild.id, target.id)];
      if (!carte) return interaction.reply({ content: `<@${target.id}> n'a pas encore de carte d'identité. Utilise /cni pour en créer une.`, ephemeral: true });
      const embed = new EmbedBuilder().setColor(COLOR).setTitle("🪪 Carte Nationale d'Identité").setThumbnail(target.displayAvatarURL())
        .addFields(
          { name: 'Nom', value: carte.nom, inline: true }, { name: 'Naissance', value: carte.naissance, inline: true }, { name: 'N° de carte', value: carte.numero, inline: true },
          { name: 'Adresse', value: carte.adresse }, { name: 'Délivrée le', value: carte.delivree, inline: true },
        );
      return interaction.reply({ embeds: [embed] });
    }
    if (cmd === 'me') { const action = interaction.options.getString('action'); const perso = characters[key(interaction.guild.id, interaction.user.id)]; return interaction.reply({ content: `*${perso ? perso.nom : interaction.user.username} ${action}*` }); }
    if (cmd === 'dire') { const texte = interaction.options.getString('message'); const perso = characters[key(interaction.guild.id, interaction.user.id)]; return interaction.reply({ content: `**${perso ? perso.nom : interaction.user.username} dit :** ${texte}` }); }

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
      const target = getSettings(interaction.guild.id).suggestionsChannelId ? interaction.guild.channels.cache.get(getSettings(interaction.guild.id).suggestionsChannelId) : interaction.channel;
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
      const pollId = genId();
      activePolls.set(pollId, { question, options, votes: {} });
      const poll = activePolls.get(pollId);
      await interaction.reply({ embeds: [buildPollEmbed(poll)], components: [buildPollRow(pollId, options)] });
      return;
    }
    if (interaction.isButton() && interaction.customId.startsWith('sondage_vote:')) {
      const [, pollId, idxStr] = interaction.customId.split(':');
      const poll = activePolls.get(pollId);
      if (!poll) return interaction.reply({ content: 'Ce sondage a expiré.', ephemeral: true });
      poll.votes[interaction.user.id] = parseInt(idxStr, 10);
      return interaction.update({ embeds: [buildPollEmbed(poll)], components: [buildPollRow(pollId, poll.options)] });
    }

    // ===== FUN =====
    if (cmd === '8ball') { const r = ['Oui, certainement.', 'Non, aucune chance.', 'Peut-être...', 'Demande plus tard.', "C'est certain !", 'Incertain.']; return interaction.reply({ content: `🎱 ${r[Math.floor(Math.random() * r.length)]}` }); }
    if (cmd === 'des') { const faces = interaction.options.getInteger('faces') || 6; return interaction.reply({ content: `🎲 **${Math.floor(Math.random() * faces) + 1}** (sur ${faces})` }); }
    if (cmd === 'pileouface') return interaction.reply({ content: `🪙 **${Math.random() < 0.5 ? 'Pile' : 'Face'}** !` });
  } catch (err) {
    console.error(err);
    const msg = err?.message && err.message.length < 300 ? err.message : "Une erreur est survenue.";
    if (interaction.isRepliable() && !interaction.replied && !interaction.deferred) interaction.reply({ content: `❌ ${msg}`, ephemeral: true }).catch(() => {});
    else if (interaction.isRepliable() && interaction.deferred && !interaction.replied) interaction.editReply({ content: `❌ ${msg}` }).catch(() => {});
  }
});

// ---------- Bienvenue + anti-raid ----------
client.on('guildMemberAdd', async (member) => {
  try {
    const s = getSettings(member.guild.id);
    if (s.civilianRoleId) await member.roles.add(s.civilianRoleId).catch(() => {});

    // Détection compte récent
    const accountAge = Date.now() - member.user.createdTimestamp;
    if (accountAge < 7 * 24 * 60 * 60 * 1000) {
      await sendLog(member.guild, new EmbedBuilder().setColor(0xe53e3e).setTitle('⚠️ Compte récemment créé').setDescription(`<@${member.id}> a créé son compte il y a moins de 7 jours.`).setTimestamp());
    }

    // Anti-raid : trop d'arrivées rapprochées
    if (s.automod.antiRaid) {
      const now = Date.now();
      s.recentJoins = (s.recentJoins || []).filter(t => now - t < 10000);
      s.recentJoins.push(now);
      saveSettings();
      if (s.recentJoins.length >= 8) {
        await sendLog(member.guild, new EmbedBuilder().setColor(0xe53e3e).setTitle('🚨 Raid potentiel détecté').setDescription('8+ arrivées en moins de 10 secondes.').setTimestamp());
      }
    }

    await sendLog(member.guild, new EmbedBuilder().setColor(0x38a169).setTitle('➕ Arrivée').setDescription(`<@${member.id}> a rejoint le serveur.`).setTimestamp());

    const channelId = s.welcomeChannelId;
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

  // IA : répond quand le bot est mentionné directement
  if (message.mentions.has(client.user.id) && !message.mentions.everyone) {
    const question = message.content.replace(/<@!?\d+>/g, '').trim();
    if (question.length > 0) {
      await message.channel.sendTyping().catch(() => {});
      const answer = await askAI(question);
      await message.reply(answer);
      return;
    }
  }

  // Anti-lien d'invitation
  const s = getSettings(message.guild.id);
  if (s.automod.antiInvite && INVITE_REGEX.test(message.content) && !message.member.permissions.has(PermissionsBitField.Flags.ManageMessages)) {
    await message.delete().catch(() => {});
    await message.channel.send(`🔗 <@${message.author.id}>, les liens d'invitation ne sont pas autorisés.`).then(m => setTimeout(() => m.delete().catch(() => {}), 5000));
    await sendLog(message.guild, new EmbedBuilder().setColor(0xe53e3e).setTitle('🔗 Lien invitation bloqué').setDescription(`<@${message.author.id}> dans ${message.channel}`).setTimestamp());
    return;
  }
  // Anti-mentions massives
  if (s.automod.antiMassMention && message.mentions.users.size >= 5) {
    await message.delete().catch(() => {});
    await sendLog(message.guild, new EmbedBuilder().setColor(0xe53e3e).setTitle('📢 Mentions massives bloquées').setDescription(`<@${message.author.id}> a mentionné ${message.mentions.users.size} membres.`).setTimestamp());
    return;
  }
  // Anti-caps (messages longs tout en majuscules)
  if (s.automod.antiCaps && message.content.length > 15) {
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
  const spamKey = key(message.guild.id, message.author.id);
  const timestamps = (spamTracker.get(spamKey) || []).filter(t => now - t < SPAM_WINDOW_MS);
  timestamps.push(now);
  spamTracker.set(spamKey, timestamps);
  if (timestamps.length > SPAM_LIMIT) {
    spamTracker.set(spamKey, []);
    try {
      const member = await message.guild.members.fetch(message.author.id);
      if (member.moderatable) {
        await member.timeout(60 * 1000, 'Anti-spam automatique');
        await message.channel.send(`🔇 <@${message.author.id}> mis en sourdine 1 min (anti-spam).`);
        addSanction(spamKey, 'timeout', 'Anti-spam automatique', 'AutoMod');
        await logModeration(message.guild, 'Anti-spam (mute auto)', message.author, client.user, 'Messages trop rapides');
      }
      const recent = await message.channel.messages.fetch({ limit: 10 });
      await message.channel.bulkDelete(recent.filter(m => m.author.id === message.author.id), true).catch(() => {});
    } catch (err) { console.error('Anti-spam:', err); }
    return;
  }

  // XP
  const xpKey = key(message.guild.id, message.author.id);
  const lastGain = xpCooldown.get(xpKey) || 0;
  if (now - lastGain < 30000) return;
  xpCooldown.set(xpKey, now);
  const { level, leveledUp } = addXp(xpKey, Math.floor(Math.random() * 10) + 5);
  if (leveledUp) {
    const data = levels[xpKey];
    const needed = xpForNextLevel(level);
    const embed = new EmbedBuilder().setColor(0xf5c518)
      .setTitle('⬆️ Niveau supérieur !')
      .setDescription(`Félicitations <@${message.author.id}> ! Tu viens d'atteindre le **niveau ${level}** ! 🎉`)
      .addFields(
        { name: '📊 Niveau', value: `${level}`, inline: true },
        { name: '⭐ XP Total', value: `${data.xp}`, inline: true },
        { name: `Progression → Niveau ${level + 1}`, value: `${progressBar(data.xp, needed)}  ${data.xp}/${needed} XP` },
      )
      .setFooter({ text: `${message.guild.name} • Niveaux` });
    const targetChannel = s.levelUpChannelId ? message.guild.channels.cache.get(s.levelUpChannelId) : message.channel;
    (targetChannel || message.channel).send({ embeds: [embed] }).catch(() => {});
    checkLevelRewards(message.guild, message.member, level);
  }
});

function buildPollEmbed(poll) {
  const totalVotes = Object.keys(poll.votes).length;
  const counts = poll.options.map((_, i) => Object.values(poll.votes).filter(v => v === i).length);
  const lines = poll.options.map((o, i) => {
    const count = counts[i];
    const pct = totalVotes ? Math.round((count / totalVotes) * 100) : 0;
    return `**${o}**\n${progressBar(count, totalVotes || 1, 12)}  ${count} vote(s) • ${pct}%`;
  });
  return new EmbedBuilder().setColor(COLOR).setTitle(`📊  ${poll.question}`).setDescription(lines.join('\n\n')).setFooter({ text: `${totalVotes} vote(s) au total • Sondage premium` });
}
function buildPollRow(pollId, options) {
  const row = new ActionRowBuilder();
  options.forEach((o, i) => row.addComponents(new ButtonBuilder().setCustomId(`sondage_vote:${pollId}:${i}`).setLabel(o.slice(0, 70)).setStyle(ButtonStyle.Primary)));
  return row;
}

function buildClassementEmbed(guildId, page) {
  const PAGE_SIZE = 10;
  const prefix = `${guildId}:`;
  const sorted = Object.entries(levels).filter(([k]) => k.startsWith(prefix)).sort((a, b) => (b[1].level - a[1].level) || (b[1].xp - a[1].xp));
  const pageItems = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const embed = new EmbedBuilder().setColor(0xf5a623).setTitle('🏆 Classement du serveur');
  if (pageItems.length === 0) {
    embed.setDescription("Personne n'a encore gagné d'XP.");
  } else {
    const lines = pageItems.map(([k, d], i) => `**#${page * PAGE_SIZE + i + 1}** — <@${k.split(':')[1]}> • Niveau ${d.level} (${d.xp} XP)`);
    embed.setDescription(lines.join('\n'));
  }
  embed.setFooter({ text: `Page ${page + 1} / ${Math.max(1, Math.ceil(sorted.length / PAGE_SIZE))}` });
  return embed;
}
function buildClassementRow(guildId, page) {
  const prefix = `${guildId}:`;
  const totalCount = Object.keys(levels).filter(k => k.startsWith(prefix)).length;
  const totalPages = Math.max(1, Math.ceil(totalCount / 10));
  return new ActionRowBuilder().addComponents(
    new ButtonBuilder().setCustomId(`classement_page:${guildId}:${page - 1}`).setLabel('◀️ Précédent').setStyle(ButtonStyle.Secondary).setDisabled(page <= 0),
    new ButtonBuilder().setCustomId(`classement_page:${guildId}:${page + 1}`).setLabel('Suivant ▶️').setStyle(ButtonStyle.Secondary).setDisabled(page + 1 >= totalPages),
  );
}

async function closeTicket(interaction) {
  const channel = interaction.channel;
  const staffRole = interaction.guild.roles.cache.get(getSettings(interaction.guild.id).staffRoleId);
  if (staffRole && interaction.member && !interaction.member.roles.cache.has(staffRole.id)) return interaction.reply({ content: "Réservé au staff.", ephemeral: true });
  await interaction.reply({ content: 'Fermeture dans 5s... Génération du transcript.' });
  const messages = await channel.messages.fetch({ limit: 100 });
  const lines = [...messages.values()].reverse().map(m => `[${m.createdAt.toISOString()}] ${m.author?.tag ?? 'Inconnu'}: ${m.content || '[embed/composant]'}`);
  const tp = path.join(__dirname, `transcript-${channel.id}.txt`);
  fs.writeFileSync(tp, lines.join('\n') || 'Aucun message.');
  const logChannel = interaction.guild.channels.cache.get(getSettings(interaction.guild.id).logsChannelId);
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
