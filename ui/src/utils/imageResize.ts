// BlackBoard/ui/src/utils/imageResize.ts
/**
 * Resize an image file to fit within maxDimension pixels on the longest edge.
 * Returns a base64 data URI (image/png or image/jpeg).
 */
export function resizeImage(
  file: File,
  maxDimension: number = 1024,
  maxSizeBytes: number = 1_400_000,
): Promise<string | null> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        let { width, height } = img;

        // Only resize if larger than maxDimension
        if (width > maxDimension || height > maxDimension) {
          const ratio = Math.min(maxDimension / width, maxDimension / height);
          width = Math.round(width * ratio);
          height = Math.round(height * ratio);
        }

        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        if (!ctx) { resolve(null); return; }

        ctx.drawImage(img, 0, 0, width, height);

        // Try JPEG first (smaller), fall back to PNG
        let dataUrl = canvas.toDataURL('image/jpeg', 0.85);
        if (dataUrl.length > maxSizeBytes) {
          dataUrl = canvas.toDataURL('image/jpeg', 0.6);
        }
        if (dataUrl.length > maxSizeBytes) {
          resolve(null); // Still too large
          return;
        }
        resolve(dataUrl);
      };
      img.onerror = () => resolve(null);
      img.src = reader.result as string;
    };
    reader.onerror = () => resolve(null);
    reader.readAsDataURL(file);
  });
}
