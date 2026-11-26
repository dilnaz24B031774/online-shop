import { AfterViewInit, Component, ElementRef, NgZone, OnDestroy, ViewChild, effect, inject, input, signal } from '@angular/core';
import type * as THREE_NS from 'three';

export type MascotId = 'aisulu' | 'altai';
export type MascotAction = 'eat' | 'drink' | 'happy' | 'wave';
export interface MascotPlay { action: MascotAction; who: MascotId; id: number; }

type Three = typeof THREE_NS;

/**
 * Where the face is on each picture (pixels of /bonus/<id>.webp, 900 px high).
 * Used to fly the kurt and the kese exactly to the mouth.
 */
const ART: Record<MascotId, { w: number; h: number; mouth: [number, number] }> = {
  aisulu: { w: 479, h: 900, mouth: [228, 335] },
  altai: { w: 440, h: 900, mouth: [213, 270] },
};
const HEIGHT = 4.4;                     // character height in scene units

/** Everything the animation loop needs to move one character. */
interface Rig {
  id: MascotId;
  root: THREE_NS.Group;                 // hop, turn towards the cursor
  figure: THREE_NS.Object3D;            // the picture plane or the loaded 3D model
  uniforms?: Record<string, { value: number }>;   // picture mode: shader controls
  mixer?: THREE_NS.AnimationMixer;      // model mode
  clips?: Record<string, THREE_NS.AnimationAction>;
  mouth: THREE_NS.Vector3;              // mouth position inside root
  kurt: THREE_NS.Mesh;
  bowl: THREE_NS.Group;
  soup: THREE_NS.Mesh;
  sparks: THREE_NS.Mesh[];
  baseX: number;
  action: { name: MascotAction; start: number } | null;
  nextIdle: number;
  nextBlink: number;
  seed: number;
}

/**
 * Aisulu and Altai, alive: the original artwork on a bending 3D card with blinking eyes,
 * breathing, swaying and real 3D kurt and kese. If /bonus/models/<id>.glb exists (a 3D model
 * made from the same picture), that model is shown instead and its animations are used.
 */
@Component({
  selector: 'app-mascot-3d',
  template: `
    <canvas #canvas (pointerdown)="down($event)" (pointermove)="move($event)" (pointerup)="up()" (pointerleave)="leave()"
            role="img" [attr.aria-label]="label()"></canvas>
    @if (failed()) {
      <div class="fallback">
        @for (id of ids(); track id) { <img [src]="'/bonus/' + id + '.webp'" [alt]="label()" /> }
      </div>
    }
  `,
  styles: [`
    :host { position: relative; display: block; width: 100%; height: 100%; min-height: 220px; }
    canvas { display: block; width: 100%; height: 100%; touch-action: pan-y; cursor: grab; }
    canvas:active { cursor: grabbing; }
    .fallback { position: absolute; inset: 0; display: flex; justify-content: center; align-items: flex-end; gap: 6%; }
    .fallback img { height: 92%; width: auto; }
  `],
})
export class Mascot3dComponent implements AfterViewInit, OnDestroy {
  readonly who = input<MascotId | 'both'>('aisulu');
  readonly play = input<MascotPlay | null>(null);
  readonly label = input('');
  readonly failed = signal(false);
  @ViewChild('canvas', { static: true }) private canvas!: ElementRef<HTMLCanvasElement>;
  private readonly zone = inject(NgZone);
  private readonly host = inject(ElementRef<HTMLElement>);

  private three?: Three;
  private renderer?: THREE_NS.WebGLRenderer;
  private scene?: THREE_NS.Scene;
  private rigs: Rig[] = [];
  private frame = 0;
  private clock = 0;
  private last = 0;
  private visible = true;
  private destroyed = false;
  private resize?: ResizeObserver;
  private seen?: IntersectionObserver;
  private dragX: number | null = null;
  private turn = 0;
  private look = { x: 0, y: 0 };
  private readonly calm = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  private lastPlay = 0;
  private pending: MascotPlay | null = null;

  constructor() {
    effect(() => {
      const play = this.play();
      if (play && play.id !== this.lastPlay) {
        this.lastPlay = play.id;
        if (!this.start(play.who, play.action)) this.pending = play;     // scene still loading
      }
    });
  }

  ids(): MascotId[] {
    const who = this.who();
    return who === 'both' ? ['aisulu', 'altai'] : [who];
  }

  async ngAfterViewInit() {
    try {
      const [THREE, { RoomEnvironment }] = await Promise.all([
        import('three'), import('three/examples/jsm/environments/RoomEnvironment.js')]);
      if (this.destroyed) return;
      await this.setup(THREE, RoomEnvironment);
    } catch {
      this.failed.set(true);
    }
  }

  ngOnDestroy() {
    this.destroyed = true;
    cancelAnimationFrame(this.frame);
    this.resize?.disconnect();
    this.seen?.disconnect();
    this.scene?.traverse(object => {
      const mesh = object as THREE_NS.Mesh;
      mesh.geometry?.dispose();
      const material = mesh.material as THREE_NS.Material | THREE_NS.Material[] | undefined;
      (Array.isArray(material) ? material : material ? [material] : []).forEach(m => {
        Object.values(m).forEach(v => (v as THREE_NS.Texture | undefined)?.isTexture && (v as THREE_NS.Texture).dispose());
        m.dispose();
      });
    });
    this.renderer?.dispose();
  }

  // ---------- pointer: drag to turn, characters lean towards the cursor ----------

  down(event: PointerEvent) { this.dragX = event.clientX; }
  up() { this.dragX = null; }
  leave() { this.dragX = null; this.look = { x: 0, y: 0 }; }
  move(event: PointerEvent) {
    const rect = this.canvas.nativeElement.getBoundingClientRect();
    this.look.x = ((event.clientX - rect.left) / rect.width - .5) * 2;
    this.look.y = ((event.clientY - rect.top) / rect.height - .5) * 2;
    if (this.dragX !== null) {
      this.turn = Math.max(-0.9, Math.min(0.9, this.turn + (event.clientX - this.dragX) * 0.008));
      this.dragX = event.clientX;
    }
  }

  private start(who: MascotId, name: MascotAction) {
    const rig = this.rigs.find(r => r.id === who);
    if (!rig) return this.rigs.length > 0;            // not on this canvas: nothing to do
    rig.action = { name, start: this.clock };
    if (rig.clips) this.playClip(rig, name);
    return true;
  }

  // ---------- scene ----------

  private async setup(THREE: Three, RoomEnvironment: new () => THREE_NS.Scene) {
    this.three = THREE;
    const canvas = this.canvas.nativeElement;
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer = renderer;

    const scene = new THREE.Scene();
    this.scene = scene;
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
    scene.add(new THREE.HemisphereLight(0xffffff, 0xd8c7a8, 0.8));
    const key = new THREE.DirectionalLight(0xfff1dd, 1.6);
    key.position.set(4, 7, 6);
    scene.add(key);

    const both = this.who() === 'both';
    const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100);
    camera.position.set(0, 2.5, both ? 11.5 : 11);
    camera.lookAt(0, 2.25, 0);

    const ids = this.ids();
    const rigs = await Promise.all(ids.map((id, index) =>
      this.character(THREE, id, both ? (index === 0 ? -1.45 : 1.45) : 0)));
    if (this.destroyed) return;
    rigs.forEach(rig => { scene.add(rig.root); this.rigs.push(rig); });
    if (this.pending) { this.start(this.pending.who, this.pending.action); this.pending = null; }

    const fit = () => {
      const { width, height } = this.host.nativeElement.getBoundingClientRect();
      if (!width || !height) return;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      // keep both characters in the frame on narrow screens
      const tanHalf = Math.tan(THREE.MathUtils.degToRad(14));
      const byHeight = 5.4 / 2 / tanHalf;                       // the figure plus a jump
      const byWidth = (both ? 6.4 : 3.4) / 2 / (tanHalf * camera.aspect);
      camera.position.z = Math.min(22, Math.max(byHeight, byWidth));
      camera.updateProjectionMatrix();
    };
    fit();
    this.resize = new ResizeObserver(fit);
    this.resize.observe(this.host.nativeElement);
    this.seen = new IntersectionObserver(entries => { this.visible = entries.some(e => e.isIntersecting); });
    this.seen.observe(this.host.nativeElement);

    this.zone.runOutsideAngular(() => {
      const loop = (now: number) => {
        this.frame = requestAnimationFrame(loop);
        const dt = Math.min(0.05, this.last ? (now - this.last) / 1000 : 0.016);
        this.last = now;
        if (!this.visible || document.hidden) return;
        this.clock += dt;
        this.rigs.forEach(rig => this.animate(rig, this.clock, dt));
        renderer.render(scene, camera);
      };
      this.frame = requestAnimationFrame(loop);
    });
  }

  private async character(THREE: Three, id: MascotId, x: number): Promise<Rig> {
    const root = new THREE.Group();
    root.position.x = x;
    const model = await this.loadModel(THREE, id);
    let figure: THREE_NS.Object3D;
    let uniforms: Rig['uniforms'];
    let mixer: THREE_NS.AnimationMixer | undefined;
    let clips: Rig['clips'];
    const art = ART[id];
    const width = HEIGHT * art.w / art.h;
    let mouth = new THREE.Vector3((art.mouth[0] / art.w - 0.5) * width, (1 - art.mouth[1] / art.h) * HEIGHT, 0.25);

    if (model) {                                            // a real 3D model made from the picture
      figure = model.scene;
      const box = new THREE.Box3().setFromObject(figure);
      const size = box.getSize(new THREE.Vector3());
      const scale = HEIGHT / (size.y || 1);
      figure.scale.setScalar(scale);
      figure.position.set(-(box.min.x + size.x / 2) * scale, -box.min.y * scale, -(box.min.z + size.z / 2) * scale);
      mixer = new THREE.AnimationMixer(figure);
      clips = {};
      for (const clip of model.animations) clips[clip.name.toLowerCase()] = mixer.clipAction(clip);
      const idle = this.findClip(clips, ['idle', 'breath', 'stand']) ?? Object.values(clips)[0];
      idle?.play();
      mouth = new THREE.Vector3(0, HEIGHT * 0.66, size.z * scale * 0.5 + 0.15);
    } else {                                                // the original picture on a living card
      const loader = new THREE.TextureLoader();
      const load = (url: string) => new Promise<THREE_NS.Texture>((resolve, reject) => loader.load(url, t => {
        t.colorSpace = THREE.SRGBColorSpace;
        t.anisotropy = 4;
        resolve(t);
      }, undefined, reject));
      const [map, blink, happy, mouthMap] = await Promise.all(
        ['', '_blink', '_happy', '_mouth'].map(suffix => load(`/bonus/${id}${suffix}.webp`)));
      uniforms = { uBlink: { value: 0 }, uHappy: { value: 0 }, uMouth: { value: 0 }, uSway: { value: 0 },
                   uSquash: { value: 0 }, uBreath: { value: 0 }, uNod: { value: 0 } };
      const material = new THREE.ShaderMaterial({
        transparent: true, side: THREE.DoubleSide,
        uniforms: { map: { value: map }, blinkMap: { value: blink }, happyMap: { value: happy },
                    mouthMap: { value: mouthMap }, ...uniforms } as Record<string, THREE_NS.IUniform>,
        vertexShader: `
          uniform float uSway, uSquash, uBreath, uNod;
          varying vec2 vUv;
          void main() {
            vUv = uv;
            vec3 p = position;
            float h = uv.y;                                     // 0 at the feet, 1 at the top
            p.y *= 1.0 - uSquash;                               // squash before a jump, stretch in the air
            p.x *= 1.0 + uSquash * 0.6;
            p.x *= 1.0 + uBreath * smoothstep(0.3, 0.5, h) * (1.0 - smoothstep(0.5, 0.68, h));
            p.x += uSway * h * h * ${HEIGHT.toFixed(1)};       // feet stay, the body bends
            float head = smoothstep(0.55, 0.75, h);
            p.x += uNod * head * (h - 0.55) * 2.0;
            p.z += -abs(uNod) * head * 0.6 + sin(h * 3.14159) * 0.18;   // a little roundness, head tips back to drink
            gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
          }`,
        fragmentShader: `
          uniform sampler2D map, blinkMap, happyMap, mouthMap;
          uniform float uBlink, uHappy, uMouth;
          varying vec2 vUv;
          void main() {
            vec4 base = texture2D(map, vUv);
            if (base.a < 0.03) discard;
            vec4 lid = texture2D(blinkMap, vUv);
            vec4 joy = texture2D(happyMap, vUv);
            vec4 open = texture2D(mouthMap, vUv);
            vec3 c = base.rgb;
            c = mix(c, lid.rgb, lid.a * uBlink);
            c = mix(c, joy.rgb, joy.a * uHappy);
            c = mix(c, open.rgb, open.a * uMouth);
            gl_FragColor = vec4(c, base.a);
            #include <colorspace_fragment>
          }`,
      });
      const plane = new THREE.Mesh(new THREE.PlaneGeometry(width, HEIGHT, 24, 64), material);
      plane.geometry.translate(0, HEIGHT / 2, 0);
      figure = plane;
    }
    root.add(figure);

    // soft round shadow on the floor
    const shadowCanvas = document.createElement('canvas');
    shadowCanvas.width = shadowCanvas.height = 64;
    const g = shadowCanvas.getContext('2d')!;
    const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, 'rgba(15,30,60,.38)');
    grad.addColorStop(1, 'rgba(15,30,60,0)');
    g.fillStyle = grad;
    g.fillRect(0, 0, 64, 64);
    const shadow = new THREE.Mesh(new THREE.PlaneGeometry(width * 1.05, 0.9),
      new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(shadowCanvas), transparent: true, depthWrite: false }));
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.02;
    shadow.name = 'shadow';
    root.add(shadow);

    const mat = (color: number, rough = 0.5, extra: Partial<THREE_NS.MeshPhysicalMaterialParameters> = {}) =>
      new THREE.MeshPhysicalMaterial({ color, roughness: rough, ...extra });
    const gold = mat(0xe0b04a, 0.25, { metalness: 1, envMapIntensity: 1.4 });

    // kurt: a small dried cheese ball
    const kurt = new THREE.Mesh(new THREE.IcosahedronGeometry(0.17, 2), mat(0xf8f3e6, 0.95, { sheen: 0.6, sheenColor: new THREE.Color(0xffffff) }));
    const bump = kurt.geometry.attributes['position'];
    for (let k = 0; k < bump.count; k++) {
      const f = 1 + Math.sin(k * 12.9898) * 0.06;
      bump.setXYZ(k, bump.getX(k) * f, bump.getY(k) * f * 0.92, bump.getZ(k) * f);
    }
    kurt.geometry.computeVertexNormals();
    kurt.visible = false;
    root.add(kurt);

    // Nauryz kozhe kese: blue porcelain bowl with a gold rim and an ornament
    const bowl = new THREE.Group();
    const points = Array.from({ length: 12 }, (_, k) => new THREE.Vector2(0.06 + Math.sin((k / 11) * Math.PI / 2) * 0.4, (k / 11) * 0.34));
    const kese = new THREE.Mesh(new THREE.LatheGeometry(points, 40), mat(0x1d5aa8, 0.18, { clearcoat: 1, side: THREE.DoubleSide }));
    bowl.add(kese);
    const rim = new THREE.Mesh(new THREE.TorusGeometry(0.455, 0.022, 8, 40), gold);
    rim.rotation.x = Math.PI / 2;
    rim.position.y = 0.34;
    bowl.add(rim);
    for (let k = 0; k < 10; k++) {
      const a = (k / 10) * Math.PI * 2;
      const dot = new THREE.Mesh(new THREE.TorusGeometry(0.04, 0.01, 6, 12, Math.PI * 1.4), gold);
      dot.position.set(Math.sin(a) * 0.36, 0.17, Math.cos(a) * 0.36);
      dot.rotation.y = a;
      bowl.add(dot);
    }
    const soup = new THREE.Mesh(new THREE.CircleGeometry(0.4, 40), mat(0xf6efdd, 0.35, { clearcoat: 0.6 }));
    soup.rotation.x = -Math.PI / 2;
    soup.position.y = 0.3;
    bowl.add(soup);
    bowl.visible = false;
    root.add(bowl);

    // golden sparkles for happy moments
    const sparks = Array.from({ length: 10 }, () => {
      const spark = new THREE.Mesh(new THREE.OctahedronGeometry(0.09), new THREE.MeshStandardMaterial({
        color: 0xf6c25b, emissive: 0xf6a623, emissiveIntensity: 0.9, metalness: 0.4, roughness: 0.3, transparent: true }));
      spark.visible = false;
      root.add(spark);
      return spark;
    });

    return { id, root, figure, uniforms, mixer, clips, mouth, kurt, bowl, soup, sparks, baseX: x, action: null,
             nextIdle: 2 + Math.random() * 3, nextBlink: 0.8 + Math.random() * 2, seed: Math.random() * 10 };
  }

  /** /bonus/models/<id>.glb, if someone has put a 3D model there. */
  private async loadModel(THREE: Three, id: MascotId) {
    try {
      const response = await fetch(`/bonus/models/${id}.glb`, { cache: 'no-cache' });
      if (!response.ok) return null;
      const data = await response.arrayBuffer();
      if (new TextDecoder().decode(data.slice(0, 4)) !== 'glTF') return null;   // the dev server answers missing files with the page
      const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js');
      return await new Promise<{ scene: THREE_NS.Group; animations: THREE_NS.AnimationClip[] }>((resolve, reject) =>
        new GLTFLoader().parse(data, '/bonus/models/', gltf => resolve(gltf), reject));
    } catch {
      return null;
    }
  }

  private findClip(clips: Record<string, THREE_NS.AnimationAction>, names: string[]) {
    const key = Object.keys(clips).find(name => names.some(n => name.includes(n)));
    return key ? clips[key] : undefined;
  }

  private playClip(rig: Rig, name: MascotAction) {
    const wanted = { eat: ['eat', 'chew'], drink: ['drink', 'sip'], happy: ['happy', 'jump', 'cheer', 'dance'],
                     wave: ['wave', 'hello', 'greet', 'thumb'] }[name];
    const clip = this.findClip(rig.clips!, wanted) ?? this.findClip(rig.clips!, ['happy', 'jump', 'wave', 'dance']);
    if (!clip || !this.three) return;
    clip.reset().setLoop(this.three.LoopOnce, 1).fadeIn(0.2).play();
    clip.clampWhenFinished = false;
  }

  // ---------- animation ----------

  private animate(rig: Rig, t: number, dt: number) {
    const ease = (p: number) => p < 0 ? 0 : p > 1 ? 1 : p * p * (3 - 2 * p);
    const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
    const bell = (p: number) => p <= 0 || p >= 1 ? 0 : Math.sin(p * Math.PI);
    const amp = this.calm ? 0.35 : 1;
    const u = rig.uniforms;
    rig.mixer?.update(dt);

    // idle: breathing, a gentle sway, eyes blink every few seconds
    let sway = Math.sin(t * 1.3 + rig.seed) * 0.012 * amp;
    let squash = Math.sin(t * 2.4 + rig.seed) * 0.006 * amp;
    const breath = (Math.sin(t * 2.4 + rig.seed) * 0.5 + 0.5) * 0.012 * amp;
    let nod = 0, hop = 0, happy = 0, mouth = 0, sparkle = -1;
    if (t > rig.nextBlink) rig.nextBlink = t + 2.2 + Math.random() * 3.2;
    const blinkLeft = rig.nextBlink - t;
    let blink = blinkLeft > 2.05 && blinkLeft < 2.2 ? 1 : 0;
    rig.kurt.visible = false;
    rig.bowl.visible = false;

    // now and then, without being fed: a little dance
    if (!rig.action && !this.calm && t > rig.nextIdle) {
      rig.action = { name: 'wave', start: t };
      rig.nextIdle = t + 6 + Math.random() * 5;
    }

    if (rig.action) {
      const p = t - rig.action.start;
      const m = rig.mouth;
      if (rig.action.name === 'wave') {             // happy wiggle with a small hop
        sway += Math.sin(p * 9) * 0.035 * bell(p / 1.6);
        hop = bell((p - 0.9) / 0.5) * 0.18;
        squash -= bell((p - 0.9) / 0.5) * 0.03;
        happy = bell(p / 1.6) > 0.4 ? 1 : 0;
        if (p > 1.6) rig.action = null;
      } else if (rig.action.name === 'eat') {       // a kurt flies in, munch munch, jump for joy
        const fly = ease(p / 0.65);
        if (p < 0.75) {
          rig.kurt.visible = true;
          rig.kurt.scale.setScalar(1);
          rig.kurt.position.set(lerp(m.x + 2.2, m.x, fly), lerp(m.y - 1.6, m.y, fly) + bell(fly) * 1.1, lerp(1.4, m.z + 0.1, fly));
          rig.kurt.rotation.set(p * 9, p * 7, 0);
        }
        squash += bell((p - 0.6) / 0.3) * 0.05;      // catches it
        if (p > 0.7 && p < 1.7) { mouth = Math.abs(Math.sin((p - 0.7) * 11)) > 0.45 ? 1 : 0; nod = Math.sin((p - 0.7) * 11) * 0.04; }
        if (p > 1.75) {
          const q = (p - 1.75) / 0.6;
          hop = bell(q) * 0.55;
          squash -= bell(q) * 0.06 - bell((q - 1) / 0.25) * 0.05;
          happy = 1;
          sparkle = p - 1.75;
        }
        if (p > 2.8) rig.action = null;
      } else if (rig.action.name === 'drink') {     // the kese comes, tips to the lips, drink to the last drop
        rig.bowl.visible = p < 2.75;
        const come = ease(p / 0.55);
        const lift = ease((p - 0.5) / 0.45);
        const go = ease((p - 2.25) / 0.45);
        rig.bowl.position.set(lerp(m.x + 2.4, m.x, come) + go * 2.4,
          lerp(m.y - 2.0, m.y - 0.75, come) + lift * 0.5 + go * 0.6, lerp(1.5, m.z + 0.45, come));
        rig.bowl.rotation.set(lift * 0.85 * (1 - go), 0, -0.15 * (1 - lift));
        rig.bowl.scale.setScalar(0.62 * (1 - go * 0.6));
        const sip = ease((p - 0.9) / 1.3);
        rig.soup.position.y = lerp(0.3, 0.1, sip);
        rig.soup.scale.setScalar(lerp(1, 0.6, sip));
        nod = -0.16 * lift * (1 - go);                // head tips back while drinking
        happy = lift * (1 - go) > 0.5 ? 1 : 0;
        squash += Math.sin(p * 10) * 0.006 * lift * (1 - go);
        if (p > 2.7) {
          const q = (p - 2.7) / 0.65;
          hop = bell(q) * 0.6;
          sway += Math.sin(q * 12) * 0.03 * bell(q);
          happy = 1;
          sparkle = p - 2.7;
        }
        if (p > 3.7) rig.action = null;
      } else if (rig.action.name === 'happy') {     // gift received: two joyful jumps
        const q = p / 0.55;
        hop = Math.abs(Math.sin(Math.min(2, q) * Math.PI)) * 0.55 * (q < 2 ? 1 : 0);
        sway += Math.sin(p * 10) * 0.03;
        happy = 1;
        sparkle = p;
        if (p > 1.3) rig.action = null;
      }
    }
    if (happy) blink = 0;

    // lean towards the cursor like a card in 3D; drag to turn
    if (this.dragX === null) this.turn *= Math.pow(0.05, dt);
    const side = rig.baseX < 0 ? 0.18 : rig.baseX > 0 ? -0.18 : 0;
    rig.root.rotation.y = lerp(rig.root.rotation.y, side + this.look.x * 0.35 + this.turn, Math.min(1, dt * 6));
    rig.figure.rotation.x = lerp(rig.figure.rotation.x, this.look.y * 0.08 + nod * 0.4, Math.min(1, dt * 6));
    rig.root.position.y = hop;
    const shadow = rig.root.getObjectByName('shadow');
    if (shadow) { shadow.position.y = 0.02 - hop; shadow.scale.setScalar(1 - hop * 0.6); }

    if (u) {
      u['uSway'].value = sway;
      u['uSquash'].value = squash;
      u['uBreath'].value = breath;
      u['uNod'].value = nod;
      u['uBlink'].value = blink;
      u['uHappy'].value = lerp(u['uHappy'].value, happy, Math.min(1, dt * 14));
      u['uMouth'].value = mouth;
    } else {
      rig.figure.scale.set(1 + squash * 0.6, 1 - squash, 1 + squash * 0.6);
      rig.figure.rotation.z = -sway * 3;
    }

    rig.sparks.forEach((spark, k) => {
      spark.visible = sparkle >= 0 && sparkle < 1.1;
      if (!spark.visible) return;
      const a = (k / rig.sparks.length) * Math.PI * 2;
      const r = 0.5 + sparkle * 1.5;
      spark.position.set(Math.cos(a) * r, HEIGHT * 0.72 + sparkle * 1.2 + Math.sin(a * 2) * 0.2, Math.sin(a) * r * 0.4 + 0.5);
      spark.rotation.set(sparkle * 6, sparkle * 4, 0);
      (spark.material as THREE_NS.MeshStandardMaterial).opacity = 1 - sparkle / 1.1;
    });
  }
}
