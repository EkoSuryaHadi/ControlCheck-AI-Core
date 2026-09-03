export const PUBLIC_BETA_MAX_UPLOAD_BYTES = 4 * 1024 * 1024
// Workbooks above the synchronous (serverless) limit go through the
// browser → R2 presigned-PUT → VPS worker queue path.
export const ASYNC_UPLOAD_MAX_BYTES = 500 * 1024 * 1024

const MS_PROJECT_EXTENSIONS = [".mpp", ".mpx"]

export function isMsProjectFile(file) {
  const lower = file.name.toLowerCase()
  return MS_PROJECT_EXTENSIONS.some((ext) => lower.endsWith(ext))
}

export function validatePublicBetaUpload(file) {
  if (file.size > ASYNC_UPLOAD_MAX_BYTES) {
    return "File exceeds the 500 MB worker-upload limit."
  }
  return null
}

export function shouldUseAsyncUpload(file) {
  // .mpp/.mpx are converted on the VPS worker (MPXJ needs a JVM, which the
  // serverless API does not have), so they always take the async path.
  return isMsProjectFile(file) || file.size > PUBLIC_BETA_MAX_UPLOAD_BYTES
}
