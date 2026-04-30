const START_PROMPT =
  "Начни кампанию с пафосного вступления. Опиши вход в Бюрократическую Цитадель, цербера-секретаря у ворот и текущую стартовую ситуацию героя. Затем задай вопрос или предложи первый осмысленный выбор.";

const asNumber = (value) => {
  if (value === "" || value === null || value === undefined) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const setStatus = (element, text, isError = false) => {
  if (!element) return;
  element.textContent = text;
  element.style.color = isError ? "#ffb6ba" : "";
};

const togglePending = (form, pending) => {
  if (!form) return;
  form.querySelectorAll("button, input, textarea, select").forEach((node) => {
    node.disabled = pending;
  });
};

const compactErrorText = (value) =>
  String(value || "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 700);

const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);

const extractErrorMessage = async (response) => {
  const rawText = await response.text();
  let parsed = null;

  try {
    parsed = rawText ? JSON.parse(rawText) : null;
  } catch {
    parsed = null;
  }

  let detail = "";
  if (typeof parsed?.detail === "string") {
    detail = parsed.detail;
  } else if (parsed?.detail) {
    detail = JSON.stringify(parsed.detail);
  } else if (rawText) {
    detail = compactErrorText(rawText);
  } else {
    detail = "Пустой ответ";
  }

  return `HTTP ${response.status}: ${detail}`;
};

const sendJson = async (url, payload, method = "POST") => {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  return response.json().catch(() => ({}));
};

const sendWithoutBody = async (url, method = "DELETE") => {
  const response = await fetch(url, { method });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }
  return response.json().catch(() => ({}));
};

const IMPORT_JOB_STORAGE_KEY = "rpg_dm_import_job_v1";
const PROMPT_TEMPLATE_STORAGE_KEY = "rpg_dm_prompt_templates_v1";
const DEMO_TEXT_API_KEY_STORAGE_KEY = "rpg_dm_demo_text_api_key_v1";
const DEMO_VOICE_API_KEY_STORAGE_KEY = "rpg_dm_demo_voice_api_key_v1";
const SCENE_PANEL_STORAGE_KEY = "rpg_dm_scene_panel_v1";
const SCENE_EMOTION_STORAGE_KEY = "rpg_dm_scene_emotion_v1";
const SCENE_TTS_ENABLED_STORAGE_KEY = "rpg_dm_scene_tts_enabled_v1";
const SCENE_TTS_LAST_SPOKEN_STORAGE_KEY = "rpg_dm_scene_tts_last_spoken_v1";
const SCENE_TTS_PROVIDER_STORAGE_KEY = "rpg_dm_scene_tts_provider_v1";
const SCENE_TTS_DEFAULT_PROVIDER = "google";
const SCENE_TTS_AUDIO_CACHE_LIMIT = 6;
const SCENE_GOOGLE_TTS_MAX_CHARS = 1400;
const SCENE_GOOGLE_TTS_HARD_CHARS = 1800;
const SCENE_GOOGLE25_TTS_MAX_CHARS = 5200;
const SCENE_GOOGLE25_TTS_HARD_CHARS = 5800;
const SCENE_GOOGLE_TTS_REQUEST_GAP_MS = 3500;
const SCENE_TTS_PROVIDERS = {
  google: {
    label: "Google 3.1 Leda",
    status: "Google 3.1 TTS говорит...",
    endpoint: "/api/tts/google",
    model: "gemini-3.1-flash-tts-preview",
  },
  google25: {
    label: "Google 2.5 Leda",
    status: "Google 2.5 TTS говорит...",
    endpoint: "/api/tts/google",
    model: "gemini-2.5-flash-preview-tts",
  },
  silero: { label: "Silero local", status: "Silero говорит...", endpoint: "/api/tts/silero" },
  edge: { label: "Edge", status: "Edge говорит...", endpoint: "/api/tts/edge" },
};
const DESIGN_WIDTH = 1920;
const DESIGN_HEIGHT = 1080;
const PLAY_ICON_SVG = '<svg viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="M8 5.14v13.72a1 1 0 0 0 1.54.84l10.67-6.86a1 1 0 0 0 0-1.68L9.54 4.3A1 1 0 0 0 8 5.14Z"/></svg>';
const PAUSE_ICON_SVG = '<svg viewBox="0 0 24 24" focusable="false" aria-hidden="true"><path d="M7 5h3a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Zm7 0h3a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z"/></svg>';

const readLocalValue = (key) => {
  try {
    return window.localStorage.getItem(key) || "";
  } catch {
    return "";
  }
};

const writeLocalValue = (key, value) => {
  try {
    const normalized = String(value || "").trim();
    if (normalized) {
      window.localStorage.setItem(key, normalized);
    } else {
      window.localStorage.removeItem(key);
    }
  } catch {
    window.alert("Браузер не дал сохранить ключ в localStorage.");
  }
};

const readDemoTextApiKey = () => readLocalValue(DEMO_TEXT_API_KEY_STORAGE_KEY);
const readDemoVoiceApiKey = () => readLocalValue(DEMO_VOICE_API_KEY_STORAGE_KEY);

const syncApiKeyForms = (root = document) => {
  const textKey = readDemoTextApiKey();
  const voiceKey = readDemoVoiceApiKey();
  root.querySelectorAll("[data-text-api-key-input]").forEach((input) => {
    input.value = textKey;
  });
  root.querySelectorAll("[data-voice-api-key-input]").forEach((input) => {
    input.value = voiceKey;
  });
  root.querySelectorAll("[data-api-key-status]").forEach((status) => {
    status.textContent = textKey || voiceKey
      ? "Ключи сохранены только в этом браузере. В проект и GitHub они не записываются."
      : "Для публичного демо вставь ключи здесь. Локальный .env продолжит работать на твоём ПК.";
  });
};

const PLAY_PANEL_META = {
  scene: {
    eyebrow: "SCENE",
    title: "Сцена",
    iconClass: "play-panel-icon--scene",
    iconSvg: '<svg viewBox="0 0 24 24" focusable="false"><path d="M12 21s6-5.15 6-11a6 6 0 1 0-12 0c0 5.85 6 11 6 11Zm0-8.25A2.75 2.75 0 1 1 12 7.25a2.75 2.75 0 0 1 0 5.5Z"/></svg>',
  },
  characters: {
    eyebrow: "CAST",
    title: "Персонажи",
    iconClass: "play-panel-icon--characters",
    iconSvg: '<svg viewBox="0 0 24 24" focusable="false"><path d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Zm-7 9v-1a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v1h-2v-1a3 3 0 0 0-3-3h-4a3 3 0 0 0-3 3v1Z"/></svg>',
  },
  quests: {
    eyebrow: "QUESTS",
    title: "Квесты",
    iconClass: "play-panel-icon--quests",
    iconSvg: '<svg viewBox="0 0 24 24" focusable="false"><path d="M7 4a2 2 0 0 0-2 2v14l7-3 7 3V6a2 2 0 0 0-2-2Zm0 2h10v10.97l-5-2.15-5 2.15Z"/></svg>',
  },
  inventory: {
    eyebrow: "INVENTORY",
    title: "Инвентарь",
    iconClass: "play-panel-icon--inventory",
    iconSvg: '<svg viewBox="0 0 24 24" focusable="false"><path d="M8 7V6a4 4 0 0 1 8 0v1h2a2 2 0 0 1 2 2v9a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V9a2 2 0 0 1 2-2Zm2 0h4V6a2 2 0 0 0-4 0Zm-4 2v9a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V9Z"/></svg>',
  },
};

const SCENE_EMOTION_LABELS = {
  auto: "Авто",
  neutral: "Гемма спокойна",
  joy: "Гемма оживилась",
  surprised: "Гемма удивлена",
  angry: "Гемма ворчит",
  fear: "Гемма тревожится",
  shock: "Гемма в шоке",
  glasses: "Гемма поправляет очки",
};

const SCENE_TTS_BY_EMOTION = {
  neutral: { rate: "-8%", pitch: "-14Hz", pauseMs: 45 },
  joy: { rate: "-1%", pitch: "+18Hz", pauseMs: 45 },
  surprised: { rate: "+5%", pitch: "+32Hz", pauseMs: 60 },
  angry: { rate: "-12%", pitch: "-28Hz", pauseMs: 55 },
  fear: { rate: "+2%", pitch: "+36Hz", pauseMs: 85 },
  shock: { rate: "-16%", pitch: "-6Hz", pauseMs: 100 },
  glasses: { rate: "-12%", pitch: "-10Hz", pauseMs: 65 },
};

/**
 * @typedef {"auto"|"neutral"|"joy"|"surprised"|"angry"|"fear"|"shock"|"glasses"} Emotion
 */

/**
 * @typedef {{
 *   text: string,
 *   emotion?: Emotion,
 *   emotion_timeline?: Array<{start: number, end: number, emotion: Emotion}>,
 *   voice_timeline?: Array<{line: number, speaker: string, emotion: Emotion, rate: string, pitch: string, pause_ms: number}>
 * }} GemmaResponse
 */

const SCENE_PANEL_META = {
  dm: { eyebrow: "Live log", title: "DM" },
  scene: { eyebrow: "Scene", title: "Сцена" },
  characters: { eyebrow: "Cast", title: "Персонажи" },
  quests: { eyebrow: "Quests", title: "Квесты" },
  inventory: { eyebrow: "Inventory", title: "Инвентарь" },
};

const GEMMA_PORTRAITS = {
  нейтрально: "/static/scene/gemma-neutral.png",
  радость: "/static/scene/gemma-joy.png?v=2",
  удивление: "/static/scene/gemma-surprised.png",
  возмущение: "/static/scene/gemma-sulking.png",
  страх: "/static/scene/gemma-fright.png",
  шок: "/static/scene/gemma-shocked.png",
  очки: "/static/scene/gemma-glasses.png",
};

const readPromptTemplates = () => {
  try {
    const raw = window.localStorage.getItem(PROMPT_TEMPLATE_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item) => item?.name && item?.text) : [];
  } catch {
    return [];
  }
};

const writePromptTemplates = (templates) => {
  try {
    window.localStorage.setItem(PROMPT_TEMPLATE_STORAGE_KEY, JSON.stringify(templates));
  } catch {
    window.alert("Не удалось сохранить шаблон: браузер не дал доступ к localStorage.");
  }
};

const refreshPromptTemplateSelectors = () => {
  const templates = readPromptTemplates();
  document.querySelectorAll("[data-prompt-template-select]").forEach((select) => {
    const current = select.value;
    select.innerHTML = '<option value="">Шаблоны описаний</option>';
    templates.forEach((template, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = template.name;
      select.appendChild(option);
    });
    select.value = templates[Number(current)] ? current : "";
  });
};

const fingerprintTranscript = (text) => {
  const s = String(text || "");
  if (s.length <= 4000) {
    return s;
  }
  return `${s.length}:${s.slice(0, 2000)}:${s.slice(-2000)}`;
};

const readImportJob = () => {
  try {
    const raw = window.localStorage.getItem(IMPORT_JOB_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const writeImportJob = (job) => {
  try {
    if (!job) {
      window.localStorage.removeItem(IMPORT_JOB_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(IMPORT_JOB_STORAGE_KEY, JSON.stringify(job));
  } catch {
    // ignore quota / private mode
  }
};

const chunkTextByLines = (rawText, maxChars = 6000, overlapChars = 240) => {
  const text = String(rawText || "");
  if (text.length <= maxChars) {
    return [text];
  }

  const lines = text.split(/\r?\n/);
  const chunks = [];
  let current = "";

  const pushChunk = () => {
    if (!current.trim()) return;
    chunks.push(current.trimEnd());
    current = "";
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const next = current ? `${current}\n${line}` : line;

    if (next.length > maxChars) {
      pushChunk();

      // If a single line is enormous, hard-split it.
      if (line.length > maxChars) {
        let start = 0;
        while (start < line.length) {
          const end = Math.min(start + maxChars, line.length);
          chunks.push(line.slice(start, end));
          start = Math.max(end - overlapChars, end);
        }
        continue;
      }

      current = line;
      continue;
    }

    current = next;
  }

  pushChunk();

  if (overlapChars > 0 && chunks.length > 1) {
    return chunks.map((chunk, idx) => {
      if (idx === 0) return chunk;
      const prevTail = chunks[idx - 1].slice(-overlapChars);
      return `${prevTail}\n${chunk}`.trim();
    });
  }

  return chunks;
};

const formatElapsed = (startedAt) => {
  const seconds = Math.max(Math.floor((Date.now() - startedAt) / 1000), 0);
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes > 0 ? `${minutes}м ${rest}с` : `${rest}с`;
};

const runImportStepWithProgress = async ({ statusEl, partIndex, total, request }) => {
  const startedAt = Date.now();
  const phases = [
    "отправляю фрагмент на сервер",
    "Google API получил запрос, модель читает лог",
    "модель собирает JSON для памяти мира",
    "ждём ответ модели и запись в базу",
  ];
  let phaseIndex = 0;

  const render = () => {
    setStatus(
      statusEl,
      `Импорт: часть ${partIndex}/${total}. Этап: ${phases[phaseIndex]}… Прошло ${formatElapsed(startedAt)}.`,
    );
  };

  render();
  const timer = window.setInterval(() => {
    phaseIndex = Math.min(phaseIndex + 1, phases.length - 1);
    render();
  }, 4500);

  try {
    return await request();
  } finally {
    window.clearInterval(timer);
  }
};

const importTranscriptProgressively = async ({
  campaignId,
  transcript,
  statusEl,
}) => {
  const chunks = chunkTextByLines(transcript, 9000, 180);
  const fp = fingerprintTranscript(transcript);
  const saved = readImportJob();
  let startIndex = 0;

  if (
    saved &&
    String(saved.campaignId) === String(campaignId) &&
    saved.fp === fp &&
    typeof saved.nextIndex === "number" &&
    saved.nextIndex > 0 &&
    saved.nextIndex < chunks.length
  ) {
    const ok = window.confirm(
      `Обнаружен незавершённый импорт: часть ${saved.nextIndex + 1}/${chunks.length}.\n\nПродолжить с этой части? (Нет — начать заново)`,
    );
    startIndex = ok ? saved.nextIndex : 0;
  }

  if (startIndex === 0) {
    writeImportJob(null);
  }

  for (let i = startIndex; i < chunks.length; i += 1) {
    const partIndex = i + 1;
    const total = chunks.length;
    setStatus(
      statusEl,
      `Импорт: часть ${partIndex}/${total}. Готовлю фрагмент для модели…`,
    );

    const framedTranscript = [
      `ИНСТРУКЦИЯ: это импорт лога старой кампании частями.`,
      `ЧАСТЬ ${partIndex} ИЗ ${total}.`,
      `Требование: извлеки факты и обнови базу мира (персонажи/локации/квесты/герой). Служебные заметки создавай только если факту нет места в других сущностях.`,
      `Формат JSON: role квестов/персонажей только латиницей: npc|enemy|ally|boss|merchant; kind квестов: main|side|hazard|deadline; category заметок: gm_note|canon|warning|loot|quest|manual; action заметок: upsert|delete.`,
      ``,
      chunks[i],
    ].join("\n");

    await runImportStepWithProgress({
      statusEl,
      partIndex,
      total,
      request: () => sendJson(`/api/campaigns/${campaignId}/import`, {
        transcript: framedTranscript,
        show_chat_summary: partIndex === total,
        api_key: readDemoTextApiKey() || null,
      }),
    });

    setStatus(
      statusEl,
      `Импорт: часть ${partIndex}/${total} записана в базу. ${partIndex < total ? "Перехожу к следующей части…" : "Финальная сводка готова."}`,
    );

    writeImportJob({
      campaignId: String(campaignId),
      fp,
      nextIndex: i + 1,
      total: chunks.length,
      updatedAt: Date.now(),
    });
  }

  writeImportJob(null);
};

const getShell = () => document.querySelector("[data-shell-root]");

const getCurrentViewMode = () => {
  const shellMode = getShell()?.dataset.viewMode;
  if (shellMode === "play" || shellMode === "dashboard") {
    return shellMode;
  }
  const queryMode = new URLSearchParams(window.location.search).get("view");
  return queryMode === "play" ? "play" : "dashboard";
};

const getCampaignUrl = (campaignId, options = {}) => {
  const params = new URLSearchParams();
  if (campaignId) {
    params.set("campaign_id", String(campaignId));
  }

  const viewMode = options.view || getCurrentViewMode();
  if (viewMode === "play") {
    params.set("view", "play");
  }

  const query = params.toString();
  return query ? `/?${query}` : "/";
};

const isNearBottom = (element) => {
  if (!element) return true;
  const gap = element.scrollHeight - element.scrollTop - element.clientHeight;
  return gap < 140;
};

const scrollChatToBottom = (force = false) => {
  const chatLog = document.getElementById("chat-log");
  if (!chatLog) return;
  if (force || isNearBottom(chatLog)) {
    chatLog.scrollTop = chatLog.scrollHeight;
  }
};

const parseDmEmotionLine = (line) => {
  const value = String(line || "").replace(/^\s*EMOTION\s*:/i, "").trim();
  if (!value) return null;

  const [rawEmotion, ...noteParts] = value.split("|");
  const emotion = normalizeSceneEmotion(rawEmotion.trim() || "neutral");
  const rawNote = noteParts.join("|").trim();
  const label = SCENE_EMOTION_LABELS[emotion] || SCENE_EMOTION_LABELS.neutral;
  const note = rawNote || `[${label.toLowerCase()} и наблюдает за сценой.]`;

  return {
    emotion,
    label,
    note: note.startsWith("[") ? note : `[${note}]`,
  };
};

const parseDmVoiceTimelineLine = (line) => {
  const raw = String(line || "").replace(/^\s*(?:VOICE_TIMELINE|EMOTION_TIMELINE|TTS_TIMELINE)\s*:/i, "").trim();
  if (!raw) return [];

  try {
    const parsed = JSON.parse(raw);
    return normalizeVoiceTimelineItems(Array.isArray(parsed) ? parsed : [parsed]);
  } catch {
    return [];
  }
};

const normalizeTtsRate = (value, fallback = "+0%") => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${Math.max(-45, Math.min(45, Math.round((value - 1) * 100)))}%`;
  }
  const raw = String(value ?? "").trim();
  if (/^[+-]?\d{1,3}%$/.test(raw)) return raw.startsWith("+") || raw.startsWith("-") ? raw : `+${raw}`;
  const numeric = Number(raw);
  if (Number.isFinite(numeric) && numeric > 0 && numeric < 2) {
    return `${Math.max(-45, Math.min(45, Math.round((numeric - 1) * 100)))}%`;
  }
  return fallback;
};

const normalizeTtsPitch = (value, fallback = "+0Hz") => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return `${Math.max(-80, Math.min(80, Math.round((value - 1) * 60)))}Hz`;
  }
  const raw = String(value ?? "").trim();
  if (/^[+-]?\d{1,3}Hz$/i.test(raw)) return raw.startsWith("+") || raw.startsWith("-") ? raw : `+${raw}`;
  const numeric = Number(raw);
  if (Number.isFinite(numeric) && numeric > 0 && numeric < 2) {
    return `${Math.max(-80, Math.min(80, Math.round((numeric - 1) * 60)))}Hz`;
  }
  return fallback;
};

const normalizeVoiceTimelineItems = (items) => {
  if (!Array.isArray(items)) return [];
  return items.slice(0, 3).map((item, index) => {
    const emotion = normalizeSceneEmotion(item?.emotion || item?.mood || "neutral");
    const defaults = SCENE_TTS_BY_EMOTION[emotion] || SCENE_TTS_BY_EMOTION.neutral;
    return {
      line: Number.isFinite(Number(item?.line)) ? Number(item.line) : index + 1,
      speaker: String(item?.speaker || item?.voice || "DM").slice(0, 80),
      emotion,
      rate: normalizeTtsRate(item?.rate, defaults.rate),
      pitch: normalizeTtsPitch(item?.pitch, defaults.pitch),
      pauseMs: Number.isFinite(Number(item?.pause_ms ?? item?.pauseMs))
        ? Number(item.pause_ms ?? item.pauseMs)
        : defaults.pauseMs,
    };
  });
};

const parseVoiceTimelinePayload = (payload) => {
  const raw = String(payload || "").replace(/^\s*(?:VOICE_TIMELINE|EMOTION_TIMELINE|TTS_TIMELINE)\s*:/i, "").trim();
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return normalizeVoiceTimelineItems(Array.isArray(parsed) ? parsed : [parsed]);
  } catch {
    return [];
  }
};

const extractVoiceTimeline = (rawText) => {
  const raw = String(rawText || "");
  const prefixed = raw.match(/^\s*(?:VOICE_TIMELINE|EMOTION_TIMELINE|TTS_TIMELINE)\s*:\s*([\s\S]*?)(?=\n\s*(?:DM|LOC|NPC|EMOTION|DM_SYSTEM)\s*:|\n\[DM_SYSTEM\]|\n\[\/DM_SYSTEM\]|\s*$)/im);
  const fromPrefix = parseVoiceTimelinePayload(prefixed?.[1] || "");
  if (fromPrefix.length) return fromPrefix;

  const jsonCandidate = raw.match(/(\[\s*\{[\s\S]{0,2600}?"(?:speaker|emotion|rate|pitch|pause_ms|pauseMs)"[\s\S]{0,2600}?\}\s*\]|\{\s*[\s\S]{0,1600}?"(?:speaker|emotion|rate|pitch|pause_ms|pauseMs)"[\s\S]{0,1600}?\})/i);
  return parseVoiceTimelinePayload(jsonCandidate?.[1] || "");
};

const isTimelineJunkLine = (line) => {
  const text = String(line || "").trim();
  if (!text) return false;
  if (/^(?:VOICE_TIMELINE|EMOTION_TIMELINE|TTS_TIMELINE)\s*:/i.test(text)) return true;
  if (/^[\[{,}\]\s]*$/.test(text) && /[\[{}\]]/.test(text)) return true;
  return /^[\[{]?\s*"?(?:line|speaker|emotion|rate|pitch|pause_ms|pauseMs)"?\s*:/i.test(text)
    || /"(?:line|speaker|emotion|rate|pitch|pause_ms|pauseMs)"\s*:/.test(text);
};

const removeHiddenServiceLines = (lines) => {
  let timelineDepth = 0;
  return lines.filter((line) => {
    const text = String(line || "");
    const trimmed = text.trim();
    const startsTimeline = /^(?:VOICE_TIMELINE|EMOTION_TIMELINE|TTS_TIMELINE)\s*:/i.test(trimmed)
      || (/^[\[{]/.test(trimmed) && /"(?:speaker|emotion|rate|pitch|pause_ms|pauseMs)"\s*:/.test(trimmed));
    if (startsTimeline || timelineDepth > 0 || isTimelineJunkLine(trimmed)) {
      timelineDepth += (text.match(/[\[{]/g) || []).length;
      timelineDepth -= (text.match(/[\]}]/g) || []).length;
      timelineDepth = Math.max(0, timelineDepth);
      return false;
    }
    return !/^\s*EMOTION\s*:/i.test(trimmed);
  });
};

const fallbackEmotionNote = (emotion) => {
  const normalized = normalizeSceneEmotion(emotion);
  const label = SCENE_EMOTION_LABELS[normalized] || SCENE_EMOTION_LABELS.neutral;
  const notes = {
    neutral: "[Тихо сверяюсь с заметками и держу сцену ровно.]",
    joy: "[Едва заметно улыбаюсь и оживляю сцену.]",
    surprised: "[Моргаю, поправляю очки и быстро пересчитываю риски.]",
    angry: "[Сухо хмурюсь и сжимаю воображаемый d20.]",
    fear: "[Замираю на полсекунды и говорю тише.]",
    shock: "[Осторожно выдыхаю и смотрю на кубики с подозрением.]",
    glasses: "[Поправляю очки и включаю режим серьёзного DM.]",
  };
  return { emotion: normalized, label, note: notes[normalized] || notes.neutral };
};

const stripSceneLinePrefix = (line) =>
  String(line || "")
    .replace(/^\s*DM\s*:\s*/i, "")
    .replace(/^\s*LOC\s*:\s*/i, "")
    .replace(/^\s*(?:NPC|НПС)\s*[:<]?\s*[^:>—-]+?\s*[>:—-]\s*/iu, "")
    .replace(/^\s*(?:NPC|НПС)\s*<?[^:>]+>?\s*:\s*/iu, "");

const parseNpcLine = (line) => {
  const trimmed = String(line || "").trim();
  const explicit = trimmed.match(/^\s*(?:NPC|НПС)\s*[:<]?\s*([^:>—-]+?)\s*[>:—-]\s*(.*)$/iu);
  if (explicit?.[1]) {
    return {
      speaker: explicit[1].trim(),
      text: String(explicit[2] || "").trim(),
    };
  }
  const colon = trimmed.match(/^\s*(?:NPC|НПС)\s*<?([^:>]+)>?\s*:\s*(.*)$/iu);
  if (colon?.[1]) {
    return {
      speaker: colon[1].trim(),
      text: String(colon[2] || "").trim(),
    };
  }
  return null;
};

const detectLineSpeaker = (line) => {
  const trimmed = String(line || "").trim();
  const npcMatch = parseNpcLine(trimmed);
  if (npcMatch?.speaker) return npcMatch.speaker;
  if (/^LOC\s*:/i.test(trimmed)) return "Narrator";
  return "DM";
};

const inferLineEmotion = (line, speaker, fallbackEmotion) => {
  const text = String(line || "");
  const lower = `${speaker || ""} ${text}`.toLowerCase();
  if (/[!?]{2,}|в ужасе|паник|кошмар|страш/i.test(text)) return "fear";
  if (/!/.test(text)) return lower.includes("зл") || lower.includes("ярост") ? "angry" : "surprised";
  if (/\?/.test(text)) return "surprised";
  if (lower.includes("элли")) return "joy";
  return normalizeSceneEmotion(fallbackEmotion || "neutral");
};

const stripTtsMarkup = (text) =>
  String(text || "")
    .replace(/^\s*(?:DM|LOC)\s*:\s*/i, "")
    .replace(/[*_`#]+/g, "")
    .replace(/\([^)]{0,120}\)\s*$/g, "")
    .replace(/[{}]/g, "")
    .replace(/\s{2,}/g, " ")
    .trim();

const stripVisibleTtsDirectives = (text) =>
  String(text || "")
    .replace(/\[(?:whispering|shouting|angry|excited|sad|sarcastic|laughs|sighs|gasp|cough|yawn)\]/gi, "")
    .replace(/<break\b[^>]*\/?>/gi, "")
    .replace(/<\/?prosody\b[^>]*>/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();

const cleanLineForTts = (line) => {
  const npc = parseNpcLine(line);
  if (npc) {
    const cleanNpcText = stripTtsMarkup(npc.text);
    return cleanNpcText || "";
  }
  return stripTtsMarkup(line);
};

const formatNpcLineForDisplay = (line) => {
  const npc = parseNpcLine(line);
  if (!npc?.speaker) return null;
  const cleanText = stripVisibleTtsDirectives(stripTtsMarkup(npc.text));
  const speaker = npc.speaker.replace(/\s+/g, " ").trim();
  return cleanText ? `${speaker} - ${cleanText}` : `${speaker} -`;
};

const splitTtsPhrases = (text) => {
  const source = String(text || "").trim();
  if (!source) return [];
  const matches = source.match(/[^.!?…]+[.!?…]+["»“”']?|[^.!?…]+$/g) || [source];
  return matches
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 6);
};

const buildTtsPlan = (visibleLines, baseEmotion, timeline) => {
  const timelineByLine = new Map((timeline || []).map((item) => [Number(item.line), item]));
  return visibleLines
    .flatMap((line, index) => {
      const trimmed = String(line || "").trim();
      if (!trimmed) return [];
      const lineNumber = index + 1;
      const planned = timelineByLine.get(lineNumber);
      const speaker = planned?.speaker || detectLineSpeaker(trimmed);
      const emotion = inferLineEmotion(trimmed, speaker, planned?.emotion || baseEmotion || "neutral");
      const defaults = SCENE_TTS_BY_EMOTION[emotion] || SCENE_TTS_BY_EMOTION.neutral;
      const phrases = splitTtsPhrases(cleanLineForTts(trimmed));
      return phrases.map((phrase, phraseIndex) => ({
        line: lineNumber,
        speaker,
        emotion,
        rate: normalizeTtsRate(planned?.rate, defaults.rate),
        pitch: normalizeTtsPitch(planned?.pitch, defaults.pitch),
        pauseMs: phraseIndex === phrases.length - 1 ? (planned?.pauseMs ?? defaults.pauseMs) : 10,
        text: phrase,
      }));
    })
    .filter((item) => item && item.text);
};

const readStoredMap = (storageKey) => {
  try {
    const raw = window.localStorage.getItem(storageKey);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
};

const writeStoredMap = (storageKey, value) => {
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(value));
  } catch {
    // ignore storage issues
  }
};

const getPlayRoot = () => document.querySelector("[data-view-mode='play']");

const syncSceneClock = (root = document) => {
  const playRoot = root.matches?.("[data-view-mode='play']") ? root : getPlayRoot();
  const clock = playRoot?.querySelector("[data-scene-clock]");
  if (!clock) return;

  const now = new Date();
  clock.textContent = now.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
};

const readScenePanelPreference = (campaignId) => {
  const all = readStoredMap(SCENE_PANEL_STORAGE_KEY);
  return all[String(campaignId || "")] || "scene";
};

const writeScenePanelPreference = (campaignId, panelName) => {
  if (!campaignId) return;
  const all = readStoredMap(SCENE_PANEL_STORAGE_KEY);
  all[String(campaignId)] = panelName;
  writeStoredMap(SCENE_PANEL_STORAGE_KEY, all);
};

const readSceneEmotionPreference = (campaignId) => {
  const all = readStoredMap(SCENE_EMOTION_STORAGE_KEY);
  return all[String(campaignId || "")] || "auto";
};

const writeSceneEmotionPreference = (campaignId, emotionName) => {
  if (!campaignId) return;
  const all = readStoredMap(SCENE_EMOTION_STORAGE_KEY);
  all[String(campaignId)] = emotionName;
  writeStoredMap(SCENE_EMOTION_STORAGE_KEY, all);
};

const getLastAssistantBubble = (root = document) => {
  const bubbles = root.querySelectorAll(".message-bubble.assistant");
  return bubbles[bubbles.length - 1] || null;
};

const hashTtsText = (value) => {
  let hash = 0;
  const text = String(value || "");
  for (let index = 0; index < text.length; index += 1) {
    hash = ((hash << 5) - hash + text.charCodeAt(index)) | 0;
  }
  return String(hash);
};

const isSceneTtsEnabled = () => {
  try {
    return window.localStorage.getItem(SCENE_TTS_ENABLED_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
};

const writeSceneTtsEnabled = (enabled) => {
  try {
    window.localStorage.setItem(SCENE_TTS_ENABLED_STORAGE_KEY, enabled ? "true" : "false");
  } catch {
    // ignore storage issues
  }
};

const readSceneTtsProvider = () => {
  try {
    const stored = window.localStorage.getItem(SCENE_TTS_PROVIDER_STORAGE_KEY);
    return SCENE_TTS_PROVIDERS[stored] ? stored : SCENE_TTS_DEFAULT_PROVIDER;
  } catch {
    return SCENE_TTS_DEFAULT_PROVIDER;
  }
};

const writeSceneTtsProvider = (provider) => {
  const normalized = SCENE_TTS_PROVIDERS[provider] ? provider : SCENE_TTS_DEFAULT_PROVIDER;
  try {
    window.localStorage.setItem(SCENE_TTS_PROVIDER_STORAGE_KEY, normalized);
  } catch {
    // ignore storage issues
  }
  return normalized;
};

const getSceneTtsProviderMeta = () =>
  SCENE_TTS_PROVIDERS[readSceneTtsProvider()] || SCENE_TTS_PROVIDERS[SCENE_TTS_DEFAULT_PROVIDER];

const setSceneTtsStatus = (root = document, message = "", tone = "idle") => {
  const playRoot = root.matches?.("[data-view-mode='play']") ? root : getPlayRoot();
  if (!playRoot) return;
  playRoot.querySelectorAll("[data-voice-status]").forEach((status) => {
    const text = String(message || "");
    status.textContent = text;
    status.title = text;
    status.dataset.voiceTone = tone;
  });
};

const setScenePlaybackState = (root = document, state = "idle") => {
  const playRoot = root?.matches?.("[data-view-mode='play']") ? root : getPlayRoot();
  if (!playRoot) return;
  window.__rpgDmTtsState = state;
  playRoot.querySelectorAll("[data-voice-replay]").forEach((button) => {
    const isSpeaking = state === "speaking";
    const isPaused = state === "paused";
    button.dataset.playbackState = state;
    button.innerHTML = isSpeaking ? PAUSE_ICON_SVG : PLAY_ICON_SVG;
    button.setAttribute("aria-label", isSpeaking ? "Поставить озвучку на паузу" : isPaused ? "Продолжить озвучку" : "Проиграть последний ответ Gemma");
    button.classList.toggle("is-speaking", isSpeaking);
    button.classList.toggle("is-paused", isPaused);
  });
};

const syncSceneVoiceToggle = (root = document) => {
  const playRoot = root.matches?.("[data-view-mode='play']") ? root : getPlayRoot();
  if (!playRoot) return;
  const enabled = isSceneTtsEnabled();
  const provider = readSceneTtsProvider();
  playRoot.querySelectorAll("[data-voice-toggle]").forEach((button) => {
    button.classList.toggle("is-enabled", enabled);
    button.classList.toggle("is-disabled", !enabled);
    button.setAttribute("aria-pressed", String(enabled));
    const text = button.querySelector("[data-voice-state-text]");
    if (text) text.textContent = enabled ? "ВКЛ" : "ВЫКЛ";
  });
  playRoot.querySelectorAll("[data-voice-provider]").forEach((select) => {
    select.value = provider;
  });
  setSceneTtsStatus(playRoot, enabled ? "Авточтение готово" : "Авточтение выключено", enabled ? "ready" : "idle");
  setScenePlaybackState(playRoot, window.__rpgDmTtsState || "idle");
};

const stopSceneTts = () => {
  window.__rpgDmTtsRunId = (window.__rpgDmTtsRunId || 0) + 1;
  window.__rpgDmTtsController?.abort?.();
  window.__rpgDmTtsController = null;
  if (window.__rpgDmCurrentAudio) {
    window.__rpgDmCurrentAudio.pause();
    window.__rpgDmCurrentAudio = null;
  }
  setScenePlaybackState(getPlayRoot() || document, "idle");
};

const pauseSceneTts = () => {
  const audio = window.__rpgDmCurrentAudio;
  if (!audio || audio.paused) return false;
  audio.pause();
  setScenePlaybackState(getPlayRoot() || document, "paused");
  setSceneTtsStatus(getPlayRoot() || document, "Пауза", "ready");
  return true;
};

const resumeSceneTts = async () => {
  const audio = window.__rpgDmCurrentAudio;
  if (!audio || !audio.paused) return false;
  await audio.play();
  setScenePlaybackState(getPlayRoot() || document, "speaking");
  setSceneTtsStatus(getPlayRoot() || document, getSceneTtsProviderMeta().status, "speaking");
  return true;
};

const waitForTtsPause = (ms, signal) => new Promise((resolve) => {
  const timerId = window.setTimeout(resolve, Math.max(0, Number(ms) || 0));
  signal?.addEventListener("abort", () => {
    window.clearTimeout(timerId);
    resolve();
  }, { once: true });
});

const getSceneTtsAudioCache = () => {
  if (!window.__rpgDmTtsAudioCache) {
    window.__rpgDmTtsAudioCache = new Map();
  }
  return window.__rpgDmTtsAudioCache;
};

const makeTtsCacheKey = (providerMeta, segment) => [
  providerMeta.endpoint || "",
  providerMeta.model || "",
  String(segment?.speaker || "DM"),
  normalizeSceneEmotion(segment?.emotion || "neutral"),
  String(segment?.text || "").trim(),
].join("\u241f");

const rememberTtsBlob = (key, blob) => {
  const cache = getSceneTtsAudioCache();
  if (cache.has(key)) cache.delete(key);
  cache.set(key, blob);
  while (cache.size > SCENE_TTS_AUDIO_CACHE_LIMIT) {
    cache.delete(cache.keys().next().value);
  }
};

const applyPlaybackEmotion = (root, emotion, { preserveTimers = false } = {}) => {
  const playRoot = root?.matches?.("[data-view-mode='play']") ? root : getPlayRoot();
  if (!playRoot) return;
  const campaignId = playRoot.dataset.campaignId || "";
  if (readSceneEmotionPreference(campaignId) !== "auto") return;
  if (!preserveTimers) {
    clearSceneEmotionTimers();
  }
  setSceneSpriteEmotion(playRoot, emotion);
};

const playTtsBlob = (blob, signal, segment = null, root = document, emotionCues = null) => new Promise((resolve, reject) => {
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  window.__rpgDmCurrentAudio = audio;
  setScenePlaybackState(getPlayRoot() || document, "speaking");
  if (segment?.emotion) {
    applyPlaybackEmotion(root, segment.emotion);
  }

  const cleanup = () => {
    URL.revokeObjectURL(url);
    if (window.__rpgDmCurrentAudio === audio) {
      window.__rpgDmCurrentAudio = null;
    }
  };

  signal?.addEventListener("abort", () => {
    audio.pause();
    cleanup();
    resolve();
  }, { once: true });

  audio.addEventListener("ended", () => {
    cleanup();
    resolve();
  }, { once: true });
  audio.addEventListener("loadedmetadata", () => {
    schedulePlaybackEmotionCues(root, emotionCues, audio);
  }, { once: true });
  audio.addEventListener("error", () => {
    cleanup();
    reject(new Error("Не удалось воспроизвести аудио TTS."));
  }, { once: true });

  audio.play().catch((error) => {
    cleanup();
    reject(error);
  });
});

const fetchTtsSegmentBlob = async (segment, signal) => {
  const providerMeta = getSceneTtsProviderMeta();
  const cacheKey = makeTtsCacheKey(providerMeta, segment);
  const cached = getSceneTtsAudioCache().get(cacheKey);
  if (cached) {
    return cached;
  }
  const response = await fetch(providerMeta.endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      segment,
      model: providerMeta.model || null,
      api_key: providerMeta.endpoint === "/api/tts/google" ? readDemoVoiceApiKey() || null : null,
    }),
    signal,
  });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }
  const blob = await response.blob();
  rememberTtsBlob(cacheKey, blob);
  return blob;
};

const readLatestTtsPlan = (root = document) => {
  const bubble = getLastAssistantBubble(root);
  if (!bubble) return { bubble: null, plan: [], fingerprint: "" };
  let plan = [];
  try {
    plan = JSON.parse(bubble.dataset.ttsPlan || "[]");
  } catch {
    plan = [];
  }
  const raw = bubble.querySelector(".message-body")?.dataset.rawBody || bubble.textContent || "";
  return {
    bubble,
    plan: Array.isArray(plan) ? plan.filter((item) => String(item?.text || "").trim()).slice(0, 60) : [],
    fingerprint: hashTtsText(raw),
  };
};

const toTtsApiSegment = (segment) => ({
  text: String(segment?.text || "").trim(),
  speaker: String(segment?.speaker || "DM").slice(0, 80),
  emotion: normalizeSceneEmotion(segment?.emotion || "neutral"),
  rate: normalizeTtsRate(segment?.rate, (SCENE_TTS_BY_EMOTION[normalizeSceneEmotion(segment?.emotion)] || SCENE_TTS_BY_EMOTION.neutral).rate),
  pitch: normalizeTtsPitch(segment?.pitch, (SCENE_TTS_BY_EMOTION[normalizeSceneEmotion(segment?.emotion)] || SCENE_TTS_BY_EMOTION.neutral).pitch),
  pauseMs: Number.isFinite(Number(segment?.pauseMs ?? segment?.pause_ms))
    ? Math.min(160, Number(segment.pauseMs ?? segment.pause_ms))
    : (SCENE_TTS_BY_EMOTION[normalizeSceneEmotion(segment?.emotion)] || SCENE_TTS_BY_EMOTION.neutral).pauseMs,
});

const splitGoogleTtsSegments = (segments, { maxChars = SCENE_GOOGLE_TTS_MAX_CHARS, hardChars = SCENE_GOOGLE_TTS_HARD_CHARS } = {}) => {
  if (!Array.isArray(segments) || !segments.length) return [];
  const chunks = [];
  let current = "";
  let currentMeta = null;

  const flush = (meta = currentMeta) => {
    const text = current.trim();
    if (text) {
      chunks.push({
        text: text.slice(0, hardChars),
        speaker: String(meta?.speaker || "DM").slice(0, 80),
        emotion: normalizeSceneEmotion(meta?.emotion || "neutral"),
        rate: "+0%",
        pitch: "+0Hz",
        pauseMs: 0,
      });
    }
    current = "";
    currentMeta = null;
  };

  const pushPart = (part, meta) => {
    const text = String(part || "").trim();
    if (!text) return;
    const normalizedMeta = {
      speaker: String(meta?.speaker || "DM").trim() || "DM",
      emotion: normalizeSceneEmotion(meta?.emotion || "neutral"),
    };
    const separator = current ? " " : "";
    const metaChanged = currentMeta
      && (currentMeta.speaker !== normalizedMeta.speaker || currentMeta.emotion !== normalizedMeta.emotion);
    if (current && (metaChanged || current.length + separator.length + text.length > maxChars)) {
      flush();
    }
    if (text.length <= hardChars) {
      currentMeta = normalizedMeta;
      current += (current ? " " : "") + text;
      return;
    }

    const sentences = text.match(/[^.!?…]+[.!?…]+["»“”']?|[^.!?…]+$/g) || [text];
    sentences.forEach((sentence) => {
      const sentenceText = String(sentence || "").trim();
      if (!sentenceText) return;
      if (current && current.length + 1 + sentenceText.length > maxChars) {
        flush();
      }
      if (sentenceText.length <= hardChars) {
        currentMeta = normalizedMeta;
        current += (current ? " " : "") + sentenceText;
        return;
      }
      for (let start = 0; start < sentenceText.length; start += hardChars) {
        if (current) flush();
        chunks.push({
          text: sentenceText.slice(start, start + hardChars).trim(),
          speaker: normalizedMeta.speaker,
          emotion: normalizedMeta.emotion,
          rate: "+0%",
          pitch: "+0Hz",
          pauseMs: 0,
        });
      }
    });
  };

  segments.slice(0, 80).forEach((segment) => {
    const text = String(segment?.text || "").replace(/\n{3,}/g, "\n\n").trim();
    if (!text) return;
    text.split(/\n{2,}|\n/g).forEach((paragraph) => {
      pushPart(paragraph, segment);
    });
  });
  flush();

  return chunks.filter((chunk) => chunk.text);
};

const combineGoogleTtsSegments = (segments) => {
  if (!Array.isArray(segments) || !segments.length) return [];
  const parts = [];
  let lastSpeaker = "";
  segments.forEach((segment) => {
    const line = String(segment?.text || "").trim();
    if (!line) return;
    const speaker = String(segment?.speaker || "DM").trim() || "DM";
    const isNarration = /^(?:DM|Narrator|Ведущий|Рассказчик)$/i.test(speaker);
    if (!isNarration && speaker !== lastSpeaker) {
      parts.push(`${speaker}: ${line}`);
    } else {
      parts.push(line);
    }
    lastSpeaker = isNarration ? "" : speaker;
  });
  const text = parts.join("\n").trim();
  if (!text) return [];
  const first = segments[0] || {};
  if (text.length <= SCENE_GOOGLE25_TTS_HARD_CHARS) {
    return [{
      text,
      speaker: String(first.speaker || "DM").slice(0, 80),
      emotion: normalizeSceneEmotion(first.emotion || "neutral"),
      rate: "+0%",
      pitch: "+0Hz",
      pauseMs: 0,
    }];
  }
  return splitGoogleTtsSegments([{ ...first, text }], {
    maxChars: SCENE_GOOGLE25_TTS_MAX_CHARS,
    hardChars: SCENE_GOOGLE25_TTS_HARD_CHARS,
  });
};

const buildCombinedEmotionCues = (segments) => {
  const source = Array.isArray(segments) ? segments.filter((segment) => String(segment?.text || "").trim()) : [];
  const totalChars = source.reduce((sum, segment) => sum + String(segment.text || "").trim().length, 0);
  if (!source.length || totalChars <= 0) return [];
  let cursor = 0;
  const cues = [];
  source.forEach((segment) => {
    const textLength = String(segment.text || "").trim().length;
    const emotion = normalizeSceneEmotion(segment.emotion || "neutral");
    const at = Math.min(0.95, Math.max(0, cursor / totalChars));
    const previous = cues[cues.length - 1];
    if (!previous || previous.emotion !== emotion) {
      cues.push({ at, emotion });
    }
    cursor += textLength;
  });
  return cues.slice(0, 6);
};

const schedulePlaybackEmotionCues = (root, cues, audio) => {
  const playRoot = root?.matches?.("[data-view-mode='play']") ? root : getPlayRoot();
  if (!playRoot || !Array.isArray(cues) || !cues.length || !audio) return;
  const campaignId = playRoot.dataset.campaignId || "";
  if (readSceneEmotionPreference(campaignId) !== "auto") return;
  clearSceneEmotionTimers();
  cues.forEach((cue) => {
    const applyCue = () => applyPlaybackEmotion(playRoot, cue.emotion, { preserveTimers: true });
    if (!Number.isFinite(audio.duration) || audio.duration <= 0 || cue.at <= 0.01) {
      if (cue.at <= 0.01) applyCue();
      return;
    }
    const timerId = window.setTimeout(applyCue, Math.max(0, audio.duration * cue.at * 1000));
    window.__rpgDmEmotionTimers.push(timerId);
  });
};

const speakLatestSceneTts = async (root = document, { force = false } = {}) => {
  const playRoot = root.matches?.("[data-view-mode='play']") ? root : getPlayRoot();
  if (!playRoot || !isSceneTtsEnabled()) return;

  const { plan, fingerprint } = readLatestTtsPlan(playRoot);
  const campaignId = playRoot.dataset.campaignId || "default";
  const spokenMap = readStoredMap(SCENE_TTS_LAST_SPOKEN_STORAGE_KEY);
  if (!plan.length) {
    setSceneTtsStatus(playRoot, "Нет текста для озвучки", "error");
    return;
  }
  if (!force && spokenMap[campaignId] === fingerprint) return;

  stopSceneTts();
  const controller = new AbortController();
  const runId = window.__rpgDmTtsRunId || 0;
  window.__rpgDmTtsController = controller;
  spokenMap[campaignId] = fingerprint;
  writeStoredMap(SCENE_TTS_LAST_SPOKEN_STORAGE_KEY, spokenMap);
  setScenePlaybackState(playRoot, "speaking");
  setSceneTtsStatus(playRoot, getSceneTtsProviderMeta().status, "speaking");

  try {
    const provider = readSceneTtsProvider();
    let apiSegments = plan.map(toTtsApiSegment).filter((segment) => segment.text);
    if (provider === "google" || provider === "google25") {
      const combinedEmotionCues = provider === "google25" ? buildCombinedEmotionCues(apiSegments) : null;
      apiSegments = provider === "google25"
        ? combineGoogleTtsSegments(apiSegments)
        : splitGoogleTtsSegments(apiSegments);
      setSceneTtsStatus(playRoot, `Google TTS: ${apiSegments.length} фрагм. по абзацам`, "speaking");
      let nextBlob = apiSegments.length ? fetchTtsSegmentBlob(apiSegments[0], controller.signal) : null;
      for (let index = 0; index < apiSegments.length; index += 1) {
        if (controller.signal.aborted || runId !== window.__rpgDmTtsRunId) return;
        setSceneTtsStatus(playRoot, `Google TTS: загрузка ${index + 1}/${apiSegments.length}`, "speaking");
        const blob = await nextBlob;
        nextBlob = apiSegments[index + 1] ? fetchTtsSegmentBlob(apiSegments[index + 1], controller.signal) : null;
        setSceneTtsStatus(playRoot, `Google TTS: играет ${index + 1}/${apiSegments.length}`, "speaking");
        await playTtsBlob(
          blob,
          controller.signal,
          apiSegments[index],
          playRoot,
          provider === "google25" && index === 0 ? combinedEmotionCues : null,
        );
      }
    } else {
      let nextBlob = apiSegments.length ? fetchTtsSegmentBlob(apiSegments[0], controller.signal) : null;
      for (let index = 0; index < apiSegments.length; index += 1) {
        if (controller.signal.aborted || runId !== window.__rpgDmTtsRunId) return;
        const apiSegment = apiSegments[index];
        const blob = await nextBlob;
        nextBlob = apiSegments[index + 1] ? fetchTtsSegmentBlob(apiSegments[index + 1], controller.signal) : null;
        await playTtsBlob(blob, controller.signal, apiSegment, playRoot);
        await waitForTtsPause(apiSegment.pauseMs, controller.signal);
      }
    }
    setScenePlaybackState(playRoot, "idle");
    setSceneTtsStatus(playRoot, "Готово", "ready");
  } catch (error) {
    if (!controller.signal.aborted) {
      setScenePlaybackState(playRoot, "idle");
      setSceneTtsStatus(playRoot, String(error?.message || "Ошибка TTS").slice(0, 240), "error");
      console.warn("Scene TTS playback failed:", error);
    }
  }
};

const setSceneSpriteEmotion = (root, emotion) => {
  const normalized = normalizeSceneEmotion(emotion);
  root.querySelectorAll("[data-emotion-frame]").forEach((frame) => {
    frame.classList.toggle("is-active", frame.dataset.emotionFrame === normalized);
  });
};

const clearSceneEmotionTimers = () => {
  (window.__rpgDmEmotionTimers || []).forEach((timerId) => window.clearTimeout(timerId));
  window.__rpgDmEmotionTimers = [];
};

const scheduleSceneEmotionTimeline = (root, timeline) => {
  clearSceneEmotionTimers();
  const items = Array.isArray(timeline) ? timeline.slice(0, 3) : [];
  if (!root || !items.length) return;

  items.forEach((item, index) => {
    const delay = index === 0 ? 0 : 5200 * index;
    const timerId = window.setTimeout(() => {
      setSceneSpriteEmotion(root, item.emotion);
    }, delay);
    window.__rpgDmEmotionTimers.push(timerId);
  });
};

const detectAwaitingRoll = (text) => {
  const raw = String(text || "");
  return /(?:\bdc\b|d20|брос|куб|сложност|9\+|12\+|15\+|18\+|20\+)/i.test(raw);
};

const setTurnRollState = (root = document) => {
  const form = root.querySelector("#turn-form[data-scene-play-form='true']");
  if (!form) return;
  const lastAssistantBubble = getLastAssistantBubble(root);
  const body = lastAssistantBubble?.querySelector(".message-body")?.dataset.rawBody
    || lastAssistantBubble?.querySelector(".message-body")?.textContent
    || "";
  form.dataset.awaitingRoll = detectAwaitingRoll(body) ? "true" : "false";
};

const updateRollOutput = (root = document) => {
  const form = root.querySelector("#turn-form[data-scene-play-form='true']");
  if (!form) return;
  const output = form.querySelector("[data-roll-output]");
  const rawValue = form.querySelector("input[name='dice_result']")?.value || "";
  if (output) {
    output.textContent = rawValue || "";
  }
};

const animateSceneRoll = (button, value, root = document) => {
  const form = root.querySelector("#turn-form[data-scene-play-form='true']");
  const output = form?.querySelector("[data-roll-output]");
  if (!button || !output) return;

  button.classList.remove("is-rolling");
  void button.offsetWidth;
  button.classList.add("is-rolling");
  output.textContent = "";

  window.setTimeout(() => {
    output.textContent = String(value);
  }, 620);

  window.setTimeout(() => {
    button.classList.remove("is-rolling");
  }, 980);
};

const syncFixedStageLayout = (root = document) => {
  const playRoot = root.matches?.("[data-view-mode='play']") ? root : getPlayRoot();
  const wrap = playRoot?.querySelector("[data-fixed-stage-wrap]");
  if (!playRoot || !wrap) return;

  const scale = Math.min(
    window.innerWidth / DESIGN_WIDTH,
    window.innerHeight / DESIGN_HEIGHT,
  );
  const offsetX = Math.max((window.innerWidth - DESIGN_WIDTH * scale) / 2, 0);
  const offsetY = Math.max((window.innerHeight - DESIGN_HEIGHT * scale) / 2, 0);

  wrap.style.transform = "translate(" + offsetX + "px, " + offsetY + "px) scale(" + scale + ")";
  wrap.classList.add("is-ready");
};

const normalizeSceneEmotion = (emotionName) => {
  const value = String(emotionName || "").trim().toLowerCase();
  if (!value || value === "auto" || value.includes("\u0430\u0432\u0442\u043e")) return "neutral";
  if (value === "neutral" || value.includes("\u043d\u0435\u0439\u0442\u0440")) return "neutral";
  if (value === "joy" || value.includes("\u0440\u0430\u0434")) return "joy";
  if (value === "surprised" || value.includes("\u0443\u0434\u0438\u0432")) return "surprised";
  if (value === "angry" || value.includes("\u0437\u043b") || value.includes("\u0432\u043e\u0437\u043c\u0443")) return "angry";
  if (value === "fear" || value.includes("\u0441\u0442\u0440\u0430")) return "fear";
  if (value === "shock" || value.includes("\u0448\u043e\u043a")) return "shock";
  if (value === "glasses" || value.includes("\u043e\u0447\u043a")) return "glasses";
  return "neutral";
};

const resolveSceneEmotion = (root) => {
  const campaignId = root?.dataset.campaignId || "";
  const preferred = readSceneEmotionPreference(campaignId);
  const autoEmotion = normalizeSceneEmotion(getLastAssistantBubble(root)?.dataset.dmEmotion || "neutral");
  return preferred === "auto"
    ? { mode: "auto", emotion: autoEmotion }
    : { mode: preferred, emotion: normalizeSceneEmotion(preferred) };
};

const applySceneEmotion = (root = document) => {
  const playRoot = root.matches?.("[data-view-mode='play']") ? root : getPlayRoot();
  if (!playRoot) return;

  const { mode, emotion } = resolveSceneEmotion(playRoot);
  const label = playRoot.querySelector("[data-scene-emotion-label]");
  const pickerButtons = playRoot.querySelectorAll("[data-emotion-choice]");

  playRoot.dataset.selectedEmotion = mode;
  setSceneSpriteEmotion(playRoot, emotion);

  if (label) {
    const emotionLabel = SCENE_EMOTION_LABELS[emotion] || SCENE_EMOTION_LABELS.neutral;
    label.textContent = mode === "auto"
      ? SCENE_EMOTION_LABELS.auto + " · " + emotionLabel
      : "Вручную · " + emotionLabel;
  }

  pickerButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.emotionChoice === mode);
  });

  if (mode === "auto") {
    if (isSceneTtsEnabled()) {
      clearSceneEmotionTimers();
      return;
    }
    const rawTimeline = getLastAssistantBubble(playRoot)?.dataset.emotionTimeline || "[]";
    try {
      scheduleSceneEmotionTimeline(playRoot, JSON.parse(rawTimeline));
    } catch {
      clearSceneEmotionTimers();
    }
  } else {
    clearSceneEmotionTimers();
  }
};

const setActiveScenePanel = (panelName, options = {}) => {
  const playRoot = getPlayRoot();
  if (!playRoot) return;

  const drawer = playRoot.querySelector("[data-scene-drawer]");
  const buttons = playRoot.querySelectorAll("[data-scene-panel-button]");
  const panels = playRoot.querySelectorAll("[data-scene-panel]");
  const eyebrow = playRoot.querySelector("[data-scene-drawer-eyebrow]");
  const title = playRoot.querySelector("[data-scene-drawer-title]");
  const icon = playRoot.querySelector("[data-scene-drawer-icon]");
  const campaignId = playRoot.dataset.campaignId || "";
  const shouldOpen = options.open ?? true;
  const meta = PLAY_PANEL_META[panelName] || PLAY_PANEL_META.scene;

  buttons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.scenePanelButton === panelName);
  });

  panels.forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.scenePanel === panelName);
  });

  if (eyebrow) eyebrow.textContent = meta.eyebrow || "PANEL";
  if (title) title.textContent = meta.title || "\u041f\u0430\u043d\u0435\u043b\u044c";
  if (icon) {
    icon.className = `play-panel-icon ${meta.iconClass || "play-panel-icon--scene"}`;
    if (meta.iconSvg) icon.innerHTML = meta.iconSvg;
  }
  if (drawer) drawer.classList.toggle("is-open", shouldOpen);
  if (shouldOpen) {
    writeScenePanelPreference(campaignId, panelName);
  }
};

const syncPlayScene = (root = document) => {
  const playRoot = root.matches?.("[data-view-mode='play']") ? root : getPlayRoot();
  if (!playRoot) return;

  const campaignId = playRoot.dataset.campaignId || "";
  const desiredPanel = readScenePanelPreference(campaignId);
  setActiveScenePanel(desiredPanel, { open: true });
  applySceneEmotion(playRoot);
  setTurnRollState(playRoot);
  updateRollOutput(playRoot);
  syncFixedStageLayout(playRoot);
  syncSceneClock(playRoot);
  syncSceneVoiceToggle(playRoot);
};

const styleAssistantMessageBodies = () => {
  document.querySelectorAll(".message-bubble.assistant .message-body").forEach((bodyEl) => {
    if (!bodyEl.dataset.rawBody) {
      bodyEl.dataset.rawBody = bodyEl.textContent || "";
    }

    const raw = bodyEl.dataset.rawBody || "";
    if (!raw.trim()) return;

    const lines = raw.split(/\r?\n/);
    const emotionLine = lines.find((line) => /^EMOTION\s*:/i.test(line)) || "";
    const emotion = parseDmEmotionLine(emotionLine);
    const timeline = extractVoiceTimeline(raw);
    const cleaned = removeHiddenServiceLines(lines);
    const displayEmotion = emotion || (cleaned.some((line) => line.trim()) ? fallbackEmotionNote(timeline[0]?.emotion || "neutral") : null);

    const html = cleaned
      .map((line) => {
        const trimmed = line.trim();
        if (!trimmed) return "<div class=\"dm-line dm-empty\"></div>";
        const npcDisplayLine = formatNpcLineForDisplay(trimmed);
        const visibleLine = npcDisplayLine || stripVisibleTtsDirectives(stripSceneLinePrefix(trimmed));
        const safeLine = escapeHtml(visibleLine);
        if (/^\[РЕКАП\]/i.test(trimmed)) return `<div class="dm-line dm-recap">${trimmed}</div>`;
        if (/^DM\s*:/i.test(trimmed)) return `<div class="dm-line dm-narrative">${safeLine}</div>`;
        if (/^LOC\s*:/i.test(trimmed)) return `<div class="dm-line dm-location">${safeLine}</div>`;
        if (/^NPC\s*:/i.test(trimmed) || /^NPC\s*<.+?>\s*:/i.test(trimmed) || /^NPC\s*[^:]+:/i.test(trimmed)) {
          return `<div class="dm-line dm-npc">${safeLine}</div>`;
        }
        return `<div class="dm-line dm-narrative">${safeLine}</div>`;
      })
      .join("");

    const bubble = bodyEl.closest(".message-bubble");
    const firstTimelineEmotion = timeline[0]?.emotion;
    const baseEmotion = firstTimelineEmotion || displayEmotion?.emotion || "neutral";
    if (bubble) {
      bubble.setAttribute("data-dm-emotion", baseEmotion);
      bubble.setAttribute("data-emotion-timeline", JSON.stringify(timeline));
      bubble.setAttribute("data-tts-plan", JSON.stringify(buildTtsPlan(cleaned, baseEmotion, timeline)));
    }

    const emotionHtml = displayEmotion
      ? `<div class="dm-emotion-line"><span>${escapeHtml(displayEmotion.label || SCENE_EMOTION_LABELS[displayEmotion.emotion] || SCENE_EMOTION_LABELS.neutral)}</span>${escapeHtml(displayEmotion.note)}</div>`
      : "";
    bodyEl.innerHTML = `${emotionHtml}${html}`;
  });
};

const getTemplateTextarea = (tools) => {
  const form = tools?.closest("form");
  return form?.querySelector("[data-prompt-template-textarea]");
};

const getSelectedPromptTemplate = (tools) => {
  const select = tools?.querySelector("[data-prompt-template-select]");
  const rawIndex = select?.value;
  const index = rawIndex === "" || rawIndex === undefined ? -1 : Number(rawIndex);
  return {
    index,
    select,
    template: Number.isInteger(index) && index >= 0 ? readPromptTemplates()[index] : null,
  };
};

const refreshShell = async (campaignId, options = {}) => {
  const {
    url = getCampaignUrl(campaignId),
    pushUrl = false,
    replaceUrl = false,
    scrollToBottom = false,
    focusComposer = false,
  } = options;

  const existingChat = document.getElementById("chat-log");
  const shouldStickToBottom = scrollToBottom || isNearBottom(existingChat);

  const response = await fetch(url, {
    headers: { "X-Requested-With": "fetch" },
  });
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response));
  }

  const html = await response.text();
  const parsed = new DOMParser().parseFromString(html, "text/html");
  const nextShell = parsed.querySelector("[data-shell-root]");
  const currentShell = getShell();
  if (!nextShell || !currentShell) {
    window.location.assign(url);
    return;
  }

  currentShell.replaceWith(nextShell);
  if (parsed.title) {
    document.title = parsed.title;
  }

  if (pushUrl) {
    window.history.pushState({}, "", url);
  } else if (replaceUrl) {
    window.history.replaceState({}, "", url);
  }

  window.requestAnimationFrame(() => {
    refreshPromptTemplateSelectors();
    syncApiKeyForms(nextShell);
    scrollChatToBottom(shouldStickToBottom);
    styleAssistantMessageBodies();
    syncPlayScene();
    syncFixedStageLayout();
    speakLatestSceneTts(nextShell);
    if (focusComposer) {
      document.querySelector("#turn-form textarea[name='message']")?.focus();
    }
  });
};

const prefillStartPrompt = () => {
  const turnForm = document.getElementById("turn-form");
  const messageField = turnForm?.querySelector("textarea[name='message']");
  if (!messageField) return;
  messageField.value = START_PROMPT;
  messageField.focus();
};

document.addEventListener("DOMContentLoaded", () => {
  scrollChatToBottom(true);
  styleAssistantMessageBodies();
  refreshPromptTemplateSelectors();
  syncApiKeyForms();
  syncPlayScene();
  syncFixedStageLayout();
  speakLatestSceneTts();
});

window.setInterval(() => {
  syncSceneClock();
}, 30000);

document.addEventListener("click", async (event) => {
  document.querySelectorAll("[data-emotion-picker]").forEach((picker) => {
    if (!picker.hidden && !event.target.closest("[data-emotion-picker]") && !event.target.closest("[data-emotion-picker-toggle]")) {
      picker.hidden = true;
    }
  });

  const clearApiKeys = event.target.closest("[data-clear-api-keys]");
  if (clearApiKeys) {
    writeLocalValue(DEMO_TEXT_API_KEY_STORAGE_KEY, "");
    writeLocalValue(DEMO_VOICE_API_KEY_STORAGE_KEY, "");
    syncApiKeyForms();
    return;
  }

  const toggleButton = event.target.closest("[data-campaign-toggle]");
  if (toggleButton) {
    const card = toggleButton.closest("[data-campaign-card]");
    const extra = card?.querySelector(".campaign-extra");
    if (!card || !extra) return;
    const isOpen = card.classList.toggle("is-open");
    extra.classList.toggle("is-open", isOpen);
    toggleButton.setAttribute("aria-expanded", String(isOpen));
    return;
  }

  const prefillButton = event.target.closest("#prefill-start-button");
  if (prefillButton) {
    prefillStartPrompt();
    return;
  }

  const voiceReplay = event.target.closest("[data-voice-replay]");
  if (voiceReplay) {
    if (window.__rpgDmTtsState === "speaking") {
      if (pauseSceneTts()) {
        return;
      }
      stopSceneTts();
      setSceneTtsStatus(getPlayRoot() || document, "Остановлено", "ready");
      return;
    }
    if (window.__rpgDmTtsState === "paused" && await resumeSceneTts()) {
      return;
    }
    writeSceneTtsEnabled(true);
    syncSceneVoiceToggle();
    await speakLatestSceneTts(getPlayRoot() || document, { force: true });
    return;
  }

  const voiceToggle = event.target.closest("[data-voice-toggle]");
  if (voiceToggle) {
    const enabled = !isSceneTtsEnabled();
    writeSceneTtsEnabled(enabled);
    syncSceneVoiceToggle();
    if (enabled) {
      await speakLatestSceneTts(getPlayRoot() || document, { force: true });
    } else {
      stopSceneTts();
    }
    return;
  }

  const viewLink = event.target.closest("[data-view-link]");
  if (viewLink) {
    event.preventDefault();
    await refreshShell(null, {
      url: viewLink.href,
      pushUrl: true,
      scrollToBottom: true,
    });
    return;
  }

  const panelButton = event.target.closest("[data-scene-panel-button]");
  if (panelButton) {
    const playRoot = getPlayRoot();
    const drawer = playRoot?.querySelector("[data-scene-drawer]");
    if (!playRoot || !drawer) return;
    const panelName = panelButton.dataset.scenePanelButton;
    const isSamePanel = panelButton.classList.contains("is-active");
    const isDrawerOpen = drawer.classList.contains("is-open");
    if (isSamePanel && isDrawerOpen) {
      drawer.classList.remove("is-open");
      return;
    }
    setActiveScenePanel(panelName, { open: true });
    return;
  }

  const drawerCloseButton = event.target.closest("[data-scene-drawer-close]");
  if (drawerCloseButton) {
    getPlayRoot()?.querySelector("[data-scene-drawer]")?.classList.remove("is-open");
    return;
  }

  const sceneDetailsToggle = event.target.closest("[data-scene-details-toggle]");
  if (sceneDetailsToggle) {
    const details = sceneDetailsToggle.parentElement?.querySelector("[data-scene-details]");
    if (!details) return;
    const willOpen = details.hidden;
    details.hidden = !willOpen;
    sceneDetailsToggle.setAttribute("aria-expanded", String(willOpen));
    sceneDetailsToggle.textContent = willOpen ? "Скрыть" : "Подробнее";
    return;
  }

  const rollButton = event.target.closest("[data-roll-d20]");
  if (rollButton) {
    const form = rollButton.closest("form");
    const input = form?.querySelector("input[name='dice_result']");
    if (!form || !input) return;
    const rollValue = Math.floor(Math.random() * 20) + 1;
    input.value = String(rollValue);
    animateSceneRoll(rollButton, rollValue, getPlayRoot() || document);
    return;
  }

  const emotionToggle = event.target.closest("[data-emotion-picker-toggle]");
  if (emotionToggle) {
    const form = emotionToggle.closest("form");
    const picker = form?.querySelector("[data-emotion-picker]");
    if (!picker) return;
    picker.hidden = !picker.hidden;
    return;
  }

  const emotionChoice = event.target.closest("[data-emotion-choice]");
  if (emotionChoice) {
    const playRoot = getPlayRoot();
    const campaignId = playRoot?.dataset.campaignId || "";
    writeSceneEmotionPreference(campaignId, emotionChoice.dataset.emotionChoice || "auto");
    playRoot?.querySelector("[data-emotion-picker]")?.setAttribute("hidden", "");
    applySceneEmotion(playRoot || document);
    return;
  }

  const saveTemplateButton = event.target.closest("[data-save-prompt-template]");
  if (saveTemplateButton) {
    const tools = saveTemplateButton.closest("[data-prompt-template-tools]");
    const textarea = getTemplateTextarea(tools);
    const nameInput = tools?.querySelector("[data-prompt-template-name]");
    const { template: selectedTemplate } = getSelectedPromptTemplate(tools);
    const text = String(textarea?.value || "").trim();
    if (!text) {
      window.alert("Сначала напиши описание кампании, потом его можно сохранить.");
      return;
    }
    const name = String(nameInput?.value || selectedTemplate?.name || "").trim();
    if (!name) {
      window.alert("Впиши короткое название шаблона.");
      nameInput?.focus();
      return;
    }
    const templates = readPromptTemplates();
    const existingIndex = templates.findIndex((item) => item.name.toLowerCase() === name.toLowerCase());
    const nextItem = { name, text, updatedAt: Date.now() };
    let savedIndex = existingIndex;
    if (existingIndex >= 0) {
      templates[existingIndex] = nextItem;
    } else {
      templates.push(nextItem);
      savedIndex = templates.length - 1;
    }
    writePromptTemplates(templates);
    refreshPromptTemplateSelectors();
    const select = tools?.querySelector("[data-prompt-template-select]");
    if (select) select.value = String(savedIndex);
    if (nameInput) nameInput.value = nextItem.name;
    return;
  }

  const loadTemplateButton = event.target.closest("[data-load-prompt-template]");
  if (loadTemplateButton) {
    const tools = loadTemplateButton.closest("[data-prompt-template-tools]");
    const textarea = getTemplateTextarea(tools);
    const nameInput = tools?.querySelector("[data-prompt-template-name]");
    const { template } = getSelectedPromptTemplate(tools);
    if (!textarea || !template) return;
    textarea.value = template.text;
    if (nameInput) nameInput.value = template.name;
    textarea.focus();
    return;
  }

  const deleteTemplateButton = event.target.closest("[data-delete-prompt-template]");
  if (deleteTemplateButton) {
    const tools = deleteTemplateButton.closest("[data-prompt-template-tools]");
    const nameInput = tools?.querySelector("[data-prompt-template-name]");
    const { index, template } = getSelectedPromptTemplate(tools);
    const templates = readPromptTemplates();
    if (!template) return;
    if (!window.confirm(`Удалить шаблон "${template.name}"?`)) return;
    templates.splice(index, 1);
    writePromptTemplates(templates);
    refreshPromptTemplateSelectors();
    if (nameInput) nameInput.value = "";
    return;
  }

  const campaignLink = event.target.closest("[data-campaign-link]");
  if (campaignLink) {
    event.preventDefault();
    await refreshShell(null, {
      url: campaignLink.href,
      pushUrl: true,
      scrollToBottom: true,
    });
    return;
  }

  const noteDeleteButton = event.target.closest("[data-delete-note-id]");
  if (noteDeleteButton) {
    const campaignId = noteDeleteButton.dataset.campaignId;
    const noteId = noteDeleteButton.dataset.deleteNoteId;
    if (!campaignId || !noteId) return;
    if (!window.confirm("Удалить эту заметку?")) return;
    try {
      noteDeleteButton.disabled = true;
      await sendWithoutBody(`/api/campaigns/${campaignId}/notes/${noteId}`, "DELETE");
      await refreshShell(campaignId, { replaceUrl: true });
    } catch (error) {
      window.alert(error.message);
      noteDeleteButton.disabled = false;
    }
    return;
  }

  const campaignDeleteButton = event.target.closest("[data-delete-campaign-id]");
  if (campaignDeleteButton) {
    const campaignId = campaignDeleteButton.dataset.deleteCampaignId;
    const campaignTitle = campaignDeleteButton.dataset.deleteCampaignTitle || "эту кампанию";
    if (!campaignId) return;

    const currentCampaignId = new URLSearchParams(window.location.search).get("campaign_id");
    if (!window.confirm(`Удалить кампанию "${campaignTitle}"? Это удалит историю ходов, заметки и память мира.`)) {
      return;
    }

    try {
      campaignDeleteButton.disabled = true;
      await sendWithoutBody(`/api/campaigns/${campaignId}`, "DELETE");
      if (currentCampaignId === campaignId) {
        await refreshShell(null, { url: getCampaignUrl(null), pushUrl: true, scrollToBottom: true });
      } else {
        await refreshShell(currentCampaignId, { replaceUrl: true });
      }
    } catch (error) {
      window.alert(error.message);
      campaignDeleteButton.disabled = false;
    }
  }
});

document.addEventListener("change", (event) => {
  const voiceProvider = event.target.closest("[data-voice-provider]");
  if (voiceProvider) {
    const provider = writeSceneTtsProvider(voiceProvider.value);
    stopSceneTts();
    syncSceneVoiceToggle();
    setSceneTtsStatus(getPlayRoot() || document, `Провайдер: ${SCENE_TTS_PROVIDERS[provider].label}`, "ready");
    return;
  }

  const select = event.target.closest("[data-prompt-template-select]");
  if (!select) return;
  const tools = select.closest("[data-prompt-template-tools]");
  const nameInput = tools?.querySelector("[data-prompt-template-name]");
  const { template } = getSelectedPromptTemplate(tools);
  if (nameInput) {
    nameInput.value = template?.name || "";
  }
});

document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;

  if (form.matches("[data-api-key-form]")) {
    event.preventDefault();
    const formData = new FormData(form);
    writeLocalValue(DEMO_TEXT_API_KEY_STORAGE_KEY, formData.get("text_api_key"));
    writeLocalValue(DEMO_VOICE_API_KEY_STORAGE_KEY, formData.get("voice_api_key"));
    syncApiKeyForms();
    return;
  }

  if (form.id === "turn-form") {
    event.preventDefault();
    const status = document.getElementById("turn-status");
    const campaignId = form.dataset.campaignId;
    const formData = new FormData(form);
    const isScenePlayForm = form.dataset.scenePlayForm === "true";
    const payload = {
      message: String(formData.get("message") || "").trim(),
      dice_result: asNumber(formData.get("dice_result")),
      api_key: readDemoTextApiKey() || null,
    };

    if (isScenePlayForm && form.dataset.awaitingRoll !== "true") {
      payload.dice_result = null;
    }

    if (!payload.message) {
      setStatus(status, "Нужно описать действие героя.", true);
      return;
    }

    try {
      togglePending(form, true);
      setStatus(status, "DM думает и синхронизирует память мира...");
      await sendJson(`/api/campaigns/${campaignId}/messages`, payload);
      await refreshShell(campaignId, { replaceUrl: true, scrollToBottom: true, focusComposer: true });
    } catch (error) {
      setStatus(status, error.message, true);
    } finally {
      togglePending(form, false);
    }
    return;
  }

  if (form.id === "note-form") {
    event.preventDefault();
    const status = document.getElementById("note-status");
    const campaignId = form.dataset.campaignId;
    const formData = new FormData(form);
    const payload = {
      title: String(formData.get("title") || "").trim(),
      body: String(formData.get("body") || "").trim(),
      category: String(formData.get("category") || "manual"),
      importance: "medium",
      is_pinned: true,
    };

    if (!payload.title || !payload.body) {
      setStatus(status, "И заголовок, и текст заметки обязательны.", true);
      return;
    }

    try {
      togglePending(form, true);
      setStatus(status, "Сохраняю заметку...");
      await sendJson(`/api/campaigns/${campaignId}/notes`, payload);
      await refreshShell(campaignId, { replaceUrl: true });
    } catch (error) {
      setStatus(status, error.message, true);
    } finally {
      togglePending(form, false);
    }
    return;
  }

  if (form.id === "campaign-form") {
    event.preventDefault();
    const formData = new FormData(form);
    const payload = {
      title: String(formData.get("title") || "").trim(),
      setting_name: String(formData.get("setting_name") || "").trim(),
      goal: String(formData.get("goal") || "").trim(),
      tone: String(formData.get("tone") || "").trim(),
      system_prompt: String(formData.get("system_prompt") || "").trim(),
      model_id: String(formData.get("model_id") || "").trim() || null,
      hero_name: String(formData.get("hero_name") || "").trim(),
      hero_archetype: String(formData.get("hero_archetype") || "").trim(),
      hero_description: String(formData.get("hero_description") || "").trim(),
      hero_inventory_text: String(formData.get("hero_inventory_text") || "").trim(),
      brute_force: asNumber(formData.get("brute_force")) ?? 0,
      bureaucracy: asNumber(formData.get("bureaucracy")) ?? 0,
      soft_skills: asNumber(formData.get("soft_skills")) ?? 0,
      evasion: asNumber(formData.get("evasion")) ?? 0,
      hp: asNumber(formData.get("hp")) ?? 20,
      max_hp: asNumber(formData.get("max_hp")) ?? 20,
      stress: asNumber(formData.get("stress")) ?? 0,
      max_stress: asNumber(formData.get("max_stress")) ?? 7,
      scrap: asNumber(formData.get("scrap")) ?? 0,
    };

    try {
      togglePending(form, true);
      const data = await sendJson("/api/campaigns", payload);
      await refreshShell(data.campaign_id, {
        url: getCampaignUrl(data.campaign_id),
        pushUrl: true,
        scrollToBottom: true,
      });
    } catch (error) {
      window.alert(error.message);
    } finally {
      togglePending(form, false);
    }
    return;
  }

  if (form.id === "campaign-settings-form") {
    event.preventDefault();
    const status = document.getElementById("campaign-settings-status");
    const campaignId = form.dataset.campaignId;
    const formData = new FormData(form);
    const payload = {
      title: String(formData.get("title") || "").trim(),
      setting_name: String(formData.get("setting_name") || "").trim(),
      goal: String(formData.get("goal") || "").trim(),
      tone: String(formData.get("tone") || "").trim(),
      model_id: String(formData.get("model_id") || "").trim() || null,
      system_prompt: String(formData.get("system_prompt") || "").trim(),
    };

    if (!payload.title || !payload.setting_name || !payload.goal || !payload.system_prompt) {
      setStatus(status, "Название, сеттинг, цель и системный промпт обязательны.", true);
      return;
    }

    try {
      togglePending(form, true);
      setStatus(status, "Сохраняю настройки кампании...");
      await sendJson(`/api/campaigns/${campaignId}`, payload, "PATCH");
      await refreshShell(campaignId, { replaceUrl: true });
    } catch (error) {
      setStatus(status, error.message, true);
    } finally {
      togglePending(form, false);
    }
    return;
  }

  if (form.id === "hero-form") {
    event.preventDefault();
    const status = document.getElementById("hero-status");
    const campaignId = form.dataset.campaignId;
    const formData = new FormData(form);
    const payload = {
      name: String(formData.get("name") || "").trim(),
      archetype: String(formData.get("archetype") || "").trim(),
      description: String(formData.get("description") || "").trim(),
      status_text: String(formData.get("status_text") || "").trim(),
      current_location_name: String(formData.get("current_location_name") || "").trim(),
      inventory_text: String(formData.get("inventory_text") || "").trim(),
      brute_force: asNumber(formData.get("brute_force")) ?? 0,
      bureaucracy: asNumber(formData.get("bureaucracy")) ?? 0,
      soft_skills: asNumber(formData.get("soft_skills")) ?? 0,
      evasion: asNumber(formData.get("evasion")) ?? 0,
      hp: asNumber(formData.get("hp")) ?? 20,
      max_hp: asNumber(formData.get("max_hp")) ?? 20,
      stress: asNumber(formData.get("stress")) ?? 0,
      max_stress: asNumber(formData.get("max_stress")) ?? 7,
      scrap: asNumber(formData.get("scrap")) ?? 0,
    };

    if (!payload.name || !payload.archetype || !payload.description) {
      setStatus(status, "Имя, архетип и описание героя обязательны.", true);
      return;
    }

    try {
      togglePending(form, true);
      setStatus(status, "Сохраняю лист героя...");
      await sendJson(`/api/campaigns/${campaignId}/hero`, payload, "PATCH");
      await refreshShell(campaignId, { replaceUrl: true });
    } catch (error) {
      setStatus(status, error.message, true);
    } finally {
      togglePending(form, false);
    }
    return;
  }

  if (form.id === "import-form") {
    event.preventDefault();
    const status = document.getElementById("import-status");
    const campaignId = form.dataset.campaignId;
    const formData = new FormData(form);
    const payload = {
      transcript: String(formData.get("transcript") || "").trim(),
    };

    if (!payload.transcript) {
      setStatus(status, "Нужен текст старой партии или краткое резюме.", true);
      return;
    }

    try {
      togglePending(form, true);
      setStatus(status, "Готовлю лог к импорту (разобью на части при необходимости)...");

      await importTranscriptProgressively({
        campaignId,
        transcript: payload.transcript,
        statusEl: status,
      });

      setStatus(status, "Импорт завершён. Обновляю интерфейс...");
      await refreshShell(campaignId, { replaceUrl: true });
    } catch (error) {
      setStatus(
        status,
        `${error.message} Если обрыв был на середине, вставь тот же лог и запусти импорт снова — спросим, с какой части продолжить.`,
        true,
      );
    } finally {
      togglePending(form, false);
    }
  }
});

window.addEventListener("popstate", async () => {
  try {
    await refreshShell(null, {
      url: `${window.location.pathname}${window.location.search}`,
      scrollToBottom: true,
    });
  } catch {
    window.location.reload();
  }
});


window.addEventListener("resize", () => {
  syncFixedStageLayout();
});

