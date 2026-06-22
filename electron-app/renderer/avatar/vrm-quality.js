import * as THREE from "three";

export const VRM_GRAPHICS_QUALITY_VALUES = Object.freeze(["low", "medium", "high"]);

const MIB = 1024 * 1024;
const MIP_FACTOR = 4 / 3;
const MIN_TEXTURE_DIMENSION = 128;

const QUALITY_PROFILES = Object.freeze({
  low: Object.freeze({
    id: "low",
    label: "Low",
    powerPreference: "low-power",
    precision: "mediump",
    antialias: false,
    pixelRatioCap: 1,
    textureMaxDimension: 512,
    textureBudgetBytes: 128 * MIB,
    anisotropy: 1,
    targetFps: 30,
    materialMode: "unlit"
  }),
  medium: Object.freeze({
    id: "medium",
    label: "Medium",
    powerPreference: "default",
    precision: "highp",
    antialias: true,
    pixelRatioCap: 1.25,
    textureMaxDimension: 1024,
    textureBudgetBytes: 256 * MIB,
    anisotropy: 4,
    targetFps: 60,
    materialMode: "authored"
  }),
  high: Object.freeze({
    id: "high",
    label: "High",
    powerPreference: "high-performance",
    precision: "highp",
    antialias: true,
    pixelRatioCap: 2,
    textureMaxDimension: 4096,
    textureBudgetBytes: 512 * MIB,
    anisotropy: 8,
    targetFps: 60,
    materialMode: "authored"
  })
});

const MATERIAL_TEXTURE_KEYS = Object.freeze([
  "map",
  "alphaMap",
  "aoMap",
  "bumpMap",
  "displacementMap",
  "emissiveMap",
  "envMap",
  "lightMap",
  "metalnessMap",
  "normalMap",
  "roughnessMap",
  "gradientMap",
  "shadeMultiplyTexture",
  "shadingShiftTexture",
  "matcapTexture",
  "rimMultiplyTexture",
  "outlineWidthMultiplyTexture",
  "uvAnimationMaskTexture"
]);

const SRGB_TEXTURE_ROLES = new Set([
  "map",
  "emissiveMap",
  "shadeMultiplyTexture",
  "matcapTexture",
  "rimMultiplyTexture"
]);

function fitDimensionsWithinMax(width, height, maxDimension) {
  const safeWidth = Math.max(1, Math.round(Number(width) || 1));
  const safeHeight = Math.max(1, Math.round(Number(height) || 1));
  const safeMax = Math.max(1, Math.round(Number(maxDimension) || 1));
  if (safeWidth <= safeMax && safeHeight <= safeMax) {
    return { width: safeWidth, height: safeHeight };
  }
  const scale = safeMax / Math.max(safeWidth, safeHeight);
  return {
    width: Math.max(1, Math.round(safeWidth * scale)),
    height: Math.max(1, Math.round(safeHeight * scale))
  };
}

function estimateTextureBytes(width, height) {
  return Math.max(1, width) * Math.max(1, height) * 4 * MIP_FACTOR;
}

function getTextureRolePriority(roles) {
  const roleSet = roles instanceof Set ? roles : new Set(roles || []);
  if (roleSet.has("map") || roleSet.has("alphaMap")) {
    return 4;
  }
  if (
    roleSet.has("normalMap") ||
    roleSet.has("shadeMultiplyTexture") ||
    roleSet.has("shadingShiftTexture")
  ) {
    return 3;
  }
  if (
    roleSet.has("emissiveMap") ||
    roleSet.has("matcapTexture") ||
    roleSet.has("rimMultiplyTexture")
  ) {
    return 2;
  }
  return 1;
}

function getTextureDimensions(texture) {
  const image = texture?.image;
  return {
    width: Number(image?.naturalWidth || image?.videoWidth || image?.width || 0),
    height: Number(image?.naturalHeight || image?.videoHeight || image?.height || 0)
  };
}

function addTextureEntry(entries, texture, role) {
  if (!texture?.isTexture) {
    return;
  }
  let entry = entries.get(texture);
  if (!entry) {
    entry = { texture, roles: new Set() };
    entries.set(texture, entry);
  }
  entry.roles.add(String(role || "uniform"));
}

export function normalizeVrmGraphicsQuality(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return VRM_GRAPHICS_QUALITY_VALUES.includes(normalized) ? normalized : "medium";
}

export function getVrmQualityProfile(value) {
  return QUALITY_PROFILES[normalizeVrmGraphicsQuality(value)];
}

export function getVrmRendererOptions(value, canvas) {
  const profile = getVrmQualityProfile(value);
  return {
    canvas,
    antialias: profile.antialias,
    alpha: true,
    premultipliedAlpha: false,
    powerPreference: profile.powerPreference,
    precision: profile.precision,
    failIfMajorPerformanceCaveat: false
  };
}

export function collectMaterialTextures(material) {
  const entries = new Map();
  if (!material) {
    return entries;
  }
  for (const key of MATERIAL_TEXTURE_KEYS) {
    try {
      addTextureEntry(entries, material[key], key);
    } catch (_) {
      // Some shader material accessors can throw before their uniforms are initialized.
    }
  }
  for (const [uniformName, uniform] of Object.entries(material.uniforms || {})) {
    const value = uniform?.value;
    if (value?.isTexture) {
      addTextureEntry(entries, value, uniformName);
    } else if (Array.isArray(value)) {
      for (const item of value) {
        addTextureEntry(entries, item, uniformName);
      }
    }
  }
  return entries;
}

export function collectVrmTextureEntries(vrm) {
  const entries = new Map();
  vrm?.scene?.traverse?.((child) => {
    const materials = child?.material
      ? (Array.isArray(child.material) ? child.material : [child.material])
      : [];
    for (const material of materials) {
      for (const [texture, materialEntry] of collectMaterialTextures(material)) {
        let entry = entries.get(texture);
        if (!entry) {
          entry = { texture, roles: new Set() };
          entries.set(texture, entry);
        }
        for (const role of materialEntry.roles) {
          entry.roles.add(role);
        }
      }
    }
  });
  return Array.from(entries.values());
}

export function createVrmTexturePlan(vrm, renderer, quality) {
  const profile = getVrmQualityProfile(quality);
  const capabilityMax = Math.max(
    1,
    Number(renderer?.capabilities?.maxTextureSize) || profile.textureMaxDimension
  );
  const profileMax = Math.min(profile.textureMaxDimension, capabilityMax);
  const entries = [];

  for (const collected of collectVrmTextureEntries(vrm)) {
    const { width, height } = getTextureDimensions(collected.texture);
    if (!width || !height) {
      continue;
    }
    const target = fitDimensionsWithinMax(width, height, profileMax);
    entries.push({
      ...collected,
      sourceWidth: width,
      sourceHeight: height,
      targetWidth: target.width,
      targetHeight: target.height,
      priority: getTextureRolePriority(collected.roles),
      estimatedBytes: estimateTextureBytes(target.width, target.height)
    });
  }

  let estimatedBytes = entries.reduce((total, entry) => total + entry.estimatedBytes, 0);
  while (estimatedBytes > profile.textureBudgetBytes) {
    const candidate = entries
      .filter((entry) => Math.max(entry.targetWidth, entry.targetHeight) > MIN_TEXTURE_DIMENSION)
      .sort((left, right) => (
        left.priority - right.priority ||
        right.estimatedBytes - left.estimatedBytes
      ))[0];
    if (!candidate) {
      break;
    }
    const nextMax = Math.max(
      MIN_TEXTURE_DIMENSION,
      Math.floor(Math.max(candidate.targetWidth, candidate.targetHeight) / 2)
    );
    const target = fitDimensionsWithinMax(
      candidate.sourceWidth,
      candidate.sourceHeight,
      nextMax
    );
    estimatedBytes -= candidate.estimatedBytes;
    candidate.targetWidth = target.width;
    candidate.targetHeight = target.height;
    candidate.estimatedBytes = estimateTextureBytes(target.width, target.height);
    estimatedBytes += candidate.estimatedBytes;
  }

  return {
    profile,
    entries,
    sourceTextureCount: entries.length,
    estimatedBytes,
    estimatedMegabytes: estimatedBytes / MIB,
    capabilityMaxTextureSize: capabilityMax,
    budgetMegabytes: profile.textureBudgetBytes / MIB
  };
}

export function configureTextureSampling(texture, roles, renderer, quality) {
  if (!texture?.isTexture) {
    return;
  }
  const profile = getVrmQualityProfile(quality);
  const maxAnisotropy = Math.max(
    1,
    Number(renderer?.capabilities?.getMaxAnisotropy?.()) || 1
  );
  const { width, height } = getTextureDimensions(texture);
  const supportsMipmaps = Boolean(
    renderer?.capabilities?.isWebGL2 ||
    THREE.MathUtils.isPowerOfTwo(width) && THREE.MathUtils.isPowerOfTwo(height)
  );
  texture.anisotropy = Math.min(profile.anisotropy, maxAnisotropy);
  texture.generateMipmaps = supportsMipmaps;
  texture.minFilter = supportsMipmaps
    ? THREE.LinearMipmapLinearFilter
    : THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  const roleSet = roles instanceof Set ? roles : new Set(roles || []);
  if (
    "colorSpace" in texture &&
    THREE.SRGBColorSpace &&
    Array.from(roleSet).some((role) => SRGB_TEXTURE_ROLES.has(role))
  ) {
    texture.colorSpace = THREE.SRGBColorSpace;
  }
  texture.needsUpdate = true;
}

export function createCompatibilityMaterial(sourceMaterial) {
  const color =
    sourceMaterial?.color ||
    sourceMaterial?.litFactor ||
    sourceMaterial?.uniforms?.litFactor?.value;
  const map = sourceMaterial?.map?.isTexture ? sourceMaterial.map : null;
  const alphaMap = sourceMaterial?.alphaMap?.isTexture ? sourceMaterial.alphaMap : null;
  const opacity = Number.isFinite(Number(sourceMaterial?.opacity))
    ? Number(sourceMaterial.opacity)
    : 1;
  const material = new THREE.MeshBasicMaterial({
    color: color?.isColor ? color.clone() : new THREE.Color(0xffffff),
    map,
    alphaMap,
    transparent: Boolean(sourceMaterial?.transparent) || opacity < 1 || Boolean(alphaMap),
    opacity,
    alphaTest: Number.isFinite(Number(sourceMaterial?.alphaTest))
      ? Number(sourceMaterial.alphaTest)
      : 0,
    side: sourceMaterial?.side ?? THREE.FrontSide,
    depthWrite: sourceMaterial?.depthWrite ?? true,
    depthTest: sourceMaterial?.depthTest ?? true,
    vertexColors: Boolean(sourceMaterial?.vertexColors)
  });
  material.name = sourceMaterial?.name
    ? `${sourceMaterial.name}-low-quality`
    : "vrm-low-quality";
  material.blending = sourceMaterial?.blending ?? material.blending;
  material.blendSrc = sourceMaterial?.blendSrc ?? material.blendSrc;
  material.blendDst = sourceMaterial?.blendDst ?? material.blendDst;
  material.blendEquation = sourceMaterial?.blendEquation ?? material.blendEquation;
  material.premultipliedAlpha = Boolean(sourceMaterial?.premultipliedAlpha);
  material.userData = {
    ...(sourceMaterial?.userData || {}),
    catbotSourceMaterialType: sourceMaterial?.type || ""
  };
  return material;
}

export function getRendererCapabilitySummary(renderer, quality) {
  const profile = getVrmQualityProfile(quality);
  const context = renderer?.getContext?.();
  return {
    requestedQuality: profile.id,
    effectiveQuality: profile.id,
    materialMode: profile.materialMode,
    targetFps: profile.targetFps,
    pixelRatio: Number(renderer?.getPixelRatio?.()) || 1,
    antialias: Boolean(context?.getContextAttributes?.()?.antialias),
    webgl2: Boolean(renderer?.capabilities?.isWebGL2),
    maxTextureSize: Number(renderer?.capabilities?.maxTextureSize) || 0,
    maxAnisotropy: Number(renderer?.capabilities?.getMaxAnisotropy?.()) || 1,
    precision: renderer?.capabilities?.precision || profile.precision
  };
}
