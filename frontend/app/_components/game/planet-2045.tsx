"use client";

// La Tierra de 2045 vista desde la colonia lunar (ADR-050), con el mismo sombreador que las cinemáticas
// (scripts/video/engine/gl.js): con `health` en 0 es naranja y negra, con humo, incendios y ciudades apagadas; cada
// lugar a salvo la cura un poco (health = estado del planeta / 100) hasta verse azul y verde. Es un efecto del juego,
// no un dato: la superficie es NASA Blue Marble y las luces NASA Black Marble (dominio público, GIBS); la máscara de
// tierra y el ruido salen de scripts/video/texturas.py. Sin WebGL2 no dibuja nada y queda el globo de siempre.

import { useEffect, useRef, useState } from "react";

const TEX = "/textures/earth/";

const VS = `#version 300 es
layout(location=0) in vec2 aPos;
void main(){ gl_Position = vec4(aPos, 0.0, 1.0); }`;

const FS = `#version 300 es
precision highp float;
uniform vec2 uRes; uniform float uTime, uHealth, uRadius; uniform vec3 uSun;
uniform sampler2D uDay, uNight, uLand, uNoise;
out vec4 outColor;
vec3 toPlanet(vec3 n, float rot, float tilt){
  float ct = cos(tilt), st = sin(tilt); n = vec3(n.x, ct * n.y - st * n.z, st * n.y + ct * n.z);
  float cr = cos(rot), sr = sin(rot); return vec3(cr * n.x + sr * n.z, n.y, -sr * n.x + cr * n.z);
}
vec2 uvOf(vec3 p){ return vec2(atan(p.x, p.z) / 6.2831853 + 0.5, 0.5 - asin(clamp(p.y, -1.0, 1.0)) / 3.1415927); }
vec4 sphereTex(sampler2D t, vec2 uv){
  vec2 a = uv, b = vec2(fract(uv.x + 0.5) - 0.5, uv.y);
  vec2 dxa = dFdx(a), dya = dFdy(a), dxb = dFdx(b), dyb = dFdy(b);
  bool useB = dot(dxb, dxb) + dot(dyb, dyb) < dot(dxa, dxa) + dot(dya, dya);
  return textureGrad(t, uv, useB ? dxb : dxa, useB ? dyb : dya);
}
void main(){
  vec2 d = (gl_FragCoord.xy - 0.5 * uRes) / uRadius;
  float r2 = dot(d, d);
  vec3 atmo = mix(vec3(0.85, 0.45, 0.2), vec3(0.35, 0.6, 1.0), uHealth);
  if (r2 < 1.0) {
    vec3 n = vec3(d, sqrt(1.0 - r2));
    vec3 p = toPlanet(n, uTime * 0.035 + 1.9, 0.38);
    vec2 uv = uvOf(p);
    vec3 day = sphereTex(uDay, uv).rgb;
    float land = sphereTex(uLand, uv).r;
    float lum = dot(day, vec3(0.3, 0.59, 0.11));
    vec3 dyingLand = mix(vec3(lum) * vec3(1.15, 0.85, 0.55), vec3(0.32, 0.22, 0.13), 0.45);
    vec3 dyingSea = vec3(lum) * vec3(0.6, 0.62, 0.5) + vec3(0.06, 0.05, 0.03);
    vec3 surf = mix(mix(dyingSea, dyingLand, land), day, uHealth);
    float diff = dot(n, uSun);
    float lit = smoothstep(-0.08, 0.25, diff);
    vec3 nz = sphereTex(uNoise, uv + vec2(uTime * 0.004, 0.0)).rgb;
    vec3 nz2 = sphereTex(uNoise, uv + vec2(-uTime * 0.002 + 0.37, 0.0)).rgb;
    float clouds = smoothstep(0.55, 0.8, nz.r) * (0.55 + 0.45 * uHealth);
    float smoke = smoothstep(0.42, 0.74, nz2.g) * (1.0 - uHealth);
    vec3 c = surf * (0.04 + 1.05 * lit);
    vec3 refl = reflect(-uSun, n);
    c += vec3(1.0, 0.95, 0.85) * pow(max(refl.z, 0.0), 40.0) * (1.0 - land) * lit * (0.3 + 0.7 * uHealth) * 0.6;
    c = mix(c, mix(vec3(0.62, 0.58, 0.52), vec3(1.0), uHealth) * (0.06 + 1.1 * lit), clouds * 0.9);
    c = mix(c, vec3(0.42, 0.33, 0.25) * (0.05 + 0.9 * lit), smoke * 0.85);
    vec3 night = sphereTex(uNight, uv).rgb;
    c += night * vec3(1.0, 0.8, 0.55) * (1.0 - lit) * (0.15 + 0.85 * uHealth) * 1.4 * (1.0 - clouds * 0.7);
    float fires = smoothstep(0.66, 0.8, sphereTex(uNoise, uv * 3.0 + vec2(0.0, uTime * 0.003)).b) * land * (1.0 - uHealth);
    c += vec3(1.0, 0.42, 0.08) * fires * (0.75 + 0.25 * sin(uTime * 9.0 + p.x * 40.0)) * 1.2;
    float rim = pow(1.0 - n.z, 2.5);
    c += atmo * rim * (0.25 + 0.75 * smoothstep(-0.3, 0.4, diff)) * 0.9;
    c = c / (1.0 + c * 0.15);
    outColor = vec4(pow(clamp(c, 0.0, 1.0), vec3(0.95)), 1.0);
  } else {
    float dist = sqrt(r2);
    float glow = exp(-(dist - 1.0) * 28.0) * 0.9 + exp(-(dist - 1.0) * 7.0) * 0.18 * 0.4;
    vec2 dir = d / dist;
    float a = clamp(glow * clamp(dot(dir, uSun.xy) * 0.5 + 0.6, 0.15, 1.0), 0.0, 1.0);
    outColor = vec4(atmo * a, a);
  }
}`;

function shader(gl: WebGL2RenderingContext, type: number, source: string) {
  const item = gl.createShader(type)!;
  gl.shaderSource(item, source);
  gl.compileShader(item);
  if (!gl.getShaderParameter(item, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(item) ?? "shader");
  return item;
}

function texture(gl: WebGL2RenderingContext, unit: number, url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      const item = gl.createTexture();
      gl.activeTexture(gl.TEXTURE0 + unit);
      gl.bindTexture(gl.TEXTURE_2D, item);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      resolve();
    };
    image.onerror = () => reject(new Error(url));
    image.src = url;
  });
}

/** Lienzo centrado en (x, y) con la Tierra de radio r en píxeles; `health` de 0 (crisis) a 1 (sana). */
export function Planet2045({ x, y, r, health, onReady }: { x: number; y: number; r: number; health: number; onReady?: (ok: boolean) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const healthRef = useRef(health);
  const shown = useRef(health);
  const onReadyRef = useRef(onReady);
  const [failed, setFailed] = useState(false);
  useEffect(() => { healthRef.current = health; }, [health]);
  useEffect(() => { onReadyRef.current = onReady; }, [onReady]);

  // Tamaño del lienzo: el planeta más el brillo de la atmósfera.
  const box = Math.max(8, Math.round(r * 2.7));

  useEffect(() => {
    const element = canvas.current;
    const gl = element?.getContext("webgl2", { premultipliedAlpha: true, alpha: true, antialias: true });
    const fail = () => { setFailed(true); onReadyRef.current?.(false); };
    if (!element || !gl || gl.isContextLost()) { fail(); return; }
    let program: WebGLProgram;
    try {
      program = gl.createProgram()!;
      gl.attachShader(program, shader(gl, gl.VERTEX_SHADER, VS));
      gl.attachShader(program, shader(gl, gl.FRAGMENT_SHADER, FS));
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error("link");
    } catch {
      fail();
      return;
    }
    gl.useProgram(program);
    const quad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    const at = (name: string) => gl.getUniformLocation(program, name);
    ["uDay", "uNight", "uLand", "uNoise"].forEach((name, unit) => gl.uniform1i(at(name), unit));
    const sun = [-0.55, 0.35, 0.76];
    const norm = Math.hypot(sun[0], sun[1], sun[2]);
    gl.uniform3f(at("uSun"), sun[0] / norm, sun[1] / norm, sun[2] / norm);

    let alive = true;
    let frame = 0;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const start = performance.now();
    const draw = () => {
      if (!alive) return;
      const size = element.width;
      gl.viewport(0, 0, size, size);
      // El cambio de estado se ve como una curación lenta, no como un salto.
      shown.current += (healthRef.current - shown.current) * (still ? 1 : 0.03);
      gl.uniform2f(at("uRes"), size, size);
      gl.uniform1f(at("uRadius"), size / 2.7);
      gl.uniform1f(at("uHealth"), Math.min(1, Math.max(0, shown.current)));
      gl.uniform1f(at("uTime"), still ? 0 : (performance.now() - start) / 1000);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      frame = requestAnimationFrame(draw);
    };
    Promise.all([
      texture(gl, 0, `${TEX}bluemarble-2k.jpg`), texture(gl, 1, `${TEX}blackmarble-2k.jpg`),
      texture(gl, 2, `${TEX}landmask-1k.png`), texture(gl, 3, `${TEX}noise-1k.jpg`),
    ]).then(() => { if (!alive) return; onReadyRef.current?.(true); draw(); }).catch(() => { if (alive) fail(); });
    // No se fuerza la pérdida del contexto al desmontar: en desarrollo React monta dos veces y el segundo montaje
    // recibiría un contexto perdido. El navegador lo libera con el lienzo.
    return () => {
      alive = false;
      cancelAnimationFrame(frame);
      gl.deleteProgram(program);
      gl.deleteBuffer(quad);
    };
  }, []);

  // Resolución del lienzo según el tamaño en pantalla (con la densidad de píxeles, máximo 2).
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const scale = Math.min(2, window.devicePixelRatio || 1);
    element.width = element.height = Math.round(box * scale);
  }, [box]);

  if (failed) return null;
  return <canvas ref={canvas} className="gamePlanet2045" aria-hidden style={{ left: x, top: y, width: box, height: box }} />;
}
