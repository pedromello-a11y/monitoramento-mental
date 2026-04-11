require('dotenv').config();

const fs = require('fs');
const path = require('path');
const express = require('express');
const qrcode = require('qrcode');
const qrcodeTerminal = require('qrcode-terminal');
const { Client, RemoteAuth } = require('whatsapp-web.js');

const PostgresSessionStore = require('./session_store');
const state = require('./state');

fs.mkdirSync(path.join(__dirname, '.wwebjs_auth'), { recursive: true });

const PORT = Number(process.env.PORT || 3001);
const WA_BRIDGE_SHARED_SECRET = (process.env.WA_BRIDGE_SHARED_SECRET || '').trim();
const WA_SESSION_ID = (process.env.WA_SESSION_ID || 'monitoramento').trim();

let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 3;

function normalizeChatId(value) {
  const raw = String(value || '').trim();
  if (!raw) throw new Error('chatId ausente');
  if (raw.endsWith('@g.us') || raw.endsWith('@c.us')) return raw;
  if (raw.endsWith('@s.whatsapp.net')) return raw.replace('@s.whatsapp.net', '@c.us');
  if (/^\d+$/.test(raw)) return `${raw}@c.us`;
  return raw;
}

const store = new PostgresSessionStore();
const authStrategy = new RemoteAuth({
  clientId: WA_SESSION_ID,
  store,
  backupSyncIntervalMs: 300000,
});

const originalStoreRemoteSession = authStrategy.storeRemoteSession.bind(authStrategy);
authStrategy.storeRemoteSession = async function patchedStoreRemoteSession(options) {
  try {
    await originalStoreRemoteSession(options);
  } catch (err) {
    if (err && err.code === 'ENOENT') {
      console.log('[session] ZIP ausente ao limpar, ignorando');
      return;
    }
    throw err;
  }
};

const puppeteerOptions = {
  headless: true,
  args: [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--disable-extensions',
    '--single-process',
    '--no-zygote',
    '--disable-background-networking',
    '--disable-default-apps',
    '--mute-audio',
  ],
};

if (process.env.PUPPETEER_EXECUTABLE_PATH) {
  puppeteerOptions.executablePath = process.env.PUPPETEER_EXECUTABLE_PATH;
}

const client = new Client({
  authStrategy,
  puppeteer: puppeteerOptions,
});
state.client = client;

client.on('qr', async (qrRaw) => {
  state.qrRaw = qrRaw;
  state.botStatus = 'qr';
  try {
    state.qrCode = await qrcode.toDataURL(qrRaw);
  } catch {
    state.qrCode = null;
  }
  console.log('[wa-gateway] QR gerado. Escaneie em /qr ou no terminal abaixo.');
  qrcodeTerminal.generate(qrRaw, { small: true });
});

client.on('authenticated', () => {
  console.log('[wa-gateway] Autenticado com sucesso.');
});

client.on('auth_failure', (msg) => {
  state.botStatus = 'offline';
  console.error('[wa-gateway] Falha de autenticação:', msg);
});

client.on('ready', () => {
  reconnectAttempts = 0;
  state.qrCode = null;
  state.qrRaw = null;
  state.botStatus = 'ready';
  console.log('[wa-gateway] ✅ WhatsApp conectado e pronto.');
});

client.on('disconnected', (reason) => {
  state.botStatus = 'disconnected';
  console.error('[wa-gateway] Desconectado:', reason);

  if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
    console.error('[wa-gateway] Máximo de tentativas atingido. Aguarde novo QR.');
    state.botStatus = 'offline';
    reconnectAttempts = 0;
    return;
  }

  reconnectAttempts += 1;
  const delayMs = reconnectAttempts * 10000;
  console.log(`[wa-gateway] Tentativa ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS} em ${delayMs / 1000}s...`);
  setTimeout(() => {
    client.initialize().catch((err) => {
      console.error('[wa-gateway] Erro ao reinicializar:', err.message || err);
    });
  }, delayMs);
});

const app = express();
app.use(express.json({ limit: '2mb' }));

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', botStatus: state.botStatus, hasQr: Boolean(state.qrCode) });
});

app.get('/qr', (_req, res) => {
  if (!state.qrCode) {
    res.send(`<html><body style="font-family:Arial,sans-serif;padding:24px">
      <h1>Monitoramento Mental — WhatsApp Gateway</h1>
      <p>Status: <strong>${state.botStatus}</strong></p>
      <p>Sem QR disponível. Se já autenticou, isso é esperado.</p>
    </body></html>`);
    return;
  }
  res.send(`<html><body style="font-family:Arial,sans-serif;padding:24px">
    <h1>Escaneie o QR</h1>
    <p>Status: <strong>${state.botStatus}</strong></p>
    <img src="${state.qrCode}" style="max-width:420px;width:100%" />
  </body></html>`);
});

app.post('/send', async (req, res) => {
  try {
    if (state.botStatus !== 'ready') {
      res.status(503).json({ status: 'failed', error: 'gateway_not_ready' });
      return;
    }

    const requestSecret = String(req.headers['x-bridge-secret'] || '').trim();
    if (WA_BRIDGE_SHARED_SECRET && requestSecret !== WA_BRIDGE_SHARED_SECRET) {
      res.status(401).json({ status: 'failed', error: 'invalid_bridge_secret' });
      return;
    }

    // aceita tanto {to, body} (formato whapi) quanto {chatId, text}
    const chatId = String(req.body?.to || req.body?.chatId || '').trim();
    const text = String(req.body?.body || req.body?.text || '').trim();

    if (!chatId || !text) {
      res.status(400).json({ status: 'failed', error: 'to e body são obrigatórios' });
      return;
    }

    const resolvedChatId = normalizeChatId(chatId);
    await client.sendMessage(resolvedChatId, text);
    res.json({ status: 'ok', chatId: resolvedChatId });
  } catch (err) {
    console.error('[wa-gateway] Erro no /send:', err.message || err);
    res.status(500).json({ status: 'failed', error: err.message || String(err) });
  }
});

app.post('/disconnect', async (req, res) => {
  const requestSecret = String(req.headers['x-bridge-secret'] || '').trim();
  if (WA_BRIDGE_SHARED_SECRET && requestSecret !== WA_BRIDGE_SHARED_SECRET) {
    res.status(401).json({ status: 'failed', error: 'invalid_bridge_secret' });
    return;
  }
  state.botStatus = 'offline';
  state.qrCode = null;
  state.qrRaw = null;
  try { await client.destroy(); } catch {}
  setTimeout(() => client.initialize().catch(() => {}), 2000);
  res.json({ ok: true });
});

app.listen(PORT, () => {
  console.log(`[wa-gateway] HTTP escutando na porta ${PORT}`);
});

console.log('[wa-gateway] Iniciando WhatsApp gateway do Monitoramento Mental...');
client.initialize().catch((err) => {
  state.botStatus = 'offline';
  console.error('[wa-gateway] Erro ao inicializar client:', err.message || err);
});
