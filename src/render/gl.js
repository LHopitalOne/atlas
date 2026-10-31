/**
 * WebGL2 renderer: shader programs and instanced layers (curves, SDF nodes, territory fills).
 * Nothing touches the GPU until initGL() runs.
 */
/** WebGL2 context and GPU resources; all created by initGL(), so importing this module never touches the GPU. */
import { glc } from '../dom.js';

export let gl, P_BG, P_EDGE, P_NODE, P_FILL, LY;
let B_CURVE, B_LINE, B_QUAD;
/** GLSL sources: [vertex, fragment] per program. */
const SHADERS = {
  P_BG: [
    `#version 300 es
void main(){ vec2 p=vec2(float((gl_VertexID<<1)&2), float(gl_VertexID&2)); gl_Position=vec4(p*2.-1.,0.,1.); }`,
    `#version 300 es
precision highp float;
uniform vec3 u_bg; uniform vec4 u_grid; uniform vec2 u_size; uniform float u_dpr; uniform vec3 u_g;
out vec4 o;
void main(){
  vec2 p=vec2(gl_FragCoord.x, u_size.y*u_dpr-gl_FragCoord.y)/u_dpr;
  vec2 g=mod(p-u_g.yz,u_g.x); vec2 dd=min(g,u_g.x-g);
  float dt=1.-smoothstep(.45,1.15,length(dd));
  float vig=1.-smoothstep(.18,.62,length((p-u_size*.5)/max(u_size.x,u_size.y)));
  o=vec4(mix(u_bg,u_grid.rgb,u_grid.a*dt*mix(.15,1.,vig)),1.);
}`,
  ],
  P_EDGE: [
    `#version 300 es
layout(location=0) in vec2 a_vt;
layout(location=1) in vec4 a_seg;
layout(location=2) in vec4 a_prm;
layout(location=3) in vec4 a_col;
uniform vec3 u_cam; uniform vec2 u_size; uniform vec4 u_mask;
out vec4 v_col; out float v_side; out float v_hw; out float v_dist; out float v_dash; out float v_len; out float v_t;
void main(){
  vec2 p0=a_seg.xy, p1=a_seg.zw, d=p1-p0;
  vec2 c=(p0+p1)*.5+vec2(-d.y,d.x)*a_prm.y;
  float t=a_vt.x, u=1.-t;
  vec2 pos=u*u*p0+2.*u*t*c+t*t*p1;
  vec2 tg=2.*u*(c-p0)+2.*t*(p1-c);
  if (dot(tg,tg)<1e-10) tg=vec2(1.,0.);
  vec2 n=normalize(vec2(-tg.y,tg.x));
  float w=a_prm.x, hw=w*.5+1.;
  vec2 s=pos*u_cam.x+u_cam.yz+n*a_vt.y*hw;
  gl_Position=vec4(s/u_size*2.-1.,0.,1.); gl_Position.y=-gl_Position.y;
  v_col=a_col; v_side=a_vt.y*hw; v_hw=w*.5; v_dist=t*length(d)*u_cam.x; v_dash=a_prm.z; v_len=length(d)*u_cam.x; v_t=t;
  float st=a_prm.w;
  float vis = st<.5 ? u_mask.x : st<1.5 ? u_mask.y : st<2.5 ? u_mask.z : st<3.5 ? u_mask.w : 1.;
  if (vis<.5 || w<=0. || a_col.a<=0.) gl_Position=vec4(2.,2.,2.,1.);
}`,
    `#version 300 es
precision mediump float;
in vec4 v_col; in float v_side; in float v_hw; in float v_dist; in float v_dash; in float v_len; in float v_t;
uniform float u_alpha; uniform float u_stub; uniform float u_fade;
out vec4 o;
void main(){
  float a=clamp(v_hw+.5-abs(v_side),0.,1.);
  // hairline beams: fade in from each end over u_fade pixels
  if (u_fade>0.){ float fe=clamp(u_fade/max(v_len,1.),.001,.45); a*=smoothstep(0.,fe,v_t)*(1.-smoothstep(1.-fe,1.,v_t)); }
  // long links become stubs that point toward their far end, like roads leaving the edge of a map
  if (u_stub>0. && v_len>u_stub*2.2){ float e=min(v_dist, v_len-v_dist); a*=1.-smoothstep(u_stub*.4, u_stub, e); }
  if (v_dash>.5 && fract(v_dist/8.)>.55) discard;
  o=vec4(v_col.rgb, v_col.a*a*u_alpha);
}`,
  ],
  P_NODE: [
    `#version 300 es
layout(location=0) in vec2 a_q;
layout(location=1) in vec4 a_n;
layout(location=2) in vec4 a_col;
layout(location=3) in vec2 a_fl;
uniform vec3 u_cam; uniform vec2 u_size; uniform float u_alpha; uniform float u_focusT; uniform float u_issues; uniform float u_minPx; uniform float u_maxPx;
out vec2 v_p; out float v_r; out vec4 v_col; flat out float v_shape; out float v_a; out float v_solid;
void main(){
  v_solid=a_fl.x*u_focusT;
  float r=clamp(a_n.z*u_cam.x,u_minPx,u_maxPx), ext=r+3.5;
  vec2 s=a_n.xy*u_cam.x+u_cam.yz+a_q*ext;
  gl_Position=vec4(s/u_size*2.-1.,0.,1.); gl_Position.y=-gl_Position.y;
  v_p=a_q*ext; v_r=r; v_col=a_col; v_shape=a_n.w;
  float a=u_alpha*mix(1.,mix(.12,1.,a_fl.x),u_focusT)*mix(1.,mix(.18,1.,a_fl.y),u_issues);
  v_a=a; if (a<.004) gl_Position=vec4(2.,2.,2.,1.);
}`,
    `#version 300 es
precision mediump float;
in vec2 v_p; in float v_r; in vec4 v_col; flat in float v_shape; in float v_a; in float v_solid;
uniform vec3 u_halo;
out vec4 o;
void main(){
  float L=length(v_p), d;
  if (v_shape>.5 && v_shape<1.5) d=(abs(v_p.x)+abs(v_p.y))*.7071-v_r*.95;
  else if (v_shape>1.5 && v_shape<2.5) d=max(abs(v_p.x),abs(v_p.y))-v_r*.88;
  else d=L-v_r;
  float f=clamp(.5-d,0.,1.);
  if (v_shape>2.5){
    float halo=clamp(.5-(L-v_r-2.),0.,1.);
    float ring=clamp(1.25-abs(L-(v_r-.75)),0.,1.)*f;
    float core=clamp(.5-(L-max(1.3,v_r*.3)),0.,1.);
    float solid=max(1.-step(3.5,v_r), v_solid);
    vec3 c=mix(u_halo, mix(u_halo,v_col.rgb,mix(.14,1.,solid)), f);
    c=mix(c, v_col.rgb, max(ring*(1.-solid), core*(1.-solid)));
    if (solid>.5) c=mix(c, u_halo, clamp(.5-(L-v_r*.34),0.,1.)*step(4.,v_r)*.5);
    o=vec4(c, max(f,halo)*v_a);
  } else o=vec4(v_col.rgb,f*v_a*v_col.a);
  if (o.a<.003) discard;
}`,
  ],
  P_FILL: [
    `#version 300 es
layout(location=0) in vec2 a_p;
layout(location=1) in vec4 a_col;
uniform vec3 u_cam; uniform vec2 u_size;
out vec4 v_col;
void main(){ vec2 s=a_p*u_cam.x+u_cam.yz; gl_Position=vec4(s/u_size*2.-1.,0.,1.); gl_Position.y=-gl_Position.y; v_col=a_col; }`,
    `#version 300 es
precision mediump float;
in vec4 v_col; uniform float u_alpha; out vec4 o;
void main(){ o=vec4(v_col.rgb,v_col.a*u_alpha); }`,
  ],
};

function shader(type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
  return s;
}
function program(vs, fs) {
  const p = gl.createProgram();
  gl.attachShader(p, shader(gl.VERTEX_SHADER, vs));
  gl.attachShader(p, shader(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  const u = {};
  const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < n; i++) {
    const nm = gl.getActiveUniform(p, i).name;
    u[nm] = gl.getUniformLocation(p, nm);
  }
  return { p, u };
}
const mkBuf = data => {
  const b = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, b);
  gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
  return b;
};
function attr(loc, buf, size, type, norm, div) {
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, size, type, norm, 0, 0);
  if (div) gl.vertexAttribDivisor(loc, 1);
}
function EdgeLayer(curved) {
  const L = {
    vao: gl.createVertexArray(),
    verts: curved ? 26 : 4,
    n: 0,
    b: [gl.createBuffer(), gl.createBuffer(), gl.createBuffer()],
  };
  gl.bindVertexArray(L.vao);
  attr(0, curved ? B_CURVE : B_LINE, 2, gl.FLOAT, false, 0);
  attr(1, L.b[0], 4, gl.FLOAT, false, 1);
  attr(2, L.b[1], 4, gl.FLOAT, false, 1);
  attr(3, L.b[2], 4, gl.UNSIGNED_BYTE, true, 1);
  gl.bindVertexArray(null);
  return L;
}
function NodeLayer() {
  const L = { vao: gl.createVertexArray(), n: 0, b: [gl.createBuffer(), gl.createBuffer(), gl.createBuffer()] };
  gl.bindVertexArray(L.vao);
  attr(0, B_QUAD, 2, gl.FLOAT, false, 0);
  attr(1, L.b[0], 4, gl.FLOAT, false, 1);
  attr(2, L.b[1], 4, gl.UNSIGNED_BYTE, true, 1);
  attr(3, L.b[2], 2, gl.UNSIGNED_BYTE, true, 1);
  gl.bindVertexArray(null);
  return L;
}
function FillLayer() {
  const L = { vao: gl.createVertexArray(), n: 0, b: [gl.createBuffer(), gl.createBuffer()] };
  gl.bindVertexArray(L.vao);
  attr(0, L.b[0], 2, gl.FLOAT, false, 0);
  attr(1, L.b[1], 4, gl.UNSIGNED_BYTE, true, 0);
  gl.bindVertexArray(null);
  return L;
}
export function upload(L, i, data, dynamic) {
  gl.bindBuffer(gl.ARRAY_BUFFER, L.b[i]);
  gl.bufferData(gl.ARRAY_BUFFER, data, dynamic ? gl.DYNAMIC_DRAW : gl.STATIC_DRAW);
}
export function patch(L, i, data) {
  gl.bindBuffer(gl.ARRAY_BUFFER, L.b[i]);
  gl.bufferSubData(gl.ARRAY_BUFFER, 0, data);
}

/**
 * Create the WebGL2 context, compile shaders and allocate layer buffers.
 * @returns {boolean} false when WebGL2 is unavailable (the caller shows a fallback)
 */
export function initGL() {
  gl = glc.getContext('webgl2', {
    antialias: false,
    alpha: false,
    depth: false,
    stencil: false,
    powerPreference: 'high-performance',
  });
  if (!gl) return false;
  P_BG = program(...SHADERS.P_BG);
  P_EDGE = program(...SHADERS.P_EDGE);
  P_NODE = program(...SHADERS.P_NODE);
  P_FILL = program(...SHADERS.P_FILL);
  B_CURVE = mkBuf(
    (() => {
      const a = [];
      for (let i = 0; i <= 12; i++) {
        const t = i / 12;
        a.push(t, -1, t, 1);
      }
      return new Float32Array(a);
    })(),
  );
  B_LINE = mkBuf(new Float32Array([0, -1, 0, 1, 1, -1, 1, 1]));
  B_QUAD = mkBuf(new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]));
  LY = {
    repoFill: FillLayer(),
    domFill: FillLayer(),
    repoLine: EdgeLayer(false),
    domLine: EdgeLayer(false),
    repoB: EdgeLayer(true),
    domB: EdgeLayer(true),
    svcB: EdgeLayer(true),
    leafE: EdgeLayer(true),
    focusE: EdgeLayer(true),
    routeCase: EdgeLayer(true),
    route: EdgeLayer(true),
    leaves: NodeLayer(),
    svcs: NodeLayer(),
  };
  return true;
}
