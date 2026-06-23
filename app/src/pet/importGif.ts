import * as ImagePicker from "expo-image-picker";
import * as FileSystem from "expo-file-system/legacy";
import type { PetState } from "@protocol/index";

const MAX_BYTES = 5_000_000;

export type ImportGifErrorCode =
  | "gif_permission_denied"
  | "gif_not_gif"
  | "gif_too_large"
  | "gif_no_document_dir";

export class ImportGifError extends Error {
  readonly code: ImportGifErrorCode;

  constructor(code: ImportGifErrorCode) {
    super(code);
    this.code = code;
  }
}

function petGifDir(): string {
  const base = FileSystem.documentDirectory;
  if (!base) throw new ImportGifError("gif_no_document_dir");
  return `${base}pet-gifs/`;
}

function isGifAsset(asset: ImagePicker.ImagePickerAsset): boolean {
  const name = (asset.fileName ?? asset.uri.split("/").pop() ?? "").toLowerCase();
  return name.endsWith(".gif") || asset.mimeType === "image/gif";
}

/** Pick a GIF from the library and copy it into app storage for the given pet state. */
export async function importPetGif(state: PetState): Promise<string | null> {
  const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!perm.granted) {
    throw new ImportGifError("gif_permission_denied");
  }

  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ["images"],
    allowsEditing: false,
    quality: 1,
  });
  if (result.canceled || !result.assets?.[0]) return null;

  const asset = result.assets[0];
  if (!isGifAsset(asset)) {
    throw new ImportGifError("gif_not_gif");
  }

  const info = await FileSystem.getInfoAsync(asset.uri);
  if (info.exists && "size" in info && typeof info.size === "number" && info.size > MAX_BYTES) {
    throw new ImportGifError("gif_too_large");
  }

  const dir = petGifDir();
  await FileSystem.makeDirectoryAsync(dir, { intermediates: true });
  const dest = `${dir}${state}.gif`;
  await FileSystem.deleteAsync(dest, { idempotent: true });
  await FileSystem.copyAsync({ from: asset.uri, to: dest });
  return dest;
}
