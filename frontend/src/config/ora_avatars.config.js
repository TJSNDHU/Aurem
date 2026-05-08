/**
 * AUREM — ORA Avatar Config (Phase 1)
 * iter 322v · 2026-02-06
 *
 * 6 avatars · 2 active by default (founder unlocks the rest from
 * /admin/avatar-manager). Personality scaffolding is consumed by the
 * voice engine (Phase 4+) and the selector UI (Phase 2).
 *
 * NOTE: glb_url + thumbnail paths are placeholders. The selector
 * component already renders an emoji fallback when the image 404s,
 * so missing assets degrade gracefully — no crashes.
 */

const _PERSONALITY_DEFAULT = {
  weekday: "professional",
  evening: "casual",
  weekend: "warm",
  address: "sir or first name if known",
  style: "crisp, confident, slight dry wit",
};

export const ORA_AVATARS = [
  {
    id: "ora_female_1",
    name: "ORA",
    gender: "female",
    ethnicity: "south_asian",
    voice_id: "cartesia_warm_female_en_ca",
    elevenlabs_voice_id: "21m00Tcm4TlvDq8ikWAM",
    glb_url: "/avatars/ora_female_1.glb",
    thumbnail: "/avatars/thumbs/ora_female_1.jpg",
    emoji: "🧕",
    personality: { ..._PERSONALITY_DEFAULT },
    status: "active",
  },
  {
    id: "ora_female_2",
    name: "ORA",
    gender: "female",
    ethnicity: "east_asian",
    voice_id: "cartesia_warm_female_en_ca",
    elevenlabs_voice_id: "",
    glb_url: "/avatars/ora_female_2.glb",
    thumbnail: "/avatars/thumbs/ora_female_2.jpg",
    emoji: "👩‍🦱",
    personality: { ..._PERSONALITY_DEFAULT },
    status: "draft",
  },
  {
    id: "ora_female_3",
    name: "ORA",
    gender: "female",
    ethnicity: "black",
    voice_id: "cartesia_warm_female_en_ca",
    elevenlabs_voice_id: "",
    glb_url: "/avatars/ora_female_3.glb",
    thumbnail: "/avatars/thumbs/ora_female_3.jpg",
    emoji: "👩🏾",
    personality: { ..._PERSONALITY_DEFAULT },
    status: "draft",
  },
  {
    id: "ora_male_1",
    name: "ORION",
    gender: "male",
    ethnicity: "south_asian",
    voice_id: "cartesia_confident_male_en_ca",
    elevenlabs_voice_id: "pNInz6obpgDQGcFmaJgB",
    glb_url: "/avatars/ora_male_1.glb",
    thumbnail: "/avatars/thumbs/ora_male_1.jpg",
    emoji: "🧑",
    personality: { ..._PERSONALITY_DEFAULT, style: "crisp, confident, authoritative" },
    status: "active",
  },
  {
    id: "ora_male_2",
    name: "ORION",
    gender: "male",
    ethnicity: "white",
    voice_id: "cartesia_confident_male_en_ca",
    elevenlabs_voice_id: "",
    glb_url: "/avatars/ora_male_2.glb",
    thumbnail: "/avatars/thumbs/ora_male_2.jpg",
    emoji: "👨",
    personality: { ..._PERSONALITY_DEFAULT },
    status: "draft",
  },
  {
    id: "ora_male_3",
    name: "ORION",
    gender: "male",
    ethnicity: "black",
    voice_id: "cartesia_confident_male_en_ca",
    elevenlabs_voice_id: "",
    glb_url: "/avatars/ora_male_3.glb",
    thumbnail: "/avatars/thumbs/ora_male_3.jpg",
    emoji: "👨🏾",
    personality: { ..._PERSONALITY_DEFAULT },
    status: "draft",
  },
];

export const AVATAR_SETTINGS = {
  default_male_customer: "ora_female_1",
  default_female_customer: "ora_male_1",
  default_unknown: "ora_female_1",
  allow_customer_selection: true,
  max_visible_in_picker: 6,
  founder_preview_mode: true,
};

export const LOCAL_STORAGE_KEY = "ora_selected_avatar";

/** Lookup helper. Returns null if id not found. */
export function getAvatarById(id) {
  if (!id) return null;
  return ORA_AVATARS.find((a) => a.id === id) || null;
}

/** Visible avatars for the selector (status === "active"). */
export function getActiveAvatars() {
  return ORA_AVATARS.filter((a) => a.status === "active").slice(0, AVATAR_SETTINGS.max_visible_in_picker);
}

/** Default avatar to load when no customer selection has been made yet. */
export function getDefaultAvatar(customerGender) {
  if (customerGender === "male") return getAvatarById(AVATAR_SETTINGS.default_male_customer);
  if (customerGender === "female") return getAvatarById(AVATAR_SETTINGS.default_female_customer);
  return getAvatarById(AVATAR_SETTINGS.default_unknown);
}
