const DEFAULT_PHONEME_TO_IMAGE = {
  A: 'mbp',
  B: 'openSlight',
  C: 'openMedium',
  D: 'openWide',
  E: 'oSmall',
  F: 'oWide',
  G: 'fv',
  H: 'lth',
  X: 'rest',
};

const BRIDGE_BY_PAIR = {
  'rest->openSlight': 'bridgeClosedToSlight',
  'openSlight->openMedium': 'bridgeSlightToMedium',
  'openMedium->openWide': 'bridgeMediumToWide',
  'oSmall->teethE': 'bridgeOToE',
  'oWide->teethE': 'bridgeOToE',
  'teethE->rest': 'bridgeEToClosed',
  'fv->rest': 'bridgeFvToClosed',
};

const MIN_CUE_SECONDS = 0.07;

function toImagePool(value) {
  if (Array.isArray(value)) {
    return value.filter((src) => typeof src === 'string' && src.trim());
  }
  if (typeof value === 'string' && value.trim()) {
    return [value.trim()];
  }
  return [];
}

function normalizeCues(raw) {
  const source = Array.isArray(raw)
    ? raw
    : Array.isArray(raw?.mouthCues)
      ? raw.mouthCues
      : [];

  const parsed = source
    .filter((cue) => cue && Number.isFinite(cue.start) && Number.isFinite(cue.end) && cue.end >= cue.start)
    .map((cue) => ({
      start: Number(cue.start),
      end: Number(cue.end),
      value: String(cue.value || '').trim().toUpperCase(),
    }))
    .sort((a, b) => a.start - b.start);

  if (!parsed.length) return [];

  const merged = [];
  for (let i = 0; i < parsed.length; i += 1) {
    const cue = parsed[i];
    const prev = merged[merged.length - 1];

    if (prev && prev.value === cue.value && cue.start <= prev.end + 0.001) {
      prev.end = Math.max(prev.end, cue.end);
      continue;
    }

    merged.push({ ...cue });
  }

  return merged.filter((cue) => cue.end - cue.start >= MIN_CUE_SECONDS);
}

function createPreloadPromise(src, loadedSet) {
  if (!src) return Promise.resolve();

  return new Promise((resolve) => {
    const img = new Image();
    img.decoding = 'async';
    img.onload = () => {
      loadedSet.add(src);
      resolve();
    };
    img.onerror = () => resolve();
    img.src = src;

    if (typeof img.decode === 'function') {
      img.decode().then(() => {
        loadedSet.add(src);
        resolve();
      }).catch(() => {
        // onload/onerror still resolve.
      });
    }
  });
}

export class ImageLipSyncAvatar {
  constructor(container, options = {}) {
    if (!container) {
      throw new Error('ImageLipSyncAvatar requires a container element.');
    }

    this.container = container;
    const src = options.images || {};
    this.imagePools = {
      rest: toImagePool(src.rest),
      openSlight: toImagePool(src.openSlight || src.slightlyOpen),
      openMedium: toImagePool(src.openMedium),
      openWide: toImagePool(src.openWide || src.wideOpen),
      oSmall: toImagePool(src.oSmall || src.oRound),
      oWide: toImagePool(src.oWide),
      teethE: toImagePool(src.teethE),
      fv: toImagePool(src.fv),
      lth: toImagePool(src.lth),
      mbp: toImagePool(src.mbp),
      jawDrop: toImagePool(src.jawDrop),
      idleSmile: toImagePool(src.idleSmile),
      bridgeClosedToSlight: toImagePool(src.bridgeClosedToSlight),
      bridgeSlightToMedium: toImagePool(src.bridgeSlightToMedium),
      bridgeMediumToWide: toImagePool(src.bridgeMediumToWide),
      bridgeOToE: toImagePool(src.bridgeOToE),
      bridgeEToClosed: toImagePool(src.bridgeEToClosed),
      bridgeFvToClosed: toImagePool(src.bridgeFvToClosed),
    };

    this._fillFallbackPool('openMedium', ['openSlight']);
    this._fillFallbackPool('oWide', ['oSmall']);
    this._fillFallbackPool('mbp', ['rest']);
    this._fillFallbackPool('jawDrop', ['openWide']);
    this._fillFallbackPool('idleSmile', ['rest']);
    this._fillFallbackPool('rest', ['mbp', 'openSlight']);

    this.phonemeToImage = { ...DEFAULT_PHONEME_TO_IMAGE, ...(options.phonemeToImage || {}) };
    this.useIdleWhenSilent = !!options.useIdleWhenSilent;

    this.state = 'listening';
    this.cues = [];
    this.cueIndex = 0;
    this.audio = null;
    this.audioContext = null;
    this.analyser = null;
    this.audioSourceNode = null;
    this.timeData = null;
    this.rafId = null;

    this.loadedSources = new Set();
    this.transitionMs = Number.isFinite(options.transitionMs) ? options.transitionMs : 90;
    this.minSwitchMs = Number.isFinite(options.minSwitchMs) ? options.minSwitchMs : 88;
    this.bridgeHoldMs = Number.isFinite(options.bridgeHoldMs) ? options.bridgeHoldMs : 48;
    this.stabilityMsCue = Number.isFinite(options.stabilityMsCue) ? options.stabilityMsCue : 42;
    this.stabilityMsEnergy = Number.isFinite(options.stabilityMsEnergy) ? options.stabilityMsEnergy : 96;
    this.bridgeMinGapMs = Number.isFinite(options.bridgeMinGapMs) ? options.bridgeMinGapMs : 120;
    this.stableFrameSelection = options.stableFrameSelection !== false;
    this.framePhase = Number.isFinite(options.framePhase) ? options.framePhase : 0.42;
    this.frameDriftMs = Number.isFinite(options.frameDriftMs) ? options.frameDriftMs : 2200;
    this.frameDriftStep = Number.isFinite(options.frameDriftStep) ? options.frameDriftStep : 0.015;

    this.frontImageIndex = 0;
    this.visibleKey = '';
    this.lastSwitchAt = 0;
    this.smoothedRms = 0;
    this.pendingBridgeTimer = null;
    this.pendingKey = '';
    this.pendingSince = 0;
    this.lastFrameByKey = {};
    this.lastFrameDriftAt = 0;
    this.lastRenderedSrc = '';

    this.rootEl = document.createElement('div');
    this.rootEl.className = 'image-avatar-wrap listening';

    this.layerEls = [document.createElement('img'), document.createElement('img')];
    for (let i = 0; i < this.layerEls.length; i += 1) {
      const imgEl = this.layerEls[i];
      imgEl.alt = 'Interviewer avatar';
      imgEl.draggable = false;
      imgEl.className = 'image-avatar-img' + (i === 0 ? ' visible' : ' hidden');
      imgEl.style.transitionDuration = this.transitionMs + 'ms';
      this.rootEl.appendChild(imgEl);
    }

    this.container.innerHTML = '';
    this.container.appendChild(this.rootEl);

    this._preloadAllImages();
    this._crossfadeToKey('rest', true);
  }

  setState(nextState) {
    const next = nextState || 'idle';
    this.state = next;
    this.rootEl.classList.remove('idle', 'speaking', 'listening');
    this.rootEl.classList.add(next);

    if (next !== 'speaking') {
      this._clearBridgeTimer();
      if (this.useIdleWhenSilent && next === 'idle') {
        this._crossfadeToKey('idleSmile', true);
      } else {
        this._crossfadeToKey('rest', true);
      }
    }
  }

  async speak(audioUrl, lipSyncUrl = '') {
    if (!audioUrl) return;

    this._stopLoop();
    this._stopAudio();
    this._clearBridgeTimer();

    this.cues = [];
    this.cueIndex = 0;
    this.smoothedRms = 0;
    this.lastFrameDriftAt = performance.now();

    if (lipSyncUrl) {
      try {
        const response = await fetch(lipSyncUrl, { cache: 'no-store' });
        if (response.ok) {
          const json = await response.json();
          this.cues = normalizeCues(json);
        }
      } catch (_) {
        this.cues = [];
      }
    }

    this.audio = new Audio(audioUrl);
    this.audio.playbackRate = 1.0;
    this._setupAudioAnalysis();

    this.setState('speaking');
    this._crossfadeToKey('rest', true);
    this._startLoop();

    try {
      if (this.audioContext && this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }

      await this.audio.play();
      await new Promise((resolve) => {
        this.audio.onended = resolve;
        this.audio.onerror = resolve;
      });
    } finally {
      this._stopLoop();
      this._stopAudio();
      this.setState('idle');
    }
  }

  destroy() {
    this._stopLoop();
    this._stopAudio();
    this._clearBridgeTimer();
    if (this.rootEl && this.rootEl.parentNode) {
      this.rootEl.parentNode.removeChild(this.rootEl);
    }
  }

  _preloadAllImages() {
    const allSources = [];
    Object.values(this.imagePools).forEach((pool) => {
      for (let i = 0; i < pool.length; i += 1) allSources.push(pool[i]);
    });
    const uniqueSources = Array.from(new Set(allSources.filter(Boolean)));
    Promise.all(uniqueSources.map((src) => createPreloadPromise(src, this.loadedSources))).catch(() => {
      // Best effort preload.
    });
  }

  _fillFallbackPool(key, fallbackKeys) {
    if (this.imagePools[key] && this.imagePools[key].length) return;

    for (let i = 0; i < fallbackKeys.length; i += 1) {
      const pool = this.imagePools[fallbackKeys[i]] || [];
      if (pool.length) {
        this.imagePools[key] = [...pool];
        return;
      }
    }

    this.imagePools[key] = [];
  }

  _hasPool(key) {
    return !!(this.imagePools[key] && this.imagePools[key].length);
  }

  _pickSrcForKey(key) {
    const pool = this.imagePools[key] || [];
    if (!pool.length) return '';

    if (pool.length === 1) return pool[0];

    if (this.stableFrameSelection) {
      const clampedPhase = Math.max(0.0, Math.min(1.0, this.framePhase));
      let idx = Math.round(clampedPhase * (pool.length - 1));
      idx = Math.max(0, Math.min(pool.length - 1, idx));
      const candidate = pool[idx];
      this.lastFrameByKey[key] = candidate;
      return candidate;
    }

    const prev = this.lastFrameByKey[key] || '';
    let candidate = pool[Math.floor(Math.random() * pool.length)];
    if (candidate === prev) {
      const idx = pool.indexOf(candidate);
      candidate = pool[(idx + 1) % pool.length];
    }
    this.lastFrameByKey[key] = candidate;
    return candidate;
  }

  _setupAudioAnalysis() {
    if (!this.audio) return;

    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;

    try {
      if (!this.audioContext) {
        this.audioContext = new Ctx();
      }

      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 256;
      this.analyser.smoothingTimeConstant = 0.85;
      this.timeData = new Uint8Array(this.analyser.fftSize);

      this.audioSourceNode = this.audioContext.createMediaElementSource(this.audio);
      this.audioSourceNode.connect(this.analyser);
      this.analyser.connect(this.audioContext.destination);
    } catch (_) {
      this.analyser = null;
      this.audioSourceNode = null;
      this.timeData = null;
    }
  }

  _stopAudio() {
    if (!this.audio) return;

    this.audio.pause();
    this.audio.onended = null;
    this.audio.onerror = null;

    if (this.audioSourceNode) {
      try {
        this.audioSourceNode.disconnect();
      } catch (_) {
        // no-op
      }
      this.audioSourceNode = null;
    }

    this.audio = null;
  }

  _startLoop() {
    if (this.rafId) return;

    const tick = () => {
      if (!this.audio) {
        this.rafId = null;
        return;
      }

      const speaking = !this.audio.paused && !this.audio.ended;
      if (!speaking) {
        this._setImageByKey('rest');
        this.rafId = requestAnimationFrame(tick);
        return;
      }

      const cue = this._getCueAtTime(this.audio.currentTime);
      if (cue) {
        const mappedKey = this.phonemeToImage[cue.value] || 'rest';
        this._setImageByKey(mappedKey, { fromCue: true });
      } else {
        this._setImageByKey(this._resolveImageFromAudioEnergy(), { fromCue: false });
      }

      this.rafId = requestAnimationFrame(tick);
    };

    this.rafId = requestAnimationFrame(tick);
  }

  _stopLoop() {
    if (!this.rafId) return;
    cancelAnimationFrame(this.rafId);
    this.rafId = null;
  }

  _getCueAtTime(currentTime) {
    if (!this.cues.length) return null;

    let i = this.cueIndex;
    while (i < this.cues.length && currentTime >= this.cues[i].end) i += 1;
    if (i >= this.cues.length) {
      this.cueIndex = this.cues.length - 1;
      return null;
    }
    while (i > 0 && currentTime < this.cues[i].start) i -= 1;

    this.cueIndex = i;
    const cue = this.cues[i];
    if (!cue) return null;

    if (currentTime >= cue.start && currentTime < cue.end) {
      return cue;
    }

    return null;
  }

  _resolveImageFromAudioEnergy() {
    if (!this.analyser || !this.timeData) {
      return 'openSlight';
    }

    this.analyser.getByteTimeDomainData(this.timeData);

    let sum = 0;
    for (let i = 0; i < this.timeData.length; i += 1) {
      const sample = (this.timeData[i] - 128) / 128;
      sum += sample * sample;
    }

    const rms = Math.sqrt(sum / this.timeData.length);
    this.smoothedRms = this.smoothedRms * 0.76 + rms * 0.24;

    if (this.smoothedRms > 0.12) return 'openWide';
    if (this.smoothedRms > 0.09) return 'openMedium';
    if (this.smoothedRms > 0.065) return 'openSlight';
    if (this.smoothedRms > 0.048) return 'jawDrop';
    if (this.smoothedRms > 0.035) return 'mbp';
    return 'rest';
  }

  _setImageByKey(key, options = {}) {
    const force = !!options.force;
    const fromCue = !!options.fromCue;
    const resolvedKey = this._hasPool(key) ? key : 'rest';

    if (!force && resolvedKey === this.visibleKey) return;

    const now = performance.now();
    const stabilityMs = fromCue ? this.stabilityMsCue : this.stabilityMsEnergy;

    if (!fromCue && this.stableFrameSelection && now - this.lastFrameDriftAt >= this.frameDriftMs) {
      const delta = (Math.random() * 2 - 1) * this.frameDriftStep;
      this.framePhase = Math.max(0.08, Math.min(0.92, this.framePhase + delta));
      this.lastFrameDriftAt = now;
    }

    if (!force) {
      if (this.pendingKey !== resolvedKey) {
        this.pendingKey = resolvedKey;
        this.pendingSince = now;
        return;
      }

      if (now - this.pendingSince < stabilityMs) {
        return;
      }
    } else {
      this.pendingKey = '';
      this.pendingSince = 0;
    }

    if (!force && now - this.lastSwitchAt < this.minSwitchMs) return;

    this._clearBridgeTimer();

    if (!force && fromCue && now - this.lastSwitchAt >= this.bridgeMinGapMs) {
      const bridgeKey = this._resolveBridgeKey(this.visibleKey, resolvedKey);
      if (bridgeKey && bridgeKey !== resolvedKey) {
        this._crossfadeToKey(bridgeKey);
        this.pendingBridgeTimer = window.setTimeout(() => {
          this._crossfadeToKey(resolvedKey, true);
          this.pendingBridgeTimer = null;
        }, this.bridgeHoldMs);
        return;
      }
    }

    this._crossfadeToKey(resolvedKey, force);
    this.pendingKey = '';
    this.pendingSince = 0;
  }

  _resolveBridgeKey(fromKey, toKey) {
    if (!fromKey || !toKey || fromKey === toKey) return '';

    const pair = fromKey + '->' + toKey;
    const bridge = BRIDGE_BY_PAIR[pair] || '';
    if (!bridge) return '';

    const pool = this.imagePools[bridge] || [];
    if (!pool.length) return '';

    const anyLoaded = pool.some((src) => this.loadedSources.has(src));
    if (!anyLoaded) return '';

    return bridge;
  }

  _crossfadeToKey(key, force = false) {
    const resolvedKey = this._hasPool(key) ? key : 'rest';
    if (!force && resolvedKey === this.visibleKey) return;

    let nextSrc = this._pickSrcForKey(resolvedKey);
    if (!nextSrc) {
      nextSrc = this._pickSrcForKey('rest');
    }
    if (!nextSrc) return;

    if (!this.loadedSources.has(nextSrc) && resolvedKey !== 'rest') {
      return;
    }

    if (!force && this.lastRenderedSrc === nextSrc) {
      this.visibleKey = resolvedKey;
      this.lastSwitchAt = performance.now();
      return;
    }

    const backIndex = this.frontImageIndex === 0 ? 1 : 0;
    const backEl = this.layerEls[backIndex];
    const frontEl = this.layerEls[this.frontImageIndex];

    backEl.src = nextSrc;
    backEl.classList.remove('hidden');
    backEl.classList.add('visible');

    frontEl.classList.remove('visible');
    frontEl.classList.add('hidden');

    this.frontImageIndex = backIndex;
    this.visibleKey = resolvedKey;
    this.lastSwitchAt = performance.now();
    this.lastRenderedSrc = nextSrc;
  }

  _clearBridgeTimer() {
    if (!this.pendingBridgeTimer) return;
    window.clearTimeout(this.pendingBridgeTimer);
    this.pendingBridgeTimer = null;
  }
}
