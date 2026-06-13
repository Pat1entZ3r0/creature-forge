import * as THREE from "three";

// A PS1-era look grafted onto a standard, skinning-capable material via
// onBeforeCompile — so glTF skinning, fog and lighting keep working while we add:
//   • clip-space vertex snapping (the fixed-point vertex jitter of the hardware)
//   • Bayer-ordered dithering + color-depth reduction (15-bit framebuffer feel)
// The affine/perspective-incorrect texture warp is the third classic artifact,
// but this asset ships vertex colors (no textures), so it does not apply here —
// faithfully, because the real pipeline ships vertex colors too.

export type Ps1Uniforms = {
  uSnap: { value: number }; // grid resolution; lower = chunkier jitter
  uPS1: { value: number }; // 0..1 master mix
  uDither: { value: number }; // dither strength
  uLevels: { value: number }; // quantized color levels per channel
};

export type Ps1Material = THREE.MeshStandardMaterial & {
  userData: { ps1: Ps1Uniforms };
};

export function makePs1Material(): Ps1Material {
  const mat = new THREE.MeshStandardMaterial({
    vertexColors: true,
    flatShading: true,
    roughness: 0.95,
    metalness: 0.0,
  }) as Ps1Material;

  const u: Ps1Uniforms = {
    uSnap: { value: 72 },
    uPS1: { value: 1 },
    uDither: { value: 1 },
    uLevels: { value: 28 },
  };
  mat.userData.ps1 = u;

  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uSnap = u.uSnap;
    shader.uniforms.uPS1 = u.uPS1;
    shader.uniforms.uDither = u.uDither;
    shader.uniforms.uLevels = u.uLevels;

    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
        uniform float uSnap;
        uniform float uPS1;`
      )
      .replace(
        "#include <project_vertex>",
        `#include <project_vertex>
        {
          vec4 snapped = gl_Position;
          snapped.xyz /= snapped.w;
          snapped.xy = floor(snapped.xy * uSnap) / uSnap;
          snapped.xyz *= snapped.w;
          gl_Position = mix(gl_Position, snapped, uPS1);
        }`
      );

    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        uniform float uPS1;
        uniform float uDither;
        uniform float uLevels;
        // recursive Bayer construction — array-free, WebGL1/2 safe
        float bayer2(vec2 a){ a = floor(a); return fract(a.x / 2.0 + a.y * a.y * 0.75); }
        float bayer4(vec2 a){ return bayer2(0.5 * a) * 0.25 + bayer2(a); }`
      )
      .replace(
        "#include <dithering_fragment>",
        `#include <dithering_fragment>
        {
          float threshold = (bayer4(gl_FragCoord.xy) - 0.5);
          vec3 c = gl_FragColor.rgb + threshold * uDither / uLevels;
          c = floor(c * uLevels + 0.5) / uLevels;
          gl_FragColor.rgb = mix(gl_FragColor.rgb, c, uPS1);
        }`
      );
  };

  return mat;
}
