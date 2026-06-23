/** Product / app display name — keep in sync with app.json expo.name */
export const PRODUCT_NAME = "DevPet";

export const DEFAULT_PET_NAME = PRODUCT_NAME;

export const MAX_PET_NAME_LENGTH = 24;

export function normalizePetName(name: string): string {
  const trimmed = name.trim().slice(0, MAX_PET_NAME_LENGTH);
  return trimmed || DEFAULT_PET_NAME;
}
