import * as THREE from 'https://esm.sh/three@0.161.0';
import { GLTFLoader } from 'https://esm.sh/three@0.161.0/examples/jsm/loaders/GLTFLoader.js';

const RHUBARB_TO_VISEME = {
  A: 0.18,
  B: 0.32,
  C: 0.44,
  D: 0.56,
  E: 0.7,
  F: 0.38,
  G: 0.54,
  H: 0.24,
  X: 0.02,
};

const PHONEME_TO_MORPH_PATTERNS = {
  A: ['viseme_aa', 'viseme-aa', 'aa', 'jawopen', 'jaw_open', 'mouthopen'],
  B: ['viseme_pp', 'viseme-bb', 'pp', 'bb', 'mm', 'mouthpress'],
  C: ['viseme_e', 'viseme_ih', 'ih', 'e'],
  D: ['viseme_dd', 'viseme_tt', 'dd', 'tt', 'viseme_nn', 'nn'],
  E: ['viseme_oh', 'viseme_o', 'oh', 'o', 'viseme_u', 'u'],
  F: ['viseme_ff', 'viseme_th', 'ff', 'th'],
  G: ['viseme_kk', 'viseme_rr', 'viseme_ch', 'kk', 'rr', 'ch'],
  H: ['viseme_ss', 'viseme_sil', 'ss', 'sil', 'mouthclose', 'mouth_closed'],
  X: ['viseme_sil', 'sil', 'mouthclose', 'mouth_closed'],
};

const BLINK_LEFT_PATTERNS = ['blink_left', 'eye_blink_l', 'blinkl', 'blinkleft', 'eyeblinkleft'];
const BLINK_RIGHT_PATTERNS = ['blink_right', 'eye_blink_r', 'blinkr', 'blinkright', 'eyeblinkright'];

const DEFAULT_HUMAN_GLB = 'https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/CesiumMan/glTF-Binary/CesiumMan.glb';

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

function lowerName(node) {
  return String(node?.name || '').toLowerCase();
}

export class InterviewerAvatar {
  constructor(container, options = {}) {
    if (!container) {
      throw new Error('InterviewerAvatar requires a container element.');
    }

    this.container = container;
    this.options = options;
    this.state = 'idle';

    this.clock = new THREE.Clock();
    this.stateClock = 0;
    this.mouthOpen = 0;
    this.mouthTarget = 0;

    this.blinkTimer = 0;
    this.nextBlinkAt = 1.4 + Math.random() * 2.0;

    this.currentAudio = null;
    this.currentLipSync = [];
    this.speechStartTime = 0;
    this.activeCueIndex = 0;

    this.audioContext = null;
    this.analyser = null;
    this.analyserData = null;
    this.audioSourceNode = null;

    this.loader = new GLTFLoader();
    this.modelRoot = null;
    this.mixer = null;
    this.idleAction = null;

    this.jawBone = null;
    this.headBone = null;
    this.neckBone = null;
    this.proxyMouthGroup = null;
    this.proxyMouthMesh = null;
    this.proxyMouthBillboard = null;

    this.faceMorphMeshes = [];
    this.currentCueSymbol = 'X';

    this._setupRenderer();
    this._setupScene();
    this._buildFallbackAvatar();
    this._loadRealHumanAvatar();

    this._onResize = this._handleResize.bind(this);
    window.addEventListener('resize', this._onResize);

    this._animationHandle = requestAnimationFrame(this._animate.bind(this));
  }

  _setupRenderer() {
    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 600;

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));
    this.renderer.setSize(width, height);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.04;
    this.container.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(30, width / height, 0.1, 100);
    this.camera.position.set(0.0, 1.52, 1.05);
    this.camera.lookAt(0.0, 1.45, 0.0);
  }

  _setupScene() {
    const ambient = new THREE.HemisphereLight(0xe2ecff, 0xbec7d7, 0.88);
    this.scene.add(ambient);

    const key = new THREE.DirectionalLight(0xffffff, 1.12);
    key.position.set(2.8, 3.3, 2.4);
    this.scene.add(key);

    const fill = new THREE.DirectionalLight(0x9ab6ff, 0.38);
    fill.position.set(-2.4, 2.1, 1.0);
    this.scene.add(fill);

    const rim = new THREE.DirectionalLight(0xa5d8ff, 0.3);
    rim.position.set(-2.1, 2.3, -2.2);
    this.scene.add(rim);

    // Keep an invisible floor reference if needed later, but skip rendering to clean up background
    this.avatarAnchor = new THREE.Group();
    // Center perfectly for webcam view
    this.avatarAnchor.position.set(0.0, 0.0, 0.0);
    this.scene.add(this.avatarAnchor);
  }

  _buildFallbackAvatar() {
    const suit = new THREE.MeshStandardMaterial({ color: 0x1f2937, roughness: 0.66, metalness: 0.05 });
    const skin = new THREE.MeshStandardMaterial({ color: 0xe7c0a2, roughness: 0.64, metalness: 0.0 });
    const lip = new THREE.MeshStandardMaterial({ color: 0x7f1d1d, roughness: 0.52, metalness: 0.02 });

    this.fallbackGroup = new THREE.Group();
    this.fallbackGroup.visible = true;
    this.avatarAnchor.add(this.fallbackGroup);

    this.fallbackBreath = new THREE.Group();
    this.fallbackGroup.add(this.fallbackBreath);

    const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.34, 0.78, 8, 20), suit);
    torso.position.set(0.0, 0.72, 0.0);
    this.fallbackBreath.add(torso);

    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.1, 0.16, 16), skin);
    neck.position.set(0.0, 1.25, 0.03);
    this.fallbackBreath.add(neck);

    this.fallbackHead = new THREE.Group();
    this.fallbackHead.position.set(0.0, 1.43, 0.03);
    this.fallbackBreath.add(this.fallbackHead);

    const head = new THREE.Mesh(new THREE.SphereGeometry(0.27, 30, 30), skin);
    this.fallbackHead.add(head);

    this.fallbackJaw = new THREE.Group();
    this.fallbackJaw.position.set(0.0, -0.03, 0.22);
    this.fallbackHead.add(this.fallbackJaw);

    this.fallbackMouth = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.024, 0.05), lip);
    this.fallbackMouth.position.set(0.0, -0.02, 0.06);
    this.fallbackJaw.add(this.fallbackMouth);
  }

  _loadRealHumanAvatar() {
    const configuredUrl = String(this.options.modelUrl || '').trim();
    const modelUrl = configuredUrl || DEFAULT_HUMAN_GLB;

    this.loader.load(
      modelUrl,
      (gltf) => {
        const model = gltf.scene || gltf.scenes?.[0];
        if (!model) {
          return;
        }

        model.traverse((obj) => {
          if (!obj.isMesh) return;
          obj.castShadow = false;
          obj.receiveShadow = false;

          if (Array.isArray(obj.material)) {
            obj.material.forEach((mat) => this._tuneMaterial(mat));
          } else {
            this._tuneMaterial(obj.material);
          }
        });

        const box = new THREE.Box3().setFromObject(model);
        const size = new THREE.Vector3();
        box.getSize(size);
        const height = Math.max(size.y, 0.001);
        // Scale to a standard 1.68m height so the head is reliably around y=1.5
        const scale = 1.68 / height;
        model.scale.setScalar(scale);

        const centeredBox = new THREE.Box3().setFromObject(model);
        const center = new THREE.Vector3();
        centeredBox.getCenter(center);
        model.position.x -= center.x;
        model.position.z -= center.z;
        model.position.y -= centeredBox.min.y;
        // Keep native facing direction for custom rig.
        model.rotation.y = 0;

        this.modelRoot = new THREE.Group();
        this.modelRoot.add(model);
        this.avatarAnchor.add(this.modelRoot);

        this._bindFaceControls(model);
        this._bindSkeletonControls(model);
        this._ensureProxyMouthForCustomRig();

        // For user-provided interviewer.glb, force interview posture and avoid animation overriding it.
        const isCustomModel = /\/static\/talvo1\/models\/interviewer\.glb$/i.test(modelUrl) || /interviewer\.glb$/i.test(modelUrl);
        this._applyInterviewerPose(model);

        if (!isCustomModel && Array.isArray(gltf.animations) && gltf.animations.length) {
          this.mixer = new THREE.AnimationMixer(model);
          const clip = gltf.animations.find((a) => /idle/i.test(a.name)) || gltf.animations[0];
          this.idleAction = this.mixer.clipAction(clip);
          this.idleAction.enabled = true;
          this.idleAction.play();
        }

        if (this.fallbackGroup) {
          this.fallbackGroup.visible = false;
        }
      },
      undefined,
      () => {
        if (this.fallbackGroup) {
          this.fallbackGroup.visible = true;
        }
      }
    );
  }

  _tuneMaterial(material) {
    if (!material) return;
    material.roughness = material.roughness ?? 0.75;
    material.metalness = material.metalness ?? 0.03;
    if (material.map) {
      material.map.anisotropy = 4;
    }
  }

  _bindSkeletonControls(model) {
    model.traverse((obj) => {
      if (!obj.isBone) return;
      const name = lowerName(obj);
      if (!this.jawBone && /jaw|mandible|chin|mouth/.test(name)) this.jawBone = obj;
      if (!this.headBone && /^head|head$|face/.test(name)) this.headBone = obj;
      if (!this.neckBone && /^neck|neck$/.test(name)) this.neckBone = obj;
    });
  }

  _ensureProxyMouthForCustomRig() {
    // Disabled by request: custom proxy mouth visuals caused a visible red overlay.
    return;
  }

  _updateProxyMouthBillboard() {
    if (!this.proxyMouthBillboard || !this.headBone) return;

    const headWorld = new THREE.Vector3();
    this.headBone.getWorldPosition(headWorld);

    const headToCamera = this.camera.position.clone().sub(headWorld).normalize();
    const target = headWorld
      .clone()
      .add(new THREE.Vector3(0, -0.09, 0))
      .add(headToCamera.multiplyScalar(0.08));

    this.proxyMouthBillboard.position.copy(target);
    this.proxyMouthBillboard.lookAt(this.camera.position);
  }

  _applyInterviewerPose(model) {
    const bones = {};
    model.traverse((obj) => {
      if (!obj.isBone) return;
      bones[String(obj.name).toLowerCase()] = obj;
    });

    const findBone = (patterns) => {
      const entries = Object.entries(bones);
      for (const [name, bone] of entries) {
        if (patterns.some((re) => re.test(name))) {
          return bone;
        }
      }
      return null;
    };

    const alignUpperArmDown = (upperArm, foreArm, xDirection) => {
      if (!upperArm || !foreArm || !upperArm.parent) return;

      upperArm.updateWorldMatrix(true, false);
      foreArm.updateWorldMatrix(true, false);

      const armPos = new THREE.Vector3();
      const forePos = new THREE.Vector3();
      upperArm.getWorldPosition(armPos);
      foreArm.getWorldPosition(forePos);

      const currentWorldDir = forePos.sub(armPos).normalize();
      const targetWorldDir = new THREE.Vector3(xDirection, -1, 0.08).normalize();

      const parentWorldQuat = new THREE.Quaternion();
      upperArm.parent.getWorldQuaternion(parentWorldQuat);
      const invParentWorldQuat = parentWorldQuat.clone().invert();

      const currentParentDir = currentWorldDir.clone().applyQuaternion(invParentWorldQuat).normalize();
      const targetParentDir = targetWorldDir.clone().applyQuaternion(invParentWorldQuat).normalize();

      const deltaLocal = new THREE.Quaternion().setFromUnitVectors(currentParentDir, targetParentDir);
      upperArm.quaternion.premultiply(deltaLocal);
      upperArm.updateMatrixWorld(true);
    };

    const leftArm = findBone([/^leftarm$/, /upperarm.*l/, /left.*upperarm/, /^arm_l$/]);
    const rightArm = findBone([/^rightarm$/, /upperarm.*r/, /right.*upperarm/, /^arm_r$/]);
    const leftForeArm = findBone([/^leftforearm$/, /lowerarm.*l/, /left.*lowerarm/, /^forearm_l$/]);
    const rightForeArm = findBone([/^rightforearm$/, /lowerarm.*r/, /right.*lowerarm/, /^forearm_r$/]);

    // Solve each side by vector alignment so arm direction is consistently downward on any rig axis layout.
    alignUpperArmDown(leftArm, leftForeArm, -0.16);
    alignUpperArmDown(rightArm, rightForeArm, 0.16);
  }

  _bindFaceControls(model) {
    this.faceMorphMeshes = [];
    model.traverse((obj) => {
      if (!obj.isMesh) return;
      if (!obj.morphTargetDictionary || !obj.morphTargetInfluences) return;
      const dict = obj.morphTargetDictionary;
      const score = Object.keys(dict).reduce((acc, key) => {
        const l = key.toLowerCase();
        if (/mouth|viseme|jaw|lip|aa|oh|blink/.test(l)) return acc + 1;
        return acc;
      }, 0);

      if (score > 0) {
        this.faceMorphMeshes.push({
          mesh: obj,
          dict,
          influences: obj.morphTargetInfluences,
          score,
        });
      }
    });

    this.faceMorphMeshes.sort((a, b) => b.score - a.score);
  }

  _setMorphByPattern(patterns, value) {
    if (!this.faceMorphMeshes.length) return false;
    let applied = false;
    this.faceMorphMeshes.forEach((entry) => {
      Object.keys(entry.dict).forEach((key) => {
        const lk = key.toLowerCase();
        if (patterns.some((p) => lk.includes(p))) {
          const idx = entry.dict[key];
          entry.influences[idx] = value;
          applied = true;
        }
      });
    });
    return applied;
  }

  _resetVisemeMorphs() {
    if (!this.faceMorphMeshes.length) return;
    this.faceMorphMeshes.forEach((entry) => {
      Object.keys(entry.dict).forEach((key) => {
        const lk = key.toLowerCase();
        if (lk.includes('viseme') || lk.includes('mouth') || lk.includes('jawopen') || lk.includes('lip')) {
          const idx = entry.dict[key];
          entry.influences[idx] *= 0.35;
        }
      });
    });
  }

  _applyCueViseme(symbol, amount) {
    const cue = PHONEME_TO_MORPH_PATTERNS[symbol] ? symbol : 'X';
    const patterns = PHONEME_TO_MORPH_PATTERNS[cue];
    return this._setMorphByPattern(patterns, amount);
  }

  setState(nextState) {
    this.state = nextState || 'idle';
  }

  async speak(audioUrl, lipSyncUrl) {
    if (!audioUrl) return;

    this._stopAudio();

    const audio = new Audio(audioUrl);
    audio.preload = 'auto';
    this.currentAudio = audio;
    this.activeCueIndex = 0;

    this.currentLipSync = [];
    let lipSyncPromise = null;
    if (lipSyncUrl) {
      lipSyncPromise = this._loadLipSync(lipSyncUrl)
        .then((cues) => {
          this.currentLipSync = cues;
          this.activeCueIndex = 0;
        })
        .catch(() => {
          this.currentLipSync = [];
          this.activeCueIndex = 0;
        });
    }

    if (lipSyncPromise) {
      await Promise.race([
        lipSyncPromise,
        new Promise((resolve) => setTimeout(resolve, 1500)),
      ]);
    }

    this._attachAnalyser(audio);
    this.state = 'speaking';

    await audio.play();
    this.speechStartTime = performance.now();

    await new Promise((resolve) => {
      const done = () => resolve();
      audio.addEventListener('ended', done, { once: true });
      audio.addEventListener('error', done, { once: true });
    });

    this._stopAudio();
    this.currentLipSync = [];
    this.state = 'idle';
    this.mouthTarget = 0.02;
  }

  _stopAudio() {
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio.src = '';
      this.currentAudio = null;
    }

    if (this.audioSourceNode) {
      try {
        this.audioSourceNode.disconnect();
      } catch (_) {
        // no-op
      }
      this.audioSourceNode = null;
    }

    this.analyser = null;
    this.analyserData = null;
    this.currentCueSymbol = 'X';
    this.activeCueIndex = 0;
  }

  async _loadLipSync(url) {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error('Lip sync file unavailable');
    }

    const payload = await response.json();
    const cues = Array.isArray(payload?.mouthCues) ? payload.mouthCues : [];

    return cues
      .map((cue) => ({
        start: Number(cue.start || 0),
        end: Number(cue.end || 0),
        value: String(cue.value || 'X').toUpperCase(),
      }))
      .filter((cue) => Number.isFinite(cue.start) && Number.isFinite(cue.end) && cue.end >= cue.start)
      .sort((a, b) => a.start - b.start);
  }

  _attachAnalyser(audio) {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;

    if (!this.audioContext) {
      this.audioContext = new AudioCtx();
    }

    if (this.audioContext.state === 'suspended') {
      this.audioContext.resume().catch(() => {});
    }

    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;
    this.analyser.smoothingTimeConstant = 0.8;
    this.analyserData = new Uint8Array(this.analyser.frequencyBinCount);

    this.audioSourceNode = this.audioContext.createMediaElementSource(audio);
    this.audioSourceNode.connect(this.analyser);
    this.analyser.connect(this.audioContext.destination);
  }

  _resolveMouthFromCues(elapsedSeconds) {
    if (!this.currentLipSync.length) {
      this.currentCueSymbol = 'X';
      return -1;
    }

    while (
      this.activeCueIndex < this.currentLipSync.length - 1
      && elapsedSeconds > this.currentLipSync[this.activeCueIndex].end
    ) {
      this.activeCueIndex += 1;
    }

    const cue = this.currentLipSync[this.activeCueIndex];
    if (!cue) {
      this.currentCueSymbol = 'X';
      return 0.02;
    }

    if (elapsedSeconds < cue.start || elapsedSeconds > cue.end) {
      this.currentCueSymbol = 'X';
      return 0.02;
    }

    this.currentCueSymbol = String(cue.value || 'X').toUpperCase();

    const visemeValue = RHUBARB_TO_VISEME[this.currentCueSymbol] ?? RHUBARB_TO_VISEME.X;
    return clamp(visemeValue, 0.02, 0.8);
  }

  _resolveMouthFromAudio() {
    this.currentCueSymbol = 'X';
    if (!this.analyser || !this.analyserData) return 0.02;

    this.analyser.getByteTimeDomainData(this.analyserData);

    let sum = 0;
    for (let i = 0; i < this.analyserData.length; i += 1) {
      const centered = (this.analyserData[i] - 128) / 128;
      sum += centered * centered;
    }

    const rms = Math.sqrt(sum / this.analyserData.length);
    const speechPulse = this.currentAudio && !this.currentAudio.paused
      ? (0.11 + (Math.sin(performance.now() * 0.016) * 0.05))
      : 0.0;
    return clamp(Math.max(rms * 4.6, speechPulse), 0.03, 0.75);
  }

  _applyFace(mouthAmount, blinkAmount) {
    const mouth = clamp(mouthAmount, 0.0, 1.0);
    const blink = clamp(blinkAmount, 0.0, 1.0);

    if (this.faceMorphMeshes.length) {
      this._setMorphByPattern(BLINK_LEFT_PATTERNS, blink);
      this._setMorphByPattern(BLINK_RIGHT_PATTERNS, blink);

      this._resetVisemeMorphs();
      const morphApplied =
        this._applyCueViseme(this.currentCueSymbol, mouth) ||
        this._setMorphByPattern(['mouthopen', 'mouth_open', 'jawopen', 'jaw_open'], mouth);

      if (morphApplied) {
        if (this.jawBone) {
          this.jawBone.rotation.x = -mouth * 0.38;
        }
        return;
      }
    }

    if (this.jawBone) {
      this.jawBone.rotation.x = -mouth * 0.62;
      if (this.proxyMouthMesh) {
        this.proxyMouthMesh.scale.y = 1.0;
      }
    } else if (this.fallbackJaw) {
      this.fallbackJaw.rotation.x = -mouth * 0.9;
      this.fallbackMouth.scale.y = 1 + mouth * 2.45;
    } else if (this.proxyMouthMesh && this.proxyMouthGroup) {
      this.proxyMouthMesh.scale.y = 1 + mouth * 4.4;
      this.proxyMouthGroup.position.z = 0.115 + mouth * 0.012;
    }

    if (this.proxyMouthBillboard) {
      this.proxyMouthBillboard.scale.y = 1 + mouth * 5.4;
      this.proxyMouthBillboard.material.opacity = 0.6 + mouth * 0.35;
    }
  }

  _applyPosture(elapsed, dt) {
    this.stateClock += dt;

    const breathe = 1 + Math.sin(elapsed * 1.12) * 0.01;
    if (this.modelRoot) {
      this.modelRoot.scale.y = breathe;
    } else if (this.fallbackBreath) {
      this.fallbackBreath.scale.y = breathe;
    }

    const targetTilt = this.state === 'listening' ? 0.045 : 0.0;
    const targetYaw = this.state === 'listening' ? -0.03 : -0.006;

    const headNode = this.headBone || this.fallbackHead;
    const neckNode = this.neckBone;

    if (headNode) {
      headNode.rotation.z += (targetTilt - headNode.rotation.z) * 0.065;
      headNode.rotation.y += (targetYaw - headNode.rotation.y) * 0.06;
    }

    if (neckNode) {
      neckNode.rotation.y += ((targetYaw * 0.45) - neckNode.rotation.y) * 0.045;
    }
  }

  _animate() {
    const elapsed = this.clock.getElapsedTime();
    const dt = this.clock.getDelta();

    if (this.mixer) {
      this.mixer.update(dt);
    }

    this._applyPosture(elapsed, dt);

    this.blinkTimer += dt;
    let blinkAmount = 0;
    if (this.blinkTimer >= this.nextBlinkAt && this.blinkTimer <= this.nextBlinkAt + 0.12) {
      const t = (this.blinkTimer - this.nextBlinkAt) / 0.12;
      blinkAmount = Math.sin(t * Math.PI);
    } else if (this.blinkTimer > this.nextBlinkAt + 0.12) {
      this.blinkTimer = 0;
      this.nextBlinkAt = 1.6 + Math.random() * 2.2;
    }

    if (this.state === 'speaking' && this.currentAudio) {
      const elapsedSpeech = Number.isFinite(this.currentAudio.currentTime)
        ? Math.max(0, this.currentAudio.currentTime)
        : Math.max(0, (performance.now() - this.speechStartTime) / 1000);
      const cueMouth = this._resolveMouthFromCues(elapsedSpeech);
      this.mouthTarget = cueMouth >= 0 ? cueMouth : this._resolveMouthFromAudio();
    } else if (this.state === 'speaking') {
      this.currentCueSymbol = 'X';
      this.mouthTarget = 0.18 + Math.abs(Math.sin(performance.now() * 0.02)) * 0.28;
    } else {
      this.mouthTarget = this.state === 'listening' ? 0.04 : 0.022;
    }

    this.mouthOpen += (this.mouthTarget - this.mouthOpen) * 0.26;
    this._applyFace(this.mouthOpen, blinkAmount);
    this._updateProxyMouthBillboard();

    this.renderer.render(this.scene, this.camera);
    this._animationHandle = requestAnimationFrame(this._animate.bind(this));
  }

  _handleResize() {
    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 600;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  destroy() {
    cancelAnimationFrame(this._animationHandle);
    window.removeEventListener('resize', this._onResize);

    this._stopAudio();

    if (this.mixer) {
      this.mixer.stopAllAction();
      this.mixer = null;
    }

    this.renderer.dispose();
    if (this.proxyMouthBillboard && this.proxyMouthBillboard.parent) {
      this.proxyMouthBillboard.parent.remove(this.proxyMouthBillboard);
    }
    if (this.renderer.domElement && this.renderer.domElement.parentNode) {
      this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
    }
  }
}
