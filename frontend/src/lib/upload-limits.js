export const PUBLIC_BETA_MAX_UPLOAD_BYTES = 4 * 1024 * 1024
// Workbooks above the synchronous (serverless) limit go through the
// browser → R2 presigned-PUT → VPS worker queue path.
export const ASYNC_UPLOAD_MAX_BYTES = 500 * 1024 * 1024

export function validatePublicBetaUpload(file) {
  if (file.size > ASYNC_UPLOAD_MAX_BYTES) {
    return "File exceeds the 500 MB worker-upload limit."
  }
  return null
}

export function shouldUseAsyncUpload(file) {
  return file.size > PUBLIC_BETA_MAX_UPLOAD_BYTES
}
