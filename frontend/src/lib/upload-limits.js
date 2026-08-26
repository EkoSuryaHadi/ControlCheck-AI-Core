export const PUBLIC_BETA_MAX_UPLOAD_BYTES = 4 * 1024 * 1024

export function validatePublicBetaUpload(file) {
  if (file.size > PUBLIC_BETA_MAX_UPLOAD_BYTES) {
    return "File exceeds the 4 MB public beta limit. Use a smaller workbook for this beta."
  }
  return null
}

