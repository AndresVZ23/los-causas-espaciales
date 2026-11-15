// Motor WebGL2 mínimo de las cinemáticas de TERRA 2045: planeta (Tierra y Luna) con shader, terreno real y túnel.
// Sin bibliotecas: el contenedor no tiene red. Todo se dibuja por fotograma con draw(t) desde render.py.
"use strict";

const GL = {};

GL.init = function (canvas) {
  const gl = canvas.getContext("webgl2", { antialias: true, preserveDrawingBuffer: true, alpha: false });
  if (!gl) throw new Error("sin WebGL2");
  GL.gl = gl;
  GL.quad = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, GL.quad);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  GL.planet = GL.program(QUAD_VS, PLANET_FS);
  GL.tunnel = GL.program(QUAD_VS, TUNNEL_FS);
  GL.terrainProg = GL.program(TERRAIN_VS, TERRAIN_FS);
  GL.textures = {};
  GL.terrains = {};
};

GL.program = function (vs, fs) {
  const gl = GL.gl;
  const compile = (type, src) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) + "\n" + src.split("\n").map((l, i) => `${i + 1}: ${l}`).join("\n"));
    return s;
  };
  const p = gl.createProgram();
  gl.attachShader(p, compile(gl.VERTEX_SHADER, vs));
  gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  const uniforms = {};
  const count = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < count; i += 1) { const info = gl.getActiveUniform(p, i); uniforms[info.name] = gl.getUniformLocation(p, info.name); }
  return { p, u: uniforms };
};

GL.loadTexture = function (name, url, repeat = true) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const gl = GL.gl;
      const tex = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, repeat ? gl.REPEAT : gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      GL.textures[name] = tex;
      resolve(tex);
    };
    img.onerror = () => reject(new Error("no se pudo cargar " + url));
    img.src = url;
  });
};

GL.bindTex = function (unit, name, loc) {
  const gl = GL.gl;
  gl.activeTexture(gl.TEXTURE0 + unit);
  gl.bindTexture(gl.TEXTURE_2D, GL.textures[name]);
  gl.uniform1i(loc, unit);
};

GL.drawQuad = function (prog) {
  const gl = GL.gl;
  gl.useProgram(prog.p);
  gl.bindBuffer(gl.ARRAY_BUFFER, GL.quad);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
};

/**
 * Planeta. o: { earth:[cx,cy,r] en px (origen arriba a la izquierda), rot (rad), tilt (rad), sun:[x,y,z] (vista),
 * health 0..1, doom 0..1, stars 0..1, moon:[cx,cy,r] o null, moonRot, time, exposure }
 */
GL.drawPlanet = function (o) {
  const gl = GL.gl, P = GL.planet, W = gl.canvas.width, H = gl.canvas.height;
  gl.viewport(0, 0, W, H);
  gl.disable(gl.DEPTH_TEST);
  gl.useProgram(P.p);
  gl.uniform2f(P.u.uRes, W, H);
  gl.uniform1f(P.u.uTime, o.time || 0);
  const e = o.earth || [-9999, -9999, 1];
  gl.uniform3f(P.u.uEarth, e[0], H - e[1], e[2]);
  gl.uniform2f(P.u.uRot, o.rot || 0, o.tilt || 0.25);
  const s = o.sun || [-0.6, 0.25, 0.75];
  const n = Math.hypot(...s);
  gl.uniform3f(P.u.uSun, s[0] / n, s[1] / n, s[2] / n);
  gl.uniform1f(P.u.uHealth, o.health ?? 1);
  gl.uniform1f(P.u.uDoom, o.doom || 0);
  gl.uniform1f(P.u.uStars, o.stars ?? 1);
  gl.uniform1f(P.u.uExposure, o.exposure ?? 1);
  const m = o.moon || [-9999, -9999, 1];
  gl.uniform3f(P.u.uMoon, m[0], H - m[1], m[2]);
  gl.uniform1f(P.u.uMoonRot, o.moonRot || 0);
  GL.bindTex(0, "day", P.u.uDay);
  GL.bindTex(1, "night", P.u.uNight);
  GL.bindTex(2, "land", P.u.uLand);
  GL.bindTex(3, "moon", P.u.uMoonTex);
  GL.bindTex(4, "noise", P.u.uNoise);
  GL.drawQuad(P);
};

GL.drawTunnel = function (o) {
  const gl = GL.gl, P = GL.tunnel, W = gl.canvas.width, H = gl.canvas.height;
  gl.viewport(0, 0, W, H);
  gl.useProgram(P.p);
  gl.uniform2f(P.u.uRes, W, H);
  gl.uniform1f(P.u.uTime, o.time || 0);
  gl.uniform1f(P.u.uSpeed, o.speed ?? 1);
  gl.uniform1f(P.u.uFlash, o.flash || 0);
  gl.uniform3f(P.u.uTint, ...(o.tint || [0.4, 0.8, 1.0]));
  GL.drawQuad(P);
};

/** Terreno real de una misión (relieve Copernicus DEM y cobertura ESA WorldCover, ya construidos en el repositorio). */
GL.addTerrain = function (id, data) {
  const gl = GL.gl;
  const n = data.grid;
  const relief = new Uint16Array(Uint8Array.from(atob(data.relief_dm), (c) => c.charCodeAt(0)).buffer);
  const cover = Uint8Array.from(atob(data.cover), (c) => c.charCodeAt(0));
  const step = n > 200 ? 2 : 1; // 256 → 128 celdas: suficiente para el video y más liviano
  const m = Math.floor((n - 1) / step) + 1;
  const cell = data.cell_m * step;
  const exag = data.size_km > 5 ? 1.25 : 1.5;
  const H = new Float32Array(m * m);
  for (let j = 0; j < m; j += 1) for (let i = 0; i < m; i += 1) H[j * m + i] = (relief[(j * step) * n + i * step] / 10) * exag;
  // Dos pasadas de promedio 3×3: GLO-30 llevado a celdas de 20 m deja escalones que se ven como terrazas.
  for (let pass = 0; pass < 2; pass += 1) {
    const S = H.slice();
    for (let j = 1; j < m - 1; j += 1) for (let i = 1; i < m - 1; i += 1) {
      let sum = 0; for (let dj = -1; dj <= 1; dj += 1) for (let di = -1; di <= 1; di += 1) sum += S[(j + dj) * m + i + di];
      H[j * m + i] = sum / 9;
    }
  }
  const pos = new Float32Array(m * m * 3), nor = new Float32Array(m * m * 3), col = new Float32Array(m * m * 4);
  const half = ((m - 1) * cell) / 2;
  const COVER = { 0: [0.6, 0.58, 0.54, 0], 10: [0.2, 0.36, 0.17, 1], 20: [0.47, 0.46, 0.25, 0.8], 30: [0.52, 0.62, 0.3, 0.9], 40: [0.68, 0.64, 0.36, 0.7],
    50: [0.55, 0.5, 0.47, 0], 60: [0.6, 0.5, 0.39, 0], 70: [0.92, 0.94, 0.97, 0], 80: [0.12, 0.3, 0.45, 0], 90: [0.3, 0.48, 0.36, 0.8], 95: [0.18, 0.36, 0.24, 1], 100: [0.55, 0.6, 0.42, 0.6] };
  for (let j = 0; j < m; j += 1) for (let i = 0; i < m; i += 1) {
    const k = j * m + i;
    pos[k * 3] = i * cell - half; pos[k * 3 + 1] = H[k]; pos[k * 3 + 2] = j * cell - half;
    const hl = H[j * m + Math.max(0, i - 1)], hr = H[j * m + Math.min(m - 1, i + 1)], hd = H[Math.max(0, j - 1) * m + i], hu = H[Math.min(m - 1, j + 1) * m + i];
    let nx = hl - hr, ny = 2 * cell, nz = hd - hu; const len = Math.hypot(nx, ny, nz); nor[k * 3] = nx / len; nor[k * 3 + 1] = ny / len; nor[k * 3 + 2] = nz / len;
    const c = COVER[cover[(j * step) * n + i * step]] || COVER[0];
    col[k * 4] = c[0]; col[k * 4 + 1] = c[1]; col[k * 4 + 2] = c[2]; col[k * 4 + 3] = c[3]; // alfa = cuánto es vegetación (se seca con la salud)
  }
  // Colores suavizados con sus vecinas: WorldCover (10 m) llevado a celdas de 20–31 m deja bloques muy marcados.
  for (let pass = 0; pass < 2; pass += 1) {
    const C = col.slice();
    for (let j = 1; j < m - 1; j += 1) for (let i = 1; i < m - 1; i += 1) for (let c = 0; c < 4; c += 1) {
      let sum = 0; for (let dj = -1; dj <= 1; dj += 1) for (let di = -1; di <= 1; di += 1) sum += C[((j + dj) * m + i + di) * 4 + c];
      col[(j * m + i) * 4 + c] = sum / 9;
    }
  }
  const idx = new Uint32Array((m - 1) * (m - 1) * 6);
  let t = 0;
  for (let j = 0; j < m - 1; j += 1) for (let i = 0; i < m - 1; i += 1) {
    const a = j * m + i, b = a + 1, c = a + m, d = c + 1;
    idx[t++] = a; idx[t++] = c; idx[t++] = b; idx[t++] = b; idx[t++] = c; idx[t++] = d;
  }
  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  const buf = (arr, loc, size) => { const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, arr, gl.STATIC_DRAW); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0); };
  buf(pos, 0, 3); buf(nor, 1, 3); buf(col, 2, 4);
  const ib = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idx, gl.STATIC_DRAW);
  gl.bindVertexArray(null);
  let maxH = 0; for (const h of H) maxH = Math.max(maxH, h);
  GL.terrains[id] = { vao, count: idx.length, half, maxH, m, cell, H };
};

GL.terrainHeight = function (id, x, z) {
  const T = GL.terrains[id];
  const i = Math.round((x + T.half) / T.cell), j = Math.round((z + T.half) / T.cell);
  if (i < 0 || j < 0 || i >= T.m || j >= T.m) return 0;
  return T.H[j * T.m + i];
};

// --- matrices -------------------------------------------------------------------------------------------------
GL.perspective = (fov, aspect, near, far) => { const f = 1 / Math.tan(fov / 2), nf = 1 / (near - far); return [f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) * nf, -1, 0, 0, 2 * far * near * nf, 0]; };
GL.lookAt = (e, c, up) => {
  let zx = e[0] - c[0], zy = e[1] - c[1], zz = e[2] - c[2]; let l = Math.hypot(zx, zy, zz); zx /= l; zy /= l; zz /= l;
  let xx = up[1] * zz - up[2] * zy, xy = up[2] * zx - up[0] * zz, xz = up[0] * zy - up[1] * zx; l = Math.hypot(xx, xy, xz); xx /= l; xy /= l; xz /= l;
  const yx = zy * xz - zz * xy, yy = zz * xx - zx * xz, yz = zx * xy - zy * xx;
  return [xx, yx, zx, 0, xy, yy, zy, 0, xz, yz, zz, 0, -(xx * e[0] + xy * e[1] + xz * e[2]), -(yx * e[0] + yy * e[1] + yz * e[2]), -(zx * e[0] + zy * e[1] + zz * e[2]), 1];
};
GL.mul = (a, b) => { const o = new Array(16).fill(0); for (let i = 0; i < 4; i += 1) for (let j = 0; j < 4; j += 1) for (let k = 0; k < 4; k += 1) o[j * 4 + i] += a[k * 4 + i] * b[j * 4 + k]; return o; };

/** o: { id, eye:[x,y,z], target:[x,y,z], health, sun:[x,y,z], sky:[r,g,b], fog, haze, time } */
GL.drawTerrain = function (o) {
  const gl = GL.gl, P = GL.terrainProg, W = gl.canvas.width, H = gl.canvas.height, T = GL.terrains[o.id];
  gl.viewport(0, 0, W, H);
  const sky = o.sky || [0.55, 0.7, 0.85];
  gl.clearColor(sky[0], sky[1], sky[2], 1);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  gl.enable(gl.DEPTH_TEST);
  gl.useProgram(P.p);
  const proj = GL.perspective(o.fov || 0.9, W / H, 5, T.half * 8);
  const view = GL.lookAt(o.eye, o.target, [0, 1, 0]);
  gl.uniformMatrix4fv(P.u.uMVP, false, new Float32Array(GL.mul(proj, view)));
  const s = o.sun || [0.5, 0.6, 0.3]; const n = Math.hypot(...s);
  gl.uniform3f(P.u.uSun, s[0] / n, s[1] / n, s[2] / n);
  gl.uniform3f(P.u.uSky, sky[0], sky[1], sky[2]);
  gl.uniform3f(P.u.uEye, ...o.eye);
  gl.uniform1f(P.u.uHealth, o.health ?? 1);
  gl.uniform1f(P.u.uFog, o.fog || T.half * 4.5);
  gl.uniform1f(P.u.uTime, o.time || 0);
  gl.uniform1f(P.u.uHaze, o.haze || 0);
  gl.uniform1f(P.u.uHalf, T.half);
  gl.bindVertexArray(T.vao);
  gl.drawElements(gl.TRIANGLES, T.count, gl.UNSIGNED_INT, 0);
  gl.bindVertexArray(null);
  gl.disable(gl.DEPTH_TEST);
};

const QUAD_VS = `#version 300 es
layout(location=0) in vec2 aPos;
void main(){ gl_Position = vec4(aPos, 0.0, 1.0); }`;

const NOISE = `
float hash3(vec3 p){ p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float vnoise(vec3 x){ vec3 i = floor(x); vec3 f = fract(x); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(hash3(i), hash3(i + vec3(1,0,0)), f.x), mix(hash3(i + vec3(0,1,0)), hash3(i + vec3(1,1,0)), f.x), f.y),
             mix(mix(hash3(i + vec3(0,0,1)), hash3(i + vec3(1,0,1)), f.x), mix(hash3(i + vec3(0,1,1)), hash3(i + vec3(1,1,1)), f.x), f.y), f.z); }
float fbm(vec3 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * vnoise(p); p = p * 2.03 + vec3(1.7, 9.2, 3.1); a *= 0.5; } return s; }
float hash2(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
`;

const PLANET_FS = `#version 300 es
precision highp float;
uniform vec2 uRes; uniform float uTime; uniform vec3 uEarth; uniform vec2 uRot; uniform vec3 uSun;
uniform float uHealth, uDoom, uStars, uExposure; uniform vec3 uMoon; uniform float uMoonRot;
uniform sampler2D uDay, uNight, uLand, uMoonTex, uNoise;
out vec4 outColor;
${NOISE}
vec3 stars(vec2 px){
  vec2 cell = floor(px / 3.0); float h = hash2(cell);
  float s = step(0.996, h) * (0.4 + 0.6 * hash2(cell + 7.0));
  vec2 c2 = floor(px / 9.0); float big = step(0.9993, hash2(c2 + 3.0));
  vec3 tint = mix(vec3(0.8, 0.85, 1.0), vec3(1.0, 0.9, 0.8), hash2(cell + 11.0));
  return tint * (s + big * 0.8);
}
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
  vec2 px = gl_FragCoord.xy;
  vec3 col = stars(px) * uStars;
  // Luna (esfera secundaria, textura LROC)
  vec2 dm = (px - uMoon.xy) / uMoon.z; float rm = dot(dm, dm);
  if (rm < 1.0) {
    vec3 n = vec3(dm, sqrt(1.0 - rm)); vec3 p = toPlanet(n, uMoonRot, 0.1);
    vec3 m = sphereTex(uMoonTex, uvOf(p)).rgb; float d = max(dot(n, uSun), 0.0);
    col = m * (0.03 + 1.15 * d);
  }
  // Tierra
  vec2 d = (px - uEarth.xy) / uEarth.z; float r2 = dot(d, d);
  vec3 atmoHealthy = vec3(0.35, 0.6, 1.0), atmoDying = vec3(0.85, 0.45, 0.2);
  vec3 atmo = mix(atmoDying, atmoHealthy, uHealth); atmo = mix(atmo, vec3(1.0, 0.25, 0.08), uDoom);
  if (r2 < 1.0) {
    vec3 n = vec3(d, sqrt(1.0 - r2));
    vec3 p = toPlanet(n, uRot.x, uRot.y);
    vec2 uv = uvOf(p);
    vec3 day = sphereTex(uDay, uv).rgb;
    float land = sphereTex(uLand, uv).r;
    float lum = dot(day, vec3(0.3, 0.59, 0.11));
    vec3 dyingLand = mix(vec3(lum) * vec3(1.15, 0.85, 0.55), vec3(0.32, 0.22, 0.13), 0.45);
    vec3 dyingSea = vec3(lum) * vec3(0.6, 0.62, 0.5) + vec3(0.06, 0.05, 0.03);
    vec3 dying = mix(dyingSea, dyingLand, land);
    vec3 surf = mix(dying, day, uHealth);
    float diff = dot(n, uSun);
    float lit = smoothstep(-0.08, 0.25, diff);
    // Nubes (sanas) y humo (agonía): ruido esférico precalculado (assets/noise.png), desplazado con el tiempo
    vec3 nz = sphereTex(uNoise, uv + vec2(uTime * 0.004, 0.0)).rgb;
    vec3 nz2 = sphereTex(uNoise, uv + vec2(-uTime * 0.002 + 0.37, 0.0)).rgb;
    float clouds = smoothstep(0.55, 0.8, nz.r) * (0.55 + 0.45 * uHealth);
    float smoke = smoothstep(0.42, 0.74, nz2.g) * (1.0 - uHealth);
    vec3 c = surf * (0.04 + 1.05 * lit);
    // Mar con brillo especular
    vec3 refl = reflect(-uSun, n); float spec = pow(max(refl.z, 0.0), 40.0) * (1.0 - land) * lit * (0.3 + 0.7 * uHealth);
    c += vec3(1.0, 0.95, 0.85) * spec * 0.6;
    c = mix(c, mix(vec3(0.62, 0.58, 0.52), vec3(1.0), uHealth) * (0.06 + 1.1 * lit), clouds * 0.9);
    c = mix(c, vec3(0.42, 0.33, 0.25) * (0.05 + 0.9 * lit), smoke * 0.85);
    // Luces de ciudades: solo donde todavía vive gente (se apagan en el 2045 crítico)
    vec3 night = sphereTex(uNight, uv).rgb;
    c += night * vec3(1.0, 0.8, 0.55) * (1.0 - lit) * (0.15 + 0.85 * uHealth) * 1.4 * (1.0 - clouds * 0.7);
    // Incendios en tierra firme y, con «doom», grietas de fuego (destrucción ficticia del final perdedor)
    float fires = smoothstep(0.66, 0.8, sphereTex(uNoise, uv * 3.0 + vec2(0.0, uTime * 0.003)).b) * land * (1.0 - uHealth);
    float flick = 0.75 + 0.25 * sin(uTime * 9.0 + p.x * 40.0);
    c += vec3(1.0, 0.42, 0.08) * fires * flick * (1.2 + 2.0 * uDoom);
    float crack = (1.0 - smoothstep(0.0, 0.03, abs(sphereTex(uNoise, uv * 1.7 + vec2(uTime * 0.002, 0.0)).g - 0.5))) * land;
    c = mix(c, c * 0.35, uDoom * 0.8);
    c += vec3(1.0, 0.35, 0.05) * crack * uDoom * 2.2 * flick;
    c += vec3(1.0, 0.5, 0.1) * fires * uDoom * 1.5;
    // Borde de atmósfera
    float rim = pow(1.0 - n.z, 2.5);
    c += atmo * rim * (0.25 + 0.75 * smoothstep(-0.3, 0.4, diff)) * 0.9;
    col = c;
  } else {
    float dist = sqrt(r2);
    float glow = exp(-(dist - 1.0) * 28.0) * 0.9 + exp(-(dist - 1.0) * 7.0) * 0.18 * (0.4 + uDoom);
    vec2 dir = d / dist; float sunside = clamp(dot(dir, uSun.xy) * 0.5 + 0.6, 0.15, 1.0);
    col += atmo * glow * sunside;
  }
  col *= uExposure;
  col = col / (1.0 + col * 0.15);
  outColor = vec4(pow(clamp(col, 0.0, 1.0), vec3(0.95)), 1.0);
}`;

const TUNNEL_FS = `#version 300 es
precision highp float;
uniform vec2 uRes; uniform float uTime, uSpeed, uFlash; uniform vec3 uTint;
out vec4 outColor;
${NOISE}
void main(){
  vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;
  float r = length(p), a = atan(p.y, p.x);
  float z = 0.35 / max(r, 0.02) + uTime * 2.2 * uSpeed;
  float streak = vnoise(vec3(a * 6.0, z * 1.6, 0.0));
  streak = pow(smoothstep(0.55, 1.0, streak), 2.0);
  float rings = 0.5 + 0.5 * sin(z * 6.0);
  vec3 c = uTint * streak * (1.4 * smoothstep(0.0, 0.6, r)) + vec3(0.08, 0.12, 0.25) * rings * smoothstep(0.1, 0.9, r) * 0.6;
  c += vec3(1.0) * pow(max(0.0, 1.0 - r * 3.0), 3.0) * 0.8;
  c = mix(c, vec3(1.0), clamp(uFlash, 0.0, 1.0));
  outColor = vec4(c, 1.0);
}`;

const TERRAIN_VS = `#version 300 es
layout(location=0) in vec3 aPos; layout(location=1) in vec3 aNor; layout(location=2) in vec4 aCol;
uniform mat4 uMVP; out vec3 vPos; out vec3 vNor; out vec4 vCol;
void main(){ vPos = aPos; vNor = aNor; vCol = aCol; gl_Position = uMVP * vec4(aPos, 1.0); }`;

const TERRAIN_FS = `#version 300 es
precision highp float;
uniform vec3 uSun, uSky, uEye; uniform float uHealth, uFog, uTime, uHaze, uHalf;
in vec3 vPos; in vec3 vNor; in vec4 vCol; out vec4 outColor;
${NOISE}
void main(){
  vec3 n = normalize(vNor);
  vec3 base = vCol.rgb;
  float slope = 1.0 - n.y;
  base = mix(base, vec3(0.45, 0.4, 0.36), smoothstep(0.35, 0.6, slope) * (1.0 - step(0.9, base.b)));
  float veg = vCol.a;
  vec3 dry = vec3(dot(base, vec3(0.3, 0.59, 0.11))) * vec3(1.2, 1.0, 0.72);
  base = mix(mix(base, dry, veg * (1.0 - uHealth)), base * vec3(0.9, 0.88, 0.85), (1.0 - uHealth) * 0.3);
  float grain = vnoise(vPos * 0.08) * 0.12 + vnoise(vPos * 0.6) * 0.06;
  base *= 0.9 + grain;
  float diff = max(dot(n, uSun), 0.0);
  vec3 c = base * (0.18 + 1.05 * pow(diff, 1.2)) + uSky * 0.05;
  float dist = length(vPos - uEye);
  float fog = 1.0 - exp(-dist / uFog);
  vec3 fogCol = mix(uSky, vec3(0.6, 0.5, 0.4), uHaze);
  // El borde del cuadrado de terreno se funde con el cielo: no se ve dónde termina el dato.
  float edge = smoothstep(uHalf * 0.8, uHalf * 0.99, max(abs(vPos.x), abs(vPos.z))) * smoothstep(uHalf * 0.6, uHalf * 1.1, dist);
  c = mix(c, fogCol, clamp(max(fog, edge) + uHaze * 0.25, 0.0, 1.0));
  outColor = vec4(pow(c, vec3(0.95)), 1.0);
}`;
