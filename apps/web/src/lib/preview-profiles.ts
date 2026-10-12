import config from "../../../api/src/visual_director/preview_profiles.json";

export const PREVIEW_PROFILES = Object.fromEntries(config.profiles.map(profile => [
  profile.id,
  { ...profile, content_width: profile.viewport_width - 2 * config.body_padding_x },
]));
export const PREVIEW_NORMALIZATION_CSS = config.normalization_css + config.mobile_css;
