let gceOcrWorker = null;
let gceOcrProgress = null;

async function recognizeScreenshot(image, progress) {
  if (!window.Tesseract) throw new Error("문자 인식 파일을 불러오지 못했습니다. 새로고침 후 다시 시도해 주세요.");
  gceOcrProgress = progress;
  if (!gceOcrWorker) {
    gceOcrWorker = Tesseract.createWorker("eng", 1, {
      workerPath: new URL("/vendor/ocr/worker.min.js", location.origin).href,
      corePath: new URL("/vendor/ocr/core", location.origin).href,
      langPath: new URL("/vendor/ocr/lang", location.origin).href,
      workerBlobURL: false,
      gzip: true,
      logger: message => {
        if (message.status === "recognizing text") {
          gceOcrProgress?.(`브라우저에서 문제를 읽고 있습니다… ${Math.round(message.progress * 100)}%`);
        } else {
          gceOcrProgress?.("문자 인식을 준비하고 있습니다. 첫 실행은 잠시 걸릴 수 있습니다…");
        }
      }
    });
  }
  let timeout;
  const task = (async () => {
    const worker = await gceOcrWorker;
    await worker.setParameters({tessedit_pageseg_mode: "6"});
    const result = await worker.recognize(image);
    const text = result.data.text.trim();
    if (text.length < 8) throw new Error("문자를 충분히 읽지 못했습니다. 문제를 확대하거나 직접 입력해 주세요.");
    return text;
  })();
  try {
    return await Promise.race([
      task,
      new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error("문자 인식 시간이 초과되었습니다. 한 문제만 잘라서 다시 올려 주세요.")), 90000); })
    ]);
  } catch (error) {
    const old = gceOcrWorker;
    gceOcrWorker = null;
    old?.then(worker => worker.terminate()).catch(() => {});
    throw error;
  } finally {
    clearTimeout(timeout);
    gceOcrProgress = null;
  }
}
