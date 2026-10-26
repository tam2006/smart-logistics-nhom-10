"use strict";

(() => {
  async function decodeImage(file, canvas) {
    if (typeof window.jsQR !== "function") {
      throw new Error("Chưa tải được thư viện jsQR.");
    }

    if (
      !file ||
      !["image/png", "image/jpeg"].includes(file.type)
    ) {
      throw new Error("Chỉ nhận ảnh PNG hoặc JPEG.");
    }

    if (file.size > 5 * 1024 * 1024) {
      throw new Error("Ảnh vượt 5 MB.");
    }

    const start = performance.now();
    let bitmap;

    try {
      bitmap = await createImageBitmap(file);
    } catch {
      throw new Error("Không mở được file ảnh.");
    }

    try {
      if (bitmap.width * bitmap.height > 20000000) {
        throw new Error("Ảnh vượt 20 triệu điểm ảnh.");
      }

      const scale = Math.min(
        1,
        1600 / Math.max(bitmap.width, bitmap.height)
      );

      canvas.width = Math.max(
        1,
        Math.round(bitmap.width * scale)
      );

      canvas.height = Math.max(
        1,
        Math.round(bitmap.height * scale)
      );

      const ctx = canvas.getContext(
        "2d",
        { willReadFrequently: true }
      );

      if (!ctx) {
        throw new Error("Không tạo được khung đọc ảnh.");
      }

      ctx.fillStyle = "white";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.drawImage(
        bitmap,
        0,
        0,
        canvas.width,
        canvas.height
      );

      const pixels = ctx.getImageData(
        0,
        0,
        canvas.width,
        canvas.height
      );

      const decoded = window.jsQR(
        pixels.data,
        pixels.width,
        pixels.height,
        { inversionAttempts: "attemptBoth" }
      );

      return {
        code: decoded ? decoded.data : "",
        found: Boolean(decoded),
        readMs: performance.now() - start,
      };
    } finally {
      bitmap.close();
    }
  }

  window.SmartLogisticsQR = Object.freeze({
    decoderVersion: "jsqr-canvas-v1",
    decodeImage,
  });
})();