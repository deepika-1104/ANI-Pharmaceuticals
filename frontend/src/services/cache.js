const CACHE_PREFIX = 'voice-ai-chat:';
const MAX_CACHED = 50;

function userPrefix(userId) {
  return userId ? `${CACHE_PREFIX}${userId}:` : CACHE_PREFIX;
}

export function saveConversation(id, data, userId) {
  try {
    localStorage.setItem(`${userPrefix(userId)}${id}`, JSON.stringify(data));
    pruneCache(userId);
  } catch (e) {
    console.warn('Cache save failed:', e);
  }
}

export function getConversation(id, userId) {
  try {
    const raw = localStorage.getItem(`${userPrefix(userId)}${id}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function getAllConversations(userId) {
  const conversations = {};
  const p = userPrefix(userId);
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(p)) {
        const id = key.slice(p.length);
        try {
          const raw = localStorage.getItem(key);
          if (raw) conversations[id] = JSON.parse(raw);
        } catch {}
      }
    }
  } catch (e) {
    console.warn('Cache read failed:', e);
  }
  return conversations;
}

export function deleteConversation(id, userId) {
  try {
    localStorage.removeItem(`${userPrefix(userId)}${id}`);
  } catch (e) {
    console.warn('Cache delete failed:', e);
  }
}

export function clearAllConversations(userId) {
  try {
    const p = userPrefix(userId);
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(p)) keysToRemove.push(key);
    }
    keysToRemove.forEach(key => localStorage.removeItem(key));
  } catch (e) {
    console.warn('Cache clear failed:', e);
  }
}

// Remove unscoped legacy conversation keys (migration from pre-user-scoped format).
// Legacy keys look like 'voice-ai-chat:conv_...' — no ':' after the conv ID segment.
export function clearLegacyConversations() {
  try {
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(CACHE_PREFIX) && !key.slice(CACHE_PREFIX.length).includes(':')) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach(key => localStorage.removeItem(key));
  } catch (e) {
    console.warn('Legacy cache clear failed:', e);
  }
}

function pruneCache(userId) {
  try {
    const all = getAllConversations(userId);
    const sorted = Object.entries(all).sort(([, a], [, b]) => b.updatedAt - a.updatedAt);
    if (sorted.length > MAX_CACHED) {
      const p = userPrefix(userId);
      sorted.slice(MAX_CACHED).forEach(([id]) => {
        localStorage.removeItem(`${p}${id}`);
      });
    }
  } catch (e) {
    console.warn('Cache prune failed:', e);
  }
}
